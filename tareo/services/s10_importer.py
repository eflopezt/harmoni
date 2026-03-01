"""
Importador del reporte S10 (sistema de gestión de obras).

Soporta variaciones de cabeceras entre versiones de S10.
Usa mapeo flexible + IA (opcional) para detectar columnas.

Columnas esperadas (pueden variar):
  Código | Nombre | Código categoría | Categoría | DNI | Recurso equiv. |
  Ocupación | Régimen Pensión | Fechas | CUSPP | AFP | SCTR |
  Partida | Proyecto | Correo...
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

logger = logging.getLogger('personal.business')

# Mapeo flexible de columnas S10 → campo canónico
# key: campo canónico, value: lista de posibles nombres de columna
COLUMNAS_S10 = {
    'codigo_s10':   ['código', 'codigo', 'cod.', 'cod'],
    'nombre':       ['nombre', 'apellidos y nombres', 'apellidos_nombres', 'trabajador'],
    'dni':          ['dni', 'doc. identidad', 'nro_doc', 'n° documento', 'documento'],
    'categoria_cod':['código categoría', 'cod. cat', 'cod categoria'],
    'categoria':    ['categoría', 'categoria', 'cat.'],
    'ocupacion':    ['ocupación', 'ocupacion', 'puesto', 'cargo'],
    'regimen_pension': ['régimen pensión', 'regimen pension', 'afp', 'pension'],
    'fecha_ingreso': ['fecha ingreso', 'fecha_ingreso', 'ingreso', 'f. ingreso'],
    'fecha_cese':   ['fecha cese', 'fecha_cese', 'cese', 'f. cese'],
    'cuspp':        ['cuspp', 'cod. afp'],
    'partida':      ['partida de control', 'partida control', 'partida', 'cod. partida'],
    'proyecto':     ['código proyecto destino', 'proyecto destino', 'proyecto', 'cod. proyecto'],
    'correo':       ['correo personal', 'correo', 'email', 'e-mail'],
    'he_25':        ['horas extras 25%', 'he 25%', 'he25'],
    'he_35':        ['horas extras 35%', 'he 35%', 'he35'],
    'he_100':       ['horas extras 100%', 'he 100%', 'he100'],
    'adelanto_ct':  ['adelanto condicion', 'adelanto cond', 'condicion trabajo'],
}


def importar_s10(ruta_o_buffer, importacion, actualizar_personal: bool = True,
                 usar_ia: bool = False) -> dict:
    """
    Importa reporte S10 (Excel).

    ruta_o_buffer: path string o BytesIO
    importacion: instancia de TareoImportacion
    actualizar_personal: sincroniza codigo_s10, partida_control en Personal
    usar_ia: intenta usar Claude API para mapeo de columnas desconocidas

    Retorna dict con contadores.
    """
    from personal.models import Personal
    from tareo.models import RegistroS10

    errores = []
    advertencias = []
    creados = 0
    sin_match = 0

    # ── Leer Excel ────────────────────────────────────────────
    try:
        df, hoja_usada = _leer_excel_s10(ruta_o_buffer, advertencias)
    except Exception as e:
        errores.append(f'Error leyendo archivo: {e}')
        importacion.estado = 'FALLIDO'
        importacion.errores = errores
        importacion.save()
        return {'creados': 0, 'errores': errores}

    if df is None or df.empty:
        errores.append('El archivo está vacío o no se pudo leer.')
        importacion.estado = 'FALLIDO'
        importacion.errores = errores
        importacion.save()
        return {'creados': 0, 'errores': errores}

    # ── Mapear columnas ───────────────────────────────────────
    col_map = _mapear_columnas(list(df.columns), usar_ia, importacion, advertencias)

    personal_map = {p.nro_doc: p for p in Personal.objects.all()}
    periodo = (f"{importacion.periodo_inicio.month:02d}/"
               f"{importacion.periodo_inicio.year}"
               if importacion.periodo_inicio else '')

    for idx, row in df.iterrows():
        raw = dict(zip(df.columns, row))

        # DNI
        dni_raw = raw.get(col_map.get('dni', '___'), '')
        dni = _limpiar_dni(str(dni_raw))
        if not dni:
            continue

        codigo_s10 = str(raw.get(col_map.get('codigo_s10', '___'), '')).strip()
        nombre = str(raw.get(col_map.get('nombre', '___'), '')).strip()
        ocupacion = str(raw.get(col_map.get('ocupacion', '___'), '')).strip()
        categoria = str(raw.get(col_map.get('categoria', '___'), '')).strip()
        partida = str(raw.get(col_map.get('partida', '___'), '')).strip()
        proyecto = str(raw.get(col_map.get('proyecto', '___'), '')).strip()
        regimen_pension = str(raw.get(col_map.get('regimen_pension', '___'), '')).strip()
        correo = str(raw.get(col_map.get('correo', '___'), '')).strip()
        fecha_ingreso = _parse_fecha(raw.get(col_map.get('fecha_ingreso', '___'), ''))
        fecha_cese = _parse_fecha(raw.get(col_map.get('fecha_cese', '___'), ''))
        he_25 = _parse_decimal(raw.get(col_map.get('he_25', '___'), ''))
        he_35 = _parse_decimal(raw.get(col_map.get('he_35', '___'), ''))
        he_100 = _parse_decimal(raw.get(col_map.get('he_100', '___'), ''))
        adelanto_ct = _parse_decimal(raw.get(col_map.get('adelanto_ct', '___'), ''))

        personal_obj = personal_map.get(dni)
        if not personal_obj:
            sin_match += 1

        # Campos extra no mapeados
        columnas_mapeadas = set(col_map.values())
        datos_extra = {
            str(k): str(v) for k, v in raw.items()
            if k not in columnas_mapeadas and str(v).strip() not in ('', 'nan', 'None')
        }

        _, created = RegistroS10.objects.update_or_create(
            importacion=importacion,
            nro_doc=dni,
            defaults={
                'personal': personal_obj,
                'codigo_s10': codigo_s10,
                'apellidos_nombres': nombre,
                'ocupacion': ocupacion,
                'categoria': categoria,
                'periodo': periodo,
                'fecha_ingreso': fecha_ingreso,
                'fecha_cese': fecha_cese,
                'horas_extra_25': he_25,
                'horas_extra_35': he_35,
                'horas_extra_100': he_100,
                'adelanto_condicion_trabajo': adelanto_ct,
                'partida_control': partida,
                'codigo_proyecto': proyecto,
                'regimen_pension': regimen_pension,
                'datos_extra': datos_extra,
            }
        )
        if created:
            creados += 1

        # Actualizar Personal
        if actualizar_personal and personal_obj:
            _sync_personal(personal_obj, codigo_s10, partida, correo,
                           regimen_pension, fecha_ingreso)

    importacion.total_registros = len(df)
    importacion.registros_ok = creados
    importacion.registros_sin_match = sin_match
    importacion.estado = 'COMPLETADO_CON_ERRORES' if errores else 'COMPLETADO'
    importacion.errores = errores
    importacion.advertencias = advertencias
    importacion.save()

    logger.info(f'S10 importado: {creados} registros, {sin_match} sin match.')
    return {'creados': creados, 'sin_match': sin_match,
            'errores': errores, 'advertencias': advertencias}


# ──────────────────────────────────────────────────────────────
# HELPERS INTERNOS
# ──────────────────────────────────────────────────────────────

def _leer_excel_s10(ruta_o_buffer, advertencias: list) -> tuple:
    """
    Intenta leer la hoja S10 del Excel.
    Si no existe, usa la primera hoja disponible.
    Detecta automáticamente la fila de encabezado (puede estar en fila 1, 2 ó 3).
    """
    try:
        xl = pd.ExcelFile(ruta_o_buffer)
    except Exception as e:
        raise ValueError(f'No se pudo abrir el archivo Excel: {e}')

    # Preferir hoja llamada 'S10' o 'Trabajadores'
    hoja_target = None
    for h in xl.sheet_names:
        if h.upper() in ('S10', 'TRABAJADORES', 'PERSONAL', 'WORKERS'):
            hoja_target = h
            break
    if not hoja_target:
        hoja_target = xl.sheet_names[0]
        advertencias.append(f'No se encontró hoja S10; usando primera hoja: "{hoja_target}".')

    # Detectar fila de encabezado (buscar la que tiene 'DNI' o 'Código')
    for header_row in range(0, 5):
        df = pd.read_excel(ruta_o_buffer, sheet_name=hoja_target, header=header_row)
        cols_lower = [str(c).lower() for c in df.columns]
        if any('dni' in c or 'código' in c or 'nombre' in c for c in cols_lower):
            return df, hoja_target

    # Fallback: leer con header=0
    df = pd.read_excel(ruta_o_buffer, sheet_name=hoja_target, header=0)
    return df, hoja_target


def _mapear_columnas(columnas: list, usar_ia: bool, importacion,
                     advertencias: list) -> dict:
    """
    Construye col_map: campo_canonico → nombre_columna_real.
    Primero intenta por matching de texto, luego opcionalmente IA.
    """
    col_map: dict[str, str] = {}
    cols_norm = {str(c).lower().strip(): str(c) for c in columnas}

    for campo, variantes in COLUMNAS_S10.items():
        for variante in variantes:
            v_norm = variante.lower().strip()
            # Exact match
            if v_norm in cols_norm:
                col_map[campo] = cols_norm[v_norm]
                break
            # Substring match
            for col_lower, col_real in cols_norm.items():
                if v_norm in col_lower or col_lower in v_norm:
                    if campo not in col_map:
                        col_map[campo] = col_real
                    break

    # Mapear campos críticos no encontrados via IA
    campos_faltantes = [c for c in ['dni', 'nombre', 'codigo_s10'] if c not in col_map]
    if campos_faltantes and usar_ia:
        ia_map = _mapear_con_ia(columnas, campos_faltantes, importacion)
        col_map.update(ia_map)
        if ia_map:
            advertencias.append(f'IA detectó columnas: {ia_map}')

    if 'dni' not in col_map:
        advertencias.append('No se detectó columna DNI en el archivo S10.')

    return col_map


def _mapear_con_ia(columnas: list, campos_faltantes: list, importacion) -> dict:
    """
    Usa Claude API para detectar columnas no identificadas por texto.
    Requiere anthropic_api_key en ConfiguracionSistema.
    """
    try:
        from tareo.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        if not config.anthropic_api_key or not config.ia_mapeo_activo:
            return {}

        import anthropic
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)

        prompt = (
            f"Tengo un archivo Excel con las siguientes columnas: {columnas}\n\n"
            f"Necesito identificar cuáles corresponden a estos campos: {campos_faltantes}\n\n"
            f"Los campos son:\n"
            f"- dni: número de documento de identidad del trabajador\n"
            f"- nombre: apellidos y nombres completos\n"
            f"- codigo_s10: código interno del sistema S10\n\n"
            f"Responde SOLO con un JSON como: "
            f'{{\"dni\": \"nombre_columna\", \"nombre\": \"nombre_columna\"}}\n'
            f"Si no encuentras un campo, omítelo del JSON."
        )

        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=200,
            messages=[{'role': 'user', 'content': prompt}]
        )

        import json
        text = msg.content[0].text.strip()
        # Extraer JSON de la respuesta
        match = re.search(r'\{[^}]+\}', text)
        if match:
            mapping = json.loads(match.group())
            # Validar que las columnas sugeridas existen
            return {k: v for k, v in mapping.items() if v in columnas}

    except Exception as e:
        logger.warning(f'IA mapeo falló: {e}')
    return {}


def _limpiar_dni(val: str) -> str:
    s = re.sub(r'\.0$', '', str(val).strip())
    s = re.sub(r'\s+', '', s)
    return s if len(s) >= 7 else ''


def _parse_fecha(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if hasattr(val, 'date'):
        return val.date()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except (ValueError, TypeError):
            pass
    return None


def _parse_decimal(val) -> Decimal | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return Decimal(str(val).strip().replace(',', '.'))
    except InvalidOperation:
        return None


def _sync_personal(personal_obj, codigo_s10, partida, correo,
                   regimen_pension, fecha_ingreso) -> None:
    changed = []
    if codigo_s10 and not personal_obj.codigo_s10:
        personal_obj.codigo_s10 = codigo_s10
        changed.append('codigo_s10')
    if partida and not personal_obj.partida_control:
        personal_obj.partida_control = partida
        changed.append('partida_control')
    if correo and not personal_obj.correo_corporativo:
        personal_obj.correo_corporativo = correo
        changed.append('correo_corporativo')
    if fecha_ingreso and not personal_obj.fecha_alta:
        personal_obj.fecha_alta = fecha_ingreso
        changed.append('fecha_alta')
    if changed:
        personal_obj.save(update_fields=changed)
