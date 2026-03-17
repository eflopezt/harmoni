"""
Harmoni ERP — Motor de Reportes PDF Ejecutivos.

Generador reutilizable de reportes PDF profesionales con ReportLab.
Cada reporte usa la paleta de colores y branding de Harmoni.
"""
import io
import logging
from datetime import date
from decimal import Decimal

from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
    PageBreak,
)
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT

logger = logging.getLogger('core.report_engine')

# ── Paleta Harmoni ──────────────────────────────────────────────────────────
C_DARK    = colors.HexColor("#0d2b27")
C_TEAL    = colors.HexColor("#0f766e")
C_ACCENT  = colors.HexColor("#5eead4")
C_GREEN_L = colors.HexColor("#a7f3d0")
C_GREEN_S = colors.HexColor("#ecfdf5")
C_GREEN_B = colors.HexColor("#065f46")
C_GRAY_L  = colors.HexColor("#f8fafc")
C_GRAY_B  = colors.HexColor("#4b5563")
C_GRAY_E  = colors.HexColor("#d1d5db")
C_GRAY_T  = colors.HexColor("#9ca3af")
C_BLACK   = colors.HexColor("#1a1a1a")
C_WHITE   = colors.white
C_SUBTOT  = colors.HexColor("#f0f4f8")
C_RED_H   = colors.HexColor("#b91c1c")
C_BLUE_H  = colors.HexColor("#1d4ed8")
C_BLUE_L  = colors.HexColor("#eff6ff")
C_AMBER   = colors.HexColor("#d97706")
C_AMBER_L = colors.HexColor("#fffbeb")


def _fmt(value):
    """Format a numeric value to 2 decimal places."""
    if value is None:
        return "0.00"
    try:
        return f"{Decimal(str(value)):,.2f}"
    except Exception:
        return "0.00"


def _safe_p(text, style):
    """Create a safe Paragraph, escaping HTML entities."""
    if text is None:
        text = ""
    text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, style)


def _load_empresa_info():
    """Load company info from ConfiguracionSistema singleton."""
    nombre = "Empresa"
    ruc = ""
    direccion = ""
    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.get()
        if cfg:
            nombre = cfg.empresa_nombre or "Empresa"
            ruc = cfg.ruc or ""
            direccion = getattr(cfg, "empresa_direccion", "") or ""
    except Exception as exc:
        logger.warning("Error loading empresa config for report: %s", exc)
    return nombre, ruc, direccion


class HarmoniReport:
    """
    Base class for Harmoni PDF reports.

    Usage:
        report = HarmoniReport('Mi Empresa', 'Reporte de Planilla', 'Marzo 2026')
        report.add_header()
        report.add_kpi_row([('Empleados', '150'), ('Masa Salarial', 'S/ 450,000')])
        report.add_table(['Nombre', 'Sueldo'], [['Juan', '3000'], ['Ana', '4000']])
        pdf_bytes = report.generate()
    """

    def __init__(self, empresa=None, titulo='Reporte', subtitulo='',
                 orientation='portrait'):
        if empresa is None:
            self.empresa_nombre, self.empresa_ruc, self.empresa_dir = _load_empresa_info()
        else:
            self.empresa_nombre = empresa
            self.empresa_ruc = ""
            self.empresa_dir = ""

        self.titulo = titulo
        self.subtitulo = subtitulo
        self.orientation = orientation
        self.story = []

        page = A4 if orientation == 'portrait' else landscape(A4)
        self.page_w, self.page_h = page
        self.margin = 14 * mm
        self.usable_w = self.page_w - 2 * self.margin

        # Styles
        self._init_styles()

    def _init_styles(self):
        def sty(name, **kw):
            d = dict(fontName="Helvetica", fontSize=8, leading=10, textColor=C_BLACK)
            d.update(kw)
            return ParagraphStyle(name, **d)

        self.s_base     = sty("rpt_base")
        self.s_bold     = sty("rpt_bold",    fontName="Helvetica-Bold")
        self.s_sm       = sty("rpt_sm",      fontSize=7, textColor=C_GRAY_B)
        self.s_h_emp    = sty("rpt_h_emp",   fontSize=14, fontName="Helvetica-Bold",
                              textColor=C_WHITE, leading=17)
        self.s_h_ruc    = sty("rpt_h_ruc",   fontSize=8, textColor=C_GREEN_L)
        self.s_h_dir    = sty("rpt_h_dir",   fontSize=7.5, textColor=C_ACCENT)
        self.s_h_tit    = sty("rpt_h_tit",   fontSize=12, fontName="Helvetica-Bold",
                              textColor=C_ACCENT, alignment=TA_RIGHT)
        self.s_h_sub    = sty("rpt_h_sub",   fontSize=8.5, textColor=C_GREEN_L,
                              alignment=TA_RIGHT)
        self.s_h_date   = sty("rpt_h_date",  fontSize=7.5, textColor=C_ACCENT,
                              alignment=TA_RIGHT)
        self.s_sect     = sty("rpt_sect",    fontSize=10, fontName="Helvetica-Bold",
                              textColor=C_TEAL, spaceBefore=12, spaceAfter=4)
        self.s_th       = sty("rpt_th",      fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=C_WHITE)
        self.s_th_r     = sty("rpt_th_r",    fontSize=7.5, fontName="Helvetica-Bold",
                              textColor=C_WHITE, alignment=TA_RIGHT)
        self.s_td       = sty("rpt_td",      fontSize=7.5)
        self.s_td_r     = sty("rpt_td_r",    fontSize=7.5, alignment=TA_RIGHT,
                              fontName="Courier")
        self.s_td_c     = sty("rpt_td_c",    fontSize=7.5, alignment=TA_CENTER)
        self.s_td_bold  = sty("rpt_td_b",    fontSize=7.5, fontName="Helvetica-Bold")
        self.s_td_bold_r = sty("rpt_td_br",  fontSize=7.5, fontName="Courier-Bold",
                               alignment=TA_RIGHT)
        self.s_kpi_lbl  = sty("rpt_kpi_lbl", fontSize=7, fontName="Helvetica-Bold",
                              textColor=C_GRAY_B, alignment=TA_CENTER)
        self.s_kpi_val  = sty("rpt_kpi_val", fontSize=14, fontName="Helvetica-Bold",
                              textColor=C_TEAL, alignment=TA_CENTER)
        self.s_footer   = sty("rpt_footer",  fontSize=6.5, textColor=C_GRAY_T,
                              alignment=TA_CENTER)
        self.s_text     = sty("rpt_text",    fontSize=8, leading=12, spaceBefore=4,
                              spaceAfter=4)

    # ── Header ──────────────────────────────────────────────────────────────

    def add_header(self):
        """Add company header with title, subtitle and date."""
        left_parts = [_safe_p(self.empresa_nombre, self.s_h_emp)]
        if self.empresa_ruc:
            left_parts.append(_safe_p(f"RUC: {self.empresa_ruc}", self.s_h_ruc))
        if self.empresa_dir:
            left_parts.append(_safe_p(self.empresa_dir, self.s_h_dir))

        right_parts = [_safe_p(self.titulo, self.s_h_tit)]
        if self.subtitulo:
            right_parts.append(_safe_p(self.subtitulo, self.s_h_sub))
        right_parts.append(_safe_p(
            f"Generado: {date.today().strftime('%d/%m/%Y')}", self.s_h_date))

        ht = Table([[left_parts, right_parts]],
                   colWidths=[self.usable_w * 0.55, self.usable_w * 0.45])
        ht.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), C_DARK),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        self.story.append(ht)
        self.story.append(Spacer(1, 8))

    # ── Section title ───────────────────────────────────────────────────────

    def add_section(self, title):
        """Add a section title."""
        self.story.append(_safe_p(title, self.s_sect))
        self.story.append(HRFlowable(
            width="100%", color=C_TEAL, thickness=0.5))
        self.story.append(Spacer(1, 4))

    # ── KPI Row ─────────────────────────────────────────────────────────────

    def add_kpi_row(self, kpis):
        """
        Add a row of KPI cards.
        kpis: list of (label, value) tuples, or (label, value, color) tuples.
        """
        if not kpis:
            return

        n = len(kpis)
        card_w = self.usable_w / n
        cells = []
        for item in kpis:
            label = item[0]
            value = item[1]
            card_color = item[2] if len(item) > 2 else C_TEAL

            val_style = ParagraphStyle(
                f"kpi_v_{label[:8]}", parent=self.s_kpi_val, textColor=card_color)
            cells.append([
                _safe_p(str(value), val_style),
                _safe_p(label, self.s_kpi_lbl),
            ])

        t = Table([cells], colWidths=[card_w] * n)
        cmds = [
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]
        # Alternating light backgrounds for each card
        bg_colors = [C_GREEN_S, C_BLUE_L, C_AMBER_L, C_GRAY_L, C_GREEN_S, C_BLUE_L]
        for i in range(n):
            cmds.append(("BACKGROUND", (i, 0), (i, 0), bg_colors[i % len(bg_colors)]))
            if i < n - 1:
                cmds.append(("LINEAFTER", (i, 0), (i, 0), 0.5, C_GRAY_E))
        cmds.append(("BOX", (0, 0), (-1, -1), 0.5, C_GRAY_E))
        t.setStyle(TableStyle(cmds))
        self.story.append(t)
        self.story.append(Spacer(1, 8))

    # ── Table ───────────────────────────────────────────────────────────────

    def add_table(self, headers, data, widths=None, right_align_cols=None,
                  center_align_cols=None, totals_row=None):
        """
        Add a formatted data table.

        headers: list of column header strings
        data: list of lists (rows of cell values)
        widths: optional list of column widths
        right_align_cols: set of 0-based column indices to right-align
        center_align_cols: set of 0-based column indices to center-align
        totals_row: optional list of values for a totals row at the bottom
        """
        if not headers:
            return

        right_align_cols = right_align_cols or set()
        center_align_cols = center_align_cols or set()
        ncols = len(headers)

        if widths is None:
            widths = [self.usable_w / ncols] * ncols

        # Header row
        hdr_cells = []
        for i, h in enumerate(headers):
            style = self.s_th_r if i in right_align_cols else self.s_th
            hdr_cells.append(_safe_p(str(h), style))
        rows = [hdr_cells]

        # Data rows
        for row_data in data:
            cells = []
            for i, val in enumerate(row_data):
                if i in right_align_cols:
                    style = self.s_td_r
                elif i in center_align_cols:
                    style = self.s_td_c
                else:
                    style = self.s_td
                cells.append(_safe_p(str(val) if val is not None else "", style))
            rows.append(cells)

        # Totals row
        if totals_row:
            tot_cells = []
            for i, val in enumerate(totals_row):
                if i in right_align_cols:
                    style = self.s_td_bold_r
                else:
                    style = self.s_td_bold
                tot_cells.append(_safe_p(str(val) if val is not None else "", style))
            rows.append(tot_cells)

        t = Table(rows, colWidths=widths, repeatRows=1)

        nrows = len(rows)
        cmds = [
            # Header
            ("BACKGROUND",    (0, 0), (-1, 0), C_TEAL),
            ("TOPPADDING",    (0, 0), (-1, 0), 4),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            # Data rows
            ("TOPPADDING",    (0, 1), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 2),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            # Grid
            ("LINEBELOW",     (0, 0), (-1, -2), 0.3, C_GRAY_E),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_E),
        ]

        # Alternating row backgrounds
        for i in range(2, nrows, 2):
            cmds.append(("BACKGROUND", (0, i), (-1, i), C_GRAY_L))

        # Totals row styling
        if totals_row:
            cmds.append(("BACKGROUND",  (0, -1), (-1, -1), C_SUBTOT))
            cmds.append(("LINEABOVE",   (0, -1), (-1, -1), 0.8, C_TEAL))
            cmds.append(("TOPPADDING",  (0, -1), (-1, -1), 4))
            cmds.append(("BOTTOMPADDING", (0, -1), (-1, -1), 4))

        t.setStyle(TableStyle(cmds))
        self.story.append(t)
        self.story.append(Spacer(1, 8))

    # ── Chart Placeholder (Summary Stats) ───────────────────────────────────

    def add_chart_placeholder(self, title, data):
        """
        Add a summary statistics block (label-value pairs displayed as a mini table).
        data: list of (label, value) tuples
        """
        if not data:
            return

        self.add_section(title)

        rows = []
        for label, value in data:
            rows.append([
                _safe_p(str(label), self.s_td_bold),
                _safe_p(str(value), self.s_td_r),
            ])

        lw = self.usable_w * 0.5
        t = Table(rows, colWidths=[lw, lw])
        cmds = [
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("BOX",           (0, 0), (-1, -1), 0.5, C_GRAY_E),
        ]
        for i in range(0, len(rows), 2):
            cmds.append(("BACKGROUND", (0, i), (-1, i), C_GREEN_S))
        t.setStyle(TableStyle(cmds))
        self.story.append(t)
        self.story.append(Spacer(1, 8))

    # ── Text ────────────────────────────────────────────────────────────────

    def add_text(self, text):
        """Add a paragraph of text."""
        self.story.append(_safe_p(text, self.s_text))

    # ── Page Break ──────────────────────────────────────────────────────────

    def add_page_break(self):
        """Insert a page break."""
        self.story.append(PageBreak())

    # ── Footer callback ────────────────────────────────────────────────────

    def _add_footer(self, canvas, doc):
        """Draw footer on every page."""
        canvas.saveState()
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(C_GRAY_T)

        footer_text = (
            f"Harmoni ERP - {self.titulo} - "
            f"Generado: {date.today().strftime('%d/%m/%Y')} - "
            f"Pagina {canvas.getPageNumber()}"
        )
        canvas.drawCentredString(
            self.page_w / 2, self.margin - 6 * mm, footer_text)

        # Thin line above footer
        canvas.setStrokeColor(C_GRAY_E)
        canvas.setLineWidth(0.3)
        canvas.line(self.margin, self.margin - 3 * mm,
                    self.page_w - self.margin, self.margin - 3 * mm)
        canvas.restoreState()

    # ── Generate ────────────────────────────────────────────────────────────

    def generate(self):
        """Build the PDF and return bytes."""
        buf = io.BytesIO()
        page = A4 if self.orientation == 'portrait' else landscape(A4)
        doc = SimpleDocTemplate(
            buf, pagesize=page,
            leftMargin=self.margin, rightMargin=self.margin,
            topMargin=self.margin, bottomMargin=self.margin + 4 * mm,
        )

        doc.build(
            self.story,
            onFirstPage=self._add_footer,
            onLaterPages=self._add_footer,
        )
        return buf.getvalue()
