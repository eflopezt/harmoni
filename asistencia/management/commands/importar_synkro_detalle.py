"""
Importador de asistencia desde el formato Synkro Detalle (Asistencia_Detalle_*.xlsx).

FORMATO DEL ARCHIVO (14 columnas):
  DNI | Personal | Celular | FechaIngreso | Condicion | TipoTrabajador |
  Area | Cargo | Lugar Trabajo | Fecha | Ingreso | Refrigerio | FinRefrigerio | Salida

  - Una fila por empleado por día (ya consolidado por el sistema Synkro)
  - Todas las columnas son texto plano (fechas DD/MM/YYYY, horas HH:MM)
  - No existe columna "grupo" — se toma de Personal.grupo_tareo

CÁLCULO DE horas_marcadas (verificado con datos reales feb-mar 2026):
  Las horas se calculan directamente de los tiempos biométricos sin redondeo previo.

  Caso 1 — Ingreso + Salida:
    raw = Salida − Ingreso (exacto en horas decimales, sin redondear)
    si raw > 6h → descontar 1h de almuerzo
    horas_netas = round_half(raw − almuerzo)   # redondear a la media hora más cercana (0 o 0.5)

  Caso 2 — Ingreso + Refrigerio (sin Salida):
    El trabajador registró salida a almuerzo pero no volvió a marcar.
    raw = Refrigerio − Ingreso
    sin descuento de almuerzo (ya se fue a comer)
    horas_netas = round_half(raw)

  Caso 3 — Solo Ingreso (sin Salida ni Refrigerio → SS):
    No se computan horas: se asigna código SS y se paga jornada completa del día.

  Caso 4 — Sin Ingreso:
    No se crea registro (ausencia manejada por el proceso normal de tareo).

JORNADAS DIARIAS:
  LOCAL / LIMA  Lun–Vie : config.jornada_local_horas (8.5 h)
  LOCAL / LIMA  Sábado  : 5.5 h (JORNADA_SABADO_LOCAL, sin descuento almuerzo)
  LOCAL / LIMA  Domingo : descanso — si labora → 100 % HE
  FORÁNEO       Lun–Sáb : config.jornada_foraneo_horas (configurar a 10 h)
  FORÁNEO       Domingo  : 4 h (JORNADA_DOMINGO_FORANEO, parte de su ciclo normal)

DISTRIBUCIÓN HE:
  RCO   → HE se paga directamente (he_25, he_35, he_100 en RegistroTareo)
  STAFF → HE va al BancoHoras acumulativo (he_al_banco = True)

PRIORIDAD EN EL REPORTE:
  RELOJ > EXCEL para la misma fecha/empleado.

USO:
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --dry-run
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --forzar
  python manage.py importar_synkro_detalle /ruta/Asistencia_Detalle.xlsx --fecha-ini 2026-02-21 --fecha-fin 2026-03-21
"""
import logging
from datetime import date, time, datetime
from decimal import Decimal, ROUND_FLOOR
from pathlib import Path

import pandas as pd

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from asistencia.models import (
    RegistroTareo,
    TareoImportacion,
    BancoHoras,
    ConfiguracionSistema,
    FeriadoCalendario,
    CompensacionFeriado,
)
from personal.models import Personal

logger = logging.getLogger(__name__)

CERO = Decimal('0')
DOS  = Decimal('2')

# Jornadas hardcodeadas
# ConfiguracionSistema.jornada_foraneo_horas estaba en 11.0h (turno bruto incluyendo almuerzo).
# En el importer biométrico ya descontamos 1h de almuerzo, por lo que la jornada
# de referencia para split normal/HE debe ser la jornada EFECTIVA: 10h.
JORNADA_SABADO_LOCAL    = Decimal('5.5')   # LOCAL/LIMA sábado (45h/sem: 8.5×5 + 5.5)
JORNADA_DIA_FORANEO     = Decimal('10')    # FORÁNEO Lun–Sáb efectiva (192h en 3 semanas)
JORNADA_DOMINGO_FORANEO = Decimal('4')     # FORÁNEO domingo (parte del ciclo normal)

# Umbral de horas trabajadas a partir del cual se descuenta el almuerzo
UMBRAL_ALMUERZO = Decimal('7')
DESCUENTO_ALMUERZO = Decimal('1')

# Gracia de redondeo: offset que se suma ANTES del floor al 0.5h.
# Con 7 min de gracia, el corte de redondeo pasa de 15 min a 23 min:
#   < 23 min en el tramo → floor (queda en la media hora inferior)
#   ≥ 23 min en el tramo → sube a la siguiente media hora
# Esto evita AÑADIR 0.5h por solo unos minutos de exceso,
# y a la vez no DESCUENTA 0.5h si faltan ≤ 7 min para completarla.
GRACIA_ROUNDING = Decimal('7') / 60       # 7 minutos en horas

# Códigos que NO generan horas normales ni HE
CODIGOS_SIN_HE = {
    'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF',
    'LP', 'LSG', 'FA', 'TR', 'CDT', 'CPF', 'FER', 'ATM', 'SAI',
}

DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


# ─────────────────────────────────────────────────────────────────────────────
# Utilidades de parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_hhmm(val) -> time | None:
    """Convierte 'HH:MM' (string) a time. Retorna None si vacío o inválido."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s or s.lower() in ('nan', 'none', '-', ''):
        return None
    try:
        h, m = s.split(':')
        return time(int(h), int(m))
    except Exception:
        return None


def _parse_fecha(val) -> date | None:
    """Convierte 'DD/MM/YYYY' a date."""
    try:
        return datetime.strptime(str(val).strip(), '%d/%m/%Y').date()
    except Exception:
        return None


def _to_minutos(t: time) -> int:
    return t.hour * 60 + t.minute


def _round_half(h: Decimal) -> Decimal:
    """
    Redondea h a la media hora (0.5h) con gracia de ±7 minutos.

    Equivale a: floor((h + 7min) / 0.5h) * 0.5h

    El corte de redondeo queda en el minuto 23 (no en el 15):
      < 23 min en el tramo → queda en la media hora inferior
      ≥ 23 min en el tramo → sube a la siguiente media hora

    Ejemplos:
      11h05min → 11.0h  (solo 5 min de exceso → no añade 0.5h)
      11h22min → 11.0h  (22 min < 23 min umbral → no añade 0.5h)
      11h23min → 11.5h  (≥ 23 min → se acredita, faltan solo 7 min para 11.5h)
      11h30min → 11.5h  ✓
    """
    return ((h + GRACIA_ROUNDING) * 2).to_integral_value(rounding=ROUND_FLOOR) / 2


# ─────────────────────────────────────────────────────────────────────────────
# Cálculo de horas desde biométrico
# ─────────────────────────────────────────────────────────────────────────────

def _calc_horas_biometrico(
    ingreso: time,
    salida: time | None = None,
    refrigerio: time | None = None,
) -> Decimal | None:
    """
    Calcula horas efectivas netas desde tiempos biométricos (HH:MM exacto).

    Caso Ingreso + Salida:
        raw = Salida − Ingreso (sin redondear)
        si raw > 6h  →  descuento 1h almuerzo
        resultado = floor_half(raw − descuento)

    Caso Ingreso + Refrigerio (sin Salida):
        El trabajador solo tiene marca de salida a almuerzo.
        raw = Refrigerio − Ingreso  (sin descuento)
        resultado = floor_half(raw)

    Caso Sin Salida ni Refrigerio (SS):
        Retorna None  →  se asigna jornada completa en _calcular_horas()
    """
    if salida is not None:
        raw_min = _to_minutos(salida) - _to_minutos(ingreso)
        if raw_min < 0:
            raw_min += 1440                          # cruce medianoche (raro)
        raw_h = Decimal(raw_min) / 60
        almuerzo = DESCUENTO_ALMUERZO if raw_h > UMBRAL_ALMUERZO else CERO
        neto = max(CERO, raw_h - almuerzo)
        return _round_half(neto)

    if refrigerio is not None:
        raw_min = _to_minutos(refrigerio) - _to_minutos(ingreso)
        if raw_min < 0:
            raw_min += 1440
        raw_h = Decimal(raw_min) / 60
        return _round_half(raw_h)                       # sin descuento

    return None                                       # SS: sin salida


# ─────────────────────────────────────────────────────────────────────────────
# Jornada diaria por condición y día
# ─────────────────────────────────────────────────────────────────────────────

def _jornada_correcta(config, condicion: str, dia_semana: int) -> Decimal:
    """
    Jornada diaria de referencia para split normal/HE.

    LOCAL/LIMA:
      Lun–Vie → config.jornada_local_horas (8.5h)
      Sábado  → 5.5h  (hardcoded: sin descuento almuerzo, jornada corta)
      Domingo → 0h    (descanso; si labora, todo va a HE100)

    FORÁNEO:
      Lun–Sáb → config.jornada_foraneo_horas  (debe estar configurado a 10h)
      Domingo → 4h    (parte del ciclo 192h/3 semanas; HE25/35 si supera 4h)
    """
    if condicion.upper().replace('Á', 'A') == 'FORANEO':
        if dia_semana == 6:
            return JORNADA_DOMINGO_FORANEO          # 4h — parte del ciclo 192h/3 semanas
        return JORNADA_DIA_FORANEO                  # 10h Lun–Sáb (efectivo, sin almuerzo)
    # LOCAL / LIMA
    if dia_semana == 5:
        return JORNADA_SABADO_LOCAL
    if dia_semana == 6:
        return CERO                                   # descanso → 100 % si labora
    return Decimal(str(config.jornada_local_horas))


# ─────────────────────────────────────────────────────────────────────────────
# Distribución en normal / HE
# ─────────────────────────────────────────────────────────────────────────────

def _calcular_horas(
    codigo: str,
    horas_netas: Decimal | None,
    jornada_h: Decimal,
    es_feriado: bool,
    dia_semana: int,
) -> tuple:
    """
    Distribuye horas_netas (ya con almuerzo descontado) en:
      (horas_efectivas, horas_normales, he_25, he_35, he_100)

    horas_netas proviene de _calc_horas_biometrico(); el almuerzo ya fue deducido.
    Esta función NO aplica ningún descuento adicional.
    """
    # SS (sin salida): presente sin marca de salida → paga jornada completa.
    # En feriado laborado o LOCAL domingo trabajado, la jornada va al 100%.
    if codigo == 'SS':
        j = jornada_h if jornada_h > CERO else Decimal('8.5')
        if es_feriado or (dia_semana == 6 and jornada_h == CERO):
            return j, CERO, CERO, CERO, j
        return j, j, CERO, CERO, CERO

    # Códigos de ausencia/permiso
    if codigo in CODIGOS_SIN_HE:
        return CERO, CERO, CERO, CERO, CERO

    # Sin horas válidas (no debería ocurrir con fuente biométrica)
    if horas_netas is None or horas_netas <= CERO:
        return CERO, CERO, CERO, CERO, CERO

    horas_ef = horas_netas

    # Feriado laborado  o  LOCAL domingo (descanso semanal laborado) → 100 % HE
    if es_feriado or (dia_semana == 6 and jornada_h == CERO):
        return horas_ef, CERO, CERO, CERO, horas_ef

    # Dentro o igual a la jornada → solo horas normales
    if horas_ef <= jornada_h:
        return horas_ef, horas_ef, CERO, CERO, CERO

    # Con horas extra — el exceso también se redondea a la media hora más cercana
    exceso = _round_half(horas_ef - jornada_h)
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
        'fuente_codigo=RELOJ y calcula horas/HE con descuento real de '
        'almuerzo (1h si >6h trabajadas, verificado con datos biométricos).'
    )

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help='Ruta al archivo Excel Synkro Detalle.')
        parser.add_argument('--dry-run', action='store_true', help='Muestra cambios sin guardar.')
        parser.add_argument(
            '--forzar', action='store_true',
            help='Sobreescribe registros RELOJ existentes para la misma fecha/empleado.',
        )
        parser.add_argument('--fecha-ini', default=None, metavar='YYYY-MM-DD',
                            help='Filtrar desde esta fecha (inclusive).')
        parser.add_argument('--fecha-fin', default=None, metavar='YYYY-MM-DD',
                            help='Filtrar hasta esta fecha (inclusive).')
        parser.add_argument('--importacion-id', type=int, default=None,
                            help='Usar TareoImportacion existente (en vez de crear nueva).')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _ok(self, msg):   self.stdout.write(self.style.SUCCESS(msg))
    def _warn(self, msg): self.stdout.write(self.style.WARNING(msg))
    def _err(self, msg):  self.stderr.write(self.style.ERROR(msg))
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

    # ── parseo de una fila ────────────────────────────────────────────────────

    def _procesar_fila(self, row) -> dict | None:
        """
        Parsea una fila del Detalle y retorna:
          codigo_dia, horas_netas, hora_entrada_real, hora_salida_real, desc_almuerzo

        Retorna None si no hay Ingreso (ausencia → no se crea registro).
        """
        ingreso  = _parse_hhmm(row.get('Ingreso'))
        salida   = _parse_hhmm(row.get('Salida'))
        refrigerio = _parse_hhmm(row.get('Refrigerio'))

        if ingreso is None and refrigerio is None and salida is None:
            return None   # sin ninguna marca → ausencia, no crear registro

        if ingreso is None:
            # Sin ingreso pero con alguna otra marca (refrigerio/salida) → SS
            # El trabajador estuvo presente pero no marcó entrada correctamente.
            primera_marca = refrigerio or salida
            return {
                'codigo_dia':        'SS',
                'horas_netas':       None,
                'hora_entrada_real': primera_marca,
                'hora_salida_real':  salida,
                'raw_h':             None,
                'almuerzo':          CERO,
            }

        if salida is not None:
            # Caso normal: entrada + salida
            raw_min = _to_minutos(salida) - _to_minutos(ingreso)
            if raw_min < 0:
                raw_min += 1440
            raw_h = Decimal(raw_min) / 60
            tiene_almuerzo = raw_h > UMBRAL_ALMUERZO
            horas_netas = _calc_horas_biometrico(ingreso, salida=salida)
            return {
                'codigo_dia':        'A',
                'horas_netas':       horas_netas,
                'hora_entrada_real': ingreso,
                'hora_salida_real':  salida,
                'raw_h':             raw_h,
                'almuerzo':          DESCUENTO_ALMUERZO if tiene_almuerzo else CERO,
            }

        if refrigerio is not None:
            # Solo entrada + refrigerio (salió a almuerzo, no registró retorno/salida)
            raw_min = _to_minutos(refrigerio) - _to_minutos(ingreso)
            if raw_min < 0:
                raw_min += 1440
            raw_h = Decimal(raw_min) / 60
            horas_netas = _calc_horas_biometrico(ingreso, refrigerio=refrigerio)
            return {
                'codigo_dia':        'A',
                'horas_netas':       horas_netas,
                'hora_entrada_real': ingreso,
                'hora_salida_real':  refrigerio,   # última marca registrada
                'raw_h':             raw_h,
                'almuerzo':          CERO,
            }

        # Solo ingreso, sin salida ni refrigerio → SS
        return {
            'codigo_dia':        'SS',
            'horas_netas':       None,
            'hora_entrada_real': ingreso,
            'hora_salida_real':  None,
            'raw_h':             None,
            'almuerzo':          CERO,
        }

    # ── main ─────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        forzar    = options['forzar']
        verbosity = options['verbosity']
        archivo   = options['archivo']
        imp_id    = options.get('importacion_id')

        fecha_ini_str = options.get('fecha_ini')
        fecha_fin_str = options.get('fecha_fin')
        prefix = '[DRY-RUN] ' if dry_run else ''

        # ── 1. Leer Excel ─────────────────────────────────────────────────────
        self.stdout.write(f'\n{prefix}Leyendo {Path(archivo).name} …')
        df = self._leer_excel(archivo)

        fecha_ini = date.fromisoformat(fecha_ini_str) if fecha_ini_str else df['Fecha_parsed'].min()
        fecha_fin = date.fromisoformat(fecha_fin_str) if fecha_fin_str else df['Fecha_parsed'].max()
        df = df[df['Fecha_parsed'].between(fecha_ini, fecha_fin)]

        self.stdout.write(
            f'  Filas cargadas  : {len(df):,}\n'
            f'  Período         : {fecha_ini} → {fecha_fin}\n'
            f'  DNIs únicos     : {df["DNI"].nunique():,}\n'
            f'  Modo            : {"DRY-RUN" if dry_run else "GUARDAR"}'
            f'{" + FORZAR (sobreescribe RELOJ existentes)" if forzar else ""}'
        )

        # ── 2. Configuración y feriados ───────────────────────────────────────
        config = ConfiguracionSistema.get()

        # Feriados activos del período (traslados de CompensacionFeriado
        # aplicados por el helper único)
        from asistencia.services.feriados import feriados_efectivos
        feriados = feriados_efectivos(fecha_ini, fecha_fin)
        hay_comp = CompensacionFeriado.objects.filter(activo=True).exists()

        self.stdout.write(
            f'  Feriados en período : {len(feriados)}'
            f'{" (con compensaciones)" if hay_comp else ""}\n'
            f'  Jornada LOCAL L-V   : {config.jornada_local_horas}h\n'
            f'  Jornada LOCAL Sáb   : {JORNADA_SABADO_LOCAL}h\n'
            f'  Jornada FORÁNEO L-S : {JORNADA_DIA_FORANEO}h (efectiva, sin almuerzo)\n'
            f'  Jornada FORÁNEO Dom : {JORNADA_DOMINGO_FORANEO}h\n'
            f'  Almuerzo            : {DESCUENTO_ALMUERZO}h si raw > {UMBRAL_ALMUERZO}h'
        )

        # ── 3. Caché de empleados ─────────────────────────────────────────────
        dnis = df['DNI'].unique().tolist()
        personal_map = {
            str(p.nro_doc).zfill(8): p
            for p in Personal.objects.filter(nro_doc__in=dnis)
        }
        self.stdout.write(
            f'  Empleados en BD : {len(personal_map):,} / {len(dnis):,} DNIs del archivo'
        )
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

        # ── 5. Registros RELOJ existentes ─────────────────────────────────────
        if forzar:
            # Eliminar TODOS los registros RELOJ del período para evitar
            # que queden registros stale de importaciones anteriores.
            # Con esto cada --forzar deja exactamente un RELOJ por empleado+fecha.
            n_deleted, _ = RegistroTareo.objects.filter(
                fecha__gte=fecha_ini,
                fecha__lte=fecha_fin,
                fuente_codigo='RELOJ',
                personal__isnull=False,
            ).delete()
            self.stdout.write(f'  Registros RELOJ eliminados (--forzar): {n_deleted:,}')
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
        omitidos     = 0
        sin_personal = 0
        errores      = 0
        a_crear      = []

        for _, row in df.iterrows():
            try:
                dni   = str(row['DNI']).zfill(8)
                fecha = row['Fecha_parsed']

                personal = personal_map.get(dni)
                if personal is None:
                    sin_personal += 1
                    continue

                # ¿Ya existe RELOJ y no forzamos?
                if (dni, fecha) in existentes and not forzar:
                    omitidos += 1
                    continue

                resultado = self._procesar_fila(row)
                if resultado is None:
                    # Sin Ingreso → ausencia, no crear registro
                    omitidos += 1
                    continue

                codigo      = resultado['codigo_dia']
                horas_netas = resultado['horas_netas']
                h_entrada   = resultado['hora_entrada_real']
                h_salida    = resultado['hora_salida_real']
                raw_h       = resultado['raw_h']
                almuerzo    = resultado['almuerzo']

                dia_semana = fecha.weekday()           # 0=Lun … 6=Dom
                # condicion: siempre desde Personal (Tareo → Régimen Laboral)
                # El archivo puede tener condicion incorrecta; la fuente de verdad es BD.
                condicion  = (personal.condicion or 'LOCAL').strip().upper()
                es_feriado = fecha in feriados
                jornada_h  = _jornada_correcta(config, condicion, dia_semana)
                grupo      = personal.grupo_tareo or 'STAFF'

                h_ef, h_norm, he25, he35, he100 = _calcular_horas(
                    codigo=codigo,
                    horas_netas=horas_netas,
                    jornada_h=jornada_h,
                    es_feriado=es_feriado,
                    dia_semana=dia_semana,
                )

                if verbosity >= 2:
                    raw_str = f'{float(raw_h):5.2f}h' if raw_h is not None else '  SS  '
                    alm_str = f'-{float(almuerzo):.1f}h' if almuerzo else '     '
                    self.stdout.write(
                        f'  {fecha} {DIAS[dia_semana]:<3} | {dni} | '
                        f'{codigo:<3} | {condicion:<7} | {grupo:<5} | '
                        f'raw={raw_str} {alm_str} → '
                        f'net={float(horas_netas or 0):4.1f}h | '
                        f'n={float(h_norm):4.1f} '
                        f'25%={float(he25):4.1f} '
                        f'35%={float(he35):4.1f} '
                        f'100%={float(he100):4.1f} '
                        f'[j={float(jornada_h):.1f}h]'
                    )

                if dry_run:
                    creados += 1
                    continue

                campos = dict(
                    importacion       = imp,
                    personal          = personal,
                    dni               = dni,
                    nombre_archivo    = personal.apellidos_nombres,
                    grupo             = grupo,
                    condicion         = condicion,
                    fecha             = fecha,
                    dia_semana        = dia_semana,
                    es_feriado        = es_feriado,
                    codigo_dia        = codigo,
                    fuente_codigo     = 'RELOJ',
                    hora_entrada_real = h_entrada,
                    hora_salida_real  = h_salida,
                    horas_marcadas    = raw_h if raw_h is not None else horas_netas,  # brutas (almuerzo se descuenta en horas_efectivas)
                    horas_efectivas   = h_ef,
                    horas_normales    = h_norm,
                    he_25             = he25,
                    he_35             = he35,
                    he_100            = he100,
                    he_al_banco       = (grupo == 'STAFF'),
                )

                a_crear.append(RegistroTareo(**campos))
                creados += 1

            except Exception as exc:
                errores += 1
                self._err(
                    f'  ERROR fila DNI={row.get("DNI")} '
                    f'fecha={row.get("Fecha")}: {exc}'
                )

        # ── 7. Guardar ────────────────────────────────────────────────────────
        if not dry_run:
            with transaction.atomic():
                if a_crear:
                    RegistroTareo.objects.bulk_create(a_crear, batch_size=300)

                if imp:
                    imp.estado          = 'COMPLETADO'
                    imp.total_registros = creados
                    imp.registros_ok    = creados
                    imp.save()

        # ── 8. BancoHoras ─────────────────────────────────────────────────────
        if not dry_run and creados > 0 and imp:
            self._sep()
            self.stdout.write('Recalculando BancoHoras …')
            self._recalcular_banco(imp)

        # ── 9. Resumen ────────────────────────────────────────────────────────
        self._sep('═')
        self.stdout.write(self.style.MIGRATE_HEADING(f'{prefix}RESUMEN'))
        self.stdout.write(
            f'  Registros creados     : {creados:,}\n'
            f'  Omitidos (sin ingreso): {omitidos:,}\n'
            f'  Sin match en BD       : {sin_personal:,}\n'
            f'  Errores               : {errores}'
        )
        if dry_run:
            self._warn('\n  ⚠ DRY-RUN — ningún dato fue guardado.')
        elif creados:
            self._ok(f'\n  ✓ Importación #{imp.pk if imp else "—"} completada.')

    # ── BancoHoras ────────────────────────────────────────────────────────────

    def _recalcular_banco(self, imp: TareoImportacion):
        """
        Recalcula BancoHoras para los empleados STAFF de esta importación.
        Incluye descuento de compensaciones (papeletas CHE aprobadas).
        """
        periodo_anio = imp.periodo_fin.year
        periodo_mes  = imp.periodo_fin.month

        # Suma HE por personal (solo STAFF)
        resumen = (
            RegistroTareo.objects
            .filter(importacion=imp, grupo='STAFF', personal__isnull=False)
            .values('personal_id')
            .annotate(
                sum_25=Sum('he_25'),
                sum_35=Sum('he_35'),
                sum_100=Sum('he_100'),
            )
        )

        # Compensaciones aprobadas (papeletas CHE)
        from collections import defaultdict
        che_map = defaultdict(lambda: CERO)
        try:
            from asistencia.models import PapeletaPermiso
            paps = PapeletaPermiso.objects.filter(
                importacion=imp,
                tipo_permiso='COMPENSACION_HE',
                estado='APROBADA',
                personal__isnull=False,
            ).values('personal_id', 'dias_solicitados')
            for p in paps:
                che_map[p['personal_id']] += Decimal(str(p['dias_solicitados'] or 0))
        except Exception:
            pass

        to_create  = []
        to_update  = []
        creados_b  = 0
        act_b      = 0

        for row in resumen:
            pid   = row['personal_id']
            s25   = row['sum_25']  or CERO
            s35   = row['sum_35']  or CERO
            s100  = row['sum_100'] or CERO
            total = s25 + s35 + s100
            comp  = che_map[pid]
            saldo = total - comp

            try:
                banco = BancoHoras.objects.get(
                    personal_id=pid,
                    periodo_anio=periodo_anio,
                    periodo_mes=periodo_mes,
                )
                banco.he_25_acumuladas  = s25
                banco.he_35_acumuladas  = s35
                banco.he_100_acumuladas = s100
                banco.he_compensadas    = comp
                banco.saldo_horas       = saldo
                to_update.append(banco)
                act_b += 1
            except BancoHoras.DoesNotExist:
                to_create.append(BancoHoras(
                    personal_id=pid,
                    periodo_anio=periodo_anio,
                    periodo_mes=periodo_mes,
                    he_25_acumuladas=s25,
                    he_35_acumuladas=s35,
                    he_100_acumuladas=s100,
                    he_compensadas=comp,
                    saldo_horas=saldo,
                ))
                creados_b += 1

        with transaction.atomic():
            if to_update:
                BancoHoras.objects.bulk_update(
                    to_update,
                    ['he_25_acumuladas', 'he_35_acumuladas',
                     'he_100_acumuladas', 'he_compensadas', 'saldo_horas'],
                    batch_size=200,
                )
            if to_create:
                BancoHoras.objects.bulk_create(to_create, batch_size=200)

        self._ok(
            f'  BancoHoras actualizados: {act_b:,} | creados: {creados_b:,}'
        )
