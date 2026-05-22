"""
Contrato de Préstamo — PDF formal con cronograma de cuotas.
"""
from __future__ import annotations

import hashlib
import io
from datetime import date
from decimal import Decimal

from django.conf import settings


def generar_contrato_prestamo_pdf(prestamo) -> bytes:
    """Genera el contrato PDF de un préstamo.

    Si tiene cuotas generadas las incluye, si no se calcula teórico.
    Returns: bytes PDF A4.
    """
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY

    from .cronograma import calcular_cronograma

    PAGE_W, PAGE_H = A4
    MARGIN = 18 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    C_DARK = colors.HexColor('#0d2b27')
    C_TEAL = colors.HexColor('#134e4a')
    C_GRAY_B = colors.HexColor('#475569')
    C_GRAY_L = colors.HexColor('#f1f5f9')
    C_GRAY_E = colors.HexColor('#e2e8f0')
    C_WHITE = colors.white
    C_BLACK = colors.HexColor('#0f172a')

    def sty(name, **kw):
        d = dict(fontName='Helvetica', fontSize=9, leading=12, textColor=C_BLACK)
        d.update(kw)
        return ParagraphStyle(name, **d)

    title = sty('title', fontSize=16, fontName='Helvetica-Bold',
                textColor=C_DARK, alignment=TA_CENTER, leading=20)
    subt = sty('subt', fontSize=10, textColor=C_TEAL, alignment=TA_CENTER, leading=13)
    body = sty('body', fontSize=9, alignment=TA_JUSTIFY, leading=12)
    lbl = sty('lbl', fontSize=7.5, fontName='Helvetica-Bold', textColor=C_GRAY_B)
    val = sty('val', fontSize=9)
    th = sty('th', fontSize=8, fontName='Helvetica-Bold', textColor=C_WHITE,
             alignment=TA_CENTER)
    td = sty('td', fontSize=8, alignment=TA_CENTER)
    td_right = sty('td_right', fontSize=8, alignment=2)
    firma = sty('firma', fontSize=8.5, fontName='Helvetica-Bold',
                textColor=C_GRAY_B, alignment=TA_CENTER)
    foot = sty('foot', fontSize=7, textColor=C_GRAY_B, alignment=TA_CENTER, leading=9)

    personal = prestamo.personal
    empresa_nombre = getattr(settings, 'EMPRESA_NOMBRE', 'Harmoni ERP')
    empresa_ruc = getattr(settings, 'EMPRESA_RUC', '')
    empresa_direccion = getattr(settings, 'EMPRESA_DIRECCION', '')

    raw = (f'{prestamo.pk}|{personal.nro_doc}|{prestamo.monto_efectivo}|'
           f'{prestamo.num_cuotas}|{prestamo.fecha_desembolso or prestamo.fecha_solicitud}')
    verif_hash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f'Contrato Prestamo #{prestamo.pk}',
    )
    story = []

    story.append(Paragraph(empresa_nombre.upper(), title))
    sub_parts = []
    if empresa_ruc:
        sub_parts.append(f'RUC {empresa_ruc}')
    if empresa_direccion:
        sub_parts.append(empresa_direccion)
    if sub_parts:
        story.append(Paragraph(' · '.join(sub_parts), subt))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width='100%', thickness=0.8, color=C_TEAL))
    story.append(Spacer(1, 8))

    story.append(Paragraph('CONTRATO DE PRÉSTAMO Y AUTORIZACIÓN DE DESCUENTO', title))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f'Documento #{prestamo.pk:06d} — Tipo: {prestamo.tipo.nombre}', subt))
    story.append(Spacer(1, 12))

    monto_efectivo = prestamo.monto_efectivo
    fecha_desembolso = prestamo.fecha_desembolso or prestamo.fecha_aprobacion \
        or prestamo.fecha_solicitud
    fecha_primer = prestamo.fecha_primer_descuento or fecha_desembolso

    data_emp = [
        [Paragraph('TRABAJADOR', lbl), Paragraph(personal.apellidos_nombres, val)],
        [Paragraph('DOCUMENTO', lbl), Paragraph(personal.nro_doc, val)],
        [Paragraph('CARGO', lbl), Paragraph(getattr(personal, 'cargo', '') or '—', val)],
        [Paragraph('TIPO PRÉSTAMO', lbl), Paragraph(prestamo.tipo.nombre, val)],
        [Paragraph('MONTO APROBADO', lbl), Paragraph(f'S/ {monto_efectivo:,.2f}', val)],
        [Paragraph('NÚMERO DE CUOTAS', lbl), Paragraph(str(prestamo.num_cuotas), val)],
        [Paragraph('TASA INTERÉS MENSUAL', lbl),
         Paragraph(f'{prestamo.tasa_interes}%' if prestamo.tasa_interes
                   else 'Sin interés (préstamo blanco)', val)],
        [Paragraph('FECHA DESEMBOLSO', lbl),
         Paragraph(fecha_desembolso.strftime('%d/%m/%Y') if fecha_desembolso else '—', val)],
        [Paragraph('INICIO DE DESCUENTO', lbl),
         Paragraph(fecha_primer.strftime('%d/%m/%Y') if fecha_primer else '—', val)],
        [Paragraph('MOTIVO', lbl), Paragraph(prestamo.motivo or '—', val)],
    ]
    tbl_emp = Table(data_emp, colWidths=[55 * mm, USABLE_W - 55 * mm])
    tbl_emp.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), C_GRAY_L),
        ('GRID', (0, 0), (-1, -1), 0.4, C_GRAY_E),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(tbl_emp)
    story.append(Spacer(1, 14))

    clauses = [
        ('PRIMERO — Objeto.',
         f'EL EMPLEADOR otorga a EL TRABAJADOR un préstamo por la suma de '
         f'<b>S/ {monto_efectivo:,.2f}</b> ({prestamo.tipo.nombre}), monto '
         f'que el trabajador declara recibir a su entera satisfacción.'),
        ('SEGUNDO — Forma de pago.',
         f'EL TRABAJADOR autoriza expresamente al EMPLEADOR a descontar de '
         f'su remuneración mensual el importe correspondiente a {prestamo.num_cuotas} '
         f'cuota(s) mensual(es), conforme al cronograma adjunto, a partir '
         f'del período {fecha_primer.strftime("%m/%Y") if fecha_primer else "—"}.'),
        ('TERCERO — Continuidad.',
         'En caso de cese, vacaciones, licencia sin goce o cualquier '
         'modalidad sin remuneración íntegra, el saldo pendiente se '
         'descontará de los conceptos que el empleador deba pagarle '
         '(gratificaciones, CTS, vacaciones truncas, liquidación), '
         'conforme a ley.'),
        ('CUARTO — Pago anticipado.',
         'EL TRABAJADOR podrá cancelar anticipadamente el saldo pendiente '
         'en cualquier momento, sin penalidad alguna.'),
        ('QUINTO — Base legal.',
         'Se rige por el D.S. 003-97-TR (TUO LPCL) y el D.S. 001-98-TR. '
         'La autorización de descuento cumple lo previsto en el artículo '
         '51° del D.S. 001-98-TR.'),
    ]
    for titulo, txt in clauses:
        story.append(Paragraph(f'<b>{titulo}</b> {txt}', body))
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 6))
    story.append(Paragraph('<b>CRONOGRAMA DE CUOTAS</b>', subt))
    story.append(Spacer(1, 4))

    cuotas_qs = list(prestamo.cuotas.order_by('numero').all())
    if cuotas_qs:
        rows_data = [
            (c.numero, c.periodo, c.monto, c.monto, Decimal('0.00'))
            for c in cuotas_qs
        ]
    else:
        cron = calcular_cronograma(
            monto=monto_efectivo,
            num_cuotas=prestamo.num_cuotas,
            fecha_desembolso=fecha_primer or date.today(),
            tasa_interes=prestamo.tasa_interes,
        )
        rows_data = [
            (r['numero'], r['fecha_vencimiento'], r['monto'],
             r['capital'], r['interes'])
            for r in cron
        ]

    header = [
        Paragraph('N°', th),
        Paragraph('Fecha Venc.', th),
        Paragraph('Capital', th),
        Paragraph('Interés', th),
        Paragraph('Cuota', th),
    ]
    table_data = [header]
    total_capital = Decimal('0.00')
    total_interes = Decimal('0.00')
    total_cuota = Decimal('0.00')
    for numero, fecha_v, monto_total, capital, interes in rows_data:
        table_data.append([
            Paragraph(str(numero), td),
            Paragraph(fecha_v.strftime('%d/%m/%Y') if fecha_v else '—', td),
            Paragraph(f'S/ {capital:,.2f}', td_right),
            Paragraph(f'S/ {interes:,.2f}', td_right),
            Paragraph(f'S/ {monto_total:,.2f}', td_right),
        ])
        total_capital += capital
        total_interes += interes
        total_cuota += monto_total

    table_data.append([
        Paragraph('<b>Total</b>', td), '',
        Paragraph(f'<b>S/ {total_capital:,.2f}</b>', td_right),
        Paragraph(f'<b>S/ {total_interes:,.2f}</b>', td_right),
        Paragraph(f'<b>S/ {total_cuota:,.2f}</b>', td_right),
    ])

    tbl_cron = Table(table_data, colWidths=[12 * mm, 28 * mm, 42 * mm, 42 * mm, 42 * mm])
    tbl_cron.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_TEAL),
        ('GRID', (0, 0), (-1, -1), 0.4, C_GRAY_E),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND', (0, -1), (-1, -1), C_GRAY_L),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [C_WHITE, C_GRAY_L]),
    ]))
    story.append(tbl_cron)
    story.append(Spacer(1, 18))

    firmas_data = [
        ['_' * 38, '', '_' * 38],
        [Paragraph('EL TRABAJADOR', firma), '',
         Paragraph('POR EL EMPLEADOR', firma)],
        [Paragraph(personal.apellidos_nombres, firma), '',
         Paragraph('RRHH', firma)],
        [Paragraph(f'DNI {personal.nro_doc}', firma), '',
         Paragraph(empresa_ruc and f'RUC {empresa_ruc}' or '', firma)],
    ]
    tbl_firmas = Table(firmas_data, colWidths=[USABLE_W * 0.45, USABLE_W * 0.10, USABLE_W * 0.45])
    tbl_firmas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(tbl_firmas)
    story.append(Spacer(1, 14))

    story.append(Paragraph(
        f'Documento emitido el {date.today().strftime("%d/%m/%Y")} — '
        f'Hash de verificación: {verif_hash}', foot,
    ))

    doc.build(story)
    return buffer.getvalue()
