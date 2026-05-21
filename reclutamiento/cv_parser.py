"""
CV Parser — adaptación del pipeline de NexoTalent para Harmoni.

Pipeline:
  1. Extracción de texto (PDF/DOCX/TXT)
     - PyMuPDF (fitz) → más rápido para PDFs nativos
     - pdfplumber → fallback
     - python-docx → DOCX
  2. Extracción de entidades (regex + NER opcional)
     - Email, teléfono peruano, DNI/RUC
     - Skills (lista predefinida + heurísticas)
     - Experiencia (años calculados desde fechas)
     - Educación (último título/institución)

Las funciones devuelven `str` para texto o `dict` con campos extraídos.
Si todas las extracciones fallan, devuelve dict con campos vacíos —
nunca crashea.

Crédito: pipeline derivado de NexoTalent (apps/ia/pdf_extractor.py,
cv_structure.py, ner_extractor.py).
"""
from __future__ import annotations

import logging
import os
import re
from datetime import date
from typing import Optional

logger = logging.getLogger('reclutamiento.cv_parser')


# ──────────────────────────────────────────────────────────────────
# Constantes
# ──────────────────────────────────────────────────────────────────

EXTENSIONES_SOPORTADAS = {'.pdf', '.docx', '.doc', '.txt', '.rtf'}
_MIN_CHARS_OK = 80  # umbral mínimo para considerar extracción válida

# Listado de skills frecuentes en gastronomía + tech + admin
SKILLS_CATALOG = {
    # Gastronomía
    'cocina_caliente', 'cocina_fria', 'pasteleria', 'panaderia', 'parrilla',
    'sushi', 'pizza', 'mariscos', 'reposteria', 'manipulacion de alimentos',
    'haccp', 'iso 22000', 'control de costos', 'inventarios',
    # Salón / Bar
    'sommelier', 'bartender', 'cata de vinos', 'mixologia', 'atencion al cliente',
    'protocolo de servicio', 'caja', 'manejo de propinas',
    # Admin / RRHH
    'planillas', 'plame', 'sunat', 'sunafil', 'ley 27735', 'cts', 'gratificaciones',
    'liquidacion', 'reclutamiento', 'contratacion', 'evaluacion de desempeño',
    'capacitacion', 'compensaciones', 'desarrollo organizacional',
    # Idiomas
    'ingles avanzado', 'ingles intermedio', 'portugues', 'frances', 'italiano',
    'aleman', 'mandarin', 'japones', 'quechua',
    # Tech
    'excel avanzado', 'excel intermedio', 'power bi', 'sap', 'oracle', 'spring',
    'concar', 'siscont', 'tableau', 'sql', 'python', 'office',
}

# Cargos / títulos típicos peruanos (para detección de experiencia)
CARGOS_FRECUENTES = {
    'chef', 'sous chef', 'chef ejecutivo', 'chef de partie', 'commis',
    'cocinero', 'parrillero', 'panadero', 'pastelero', 'sushiman',
    'mesero', 'mesera', 'capitan de meseros', 'maitre', 'host',
    'sommelier', 'bartender', 'cajero', 'cajera', 'runner', 'busser',
    'administrador', 'gerente', 'jefe', 'supervisor', 'coordinador',
    'asistente', 'analista', 'auxiliar', 'tecnico', 'practicante',
}


# ──────────────────────────────────────────────────────────────────
# Extracción de texto (3 estrategias en cascada)
# ──────────────────────────────────────────────────────────────────

def extract_text_from_file(filepath: str) -> str:
    """Extrae texto de un archivo CV.

    Args:
        filepath: ruta absoluta al archivo.

    Returns:
        Texto extraído, o cadena vacía si no se pudo.
    """
    if not filepath or not os.path.exists(filepath):
        logger.warning('extract_text: archivo no existe: %s', filepath)
        return ''

    ext = os.path.splitext(filepath)[1].lower()
    if ext not in EXTENSIONES_SOPORTADAS:
        logger.warning('extract_text: extensión no soportada: %s', ext)
        return ''

    # PDF: PyMuPDF (fitz) → pdfplumber fallback
    if ext == '.pdf':
        text = _extract_pdf_pymupdf(filepath)
        if len(text.strip()) >= _MIN_CHARS_OK:
            return text
        # Fallback
        text = _extract_pdf_pdfplumber(filepath)
        return text

    # DOCX/DOC
    if ext in ('.docx', '.doc'):
        return _extract_docx(filepath)

    # TXT/RTF
    if ext in ('.txt', '.rtf'):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            logger.warning('extract_text TXT/RTF: %s', e)
            return ''

    return ''


def _extract_pdf_pymupdf(filepath: str) -> str:
    """Extrae texto con PyMuPDF (fitz). Más rápido para PDFs nativos."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.debug('PyMuPDF no instalado, saltando.')
        return ''
    try:
        parts = []
        with fitz.open(filepath) as doc:
            for page in doc:
                t = page.get_text('text') or ''
                if t.strip():
                    parts.append(t)
        text = '\n'.join(parts)
        if text.strip():
            logger.info('PyMuPDF: %d chars en %d páginas.', len(text), len(parts))
        return text
    except Exception as exc:
        logger.warning('PyMuPDF error: %s', exc)
        return ''


def _extract_pdf_pdfplumber(filepath: str) -> str:
    """Fallback para PDFs raros que PyMuPDF no procesa bien."""
    try:
        import pdfplumber
    except ImportError:
        return ''
    try:
        parts = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ''
                if t.strip():
                    parts.append(t)
        text = '\n'.join(parts)
        if text.strip():
            logger.info('pdfplumber: %d chars.', len(text))
        return text
    except Exception as exc:
        logger.warning('pdfplumber error: %s', exc)
        return ''


def _extract_docx(filepath: str) -> str:
    """Extrae texto de un DOCX."""
    try:
        from docx import Document
    except ImportError:
        logger.debug('python-docx no instalado, saltando.')
        return ''
    try:
        doc = Document(filepath)
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        # Tablas también pueden contener info importante
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        parts.append(cell.text)
        text = '\n'.join(parts)
        if text.strip():
            logger.info('python-docx: %d chars.', len(text))
        return text
    except Exception as exc:
        logger.warning('python-docx error: %s', exc)
        return ''


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────

def _strip_tildes(s: str) -> str:
    """Quita tildes y diacríticos para matching robusto."""
    import unicodedata
    return ''.join(
        c for c in unicodedata.normalize('NFKD', s)
        if not unicodedata.combining(c)
    )


# ──────────────────────────────────────────────────────────────────
# Extracción de entidades (regex)
# ──────────────────────────────────────────────────────────────────

# Email (RFC 5322 simplificado)
RE_EMAIL = re.compile(
    r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}',
)

# Teléfono peruano (móvil 9XX-XXX-XXX o fijo (01)XXXXXXX)
RE_TELEFONO_PE = re.compile(
    r'(?:\+?51[\s-]?)?(?:\(0?1\)[\s-]?\d{7}|9\d{2}[\s-]?\d{3}[\s-]?\d{3})',
)

# DNI peruano (8 dígitos)
RE_DNI_PE = re.compile(r'\b\d{8}\b')

# Fechas (varios formatos)
RE_FECHA = re.compile(
    r'\b(?:0?[1-9]|[12]\d|3[01])[/\-\.]'    # día
    r'(?:0?[1-9]|1[0-2])[/\-\.]'             # mes
    r'(?:19|20)\d{2}\b'                       # año
    r'|\b(?:Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Oct|Nov|Dic)[a-z]*\.?\s+(?:19|20)\d{2}\b'
    r'|\b(?:19|20)\d{2}\b',                   # año solo
    re.IGNORECASE,
)

# Headers de secciones (basado en NexoTalent cv_structure.py)
RE_HEADER_EXPERIENCIA = re.compile(
    r'(?im)^(?:experiencia\s+(?:laboral|profesional|de\s+trabajo)|'
    r'historial\s+(?:laboral|profesional)|work\s+experience|'
    r'antecedentes\s+laborales)\b'
)
RE_HEADER_EDUCACION = re.compile(
    r'(?im)^(?:formaci[oó]n\s+(?:acad[eé]mica|profesional)|'
    r'educaci[oó]n|estudios|education)\b'
)
RE_HEADER_SKILLS = re.compile(
    r'(?im)^(?:habilidades|competencias|skills|herramientas|conocimientos)\b'
)
RE_HEADER_IDIOMAS = re.compile(
    r'(?im)^(?:idiomas|languages)\b'
)


def parse_cv(text: str) -> dict:
    """Parsea un texto de CV y devuelve dict con entidades extraídas.

    Estructura del dict retornado:
        {
            'email':              'maria@ejemplo.com',  # primer match
            'telefono':           '987654321',
            'dni':                '71234567',
            'nombre_completo':    'MARIA QUISPE LOPEZ',  # mejor guess
            'anios_experiencia':  3,                     # calculado de fechas
            'fecha_min':          1995,                  # año más antiguo
            'fecha_max':          2025,
            'skills':             ['cocina_caliente', 'haccp', ...],
            'tiene_experiencia':  True,
            'tiene_educacion':    True,
            'longitud_texto':     12345,
            'idiomas':            ['ingles avanzado'],
        }
    """
    if not text:
        return _empty_parse_result()

    result = _empty_parse_result()
    result['longitud_texto'] = len(text)

    # ── Contacto ──
    emails = RE_EMAIL.findall(text)
    if emails:
        result['email'] = emails[0].lower()

    tels = RE_TELEFONO_PE.findall(text)
    if tels:
        # Normalizar — solo dígitos
        tel = re.sub(r'\D', '', tels[0])
        result['telefono'] = tel[-9:] if len(tel) >= 9 else tel

    # DNI (8 dígitos exactos, excluyendo fechas posibles)
    dnis = RE_DNI_PE.findall(text)
    for d in dnis:
        # Filtrar años (19XX o 20XX que aparecen como 8 dígitos seguidos)
        if not d.startswith(('19', '20')) or len(d) != 8 or int(d[:4]) > 2050:
            result['dni'] = d
            break

    # ── Nombre completo (heurística: primeras 2-3 líneas no vacías) ──
    lineas = [l.strip() for l in text.split('\n') if l.strip()]
    for linea in lineas[:5]:
        # Línea con 2-4 palabras, en mayúsculas (típico nombre)
        palabras = linea.split()
        if (2 <= len(palabras) <= 4
                and all(p[0].isupper() for p in palabras if p)
                and not RE_EMAIL.search(linea)
                and not RE_TELEFONO_PE.search(linea)
                and len(linea) < 80):
            result['nombre_completo'] = linea
            break

    # ── Fechas y experiencia ──
    años_encontrados = []
    for m in RE_FECHA.finditer(text):
        s = m.group()
        # Extraer año del match
        año_match = re.search(r'(?:19|20)\d{2}', s)
        if año_match:
            año = int(año_match.group())
            if 1950 <= año <= date.today().year + 1:
                años_encontrados.append(año)

    if años_encontrados:
        result['fecha_min'] = min(años_encontrados)
        result['fecha_max'] = max(años_encontrados)
        # Experiencia = max - min, capada a 50
        result['anios_experiencia'] = min(
            max(0, result['fecha_max'] - result['fecha_min']),
            50,
        )

    # ── Secciones ──
    result['tiene_experiencia'] = bool(RE_HEADER_EXPERIENCIA.search(text))
    result['tiene_educacion'] = bool(RE_HEADER_EDUCACION.search(text))

    # ── Skills (búsqueda case-insensitive + normalización tildes) ──
    text_norm = _strip_tildes(text.lower())
    skills_encontrados = []
    for skill in SKILLS_CATALOG:
        if _strip_tildes(skill) in text_norm:
            skills_encontrados.append(skill)
    result['skills'] = sorted(skills_encontrados)

    # ── Idiomas (separar de skills) ──
    idiomas = [s for s in result['skills']
               if any(idioma in s for idioma in (
                   'ingles', 'portugues', 'frances', 'italiano',
                   'aleman', 'mandarin', 'japones', 'quechua'
               ))]
    result['idiomas'] = idiomas

    return result


def _empty_parse_result() -> dict:
    return {
        'email':             '',
        'telefono':          '',
        'dni':               '',
        'nombre_completo':   '',
        'anios_experiencia': 0,
        'fecha_min':         None,
        'fecha_max':         None,
        'skills':            [],
        'idiomas':           [],
        'tiene_experiencia': False,
        'tiene_educacion':   False,
        'longitud_texto':    0,
    }


def parse_cv_from_file(filepath: str) -> dict:
    """Extrae texto y parsea entidades en un solo paso."""
    text = extract_text_from_file(filepath)
    result = parse_cv(text)
    result['texto_extraido'] = text
    # Extracción estructurada de experiencias y educación
    result['experiencias'] = extraer_experiencias(text)
    result['educacion_items'] = extraer_educacion(text)
    return result


# ──────────────────────────────────────────────────────────────────
# Extracción estructurada (adaptado de NexoTalent cv_structure.py)
# ──────────────────────────────────────────────────────────────────

# Patrones de fecha extendidos para experiencias
RE_BLOQUE_FECHA = re.compile(
    r'(?P<inicio>'
        # Mes año ó solo año
        r'(?:Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Set|Oct|Nov|Dic)[a-z]*\.?\s+\d{4}'
        r'|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}'
        r'|\d{4}'
    r')'
    r'\s*[-–—a]+\s*'      # separador (–, -, a)
    r'(?P<fin>'
        r'(?:Ene|Feb|Mar|Abr|May|Jun|Jul|Ago|Sep|Set|Oct|Nov|Dic)[a-z]*\.?\s+\d{4}'
        r'|\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{4}'
        r'|\d{4}'
        r'|Actualidad|Presente|Hoy|Actual'
    r')',
    re.IGNORECASE,
)


def _seccion_texto(text: str, header_re, max_chars: int = 4000) -> str:
    """Devuelve el texto que sigue a un header dado, hasta el siguiente
    header de sección o max_chars."""
    m = header_re.search(text)
    if not m:
        return ''
    start = m.end()
    # Buscar el siguiente header (cualquiera)
    next_headers = [
        RE_HEADER_EXPERIENCIA, RE_HEADER_EDUCACION,
        RE_HEADER_SKILLS, RE_HEADER_IDIOMAS,
    ]
    next_pos = start + max_chars
    for nh in next_headers:
        m2 = nh.search(text, pos=start + 5)
        if m2 and m2.start() < next_pos:
            next_pos = m2.start()
    return text[start:next_pos]


def extraer_experiencias(text: str) -> list:
    """Detecta bloques de experiencia laboral con fechas.

    Devuelve lista de dicts:
        {
            'fecha_inicio': 'Mar 2022',
            'fecha_fin':    'Actualidad',
            'lineas_siguientes': ['Restaurante Insignia', 'Mesera Senior'],
            'año_inicio': 2022,
            'año_fin':    2026,
        }
    """
    seccion = _seccion_texto(text, RE_HEADER_EXPERIENCIA, max_chars=4000)
    if not seccion:
        return []

    experiencias = []
    matches = list(RE_BLOQUE_FECHA.finditer(seccion))

    for i, m in enumerate(matches):
        fecha_inicio = m.group('inicio').strip()
        fecha_fin = m.group('fin').strip()

        # Texto entre este match y el siguiente (max 300 chars)
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else min(m.end() + 400, len(seccion))
        contexto = seccion[m.end():end_pos].strip()
        # Tomar primeras 2-3 líneas no vacías
        lineas = [l.strip() for l in contexto.split('\n') if l.strip()][:3]

        # Año inicio / fin numéricos
        año_inicio = _año_de_str(fecha_inicio)
        año_fin = _año_de_str(fecha_fin)
        if not año_fin and fecha_fin.lower() in ('actualidad', 'presente', 'hoy', 'actual'):
            from datetime import date as _date
            año_fin = _date.today().year

        experiencias.append({
            'fecha_inicio': fecha_inicio,
            'fecha_fin':    fecha_fin,
            'año_inicio':   año_inicio,
            'año_fin':      año_fin,
            'lineas':       lineas,
        })

    return experiencias[:10]  # cap a 10


def extraer_educacion(text: str) -> list:
    """Detecta bloques de educación con años + institución/título."""
    seccion = _seccion_texto(text, RE_HEADER_EDUCACION, max_chars=2500)
    if not seccion:
        return []

    items = []
    # Para educación, usar años solos también es válido
    año_re = re.compile(r'\b(19|20)\d{2}\b')
    años_encontrados = [(m.start(), m.group()) for m in año_re.finditer(seccion)]

    if not años_encontrados:
        return []

    # Tomar el primer año como referencia y el contexto siguiente
    for pos, año in años_encontrados[:5]:
        # Texto en línea + siguiente línea
        line_start = seccion.rfind('\n', 0, pos) + 1
        line_end = seccion.find('\n\n', pos)
        if line_end == -1:
            line_end = pos + 200
        contexto = seccion[line_start:line_end].strip()
        lineas = [l.strip() for l in contexto.split('\n') if l.strip()][:2]
        items.append({
            'año':    int(año),
            'lineas': lineas,
        })

    return items[:5]


def _año_de_str(s: str) -> int | None:
    m = re.search(r'\b(19|20)\d{2}\b', s)
    if m:
        return int(m.group())
    return None
