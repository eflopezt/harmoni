"""
PDF unificado del candidato — para imprimir antes de entrevista.

Incluye datos personales, contacto, score breakdown, skills detectados,
experiencia, historial de etapas, notas y tags.
"""
from io import BytesIO

from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Paleta Harmoni ──────────────────────────────────────────
TEAL_DARK = colors.HexColor('#0d2b27')
TEAL      = colors.HexColor('#0f766e')
AMBER     = colors.HexColor('#92400e')
GREEN     = colors.HexColor('#065f46')
RED       = colors.HexColor('#991b1b')
GRAY      = colors.HexColor('#475569')
GRAY_BG   = colors.HexColor('#f8fafc')
BORDER    = colors.HexColor('#e2e8f0')


def _styles():
    """Devuelve estilos preconfigurados."""
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'T', parent=base['Heading1'],
            fontName='Helvetica-Bold', fontSize=20, textColor=TEAL_DARK,
            alignment=TA_LEFT, leading=24, spaceAfter=2,
        ),
        'subtitle': ParagraphStyle(
            'S', parent=base['Normal'], fontName='Helvetica', fontSize=11,
            textColor=GRAY, alignment=TA_LEFT, spaceAfter=10,
        ),
        'section': ParagraphStyle(
            'ST', parent=base['Heading2'], fontName='Helvetica-Bold',
            fontSize=11, textColor=TEAL, leading=14, spaceAfter=6,
            spaceBefore=10, alignment=TA_LEFT,
        ),
        'body': ParagraphStyle(
            'B', parent=base['Normal'], fontName='Helvetica', fontSize=10,
            textColor=colors.HexColor('#1f2937'), leading=14,
        ),
        'kv_label': ParagraphStyle(
            'KVL', parent=base['Normal'], fontName='Helvetica-Bold', fontSize=9,
            textColor=GRAY, alignment=TA_LEFT,
        ),
        'kv_value': ParagraphStyle(
            'KVV', parent=base['Normal'], fontName='Helvetica', fontSize=10,
            textColor=colors.HexColor('#1f2937'), alignment=TA_LEFT,
        ),
        'footer': ParagraphStyle(
            'F', parent=base['Normal'], fontName='Helvetica', fontSize=8,
            textColor=GRAY, alignment=TA_CENTER,
        ),
        'score_big': ParagraphStyle(
            'SB', parent=base['Normal'], fontName='Helvetica-Bold', fontSize=24,
            textColor=TEAL_DARK, alignment=TA_CENTER, leading=28,
        ),
    }


def _score_color(score):
    if score >= 80:
        return colors.HexColor('#10b981')
    if score >= 60:
        return colors.HexColor('#f59e0b')
    return colors.HexColor('#94a3b8')


def _build_desglose_from_postulacion(postulacion):
    """Reconstruye el desglose del score usando los campos almacenados.

    Llama a _desglose_score_matching pasando un dict 'parsed' construido
    desde los datos guardados en la Postulacion.
    """
    try:
        from reclutamiento.views import _desglose_score_matching
        parsed = {
            'email':              postulacion.email or '',
            'telefono':           postulacion.telefono or '',
            'anios_experiencia':  getattr(postulacion, 'experiencia_anos', 0) or 0,
            'skills':             list(postulacion.cv_skills or []),
            'idiomas':            list(postulacion.cv_idiomas or []),
            'tiene_experiencia':  bool(postulacion.cv_texto_extraido),
            'tiene_educacion':    bool(
                postulacion.cv_texto_extraido and
                any(w in postulacion.cv_texto_extraido.lower()
                    for w in ['educacion', 'educación', 'estudios', 'universidad'])
            ),
        }
        return _desglose_score_matching(parsed, postulacion.vacante)
    except Exception:
        return None


def _section_title(text, st, color=None):
    style = ParagraphStyle(
        'sect', parent=st['section'],
        textColor=color or TEAL,
    )
    return Paragraph(text.upper(), style)


def build_candidato_pdf(postulacion):
    """Genera bytes PDF para una Postulacion."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title=f'Candidato {postulacion.nombre_completo}',
        author='Harmoni ERP',
    )

    st = _styles()
    story = []

    # ── HEADER: Nombre + Score badge ──
    score = postulacion.cv_score or 0
    header_data = [[
        [
            Paragraph(postulacion.nombre_completo, st['title']),
            Paragraph(
                f"<b>Vacante:</b> {postulacion.vacante.titulo}  ·  "
                f"<b>Etapa:</b> {postulacion.etapa.nombre if postulacion.etapa else '—'}  ·  "
                f"<b>Estado:</b> {postulacion.get_estado_display()}",
                st['subtitle'],
            ),
        ],
        [
            Paragraph(
                f'<font color="{_score_color(score).hexval()}"><b>{score}</b></font><font size="9" color="#94a3b8">/100</font>',
                st['score_big'],
            ),
            Paragraph('SCORE CV', ParagraphStyle(
                'lbl', parent=st['footer'], fontSize=8, alignment=TA_CENTER,
                textColor=GRAY,
            )),
        ],
    ]]
    header_t = Table(header_data, colWidths=[140 * mm, 35 * mm])
    header_t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BACKGROUND', (1, 0), (1, 0), GRAY_BG),
        ('BOX', (1, 0), (1, 0), 0.5, BORDER),
        ('LEFTPADDING', (1, 0), (1, 0), 10),
        ('RIGHTPADDING', (1, 0), (1, 0), 10),
        ('TOPPADDING', (1, 0), (1, 0), 8),
        ('BOTTOMPADDING', (1, 0), (1, 0), 8),
    ]))
    story.append(header_t)
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL,
                            spaceBefore=0, spaceAfter=10))

    # ── DATOS DE CONTACTO ──
    story.append(_section_title('Datos de Contacto', st))
    contacto_data = [
        ['Email:',     postulacion.email or '—',         'Teléfono:', postulacion.telefono or '—'],
        ['DNI:',       getattr(postulacion, 'dni', '') or '—',
                                                         'Postulación:', postulacion.fecha_postulacion.strftime('%d/%m/%Y %H:%M')],
        ['Fuente:',    postulacion.get_fuente_display(), 'Salario pretendido:',
                                                         f"S/ {postulacion.salario_pretendido}" if postulacion.salario_pretendido else '—'],
        ['Experiencia:', f"{postulacion.experiencia_anos or 0} año(s)" if hasattr(postulacion, 'experiencia_anos') else '—',
                                                         'Días en proceso:', f"{postulacion.dias_en_proceso} día(s)"],
    ]
    contacto_t = Table(contacto_data, colWidths=[30 * mm, 60 * mm, 35 * mm, 50 * mm])
    contacto_t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY),
        ('TEXTCOLOR', (2, 0), (2, -1), GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(contacto_t)
    story.append(Spacer(1, 6))

    # ── TAGS ──
    if postulacion.tags:
        story.append(_section_title('Etiquetas', st, color=AMBER))
        tags_pretty = []
        d = dict(postulacion.TAG_CHOICES)
        for code in postulacion.tags:
            tags_pretty.append(d.get(code, code))
        story.append(Paragraph(' · '.join(tags_pretty), st['body']))
        story.append(Spacer(1, 6))

    # ── SKILLS detectados ──
    if postulacion.cv_skills:
        story.append(_section_title('Skills Detectados en CV', st))
        skills_pretty = ' · '.join(
            s.replace('_', ' ').title() for s in postulacion.cv_skills
        )
        story.append(Paragraph(skills_pretty, st['body']))
        story.append(Spacer(1, 6))

    # ── IDIOMAS ──
    if postulacion.cv_idiomas:
        story.append(_section_title('Idiomas', st))
        story.append(Paragraph(' · '.join(postulacion.cv_idiomas), st['body']))
        story.append(Spacer(1, 6))

    # ── SCORE DESGLOSE ──
    desglose = _build_desglose_from_postulacion(postulacion)
    if desglose and desglose.get('componentes'):
        story.append(_section_title('Score de Matching — Desglose', st))
        rows = [['Componente', 'Puntos', 'Detalle']]
        for c in desglose['componentes']:
            rows.append([
                c.get('concepto', '—'),
                f"{c.get('pts', 0)}",
                (c.get('detalle', '') or '')[:80],
            ])
        rows.append(['TOTAL', f"{desglose.get('total', 0)} / 100", ''])
        score_t = Table(rows, colWidths=[55 * mm, 30 * mm, 90 * mm])
        score_t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEAL_DARK),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 4),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0f2f1')),
        ]))
        story.append(score_t)
        story.append(Spacer(1, 6))

    # ── EXPERIENCIA EXTRAÍDA ──
    try:
        from reclutamiento.cv_parser import extraer_experiencias
        experiencias = (
            extraer_experiencias(postulacion.cv_texto_extraido)
            if postulacion.cv_texto_extraido else []
        )
    except Exception:
        experiencias = []
    if experiencias:
        story.append(_section_title('Experiencia Detectada', st))
        for exp in experiencias[:5]:
            exp_str = f"<b>{exp.get('periodo', '—')}</b> — {exp.get('texto', '')[:200]}"
            story.append(Paragraph(exp_str, st['body']))
            story.append(Spacer(1, 2))
        story.append(Spacer(1, 4))

    # ── NOTAS ──
    notas = postulacion.notas_detalle.all().order_by('-fecha')[:10] if hasattr(postulacion, 'notas_detalle') else []
    if notas:
        story.append(_section_title('Notas / Historial', st))
        for n in notas:
            autor = n.autor.username if n.autor else '—'
            fecha = n.fecha.strftime('%d/%m %H:%M')
            tipo = n.get_tipo_display() if hasattr(n, 'get_tipo_display') else ''
            story.append(Paragraph(
                f"<b>{fecha}</b> · <font color='#475569'>{autor}</font> · "
                f"<font color='#0f766e'>{tipo}</font><br/>{n.texto}",
                st['body'],
            ))
            story.append(Spacer(1, 4))

    # ── FOOTER ──
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER,
                            spaceBefore=0, spaceAfter=4))
    story.append(Paragraph(
        f"Harmoni ERP · Perfil generado para entrevista · {postulacion.fecha_postulacion.strftime('%d/%m/%Y')}",
        st['footer'],
    ))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    return pdf


def candidato_pdf_response(postulacion):
    """Devuelve HttpResponse con el PDF inline."""
    pdf = build_candidato_pdf(postulacion)
    response = HttpResponse(pdf, content_type='application/pdf')
    safe_name = ''.join(
        c if c.isalnum() else '_' for c in postulacion.nombre_completo
    )[:40]
    fname = f'candidato_{postulacion.pk}_{safe_name}.pdf'
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response
