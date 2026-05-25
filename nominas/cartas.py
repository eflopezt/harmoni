"""
Generadores PDF de documentos al cese — Sprint 3 Liquidaciones.

Documentos producidos:
- `generar_carta_no_adeudo(liquidacion)` — Carta de no adeudo y liberación mutua,
  emitida por la empresa al trabajador cesado tras pagar la liquidación.
- `generar_certificado_trabajo(personal)` — Certificado de trabajo según
  costumbre peruana (período laborado, cargo, desempeño).

Ambos usan ReportLab y reutilizan el header / paleta / token de verificación de
`nominas.pdf` para conservar la identidad visual de Harmoni.
"""
from __future__ import annotations

import hashlib
import io
import logging
import os
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from django.conf import settings

logger = logging.getLogger('nominas.cartas')


# ── Helpers compartidos ──────────────────────────────────────────────────────

C_BORDER = colors.HexColor('#000000')
C_TXT    = colors.HexColor('#1a1a1a')
C_LBL    = colors.HexColor('#374151')
C_MUTED  = colors.HexColor('#6b7280')
C_LINE_S = colors.HexColor('#d1d5db')


_MESES_ES = [
    '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'setiembre', 'octubre', 'noviembre', 'diciembre',
]


def _fecha_larga_es(d) -> str:
    """Devuelve fecha en formato 'Lima, 25 de mayo de 2026'."""
    if d is None:
        return ''
    try:
        return f"{d.day} de {_MESES_ES[d.month]} de {d.year}"
    except Exception:
        return d.isoformat() if hasattr(d, 'isoformat') else str(d)


def _monto(v) -> str:
    if v is None:
        return '0.00'
    try:
        d = Decimal(str(v))
        # Formato peruano con separador de miles
        entero = int(d)
        decimales = (d - Decimal(entero)).copy_abs()
        s_ent = f"{entero:,}".replace(',', ' ').replace(' ', ',')
        return f"{s_ent}.{int(decimales * 100):02d}"
    except Exception:
        return '0.00'


def _safe(text):
    if text is None:
        return ''
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _p(text, style):
    return Paragraph(_safe(text), style)


def _load_logo_path():
    """Mismo logo que la boleta — favicon-512 sólido para nitidez."""
    try:
        for candidate in [
            os.path.join(settings.BASE_DIR, 'static', 'images', 'brand', 'png', 'harmoni-favicon-512.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'brand', 'png', 'harmoni-favicon-256.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'brand', 'png', 'harmoni-mark-256.png'),
        ]:
            if os.path.exists(candidate):
                return candidate
    except Exception:
        return None
    return None


def _empresa_info(personal):
    """
    Resuelve nombre / RUC / dirección de la empresa con la misma prioridad
    que `nominas.pdf.generar_boleta_pdf`:
        1) `Personal.empresa` (multi-tenant).
        2) `ConfiguracionSistema` singleton (fallback).
    """
    nombre = 'Empresa'
    ruc = ''
    direccion = ''
    emp = getattr(personal, 'empresa', None)
    if emp is not None:
        nombre = (
            getattr(emp, 'razon_social', None)
            or getattr(emp, 'nombre_comercial', None)
            or nombre
        )
        ruc = getattr(emp, 'ruc', '') or ''
        direccion = getattr(emp, 'direccion', '') or ''
    if nombre == 'Empresa' or not ruc:
        try:
            from asistencia.models import ConfiguracionSistema
            cfg = ConfiguracionSistema.get()
            if cfg:
                if nombre == 'Empresa':
                    nombre = cfg.empresa_nombre or nombre
                ruc = ruc or (cfg.ruc or '')
                direccion = direccion or (getattr(cfg, 'empresa_direccion', '') or '')
        except Exception as exc:
            logger.warning('No se pudo cargar ConfiguracionSistema: %s', exc)
    return nombre, ruc, direccion


def _generar_token_carta(prefix: str, *partes) -> str:
    """
    Token de verificación pública para la carta. 32 chars. Reusa la
    misma estructura que `nominas.pdf.generar_token_verificacion`
    (sha256 + SECRET_KEY) pero parametrizable según el tipo de documento.
    """
    try:
        secret = getattr(settings, 'SECRET_KEY', '')
        raw = '|'.join([prefix] + [str(p) for p in partes] + [secret])
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:32]
    except Exception as exc:
        logger.warning('Error generando token carta: %s', exc)
        return ''


def _hash_integridad(*partes) -> str:
    """Hash interno (16 chars) — no depende de SECRET_KEY."""
    try:
        raw = '|'.join(str(p) for p in partes)
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]
    except Exception as exc:
        logger.warning('Error hash integridad carta: %s', exc)
        return ''


def _build_qr_image(url, size_mm=18):
    try:
        import qrcode
    except Exception:
        return None
    try:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        return RLImage(buf, width=size_mm * mm, height=size_mm * mm)
    except Exception as exc:
        logger.warning('Error renderizando QR carta: %s', exc)
        return None


def _styles():
    """Estilos base reutilizados por ambos PDFs."""
    def sty(name, **kw):
        d = dict(fontName='Helvetica', fontSize=10, leading=14, textColor=C_TXT)
        d.update(kw)
        return ParagraphStyle(name, **d)

    return dict(
        h_emp    = sty('h_emp',   fontSize=12, fontName='Helvetica-Bold', leading=14),
        h_meta   = sty('h_meta',  fontSize=8.5, textColor=C_TXT),
        h_title  = sty('h_title', fontSize=15, fontName='Helvetica-Bold',
                       alignment=TA_CENTER, leading=20, spaceAfter=6, spaceBefore=4),
        body     = sty('body',    fontSize=10, leading=15, alignment=TA_JUSTIFY),
        body_b   = sty('body_b',  fontSize=10, leading=15, alignment=TA_JUSTIFY,
                       fontName='Helvetica-Bold'),
        right    = sty('right',   fontSize=10, leading=14, alignment=TA_RIGHT),
        sig_line = sty('sig_l',   fontSize=10, alignment=TA_CENTER),
        sig_lbl  = sty('sig_lbl', fontSize=9, fontName='Helvetica-Bold',
                       textColor=C_LBL, alignment=TA_CENTER),
        sig_sub  = sty('sig_sub', fontSize=8.5, textColor=C_MUTED,
                       alignment=TA_CENTER),
        ft_note  = sty('ft_note', fontSize=7, textColor=C_MUTED,
                       alignment=TA_CENTER, leading=9),
        ft_hash  = sty('ft_hash', fontSize=6.5, textColor=C_MUTED,
                       fontName='Courier'),
    )


def _build_header(empresa_nombre, empresa_ruc, empresa_dir, usable_w, styles):
    """Header común: logo + datos empresa + línea separadora."""
    info_box = [_p(empresa_nombre, styles['h_emp'])]
    if empresa_ruc:
        info_box.append(_p(f'RUC: {empresa_ruc}', styles['h_meta']))
    if empresa_dir:
        info_box.append(_p(empresa_dir, styles['h_meta']))

    logo_path = _load_logo_path()
    if logo_path:
        try:
            logo_img = RLImage(logo_path, width=18 * mm, height=18 * mm)
            logo_img.hAlign = 'LEFT'
            hl = Table([[logo_img, info_box]], colWidths=[20 * mm, usable_w - 20 * mm])
            hl.setStyle(TableStyle([
                ('VALIGN',       (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING',  (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING',   (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
            ]))
            return hl
        except Exception as exc:
            logger.warning('No se pudo cargar logo en carta: %s', exc)
    # Fallback sin logo
    tbl = Table([[info_box]], colWidths=[usable_w])
    tbl.setStyle(TableStyle([
        ('LEFTPADDING',  (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    return tbl


def _build_footer(token, hash_int, doc_num, base_url, usable_w, styles, prefix='carta'):
    """Footer: hash de integridad, número de documento, QR de verificación."""
    verify_url = ''
    if token:
        verify_url = f"{base_url.rstrip('/')}/nominas/verificar-doc/{prefix}/{token}/"

    meta_lines = [
        _p(
            f'Documento N° {doc_num} · Documento electrónico generado por Harmoni ERP',
            styles['ft_note'],
        ),
    ]
    if hash_int:
        meta_lines.append(_p(f'Hash integridad: {hash_int}', styles['ft_hash']))
    if verify_url:
        meta_lines.append(_p(f'Verificación: {verify_url}', styles['ft_hash']))

    qr = _build_qr_image(verify_url, size_mm=20) if verify_url else None
    if qr is not None:
        qr_w = 24 * mm
        ft_block = Table(
            [[meta_lines, [qr]]],
            colWidths=[usable_w - qr_w, qr_w],
        )
        ft_block.setStyle(TableStyle([
            ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
            ('ALIGN',        (1, 0), (1, 0),   'RIGHT'),
            ('LEFTPADDING',  (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING',   (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING',(0, 0), (-1, -1), 2),
        ]))
        return [ft_block]
    return meta_lines


# ── 1. Carta de no adeudo ────────────────────────────────────────────────────

def generar_carta_no_adeudo(liquidacion) -> bytes:
    """
    Genera el PDF "Carta de no adeudo y liberación mutua" para una
    `LiquidacionLaboral` ya aprobada/pagada.

    Estructura:
        - Header empresa (logo + razón social + RUC + dirección)
        - Título "CARTA DE NO ADEUDO Y LIBERACIÓN MUTUA"
        - Lugar y fecha (Lima, dd de mes de aaaa)
        - Cuerpo formal: empresa declara que pagó la liquidación al
          trabajador (DNI + nombre), detallando el monto total y los
          conceptos. Ambas partes declaran no tener deudas pendientes.
        - 2 firmas: empleador (línea + nombre/cargo) y trabajador (línea + DNI)
        - Footer: N° doc, hash integridad, URL de verificación + QR

    Returns: bytes del PDF.
    """
    personal = liquidacion.personal
    empresa_nombre, empresa_ruc, empresa_dir = _empresa_info(personal)

    # ── Datos clave ──────────────────────────────────────────────────────
    fecha_emision = liquidacion.firmada_en.date() if liquidacion.firmada_en else liquidacion.fecha_cese
    doc_num = f'CNA-{liquidacion.pk:06d}'

    # Token de verificación pública
    token = _generar_token_carta(
        'carta-no-adeudo',
        liquidacion.pk,
        personal.nro_doc,
        liquidacion.total_neto,
        liquidacion.fecha_cese,
    )
    hash_int = _hash_integridad(
        liquidacion.pk,
        personal.nro_doc,
        liquidacion.total_neto,
        liquidacion.fecha_cese,
    )
    base_url = getattr(settings, 'BOLETA_VERIFY_BASE_URL', 'https://harmoni.pe')

    # ── PDF ──────────────────────────────────────────────────────────────
    PAGE_W, PAGE_H = A4
    MARGIN   = 20 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f'Carta de no adeudo — {personal.apellidos_nombres}',
        author=empresa_nombre,
    )
    s = _styles()
    story = []

    # Header
    story.append(_build_header(empresa_nombre, empresa_ruc, empresa_dir, USABLE_W, s))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', color=C_BORDER, thickness=1))
    story.append(Spacer(1, 12))

    # Lugar y fecha (alineado a la derecha)
    lugar = 'Lima'
    if empresa_dir:
        # tomar la última parte como ciudad si el texto trae coma
        partes = [p.strip() for p in empresa_dir.split(',') if p.strip()]
        if partes:
            lugar = partes[-1]
    story.append(_p(f'{lugar}, {_fecha_larga_es(fecha_emision)}', s['right']))
    story.append(Spacer(1, 16))

    # Título
    story.append(_p('CARTA DE NO ADEUDO Y LIBERACIÓN MUTUA', s['h_title']))
    story.append(Spacer(1, 10))

    # Cuerpo
    motivo_display = liquidacion.get_motivo_cese_display() if hasattr(liquidacion, 'get_motivo_cese_display') else liquidacion.motivo_cese
    monto_total = _monto(liquidacion.total_neto)

    # Lista de conceptos efectivamente pagados
    conceptos = []
    for label, valor in [
        ('Sueldo del mes en curso',     liquidacion.sueldo_mes_curso),
        ('Gratificación trunca',        liquidacion.gratif_trunca),
        ('CTS trunca',                  liquidacion.cts_trunca),
        ('Vacaciones truncas',          liquidacion.vacaciones_truncas),
        ('Horas extra no compensadas',  liquidacion.he_no_compensadas),
        ('Indemnización por despido',   liquidacion.indemnizacion),
        ('Otros pagos',                 liquidacion.otros_pagos),
    ]:
        try:
            if Decimal(str(valor or 0)) > Decimal('0'):
                conceptos.append(f'{label} (S/ {_monto(valor)})')
        except Exception:
            continue
    conceptos_txt = '; '.join(conceptos) if conceptos else 'beneficios sociales legales correspondientes'

    body_html = (
        f'Por la presente, <b>{_safe(empresa_nombre)}</b>'
        + (f', identificada con RUC N° <b>{_safe(empresa_ruc)}</b>' if empresa_ruc else '')
        + (f', con domicilio en {_safe(empresa_dir)}' if empresa_dir else '')
        + f', declara que el/la Sr./Sra. <b>{_safe(personal.apellidos_nombres)}</b>, '
        f'identificado(a) con DNI N° <b>{_safe(personal.nro_doc)}</b>, '
        f'ha recibido íntegramente y a entera conformidad su <b>liquidación de '
        f'beneficios sociales</b> por el monto total de '
        f'<b>S/ {monto_total}</b> (Soles), correspondiente al cese de su '
        f'vínculo laboral con fecha <b>{liquidacion.fecha_cese.strftime("%d/%m/%Y")}</b> '
        f'por motivo de <b>{_safe(motivo_display)}</b>, conceptos que '
        f'comprenden: {_safe(conceptos_txt)}.'
    )
    story.append(Paragraph(body_html, s['body']))
    story.append(Spacer(1, 10))

    body_html_2 = (
        'En tal sentido, ambas partes dejan expresa constancia de que NO '
        'EXISTEN deudas pendientes ni reclamos por concepto de remuneraciones, '
        'beneficios sociales, indemnizaciones, ni ningún otro derecho derivado '
        'del vínculo laboral extinguido, otorgándose recíprocamente la más '
        'amplia <b>liberación, finiquito y descargo mutuo</b>.'
    )
    story.append(Paragraph(body_html_2, s['body']))
    story.append(Spacer(1, 10))

    body_html_3 = (
        'Sin perjuicio de lo anterior, se deja constancia que la firma de la '
        'presente carta no implica renuncia al derecho del trabajador de '
        'reclamar judicialmente cualquier diferencia que considere le '
        'corresponda, conforme a lo dispuesto por el D.S. 009-2011-TR.'
    )
    story.append(Paragraph(body_html_3, s['body']))
    story.append(Spacer(1, 24))

    # Firmas
    sig_emp = [
        _p('_' * 38, s['sig_line']),
        _p('Por la Empresa', s['sig_lbl']),
        _p(f'{_safe(empresa_nombre)}', s['sig_sub']),
        _p('RRHH / Representante autorizado', s['sig_sub']),
    ]
    sig_trab = [
        _p('_' * 38, s['sig_line']),
        _p('Trabajador', s['sig_lbl']),
        _p(_safe(personal.apellidos_nombres), s['sig_sub']),
        _p(f'DNI N° {_safe(personal.nro_doc)}', s['sig_sub']),
    ]
    fdata = [
        [_p('', s['body']), _p('', s['body'])],   # espacio para firma manual
        [sig_emp, sig_trab],
    ]
    ftt = Table(fdata, colWidths=[USABLE_W * 0.5, USABLE_W * 0.5], rowHeights=[40, None])
    ftt.setStyle(TableStyle([
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
        ('ALIGN',        (0, 0), (-1, -1), 'CENTER'),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',   (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 0),
    ]))
    story.append(ftt)
    story.append(Spacer(1, 20))

    # Footer
    story.append(HRFlowable(width='100%', color=C_LINE_S, thickness=0.3))
    story.append(Spacer(1, 4))
    for elem in _build_footer(token, hash_int, doc_num, base_url, USABLE_W, s,
                              prefix='carta-no-adeudo'):
        story.append(elem)

    doc.build(story)
    return buf.getvalue()


# ── 2. Certificado de trabajo ────────────────────────────────────────────────

def generar_certificado_trabajo(personal) -> bytes:
    """
    Genera el PDF "Certificado de Trabajo" para un trabajador cesado.

    Requiere que el trabajador esté en estado 'Cesado' con `fecha_cese`
    establecida. Lanza ValueError si no cumple.

    Estructura:
        - Header empresa
        - Título "CERTIFICADO DE TRABAJO"
        - Cuerpo: certifica período laborado, cargo, desempeño
        - Frase formal "se expide a solicitud del interesado..."
        - Lugar y fecha
        - Firma de RRHH
        - Footer con N° doc, hash y QR
    """
    if getattr(personal, 'estado', None) != 'Cesado':
        raise ValueError(
            f'No se puede emitir certificado de trabajo para {personal}: '
            f'trabajador no está cesado (estado={personal.estado}).'
        )
    if not personal.fecha_cese:
        raise ValueError(
            f'No se puede emitir certificado de trabajo para {personal}: '
            f'sin fecha_cese registrada.'
        )

    empresa_nombre, empresa_ruc, empresa_dir = _empresa_info(personal)
    fecha_alta = personal.fecha_alta
    fecha_cese = personal.fecha_cese
    cargo = personal.cargo or 'S/E'

    # Desempeño — por defecto "satisfactorio". Si el motivo de cese es
    # despido por causa justa, omitimos el calificativo para no inducir
    # a engaño legal.
    desempeno = 'satisfactorio'
    motivo = (getattr(personal, 'motivo_cese', '') or '').upper()
    if motivo == 'DESPIDO':
        desempeno = ''

    fecha_emision = fecha_cese
    doc_num = f'CT-{personal.pk:06d}'

    token = _generar_token_carta(
        'certificado-trabajo',
        personal.pk,
        personal.nro_doc,
        fecha_alta,
        fecha_cese,
    )
    hash_int = _hash_integridad(
        personal.pk,
        personal.nro_doc,
        fecha_alta,
        fecha_cese,
    )
    base_url = getattr(settings, 'BOLETA_VERIFY_BASE_URL', 'https://harmoni.pe')

    PAGE_W, PAGE_H = A4
    MARGIN   = 20 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title=f'Certificado de Trabajo — {personal.apellidos_nombres}',
        author=empresa_nombre,
    )
    s = _styles()
    story = []

    # Header
    story.append(_build_header(empresa_nombre, empresa_ruc, empresa_dir, USABLE_W, s))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width='100%', color=C_BORDER, thickness=1))
    story.append(Spacer(1, 20))

    # Título
    story.append(_p('CERTIFICADO DE TRABAJO', s['h_title']))
    story.append(Spacer(1, 18))

    # Cuerpo
    desempeno_txt = f' con desempeño <b>{desempeno}</b>' if desempeno else ''
    body_html = (
        f'Por la presente se <b>CERTIFICA</b> que el/la Sr./Sra. '
        f'<b>{_safe(personal.apellidos_nombres)}</b>, identificado(a) con '
        f'Documento Nacional de Identidad N° <b>{_safe(personal.nro_doc)}</b>, '
        f'laboró en <b>{_safe(empresa_nombre)}</b>'
        + (f' (RUC {_safe(empresa_ruc)})' if empresa_ruc else '')
        + f' desde el <b>{fecha_alta.strftime("%d/%m/%Y") if fecha_alta else "—"}</b> '
        f'hasta el <b>{fecha_cese.strftime("%d/%m/%Y")}</b>, '
        f'desempeñando el cargo de <b>{_safe(cargo)}</b>{desempeno_txt}, '
        f'durante todo el período de su relación laboral.'
    )
    story.append(Paragraph(body_html, s['body']))
    story.append(Spacer(1, 14))

    body_html_2 = (
        'Se expide la presente constancia a solicitud del interesado, '
        'para los fines que estime conveniente.'
    )
    story.append(Paragraph(body_html_2, s['body']))
    story.append(Spacer(1, 30))

    # Lugar y fecha
    lugar = 'Lima'
    if empresa_dir:
        partes = [p.strip() for p in empresa_dir.split(',') if p.strip()]
        if partes:
            lugar = partes[-1]
    story.append(_p(f'{lugar}, {_fecha_larga_es(fecha_emision)}', s['right']))
    story.append(Spacer(1, 36))

    # Firma RRHH (centrada)
    sig = [
        _p('_' * 42, s['sig_line']),
        _p('Recursos Humanos', s['sig_lbl']),
        _p(_safe(empresa_nombre), s['sig_sub']),
    ]
    sig_tbl = Table([[sig]], colWidths=[USABLE_W])
    sig_tbl.setStyle(TableStyle([
        ('ALIGN',  (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(sig_tbl)
    story.append(Spacer(1, 20))

    # Footer
    story.append(HRFlowable(width='100%', color=C_LINE_S, thickness=0.3))
    story.append(Spacer(1, 4))
    for elem in _build_footer(token, hash_int, doc_num, base_url, USABLE_W, s,
                              prefix='certificado-trabajo'):
        story.append(elem)

    doc.build(story)
    return buf.getvalue()
