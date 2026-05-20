"""
Constancia de Entrega y Recepción de Boleta de Pago.

PDF formal cumpliendo DS 009-2011-TR (Reglamento de Boletas Electrónicas).
Inspirado en SmartBoletas: documento auditable que sirve como prueba ante
SUNAFIL de que el trabajador recibió efectivamente su boleta.

Contenido:
- Datos del empleador (razón social, RUC, dirección).
- Datos del trabajador (nombres, DNI, cargo, área).
- Boleta período + neto pagado.
- Hash de integridad (mismo que el de la boleta original).
- Trail completo de actividad del trabajador:
    * Login(s) más reciente(s)
    * Vista(s) de la boleta en el portal
    * Descarga(s) del PDF
    * Confirmación de recepción explícita
- Texto legal de cumplimiento DS 009-2011-TR.
- QR para verificación pública.
"""
from __future__ import annotations

import io
import hashlib
from decimal import Decimal
from datetime import date

from django.conf import settings


def generar_constancia_recepcion_pdf(registro):
    """Genera una constancia de recepción PDF para un RegistroNomina.

    Returns: bytes del PDF.
    """
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
        Image as RLImage,
    )
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT, TA_JUSTIFY

    from .pdf import (
        generar_token_verificacion, calcular_hash_integridad,
        _build_qr_image, _monto, _p,
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

    base       = sty("base")
    bold       = sty("bold",   fontName="Helvetica-Bold")
    sm         = sty("sm",     fontSize=7.5, textColor=C_GRAY_B)
    smr        = sty("smr",    fontSize=7.5, textColor=C_GRAY_B, alignment=TA_RIGHT)
    title      = sty("title",  fontSize=18, fontName="Helvetica-Bold",
                     textColor=C_DARK, alignment=TA_CENTER, leading=22)
    subtitle   = sty("subt",   fontSize=11, textColor=C_TEAL, alignment=TA_CENTER,
                     leading=14)
    section    = sty("sect",   fontSize=10, fontName="Helvetica-Bold",
                     textColor=C_WHITE, leading=13)
    lbl        = sty("lbl",    fontSize=8, fontName="Helvetica-Bold", textColor=C_GRAY_B)
    val        = sty("val",    fontSize=9)
    legal      = sty("legal",  fontSize=8, textColor=C_GRAY_B, alignment=TA_JUSTIFY,
                     leading=11)
    foot       = sty("foot",   fontSize=7, textColor=C_GRAY_T, alignment=TA_CENTER,
                     leading=9)
    hash_st    = sty("hash",   fontSize=8, textColor=C_GRAY_B, fontName="Courier")
    evento_l   = sty("evt_l",  fontSize=8.5, fontName="Helvetica-Bold")
    evento_v   = sty("evt_v",  fontSize=8)
    evento_t   = sty("evt_t",  fontSize=7.5, textColor=C_GRAY_B, fontName="Courier")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f"Constancia Recepción Boleta — {registro.personal}",
    )

    story = []
    p = registro.personal
    periodo = registro.periodo

    # ── Header con logo ───────────────────────────────────────────
    import os as _os
    logo_path = _os.path.join(settings.BASE_DIR, 'static', 'images', 'logo-mark-120.png')
    if _os.path.exists(logo_path):
        logo = RLImage(logo_path, width=20*mm, height=20*mm)
        hdr = Table(
            [[logo, Paragraph(
                "<b>CONSTANCIA DE ENTREGA<br/>Y RECEPCIÓN</b><br/>"
                "<font size=8 color='#475569'>"
                "Boleta de Pago Electrónica · DS 009-2011-TR"
                "</font>",
                ParagraphStyle("hdr_t", fontSize=14, leading=17,
                               textColor=C_DARK, alignment=TA_RIGHT),
            )]],
            colWidths=[24*mm, USABLE_W - 24*mm],
        )
        hdr.setStyle(TableStyle([
            ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",  (0,0),(-1,-1), 0),
            ("RIGHTPADDING", (0,0),(-1,-1), 0),
        ]))
        story.append(hdr)
    else:
        story.append(Paragraph("CONSTANCIA DE ENTREGA Y RECEPCIÓN", title))
        story.append(Paragraph("Boleta de Pago Electrónica · DS 009-2011-TR", subtitle))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=C_TEAL, thickness=1.5))
    story.append(Spacer(1, 12))

    # ── Datos empleador ──────────────────────────────────────────
    emp = getattr(p, 'empresa', None)
    razon_social = getattr(emp, 'razon_social', '') if emp else ''
    ruc          = getattr(emp, 'ruc', '') if emp else ''
    direccion    = getattr(emp, 'direccion', '') if emp else ''

    sec_emp = Table([[Paragraph("DATOS DEL EMPLEADOR", section)]],
                    colWidths=[USABLE_W])
    sec_emp.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), C_DARK),
        ("LEFTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",  (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(sec_emp)
    story.append(Spacer(1, 3))

    emp_data = [
        [_p("Razón Social:", lbl), _p(razon_social or "—", val)],
        [_p("RUC:", lbl),           _p(ruc or "—", val)],
        [_p("Dirección:", lbl),     _p(direccion or "—", val)],
    ]
    et = Table(emp_data, colWidths=[35*mm, USABLE_W - 35*mm])
    et.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_GRAY_L),
        ("BOX",          (0,0),(-1,-1), 0.5, C_GRAY_E),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(et)
    story.append(Spacer(1, 10))

    # ── Datos trabajador ─────────────────────────────────────────
    cargo = str(getattr(p, 'cargo', '') or '—')
    try:
        area = p.subarea.area.nombre if p.subarea and p.subarea.area else '—'
    except Exception:
        area = '—'

    sec_trab = Table([[Paragraph("DATOS DEL TRABAJADOR", section)]],
                     colWidths=[USABLE_W])
    sec_trab.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), C_TEAL),
        ("LEFTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",  (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(sec_trab)
    story.append(Spacer(1, 3))

    trab_data = [
        [_p("Nombres y Apellidos:", lbl), _p(str(p.apellidos_nombres), bold),
         _p("DNI/CE:", lbl), _p(str(p.nro_doc), val)],
        [_p("Cargo:", lbl), _p(cargo, val),
         _p("Área:", lbl), _p(area, val)],
    ]
    tt = Table(trab_data, colWidths=[42*mm, 65*mm, 24*mm, 43*mm])
    tt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_GRAY_L),
        ("BOX",          (0,0),(-1,-1), 0.5, C_GRAY_E),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(tt)
    story.append(Spacer(1, 10))

    # ── Boleta referenciada ──────────────────────────────────────
    sec_bol = Table([[Paragraph("BOLETA DE PAGO REFERENCIADA", section)]],
                    colWidths=[USABLE_W])
    sec_bol.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), C_GREEN_B),
        ("LEFTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",  (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(sec_bol)
    story.append(Spacer(1, 3))

    hash_int = calcular_hash_integridad(registro)
    token_ver = generar_token_verificacion(registro)
    neto = registro.neto_a_pagar or Decimal("0")
    try:
        mes_nombre = periodo.mes_nombre
        anio = periodo.anio
        tipo = periodo.get_tipo_display() if hasattr(periodo, 'get_tipo_display') else 'Planilla Regular'
    except Exception:
        mes_nombre, anio, tipo = '', '', 'Planilla Regular'

    bol_data = [
        [_p("Período:", lbl),   _p(f"{mes_nombre} {anio}", bold),
         _p("Tipo:", lbl),       _p(tipo, val)],
        [_p("Neto pagado:", lbl), _p(f"S/ {_monto(neto)}", bold),
         _p("Hash:", lbl),      _p(hash_int or "—", hash_st)],
    ]
    bt = Table(bol_data, colWidths=[32*mm, 50*mm, 32*mm, 60*mm])
    bt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), C_GRAY_L),
        ("BOX",          (0,0),(-1,-1), 0.5, C_GRAY_E),
        ("VALIGN",       (0,0),(-1,-1), "TOP"),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 4),
        ("BOTTOMPADDING",(0,0),(-1,-1), 4),
    ]))
    story.append(bt)
    story.append(Spacer(1, 10))

    # ── Trail de actividad ───────────────────────────────────────
    sec_log = Table([[Paragraph("TRAIL DE ACTIVIDAD DEL TRABAJADOR", section)]],
                    colWidths=[USABLE_W])
    sec_log.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), colors.HexColor("#7c3aed")),
        ("LEFTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",  (0,0),(-1,-1), 5),
        ("BOTTOMPADDING", (0,0),(-1,-1), 5),
    ]))
    story.append(sec_log)
    story.append(Spacer(1, 3))

    eventos = _obtener_trail(registro)

    if eventos:
        # Header de la tabla
        log_rows = [[
            _p("Evento", evento_l), _p("Fecha y hora", evento_l),
            _p("IP", evento_l), _p("Dispositivo", evento_l),
        ]]
        for ev in eventos:
            log_rows.append([
                _p(ev["tipo_display"], evento_v),
                _p(ev["timestamp_str"], evento_v),
                _p(ev["ip"] or "—", evento_t),
                _p(_truncar(ev["user_agent"], 40), evento_t),
            ])
        lt = Table(log_rows, colWidths=[42*mm, 38*mm, 28*mm, 66*mm])
        lt.setStyle(TableStyle([
            ("BACKGROUND",   (0,0),(-1,0), colors.HexColor("#ddd6fe")),
            ("BOX",          (0,0),(-1,-1), 0.5, C_GRAY_E),
            ("INNERGRID",    (0,0),(-1,-1), 0.25, C_GRAY_E),
            ("VALIGN",       (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",  (0,0),(-1,-1), 6),
            ("RIGHTPADDING", (0,0),(-1,-1), 6),
            ("TOPPADDING",   (0,0),(-1,-1), 3),
            ("BOTTOMPADDING",(0,0),(-1,-1), 3),
        ]))
        story.append(lt)
    else:
        story.append(_p("Sin actividad registrada aún.", sm))
    story.append(Spacer(1, 12))

    # ── Texto legal ──────────────────────────────────────────────
    texto_legal = (
        "Conste por el presente documento que el trabajador identificado arriba "
        "ha tenido acceso efectivo a su boleta de pago correspondiente al período "
        f"<b>{mes_nombre} {anio}</b> a través del portal del trabajador del sistema "
        "Harmoni ERP, en cumplimiento de lo dispuesto por el Decreto Supremo "
        "N° 009-2011-TR (Reglamento de la Ley sobre Modalidades Formativas Laborales "
        "y otras disposiciones).<br/><br/>"
        "El presente registro de actividad constituye <b>constancia de entrega y "
        "recepción electrónica</b> de la boleta de pago, sustituyendo la firma "
        "física en cumplimiento de los criterios establecidos en el referido "
        "decreto supremo. La integridad del documento original está garantizada "
        f"por el hash criptográfico SHA-256 mostrado arriba ({hash_int})."
    )
    story.append(Paragraph(texto_legal, legal))
    story.append(Spacer(1, 14))

    # ── Footer con QR + fecha emisión ─────────────────────────────
    from django.utils import timezone as _tz
    emitido = _tz.localtime().strftime("%d de %B de %Y, %H:%M:%S")
    # Reemplazar nombres de mes en inglés por español (si el locale no lo hace)
    meses_es = {
        "January": "enero", "February": "febrero", "March": "marzo",
        "April": "abril", "May": "mayo", "June": "junio",
        "July": "julio", "August": "agosto", "September": "septiembre",
        "October": "octubre", "November": "noviembre", "December": "diciembre",
    }
    for en, es in meses_es.items():
        emitido = emitido.replace(en, es)

    verify_url = ""
    try:
        from django.urls import reverse
        from django.conf import settings as _s
        host = getattr(_s, 'PUBLIC_HOST', 'https://harmoni.pe')
        if token_ver:
            verify_url = f"{host}/nominas/verificar/{token_ver}/"
    except Exception:
        pass

    qr_img = _build_qr_image(verify_url, size_mm=22) if verify_url else None

    if qr_img:
        foot_table = Table([[
            qr_img,
            Paragraph(
                f"<b>Documento emitido el {emitido} (hora Lima).</b><br/>"
                "Verificación pública de la boleta:<br/>"
                f"<font size=6 face='Courier'>{verify_url}</font><br/><br/>"
                f"Hash de integridad: <font face='Courier'>{hash_int}</font>",
                ParagraphStyle("foot_p", fontSize=7.5, leading=10,
                               textColor=C_GRAY_B),
            ),
        ]], colWidths=[26*mm, USABLE_W - 26*mm])
        foot_table.setStyle(TableStyle([
            ("VALIGN", (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0),(-1,-1), 0),
            ("RIGHTPADDING",(0,0),(-1,-1), 0),
        ]))
        story.append(foot_table)
    else:
        story.append(_p(f"Documento emitido el {emitido}.", foot))
        story.append(_p(f"Hash de integridad: {hash_int}", foot))

    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", color=C_GRAY_E, thickness=0.5))
    story.append(_p("Generado por Harmoni ERP — Sistema de Gestión de RRHH y Planillas", foot))

    doc.build(story)
    return buf.getvalue()


def _obtener_trail(registro):
    """Devuelve la lista de eventos del log para mostrar en el PDF.

    Eventos relevantes: LOGIN (del trabajador) + VIEW_BOLETA + DOWNLOAD_BOLETA
    + CONFIRM_BOLETA. Limitado a los últimos 30 eventos para no inflar el PDF.
    """
    try:
        from documentos.models import LogActividadTrabajador
        tipos_relevantes = ['LOGIN', 'VIEW_BOLETA', 'DOWNLOAD_BOLETA', 'CONFIRM_BOLETA']
        qs = LogActividadTrabajador.objects.filter(
            personal=registro.personal,
            tipo__in=tipos_relevantes,
        ).order_by('-timestamp')[:30]
        from django.utils import timezone as _tz
        eventos = []
        # Mostramos en orden cronológico (más viejo primero)
        for log in reversed(list(qs)):
            try:
                ts_local = _tz.localtime(log.timestamp)
                ts_str = ts_local.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                ts_str = str(log.timestamp)
            eventos.append({
                "tipo_display": log.get_tipo_display(),
                "timestamp_str": ts_str,
                "ip": log.ip,
                "user_agent": log.user_agent,
            })
        return eventos
    except Exception:
        return []


def _truncar(text, n):
    if text is None:
        return ""
    s = str(text)
    return s if len(s) <= n else s[: max(1, n - 1)] + "…"
