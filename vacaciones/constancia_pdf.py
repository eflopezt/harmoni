"""
Constancia de Vacaciones — PDF formal.

Generado al APROBARSE una SolicitudVacacion. Sirve como respaldo
documental para el trabajador y para SUNAFIL ante una eventual
inspección laboral (D.Leg. 713).

Contenido:
- Datos del empleador y del trabajador
- Período de vacaciones aprobado
- Saldo restante post-aprobación
- Firma del manager que aprobó
- QR / hash de verificación (opcional, derivado del pk)
"""
from __future__ import annotations

import hashlib
import io
from datetime import date

from django.conf import settings

# Reutiliza la paleta y helpers existentes de nominas/pdf.py
from nominas.pdf import (
    C_DARK, C_TEAL, C_ACCENT, C_GREEN_L, C_GREEN_B,
    C_GRAY_L, C_GRAY_B, C_GRAY_E, C_GRAY_T, C_BLACK, C_WHITE,
    _p,
)


def generar_constancia_vacaciones_pdf(solicitud) -> bytes:
    """Genera la constancia PDF para una SolicitudVacacion APROBADA.

    Args:
        solicitud: instancia SolicitudVacacion (debe estar en estado APROBADA)

    Returns:
        bytes — contenido binario del PDF
    """
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT

    from .calculadora_saldo import calcular_saldo_vacaciones

    PAGE_W, PAGE_H = A4
    MARGIN = 18 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    def sty(name, **kw):
        d = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=C_BLACK)
        d.update(kw)
        return ParagraphStyle(name, **d)

    title = sty("title", fontSize=18, fontName="Helvetica-Bold",
                textColor=C_DARK, alignment=TA_CENTER, leading=22)
    subtitle = sty("subt", fontSize=11, textColor=C_TEAL, alignment=TA_CENTER,
                   leading=14)
    section = sty("sect", fontSize=10, fontName="Helvetica-Bold",
                  textColor=C_WHITE, leading=13)
    lbl = sty("lbl", fontSize=8, fontName="Helvetica-Bold", textColor=C_GRAY_B)
    val = sty("val", fontSize=9)
    body = sty("body", fontSize=9, alignment=TA_JUSTIFY, leading=13)
    foot = sty("foot", fontSize=7, textColor=C_GRAY_T, alignment=TA_CENTER, leading=9)
    hashst = sty("hash", fontSize=8, textColor=C_GRAY_B, fontName="Courier",
                 alignment=TA_CENTER)
    firma = sty("firma", fontSize=8.5, fontName="Helvetica-Bold",
                textColor=C_GRAY_B, alignment=TA_CENTER)

    personal = solicitud.personal
    empresa_nombre = getattr(settings, 'EMPRESA_NOMBRE', 'Harmoni ERP')
    empresa_ruc = getattr(settings, 'EMPRESA_RUC', '')
    empresa_direccion = getattr(settings, 'EMPRESA_DIRECCION', '')

    # Hash de verificación (auditable)
    raw = f"{solicitud.pk}|{personal.nro_doc}|{solicitud.fecha_inicio}|" \
          f"{solicitud.fecha_fin}|{solicitud.dias_calendario}"
    verif_hash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

    # Saldo restante (recalculado)
    saldo_info = calcular_saldo_vacaciones(personal)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Constancia Vacaciones {personal.nro_doc}",
    )

    story = []

    # ── Encabezado ──
    story.append(Paragraph(empresa_nombre.upper(), title))
    if empresa_ruc or empresa_direccion:
        story.append(Paragraph(
            f"RUC: {empresa_ruc}  ·  {empresa_direccion}",
            sty("hdr", fontSize=8, textColor=C_GRAY_B, alignment=TA_CENTER)
        ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width=USABLE_W, thickness=0.6, color=C_TEAL))
    story.append(Spacer(1, 8))
    story.append(Paragraph("CONSTANCIA DE OTORGAMIENTO DE VACACIONES", subtitle))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Solicitud N° {solicitud.pk:06d} — Emitida el {date.today().strftime('%d/%m/%Y')}",
        sty("sm", fontSize=8, textColor=C_GRAY_B, alignment=TA_CENTER)
    ))
    story.append(Spacer(1, 10))

    # ── Datos del trabajador ──
    area_nombre = '—'
    if personal.subarea:
        if personal.subarea.area:
            area_nombre = f"{personal.subarea.area.nombre} / {personal.subarea.nombre}"
        else:
            area_nombre = personal.subarea.nombre

    datos_trab = [
        [Paragraph("Trabajador", lbl), Paragraph(personal.apellidos_nombres, val)],
        [Paragraph(f"{personal.tipo_doc}", lbl), Paragraph(personal.nro_doc, val)],
        [Paragraph("Área", lbl), Paragraph(area_nombre, val)],
        [Paragraph("Cargo", lbl),
         Paragraph(getattr(personal, 'cargo', '') or '—', val)],
        [Paragraph("Fecha Ingreso", lbl),
         Paragraph(
             personal.fecha_alta.strftime('%d/%m/%Y') if personal.fecha_alta else '—',
             val)],
    ]
    t_trab = Table(datos_trab, colWidths=[USABLE_W * 0.30, USABLE_W * 0.70])
    t_trab.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), C_GRAY_L),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C_GRAY_E),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_trab)
    story.append(Spacer(1, 12))

    # ── Período aprobado ──
    story.append(Paragraph("Período Vacacional Aprobado", sty(
        "h", fontSize=10, fontName="Helvetica-Bold",
        textColor=C_DARK, leading=13,
    )))
    story.append(Spacer(1, 4))

    periodo = [
        [Paragraph("Fecha Inicio", lbl),
         Paragraph(solicitud.fecha_inicio.strftime('%d/%m/%Y'), val),
         Paragraph("Fecha Fin", lbl),
         Paragraph(solicitud.fecha_fin.strftime('%d/%m/%Y'), val)],
        [Paragraph("Días Calendario", lbl),
         Paragraph(f"<b>{solicitud.dias_calendario}</b> días", val),
         Paragraph("Días Hábiles", lbl),
         Paragraph(f"{solicitud.dias_habiles} días", val)],
        [Paragraph("Estado", lbl),
         Paragraph(
             f"<b><font color='#065f46'>{solicitud.get_estado_display()}</font></b>",
             val),
         Paragraph("Fecha Aprobación", lbl),
         Paragraph(
             solicitud.fecha_aprobacion.strftime('%d/%m/%Y') if solicitud.fecha_aprobacion else '—',
             val)],
    ]
    t_per = Table(periodo, colWidths=[
        USABLE_W * 0.20, USABLE_W * 0.30, USABLE_W * 0.20, USABLE_W * 0.30,
    ])
    t_per.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), C_GRAY_L),
        ('BACKGROUND', (2, 0), (2, -1), C_GRAY_L),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C_GRAY_E),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_per)
    story.append(Spacer(1, 12))

    # ── Saldo restante ──
    story.append(Paragraph("Saldo Vacacional Post-Aprobación", sty(
        "h", fontSize=10, fontName="Helvetica-Bold",
        textColor=C_DARK, leading=13,
    )))
    story.append(Spacer(1, 4))

    saldo_tbl = [
        [
            Paragraph("Días Generados (Completos + Truncos)", lbl),
            Paragraph(
                f"{saldo_info['dias_completos']} + {saldo_info['dias_truncos']:.1f} truncos",
                val),
        ],
        [
            Paragraph("Días Consumidos (incluye esta solicitud)", lbl),
            Paragraph(f"{saldo_info['dias_consumidos']} días", val),
        ],
        [
            Paragraph("Saldo Disponible Restante", lbl),
            Paragraph(
                f"<b><font color='#0f766e'>{saldo_info['dias_disponibles']}</font></b> días",
                val),
        ],
    ]
    t_sal = Table(saldo_tbl, colWidths=[USABLE_W * 0.65, USABLE_W * 0.35])
    t_sal.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), C_GRAY_L),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.3, C_GRAY_E),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(t_sal)
    story.append(Spacer(1, 14))

    # ── Cuerpo legal ──
    story.append(Paragraph(
        "Por medio del presente documento, el empleador deja constancia que el "
        f"trabajador <b>{personal.apellidos_nombres}</b>, identificado con "
        f"{personal.tipo_doc} N° <b>{personal.nro_doc}</b>, gozará del descanso "
        f"vacacional correspondiente a su período de servicios, comprendido del "
        f"<b>{solicitud.fecha_inicio.strftime('%d/%m/%Y')}</b> al "
        f"<b>{solicitud.fecha_fin.strftime('%d/%m/%Y')}</b> "
        f"({solicitud.dias_calendario} días calendario), conforme a lo dispuesto "
        "en el Decreto Legislativo N° 713 — Ley de Descansos Remunerados — y su "
        "reglamento DS 012-92-TR.",
        body,
    ))
    story.append(Spacer(1, 6))

    if solicitud.motivo:
        story.append(Paragraph(
            f"<b>Observación del trabajador:</b> {solicitud.motivo}", body
        ))
        story.append(Spacer(1, 6))

    story.append(Paragraph(
        "El trabajador deberá reintegrarse a sus labores habituales el día hábil "
        "siguiente al término del período señalado, salvo que las partes acuerden "
        "por escrito una extensión o anticipo del retorno.",
        body,
    ))
    story.append(Spacer(1, 20))

    # ── Firmas ──
    fecha_emision = date.today().strftime('%d de %B de %Y')
    nombre_mgr = solicitud.aprobado_por.get_full_name() if solicitud.aprobado_por else '—'
    if not nombre_mgr.strip() or nombre_mgr == '—':
        nombre_mgr = (solicitud.aprobado_por.username
                      if solicitud.aprobado_por else 'Recursos Humanos')

    firmas = [
        ["", "", ""],
        ["", "", ""],
        [
            Paragraph("_______________________________", firma),
            "",
            Paragraph("_______________________________", firma),
        ],
        [
            Paragraph(f"<b>{personal.apellidos_nombres}</b>", firma),
            "",
            Paragraph(f"<b>{nombre_mgr}</b>", firma),
        ],
        [
            Paragraph(f"Trabajador<br/>{personal.tipo_doc}: {personal.nro_doc}", firma),
            "",
            Paragraph("Aprobado por<br/>Recursos Humanos / Manager", firma),
        ],
    ]
    t_firmas = Table(firmas, colWidths=[USABLE_W * 0.45, USABLE_W * 0.10, USABLE_W * 0.45])
    t_firmas.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
    ]))
    story.append(t_firmas)
    story.append(Spacer(1, 18))

    # ── Footer con hash ──
    story.append(HRFlowable(width=USABLE_W, thickness=0.3, color=C_GRAY_E))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Documento generado electrónicamente el {fecha_emision}. "
        f"Verificación: <b>{verif_hash}</b>",
        foot,
    ))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
