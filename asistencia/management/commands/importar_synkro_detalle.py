"""
Importador de asistencia desde el formato Synkro Detalle (Asistencia_Detalle_*.xlsx).

FORMATO DEL ARCHIVO (14 columnas):
  DNI | Personal | Celular | FechaIngreso | Condicion | TipoTrabajador |
  Area | Cargo | Lugar Trabajo | Fecha | Ingreso | Refrigerio | FinRefrigerio | Salida

  - Una fila por empleado por día (ya consolidado por el sistema Synkro)
  - Todas las columnas son texto plano (fechas DD/MM/YYYY, horas HH:MM)
  - No existe columna "grupo" — se toma de Personal.grupo_tareo

CÁLCULO DE horas_marcadas:
  1. Ingreso + Salida presentes      → Salida - Ingreso  (horas decimales exactas)
  2. Ingreso + Refrigerio (sin Salida) → Refrigerio - Ingreso (salió a almuerzo)
  3. Ingreso sin Salida ni Refrigerio → SS (sin salida — biométrico no capturó salida)
  4. Sin Ingreso                      → ausencia, no se crea registro

  El descuento de almuerzo (0.5h) lo aplica el processor según condición/jornada,
  igual que en el resto del sistema. NO se descuenta aquí.

PRIORIDAD EN EL REPORTE:
  RELOJ > EXCEL para la misma fecha (ver _build_rco_data en reporte_individual.py).
  Los registros creados aquí (fuente_codigo='RELOJ') ganarán sobre los EXCEL.

USO:
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --dry-run
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --forzar
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --fecha-ini 2026-02-21 --fecha-fin 2026-03-21
"""
import logging
from datetime import date, time, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from asistencia.models import (
    RegistroTareo,
    TareoImportacion,
    BancoHoras,
    ConfiguracionSistema,
)
from personal.models import Personal

logger = logging.getLogger(__name__)

CERO = Decimal('0')
DOS  = Decimal('2')
JORNADA_SABADO_LOCAL = Decimal('5.5')

# Códigos que NO generan horas normales ni HE
CODIGOS_SIN_HE = {
    'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF',
    'LP', 'LSG', 'FA', 'TR', 'CDT', 'CPF', 'FR', 'ATM', 'SAI',
}


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_hhmm(val) -> time | None:
    """Convierte 'HH:MM' (string) a time. Retorna None si vacío o inválido."""
    if pd.isna(val) or not str(val).strip() or str(val).strip().lower() == 'nan':
        return None
    try:
        h, m = str(val).strip().split(':')
        return time(int(h), int(m))
    except Exception:
        return None


def _parse_fecha(val) -> date | None:
    """Convierte 'DD/MM/YYYY' a date."""
    try:
        return datetime.strptime(str(val).strip(), '%d/%m/%Y').date()
    except Exception:
        return None


def _time_diff_decimal(t1: time, t2: time) -> Decimal:
    """
    Diferencia t2 - t1 en horas decimales (redondeado a 2 decimales).
    Ejemplo: 06:03 → 18:19  = 12h 16min = 12.27h
    """
    d1 = timedelta(hours=t1.hour, minutes=t1.minute)
    d2 = timedelta(hours=t2.hour, minutes=t2.minute)
    diff = d2 - d1
    if diff.total_seconds() < 0:
        diff += timedelta(days=1)
    horas = Decimal(str(diff.total_seconds() / 3600))
    return horas.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de horas (replica processor._calcular_horas)
# ─────────────────────────────────────────────────────────────────────────────

def _jornada_correcta(config, condicion: str, dia_semana: int) -> Decimal:
    if condicion == 'FORANEO':
        return Decimal(str(config.jornada_foraneo_horas))
    if dia_semana == 5:
        return JORNADA_SABADO_LOCAL
    if dia_semana == 6:
        return CERO
    return Decimal(str(config.jornada_local_horas))


def _calcular_horas(
    codigo: str,
    horas_marcadas,
    jornada_h: Decimal,
    es_feriado: bool,
    dia_semana: int,
) -> tuple:
    """
    Retorna (horas_efectivas, horas_normales, he_25, he_35, he_100).
    Idéntico a processor._calcular_horas().
    """
    if codigo == 'SS':
        j = jornada_h if jornada_h > CERO else Decimal('8.5')
        return j, j, CERO, CERO, CERO

    if codigo in CODIGOS_SIN_HE:
        return CERO, CERO, CERO, CERO, CERO

    if not horas_marcadas or horas_marcadas <= CERO:
        return jornada_h, jornada_h, CERO, CERO, CERO

    horas_m = Decimal(str(horas_marcadas))

    # Descuento almuerzo
    if jornada_h > Decimal('9'):
        horas_ef = horas_m                                       # foráneo: sin descuento
    elif jornada_h <= Decimal('6') or dia_semana == 5:
        horas_ef = horas_m                                       # sábado/jornada corta
    else:
        almuerzo = Decimal('0.5') if horas_m > 5 else CERO
        horas_ef = max(CERO, horas_m - almuerzo)

    if horas_ef <= CERO:
        return CERO, CERO, CERO, CERO, CERO

    # Feriado o descanso semanal laborado → 100%
    if es_feriado or dia_semana == 6:
        return horas_ef, CERO, CERO, CERO, horas_ef

    if horas_ef <= jornada_h:
        return horas_ef, horas_ef, CERO, CERO, CERO

    exceso = horas_ef - jornada_h
    he25   = min(exceso, DOS)
    he35   = max(CERO, exceso - DOS)
    return horas_ef, jornada_h, he25, he35, CERO


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Importa asistencia desde el formato Synkro Detalle '
        '(Asistencia_Detalle_*.xlsx). Crea RegistroTareo con '
        'fuente_codigo=RELOJ y calcula horas/HE correctamente.'
    )

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo Excel Synkro Detalle.')
        parser.add_argument('--dry-run', action='store_true', help='Muestra cambios sin guardar.')
        parser.add_argument('--forzar', action='store_true',
                            help='Sobreescribe registros RELOJ existentes para la misma fecha.')
        parser.add_argument('--fecha-ini', default=None, metavar='YYYY-MM-DD',
                            help='Filtrar desde esta fecha (inclusive).')
        parser.add_argument('--fecha-fin', default=None, metavar='YYYY-MM-DD',
                            help='Filtrar hasta esta fecha (inclusive).')
        parser.add_argument('--importacion-id', type=int, default=None,
                            help='Usar una TareoImportacion existente en vez de crear nueva.')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _ok(self, msg): self.stdout.write(self.style.SUCCESS(msg))
    def _warn(self, msg): self.stdout.write(self.style.WARNING(msg))
    def _err(self, msg): self.stderr.write(self.style.ERROR(msg))
    def _sep(self, c='─', n=72): self.stdout.write(c * n)

    # ── lectura del Excel ─────────────────────────────────────────────────────

    def _leer_excel(self, ruta: str) -> pd.DataFrame:
        """Lee y valida el Excel Synkro Detalle."""
        path = Path(ruta)
        if not path.exists():
            raise CommandError(f'Archivo no encontrado: {ruta}')

        df = pd.read_excel(path, dtype=str, sheet_name=0)
        df.columns = [str(c).strip() for c in df.columns]

        required = {'DNI', 'Personal', 'Condicion', 'Fecha', 'Ingreso'}
        missing = required - set(df.columns)
        if missing:
            raise CommandError(
                f'Columnas requeridas no encontradas: {missing}\n'
                f'Columnas disponibles: {list(df.columns)}'
            )

        df['DNI'] = df['DNI'].astype(str).str.strip().str.zfill(8)
        df['Fecha_parsed'] = df['Fecha'].apply(_parse_fecha)
        df = df.dropna(subset=['Fecha_parsed'])
        return df

    # ── determinación de horas y código ──────────────────────────────────────

    def _procesar_fila(self, row) -> dict | None:
        """
        Analiza una fila del Detalle y retorna un dict con:
          codigo_dia, es_ss, horas_marcadas, hora_entrada_real, hora_salida_real
        Retorna None si no hay datos de asistencia (sin Ingreso).
        """
        ingreso = _parse_hhmm(row.get('Ingreso'))
        salida  = _parse_hhmm(row.get('Salida'))
        refrig  = _parse_hhmm(row.get('Refrigerio'))

        if ingreso is None:
            return None  # Sin entrada → ausencia, no crear registro

        hora_entrada = ingreso
        hora_salida  = salida

        if salida is not None:
            # Caso normal: entrada + salida
            horas_m  = _time_diff_decimal(ingreso, salida)
            codigo   = 'A'
            es_ss    = False
        elif refrig is not None:
            # Solo entrada + refrigerio (salió a almuerzo sin registrar retorno/salida)
            horas_m  = _time_diff_decimal(ingreso, refrig)
            hora_salida = refrig
            codigo   = 'A'
            es_ss    = False
        else:
            # Solo entrada, sin salida ni refrigerio → SS (sin salida)
            horas_m  = None
            codigo   = 'SS'
            es_ss    = True

        return {
            'codigo_dia':       codigo,
            'es_ss':            es_ss,
            'horas_marcadas':   horas_m,
            'hora_entrada_real': hora_entrada,
            'hora_salida_real':  hora_salida,
        }

    # ── main ─────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        dry_run  = options['dry_run']
        forzar   = options['forzar']
        verbosity = options['verbosity']
        archivo  = options['archivo']

        fecha_ini_str = options.get('fecha_ini')
        fecha_fin_str = options.get('fecha_fin')
        imp_id        = options.get('importacion_id')

        prefix = '[DRY-RUN] ' if dry_run else ''

        # ── 1. Leer Excel ─────────────────────────────────────────────────────
        self.stdout.write(f'\n{prefix}Leyendo {Path(archivo).name} …')
        df = self._leer_excel(archivo)

        # Filtro de fechas
        fecha_ini = date.fromisoformat(fecha_ini_str) if fecha_ini_str else df['Fecha_parsed'].min()
        fecha_fin = date.fromisoformat(fecha_fin_str) if fecha_fin_str else df['Fecha_parsed'].max()
        df = df[df['Fecha_parsed'].between(fecha_ini, fecha_fin)]

        self.stdout.write(
            f'  Filas cargadas  : {len(df):,}\n'
            f'  Período         : {fecha_ini} → {fecha_fin}\n'
            f'  DNIs únicos     : {df["DNI"].nunique():,}\n'
            f'  Modo            : {"DRY-RUN" if dry_run else "GUARDAR"}'
            f'{" + FORZAR (sobreescribe RELOJ)" if forzar else ""}'
        )

        # ── 2. Configuración y feriados ───────────────────────────────────────
        config = ConfiguracionSistema.get()
        try:
            from core.models import Feriado
            feriados = set(
                Feriado.objects.filter(
                    fecha__gte=fecha_ini, fecha__lte=fecha_fin
                ).values_list('fecha', flat=True)
            )
        except Exception:
            feriados = set()
        self.stdout.write(f'  Feriados en período: {len(feriados)}')

        # ── 3. Caché de empleados (DNI → Personal) ────────────────────────────
        dnis = df['DNI'].unique().tolist()
        personal_map = {
            str(p.nro_doc).zfill(8): p
            for p in Personal.objects.filter(nro_doc__in=dnis)
        }
        self.stdout.write(f'  Empleados en BD : {len(personal_map):,} / {len(dnis):,} DNIs del archivo')

        sin_match = set(dnis) - set(personal_map)
        if sin_match and verbosity >= 2:
            self._warn(f'  Sin match en BD : {sorted(sin_match)}')

        # ── 4. TareoImportacion ───────────────────────────────────────────────
        if not dry_run:
            if imp_id:
                try:
                    imp = TareoImportacion.objects.get(pk=imp_id)
                    self.stdout.write(f'  Usando importación existente #{imp.pk}')
                except TareoImportacion.DoesNotExist:
                    raise CommandError(f'TareoImportacion #{imp_id} no existe.')
            else:
                imp = TareoImportacion.objects.create(
                    archivo_nombre=Path(archivo).name,
                    tipo='RELOJ',
                    periodo_inicio=fecha_ini,
                    periodo_fin=fecha_fin,
                    estado='PROCESANDO',
                )
                self.stdout.write(f'  TareoImportacion #{imp.pk} creada')
        else:
            imp = None

        # ── 5. Registros RELOJ existentes en el período (para deduplicar) ─────
        if forzar:
            existentes = {}
        else:
            existentes_qs = RegistroTareo.objects.filter(
                fecha__gte=fecha_ini,
                fecha__lte=fecha_fin,
                fuente_codigo='RELOJ',
                personal__isnull=False,
            ).values_list('personal__nro_doc', 'fecha')
            existentes = {(str(d).zfill(8), f) for d, f in existentes_qs}
        self.stdout.write(f'  Registros RELOJ existentes: {len(existentes):,}')

        # ── 6. Procesar filas ─────────────────────────────────────────────────
        self._sep()
        self.stdout.write('Procesando filas …')

        creados      = 0
        actualizados = 0
        omitidos     = 0
        sin_personal = 0
        errores      = 0
        a_crear  = []
        a_update = []

        for _, row in df.iterrows():
            try:
                dni   = str(row['DNI']).zfill(8)
                fecha = row['Fecha_parsed']

                # Coincidencia con Personal
                personal = personal_map.get(dni)
                if personal is None:
                    sin_personal += 1
                    continue

                # ¿Ya existe un RELOJ para este empleado+fecha y no forzamos?
                if (dni, fecha) in existentes and not forzar:
                    omitidos += 1
                    continue

                # Parsear horarios y calcular horas
                resultado = self._procesar_fila(row)
                if resultado is None:
                    omitidos += 1
                    continue

                codigo     = resultado['codigo_dia']
                horas_m    = resultado['horas_marcadas']
                h_entrada  = resultado['hora_entrada_real']
                h_salida   = resultado['hora_salida_real']

                dia_semana = fecha.weekday()          # 0=Lun … 6=Dom
                condicion  = (row.get('Condicion') or personal.condicion or 'LOCAL').strip().upper()
                es_feriado = fecha in feriados
                jornada_h  = _jornada_correcta(config, condicion, dia_semana)
                grupo      = personal.grupo_tareo or 'STAFF'

                h_ef, h_norm, he25, he35, he100 = _calcular_horas(
                    codigo=codigo,
                    horas_marcadas=horas_m,
                    jornada_h=jornada_h,
                    es_feriado=es_feriado,
                    dia_semana=dia_semana,
                )

                if verbosity >= 2:
                    dias = ['Lun','Mar','Mié','Jue','Vie','Sáb','Dom']
                    self.stdout.write(
                        f'  {fecha} {dias[dia_semana]:<3} | {dni} | '
                        f'{codigo:<3} | {condicion:<7} | '
                        f'bruto={float(horas_m or 0):5.2f}h | '
                        f'n={float(h_norm):4.1f} '
                        f'25%={float(he25):4.1f} '
                        f'35%={float(he35):4.1f} '
                        f'100%={float(he100):4.1f}'
                    )

                if dry_run:
                    creados += 1
                    continue

                # ¿Actualizar o crear?
                if forzar:
                    existing_reg = RegistroTareo.objects.filter(
                        personal=personal,
                        fecha=fecha,
                        fuente_codigo='RELOJ',
                        importacion=imp,
                    ).first()
                else:
                    existing_reg = None

                campos = dict(
                    importacion      = imp,
                    personal         = personal,
                    dni              = dni,
                    nombre_archivo   = Path(archivo).name,
                    grupo            = grupo,
                    condicion        = condicion,
                    fecha            = fecha,
                    dia_semana       = dia_semana,
                    es_feriado       = es_feriado,
                    codigo_dia       = codigo,
                    fuente_codigo    = 'RELOJ',
                    hora_entrada_real = h_entrada,
                    hora_salida_real  = h_salida,
                    horas_marcadas   = horas_m,
                    horas_efectivas  = h_ef,
                    horas_normales   = h_norm,
                    he_25            = he25,
                    he_35            = he35,
                    he_100           = he100,
                    he_al_banco      = (grupo == 'STAFF'),
                )

                if existing_reg:
                    for k, v in campos.items():
                        if k != 'importacion':
                            setattr(existing_reg, k, v)
                    a_update.append(existing_reg)
                    actualizados += 1
                else:
                    a_crear.append(RegistroTareo(**campos))
                    creados += 1

            except Exception as exc:
                errores += 1
                self._err(f'  ERROR fila DNI={row.get("DNI")} fecha={row.get("Fecha")}: {exc}')

        # ── 7. Guardar ────────────────────────────────────────────────────────
        if not dry_run:
            with transaction.atomic():
                if a_crear:
                    RegistroTareo.objects.bulk_create(a_crear, batch_size=300)
                if a_update:
                    update_fields = [
                        'grupo', 'condicion', 'codigo_dia', 'fuente_codigo',
                        'hora_entrada_real', 'hora_salida_real', 'horas_marcadas',
                        'horas_efectivas', 'horas_normales', 'he_25', 'he_35', 'he_100',
                        'he_al_banco', 'es_feriado', 'dia_semana',
                    ]
                    RegistroTareo.objects.bulk_update(a_update, update_fields, batch_size=300)

                # Marcar importación como completada
                if imp:
                    imp.estado        = 'COMPLETADO'
                    imp.total_registros = creados + actualizados
                    imp.registros_ok    = creados + actualizados
                    imp.save()

        # ── 8. BancoHoras (solo si creamos registros STAFF) ──────────────────
        if not dry_run and (creados > 0 or actualizados > 0) and imp:
            self._sep()
            self.stdout.write('Recalculando BancoHoras …')
            self._recalcular_banco(imp, fecha_ini, fecha_fin)

        # ── 9. Resumen ────────────────────────────────────────────────────────
        self._sep('═')
        self.stdout.write(self.style.MIGRATE_HEADING(f'{prefix}RESUMEN'))
        self.stdout.write(
            f'  Registros creados    : {creados:,}\n'
            f'  Registros actualizados: {actualizados:,}\n'
            f'  Omitidos (ya existían): {omitidos:,}\n'
            f'  Sin match en BD       : {sin_personal:,}\n'
            f'  Errores               : {errores}'
        )
        if dry_run:
            self._warn('\n  ⚠ DRY-RUN — ningún dato fue guardado.')
        elif creados or actualizados:
            self._ok(f'\n  ✓ Importación #{imp.pk if imp else "—"} completada.')

    # ── BancoHoras ────────────────────────────────────────────────────────────

    def _recalcular_banco(self, imp, fecha_ini, fecha_fin):
        """Recalcula BancoHoras para los STAFF de la importación."""
        from collections import defaultdict

        periodo_anio = imp.periodo_fin.year
        periodo_mes  = imp.periodo_fin.month

        resumen = (
            RegistroTareo.objects
            .filter(importacion=imp, grupo='STAFF', personal__isnull=False)
            .values('personal_id')
            .annotate(
                sum_25=__import__('django.db.models', fromlist=['Sum']).Sum('he_25'),
                sum_35=__import__('django.db.models', fromlist=['Sum']).Sum('he_35'),
                sum_100=__import__('django.db.models', fromlist=['Sum']).Sum('he_100'),
            )
        )

        creados_b = actualizados_b = 0
        to_create = []
        to_update = []

        for row in resumen:
            pid   = row['personal_id']
            s25   = row['sum_25']  or CERO
            s35   = row['sum_35']  or CERO
            s100  = row['sum_100'] or CERO
            total = s25 + s35 + s100

            try:
                banco = BancoHoras.objects.get(
                    personal_id=pid,
                    periodo_anio=periodo_anio,
                    periodo_mes=periodo_mes,
                )
                banco.he_25_acumuladas  = s25
                banco.he_35_acumuladas  = s35
                banco.he_100_acumuladas = s100
                banco.saldo_horas       = total
                to_update.append(banco)
                actualizados_b += 1
            except BancoHoras.DoesNotExist:
                to_create.append(BancoHoras(
                    personal_id=pid,
                    periodo_anio=periodo_anio,
                    periodo_mes=periodo_mes,
                    he_25_acumuladas=s25,
                    he_35_acumuladas=s35,
                    he_100_acumuladas=s100,
                    saldo_horas=total,
                ))
                creados_b += 1

        with transaction.atomic():
            if to_update:
                BancoHoras.objects.bulk_update(
                    to_update,
                    ['he_25_acumuladas', 'he_35_acumuladas', 'he_100_acumuladas', 'saldo_horas'],
                    batch_size=200,
                )
            if to_create:
                BancoHoras.objects.bulk_create(to_create, batch_size=200)

        self._ok(
            f'  BancoHoras actualizados: {actualizados_b:,} | '
            f'creados: {creados_b:,}'
        )
