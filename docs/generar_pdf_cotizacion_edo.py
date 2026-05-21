"""
Genera PDF profesional con el anexo de cotización EDO + Onboarding Express.

Output: docs/Anexo_Cotizacion_EDO_Onboarding_Express.pdf

Uso:
    python docs/generar_pdf_cotizacion_edo.py
"""
import os
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable


# ── Paleta Harmoni ──────────────────────────────────────────────
TEAL_DARK = colors.HexColor("#0d2b27")
TEAL = colors.HexColor("#0f766e")
TEAL_LIGHT = colors.HexColor("#5eead4")
TEAL_BG = colors.HexColor("#f0fafa")
WHITE = colors.white
GRAY_DARK = colors.HexColor("#1f2937")
GRAY = colors.HexColor("#6b7280")
GRAY_LIGHT = colors.HexColor("#e5e7eb")
GREEN = colors.HexColor("#10b981")
RED = colors.HexColor("#ef4444")
AMBER = colors.HexColor("#f59e0b")


# ── Estilos ──────────────────────────────────────────────────────
styles = getSampleStyleSheet()

style_h1 = ParagraphStyle(
    'H1', parent=styles['Heading1'],
    fontName='Helvetica-Bold', fontSize=22, textColor=TEAL_DARK,
    leading=26, spaceAfter=6, spaceBefore=0,
)
style_h2 = ParagraphStyle(
    'H2', parent=styles['Heading2'],
    fontName='Helvetica-Bold', fontSize=14, textColor=TEAL,
    leading=18, spaceAfter=4, spaceBefore=12,
)
style_h3 = ParagraphStyle(
    'H3', parent=styles['Heading3'],
    fontName='Helvetica-Bold', fontSize=11, textColor=TEAL_DARK,
    leading=14, spaceAfter=3, spaceBefore=8,
)
style_body = ParagraphStyle(
    'Body', parent=styles['Normal'],
    fontName='Helvetica', fontSize=9.5, textColor=GRAY_DARK,
    leading=14, spaceAfter=6, alignment=TA_JUSTIFY,
)
style_quote = ParagraphStyle(
    'Quote', parent=style_body,
    fontName='Helvetica-Oblique', textColor=TEAL,
    leftIndent=10, borderColor=TEAL, borderPadding=(8, 8, 8, 8),
)
style_small = ParagraphStyle(
    'Small', parent=styles['Normal'],
    fontName='Helvetica', fontSize=8, textColor=GRAY,
    leading=11, alignment=TA_CENTER,
)
style_subtitle = ParagraphStyle(
    'Subtitle', parent=styles['Normal'],
    fontName='Helvetica', fontSize=11, textColor=GRAY,
    leading=14, spaceAfter=12, alignment=TA_LEFT,
)


# ── Helpers ──────────────────────────────────────────────────────

def page_header(canvas, doc):
    canvas.saveState()
    # Logo / brand top-left
    canvas.setFillColor(TEAL_DARK)
    canvas.setFont('Helvetica-Bold', 11)
    canvas.drawString(2 * cm, 28 * cm, "HARMONI ERP")
    canvas.setFillColor(GRAY)
    canvas.setFont('Helvetica', 8)
    canvas.drawString(2 * cm, 27.6 * cm, "Anexo de Cotización · EDO Grupo · 2026")
    # Page number bottom-right
    canvas.setFillColor(GRAY)
    canvas.setFont('Helvetica', 8)
    canvas.drawRightString(19 * cm, 1.5 * cm,
                           f"Página {doc.page}  ·  harmoni.pe")
    # Línea decorativa
    canvas.setStrokeColor(TEAL_LIGHT)
    canvas.setLineWidth(2)
    canvas.line(2 * cm, 27.3 * cm, 19 * cm, 27.3 * cm)
    canvas.restoreState()


def section_separator():
    return [
        Spacer(1, 8),
        HRFlowable(width="100%", thickness=0.5, color=GRAY_LIGHT,
                   spaceBefore=0, spaceAfter=0),
        Spacer(1, 8),
    ]


def kv_table(rows, col1_w=6*cm, col2_w=10*cm):
    """Crea una tabla key-value sobria."""
    data = [[Paragraph(f"<b>{k}</b>", style_body), Paragraph(v, style_body)] for k, v in rows]
    t = Table(data, colWidths=[col1_w, col2_w])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), TEAL_BG),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, GRAY_LIGHT),
    ]))
    return t


def compare_table(headers, rows):
    """Tabla comparativa con header oscuro."""
    data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('hdr', parent=style_body,
                                                      textColor=WHITE, alignment=TA_LEFT,
                                                      fontName='Helvetica-Bold', fontSize=9))
             for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), style_body) for c in row])
    t = Table(data, colWidths=[8*cm, 8*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, -1), 0.3, GRAY_LIGHT),
        ('BACKGROUND', (0, 1), (-1, -1), WHITE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, TEAL_BG]),
    ]))
    return t


def plan_table(headers, rows):
    """Tabla de plan/semanas con colores temáticos."""
    data = [[Paragraph(f"<b>{h}</b>", ParagraphStyle('hdr', parent=style_body,
                                                       textColor=WHITE, fontName='Helvetica-Bold',
                                                       fontSize=9))
             for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), style_body) for c in row])
    t = Table(data, colWidths=[2*cm, 11.5*cm, 3.5*cm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.3, GRAY_LIGHT),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [WHITE, TEAL_BG]),
    ]))
    return t


# ── Contenido ────────────────────────────────────────────────────

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=2.5*cm, bottomMargin=2*cm,
        leftMargin=2*cm, rightMargin=2*cm,
    )

    story = []

    # ── Portada ──────────────────────────────────────────────────
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("Harmoni × EDO Grupo", style_h1))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Anexo de Cotización · Onboarding Express en 2 semanas",
        style_subtitle,
    ))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="20%", thickness=3, color=TEAL_LIGHT,
                            spaceBefore=0, spaceAfter=14))

    story.append(Paragraph(
        "Después de revisar la operación de EDO Grupo en profundidad, "
        "simplificamos el go-live de Harmoni. La promesa es nueva: "
        "<b>no migramos 12 meses de historia</b>. Cargamos saldos al corte "
        "y arrancamos.",
        style_body,
    ))
    story.append(Spacer(1, 14))

    # Tabla comparativa
    story.append(Paragraph("La diferencia frente al enfoque clásico", style_h2))
    story.append(Spacer(1, 4))
    story.append(compare_table(
        ["Enfoque clásico (industria)", "Onboarding Express Harmoni"],
        [
            ["Migrar 12 meses de planillas históricas",            "<b>NO migramos historia</b>"],
            ["4-5 semanas de implementación",                       "<b>1-2 semanas</b>"],
            ["IT de EDO involucrado en parallel runs",              "RRHH llena un Excel"],
            ["Validación centavo a centavo de meses pasados",       "Solo saldos al corte"],
            ["Riesgo de duplicar boletas ene-may",                  "Cero — salto en limpio"],
        ],
    ))

    story.append(PageBreak())

    # ── Cómo funciona ───────────────────────────────────────────
    story.append(Paragraph("Cómo funciona el wizard de apertura", style_h2))
    story.append(Paragraph(
        "Tu equipo de RRHH ejecuta tres pasos en Harmoni:",
        style_body,
    ))

    story.append(Paragraph(
        "<b>1.</b> Define la fecha de corte (recomendado: <b>31/05/2026</b>, último cierre Spring).",
        style_body,
    ))
    story.append(Paragraph(
        "<b>2.</b> Descarga la plantilla Excel — <i>pre-llenada con todos los trabajadores activos</i>.",
        style_body,
    ))
    story.append(Paragraph(
        "<b>3.</b> Sube el Excel completado con: provisión CTS, provisión gratificación, "
        "provisión vacaciones, días vacaciones pendientes, IR 5ta acumulado del año, "
        "saldo préstamos vigentes.",
        style_body,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "Validamos los datos, mostramos preview, confirman. "
        "<b>Harmoni arranca a procesar desde junio 2026 en adelante.</b>",
        style_body,
    ))

    story.extend(section_separator())

    # ── Qué le manda a Spring ────────────────────────────────────
    story.append(Paragraph("Lo que Harmoni le manda a Spring", style_h2))
    story.append(Paragraph(
        "Spring sigue corriendo Contabilidad, Logística y Facturación como hoy. "
        "Harmoni asume RRHH end-to-end y le manda a Spring <b>tres cosas estandarizadas</b> "
        "cada cierre:",
        style_body,
    ))
    story.append(kv_table([
        ("Asiento contable mensual",
         "Desagregado por RUC y centro de costo. Formato Excel Universal, "
         "CONCAR, Siscont, SAP o SIRE PLE — a elección."),
        ("Maestro de empleados activos",
         "DNI, local, puesto, estado. Para que el módulo de Logística de Spring "
         "sepa a quién entregarle uniforme, vales, herramientas."),
        ("Costos por centro de costo",
         "Para análisis de rentabilidad por local. Spring lo cruza con ventas "
         "para sacar margen real."),
    ]))

    story.extend(section_separator())

    # ── Plan revisado ───────────────────────────────────────────
    story.append(Paragraph("Plan revisado de implementación", style_h2))
    story.append(Spacer(1, 4))
    story.append(plan_table(
        ["Semana", "Trabajo", "Responsable"],
        [
            ["S1", "Setup empresa, locales, puestos. Configurar conceptos remunerativos "
                   "de EDO (propinas pool, bono nocturno).", "Harmoni + RRHH EDO"],
            ["S1", "Configurar plan de cuentas para asiento contable (mapeo a Spring).",
                   "Harmoni + Contador"],
            ["S2", "Equipo RRHH EDO llena la plantilla de apertura (saldos al 31/05/2026).",
                   "RRHH EDO"],
            ["S2", "Capacitación equipo RRHH (2 sesiones de 90 min).", "Harmoni"],
            ["S2", "Doble corrida paralela: planilla mayo en Spring vs Harmoni. "
                   "Validar coincidencia centavo a centavo.", "Harmoni + Contador"],
            ["Jun", "<b>Go-live</b>. Harmoni emite planilla oficial de junio 2026. "
                    "Exporta asiento a Spring. Contador valida.", "Equipo EDO"],
        ],
    ))

    story.append(PageBreak())

    # ── Features destacadas ────────────────────────────────────
    story.append(Paragraph("Features destacadas para Grupo Gastronómico Premium", style_h2))
    story.append(Paragraph(
        "Harmoni incluye features específicas pensadas para grupos como EDO. "
        "Algunas no las ofrece ningún competidor en el mercado peruano.",
        style_body,
    ))

    features = [
        ("🎯 Pulse del Grupo",
         "Dashboard ejecutivo con las 24 empresas/locales como tarjetas. "
         "Cada local muestra headcount, asistencia hoy, planilla del mes, alertas. "
         "Código verde/amarillo/rojo según salud operativa. "
         "<i>La pantalla que el dueño abre cada mañana con su café.</i>"),
        ("📋 Briefing del Día",
         "Pre-shift handover estilo brigade kitchen (Escoffier). "
         "El jefe de local publica antes del servicio: covers esperados, "
         "VIPs/alergias, especiales del chef, items 86'd (sin stock), "
         "dress code, notas operativas. "
         "<i>Trail auditable para operación premium. Ningún competidor lo tiene.</i>"),
        ("🗓 Cuadrícula Semanal del Local",
         "Vista brigade view de turnos semanales — eje X = 7 días, "
         "eje Y = trabajadores. Celdas con turno (M/T/N/Q/D). "
         "Alertas automáticas: +6 días seguidos (DS 003-97-TR), sin descanso semanal."),
        ("📊 Comparativo Mensual",
         "Vista evolutiva últimos 3/6/9/12 meses: trabajadores, neto pagado, "
         "costo empresa, AFP/ONP. Gráfico Chart.js + tabla con deltas porcentuales "
         "+ export CSV. Para gerencia y planeación presupuestaria."),
        ("💼 Saldos de Apertura",
         "Wizard de onboarding express. Reemplaza la migración histórica "
         "completa por una plantilla Excel."),
        ("🔌 Outputs Universales",
         "Excel Universal + CONCAR + Siscont + SAP + SIRE PLE SUNAT + "
         "Provisiones separadas. Funciona con cualquier ERP receptor — "
         "no dependencia de un proveedor específico."),
    ]
    for titulo, desc in features:
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>{titulo}</b>", style_h3))
        story.append(Paragraph(desc, style_body))

    story.append(PageBreak())

    # ── Garantías ───────────────────────────────────────────────
    story.append(Paragraph("Garantías del Onboarding Express", style_h2))
    story.append(Spacer(1, 4))
    garantias = [
        ("Parallel run validado",
         "Corremos planilla mayo en Spring y en Harmoni. Si no coinciden "
         "centavo a centavo, no hacemos go-live."),
        ("Backup primer mes",
         "La primera planilla de Harmoni en producción tiene revisión "
         "adicional de nuestro equipo sin costo."),
        ("Soporte intensivo",
         "Respuesta menor a 4 horas hábiles durante los primeros 30 días "
         "de operación."),
        ("Rollback plan",
         "Si por cualquier razón hay que volver a Spring antes de 60 días, "
         "Harmoni entrega toda la data en formato estándar para re-cargar. "
         "Sin data lock-in."),
    ]
    for titulo, desc in garantias:
        story.append(Paragraph(f"<b>✓ {titulo}</b>", style_h3))
        story.append(Paragraph(desc, style_body))
        story.append(Spacer(1, 4))

    story.extend(section_separator())

    # ── Impacto económico ──────────────────────────────────────
    story.append(Paragraph("Impacto económico del Onboarding Express", style_h2))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "Al simplificar el go-live, eliminamos componentes costosos:",
        style_body,
    ))
    story.append(Paragraph(
        "• Eliminamos las <b>40-60 horas profesionales</b> de migración histórica<br/>"
        "• Eliminamos el <b>parallel run de 12 meses</b><br/>"
        "• Mantenemos funcionalidad completa<br/>"
        "• <b>Time-to-value se acelera</b> — EDO opera en Harmoni el mes siguiente al contrato",
        style_body,
    ))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Reducción estimada: 20-30% del costo de implementación</b>",
        ParagraphStyle('emphasis', parent=style_body,
                       textColor=TEAL, fontSize=11, fontName='Helvetica-Bold',
                       alignment=TA_CENTER),
    ))

    story.append(PageBreak())

    # ── Próximos pasos ──────────────────────────────────────────
    story.append(Paragraph("Próximos pasos sugeridos", style_h2))
    story.append(Spacer(1, 4))

    pasos = [
        "<b>1.</b> Validar con Isabel el ángulo \"Onboarding Express\" antes del próximo meeting.",
        "<b>2.</b> Conseguir una muestra del asiento contable que Spring importa "
        "(un archivo de cualquier mes) — esto nos permite afinar el conector específico "
        "si fuera necesario.",
        "<b>3.</b> Definir fecha de corte preferida — recomendamos <b>31/05/2026</b>.",
        "<b>4.</b> Agendar demo en vivo del wizard de apertura + Pulse del Grupo + "
        "Briefing del Día.",
    ]
    for p in pasos:
        story.append(Paragraph(p, style_body))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 16))
    story.append(HRFlowable(width="40%", thickness=2, color=TEAL_LIGHT,
                            spaceBefore=0, spaceAfter=12, hAlign='CENTER'))

    story.append(Paragraph(
        "<b>Edwin López</b>", style_h3))
    story.append(Paragraph(
        "Gerente de Operaciones Harmoni",
        ParagraphStyle('contact', parent=style_body, alignment=TA_LEFT,
                       textColor=GRAY)))
    story.append(Paragraph(
        "eflopezt@gmail.com  ·  www.harmoni.pe  ·  demo.harmoni.pe",
        ParagraphStyle('contact2', parent=style_body, alignment=TA_LEFT,
                       textColor=TEAL, fontName='Helvetica-Bold')))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Documento generado el {datetime.now().strftime('%d/%m/%Y')} · "
        f"Versión 2026-05-21. Cotización viva. Sujeta a revisión final "
        f"tras llamada de validación con EDO.",
        ParagraphStyle('footer_doc', parent=style_small,
                       alignment=TA_LEFT, textColor=GRAY)))

    doc.build(story, onFirstPage=page_header, onLaterPages=page_header)


if __name__ == '__main__':
    output = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        'Anexo_Cotizacion_EDO_Onboarding_Express.pdf',
    )
    build_pdf(output)
    print(f"PDF generado: {output}")
    print(f"Tamaño: {os.path.getsize(output) / 1024:.1f} KB")
