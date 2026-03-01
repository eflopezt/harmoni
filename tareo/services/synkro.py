"""
Importador del reporte Synkro (reloj biométrico + papeletas).

Soporta dos modos:
  1. Archivo combinado: contiene hojas 'Reloj' y 'Papeletas' (export estándar Synkro)
  2. Archivos separados: un Excel solo con la hoja Reloj, otro solo con Papeletas

Flujo:
  parse_reloj()      → lista de RegistroRelojRaw (dicts)
  parse_papeletas()  → lista de PapeletaRaw (dicts)
  Luego el Processor consolida ambos en RegistroTareo.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import pandas as pd

logger = logging.getLogger('personal.business')


# ──────────────────────────────────────────────────────────────
# CONSTANTES
# ──────────────────────────────────────────────────────────────

# Códigos string que puede traer el Reloj (no son horas numéricas)
CODIGOS_RELOJ = {'B', 'V', 'VAC', 'SS', 'CHE', 'DM', 'LF', 'LCG', 'LP',
                 'LSG', 'DL', 'DLA', 'FA', 'F', 'NOR', 'T', 'TR', 'FR',
                 'CDT', 'CT', 'ATM', 'A', 'DS', 'DOL', 'FC', '-'}

# Valores que indican ausencia sin código (falta)
VALORES_FALTA = {'', '-', 'nan', 'none', 'null'}

MESES_ES = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'ago': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
    'jan': 1, 'apr': 4, 'aug': 8, 'dec': 12,
}


# ──────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────

def _parse_date_column(val: Any) -> date | None:
    """
    Intenta convertir un valor de cabecera de columna en una fecha.
    Acepta: datetime, date, 'Ene-21', '21/01/2026', '2026-01-21', Excel serial int.
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date() if hasattr(val, 'date') else val
    if isinstance(val, date):
        return val
    # Excel serial number
    if isinstance(val, (int, float)):
        try:
            return pd.Timestamp('1899-12-30') + pd.Timedelta(days=int(val))
        except Exception:
            return None
    s = str(val).strip()
    # 'Ene-21', 'Feb-20', etc.
    m = re.match(r'^([A-Za-záéíóú]{3})[- _.](\d{1,2})$', s, re.IGNORECASE)
    if m:
        mes_str, dia = m.group(1).lower(), int(m.group(2))
        mes = MESES_ES.get(mes_str)
        if mes:
            anio = datetime.now().year
            try:
                return date(anio, mes, dia)
            except ValueError:
                pass
    # Formatos estándar
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


def _parse_valor_dia(val: Any) -> tuple[str | None, Decimal | None]:
    """
    Interpreta el valor de una celda diaria del Reloj.
    Retorna (codigo, horas):
      - Si es número → (None, horas)
      - Si es código string → (codigo, None)
      - Si está vacío o '-' → ('FA', None)  ← se marcará como falta
    """
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 'FA', None
    if isinstance(val, (int, float)):
        try:
            h = Decimal(str(round(float(val), 2)))
            if h > 0:
                return None, h
        except InvalidOperation:
            pass
        return 'FA', None
    s = str(val).strip().upper()
    if s in VALORES_FALTA:
        return 'FA', None
    # SS = medio día → 0.5 días → lo tratamos como código
    if s == 'SS':
        return 'SS', None
    # Si es código conocido
    if s in CODIGOS_RELOJ:
        return s, None
    # Intentar como número
    try:
        h = Decimal(s.replace(',', '.'))
        if h > 0:
            return None, h
    except InvalidOperation:
        pass
    # Código desconocido — devolver tal cual para homologación posterior
    return s if s else 'FA', None


# ──────────────────────────────────────────────────────────────
# PARSER PRINCIPAL
# ──────────────────────────────────────────────────────────────

class SynkroParser:
    """
    Parsea archivos Excel exportados por el sistema Synkro.

    Uso:
        parser = SynkroParser(ruta_archivo)
        registros = parser.parse_reloj()
        papeletas = parser.parse_papeletas()
    """

    def __init__(self, ruta_o_buffer, config=None):
        """
        ruta_o_buffer: str path o BytesIO
        config: instancia de ConfiguracionSistema (opcional, usa defaults si no se pasa)
        """
        self.ruta = ruta_o_buffer
        self.config = config
        self._workbook = None
        self._hoja_reloj = config.synkro_hoja_reloj if config else 'Reloj'
        self._hoja_papeletas = config.synkro_hoja_papeletas if config else 'Papeletas'
        self._col_dni = config.reloj_col_dni if config else 0
        self._col_nombre = config.reloj_col_nombre if config else 1
        self._col_condicion = config.reloj_col_condicion if config else 5
        self._col_tipo_trab = config.reloj_col_tipo_trab if config else 6
        self._col_area = config.reloj_col_area if config else 7
        self._col_cargo = config.reloj_col_cargo if config else 8
        self._col_inicio_dias = config.reloj_col_inicio_dias if config else 9

    def _get_workbook(self):
        if self._workbook is None:
            self._workbook = pd.ExcelFile(self.ruta)
        return self._workbook

    def hojas_disponibles(self) -> list[str]:
        return self._get_workbook().sheet_names

    def _detectar_hoja(self, nombre_buscado: str) -> str | None:
        """Busca la hoja por nombre exacto o substring case-insensitive."""
        hojas = self.hojas_disponibles()
        for h in hojas:
            if h.strip().lower() == nombre_buscado.strip().lower():
                return h
        for h in hojas:
            if nombre_buscado.lower() in h.lower():
                return h
        return None

    # ── Reloj ──────────────────────────────────────────────────

    def parse_reloj(self, hoja: str | None = None) -> dict:
        """
        Parsea la hoja Reloj.

        Retorna:
        {
          'registros': [  # lista de dicts por persona×día
            {
              'dni': str,
              'nombre': str,
              'condicion': str,        # LOCAL/FORANEO
              'tipo_trabajador': str,
              'area': str,
              'cargo': str,
              'fecha': date,
              'valor_raw': str,        # valor original de la celda
              'codigo': str|None,      # código si es string
              'horas': Decimal|None,   # horas si es numérico
            }
          ],
          'fechas': [date, ...],       # fechas detectadas (columnas)
          'personas': [...],           # resumen por persona
          'advertencias': [...],
          'errores': [...],
        }
        """
        hoja_real = hoja or self._detectar_hoja(self._hoja_reloj)
        if not hoja_real:
            # Intentar detectar automáticamente: buscar hoja con columnas de fechas
            hoja_real = self._auto_detectar_hoja_reloj()

        if not hoja_real:
            return {'registros': [], 'fechas': [], 'personas': [],
                    'advertencias': [], 'errores': [f'No se encontró hoja Reloj. Disponibles: {self.hojas_disponibles()}']}

        df_raw = pd.read_excel(self.ruta, sheet_name=hoja_real, header=0)
        return self._procesar_df_reloj(df_raw)

    def _auto_detectar_hoja_reloj(self) -> str | None:
        """
        Detecta automáticamente qué hoja es el Reloj buscando la que tiene
        más columnas con fechas y una columna DNI.
        """
        mejor_hoja = None
        mejor_score = 0
        for h in self.hojas_disponibles():
            try:
                df = pd.read_excel(self.ruta, sheet_name=h, header=0, nrows=3)
                fechas = sum(1 for c in df.columns if _parse_date_column(c))
                if fechas > mejor_score:
                    mejor_score = fechas
                    mejor_hoja = h
            except Exception:
                continue
        return mejor_hoja if mejor_score >= 5 else None

    def _procesar_df_reloj(self, df: pd.DataFrame) -> dict:
        registros = []
        advertencias = []
        errores = []

        cols = list(df.columns)
        # Detectar qué columnas son fechas (día a día)
        col_fechas = {}  # col_index → date
        for i, c in enumerate(cols):
            if i < self._col_inicio_dias:
                continue
            d = _parse_date_column(c)
            if d:
                col_fechas[i] = d

        if not col_fechas:
            errores.append('No se detectaron columnas de fechas. Verifica el formato del archivo.')
            return {'registros': [], 'fechas': [], 'personas': [],
                    'advertencias': advertencias, 'errores': errores}

        fechas_detectadas = sorted(col_fechas.values())
        personas_set = {}

        for idx, row in df.iterrows():
            # Leer datos del empleado
            raw_vals = list(row)

            dni = str(raw_vals[self._col_dni]).strip() if len(raw_vals) > self._col_dni else ''
            nombre = str(raw_vals[self._col_nombre]).strip() if len(raw_vals) > self._col_nombre else ''
            condicion = str(raw_vals[self._col_condicion]).strip().upper() if len(raw_vals) > self._col_condicion else ''
            tipo_trab = str(raw_vals[self._col_tipo_trab]).strip() if len(raw_vals) > self._col_tipo_trab else ''
            area = str(raw_vals[self._col_area]).strip() if len(raw_vals) > self._col_area else ''
            cargo = str(raw_vals[self._col_cargo]).strip() if len(raw_vals) > self._col_cargo else ''

            # Limpiar DNI (quitar punto decimal si lo tiene)
            dni = re.sub(r'\.0$', '', dni)
            if not dni or dni.lower() in ('nan', 'none', '', 'dni'):
                continue  # fila de encabezado o vacía
            if not dni.isdigit():
                advertencias.append(f'Fila {idx+2}: DNI "{dni}" no es numérico, se omite.')
                continue

            # Normalizar condición
            if 'FOR' in condicion or 'FO' == condicion[:2]:
                condicion_norm = 'FORANEO'
            elif 'LIM' in condicion:
                condicion_norm = 'LIMA'
            else:
                condicion_norm = 'LOCAL'

            personas_set[dni] = {
                'nombre': nombre, 'condicion': condicion_norm,
                'tipo_trab': tipo_trab, 'area': area, 'cargo': cargo
            }

            # Procesar cada día
            for col_idx, fecha in col_fechas.items():
                if col_idx >= len(raw_vals):
                    continue
                val = raw_vals[col_idx]
                codigo, horas = _parse_valor_dia(val)

                registros.append({
                    'dni': dni,
                    'nombre': nombre,
                    'condicion': condicion_norm,
                    'tipo_trabajador': tipo_trab,
                    'area': area,
                    'cargo': cargo,
                    'fecha': fecha,
                    'valor_raw': str(val),
                    'codigo': codigo,
                    'horas': horas,
                })

        return {
            'registros': registros,
            'fechas': fechas_detectadas,
            'personas': list(personas_set.values()),
            'advertencias': advertencias,
            'errores': errores,
        }

    # ── Papeletas ───────────────────────────────────────────────

    def parse_papeletas(self, hoja: str | None = None) -> dict:
        """
        Parsea la hoja Papeletas.

        Formato esperado (Synkro estándar):
          TipoPermiso | DNI | Personal | Area | Cargo | Iniciales | FechaInicio | FechaFin | Detalle

        Retorna lista de dicts.
        """
        hoja_real = hoja or self._detectar_hoja(self._hoja_papeletas)
        if not hoja_real:
            return {'papeletas': [], 'advertencias': ['No se encontró hoja Papeletas.'], 'errores': []}

        df = pd.read_excel(self.ruta, sheet_name=hoja_real, header=0)
        return self._procesar_df_papeletas(df)

    def _procesar_df_papeletas(self, df: pd.DataFrame) -> dict:
        papeletas = []
        advertencias = []
        errores = []

        # Normalizar nombres de columnas para mapeo flexible
        col_map = self._mapear_columnas_papeletas(list(df.columns))

        for idx, row in df.iterrows():
            raw = dict(zip(df.columns, row))

            dni_raw = raw.get(col_map.get('dni', ''), '')
            dni = re.sub(r'\.0$', '', str(dni_raw).strip())
            dni = dni if dni else ''

            if not dni or not str(dni).isdigit():
                if str(dni).strip().lower() not in ('', 'nan', 'none', 'dni'):
                    advertencias.append(f'Papeleta fila {idx+2}: DNI "{dni}" inválido, se omite.')
                continue

            tipo_raw = str(raw.get(col_map.get('tipo_permiso', ''), '')).strip()
            iniciales = str(raw.get(col_map.get('iniciales', ''), '')).strip().upper()
            fecha_ini_raw = raw.get(col_map.get('fecha_inicio', ''), None)
            fecha_fin_raw = raw.get(col_map.get('fecha_fin', ''), None)
            nombre = str(raw.get(col_map.get('nombre', ''), '')).strip()
            area = str(raw.get(col_map.get('area', ''), '')).strip()
            cargo = str(raw.get(col_map.get('cargo', ''), '')).strip()
            detalle = str(raw.get(col_map.get('detalle', ''), '')).strip()

            fecha_ini = self._parse_fecha(fecha_ini_raw)
            fecha_fin = self._parse_fecha(fecha_fin_raw)

            if not fecha_ini or not fecha_fin:
                advertencias.append(f'Papeleta fila {idx+2} DNI {dni}: fechas inválidas ({fecha_ini_raw}–{fecha_fin_raw}), se omite.')
                continue

            papeletas.append({
                'dni': str(int(float(dni))),
                'nombre': nombre,
                'area': area,
                'cargo': cargo,
                'tipo_permiso_raw': tipo_raw,
                'iniciales': iniciales,
                'fecha_inicio': fecha_ini,
                'fecha_fin': fecha_fin,
                'detalle': detalle,
            })

        return {'papeletas': papeletas, 'advertencias': advertencias, 'errores': errores}

    def _mapear_columnas_papeletas(self, columnas: list) -> dict:
        """
        Mapea columnas reales del DataFrame a nombres canónicos.
        Flexible ante variaciones de nombre.
        """
        mapping = {}
        patrones = {
            'tipo_permiso': ['tipopermiso', 'tipo_permiso', 'tipo permiso', 'permiso', 'tipo'],
            'dni': ['dni', 'documento', 'nro_doc', 'nrodoc', 'num_doc'],
            'nombre': ['personal', 'nombre', 'apellidos', 'apellidos_nombres', 'trabajador'],
            'area': ['area', 'área', 'area_trabajo', 'areatrabajo', 'departamento'],
            'cargo': ['cargo', 'puesto', 'ocupacion'],
            'iniciales': ['iniciales', 'codigo', 'código', 'abrev'],
            'fecha_inicio': ['fechainicio', 'fecha_inicio', 'fecha inicio', 'inicio', 'desde'],
            'fecha_fin': ['fechafin', 'fecha_fin', 'fecha fin', 'fin', 'hasta'],
            'detalle': ['detalle', 'motivo', 'observacion', 'descripcion', 'comentario'],
        }
        for col in columnas:
            col_norm = str(col).lower().strip().replace(' ', '').replace('_', '')
            for canon, variantes in patrones.items():
                if canon not in mapping:
                    if col_norm in [v.replace(' ', '').replace('_', '') for v in variantes]:
                        mapping[canon] = col
                        break
        return mapping

    @staticmethod
    def _parse_fecha(val) -> date | None:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return None
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


# ──────────────────────────────────────────────────────────────
# HELPER: re.sub con 1 arg  (limpiar DNI)
# ──────────────────────────────────────────────────────────────

def _strip_decimal(s: str) -> str:
    return re.sub(r'\.0$', '', str(s).strip())


# Parchear el método que lo usa
def _fix_dni(raw) -> str:
    return _strip_decimal(str(raw))
