"""
Nominas - Generador de Boletas de Pago PDF.

Usa ReportLab (dep de xhtml2pdf). Migrado desde xhtml2pdf para evitar
el bug TypeError NoneType>NoneType (negative availWidth en tablas anidadas).
"""
import hashlib
import io
import logging
from decimal import Decimal

logger = logging.getLogger('nominas.pdf')

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    PageBreak, Image as RLImage,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

from django.conf import settings


# Paleta Harmoni
C_DARK    = colors.HexColor("#0d2b27")
C_TEAL    = colors.HexColor("#0f766e")
C_ACCENT  = colors.HexColor("#5eead4")
C_GREEN_L = colors.HexColor("#a7f3d0")
C_GREEN_S = colors.HexColor("#ecfdf5")
C_GREEN_B = colors.HexColor("#065f46")
C_GREEN_E = colors.HexColor("#6ee7b7")
C_RED_H   = colors.HexColor("#b91c1c")
C_RED_L   = colors.HexColor("#fef2f2")
C_RED_B   = colors.HexColor("#991b1b")
C_RED_E   = colors.HexColor("#fca5a5")
C_BLUE_H  = colors.HexColor("#1d4ed8")
C_BLUE_L  = colors.HexColor("#eff6ff")
C_BLUE_B  = colors.HexColor("#1e40af")
C_BLUE_E  = colors.HexColor("#bfdbfe")
C_GRAY_L  = colors.HexColor("#f8fafc")
C_GRAY_B  = colors.HexColor("#4b5563")
C_GRAY_E  = colors.HexColor("#d1d5db")
C_GRAY_T  = colors.HexColor("#9ca3af")
C_PURP_L  = colors.HexColor("#ddd6fe")
C_SUBTOT  = colors.HexColor("#f0f4f8")
C_SUBTOT2 = colors.HexColor("#cbd5e1")
C_BLACK   = colors.HexColor("#1a1a1a")
C_WHITE   = colors.white


def _monto(value):
    if value is None: return "0.00"
    try: return f"{Decimal(str(value)):.2f}"
    except Exception: return "0.00"


def _p(text, style):
    if text is None: text = ""
    text = str(text).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")
    return Paragraph(text, style)


def _truncate(text, n):
    """Trunca con ellipsis si supera n chars."""
    if text is None:
        return ""
    s = str(text)
    return s if len(s) <= n else s[: max(1, n - 1)] + "..."


def generar_token_verificacion(registro):
    """
    Token de verificación pública (32 chars). Estable mientras no cambien:
    id, DNI, neto, fecha_fin del periodo, y SECRET_KEY.
    """
    try:
        personal = registro.personal
        periodo = registro.periodo
        neto = registro.neto_a_pagar or Decimal("0")
        fecha_fin = periodo.fecha_fin if periodo and periodo.fecha_fin else ""
        secret = getattr(settings, "SECRET_KEY", "")
        raw = f"{registro.id}|{personal.nro_doc}|{neto}|{fecha_fin}|{secret}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]
    except Exception as exc:
        logger.warning("Error generando token verificacion: %s", exc)
        return ""


def calcular_hash_integridad(registro):
    """
    Hash interno (16 chars) del snapshot inmutable del registro.
    No depende del SECRET_KEY: dos sistemas con los mismos datos generan el mismo hash.
    """
    try:
        personal = registro.personal
        periodo = registro.periodo
        neto = registro.neto_a_pagar or Decimal("0")
        fecha_fin = periodo.fecha_fin if periodo and periodo.fecha_fin else ""
        raw = f"{neto}|{fecha_fin}|{personal.nro_doc}|{periodo.id if periodo else ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    except Exception as exc:
        logger.warning("Error calculando hash integridad: %s", exc)
        return ""


def _build_qr_image(url, size_mm=20):
    """
    Genera un QR PNG en memoria para `url` y devuelve un reportlab.platypus.Image
    o None si la librería qrcode no está disponible.
    """
    try:
        import qrcode  # opcional — no quiero forzar la dep en tiempo de import
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
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return RLImage(buf, width=size_mm * mm, height=size_mm * mm)
    except Exception as exc:
        logger.warning("Error renderizando QR: %s", exc)
        return None


def generar_boleta_pdf(registro):
    """
    Genera la boleta de pago PDF para RegistroNomina.

    Diseño: estilo formal S10 — sobrio, B&N, formato compacto en 1 página.
    - Logo discreto en cabecera
    - 3 columnas (Remuneraciones / Descuentos / Aportes empleador)
    - Sin sección de provisiones (se acumulan internamente, no van en boleta)
    - Sin caja colorida de Neto, solo línea sobria
    - Una sola hoja (no se duplica empleador/trabajador — boleta digital)
    - QR + hash discretos al pie + leyenda DS 009-2011-TR

    Returns bytes.
    """
    PAGE_W, PAGE_H = A4
    MARGIN   = 12 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    # ── Paleta sobria estilo S10 ─────────────────────────────────────
    C_BORDER = colors.HexColor("#000000")
    C_HEADER_BG = colors.HexColor("#f8f9fa")
    C_LINE   = colors.HexColor("#000000")
    C_LINE_S = colors.HexColor("#d1d5db")
    C_TXT    = colors.HexColor("#1a1a1a")
    C_LBL    = colors.HexColor("#374151")
    C_MUTED  = colors.HexColor("#6b7280")

    def sty(name, **kw):
        d = dict(fontName="Helvetica", fontSize=8, leading=10, textColor=C_TXT)
        d.update(kw)
        return ParagraphStyle(name, **d)

    bold     = sty("bold",    fontName="Helvetica-Bold")
    sm       = sty("sm",      fontSize=7, textColor=C_MUTED)
    smr      = sty("smr",     fontSize=7, textColor=C_MUTED, alignment=TA_RIGHT)
    lbl      = sty("lbl",     fontSize=7,  textColor=C_LBL)            # label de campo (Cargo:, DNI:)
    val      = sty("val",     fontSize=8,  fontName="Helvetica-Bold")  # valor del campo
    h_emp    = sty("h_emp",   fontSize=11, fontName="Helvetica-Bold", textColor=C_TXT, leading=13)
    h_meta   = sty("h_meta",  fontSize=7.5, textColor=C_TXT)
    h_tit    = sty("h_tit",   fontSize=13, fontName="Helvetica-Bold", textColor=C_TXT, alignment=TA_RIGHT, leading=18, spaceAfter=4)
    h_per    = sty("h_per",   fontSize=8, textColor=C_TXT, alignment=TA_RIGHT, leading=11)
    ct_hdr   = sty("ct_hdr",  fontSize=8, fontName="Helvetica-Bold", textColor=C_TXT, alignment=TA_CENTER)
    ct_sub   = sty("ct_sub",  fontSize=7, textColor=C_LBL, alignment=TA_RIGHT)
    ct_nm    = sty("ct_nm",   fontSize=8)
    ct_amt   = sty("ct_amt",  fontName="Helvetica", fontSize=8, alignment=TA_RIGHT)
    ct_sub_l = sty("ct_subl", fontName="Helvetica-Bold", fontSize=8)
    ct_sub_r = sty("ct_subr", fontName="Helvetica-Bold", fontSize=8, alignment=TA_RIGHT)
    net_lbl  = sty("net_lbl", fontSize=10, fontName="Helvetica-Bold", textColor=C_TXT)
    net_val  = sty("net_val", fontName="Helvetica-Bold", fontSize=12, alignment=TA_RIGHT, textColor=C_TXT)
    ft_note  = sty("ft_note", fontSize=6.5, textColor=C_MUTED, alignment=TA_CENTER)
    ft_legal = sty("ft_legal",fontSize=6.5, textColor=C_MUTED, alignment=TA_CENTER, leading=8)
    ft_hash  = sty("ft_hash", fontSize=6.2, textColor=C_MUTED, fontName="Courier")
    pago_st  = sty("pago",    fontSize=7.5)
    fl_st    = sty("fl",      fontSize=7, textColor=C_MUTED, alignment=TA_CENTER)
    fr_st    = sty("fr",      fontSize=7, textColor=C_MUTED, alignment=TA_CENTER)

    # Clasificar lineas — las provisiones (CTS/gratif acumuladas) se
    # excluyen del PDF de boleta. Son acumulaciones internas del empleador
    # que se pagan en las fechas legales (mayo/nov CTS, jul/dic gratif).
    # No aparecen como "provisión" en una boleta digital formal — solo los
    # conceptos efectivamente cobrados/descontados del mes.
    #
    # DS 001-98-TR Art. 19 inc. f) — debemos discriminar conceptos
    # remunerativos (afectos) de los no remunerativos (asignación familiar,
    # viáticos, refrigerio, etc.) para que el trabajador conozca la base
    # de cálculo de sus aportes y CTS.
    lineas_ingresos    = []
    lineas_descuentos  = []
    lineas_aportes     = []
    total_ingresos     = Decimal("0")
    total_descuentos   = Decimal("0")
    total_aportes      = Decimal("0")
    remuneracion_computable = Decimal("0")  # solo conceptos REMUNERATIVOS

    for linea in registro.lineas.select_related("concepto").order_by(
            "concepto__tipo", "concepto__orden"):
        # Filtrar provisiones (CTS, gratif): no van en boleta digital.
        es_provision = (
            getattr(linea.concepto, 'subtipo', '') == 'PROVISION'
            or linea.concepto.formula in ('GRATIFICACION', 'CTS')
        )
        if es_provision and linea.concepto.tipo == "INGRESO":
            continue
        subtipo = getattr(linea.concepto, 'subtipo', 'REMUNERATIVO') or 'REMUNERATIVO'
        es_no_remunerativo = (subtipo == 'NO_REMUNERATIVO')
        # Marcar nombre con asterisco si es no remunerativo (legend al pie)
        nombre_display = linea.concepto.nombre
        if es_no_remunerativo:
            nombre_display = f"{nombre_display} *"
        entry = {"nombre": nombre_display,
                 "monto": linea.monto or Decimal("0"),
                 "monto_str": _monto(linea.monto),
                 "no_remun": es_no_remunerativo,
                 "obs": linea.observacion or ""}
        if linea.concepto.tipo == "INGRESO":
            lineas_ingresos.append(entry)
            total_ingresos += linea.monto or Decimal("0")
            if not es_no_remunerativo:
                remuneracion_computable += linea.monto or Decimal("0")
        elif linea.concepto.tipo == "DESCUENTO":
            lineas_descuentos.append(entry)
            total_descuentos += linea.monto or Decimal("0")
        else:
            lineas_aportes.append(entry)
            total_aportes += linea.monto or Decimal("0")

    # Indicador: ¿hay conceptos no remunerativos en la boleta?
    hay_no_remun = any(l.get('no_remun') for l in lineas_ingresos)

    essalud = registro.aporte_essalud or Decimal("0")
    essalud_en_lineas = any(
        "essalud" in l["nombre"].lower() or "seguro" in l["nombre"].lower()
        for l in lineas_aportes)
    if not essalud_en_lineas and essalud > 0:
        lineas_aportes.append({"nombre": "EsSalud", "monto": essalud,
                                "monto_str": _monto(essalud), "obs": ""})
        total_aportes += essalud

    neto = registro.neto_a_pagar or Decimal("0")

    # Datos trabajador
    personal = registro.personal
    try:
        fi = personal.fecha_ingreso
        fecha_ingreso_str = fi.strftime("%d/%m/%Y") if fi else "—"
    except Exception: fecha_ingreso_str = "—"
    try:
        ff = personal.fecha_fin_contrato
        fecha_fin_str = ff.strftime("%d/%m/%Y") if ff else "Indefinido"
    except Exception: fecha_fin_str = "S/D"
    try:
        dias_periodo = registro.periodo.fecha_fin.day if registro.periodo.fecha_fin else 30
    except Exception: dias_periodo = 30
    try: banco_nombre = personal.banco or ""
    except Exception: banco_nombre = ""
    try: cuenta_cci = personal.cuenta_cci or ""
    except Exception: cuenta_cci = ""
    try: cuspp = personal.cuspp or ""
    except Exception: cuspp = ""
    try: area_nombre = personal.subarea.area.nombre if personal.subarea else "S/D"
    except Exception: area_nombre = "S/D"
    try:
        regimen_str = personal.get_regimen_pension_display()
        if personal.afp: regimen_str += f" - {personal.afp}"
    except Exception: regimen_str = str(getattr(personal, "regimen_pension", "") or "")
    try: cargo_str = personal.cargo or "S/D"
    except Exception: cargo_str = "S/D"
    try: grupo = personal.grupo_tareo or ""
    except Exception: grupo = ""
    try:
        periodo      = registro.periodo
        mes_nombre   = periodo.mes_nombre
        anio         = str(periodo.anio)
        tipo_display = periodo.get_tipo_display()
    except Exception: mes_nombre = ""; anio = ""; tipo_display = ""

    empresa_nombre = "Empresa"; empresa_ruc = ""; empresa_dir = ""
    # Prioridad 1: empresa del trabajador (multi-tenant)
    emp = getattr(registro.personal, 'empresa', None)
    if emp is not None:
        empresa_nombre = (getattr(emp, 'razon_social', None) or
                          getattr(emp, 'nombre_comercial', None) or
                          empresa_nombre)
        empresa_ruc    = getattr(emp, 'ruc', '') or ''
        empresa_dir    = getattr(emp, 'direccion', '') or ''
    # Prioridad 2: ConfiguracionSistema global (fallback si Personal no tiene empresa)
    if empresa_nombre == "Empresa":
        try:
            from core.context_processors import _get_config
            cfg = _get_config()
            if cfg:
                empresa_nombre = cfg.empresa_nombre or "Empresa"
                empresa_ruc    = empresa_ruc or (cfg.empresa_ruc or "")
                empresa_dir    = empresa_dir or (getattr(cfg, "empresa_direccion", "") or "")
        except Exception as exc:
            logger.warning('Error loading empresa config for boleta PDF: %s', exc)

    he_parts = []
    if registro.horas_extra_25:  he_parts.append(f"25%: {registro.horas_extra_25}h")
    if registro.horas_extra_35:  he_parts.append(f"35%: {registro.horas_extra_35}h")
    if registro.horas_extra_100: he_parts.append(f"100%: {registro.horas_extra_100}h")
    he_str = "  ".join(he_parts) if he_parts else "—"

    dias_str = f"{registro.dias_trabajados} / {dias_periodo}"
    if registro.dias_falta and registro.dias_falta > 0:
        plural = "s" if registro.dias_falta != 1 else ""
        dias_str += f"  ({registro.dias_falta} falta{plural})"

    # Token de verificación pública y hash de integridad
    token = generar_token_verificacion(registro)
    hash_int = calcular_hash_integridad(registro)
    # Persistir hash_integridad si cambió y el campo existe.
    try:
        if hash_int and hasattr(registro, "hash_integridad") and registro.hash_integridad != hash_int:
            registro.hash_integridad = hash_int
            registro.save(update_fields=["hash_integridad"])
    except Exception as exc:
        logger.warning("No se pudo persistir hash_integridad: %s", exc)

    base_url = getattr(settings, "BOLETA_VERIFY_BASE_URL", "https://harmoni.pe")
    verify_url = f"{base_url.rstrip('/')}/nominas/verificar/{token}/" if token else ""

    # PDF setup
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    story = []

    def make_col(lineas, titulo, total_str, col_w, target_rows=None):
        """
        Tabla de 2 columnas (descripción | monto). Estilo S10:
        - Header con fondo gris claro y borde
        - Filas con borde inferior fino
        - Fila TOTAL con borde superior

        Args:
            target_rows: número objetivo de filas de datos (sin header ni TOTAL).
                         Si es None usa min_rows=4. Si se pasa, rellena con
                         filas vacías hasta alcanzar target_rows — útil para
                         que 3 columnas terminen a la misma altura.
        """
        nw = col_w * 0.66
        aw = col_w * 0.34
        # Header
        rows = [[_p(titulo, ct_hdr), _p("Monto (S/)", ct_sub)]]
        if lineas:
            for l in lineas:
                rows.append([_p(l["nombre"], ct_nm), _p(l["monto_str"], ct_amt)])
        # Rellena con filas vacías para que las 3 columnas tengan misma altura
        objetivo = target_rows if target_rows is not None else 4
        while len(rows) - 1 < objetivo:
            rows.append([_p("", ct_nm), _p("", ct_amt)])
        # TOTAL
        rows.append([_p("TOTAL", ct_sub_l), _p(total_str, ct_sub_r)])
        n = len(rows)
        cmds = [
            # Borde exterior de la tabla
            ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
            # Header
            ("BACKGROUND",    (0,0),(-1,0),   C_HEADER_BG),
            ("LINEBELOW",     (0,0),(-1,0),   0.5, C_BORDER),
            ("TOPPADDING",    (0,0),(-1,0),   4),
            ("BOTTOMPADDING", (0,0),(-1,0),   4),
            ("LEFTPADDING",   (0,0),(-1,0),   5),
            ("RIGHTPADDING",  (0,0),(-1,0),   5),
            # Filas
            ("TOPPADDING",    (0,1),(-1,-2),  2),
            ("BOTTOMPADDING", (0,1),(-1,-2),  2),
            ("LEFTPADDING",   (0,1),(-1,-2),  5),
            ("RIGHTPADDING",  (0,1),(-1,-2),  5),
            # TOTAL
            ("LINEABOVE",     (0,-1),(-1,-1), 0.5, C_BORDER),
            ("TOPPADDING",    (0,-1),(-1,-1), 3),
            ("BOTTOMPADDING", (0,-1),(-1,-1), 3),
            ("LEFTPADDING",   (0,-1),(-1,-1), 5),
            ("RIGHTPADDING",  (0,-1),(-1,-1), 5),
            ("VALIGN",        (0,0),(-1,-1),  "TOP"),
            # Línea vertical separadora
            ("LINEAFTER",     (0,0),(0,-1),   0.3, C_LINE_S),
        ]
        # rowHeights uniformes para filas de datos (no header ni TOTAL):
        # garantiza que las 3 columnas terminen a la misma altura aunque
        # un concepto haga wrap a 2 líneas (ej. "AFP — Aporte Obligatorio 10%").
        # Altura suficiente para 2 líneas de texto a 8pt + padding.
        DATA_ROW_HEIGHT = 22  # puntos — cubre wrap de 2 líneas cómodamente
        n = len(rows)
        rh = [None]  # header altura natural
        rh += [DATA_ROW_HEIGHT] * (n - 2)  # filas de datos uniformes
        rh.append(None)  # TOTAL altura natural
        t = Table(rows, colWidths=[nw, aw], rowHeights=rh)
        t.setStyle(TableStyle(cmds))
        return t

    # Logo Harmoni (brand pack oficial) — solo elemento a color
    # Preferimos harmoni-mark-256 (transparent, 256x256) que se renderiza nítido
    # a cualquier tamaño en ReportLab. Fallback al legacy logo-mark-120 por compat.
    logo_path = None
    try:
        import os
        for candidate in [
            os.path.join(settings.BASE_DIR, 'static', 'images', 'brand', 'png', 'harmoni-mark-256.png'),
            os.path.join(settings.BASE_DIR, 'static', 'images', 'logo-mark-120.png'),
        ]:
            if os.path.exists(candidate):
                logo_path = candidate
                break
    except Exception:
        logo_path = None

    # ════════════════════════════════════════════════════════════════
    # HEADER — formato S10 sobrio
    # ════════════════════════════════════════════════════════════════
    # Línea 1: [logo] EMPRESA + dirección  |  Boleta de Pago + período
    info_box = [_p(empresa_nombre, h_emp)]
    if empresa_ruc: info_box.append(_p(f"RUC: {empresa_ruc}", h_meta))
    if empresa_dir: info_box.append(_p(empresa_dir, h_meta))

    if logo_path:
        try:
            logo_img = RLImage(logo_path, width=14*mm, height=14*mm)
            logo_img.hAlign = 'LEFT'
            hl = Table([[logo_img, info_box]], colWidths=[16*mm, USABLE_W*0.58 - 16*mm])
            hl.setStyle(TableStyle([
                ("VALIGN",       (0,0),(-1,-1), "MIDDLE"),
                ("LEFTPADDING",  (0,0),(-1,-1), 0),
                ("RIGHTPADDING", (0,0),(-1,-1), 4),
                ("TOPPADDING",   (0,0),(-1,-1), 0),
                ("BOTTOMPADDING",(0,0),(-1,-1), 0),
            ]))
        except Exception as exc:
            logger.warning('No se pudo cargar logo en boleta PDF: %s', exc)
            hl = info_box
    else:
        hl = info_box

    hr_list = [
        _p("Boleta de Pago", h_tit),
        _p(f"{mes_nombre} {anio}  ·  {tipo_display}", h_per),
        _p(f"Del {registro.periodo.fecha_inicio.strftime('%d/%m/%Y')} al {registro.periodo.fecha_fin.strftime('%d/%m/%Y')}", h_per),
    ]
    ht = Table([[hl, hr_list]], colWidths=[USABLE_W*0.58, USABLE_W*0.42])
    ht.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
        ("LINEBELOW",     (0,0),(-1,-1), 1, C_BORDER),
    ]))
    story.append(ht)

    # ════════════════════════════════════════════════════════════════
    # DATOS TRABAJADOR — formato S10 tipo formulario
    # ════════════════════════════════════════════════════════════════
    fecha_nac_str = "—"
    try:
        fn = personal.fecha_nacimiento
        fecha_nac_str = fn.strftime("%d/%m/%Y") if fn else "—"
    except Exception: pass

    # Modalidad de contrato (DS 001-98-TR Art. 19 inc. e)
    modalidad_str = "Plazo Indeterminado"
    try:
        if personal.tipo_contrato:
            modalidad_str = personal.get_tipo_contrato_display()
            # Si tiene fecha de fin definida, agregar vigencia
            if personal.fecha_fin_contrato:
                modalidad_str += f" (hasta {personal.fecha_fin_contrato.strftime('%d/%m/%Y')})"
    except Exception:
        pass

    # Filas tipo formulario: [label, value, label, value, label, value]
    cat_str = "Empleado"
    try:
        if hasattr(personal, 'get_tipo_trab_display'):
            cat_str = personal.get_tipo_trab_display() or "Empleado"
        elif personal.tipo_trab:
            cat_str = personal.tipo_trab
    except Exception:
        pass

    cta_bancaria = "—"
    if banco_nombre and cuenta_cci:
        cta_bancaria = f"{banco_nombre} — {_truncate(cuenta_cci, 22)}"
    elif banco_nombre:
        cta_bancaria = banco_nombre
    elif cuenta_cci:
        cta_bancaria = _truncate(cuenta_cci, 30)

    dd = [
        [_p("DNI", lbl), _p(str(personal.nro_doc), val),
         _p("Nombre", lbl), _p(str(personal.apellidos_nombres), val),
         _p("F.Ing.", lbl), _p(fecha_ingreso_str, val)],
        [_p("Código", lbl), _p(str(personal.nro_doc), val),
         _p("Ocupación", lbl), _p(cargo_str, val),
         _p("Modalidad", lbl), _p(modalidad_str, val)],
        [_p("F.Nac.", lbl), _p(fecha_nac_str, val),
         _p("Categoría", lbl), _p(cat_str, val),
         _p("Grupo", lbl), _p(grupo or "—", val)],
        [_p("Afiliación", lbl), _p(regimen_str, val),
         _p("CUSPP", lbl), _p(cuspp or "—", val),
         _p("Sueldo Base", lbl), _p(f"S/ {_monto(registro.sueldo_base)}", val)],
        [_p("Régimen Salud", lbl), _p("ESSALUD", val),
         _p("Cuenta Bancaria", lbl), _p(cta_bancaria, val),
         _p("Días Trab.", lbl), _p(dias_str, val)],
    ]
    dt = Table(dd, colWidths=[
        USABLE_W * 0.10, USABLE_W * 0.17,
        USABLE_W * 0.11, USABLE_W * 0.32,
        USABLE_W * 0.08, USABLE_W * 0.22,
    ])
    dt.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 0.5, C_BORDER),
        ("INNERGRID",     (0,0),(-1,-1), 0.3, C_LINE_S),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))
    story.append(dt)
    story.append(Spacer(1, 6))

    # ════════════════════════════════════════════════════════════════
    # 3 COLUMNAS — Remuneraciones | Descuentos | Aportaciones
    # UNA sola tabla con 6 columnas (3 pares concepto/monto) en lugar de
    # 3 tablas separadas. Garantiza que el TOTAL de las 3 termine en la
    # MISMA fila (misma altura visual) aunque un concepto haga wrap a
    # 2 líneas — todas las celdas de la misma fila comparten altura.
    # ════════════════════════════════════════════════════════════════
    col_w = USABLE_W / 3
    nw = col_w * 0.66  # ancho columna nombre
    aw = col_w * 0.34  # ancho columna monto

    max_filas = max(
        len(lineas_ingresos),
        len(lineas_descuentos),
        len(lineas_aportes),
        4,  # mínimo razonable para presencia visual
    )

    # Header row con 3 títulos
    grid_rows = [[
        _p("Remuneraciones", ct_hdr), _p("Monto (S/)", ct_sub),
        _p("Descuentos del trabajador", ct_hdr), _p("Monto (S/)", ct_sub),
        _p("Aportaciones del empleador", ct_hdr), _p("Monto (S/)", ct_sub),
    ]]

    # Filas de datos: cada fila tiene 6 celdas (2 por columna conceptual)
    def _get(lineas, i):
        """Devuelve (nombre, monto_str) o ('', '') si no hay item en ese index."""
        if i < len(lineas):
            return lineas[i]["nombre"], lineas[i]["monto_str"]
        return "", ""

    for i in range(max_filas):
        n_ing, m_ing = _get(lineas_ingresos, i)
        n_desc, m_desc = _get(lineas_descuentos, i)
        n_apo, m_apo = _get(lineas_aportes, i)
        grid_rows.append([
            _p(n_ing, ct_nm),  _p(m_ing, ct_amt),
            _p(n_desc, ct_nm), _p(m_desc, ct_amt),
            _p(n_apo, ct_nm),  _p(m_apo, ct_amt),
        ])

    # Fila TOTAL: las 3 columnas mostrarán TOTAL en la MISMA fila
    grid_rows.append([
        _p("TOTAL", ct_sub_l), _p(_monto(total_ingresos), ct_sub_r),
        _p("TOTAL", ct_sub_l), _p(_monto(total_descuentos), ct_sub_r),
        _p("TOTAL", ct_sub_l), _p(_monto(total_aportes), ct_sub_r),
    ])

    n_rows = len(grid_rows)
    grid = Table(
        grid_rows,
        colWidths=[nw, aw, nw, aw, nw, aw],
    )
    grid.setStyle(TableStyle([
        # Header: fondo gris, línea inferior
        ("BACKGROUND",    (0, 0), (-1, 0), C_HEADER_BG),
        ("LINEBELOW",     (0, 0), (-1, 0), 0.5, C_BORDER),
        ("TOPPADDING",    (0, 0), (-1, 0), 4),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        # Filas de datos
        ("TOPPADDING",    (0, 1), (-1, -2), 2),
        ("BOTTOMPADDING", (0, 1), (-1, -2), 2),
        # Fila TOTAL: línea superior
        ("LINEABOVE",     (0, -1), (-1, -1), 0.5, C_BORDER),
        ("TOPPADDING",    (0, -1), (-1, -1), 3),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 3),
        # Padding lateral uniforme
        ("LEFTPADDING",   (0, 0), (-1, -1), 5),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        # Borde exterior
        ("BOX",           (0, 0), (-1, -1), 0.5, C_BORDER),
        # Líneas verticales separadoras entre las 3 columnas conceptuales
        ("LINEAFTER",     (1, 0), (1, -1), 0.5, C_BORDER),
        ("LINEAFTER",     (3, 0), (3, -1), 0.5, C_BORDER),
    ]))
    story.append(grid)
    story.append(Spacer(1, 8))

    # ════════════════════════════════════════════════════════════════
    # NETO A PAGAR — sobrio, sin fondo coloreado
    # ════════════════════════════════════════════════════════════════
    nd = [[
        _p("NETO A PAGAR", net_lbl),
        _p(f"S/ {_monto(neto)}", net_val),
    ]]
    nt = Table(nd, colWidths=[USABLE_W*0.62, USABLE_W*0.38])
    nt.setStyle(TableStyle([
        ("BOX",           (0,0),(-1,-1), 1, C_BORDER),
        ("BACKGROUND",    (0,0),(-1,-1), C_HEADER_BG),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("LEFTPADDING",   (0,0),(-1,-1), 10),
        ("RIGHTPADDING",  (0,0),(-1,-1), 10),
        ("TOPPADDING",    (0,0),(-1,-1), 6),
        ("BOTTOMPADDING", (0,0),(-1,-1), 6),
    ]))
    story.append(nt)
    story.append(Spacer(1, 6))

    # ════════════════════════════════════════════════════════════════
    # BASE DE CÁLCULO + LEYENDA NO REMUNERATIVO (DS 001-98-TR Art. 19)
    # ════════════════════════════════════════════════════════════════
    base_lines = [
        f"Remuneración computable del mes (base aportes y CTS): S/ {_monto(remuneracion_computable)}"
    ]
    if hay_no_remun:
        base_lines.append(
            "(*) Concepto NO remunerativo. No forma parte de la base de cálculo "
            "para aportes ni beneficios sociales (Art. 7 D.S. 003-97-TR)."
        )
    base_st = sty("base_st", fontSize=7, textColor=C_MUTED, leading=9)
    base_tbl = Table(
        [[_p(line, base_st)] for line in base_lines],
        colWidths=[USABLE_W],
    )
    base_tbl.setStyle(TableStyle([
        ("LEFTPADDING",   (0,0),(-1,-1), 2),
        ("RIGHTPADDING",  (0,0),(-1,-1), 2),
        ("TOPPADDING",    (0,0),(-1,-1), 1),
        ("BOTTOMPADDING", (0,0),(-1,-1), 1),
    ]))
    story.append(base_tbl)
    story.append(Spacer(1, 10))

    # ════════════════════════════════════════════════════════════════
    # FIRMAS — Empleador (izq) y Trabajador (der)
    # Para que ambos labels queden alineados verticalmente con la línea,
    # uso dos líneas debajo de cada uno (incluyendo línea vacía si solo
    # hay un label de un lado).
    # ════════════════════════════════════════════════════════════════
    # Estilo dedicado: alineación CENTER ambos lados
    sig_line_st = sty("sig_l",  fontSize=8, textColor=C_LBL, alignment=TA_CENTER)
    sig_lbl_st  = sty("sig_lbl", fontSize=7.5, fontName="Helvetica-Bold", textColor=C_LBL, alignment=TA_CENTER)
    sig_sub_st  = sty("sig_sub", fontSize=7, textColor=C_MUTED, alignment=TA_CENTER)

    # Cada celda contiene: [línea de firma] [label principal] [sub-label opcional]
    sig_emp = [
        _p("_" * 38, sig_line_st),
        _p("Empleador / RRHH", sig_lbl_st),
    ]
    sig_trab = [
        _p("_" * 38, sig_line_st),
        _p("Recibí conforme", sig_lbl_st),
        _p(f"Trabajador — {personal.nro_doc}", sig_sub_st),
    ]
    # Espacio arriba para la firma manual
    fdata = [
        [_p("", sm), _p("", sm)],   # espacio para escribir firma
        [sig_emp, sig_trab],
    ]
    ftt = Table(fdata, colWidths=[USABLE_W*0.5, USABLE_W*0.5], rowHeights=[28, None])
    ftt.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("TOPPADDING",    (0,0),(-1,-1), 0),
        ("BOTTOMPADDING", (0,0),(-1,-1), 0),
    ]))
    story.append(ftt)
    story.append(Spacer(1, 8))

    # ════════════════════════════════════════════════════════════════
    # FOOTER — leyenda legal + hash + QR (discretos)
    # ════════════════════════════════════════════════════════════════
    try: estado_display = registro.get_estado_display()
    except Exception: estado_display = str(getattr(registro, "estado", ""))

    story.append(HRFlowable(width="100%", color=C_LINE_S, thickness=0.3))
    story.append(Spacer(1, 3))

    qr_img = _build_qr_image(verify_url, size_mm=18) if verify_url else None
    legal_txt = (
        "Recibir y firmar la presente boleta no implica renuncia al derecho de "
        "reclamar los pagos que el trabajador considere le corresponden (DS 009-2011-TR)."
    )
    meta_lines = [
        _p(legal_txt, ft_legal),
        _p(
            f"Boleta digital — {mes_nombre} {anio} · "
            f"Estado: {estado_display} · Documento electrónico generado por Harmoni ERP",
            ft_note),
    ]
    if hash_int:
        meta_lines.append(_p(f"Hash integridad: {hash_int}", ft_hash))
    if token:
        meta_lines.append(_p(f"Verificación: {base_url.rstrip('/')}/nominas/verificar/{token}/", ft_hash))

    if qr_img is not None:
        qr_w = 22 * mm
        ft_block = Table([[meta_lines, [qr_img]]],
                          colWidths=[USABLE_W - qr_w, qr_w])
        ft_block.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("ALIGN",         (1,0),(1,0),   "RIGHT"),
            ("LEFTPADDING",   (0,0),(-1,-1), 2),
            ("RIGHTPADDING",  (0,0),(-1,-1), 2),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ]))
        story.append(ft_block)
    else:
        for line in meta_lines:
            story.append(line)

    doc.build(story)
    return buf.getvalue()
