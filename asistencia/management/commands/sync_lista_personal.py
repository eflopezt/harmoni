"""
Sincroniza Lista_Personal.xlsx con BD Personal.

Acciones:
  - Cesa empleados que Excel marca cesados (Estado=False) y están activos en BD.
    Actualiza estado='Cesado', fecha_cese, motivo_cese.
  - Crea empleados nuevos ACTIVOS que no existen en BD
    (nro_doc, apellidos_nombres, condicion, cargo, fecha_alta, celular, sexo).
  - NO crea cesados históricos (solo si --incluir-cesados-historicos).
  - NO modifica condicion/cargo de empleados ya existentes (política segura).

Uso:
    python manage.py sync_lista_personal /tmp/Lista_Personal.xlsx
    python manage.py sync_lista_personal /tmp/Lista_Personal.xlsx --dry-run
    python manage.py sync_lista_personal /tmp/Lista_Personal.xlsx --incluir-cesados-historicos
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError

from empresas.models import Empresa
from personal.models import Personal


def _norm_condicion(val):
    """Normaliza condicion a LOCAL / FORANEO / LIMA (sin tilde)."""
    if pd.isna(val):
        return 'LOCAL'
    s = (str(val).upper()
         .replace('\ufffd', 'N')  # char reemplazo del encoding
         .replace('Á', 'A')
         .replace('É', 'E')
         .replace('Í', 'I')
         .replace('Ó', 'O')
         .replace('Ú', 'U')
         .replace('Ñ', 'N'))
    # Casos post-normalización
    if 'FORANEO' in s or 'FORNEO' in s:
        return 'FORANEO'
    if 'LIMA' in s:
        return 'LIMA'
    return 'LOCAL'


def _parse_fecha(val):
    if pd.isna(val):
        return None
    try:
        return pd.to_datetime(val).date()
    except Exception:
        return None


def _fix_str(val):
    """Reemplaza chars de encoding en strings."""
    if pd.isna(val):
        return ''
    s = str(val)
    # Heurística: '�' viene casi siempre por Ñ o Á/É/Í/Ó/Ú
    # Para nombres, asumir Ñ (más común en nombres hispanos).
    return s.replace('\ufffd', 'Ñ')


class Command(BaseCommand):
    help = 'Sincroniza Lista_Personal.xlsx con BD Personal (ceses + nuevos ingresos).'

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al Excel Lista_Personal.xlsx')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--incluir-cesados-historicos', action='store_true',
                            help='También crea los cesados que no están en BD.')

    def handle(self, *args, **opts):
        ruta = Path(opts['archivo'])
        if not ruta.exists():
            raise CommandError(f'Archivo no encontrado: {ruta}')
        dry = opts['dry_run']
        incluir_hist = opts['incluir_cesados_historicos']

        df = pd.read_excel(ruta, sheet_name='Sheet', dtype=str)
        df['DNI'] = df['DNI'].astype(str).str.strip()
        df['_activo'] = df['Estado'] == 'True'
        df['_condicion'] = df['Condicion'].map(_norm_condicion)
        df['_fecha_ingreso'] = df['FechaIngreso'].map(_parse_fecha)
        df['_fecha_cese'] = df['FechaCese'].map(_parse_fecha)
        df['_nombres'] = df['Personal'].map(_fix_str)
        df['_cargo'] = df['Cargo'].map(_fix_str)
        df['_motivo_cese'] = df['MotivoCese'].map(_fix_str)
        df['_lugar'] = df['Lugar Trabajo'].map(_fix_str)

        empresa = Empresa.objects.first()
        if not empresa:
            raise CommandError('No hay Empresa en BD')
        self.stdout.write(f'Empresa: {empresa.razon_social}')

        bd_dnis = set(Personal.objects.values_list('nro_doc', flat=True))
        bd_activos = set(Personal.objects.filter(estado='Activo').values_list('nro_doc', flat=True))
        excel_dnis = set(df['DNI'].tolist())

        nuevos = excel_dnis - bd_dnis
        excel_cesados = set(df[~df['_activo']]['DNI'])
        a_cesar = excel_cesados & bd_activos

        self.stdout.write(f'\n=== RESUMEN ===')
        self.stdout.write(f'BD: {len(bd_dnis)} | Excel: {len(excel_dnis)}')
        self.stdout.write(f'Nuevos a crear: {len(nuevos)}  '
                          f'(activos={len(df[df["DNI"].isin(nuevos) & df["_activo"]])}, '
                          f'cesados-hist={len(df[df["DNI"].isin(nuevos) & ~df["_activo"]])})')
        self.stdout.write(f'A cesar (activos BD → cesados Excel): {len(a_cesar)}')

        # ── 1) Cesar empleados ─────────────────────────────────────
        self.stdout.write(f'\n=== CESAR {len(a_cesar)} ===')
        cesados_ok = 0
        for dni in sorted(a_cesar):
            row = df[df['DNI'] == dni].iloc[0]
            p = Personal.objects.get(nro_doc=dni)
            fcese = row['_fecha_cese']
            motivo = row['_motivo_cese'][:20] if row['_motivo_cese'] else ''
            self.stdout.write(f'  {dni} {p.apellidos_nombres[:40]:40s} -> Cesado {fcese} ({motivo})')
            if not dry:
                p.estado = 'Cesado'
                p.fecha_cese = fcese
                p.motivo_cese = motivo
                p.save()
            cesados_ok += 1

        # ── 2) Crear nuevos ────────────────────────────────────────
        a_crear = df[df['DNI'].isin(nuevos)]
        if not incluir_hist:
            a_crear = a_crear[a_crear['_activo']]
        self.stdout.write(f'\n=== CREAR {len(a_crear)} ===')
        creados_ok = 0
        for _, row in a_crear.iterrows():
            dni = row['DNI']
            estado = 'Activo' if row['_activo'] else 'Cesado'
            cond = row['_condicion']
            cargo = row['_cargo'][:100] if row['_cargo'] else ''
            lugar = row['_lugar'][:80] if row['_lugar'] else ''
            fecha_alta = row['_fecha_ingreso'] or date.today()
            fecha_cese = row['_fecha_cese'] if estado == 'Cesado' else None
            motivo_cese = row['_motivo_cese'][:20] if row['_motivo_cese'] else ''
            tipo_doc = (row.get('TipoDoc') or 'DNI')
            # Nombres pueden venir como "APELLIDOS, NOMBRES" → dejar tal cual
            nombres = (row['_nombres'] or '').strip()
            self.stdout.write(
                f'  {dni:10s} {nombres[:38]:38s} {estado:7s} '
                f'{cond:8s} alta={fecha_alta} cargo={cargo[:25]}'
            )
            if not dry:
                Personal.objects.create(
                    empresa=empresa,
                    nro_doc=dni,
                    tipo_doc=tipo_doc,
                    apellidos_nombres=nombres,
                    condicion=cond,
                    cargo=cargo,
                    fecha_alta=fecha_alta,
                    fecha_cese=fecha_cese,
                    motivo_cese=motivo_cese,
                    estado=estado,
                    # valores razonables por defecto
                    grupo_tareo='STAFF' if cond != 'FORANEO' else 'RCO',
                    jornada_horas=(Decimal('11.0') if cond == 'FORANEO' else Decimal('8.5')),
                )
            creados_ok += 1

        # ── Reporte ────────────────────────────────────────────────
        self.stdout.write(f'\n=== DONE ===')
        self.stdout.write(f'Cesados: {cesados_ok}')
        self.stdout.write(f'Creados: {creados_ok}')
        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN - no se guardó.'))
