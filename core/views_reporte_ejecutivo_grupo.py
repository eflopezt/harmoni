"""
Reporte Ejecutivo del Grupo — PDF descargable de 1 página.

URL: /reportes/grupo-ejecutivo/

Para que el dueño (Isabel) pueda imprimirlo o llevarlo a su reunión semanal.
Una página, KPIs visuales, sin nada superfluo.
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
    )
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False


TEAL      = colors.HexColor('#0f766e')
TEAL_DARK = colors.HexColor('#0d2b27')
TEAL_SOFT = colors.HexColor('#5eead4')
GREY      = colors.HexColor('#64748b')
GREY_SOFT = colors.HexColor('#e2e8f0')
INK       = colors.HexColor('#0d2b27')
ACCENT    = colors.HexColor('#f59e0b')
GREEN     = colors.HexColor('#16a34a')
RED       = colors.HexColor('#dc2626')


@login_required
def reporte_grupo_ejecutivo(request):
    """Genera PDF de 1 página con KPIs del grupo."""
    if not REPORTLAB_OK:
        return HttpResponse('reportlab no instalado.', status=500)

    from empresas.models import Empresa
    from personal.models import Personal, Contrato

    empresas = Empresa.objects.filter(activa=True).exclude(ruc='20612345678')

    # ── KPIs ──
    total_workers = Personal.objects.filter(estado='Activo', empresa__in=empresas).count()
    total_empresas = empresas.count()
    costo_estimado = sum(
        (p.sueldo_base or Decimal('0'))
        for p in Personal.objects.filter(estado='Activo', empresa__in=empresas).only('sueldo_base')
    ) * Decimal('1.40')

    # Contratos por vencer
    try:
        contratos_vence_30d = Contrato.objects.filter(
            estado='VIGENTE',
            fecha_fin__lte=date.today() + timedelta(days=30),
            fecha_fin__gte=date.today(),
        ).count()
    except Exception:
        contratos_vence_30d = 0

    # ── PDF ──
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm,
        topMargin=1.4 * cm, bottomMargin=1.4 * cm,
    )

    styles = getSampleStyleSheet()
    titulo = ParagraphStyle(
        'titulo', parent=styles['Title'], fontSize=22,
        textColor=TEAL_DARK, alignment=0, spaceAfter=4,
    )
    subtitulo = ParagraphStyle(
        'subtitulo', parent=styles['Normal'], fontSize=10,
        textColor=GREY, alignment=0, spaceAfter=14,
    )
    h2 = ParagraphStyle(
        'h2', parent=styles['Heading2'], fontSize=12,
        textColor=TEAL, spaceBefore=12, spaceAfter=6,
    )
    body = ParagraphStyle(
        'body', parent=styles['Normal'], fontSize=9,
        textColor=INK, leading=13,
    )

    story = []

    # ── Header ──
    story.append(Paragraph(
        f'<b>Resumen Ejecutivo del Grupo</b>',
        titulo,
    ))
    story.append(Paragraph(
        f'Generado el {date.today().strftime("%d de %B, %Y")} · '
        f'{total_empresas} locales · {total_workers} colaboradores',
        subtitulo,
    ))

    # ── 4 KPIs grandes en tabla ──
    kpi_data = [[
        Paragraph(f'<para alignment="center"><font size="9" color="#64748b">COLABORADORES</font><br/>'
                  f'<font size="22" color="#0d2b27"><b>{total_workers}</b></font></para>', body),
        Paragraph(f'<para alignment="center"><font size="9" color="#64748b">LOCALES</font><br/>'
                  f'<font size="22" color="#0d2b27"><b>{total_empresas}</b></font></para>', body),
        Paragraph(f'<para alignment="center"><font size="9" color="#64748b">COSTO PLANILLA EST./MES</font><br/>'
                  f'<font size="16" color="#0d2b27"><b>S/ {costo_estimado:,.0f}</b></font></para>', body),
        Paragraph(f'<para alignment="center"><font size="9" color="#64748b">CONTRATOS POR VENCER (30d)</font><br/>'
                  f'<font size="22" color="{"#dc2626" if contratos_vence_30d > 5 else "#16a34a"}"><b>{contratos_vence_30d}</b></font></para>', body),
    ]]
    kpi_t = Table(kpi_data, colWidths=[4.2 * cm] * 4)
    kpi_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.8, GREY_SOFT),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, GREY_SOFT),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fafbfc')),
    ]))
    story.append(kpi_t)

    # ── Desglose por local ──
    story.append(Paragraph('Desglose por local', h2))
    locales_data = [['Local', 'RUC', 'Colaboradores', 'Plan']]
    for emp in empresas:
        n = Personal.objects.filter(empresa=emp, estado='Activo').count()
        locales_data.append([
            Paragraph(f'<font size="9">{emp.razon_social[:45]}</font>', body),
            Paragraph(f'<font size="8" color="#64748b">{emp.ruc}</font>', body),
            Paragraph(f'<para alignment="center"><font size="10"><b>{n}</b></font></para>', body),
            Paragraph(f'<font size="8" color="#0f766e">{emp.plan}</font>', body),
        ])
    locales_t = Table(locales_data, colWidths=[8 * cm, 3 * cm, 3 * cm, 3 * cm])
    locales_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (2, 0), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, GREY_SOFT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#fafbfc')]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(locales_t)

    # ── Alertas / Próximos pasos ──
    story.append(Paragraph('Alertas y próximos pasos', h2))
    alertas_text = []
    if contratos_vence_30d > 0:
        alertas_text.append(f'• <b>{contratos_vence_30d} contratos vencen en próximos 30 días</b> — revisar para renovación.')

    try:
        from vacaciones.models import SolicitudVacacion
        vac_pend = SolicitudVacacion.objects.filter(estado='PENDIENTE').count()
        if vac_pend > 0:
            alertas_text.append(f'• <b>{vac_pend} solicitudes de vacaciones pendientes</b> — RRHH debe aprobar.')
    except Exception:
        pass

    try:
        from workflows.models import InstanciaFlujo
        wf_pend = InstanciaFlujo.objects.filter(estado='PENDIENTE').count()
        if wf_pend > 0:
            alertas_text.append(f'• <b>{wf_pend} aprobaciones en bandeja</b> — workflows esperando.')
    except Exception:
        pass

    if not alertas_text:
        alertas_text.append('• <font color="#16a34a">✓ Sin alertas críticas. Todo en orden.</font>')

    for txt in alertas_text:
        story.append(Paragraph(txt, body))
        story.append(Spacer(1, 0.15 * cm))

    # ── Footer ──
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f'<para alignment="center"><font size="7" color="#94a3b8">'
        f'Generado por Harmoni ERP · {date.today().strftime("%d/%m/%Y")} · harmoni.pe'
        f'</font></para>',
        body,
    ))

    doc.build(story)
    buffer.seek(0)

    fname = f'reporte_grupo_ejecutivo_{date.today().strftime("%Y%m%d")}.pdf'
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response
