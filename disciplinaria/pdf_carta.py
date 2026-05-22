"""
Generación de cartas disciplinarias en PDF.

- build_carta_amonestacion_pdf(medida) — para amonestaciones escritas / memorándums
- build_carta_suspension_pdf(medida)   — para suspensiones sin goce

Base legal:
- DS 003-97-TR (TUO DL 728): Art. 24-28 (faltas), Art. 31 (procedimiento).
- Ley 27942 (hostigamiento) cuando aplique.
- DS 005-2012-TR (SST) cuando aplique.

El PDF incluye espacio para descargo (5/6 días hábiles) y cargo de recepción.
"""
from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Optional

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Paleta Harmoni ──────────────────────────────────────────
TEAL_DARK = colors.HexColor('#0d2b27')
TEAL      = colors.HexColor('#0f766e')
GRAY      = colors.HexColor('#475569')
GRAY_BG   = colors.HexColor('#f8fafc')
BORDER    = colors.HexColor('#e2e8f0')
DARK_TEXT = colors.HexColor('#1f2937')
RED       = colors.HexColor('#991b1b')


_MESES_ES = [
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'setiembre', 'octubre', 'noviembre', 'diciembre',
]


def _fecha_larga(d: Optional[date]) -> str:
    if not d:
        return '—'
    return f'{d.day} de {_MESES_ES[d.month]} de {d.year}'


def _styles():
    base = getSampleStyleSheet()
    return {
        'header_empresa': ParagraphStyle(
            'HE', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=12, textColor=TEAL_DARK, leading=15, alignment=TA_LEFT,
        ),
        'header_meta': ParagraphStyle(
            'HM', parent=base['Normal'], fontName='Helvetica',
            fontSize=9, textColor=GRAY, leading=12, alignment=TA_LEFT,
        ),
        'lugar_fecha': ParagraphStyle(
            'LF', parent=base['Normal'], fontName='Helvetica',
            fontSize=10, textColor=DARK_TEXT, leading=14, alignment=TA_RIGHT,
        ),
        'titulo': ParagraphStyle(
            'T', parent=base['Heading1'], fontName='Helvetica-Bold',
            fontSize=14, textColor=TEAL_DARK, alignment=TA_CENTER,
            leading=18, spaceBefore=14, spaceAfter=14,
        ),
        'destinatario_lbl': ParagraphStyle(
            'DL', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=10, textColor=DARK_TEXT, leading=14, alignment=TA_LEFT,
        ),
        'destinatario': ParagraphStyle(
            'D', parent=base['Normal'], fontName='Helvetica',
            fontSize=10, textColor=DARK_TEXT, leading=14, alignment=TA_LEFT,
        ),
        'asunto': ParagraphStyle(
            'A', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=10.5, textColor=TEAL_DARK, leading=14, alignment=TA_LEFT,
            spaceBefore=6, spaceAfter=10,
        ),
        'cuerpo': ParagraphStyle(
            'C', parent=base['Normal'], fontName='Helvetica',
            fontSize=10.5, textColor=DARK_TEXT, leading=15, alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        'cuerpo_b': ParagraphStyle(
            'CB', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=10.5, textColor=DARK_TEXT, leading=15, alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        'nota_legal': ParagraphStyle(
            'NL', parent=base['Normal'], fontName='Helvetica-Oblique',
            fontSize=8.5, textColor=GRAY, leading=11, alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        'firma_lbl': ParagraphStyle(
            'FL', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=9.5, textColor=DARK_TEXT, leading=12, alignment=TA_CENTER,
        ),
        'firma_meta': ParagraphStyle(
            'FM', parent=base['Normal'], fontName='Helvetica',
            fontSize=8.5, textColor=GRAY, leading=11, alignment=TA_CENTER,
        ),
        'cargo_label': ParagraphStyle(
            'CL', parent=base['Normal'], fontName='Helvetica-Bold',
            fontSize=9, textColor=RED, leading=11, alignment=TA_LEFT,
        ),
    }


# ──────────────────────────────────────────────────────────────
# HELPERS PARA EMPRESA / DESTINATARIO
# ──────────────────────────────────────────────────────────────

def _resolver_empresa(medida):
    """Intenta resolver la empresa empleadora desde la medida."""
    empresa = None
    try:
        empresa = getattr(medida.personal, 'empresa', None)
    except Exception:
        empresa = None
    if not empresa:
        try:
            from empresas.models import Empresa
            empresa = Empresa.objects.filter(activa=True, es_principal=True).first() \
                or Empresa.objects.filter(activa=True).first() \
                or Empresa.objects.first()
        except Exception:
            empresa = None
    return empresa


def _area_personal(personal) -> str:
    """Devuelve el área del trabajador como string, vacío si no tiene."""
    try:
        sub = getattr(personal, 'subarea', None)
        if sub:
            area = getattr(sub, 'area', None)
            if area:
                return f'{area.nombre} / {sub.nombre}'
            return sub.nombre or ''
    except Exception:
        pass
    return ''


def _bloque_encabezado_empresa(empresa, styles):
    """Encabezado superior con razón social + RUC."""
    if not empresa:
        return [
            Paragraph('<b>EMPRESA EMPLEADORA</b>', styles['header_empresa']),
            Paragraph('RUC: —', styles['header_meta']),
        ]
    razon = getattr(empresa, 'razon_social', '') or 'EMPRESA'
    ruc = getattr(empresa, 'ruc', '') or '—'
    direccion = getattr(empresa, 'direccion', '') or ''
    lineas = [Paragraph(f'<b>{razon}</b>', styles['header_empresa']),
              Paragraph(f'RUC: {ruc}', styles['header_meta'])]
    if direccion:
        lineas.append(Paragraph(direccion, styles['header_meta']))
    return lineas


def _firmas_table(empresa, personal, styles, dias_descargo=6):
    """Tabla con espacios de firma del empleador y trabajador (cargo)."""
    nombre_emp = getattr(empresa, 'razon_social', '') or 'LA EMPRESA' if empresa else 'LA EMPRESA'

    firma_emp = [
        Paragraph('______________________________', styles['firma_lbl']),
        Paragraph('Por el Empleador', styles['firma_lbl']),
        Paragraph(nombre_emp, styles['firma_meta']),
        Paragraph('Gerencia / Recursos Humanos', styles['firma_meta']),
    ]
    firma_trab = [
        Paragraph('______________________________', styles['firma_lbl']),
        Paragraph(personal.apellidos_nombres, styles['firma_lbl']),
        Paragraph(f'DNI: {personal.nro_doc}', styles['firma_meta']),
        Paragraph('Recibí copia y tomé conocimiento', styles['firma_meta']),
    ]
    data = [[firma_emp, firma_trab]]
    tbl = Table(data, colWidths=[85*mm, 85*mm])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tbl


# ──────────────────────────────────────────────────────────────
# BUILDERS
# ──────────────────────────────────────────────────────────────

def _build_doc(buffer):
    return SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=22*mm, rightMargin=22*mm,
        topMargin=18*mm, bottomMargin=18*mm,
        title='Carta Disciplinaria',
    )


def _bloque_datos_trabajador(personal, styles):
    """Tabla con datos del trabajador."""
    cargo = getattr(personal, 'cargo', '') or '—'
    area = _area_personal(personal) or '—'
    data = [
        [Paragraph('<b>Trabajador:</b>', styles['destinatario']),
         Paragraph(personal.apellidos_nombres, styles['destinatario'])],
        [Paragraph('<b>DNI / Doc.:</b>', styles['destinatario']),
         Paragraph(personal.nro_doc, styles['destinatario'])],
        [Paragraph('<b>Cargo:</b>', styles['destinatario']),
         Paragraph(cargo, styles['destinatario'])],
        [Paragraph('<b>Área:</b>', styles['destinatario']),
         Paragraph(area, styles['destinatario'])],
    ]
    tbl = Table(data, colWidths=[35*mm, 130*mm])
    tbl.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, -1), (-1, -1), 0.4, BORDER),
        ('LINEABOVE', (0, 0), (-1, 0), 0.4, BORDER),
    ]))
    return tbl


def _segunda_pagina_cargo(empresa, personal, medida, styles, titulo_carta):
    """Genera el 'cargo' — copia para devolver firmada."""
    flow = []
    flow.append(Paragraph('CARGO DE RECEPCIÓN', styles['cargo_label']))
    flow.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    flow.append(Spacer(1, 4*mm))
    flow.append(Paragraph(
        f'Declaro haber recibido el documento <b>"{titulo_carta}"</b> '
        f'de fecha {_fecha_larga(date.today())}, correspondiente a {personal.apellidos_nombres} '
        f'(DNI {personal.nro_doc}). Tomo conocimiento del contenido y de los plazos para '
        f'presentar mi descargo conforme a ley.',
        styles['cuerpo'],
    ))
    flow.append(Spacer(1, 18*mm))
    flow.append(_firmas_table(empresa, personal, styles))
    return flow


def _carta_base_flow(medida, styles, *, titulo_carta: str, tipo: str):
    """
    Construye el flow común a amonestación y suspensión.
    tipo: 'AMONESTACION' o 'SUSPENSION'.
    """
    empresa = _resolver_empresa(medida)
    personal = medida.personal
    flow = []

    # Encabezado empresa
    for f in _bloque_encabezado_empresa(empresa, styles):
        flow.append(f)
    flow.append(Spacer(1, 6*mm))

    # Lugar y fecha
    lugar = (getattr(empresa, 'distrito', '') or 'Lima').strip() or 'Lima'
    flow.append(Paragraph(
        f'{lugar}, {_fecha_larga(date.today())}',
        styles['lugar_fecha'],
    ))
    flow.append(Spacer(1, 6*mm))

    # Título centrado
    flow.append(Paragraph(titulo_carta, styles['titulo']))

    # Datos del trabajador
    flow.append(_bloque_datos_trabajador(personal, styles))
    flow.append(Spacer(1, 4*mm))

    # Asunto
    tipo_falta_nombre = getattr(medida.tipo_falta, 'nombre', 'Falta laboral')
    flow.append(Paragraph(
        f'<b>ASUNTO:</b> {titulo_carta.title()} por {tipo_falta_nombre}.',
        styles['asunto'],
    ))

    # Cuerpo principal
    saludo = f'Estimado(a) Sr.(a) {personal.apellidos_nombres}:'
    flow.append(Paragraph(saludo, styles['cuerpo']))

    intro = (
        'Por medio del presente le comunicamos formalmente que, luego de '
        'haber tomado conocimiento de los hechos que a continuación se '
        'describen, la empresa ha decidido aplicar la presente medida '
        'disciplinaria de conformidad con el reglamento interno de trabajo '
        'y la legislación laboral vigente.'
    )
    flow.append(Paragraph(intro, styles['cuerpo']))

    # Hechos
    fecha_hechos_str = _fecha_larga(medida.fecha_hechos)
    descripcion = (medida.descripcion_hechos or '').strip() or 'No se ha consignado descripción.'
    # escapar HTML básico
    descripcion_html = (
        descripcion
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('\n', '<br/>')
    )
    flow.append(Paragraph(
        f'<b>Hechos imputados (ocurridos el {fecha_hechos_str}):</b><br/>{descripcion_html}',
        styles['cuerpo'],
    ))

    # Base legal
    base_legal = (getattr(medida.tipo_falta, 'base_legal', '') or '').strip()
    if base_legal:
        flow.append(Paragraph(
            f'<b>Base legal aplicable:</b> {base_legal} (TUO DS 003-97-TR — '
            f'Ley de Productividad y Competitividad Laboral).',
            styles['cuerpo'],
        ))
    else:
        flow.append(Paragraph(
            '<b>Base legal:</b> TUO DS 003-97-TR (Ley de Productividad y '
            'Competitividad Laboral) y Reglamento Interno de Trabajo.',
            styles['cuerpo'],
        ))

    # Sanción
    if tipo == 'SUSPENSION':
        dias = medida.dias_suspension or 1
        flow.append(Paragraph(
            f'<b>SANCIÓN APLICADA:</b> Se le impone <b>SUSPENSIÓN SIN GOCE DE '
            f'REMUNERACIONES por {dias} día(s) hábil(es)</b>, de conformidad '
            f'con el Reglamento Interno y la legislación laboral.',
            styles['cuerpo_b'],
        ))
        if medida.fecha_cese:
            flow.append(Paragraph(
                f'La suspensión se hará efectiva a partir del '
                f'<b>{_fecha_larga(medida.fecha_cese)}</b>.',
                styles['cuerpo'],
            ))
    else:
        flow.append(Paragraph(
            '<b>SANCIÓN APLICADA:</b> AMONESTACIÓN ESCRITA. La presente '
            'amonestación quedará registrada en su file personal y se '
            'considerará como antecedente para futuras medidas disciplinarias '
            'en caso de reincidencia.',
            styles['cuerpo_b'],
        ))

    # Plazo descargo
    flow.append(Paragraph(
        'En aplicación del principio del debido proceso, usted cuenta con '
        '<b>cinco (5) días hábiles</b> contados desde la recepción de la '
        'presente para presentar el descargo respectivo, ofreciendo los medios '
        'probatorios que estime pertinentes. Para faltas que ameriten despido '
        'el plazo será de seis (6) días hábiles conforme al Art. 31 del DS 003-97-TR.',
        styles['cuerpo'],
    ))

    flow.append(Paragraph(
        'Se le exhorta a corregir su conducta a fin de evitar la aplicación '
        'de medidas más severas en el marco del principio de progresividad '
        'de la sanción disciplinaria.',
        styles['cuerpo'],
    ))

    flow.append(Spacer(1, 4*mm))
    flow.append(Paragraph('Atentamente,', styles['cuerpo']))
    flow.append(Spacer(1, 16*mm))

    # Firmas
    flow.append(_firmas_table(empresa, personal, styles))
    flow.append(Spacer(1, 6*mm))

    # Nota legal pie
    flow.append(HRFlowable(width="100%", thickness=0.3, color=BORDER))
    flow.append(Paragraph(
        'Documento generado por Harmoni ERP — Sistema de Gestión de Recursos Humanos. '
        'Base legal: TUO DS 003-97-TR (Ley de Productividad y Competitividad Laboral), '
        'Art. 24-28 y Art. 31. Original para el archivo del empleador, copia para el trabajador.',
        styles['nota_legal'],
    ))

    # Segunda página: cargo
    flow.append(PageBreak())
    for f in _segunda_pagina_cargo(empresa, personal, medida, styles, titulo_carta):
        flow.append(f)

    return flow


def build_carta_amonestacion_pdf(medida) -> bytes:
    """Genera el PDF de amonestación escrita / memorándum.

    Returns: bytes del PDF.
    """
    buffer = BytesIO()
    doc = _build_doc(buffer)
    styles = _styles()
    flow = _carta_base_flow(
        medida, styles,
        titulo_carta='MEMORÁNDUM DE AMONESTACIÓN ESCRITA',
        tipo='AMONESTACION',
    )
    doc.build(flow)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def build_carta_suspension_pdf(medida) -> bytes:
    """Genera el PDF de carta de suspensión sin goce."""
    buffer = BytesIO()
    doc = _build_doc(buffer)
    styles = _styles()
    flow = _carta_base_flow(
        medida, styles,
        titulo_carta='CARTA DE SUSPENSIÓN SIN GOCE DE REMUNERACIONES',
        tipo='SUSPENSION',
    )
    doc.build(flow)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes


def carta_pdf_response(medida) -> HttpResponse:
    """Helper para devolver HttpResponse con el PDF correcto según tipo_medida."""
    tipo = (medida.tipo_medida or '').upper()
    if tipo == 'SUSPENSION':
        pdf_bytes = build_carta_suspension_pdf(medida)
        nombre = f'carta_suspension_{medida.personal.nro_doc}_{medida.pk}.pdf'
    else:
        # Default: amonestación (cubre VERBAL, ESCRITA y como fallback)
        pdf_bytes = build_carta_amonestacion_pdf(medida)
        nombre = f'carta_amonestacion_{medida.personal.nro_doc}_{medida.pk}.pdf'
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nombre}"'
    return response
