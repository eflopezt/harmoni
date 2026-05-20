"""
Management command: sync_matrix_contratos
==========================================
Sincroniza datos de la MATRIX DE CONTRATOS 2026 (Excel) con la BD:

  - Sueldo base
  - Asignación de alimentación
  - Área (subarea) → mapeo fuzzy con las subareas existentes
  - Fecha fin de contrato (ULTIMA PRORROGA)
  - Correo corporativo
  - Hospedaje (viaticos_mensual si existe el campo)

Reglas:
  - NUNCA actualiza condicion (LOCAL/FORANEO) de empleados existentes
  - NUNCA crea empleados nuevos (solo actualiza)
  - El área se asigna solo si se encuentra una subarea válida en BD
  - Solo actualiza campos no vacíos/nulos del Excel

Uso:
    python manage.py sync_matrix_contratos
    python manage.py sync_matrix_contratos --dry-run
    python manage.py sync_matrix_contratos --solo sueldo
    python manage.py sync_matrix_contratos --solo area
"""
from __future__ import annotations

import unicodedata
from decimal import Decimal, InvalidOperation
from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

ARCHIVO_MATRIX = Path(
    r"C:\Users\EDWIN LOPEZ\RIPCON\Proyectos Perú - Recursos humanos (1)"
    r"\02 Administración de Personal\Control de Contratos"
    r"\MATRIX DE CONTRATOS NUEVO 2026.xlsx"
)


def _sin_tildes(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )


def _norm(s) -> str:
    return _sin_tildes(str(s or '')).upper().strip()


def _norm_dni(val) -> str:
    if val is None:
        return ''
    s = str(val).strip().split('.')[0].replace(' ', '')
    return s.zfill(8) if s.isdigit() else s


def _parse_decimal(val) -> Decimal | None:
    try:
        v = str(val).strip().replace(',', '.')
        if not v or v.lower() in ('nan', 'none', '-'):
            return None
        return Decimal(v)
    except (InvalidOperation, ValueError):
        return None


def _parse_fecha(val) -> date | None:
    if val is None:
        return None
    import pandas as pd
    if hasattr(val, 'date'):
        return val.date() if hasattr(val, 'date') and callable(val.date) else None
    try:
        ts = pd.Timestamp(val)
        if pd.isna(ts):
            return None
        return ts.date()
    except Exception:
        return None


def _build_subarea_map():
    """
    Construye mapa: norm(nombre_subarea) → SubArea ORM object.
    También indexa por norm(nombre_area) para fallback.
    """
    from personal.models import SubArea
    m = {}
    for sa in SubArea.objects.select_related('area').all():
        # Clave principal: nombre normalizado de la subarea
        k = _norm(sa.nombre)
        if k not in m:
            m[k] = sa
        # Clave secundaria: nombre del area normalizado
        ka = _norm(sa.area.nombre)
        if ka not in m:
            m[ka] = sa
    return m


def _buscar_subarea(area_excel: str, subarea_map: dict):
    """
    Busca la SubArea que mejor coincide con el texto del Excel.
    Estrategia:
      1. Exact match
      2. Strip trailing spaces
      3. Prefix match (e.g. "CALIDAD INTERVENCION LORENA" → "CALIDAD")
    """
    if not area_excel or not area_excel.strip():
        return None

    clave = _norm(area_excel)

    # Exact
    if clave in subarea_map:
        return subarea_map[clave]

    # Prefix: busca la subarea cuyo nombre normalizado el Excel empieza con él
    # (para casos como "CALIDAD INTERVENCION LORENA" → CALIDAD)
    for k, sa in subarea_map.items():
        if clave.startswith(k) and len(k) >= 3:
            return sa

    # Contained: el Excel contiene el nombre de la subarea
    for k, sa in subarea_map.items():
        if k in clave and len(k) >= 5:
            return sa

    return None


class Command(BaseCommand):
    help = 'Sincroniza Matrix de Contratos 2026 (Excel) con la BD'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra cambios sin guardar')
        parser.add_argument('--solo', choices=['sueldo', 'area', 'contrato', 'correo'],
                            help='Actualizar solo un tipo de dato')

    def handle(self, *args, **options):
        try:
            import pandas as pd
        except ImportError:
            raise CommandError('Instalar pandas: pip install pandas openpyxl')

        self.dry  = options['dry_run']
        self.solo = options.get('solo')
        pd_mod    = pd

        if self.dry:
            self.stdout.write('=== DRY-RUN: no se guardara nada ===\n')

        if not ARCHIVO_MATRIX.exists():
            raise CommandError(f'No se encontró el archivo: {ARCHIVO_MATRIX}')

        self.stdout.write(f'Leyendo {ARCHIVO_MATRIX.name}...')
        try:
            df = pd.read_excel(
                ARCHIVO_MATRIX,
                sheet_name='MATRIX NUEVO',
                dtype={'DNI O CE': str},
                engine='openpyxl',
            )
        except Exception as e:
            raise CommandError(f'Error leyendo Excel: {e}')

        self.stdout.write(f'  {len(df)} filas encontradas')

        # Normalizar DNI
        df['_dni'] = df['DNI O CE'].apply(_norm_dni)
        df = df[df['_dni'].str.len() > 0]

        # Cargar empleados activos de BD
        from personal.models import Personal
        personal_map = {p.nro_doc: p for p in Personal.objects.all()}
        self.stdout.write(f'  {len(personal_map)} empleados en BD\n')

        # Mapa de subareas
        subarea_map = _build_subarea_map()
        self.stdout.write(f'  {len(subarea_map)} subareas indexadas')

        stats = {
            'sueldo': 0, 'area': 0, 'contrato': 0, 'correo': 0,
            'sin_match': [], 'errores': [],
        }

        with transaction.atomic():
            for _, row in df.iterrows():
                dni = row['_dni']
                p = personal_map.get(dni)
                if not p:
                    if len(stats['sin_match']) < 30:
                        stats['sin_match'].append(dni)
                    continue

                changes = {}

                # ── SUELDO BASE ──────────────────────────────────────────
                if not self.solo or self.solo == 'sueldo':
                    basico = _parse_decimal(row.get('BASICO'))
                    aliment = _parse_decimal(row.get('ALIMENTACION'))
                    hosped = _parse_decimal(row.get('HOSPEDAJE'))

                    if basico is not None and basico > 0:
                        changes['sueldo_base'] = basico
                    if aliment is not None and aliment >= 0:
                        changes['alimentacion_mensual'] = aliment
                    # viaticos_mensual si el campo existe
                    if hosped is not None and hosped >= 0:
                        if hasattr(p, 'viaticos_mensual'):
                            changes['viaticos_mensual'] = hosped

                # ── ÁREA ─────────────────────────────────────────────────
                if not self.solo or self.solo == 'area':
                    area_raw = str(row.get('AREA', '') or '').strip()
                    subarea = _buscar_subarea(area_raw, subarea_map)
                    if subarea:
                        if p.subarea_id != subarea.pk:
                            changes['subarea'] = subarea
                    else:
                        # Intentar crear subarea nueva dentro del area si es posible
                        pass  # No creamos subareas nuevas, solo mapeamos

                # ── FECHA FIN CONTRATO (ULTIMA PRORROGA) ─────────────────
                if not self.solo or self.solo == 'contrato':
                    ultima_prorroga = _parse_fecha(row.get('ULTIMA PRORROGA'))
                    if ultima_prorroga:
                        changes['fecha_fin_contrato'] = ultima_prorroga
                    fecha_ingreso = _parse_fecha(row.get('FECHA DE INGRESO A NOMINA'))
                    if fecha_ingreso and not p.fecha_inicio_contrato:
                        changes['fecha_inicio_contrato'] = fecha_ingreso

                # ── CORREO ───────────────────────────────────────────────
                if not self.solo or self.solo == 'correo':
                    correo = str(row.get('CORREO', '') or '').strip()
                    if correo and '@' in correo:
                        # Poner en corporativo si no tiene, sino en personal
                        if not p.correo_corporativo:
                            changes['correo_corporativo'] = correo
                        elif not p.correo_personal:
                            changes['correo_personal'] = correo

                # ── APLICAR CAMBIOS ──────────────────────────────────────
                if changes:
                    cambios_str = ', '.join(f'{k}={v}' for k, v in changes.items())
                    self.stdout.write(
                        f'  {dni} {p.apellidos_nombres[:30]!r}: {cambios_str}'
                    )
                    if not self.dry:
                        for campo, valor in changes.items():
                            setattr(p, campo, valor)
                        p.save(update_fields=list(changes.keys()))

                    # Conteo por tipo
                    if 'sueldo_base' in changes:
                        stats['sueldo'] += 1
                    if 'subarea' in changes:
                        stats['area'] += 1
                    if 'fecha_fin_contrato' in changes:
                        stats['contrato'] += 1
                    if 'correo_corporativo' in changes or 'correo_personal' in changes:
                        stats['correo'] += 1

            if self.dry:
                transaction.set_rollback(True)

        self.stdout.write('\n=== RESUMEN ===')
        self.stdout.write(f'  Sueldos actualizados : {stats["sueldo"]}')
        self.stdout.write(f'  Areas actualizadas   : {stats["area"]}')
        self.stdout.write(f'  Contratos (fecha fin): {stats["contrato"]}')
        self.stdout.write(f'  Correos actualizados : {stats["correo"]}')
        self.stdout.write(f'  Sin match en BD      : {len(stats["sin_match"])}')
        if stats['sin_match']:
            self.stdout.write(f'    DNIs: {stats["sin_match"][:10]}...')
        self.stdout.write(self.style.SUCCESS('\nSync completado.'))
