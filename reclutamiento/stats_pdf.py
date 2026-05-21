"""
PDF del Dashboard Stats Reclutadores — reporte ejecutivo mensual.

Genera un reporte profesional para imprimir o enviar al director/CEO con:
- KPIs globales del periodo
- Ranking de reclutadores con medallas
- Fuentes de mayor conversión
- Conclusiones / recomendaciones automáticas
"""
from datetime import timedelta
from io import BytesIO

from django.http import HttpResponse
from django.utils import timezone
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


# Paleta Harmoni
TEAL_DARK = colors.HexColor('#0d2b27')
TEAL      = colors.HexColor('#0f766e')
TEAL_LITE = colors.HexColor('#5eead4')
AMBER     = colors.HexColor('#f59e0b')
GREEN     = colors.HexColor('#10b981')
RED       = colors.HexColor('#dc2626')
GRAY      = colors.HexColor('#475569')
GRAY_BG   = colors.HexColor('#f8fafc')
BORDER    = colors.HexColor('#e2e8f0')


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'T', parent=base['Heading1'],
            fontName='Helvetica-Bold', fontSize=20, textColor=TEAL_DARK,
            alignment=TA_LEFT, leading=24, spaceAfter=4,
        ),
        'subtitle': ParagraphStyle(
            'S', parent=base['Normal'], fontName='Helvetica', fontSize=11,
            textColor=GRAY, alignment=TA_LEFT, spaceAfter=10,
        ),
        'section': ParagraphStyle(
            'ST', parent=base['Heading2'], fontName='Helvetica-Bold',
            fontSize=12, textColor=TEAL, leading=15, spaceAfter=6,
            spaceBefore=14, alignment=TA_LEFT,
        ),
        'body': ParagraphStyle(
            'B', parent=base['Normal'], fontName='Helvetica', fontSize=9,
            textColor=colors.HexColor('#1f2937'), leading=13,
        ),
        'footer': ParagraphStyle(
            'F', parent=base['Normal'], fontName='Helvetica', fontSize=8,
            textColor=GRAY, alignment=TA_CENTER,
        ),
        'kpi_big': ParagraphStyle(
            'KB', parent=base['Normal'], fontName='Helvetica-Bold', fontSize=22,
            textColor=TEAL_DARK, alignment=TA_CENTER, leading=24,
        ),
        'kpi_label': ParagraphStyle(
            'KL', parent=base['Normal'], fontName='Helvetica', fontSize=8,
            textColor=GRAY, alignment=TA_CENTER, leading=10,
        ),
    }


def _kpi_card(value, label, color=TEAL_DARK):
    """Construye una mini-tabla que actúa como KPI card."""
    st = _styles()
    inner_label = ParagraphStyle(
        'kl', parent=st['kpi_label'], textColor=GRAY,
    )
    inner_value = ParagraphStyle(
        'kv', parent=st['kpi_big'], textColor=color, fontSize=18,
    )
    data = [
        [Paragraph(str(value), inner_value)],
        [Paragraph(label, inner_label)],
    ]
    t = Table(data, colWidths=[36*mm], rowHeights=[16*mm, 8*mm])
    t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('BACKGROUND', (0, 0), (0, 0), GRAY_BG),
        ('BACKGROUND', (0, 1), (0, 1), colors.white),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return t


def build_stats_pdf(stats_data, dias):
    """
    Genera bytes PDF del dashboard de stats reclutadores.

    stats_data dict debe contener:
        - stats_por_reclutador: list of dicts
        - total_postulaciones, total_contratados, total_descartados, total_entrevistas
        - tasa_conversion, tiempo_promedio_dias, total_reclutadores
        - fuentes_exito
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15*mm, bottomMargin=15*mm,
        leftMargin=15*mm, rightMargin=15*mm,
        title=f'Stats Reclutadores - {dias} días',
        author='Harmoni ERP',
    )

    st = _styles()
    story = []

    # ── HEADER ──
    story.append(Paragraph('Reporte de Productividad — Reclutamiento', st['title']))
    fecha_emision = timezone.now().strftime('%d de %B de %Y')
    desde = (timezone.now() - timedelta(days=dias)).strftime('%d/%m/%Y')
    hasta = timezone.now().strftime('%d/%m/%Y')
    story.append(Paragraph(
        f"Periodo analizado: <b>{desde} — {hasta}</b> ({dias} días) · Emitido: {fecha_emision}",
        st['subtitle'],
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL,
                            spaceBefore=0, spaceAfter=10))

    # ── KPIs GLOBALES (3 columnas x 2 filas) ──
    story.append(Paragraph('KPIs Globales del Periodo', st['section']))
    kpi_row1 = Table([[
        _kpi_card(stats_data['total_postulaciones'], 'Postulaciones', TEAL),
        _kpi_card(stats_data['total_contratados'],   'Contratados', GREEN),
        _kpi_card(f"{stats_data['tasa_conversion']}%", 'Tasa Conversión', AMBER),
    ]], colWidths=[60*mm, 60*mm, 60*mm])
    kpi_row1.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(kpi_row1)
    story.append(Spacer(1, 4))

    kpi_row2 = Table([[
        _kpi_card(stats_data['total_entrevistas'],  'Entrevistas', TEAL_DARK),
        _kpi_card(stats_data['tiempo_promedio_dias'], 'Días Avg p/Contratar', AMBER),
        _kpi_card(stats_data['total_descartados'],  'Descartados', RED),
    ]], colWidths=[60*mm, 60*mm, 60*mm])
    kpi_row2.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(kpi_row2)
    story.append(Spacer(1, 8))

    # ── RANKING DE RECLUTADORES ──
    story.append(Paragraph('Ranking de Reclutadores', st['section']))

    if stats_data['stats_por_reclutador']:
        rows = [['#', 'Reclutador', 'Candidatos', 'Notas', 'Entrev.', 'Aprob.', 'Contrat.', 'Avg Cal.', 'Tasa %']]
        for i, r in enumerate(stats_data['stats_por_reclutador'][:15], start=1):
            medal = '🥇' if i == 1 else '🥈' if i == 2 else '🥉' if i == 3 else str(i)
            avg_cal = f"{r['avg_calificacion']}/10" if r.get('avg_calificacion') else '—'
            rows.append([
                medal,
                r['nombre'][:30],
                str(r['candidatos_tocados']),
                str(r['notas_count']),
                str(r['entrev_count']),
                str(r['entrev_aprobadas']),
                str(r['contrataciones']),
                avg_cal,
                f"{r['tasa_aprobacion']}%",
            ])

        ranking_t = Table(rows, colWidths=[10*mm, 50*mm, 22*mm, 16*mm, 16*mm, 16*mm, 18*mm, 18*mm, 16*mm])
        ranking_t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), TEAL_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('ALIGN', (1, 1), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, GRAY_BG]),
            ('PADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(ranking_t)
    else:
        story.append(Paragraph('Sin actividad de reclutadores en el periodo.', st['body']))

    # ── FUENTES EXITOSAS ──
    story.append(Spacer(1, 8))
    story.append(Paragraph('Fuentes con Mejor Conversión', st['section']))
    if stats_data.get('fuentes_exito'):
        rows = [['Fuente', 'Contrataciones']]
        for f in stats_data['fuentes_exito']:
            rows.append([f['fuente'], f"{f['count']} contratado(s)"])
        fuentes_t = Table(rows, colWidths=[60*mm, 50*mm])
        fuentes_t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, 0), (-1, 0), GRAY_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), TEAL_DARK),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.3, BORDER),
            ('ALIGN', (1, 0), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(fuentes_t)
    else:
        story.append(Paragraph('No hay contrataciones en el periodo para analizar fuentes.', st['body']))

    # ── INSIGHTS / CONCLUSIONES ──
    story.append(Spacer(1, 10))
    story.append(Paragraph('Insights del Periodo', st['section']))
    insights = []
    if stats_data['tasa_conversion'] > 15:
        insights.append(f"• <b>Excelente tasa de conversión</b> ({stats_data['tasa_conversion']}%): el equipo está cerrando bien.")
    elif stats_data['tasa_conversion'] < 5:
        insights.append(f"• <b>Tasa de conversión baja</b> ({stats_data['tasa_conversion']}%): revisar criterios de filtrado o calidad de fuentes.")
    if stats_data['tiempo_promedio_dias'] > 45:
        insights.append(f"• <b>Tiempo de contratación largo</b> ({stats_data['tiempo_promedio_dias']} días promedio): acelerar etapas intermedias.")
    elif 0 < stats_data['tiempo_promedio_dias'] < 14:
        insights.append(f"• <b>Tiempo de contratación rápido</b> ({stats_data['tiempo_promedio_dias']} días promedio): proceso fluido.")
    if stats_data['stats_por_reclutador']:
        top = stats_data['stats_por_reclutador'][0]
        insights.append(f"• <b>Top reclutador</b>: {top['nombre']} con {top['candidatos_tocados']} candidatos tocados y {top['contrataciones']} contrataciones.")
    if stats_data['total_descartados'] > stats_data['total_contratados'] * 5:
        insights.append("• <b>Muchos descartes</b>: considerar mejorar criterios de pre-screening para reducir esfuerzo.")
    if not insights:
        insights.append("• Periodo con actividad moderada. Recopilar más datos para insights significativos.")

    for ins in insights:
        story.append(Paragraph(ins, st['body']))
        story.append(Spacer(1, 2))

    # ── FOOTER ──
    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER,
                            spaceBefore=0, spaceAfter=4))
    story.append(Paragraph(
        'Harmoni ERP · Reporte ejecutivo generado automáticamente · Confidencial',
        st['footer'],
    ))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()
    return pdf


def stats_pdf_response(stats_data, dias):
    """Devuelve HttpResponse con el PDF inline."""
    pdf = build_stats_pdf(stats_data, dias)
    response = HttpResponse(pdf, content_type='application/pdf')
    fname = f'stats_reclutadores_{dias}d_{timezone.now().strftime("%Y%m%d")}.pdf'
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response
