"""
Nominas - Generador de Boletas de Pago PDF.

Usa ReportLab (dep de xhtml2pdf). Migrado desde xhtml2pdf para evitar
el bug TypeError NoneType>NoneType (negative availWidth en tablas anidadas).
"""
import io
import logging
from decimal import Decimal

logger = logging.getLogger('nominas.pdf')

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER


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


def generar_boleta_pdf(registro):
    """Genera la boleta de pago PDF para RegistroNomina. Returns bytes."""
    PAGE_W, PAGE_H = A4
    MARGIN   = 12 * mm
    USABLE_W = PAGE_W - 2 * MARGIN

    def sty(name, **kw):
        d = dict(fontName="Helvetica", fontSize=8, leading=10, textColor=C_BLACK)
        d.update(kw)
        return ParagraphStyle(name, **d)

    base     = sty("base")
    bold     = sty("bold",    fontName="Helvetica-Bold")
    sm       = sty("sm",      fontSize=7, textColor=C_GRAY_B)
    smr      = sty("smr",     fontSize=7, textColor=C_GRAY_B, alignment=TA_RIGHT)
    lbl      = sty("lbl",     fontSize=7.5, fontName="Helvetica-Bold", textColor=C_GRAY_B)
    val      = sty("val",     fontSize=8.5)
    h_emp    = sty("h_emp",   fontSize=13, fontName="Helvetica-Bold", textColor=C_WHITE, leading=16)
    h_ruc    = sty("h_ruc",   fontSize=8, textColor=C_GREEN_L)
    h_dir    = sty("h_dir",   fontSize=7.5, textColor=C_GREEN_E)
    h_tit    = sty("h_tit",   fontSize=11, fontName="Helvetica-Bold", textColor=C_ACCENT, alignment=TA_RIGHT)
    h_per    = sty("h_per",   fontSize=8, textColor=C_GREEN_L, alignment=TA_RIGHT)
    h_cop    = sty("h_cop",   fontSize=7, textColor=C_GREEN_E, alignment=TA_RIGHT)
    ct_hdr   = sty("ct_hdr",  fontSize=7.5, fontName="Helvetica-Bold", textColor=C_WHITE)
    ct_hdr_r = sty("ct_hr",   fontSize=7.5, fontName="Helvetica-Bold", textColor=C_WHITE, alignment=TA_RIGHT)
    ct_nm    = sty("ct_nm",   fontSize=8)
    ct_obs   = sty("ct_obs",  fontSize=7, textColor=C_GRAY_B)
    ct_amt   = sty("ct_amt",  fontName="Courier", fontSize=8, alignment=TA_RIGHT)
    ct_sub   = sty("ct_sub",  fontName="Helvetica-Bold", fontSize=8)
    ct_sub_r = sty("ct_sr",   fontName="Courier-Bold", fontSize=8, alignment=TA_RIGHT)
    net_lbl  = sty("net_lbl", fontSize=9.5, fontName="Helvetica-Bold", textColor=C_GREEN_L)
    net_fml  = sty("net_fml", fontSize=7.5, textColor=C_GREEN_E, alignment=TA_RIGHT)
    net_val  = sty("net_val", fontName="Courier-Bold", fontSize=15, alignment=TA_RIGHT, textColor=C_WHITE)
    ft_note  = sty("ft_note", fontSize=7, textColor=C_GRAY_T, alignment=TA_CENTER)
    cut_st   = sty("cut_st",  fontSize=6.5, textColor=C_GRAY_T, alignment=TA_CENTER)
    badge_s  = sty("badge_s", fontSize=7, fontName="Helvetica-Bold", textColor=C_ACCENT)
    badge_r  = sty("badge_r", fontSize=7, fontName="Helvetica-Bold", textColor=C_PURP_L)
    tv_ing   = sty("tv_ing",  fontName="Courier-Bold", fontSize=11, alignment=TA_CENTER, textColor=C_GREEN_B)
    tv_desc  = sty("tv_desc", fontName="Courier-Bold", fontSize=11, alignment=TA_CENTER, textColor=C_RED_B)
    tv_ap    = sty("tv_ap",   fontName="Courier-Bold", fontSize=11, alignment=TA_CENTER, textColor=C_BLUE_B)
    tot_lbl  = sty("tot_lbl", fontSize=7, fontName="Helvetica-Bold", alignment=TA_CENTER, textColor=C_BLACK)
    costo_st = sty("costo",   fontSize=7.5, textColor=colors.HexColor("#166534"))
    pago_st  = sty("pago",    fontSize=7.5)
    fl_st    = sty("fl",      fontSize=7.5, textColor=C_GRAY_B)
    fr_st    = sty("fr",      fontSize=7.5, textColor=C_GRAY_B, alignment=TA_RIGHT)

    # Clasificar lineas
    lineas_ingresos   = []
    lineas_descuentos = []
    lineas_aportes    = []
    total_ingresos    = Decimal("0")
    total_descuentos  = Decimal("0")
    total_aportes     = Decimal("0")

    for linea in registro.lineas.select_related("concepto").order_by(
            "concepto__tipo", "concepto__orden"):
        entry = {"nombre": linea.concepto.nombre,
                 "monto": linea.monto or Decimal("0"),
                 "monto_str": _monto(linea.monto),
                 "obs": linea.observacion or ""}
        if linea.concepto.tipo == "INGRESO":
            lineas_ingresos.append(entry)
            total_ingresos += linea.monto or Decimal("0")
        elif linea.concepto.tipo == "DESCUENTO":
            lineas_descuentos.append(entry)
            total_descuentos += linea.monto or Decimal("0")
        else:
            lineas_aportes.append(entry)
            total_aportes += linea.monto or Decimal("0")

    essalud = registro.aporte_essalud or Decimal("0")
    essalud_en_lineas = any(
        "essalud" in l["nombre"].lower() or "seguro" in l["nombre"].lower()
        for l in lineas_aportes)
    if not essalud_en_lineas and essalud > 0:
        lineas_aportes.append({"nombre": "EsSalud (9%)", "monto": essalud,
                                "monto_str": _monto(essalud), "obs": "Aporte empleador"})
        total_aportes += essalud

    neto = registro.neto_a_pagar or Decimal("0")

    # Datos trabajador
    personal = registro.personal
    try:
        fi = personal.fecha_ingreso
        fecha_ingreso_str = fi.strftime("%d/%m/%Y") if fi else "S/D"
    except Exception: fecha_ingreso_str = "S/D"
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
    try:
        from core.context_processors import _get_config
        cfg = _get_config()
        if cfg:
            empresa_nombre = cfg.empresa_nombre or "Empresa"
            empresa_ruc    = cfg.empresa_ruc    or ""
            empresa_dir    = getattr(cfg, "empresa_direccion", "") or ""
    except Exception as exc:
        logger.warning('Error loading empresa config for boleta PDF: %s', exc)

    he_parts = []
    if registro.horas_extra_25:  he_parts.append(f"25%: {registro.horas_extra_25}h")
    if registro.horas_extra_35:  he_parts.append(f"35%: {registro.horas_extra_35}h")
    if registro.horas_extra_100: he_parts.append(f"100%: {registro.horas_extra_100}h")
    he_str = "  ".join(he_parts) if he_parts else "S/D"

    dias_str = f"{registro.dias_trabajados} / {dias_periodo}"
    if registro.dias_falta and registro.dias_falta > 0:
        plural = "s" if registro.dias_falta != 1 else ""
        dias_str += f"  ({registro.dias_falta} falta{plural})"

    # PDF setup
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN)
    story = []

    def make_col(lineas, titulo, hdr_color, sub_bg, sub_border, total_str, col_w):
        """Build a 2-col concept table (name | amount)."""
        nw = col_w * 0.67
        aw = col_w * 0.33
        rows = [[_p(titulo, ct_hdr), _p("S/", ct_hdr_r)]]
        if lineas:
            for l in lineas:
                rows.append([_p(l["nombre"], ct_nm), _p(l["monto_str"], ct_amt)])
        else:
            rows.append([_p("---", ct_obs), _p("", ct_amt)])
        rows.append([_p("TOTAL", ct_sub), _p(total_str, ct_sub_r)])
        n = len(rows)
        cmds = [
            ("BACKGROUND",    (0,0),(-1,0),   hdr_color),
            ("TOPPADDING",    (0,0),(-1,0),   4),
            ("BOTTOMPADDING", (0,0),(-1,0),   4),
            ("LEFTPADDING",   (0,0),(-1,0),   7),
            ("RIGHTPADDING",  (0,0),(-1,0),   7),
            ("TOPPADDING",    (0,1),(-1,-2),  2),
            ("BOTTOMPADDING", (0,1),(-1,-2),  2),
            ("LEFTPADDING",   (0,1),(-1,-2),  7),
            ("RIGHTPADDING",  (0,1),(-1,-2),  7),
            ("LINEBELOW",     (0,1),(-1,-2),  0.5, colors.HexColor("#f3f4f6")),
            ("BACKGROUND",    (0,-1),(-1,-1), sub_bg),
            ("LINEABOVE",     (0,-1),(-1,-1), 0.5, sub_border),
            ("TOPPADDING",    (0,-1),(-1,-1), 3),
            ("BOTTOMPADDING", (0,-1),(-1,-1), 3),
            ("LEFTPADDING",   (0,-1),(-1,-1), 7),
            ("RIGHTPADDING",  (0,-1),(-1,-1), 7),
            ("VALIGN",        (0,0),(-1,-1),  "TOP"),
        ]
        for i in range(2, n-1, 2):
            cmds.append(("BACKGROUND", (0,i),(-1,i), colors.HexColor("#fafafa")))
        t = Table(rows, colWidths=[nw, aw])
        t.setStyle(TableStyle(cmds))
        return t

    for copia_idx in range(2):
        clabel = "EMPLEADOR" if copia_idx == 0 else "TRABAJADOR"

        # --- HEADER ---
        hl = [_p(empresa_nombre, h_emp)]
        if empresa_ruc: hl.append(_p(f"RUC: {empresa_ruc}", h_ruc))
        if empresa_dir: hl.append(_p(empresa_dir, h_dir))
        hr_list = [_p("Boleta de Pago", h_tit),
                   _p(f"{mes_nombre} {anio}  -  {tipo_display}", h_per),
                   _p(f"Copia: {clabel}", h_cop)]
        ht = Table([[hl, hr_list]], colWidths=[USABLE_W*0.62, USABLE_W*0.38])
        ht.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_DARK),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0),(-1,-1), 10),
            ("RIGHTPADDING",  (0,0),(-1,-1), 10),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ]))
        story.append(ht)
        story.append(Spacer(1, 4))

        # --- DATOS TRABAJADOR ---
        if grupo == "STAFF":   gc = _p("STAFF", badge_s)
        elif grupo == "RCO":   gc = _p("RCO", badge_r)
        else:                   gc = _p(str(grupo), val)
        dd = [
            [_p("Trabajador:",lbl), _p(str(personal.apellidos_nombres),bold),
             _p("DNI/CE:",lbl), _p(str(personal.nro_doc),val),
             _p("Grupo:",lbl), gc],
            [_p("Cargo:",lbl), _p(cargo_str,val),
             _p("Area:",lbl), _p(area_nombre,val),
             _p("Sueldo Base:",lbl), _p(f"S/ {_monto(registro.sueldo_base)}",bold)],
            [_p("Regimen:",lbl), _p(regimen_str,val),
             _p("CUSPP:",lbl), _p(cuspp or "S/D",val),
             _p("Ingreso:",lbl), _p(fecha_ingreso_str,val)],
            [_p("Dias Trab.:",lbl), _p(dias_str,val),
             _p("HE:",lbl), _p(he_str,val),
             _p("Contrato:",lbl), _p(fecha_fin_str,val)],
        ]
        dt = Table(dd, colWidths=[95, 145, 52, 85, 60, 90])
        dt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_GRAY_L),
            ("BOX",           (0,0),(-1,-1), 0.5, C_GRAY_E),
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0),(-1,-1), 4),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
            ("TOPPADDING",    (0,0),(-1,-1), 2),
            ("BOTTOMPADDING", (0,0),(-1,-1), 2),
        ]))
        story.append(dt)
        story.append(Spacer(1, 5))

        # --- 3 COLUMNAS ---
        gap = 4
        ciw = int(USABLE_W * 0.36) - gap
        cdw = int(USABLE_W * 0.34) - gap
        caw = int(USABLE_W - ciw - cdw - gap * 2)
        ci = make_col(lineas_ingresos,   "Remuneraciones",   C_TEAL,
                      C_SUBTOT, C_SUBTOT2, _monto(total_ingresos),   ciw)
        cd = make_col(lineas_descuentos, "Descuentos",        C_RED_H,
                      C_RED_L,  C_RED_E,   _monto(total_descuentos), cdw)
        ca = make_col(lineas_aportes,    "Aportes Empleador", C_BLUE_H,
                      C_BLUE_L, C_BLUE_E,  _monto(total_aportes),    caw)
        tc = Table([[ci, cd, ca]], colWidths=[ciw+gap, cdw+gap, caw])
        tc.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING",   (0,0),(-1,-1), 0),
            ("RIGHTPADDING",  (0,0),(0,0),   gap),
            ("RIGHTPADDING",  (1,0),(1,0),   gap),
            ("RIGHTPADDING",  (2,0),(2,0),   0),
            ("TOPPADDING",    (0,0),(-1,-1), 0),
            ("BOTTOMPADDING", (0,0),(-1,-1), 0),
        ]))
        story.append(tc)
        story.append(Spacer(1, 5))

        # --- BARRA TOTALES ---
        tw = USABLE_W / 3
        tdata = [[
            [_p("TOTAL INGRESOS", tot_lbl),   _p(f"S/ {_monto(total_ingresos)}",   tv_ing)],
            [_p("TOTAL DESCUENTOS", tot_lbl), _p(f"S/ {_monto(total_descuentos)}", tv_desc)],
            [_p("APORTES EMPLEADOR",tot_lbl), _p(f"S/ {_monto(total_aportes)}",    tv_ap)],
        ]]
        tt = Table(tdata, colWidths=[tw, tw, tw])
        tt.setStyle(TableStyle([
            ("BACKGROUND", (0,0),(0,0), C_GREEN_S), ("BOX",(0,0),(0,0),0.5,C_GREEN_E),
            ("BACKGROUND", (1,0),(1,0), C_RED_L),   ("BOX",(1,0),(1,0),0.5,C_RED_E),
            ("BACKGROUND", (2,0),(2,0), C_BLUE_L),  ("BOX",(2,0),(2,0),0.5,C_BLUE_E),
            ("ALIGN",         (0,0),(-1,-1), "CENTER"),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("TOPPADDING",    (0,0),(-1,-1), 6),
            ("BOTTOMPADDING", (0,0),(-1,-1), 6),
            ("LEFTPADDING",   (0,0),(-1,-1), 3),
            ("RIGHTPADDING",  (0,0),(-1,-1), 3),
        ]))
        story.append(tt)
        story.append(Spacer(1, 5))

        # --- NETO A PAGAR ---
        nf = f"{_monto(total_ingresos)} - {_monto(total_descuentos)}"
        nd = [[_p("NETO A PAGAR", net_lbl), _p(nf, net_fml), _p(f"S/ {_monto(neto)}", net_val)]]
        nt = Table(nd, colWidths=[USABLE_W*0.32, USABLE_W*0.33, USABLE_W*0.35])
        nt.setStyle(TableStyle([
            ("BACKGROUND",    (0,0),(-1,-1), C_DARK),
            ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
            ("LEFTPADDING",   (0,0),(-1,-1), 12),
            ("RIGHTPADDING",  (0,0),(-1,-1), 12),
            ("TOPPADDING",    (0,0),(-1,-1), 8),
            ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ]))
        story.append(nt)
        story.append(Spacer(1, 4))

        # --- COSTO EMPRESA ---
        costo = registro.costo_total_empresa
        if costo and costo > 0:
            ct2 = Table([[_p(
                f"Costo total empresa: S/ {_monto(costo)}  (Remun. + Aportes EsSalud)",
                costo_st)]], colWidths=[USABLE_W])
            ct2.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#f0fdf4")),
                ("BOX",           (0,0),(-1,-1), 0.5, colors.HexColor("#bbf7d0")),
                ("LEFTPADDING",   (0,0),(-1,-1), 10),
                ("RIGHTPADDING",  (0,0),(-1,-1), 10),
                ("TOPPADDING",    (0,0),(-1,-1), 4),
                ("BOTTOMPADDING", (0,0),(-1,-1), 4),
            ]))
            story.append(ct2)
            story.append(Spacer(1, 4))

        # --- BANCO / PAGO ---
        if banco_nombre or cuenta_cci:
            pp = ["Forma de pago: Deposito bancario"]
            if banco_nombre: pp.append(f"Banco: {banco_nombre}")
            if cuenta_cci:   pp.append(f"CCI: {cuenta_cci}")
            pt = Table([[_p("     ".join(pp), pago_st)]], colWidths=[USABLE_W])
            pt.setStyle(TableStyle([
                ("BACKGROUND",    (0,0),(-1,-1), colors.HexColor("#fafafa")),
                ("BOX",           (0,0),(-1,-1), 0.5, C_GRAY_E),
                ("LEFTPADDING",   (0,0),(-1,-1), 10),
                ("RIGHTPADDING",  (0,0),(-1,-1), 10),
                ("TOPPADDING",    (0,0),(-1,-1), 5),
                ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ]))
            story.append(pt)
            story.append(Spacer(1, 8))

        # --- FIRMAS ---
        fdata = [
            [_p("_" * 35, sm), _p("_" * 35, smr)],
            [_p("Firma Empleador / RRHH", fl_st),
             _p(f"Firma Trabajador - {personal.nro_doc}", fr_st)],
        ]
        ft = Table(fdata, colWidths=[USABLE_W*0.5, USABLE_W*0.5])
        ft.setStyle(TableStyle([
            ("VALIGN",        (0,0),(-1,-1), "BOTTOM"),
            ("LEFTPADDING",   (0,0),(-1,-1), 4),
            ("RIGHTPADDING",  (0,0),(-1,-1), 4),
            ("TOPPADDING",    (0,0),(-1,-1), 1),
            ("BOTTOMPADDING", (0,0),(-1,-1), 1),
        ]))
        story.append(ft)
        story.append(Spacer(1, 6))

        # --- FOOTER ---
        try: estado_display = registro.get_estado_display()
        except Exception: estado_display = str(getattr(registro, "estado", ""))
        story.append(HRFlowable(width="100%", color=C_GRAY_E, thickness=0.5, dash=(2,2)))
        story.append(Spacer(1, 2))
        story.append(_p(
            f"Generado por Harmoni ERP - {mes_nombre} {anio} - "
            f"Estado: {estado_display} - Documento informativo. Conserve este comprobante.",
            ft_note))

        # --- SEPARADOR COPIAS ---
        if copia_idx == 0:
            story.append(Spacer(1, 10))
            story.append(HRFlowable(width="100%", color=C_GRAY_T, thickness=0.5, dash=(3,4)))
            story.append(_p("- - - SEPARAR POR LA LINEA PUNTEADA - - -", cut_st))
            story.append(HRFlowable(width="100%", color=C_GRAY_T, thickness=0.5, dash=(3,4)))
            story.append(Spacer(1, 10))

    doc.build(story)
    return buf.getvalue()
