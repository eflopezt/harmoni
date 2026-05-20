"""
Importador flexible de asistencia — auto-detecta el formato del Excel.

Formatos soportados:
  WIDE          — DNI + cols meta + cols fecha (una col por día, pivote)
                  Ej: Asistencia_SegunFechas.xlsx  (Synkro / matrices de reloj)
  TRANSACCIONAL — DNI + Fecha + Ingreso + Salida  (una fila por persona-día)
                  Ej: Asistencia_Detalle_Consorcio.xlsx
  PAPELETAS     — TipoPermiso + DNI + FechaInicio + FechaFin (rangos)
                  Ej: PermisosLicencias_Personal.xlsx

Uso:
    parser  = FlexibleAttendanceParser(ruta_o_buffer)
    analisis = parser.analizar()     # {hoja: formato, ...}
    resultado = parser.parse_todo()
    # {
    #   'registros':    [...],   # para TareoProcessor.procesar(registros, papeletas)
    #   'papeletas':    [...],
    #   'fechas':       [date, ...],
    #   'hojas':        {'Sheet': 'WIDE', 'Sheet2': 'PAPELETAS', ...},
    #   'advertencias': [...],
    #   'errores':      [...],
    # }
"""
from __future__ import annotations

import logging
import re
import unicodedata
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

import pandas as pd

from asistencia.services.synkro import (
    _parse_date_column,
    _parse_valor_dia,
)

logger = logging.getLogger('personal.business')


# ---------------------------------------------------------------------------
# Constantes de formato
# ---------------------------------------------------------------------------

FORMAT_WIDE          = 'WIDE'
FORMAT_TRANSACCIONAL = 'TRANSACCIONAL'
FORMAT_PAPELETAS     = 'PAPELETAS'
FORMAT_DESCONOCIDO   = 'DESCONOCIDO'

# Numero minimo de columnas-fecha para clasificar una hoja como WIDE
_MIN_DATE_COLS = 5


# ---------------------------------------------------------------------------
# Helpers de normalización
# ---------------------------------------------------------------------------

def _normalize_col(col: Any) -> str:
    """
    Normaliza el nombre de una columna para comparación flexible:
    lowercase + sin acentos + sin espacios / guiones / puntos / subguiones.
    """
    s = str(col).lower().strip()
    # Quitar acentos (NFD decomposition, drop Mn category)
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    return re.sub(r'[\s_\-./\\]', '', s)


def _clean_dni(raw: Any) -> str:
    """
    Limpia DNI: quita '.0' y whitespace.
    Normaliza a 8 digitos (zero-pad) para DNI peruano almacenado como número
    en Excel — Excel convierte '01234567' → 1234567 al perder el cero inicial.
    """
    s = re.sub(r'\.0$', '', str(raw).strip())
    # Zero-pad: solo si es puramente numérico y tiene 7 dígitos
    if s.isdigit() and len(s) == 7:
        s = s.zfill(8)
    return s


def _parse_date_column_year(val: Any, anio: int) -> date | None:
    """
    Igual que synkro._parse_date_column pero permite forzar el año
    para columnas tipo 'Mar-1', 'Ene-5', etc.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    if isinstance(val, date):
        return val
    if isinstance(val, (int, float)):
        try:
            return (pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(val))).date()
        except Exception:
            return None
    s = str(val).strip()
    # 'Ene-21', 'Mar-5', etc. — usar el año forzado
    m = re.match(r'^([A-Za-záéíóú]{3})[- _.](\d{1,2})$', s, re.IGNORECASE)
    if m:
        mes_str, dia = m.group(1).lower(), int(m.group(2))
        from asistencia.services.synkro import MESES_ES
        mes = MESES_ES.get(mes_str)
        if mes:
            try:
                return date(anio, mes, dia)
            except ValueError:
                pass
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _inferir_anio_columnas(col_fechas: dict[int, date]) -> int | None:
    """
    Detecta si las fechas WIDE tienen el año incorrecto.
    Si la mayoría de fechas quedan > 60 días en el futuro, probablemente
    pertenecen al año anterior (el archivo es de diciembre importado en enero, etc.)
    Retorna el año correcto, o None si el año actual parece correcto.
    """
    if not col_fechas:
        return None
    hoy = date.today()
    futuras = sum(1 for d in col_fechas.values() if d > hoy + timedelta(days=60))
    if futuras > len(col_fechas) * 0.5:
        return hoy.year - 1
    return None


def _norm_condicion(condicion: str) -> str:
    c = condicion.upper()
    if 'FOR' in c or c[:2] == 'FO':
        return 'FORANEO'
    if 'LIM' in c:
        return 'LIMA'
    return 'LOCAL'


def _parse_fecha_flex(val: Any) -> date | None:
    """Convierte cualquier representacion razonable a date."""
    if val is None:
        return None
    # pd.NaT, float NaN, numpy NaN — todos indican valor ausente
    try:
        if pd.isnull(val):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_time_flex(val: Any) -> time | None:
    """
    Convierte un valor de hora a time. Acepta:
    - datetime / Timestamp (extrae .time())
    - time object
    - str 'HH:MM' o 'HH:MM:SS'
    - float (fraccion de dia Excel, e.g. 0.375 = 09:00)
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.time()
    if isinstance(val, time):
        return val
    if isinstance(val, float):
        # Fraccion de dia de Excel
        try:
            total_secs = int(round(abs(val) * 86400))
            hh = total_secs // 3600
            mm = (total_secs % 3600) // 60
            ss = total_secs % 60
            return time(hh % 24, mm, ss)
        except (ValueError, OverflowError):
            return None
    s = str(val).strip()
    for fmt in ('%H:%M:%S', '%H:%M', '%I:%M %p', '%I:%M:%S %p'):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            pass
    return None


def _compute_hours_from_times(
    ingreso: Any,
    salida: Any,
    refrig: Any,
    fin_refrig: Any,
    fecha: date,
) -> tuple[str | None, Decimal | None]:
    """
    Calcula (codigo, horas) a partir de horarios de entrada/salida.

    Casos:
      - Sin ingreso y sin salida  -> ('FA', None)   falta
      - Solo ingreso, sin salida  -> ('SS', None)   sin salida
      - Ambos                     -> (None, horas)  normal / HE
    """
    t_in  = _parse_time_flex(ingreso)
    t_out = _parse_time_flex(salida)
    t_bs  = _parse_time_flex(refrig)      # break start
    t_be  = _parse_time_flex(fin_refrig)  # break end

    if t_in is None and t_out is None:
        return 'FA', None
    if t_in is not None and t_out is None:
        return 'SS', None
    if t_in is None:
        # Solo salida registrada — inusual; tratar como entrada desde 00:00
        t_in = time(0, 0, 0)

    dt_in  = datetime.combine(fecha, t_in)
    dt_out = datetime.combine(fecha, t_out)
    if dt_out < dt_in:
        dt_out += timedelta(days=1)   # cruce de medianoche

    total_sec = (dt_out - dt_in).total_seconds()

    if t_bs and t_be:
        dt_bs = datetime.combine(fecha, t_bs)
        dt_be = datetime.combine(fecha, t_be)
        if dt_be < dt_bs:
            dt_be += timedelta(days=1)
        break_sec = max(0, (dt_be - dt_bs).total_seconds())
        total_sec -= break_sec

    if total_sec <= 0:
        return 'FA', None

    horas = Decimal(str(round(total_sec / 3600, 2)))
    return None, horas


# ---------------------------------------------------------------------------
# Patrones de nombres de columna (normalizados)
# ---------------------------------------------------------------------------

_META_PATTERNS: dict[str, list[str]] = {
    # Comunes a todos los formatos
    'dni': [
        'dni', 'documento', 'nrodoc', 'numdoc', 'numerodocumento',
        'nrodocumento', 'cedula',
    ],
    'nombre': [
        'nombrecompleto', 'nombre', 'personal', 'apellidosnombres',
        'trabajador', 'empleado', 'apellidos', 'nombresyapellidos',
    ],
    'condicion': [
        'condicion', 'partida', 'ubicacion', 'modalidad',
    ],
    'tipo_trabajador': [
        'tipotrabajador', 'tipotrab', 'tipopersonal', 'tipo', 'categoria',
    ],
    'area': [
        'area', 'areatrabajo', 'departamento', 'gerencia', 'division',
        'unidad', 'seccion',
    ],
    'cargo': [
        'cargo', 'puesto', 'ocupacion', 'posicion', 'rol',
    ],
    # Especificos para TRANSACCIONAL
    'fecha': [
        'fecha', 'date', 'dia', 'fechaasistencia',
    ],
    'ingreso': [
        'ingreso', 'horaingreso', 'entrada', 'checkin', 'horainicio',
        'horaentrada', 'marcacionentrada',
    ],
    'refrigerio': [
        'refrigerio', 'almuerzo', 'inicialmuerzo', 'breakstart',
        'iniciorefrigerio',
    ],
    'fin_refrigerio': [
        'finrefrigerio', 'finalmuerzo', 'breakend',
        'retornorefrigerio', 'vueltaalmuerzo',
    ],
    'salida': [
        'salida', 'horasalida', 'checkout', 'horafin',
        'marcacionsalida',
    ],
    # Especificos para PAPELETAS
    'tipo_permiso': [
        'tipopermiso', 'permiso', 'tipoabsencia', 'codigoabsencia',
        'tipolicense', 'tipolicencia',
    ],
    'iniciales': [
        'iniciales', 'codigo', 'abrev', 'sigla',
    ],
    'fecha_inicio': [
        'fechainicio', 'fechaini', 'inicio', 'desde', 'fechadesde', 'start',
    ],
    'fecha_fin': [
        'fechafin', 'fin', 'hasta', 'fechahasta', 'end',
    ],
    'detalle': [
        'detalle', 'motivo', 'observacion', 'descripcion', 'comentario',
        'sustento',
    ],
}


# Campos de hora que NO deben capturar columnas cuyo nombre empiece con 'fecha'
# Evita que "FechaIngreso" (fecha de contratación) se confunda con "Ingreso" (hora entrada)
_TIME_FIELDS = {'ingreso', 'refrigerio', 'fin_refrigerio', 'salida'}

# Campos que solo usan coincidencia EXACTA (no substring)
# Evita que "FechaIngreso" capture el campo "fecha" (fecha de asistencia del día)
_EXACT_ONLY_FIELDS = {'fecha'}


def _map_columns(columns: list) -> dict[str, str]:
    """
    Recibe lista de nombres de columna reales y retorna
    dict {canonical: col_real} para todos los campos detectados.

    Reglas de seguridad:
    - _TIME_FIELDS: nunca capturan columnas cuyo nombre empiece con 'fecha'
      (evita FechaIngreso -> ingreso)
    - _EXACT_ONLY_FIELDS: solo coincidencia exacta, sin substring
      (evita FechaIngreso -> fecha)
    """
    mapping: dict[str, str] = {}
    for col in columns:
        col_norm = _normalize_col(col)
        for canon, patterns in _META_PATTERNS.items():
            if canon in mapping:
                continue
            # Campos de tiempo: ignorar columnas que empiecen con 'fecha'
            if canon in _TIME_FIELDS and col_norm.startswith('fecha'):
                continue
            # Coincidencia exacta
            if col_norm in patterns:
                mapping[canon] = col
                break
            # Substring (solo para patrones >= 4 chars, y no para campos exactos)
            if canon in _EXACT_ONLY_FIELDS:
                continue
            for p in patterns:
                if len(p) >= 4 and p in col_norm:
                    mapping[canon] = col
                    break
    return mapping


# ---------------------------------------------------------------------------
# Detector de formato
# ---------------------------------------------------------------------------

def detectar_formato(df: pd.DataFrame) -> str:
    """
    Detecta el formato de un DataFrame de asistencia.
    Prioridad: PAPELETAS > TRANSACCIONAL > WIDE > DESCONOCIDO
    """
    cols_norm = [_normalize_col(c) for c in df.columns]

    # PAPELETAS: tiene TipoPermiso  O  (FechaInicio + FechaFin)
    has_tipo_permiso = any(
        'tipopermiso' in c or c == 'permiso' or 'tipoabsencia' in c
        for c in cols_norm
    )
    has_fecha_ini = any(
        'fechainicio' in c or c in ('inicio', 'desde', 'start')
        for c in cols_norm
    )
    has_fecha_fin = any(
        'fechafin' in c or c in ('fin', 'hasta', 'end')
        for c in cols_norm
    )
    if has_tipo_permiso or (has_fecha_ini and has_fecha_fin):
        return FORMAT_PAPELETAS

    # TRANSACCIONAL: tiene (Fecha) + (Ingreso o Salida)
    has_fecha   = any(c in ('fecha', 'date', 'dia', 'fechaasistencia') for c in cols_norm)
    has_ingreso = any('ingreso' in c or 'entrada' in c or 'checkin' in c for c in cols_norm)
    has_salida  = any('salida' in c or 'checkout' in c for c in cols_norm)
    if has_fecha and (has_ingreso or has_salida):
        return FORMAT_TRANSACCIONAL

    # WIDE: >= MIN_DATE_COLS columnas que parsean como fechas
    date_count = sum(1 for c in df.columns if _parse_date_column(c) is not None)
    if date_count >= _MIN_DATE_COLS:
        return FORMAT_WIDE

    return FORMAT_DESCONOCIDO


# ---------------------------------------------------------------------------
# Parser principal
# ---------------------------------------------------------------------------

class FlexibleAttendanceParser:
    """
    Importador flexible de asistencia: analiza un archivo Excel,
    detecta el formato de cada hoja y parsea los datos en el mismo
    esquema que SynkroParser para ser consumido por TareoProcessor.
    """

    def __init__(self, ruta_o_buffer, config=None):
        self.ruta   = ruta_o_buffer
        self.config = config
        self._wb    = None

    # ── Workbook ─────────────────────────────────────────────────

    def _get_wb(self):
        if self._wb is None:
            self._wb = pd.ExcelFile(self.ruta)
        return self._wb

    def hojas_disponibles(self) -> list[str]:
        return self._get_wb().sheet_names

    # ── Analisis rapido (sin parsear datos) ──────────────────────

    def analizar(self) -> dict[str, str]:
        """Retorna {hoja: formato} para todas las hojas del archivo."""
        resultado: dict[str, str] = {}
        for hoja in self.hojas_disponibles():
            try:
                df = pd.read_excel(self.ruta, sheet_name=hoja, header=0, nrows=5)
                resultado[hoja] = detectar_formato(df)
            except Exception as exc:
                resultado[hoja] = FORMAT_DESCONOCIDO
                logger.warning('FlexibleParser: error analizando hoja "%s": %s', hoja, exc)
        return resultado

    # ── Parseo completo ──────────────────────────────────────────

    def parse_todo(self) -> dict:
        """
        Parsea todas las hojas del archivo y consolida los resultados.

        Retorna:
        {
            'registros':    [...],   # para TareoProcessor.procesar()
            'papeletas':    [...],
            'fechas':       [date, ...],
            'hojas':        {hoja: formato, ...},
            'advertencias': [...],
            'errores':      [...],
        }
        """
        registros    = []
        papeletas    = []
        fechas_set   = set()
        advertencias = []
        errores      = []
        hojas_fmt    = {}

        for hoja in self.hojas_disponibles():
            try:
                df  = pd.read_excel(self.ruta, sheet_name=hoja, header=0)
                fmt = detectar_formato(df)
                hojas_fmt[hoja] = fmt
                logger.info(
                    'FlexibleParser: hoja "%s" -> %s (%d filas, %d cols)',
                    hoja, fmt, len(df), len(df.columns)
                )

                if fmt == FORMAT_WIDE:
                    res = self._parse_wide(df, hoja)
                    registros    += res['registros']
                    fechas_set   |= set(res['fechas'])
                    advertencias += res['advertencias']
                    errores      += res['errores']

                elif fmt == FORMAT_TRANSACCIONAL:
                    res = self._parse_transaccional(df, hoja)
                    registros    += res['registros']
                    fechas_set   |= set(res['fechas'])
                    advertencias += res['advertencias']
                    errores      += res['errores']

                elif fmt == FORMAT_PAPELETAS:
                    res = self._parse_papeletas(df, hoja)
                    papeletas    += res['papeletas']
                    advertencias += res['advertencias']
                    errores      += res['errores']

                else:
                    preview = list(df.columns)[:6]
                    advertencias.append(
                        f'Hoja "{hoja}": formato no reconocido, se omite. '
                        f'Columnas detectadas: {preview}'
                    )

            except Exception as exc:
                errores.append(f'Hoja "{hoja}": error inesperado — {exc}')
                logger.exception('FlexibleParser: error procesando hoja "%s"', hoja)

        return {
            'registros':    registros,
            'papeletas':    papeletas,
            'fechas':       sorted(fechas_set),
            'hojas':        hojas_fmt,
            'advertencias': advertencias,
            'errores':      errores,
        }

    # ── Formato WIDE ─────────────────────────────────────────────

    def _parse_wide(self, df: pd.DataFrame, hoja: str = '') -> dict:
        """
        Parsea formato ancho (pivote): columnas meta + columnas-fecha.
        Deteccion de columnas por nombre, no por indice fijo.

        Robustez:
        - Forward-fill columnas meta (area, cargo, nombre) para celdas combinadas
        - Inferencia de año: si la mayoría de fechas caen > 60 días en el futuro,
          reinterpreta las columnas 'Mar-1' con el año anterior
        - DNI zero-padding para evitar pérdida del cero inicial en Excel
        """
        registros    = []
        advertencias = []
        errores      = []

        cols    = list(df.columns)
        col_map = _map_columns(cols)

        if 'dni' not in col_map:
            errores.append(
                f'Hoja "{hoja}" (WIDE): no se encontro columna DNI. '
                f'Columnas: {cols[:10]}'
            )
            return {'registros': [], 'fechas': [], 'advertencias': [], 'errores': errores}

        # Forward-fill columnas de texto para manejar celdas combinadas (merged cells).
        # Excel con celdas fusionadas verticalmente deja NaN en las filas secundarias.
        meta_fill_cols = [
            col_map.get(k) for k in ('nombre', 'condicion', 'tipo_trabajador', 'area', 'cargo')
            if col_map.get(k)
        ]
        if meta_fill_cols:
            df = df.copy()
            df[meta_fill_cols] = df[meta_fill_cols].ffill()

        # Columnas-fecha (encabezados que parsean como date)
        col_fechas: dict[int, date] = {}
        for i, c in enumerate(cols):
            d = _parse_date_column(c)
            if d is not None:
                col_fechas[i] = d

        if not col_fechas:
            errores.append(
                f'Hoja "{hoja}" (WIDE): no se detectaron columnas de fecha.'
            )
            return {'registros': [], 'fechas': [], 'advertencias': [], 'errores': errores}

        # Inferencia de año: re-parsear si la mayoría de fechas están en el futuro
        anio_corregido = _inferir_anio_columnas(col_fechas)
        if anio_corregido:
            col_fechas_v2: dict[int, date] = {}
            for i, c in enumerate(cols):
                d = _parse_date_column_year(c, anio_corregido)
                if d is not None:
                    col_fechas_v2[i] = d
            if col_fechas_v2:
                advertencias.append(
                    f'Hoja "{hoja}" (WIDE): año ajustado a {anio_corregido} '
                    f'(las fechas originales estaban en el futuro).'
                )
                col_fechas = col_fechas_v2

        fechas_detectadas = sorted(col_fechas.values())

        for idx, row in df.iterrows():
            raw      = dict(zip(cols, row))
            row_vals = list(row)

            # DNI (ya zero-padded por _clean_dni)
            dni = _clean_dni(raw.get(col_map['dni'], ''))
            if not dni or dni.lower() in ('nan', 'none', '', 'dni'):
                continue
            if not dni.isdigit():
                advertencias.append(
                    f'Hoja "{hoja}" fila {idx + 2}: DNI "{dni}" no numerico, se omite.'
                )
                continue

            # Meta del empleado
            nombre    = str(raw.get(col_map.get('nombre',          ''), '')).strip()
            condicion = str(raw.get(col_map.get('condicion',       ''), '')).strip()
            tipo_trab = str(raw.get(col_map.get('tipo_trabajador', ''), '')).strip()
            area      = str(raw.get(col_map.get('area',            ''), '')).strip()
            cargo     = str(raw.get(col_map.get('cargo',           ''), '')).strip()

            condicion_norm = _norm_condicion(condicion)

            # Un registro por cada columna-fecha
            for col_idx, fecha in col_fechas.items():
                if col_idx >= len(row_vals):
                    continue
                val = row_vals[col_idx]
                codigo, horas = _parse_valor_dia(val)
                registros.append({
                    'dni':             dni,
                    'nombre':          nombre,
                    'condicion':       condicion_norm,
                    'tipo_trabajador': tipo_trab,
                    'area':            area,
                    'cargo':           cargo,
                    'fecha':           fecha,
                    'valor_raw':       str(val),
                    'codigo':          codigo,
                    'horas':           horas,
                })

        return {
            'registros':    registros,
            'fechas':       fechas_detectadas,
            'advertencias': advertencias,
            'errores':      errores,
        }

    # ── Formato TRANSACCIONAL ────────────────────────────────────

    def _parse_transaccional(self, df: pd.DataFrame, hoja: str = '') -> dict:
        """
        Parsea formato transaccional: una fila por persona-dia con horarios.
        Calcula horas trabajadas a partir de entrada / salida.
        """
        registros    = []
        advertencias = []
        errores      = []

        cols    = list(df.columns)
        col_map = _map_columns(cols)

        if 'dni' not in col_map:
            errores.append(
                f'Hoja "{hoja}" (TRANSACCIONAL): no se encontro columna DNI. '
                f'Columnas: {cols[:10]}'
            )
            return {'registros': [], 'fechas': [], 'advertencias': [], 'errores': errores}

        if 'fecha' not in col_map:
            errores.append(
                f'Hoja "{hoja}" (TRANSACCIONAL): no se encontro columna Fecha.'
            )
            return {'registros': [], 'fechas': [], 'advertencias': [], 'errores': errores}

        fechas_set: set[date] = set()

        for idx, row in df.iterrows():
            raw = dict(zip(cols, row))

            # DNI
            dni = _clean_dni(raw.get(col_map['dni'], ''))
            if not dni or dni.lower() in ('nan', 'none', '', 'dni'):
                continue
            if not dni.isdigit():
                advertencias.append(
                    f'Hoja "{hoja}" fila {idx + 2}: DNI "{dni}" no numerico, se omite.'
                )
                continue

            # Fecha del registro
            fecha = _parse_fecha_flex(raw.get(col_map['fecha']))
            if not fecha:
                advertencias.append(
                    f'Hoja "{hoja}" fila {idx + 2} DNI {dni}: fecha invalida, se omite.'
                )
                continue
            fechas_set.add(fecha)

            # Meta del empleado
            nombre    = str(raw.get(col_map.get('nombre',          ''), '')).strip()
            condicion = str(raw.get(col_map.get('condicion',       ''), '')).strip()
            tipo_trab = str(raw.get(col_map.get('tipo_trabajador', ''), '')).strip()
            area      = str(raw.get(col_map.get('area',            ''), '')).strip()
            cargo     = str(raw.get(col_map.get('cargo',           ''), '')).strip()

            # Horarios
            ingreso    = raw.get(col_map.get('ingreso',       ''))
            refrigerio = raw.get(col_map.get('refrigerio',    ''))
            fin_refrig = raw.get(col_map.get('fin_refrigerio',''))
            salida     = raw.get(col_map.get('salida',        ''))

            codigo, horas = _compute_hours_from_times(
                ingreso, salida, refrigerio, fin_refrig, fecha
            )

            # Representacion legible del valor crudo
            t_in  = _parse_time_flex(ingreso)
            t_out = _parse_time_flex(salida)
            valor_raw = (
                f'{t_in.strftime("%H:%M") if t_in else "?"}'
                f'-{t_out.strftime("%H:%M") if t_out else "?"}'
            )

            registros.append({
                'dni':             dni,
                'nombre':          nombre,
                'condicion':       _norm_condicion(condicion),
                'tipo_trabajador': tipo_trab,
                'area':            area,
                'cargo':           cargo,
                'fecha':           fecha,
                'valor_raw':       valor_raw,
                'codigo':          codigo,
                'horas':           horas,
            })

        return {
            'registros':    registros,
            'fechas':       sorted(fechas_set),
            'advertencias': advertencias,
            'errores':      errores,
        }

    # ── Formato PAPELETAS ────────────────────────────────────────

    def _parse_papeletas(self, df: pd.DataFrame, hoja: str = '') -> dict:
        """
        Parsea formato papeletas: TipoPermiso + DNI + rango de fechas.
        Salida compatible con PapeletaRaw de SynkroParser.
        """
        papeletas    = []
        advertencias = []
        errores      = []

        cols    = list(df.columns)
        col_map = _map_columns(cols)

        if 'dni' not in col_map:
            errores.append(
                f'Hoja "{hoja}" (PAPELETAS): no se encontro columna DNI. '
                f'Columnas: {cols[:10]}'
            )
            return {'papeletas': [], 'advertencias': [], 'errores': errores}

        for idx, row in df.iterrows():
            raw = dict(zip(cols, row))

            # DNI
            dni = _clean_dni(raw.get(col_map['dni'], ''))
            if not dni:
                continue
            if not str(dni).isdigit():
                lc = str(dni).strip().lower()
                if lc not in ('', 'nan', 'none', 'dni'):
                    advertencias.append(
                        f'Hoja "{hoja}" fila {idx + 2}: DNI "{dni}" invalido, se omite.'
                    )
                continue

            # Fechas
            fecha_ini = _parse_fecha_flex(raw.get(col_map.get('fecha_inicio', '')))
            fecha_fin = _parse_fecha_flex(raw.get(col_map.get('fecha_fin',    '')))
            if not fecha_ini or not fecha_fin:
                advertencias.append(
                    f'Hoja "{hoja}" fila {idx + 2} DNI {dni}: '
                    f'fechas invalidas ('
                    f'{raw.get(col_map.get("fecha_inicio", ""))} - '
                    f'{raw.get(col_map.get("fecha_fin", ""))}), se omite.'
                )
                continue

            # Campos opcionales
            tipo_raw  = str(raw.get(col_map.get('tipo_permiso', ''), '')).strip()
            iniciales = str(raw.get(col_map.get('iniciales',    ''), '')).strip().upper()
            nombre    = str(raw.get(col_map.get('nombre',       ''), '')).strip()
            area      = str(raw.get(col_map.get('area',         ''), '')).strip()
            cargo     = str(raw.get(col_map.get('cargo',        ''), '')).strip()
            detalle   = str(raw.get(col_map.get('detalle',      ''), '')).strip()

            # Si no hay iniciales, usar los primeros 5 chars del tipo_raw
            if not iniciales and tipo_raw:
                iniciales = tipo_raw.upper()[:5]

            # dni ya fue zero-padded por _clean_dni — no re-convertir a int (pierde el 0)
            papeletas.append({
                'dni':              dni,
                'nombre':           nombre,
                'area':             area,
                'cargo':            cargo,
                'tipo_permiso_raw': tipo_raw,
                'iniciales':        iniciales,
                'fecha_inicio':     fecha_ini,
                'fecha_fin':        fecha_fin,
                'detalle':          detalle,
            })

        return {
            'papeletas':    papeletas,
            'advertencias': advertencias,
            'errores':      errores,
        }
