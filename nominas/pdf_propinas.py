"""
Acta de Distribución de Propinas — PDF.

Reporte PDF firmable por trabajador. Best practice mundial (Toast, TipHaus,
tronc UK): cada manager imprime el acta del período, los trabajadores firman
recibiendo su parte → defensa ante SUNAFIL / disputas internas.

Contenido:
- Datos del local (empresa).
- Período del pool y fecha de distribución.
- Desglose cash + card + retención casa + tip-out BOH (si aplica).
- Tabla por trabajador: cargo, horas (si aplica), puntos, monto, anomalía.
- Sección de firma con espacios para huella/firma de cada trabajador.
- Texto legal (concepto no remunerativo según SUNAT).
- QR opcional.

Ref: docs/internal/PROPINAS_BEST_PRACTICES_2026.md §3 (Auditoría/trazabilidad).
"""
from __future__ import annotations

import io
from decimal import Decimal

from django.conf import settings


def generar_acta_distribucion_pdf(pool) -> bytes:
    """Genera el Acta de Distribución de Propinas de un Pool.

    Parameters
    ----------
    pool : PoolPropinas
        Pool a documentar (ya distribuido o pendiente — se renderiza igual,
        pero las distribuciones aparecen solo si existen).

    Returns
    -------
    bytes
        Contenido del PDF.
    """
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT, TA_JUSTIFY

    from .pdf import (
        _monto, _p,
        C_DARK, C_TEAL, C_ACCENT, C_GREEN_L, C_GREEN_B,
        C_GRAY_L, C_GRAY_B, C_GRAY_E, C_GRAY_T, C_BLACK, C_WHITE,
    )

    PAGE_W, PAGE_H = A4
    MARGIN = 18 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    def sty(name, **kw):
        d = dict(fontName="Helvetica", fontSize=9, leading=12, textColor=C_BLACK)
        d.update(kw)
        return ParagraphStyle(name, **d)

    base = sty("base")
    bold = sty("bold", fontName="Helvetica-Bold")
    sm = sty("sm", fontSize=7.5, textColor=C_GRAY_B)
    title = sty("title", fontSize=18, fontName="Helvetica-Bold",
                textColor=C_DARK, alignment=TA_CENTER, leading=22)
    subtitle = sty("subt", fontSize=11, textColor=C_TEAL, alignment=TA_CENTER,
                   leading=14)
    section = sty("sect", fontSize=10, fontName="Helvetica-Bold",
                  textColor=C_WHITE, leading=13)
    lbl = sty("lbl", fontSize=8, fontName="Helvetica-Bold", textColor=C_GRAY_B)
    val = sty("val", fontSize=9)
    legal = sty("legal", fontSize=8, textColor=C_GRAY_B, alignment=TA_JUSTIFY,
                leading=11)
    foot = sty("foot", fontSize=7, textColor=C_GRAY_T, alignment=TA_CENTER,
               leading=9)
    cell = sty("cell", fontSize=8.5)
    cell_r = sty("cell_r", fontSize=8.5, alignment=TA_RIGHT)
    cell_b = sty("cell_b", fontSize=8.5, fontName="Helvetica-Bold")
    cell_br = sty("cell_br", fontSize=8.5, fontName="Helvetica-Bold",
                  alignment=TA_RIGHT)
    warn = sty("warn", fontSize=8, fontName="Helvetica-Bold",
               textColor=colors.HexColor("#b91c1c"))

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Acta Distribución Propinas — {pool.fecha_inicio:%d-%m-%Y} a {pool.fecha_fin:%d-%m-%Y}",
    )

    story = []
    emp = pool.empresa
    cfg = getattr(emp, 'config_propinas', None)

    # ── Header ─────────────────────────────────────────────────────────
    story.append(Paragraph("ACTA DE DISTRIBUCIÓN DE PROPINAS", title))
    story.append(Paragraph(
        f"Período: {pool.fecha_inicio:%d/%m/%Y} — {pool.fecha_fin:%d/%m/%Y}",
        subtitle,
    ))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", color=C_TEAL, thickness=1.5))
    story.append(Spacer(1, 10))

    # ── Datos del local ────────────────────────────────────────────────
    razon = getattr(emp, 'razon_social', '') or '—'
    ruc = getattr(emp, 'ruc', '') or '—'
    direccion = getattr(emp, 'direccion', '') or '—'
    modo_display = cfg.get_modo_display() if cfg else 'No configurado'

    sec_emp = Table([[Paragraph("DATOS DEL LOCAL", section)]],
                    colWidths=[USABLE_W])
    sec_emp.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_DARK),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sec_emp)
    story.append(Spacer(1, 3))

    emp_data = [
        [_p("Razón Social:", lbl), _p(razon, val),
         _p("RUC:", lbl), _p(ruc, val)],
        [_p("Dirección:", lbl), _p(direccion, val),
         _p("Modo Pool:", lbl), _p(modo_display, val)],
    ]
    et = Table(emp_data, colWidths=[28*mm, 70*mm, 22*mm, USABLE_W-120*mm])
    et.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GRAY_L),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GRAY_E),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(et)
    story.append(Spacer(1, 10))

    # ── Resumen del Pool ───────────────────────────────────────────────
    sec_pool = Table([[Paragraph("RESUMEN DEL POOL", section)]],
                     colWidths=[USABLE_W])
    sec_pool.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_TEAL),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sec_pool)
    story.append(Spacer(1, 3))

    pct_casa = cfg.porcentaje_casa if cfg else Decimal('0')
    pct_boh = cfg.porcentaje_tipout_boh if cfg else Decimal('0')
    pool_rows = [
        [_p("Propinas en efectivo (cash):", lbl),
         _p(f"S/ {_monto(pool.monto_cash)}", cell_br)],
        [_p("Propinas vía tarjeta (card):", lbl),
         _p(f"S/ {_monto(pool.monto_card)}", cell_br)],
        [_p("MONTO BRUTO TOTAL:", bold),
         _p(f"S/ {_monto(pool.monto_bruto)}", cell_br)],
        [_p(f"− Retención casa ({pct_casa}%):", lbl),
         _p(f"S/ {_monto(pool.monto_casa)}", cell_br)],
        [_p("MONTO DISTRIBUIBLE:", bold),
         _p(f"S/ {_monto(pool.monto_distribuible)}", cell_br)],
    ]
    if pool.monto_tipout_boh > 0:
        pool_rows.append([
            _p(f"  · Tip-out a BOH ({pct_boh}%):", lbl),
            _p(f"S/ {_monto(pool.monto_tipout_boh)}", cell_br),
        ])
        pool_rows.append([
            _p("  · Distribuible a FOH:", lbl),
            _p(f"S/ {_monto(pool.monto_distribuible_foh)}", cell_br),
        ])
    pt = Table(pool_rows, colWidths=[USABLE_W * 0.65, USABLE_W * 0.35])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GRAY_L),
        ("BOX", (0, 0), (-1, -1), 0.5, C_GRAY_E),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GRAY_E),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        # Resaltar fila BRUTO TOTAL y DISTRIBUIBLE
        ("BACKGROUND", (0, 2), (-1, 2), C_GREEN_L),
        ("BACKGROUND", (0, 4), (-1, 4), C_GREEN_L),
    ]))
    story.append(pt)
    story.append(Spacer(1, 10))

    # ── Tabla de distribución por trabajador ──────────────────────────
    sec_dist = Table([[Paragraph("DISTRIBUCIÓN POR TRABAJADOR", section)]],
                     colWidths=[USABLE_W])
    sec_dist.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_GREEN_B),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(sec_dist)
    story.append(Spacer(1, 3))

    distribuciones = list(
        pool.distribuciones
        .select_related('personal')
        .order_by('es_tipout_boh', '-monto')
    )

    if distribuciones:
        usa_horas = cfg and cfg.usa_horas
        # Encabezado dinámico
        headers = [
            _p("Trabajador", cell_b),
            _p("DNI", cell_b),
            _p("Cargo", cell_b),
        ]
        if usa_horas:
            headers.append(_p("Horas", cell_br))
        headers.extend([
            _p("Pts", cell_br),
            _p("Monto S/", cell_br),
            _p("Firma", cell_b),
        ])

        rows = [headers]
        total = Decimal('0')
        for d in distribuciones:
            nombre = str(d.personal.apellidos_nombres or '—')
            dni = str(d.personal.nro_doc or '—')
            cargo = str(d.personal.cargo or '—')
            # Marcadores visuales
            etiqueta = ''
            if d.es_tipout_boh:
                etiqueta = ' [TIP-OUT]'
            if d.anomalia:
                etiqueta += ' ⚠'

            row = [
                _p(nombre + etiqueta, cell if not d.anomalia else warn),
                _p(dni, cell),
                _p(cargo, cell),
            ]
            if usa_horas:
                row.append(_p(f"{d.horas}", cell_r))
            row.extend([
                _p(f"{d.puntos}", cell_r),
                _p(f"{_monto(d.monto)}", cell_br),
                _p("", cell),  # espacio para firma manual
            ])
            rows.append(row)
            total += Decimal(d.monto)

        # Fila total
        col_total = 6 if usa_horas else 5
        tot_row = [_p("", cell)] * len(headers)
        tot_row[col_total - 1] = _p("TOTAL:", cell_br)
        tot_row[col_total] = _p(f"S/ {_monto(total)}", cell_br)
        rows.append(tot_row)

        # Anchos de columnas
        if usa_horas:
            col_w = [50*mm, 22*mm, 30*mm, 14*mm, 12*mm, 22*mm, USABLE_W - 150*mm]
        else:
            col_w = [55*mm, 22*mm, 30*mm, 14*mm, 24*mm, USABLE_W - 145*mm]

        dt = Table(rows, colWidths=col_w, repeatRows=1)
        dt_style = [
            ("BACKGROUND", (0, 0), (-1, 0), C_GREEN_L),
            ("BOX", (0, 0), (-1, -1), 0.5, C_GRAY_E),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, C_GRAY_E),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            # Fila TOTAL resaltada
            ("BACKGROUND", (0, -1), (-1, -1), C_GRAY_L),
            ("LINEABOVE", (0, -1), (-1, -1), 1.0, C_DARK),
            # Altura mínima para firma
            ("MINHEIGHT", (-1, 1), (-1, -2), 28),
        ]
        dt.setStyle(TableStyle(dt_style))
        story.append(dt)
    else:
        story.append(_p(
            "Sin distribución registrada aún. Ejecute la distribución antes "
            "de imprimir el acta.", sm,
        ))

    story.append(Spacer(1, 14))

    # ── Texto legal ────────────────────────────────────────────────────
    texto_legal = (
        "El presente documento constituye <b>acta de distribución de propinas</b> "
        "del período indicado. Las propinas y/o recargo al consumo son conceptos "
        "<b>NO REMUNERATIVOS</b> de acuerdo con la posición de SUNAT y la "
        "legislación peruana — no forman parte de la base imponible para AFP/ONP, "
        "CTS, gratificaciones legales ni Impuesto a la Renta de quinta categoría.<br/><br/>"
        "Cada trabajador firma confirmando haber recibido el monto que se le "
        "atribuye en la tabla anterior. Disputas o ajustes deben ser elevados al "
        "responsable del local dentro de las 72 horas posteriores a la firma. "
        "Los registros marcados con ⚠ corresponden a anomalías detectadas "
        "automáticamente (monto < 50% del promedio del cargo) y requieren "
        "revisión manual del responsable antes del pago."
    )
    story.append(Paragraph(texto_legal, legal))
    story.append(Spacer(1, 14))

    # ── Sección de firma del responsable ──────────────────────────────
    firma_resp = Table([
        [_p("Responsable del Local", lbl), _p("", val), _p("Fecha de cierre", lbl)],
        [_p("____________________________", val), _p("", val),
         _p("____________________", val)],
        [_p("Firma y sello", sm), _p("", val), _p("DD/MM/AAAA", sm)],
    ], colWidths=[USABLE_W * 0.45, USABLE_W * 0.10, USABLE_W * 0.45])
    firma_resp.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(firma_resp)
    story.append(Spacer(1, 8))

    # ── Footer ─────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", color=C_GRAY_E, thickness=0.5))
    story.append(Spacer(1, 4))
    distribuido_en = (
        pool.distribuido_en.strftime('%d/%m/%Y %H:%M')
        if pool.distribuido_en else '—'
    )
    story.append(Paragraph(
        f"Generado por Harmoni ERP · Pool ID #{pool.pk} · "
        f"Distribuido: {distribuido_en}",
        foot,
    ))

    doc.build(story)
    return buf.getvalue()
