"""
services_pdf.py — Extracción de texto y datos de PDFs externos.

Equivalente Python del PowerShell que usaba la macro Excel de cese:
  - ExtraerDNIdePDF    → identifica al empleado en PDFs de Baja SUNAT / T-Registro
  - ExtraerNombrePDF  → identifica nombre en Boletas de Liquidación S10 (BLIQ)
  - procesar_pdf_cese → función principal: retorna dict con todos los datos encontrados

Los PDFs llegan de sistemas externos (SUNAT T-Registro, S10) y pueden tener
FlateDecode streams. pdfminer.six los descomprime automáticamente.

Uso:
    from documentos.services_pdf import procesar_pdf_cese
    resultado = procesar_pdf_cese(file_obj_o_ruta)
    # resultado = {
    #     'dni': '70112345',
    #     'nombre': 'QUISPE MAMANI CARLOS EDUARDO',
    #     'tipo_doc': 'BAJA_SUNAT' | 'BLIQ' | 'DESCONOCIDO',
    #     'texto_raw': '...',
    #     'error': None | 'mensaje',
    # }
"""
import re
import io
import logging

logger = logging.getLogger(__name__)

# ─── Patrones de búsqueda en PDF ─────────────────────────────────────────────

# DNI en PDFs de Baja SUNAT / T-Registro
_PATTERNS_DNI = [
    # Forma más común en T-Registro: "DNI - 12345678" o "DNI/12345678"
    re.compile(r'DNI\s*[-/]\s*(\d{7,8})', re.IGNORECASE),
    # SUNAT en tabla: "Tipo Doc. DNI ... Nro. 12345678"
    re.compile(r'Tipo\s+Doc[.\s]+DNI[^\d]{0,30}(\d{7,8})', re.IGNORECASE | re.DOTALL),
    # S10 liquidación: "DNI: 12345678" o "D.N.I.: 12345678"
    re.compile(r'D\.?N\.?I\.?\s*:\s*(\d{7,8})', re.IGNORECASE),
    # Fallback: 8 dígitos precedidos por "DOC" o "DOCUMENTO"
    re.compile(r'DOCUMENTO[^:\d]{0,20}(\d{8})', re.IGNORECASE),
    # Último recurso: primer grupo de 8 dígitos en el texto
    re.compile(r'\b(\d{8})\b'),
]

# Nombre completo en PDFs BLIQ de S10
_PATTERNS_NOMBRE = [
    # S10 liquidación: "Apellidos y Nombres" seguido de nombre en mayúsculas
    re.compile(r'Apellidos\s+y\s+Nombres\s*[:\s]+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]{5,60}?)(?=\s{2,}|\n|\d)', re.IGNORECASE),
    # T-Registro / SUNAT: nombre en primera línea de mayúsculas tras "Apellidos"
    re.compile(r'APELLIDOS[^\n]{0,30}\n\s*([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s,]{5,60})', re.IGNORECASE),
    # Nombre como "QUISPE MAMANI, CARLOS" (apellidos, nombres separados por coma)
    re.compile(r'\b([A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,})+,\s*[A-ZÁÉÍÓÚÑ]{2,}(?:\s+[A-ZÁÉÍÓÚÑ]{2,})*)\b'),
]

# Detectores de tipo de documento
_TIPO_BAJA_SUNAT = [
    'baja de trabajador', 'constancia de baja', 't-registro', 'tregistro',
    'baja definitiva', 'cese de trabajador', 'constancia de cese',
]
_TIPO_BLIQ = [
    'boleta de liquidacion', 'liquidacion final', 'bliq', 'liquidacion de beneficios',
    'beneficios sociales', 'cts', 'gratificacion', 'liquidacion de haberes',
]


# ─── Extracción de texto ──────────────────────────────────────────────────────

def _extract_text_from_pdf(source) -> str:
    """
    Extrae texto plano de un PDF.
    source: puede ser ruta (str/Path), BytesIO, o file-like object.
    """
    from pdfminer.high_level import extract_text as pm_extract
    try:
        if isinstance(source, (str, bytes)) and not isinstance(source, io.IOBase):
            # Es una ruta de archivo
            return pm_extract(source) or ''
        else:
            # File-like object o BytesIO
            if hasattr(source, 'read'):
                data = source.read()
                if hasattr(source, 'seek'):
                    source.seek(0)
            else:
                data = source
            buf = io.BytesIO(data) if not isinstance(data, io.BytesIO) else data
            return pm_extract(buf) or ''
    except Exception as exc:
        logger.warning(f'pdfminer error: {exc}')
        return ''


# ─── Funciones públicas ───────────────────────────────────────────────────────

def extraer_dni_de_pdf(source) -> str | None:
    """
    Extrae el DNI de 8 dígitos de un PDF.
    Equivalente Python de ExtraerDNIdePDF() del Módulo3.bas de la macro.
    Retorna string con 8 dígitos (con zero-padding) o None.
    """
    texto = _extract_text_from_pdf(source)
    if not texto:
        return None

    for pattern in _PATTERNS_DNI:
        m = pattern.search(texto)
        if m:
            dni = m.group(1).strip()
            if len(dni) in (7, 8) and dni.isdigit():
                return dni.zfill(8)

    return None


def extraer_nombre_de_pdf(source) -> str | None:
    """
    Extrae el nombre del trabajador de un PDF de boleta de liquidación (BLIQ).
    Equivalente Python de ExtraerNombreDePDF() del Módulo2.bas de la macro.
    Retorna nombre en mayúsculas o None.
    """
    texto = _extract_text_from_pdf(source)
    if not texto:
        return None

    for pattern in _PATTERNS_NOMBRE:
        m = pattern.search(texto)
        if m:
            nombre = m.group(1).strip()
            # Limpiar espacios múltiples
            nombre = re.sub(r'\s+', ' ', nombre).upper()
            # Debe tener al menos 2 palabras y longitud razonable
            if len(nombre.split()) >= 2 and 5 <= len(nombre) <= 80:
                return nombre

    return None


def _detectar_tipo_doc(texto: str) -> str:
    """Clasifica el tipo de PDF según su contenido."""
    texto_lower = texto.lower()
    for kw in _TIPO_BAJA_SUNAT:
        if kw in texto_lower:
            return 'BAJA_SUNAT'
    for kw in _TIPO_BLIQ:
        if kw in texto_lower:
            return 'BLIQ'
    return 'DESCONOCIDO'


def procesar_pdf_cese(source, filename: str = '') -> dict:
    """
    Función principal: procesa un PDF de cese y retorna todos los datos encontrados.

    Retorna:
    {
        'dni':      '12345678' | None,
        'nombre':   'QUISPE MAMANI CARLOS' | None,
        'tipo_doc': 'BAJA_SUNAT' | 'BLIQ' | 'DESCONOCIDO',
        'texto_raw': str,   # primeros 500 chars para debug
        'error':    None | str,
    }
    """
    resultado = {
        'dni': None,
        'nombre': None,
        'tipo_doc': 'DESCONOCIDO',
        'texto_raw': '',
        'error': None,
    }

    try:
        texto = _extract_text_from_pdf(source)
        resultado['texto_raw'] = texto[:500]

        if not texto.strip():
            resultado['error'] = 'PDF sin texto extraíble (posiblemente escaneado/imagen)'
            return resultado

        resultado['tipo_doc'] = _detectar_tipo_doc(texto)

        # Extraer DNI siempre (útil para ambos tipos)
        for pattern in _PATTERNS_DNI:
            m = pattern.search(texto)
            if m:
                dni = m.group(1).strip().zfill(8)
                if len(dni) == 8:
                    resultado['dni'] = dni
                    break

        # Extraer nombre (más útil en BLIQ, pero útil en cualquier tipo)
        for pattern in _PATTERNS_NOMBRE:
            m = pattern.search(texto)
            if m:
                nombre = re.sub(r'\s+', ' ', m.group(1).strip()).upper()
                if len(nombre.split()) >= 2:
                    resultado['nombre'] = nombre
                    break

        # Hint del nombre de archivo
        if filename:
            fname_upper = filename.upper()
            if 'BLIQ' in fname_upper or 'LIQUIDAC' in fname_upper:
                resultado['tipo_doc'] = 'BLIQ'
            elif 'BAJA' in fname_upper or 'SUNAT' in fname_upper or 'TREGISTRO' in fname_upper:
                resultado['tipo_doc'] = 'BAJA_SUNAT'

    except Exception as exc:
        logger.error(f'procesar_pdf_cese error ({filename}): {exc}')
        resultado['error'] = str(exc)

    return resultado


def buscar_empleado_por_pdf(source, filename: str = ''):
    """
    Procesa un PDF y retorna el objeto Personal si encuentra coincidencia por DNI.
    Importa Personal aquí para evitar import circular.

    Retorna: (personal_obj | None, resultado_dict)
    """
    from personal.models import Personal

    resultado = procesar_pdf_cese(source, filename)
    personal = None

    if resultado['dni']:
        personal = Personal.objects.filter(nro_doc=resultado['dni']).first()

    # Si no hay DNI, intentar por nombre exacto
    if personal is None and resultado['nombre']:
        personal = Personal.objects.filter(
            apellidos_nombres__iexact=resultado['nombre']
        ).first()

    return personal, resultado
