"""
PDF reporte Evaluación 360° — confidencial (peers/subordinados anonimizados).
Usa ReportLab; A4. Sin matplotlib para evitar dep adicional — el
"radar" se representa como tabla comparativa con barras horizontales.
"""
import io
from collections import Counter
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# Paleta Harmoni
C_DARK = colors.HexColor('#0d2b27')
C_TEAL = colors.HexColor('#0f766e')
C_ACCENT = colors.HexColor('#5eead4')
C_LIGHT = colors.HexColor('#f0fdf4')
C_GREY = colors.HexColor('#6b7280')
C_GREY_L = colors.HexColor('#e5e7eb')
C_RED = colors.HexColor('#b91c1c')
C_AMBER = colors.HexColor('#d97706')
C_GREEN = colors.HexColor('#15803d')
C_BLUE = colors.HexColor('#1d4ed8')

TIPO_LABEL_PDF = {
    'AUTOEVALUACION': 'Auto',
    'MANAGER': 'Manager',
    'PEER': 'Peers',
    'SUBORDINADO': 'Subord.',
    'CLIENTE_INTERNO': 'Cliente',
}

TIPO_ORDEN = ['AUTOEVALUACION', 'MANAGER', 'PEER', 'SUBORDINADO', 'CLIENTE_INTERNO']


def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'T', parent=base['Title'], fontSize=18, textColor=C_DARK,
            spaceAfter=4, alignment=TA_LEFT,
        ),
        'subtitle': ParagraphStyle(
            'ST', parent=base['Normal'], fontSize=10, textColor=C_GREY,
            spaceAfter=10,
        ),
        'h2': ParagraphStyle(
            'H2', parent=base['Heading2'], fontSize=12, textColor=C_TEAL,
            spaceBefore=10, spaceAfter=6,
        ),
        'normal': ParagraphStyle(
            'N', parent=base['Normal'], fontSize=9, textColor=C_DARK,
            leading=12,
        ),
        'small': ParagraphStyle(
            'S', parent=base['Normal'], fontSize=8, textColor=C_GREY,
        ),
        'score_big': ParagraphStyle(
            'SC', parent=base['Normal'], fontSize=38, textColor=C_TEAL,
            alignment=TA_CENTER, fontName='Helvetica-Bold', leading=42,
        ),
        'badge_label': ParagraphStyle(
            'BL', parent=base['Normal'], fontSize=8, textColor=C_GREY,
            alignment=TA_CENTER,
        ),
        'confidencial': ParagraphStyle(
            'CF', parent=base['Normal'], fontSize=7, textColor=C_RED,
            alignment=TA_CENTER, fontName='Helvetica-Bold',
        ),
    }


def _score_color(score):
    if score is None:
        return C_GREY
    s = float(score)
    if s >= 4:
        return C_GREEN
    if s >= 3:
        return C_TEAL
    if s >= 2:
        return C_AMBER
    return C_RED


def _texto_score(score):
    if score is None:
        return 'N/D'
    s = float(score)
    if s >= 4.5:
        return 'Sobresaliente'
    if s >= 4:
        return 'Excelente'
    if s >= 3.5:
        return 'Cumple+'
    if s >= 3:
        return 'Cumple'
    if s >= 2:
        return 'Bajo'
    return 'Crítico'


def _safe_decimal(v):
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _build_header(evaluacion, st):
    evaluado = evaluacion.personal_evaluado
    nombre = getattr(evaluado, 'apellidos_nombres', '—')
    cargo = getattr(evaluado, 'cargo', '') or ''

    title = Paragraph(f'<b>Reporte Evaluación 360°</b>', st['title'])
    sub = Paragraph(
        f"{nombre}{' · ' + cargo if cargo else ''} · Período <b>{evaluacion.periodo}</b>"
        f" · Estado <b>{evaluacion.get_estado_display()}</b>",
        st['subtitle'],
    )
    conf = Paragraph(
        'CONFIDENCIAL — Documento de uso interno. Peers y subordinados anonimizados.',
        st['confidencial'],
    )
    return [title, sub, conf, HRFlowable(width='100%', thickness=0.8, color=C_TEAL),
            Spacer(1, 6)]


def _build_score_block(evaluacion, st):
    score = evaluacion.puntaje_global
    score_str = f'{score:.2f}' if score is not None else '—'
    score_color = _score_color(score)

    big = Paragraph(f'<font color="{score_color.hexval()}">{score_str}</font>', st['score_big'])
    label = Paragraph(
        f'<b>{_texto_score(score)}</b> · Escala 0-5 · '
        f'{evaluacion.completadas}/{evaluacion.total_participantes} participantes completaron',
        st['badge_label'],
    )

    avance = evaluacion.porcentaje_avance
    avance_p = Paragraph(
        f'<b>Avance:</b> {avance}%', st['badge_label'],
    )

    tabla = Table(
        [[big], [label], [avance_p]],
        colWidths=[170 * mm],
    )
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), C_LIGHT),
        ('BOX', (0, 0), (-1, -1), 0.4, C_GREY_L),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return [tabla, Spacer(1, 8)]


def _build_comparativa(evaluacion, st):
    matriz = evaluacion.matriz_comparativa()
    if not matriz:
        return [Paragraph('Sin respuestas registradas aún.', st['normal']),
                Spacer(1, 6)]

    header = ['Competencia']
    for tipo in TIPO_ORDEN:
        header.append(TIPO_LABEL_PDF[tipo])
    header.append('Promedio')

    rows = [header]
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), C_TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.4, C_GREY_L),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, C_GREY_L),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]

    for row_idx, (cod, info) in enumerate(matriz.items(), start=1):
        promedios = info['promedios']
        valores_validos = [v for v in promedios.values() if v is not None]
        prom_total = (
            sum(Decimal(str(v)) for v in valores_validos) / Decimal(str(len(valores_validos)))
            if valores_validos else None
        )
        row = [Paragraph(info['label'], st['normal'])]
        for tipo in TIPO_ORDEN:
            v = promedios.get(tipo)
            if v is None:
                row.append('—')
            else:
                row.append(f'{float(v):.1f}')
                col_idx = TIPO_ORDEN.index(tipo) + 1
                style_cmds.append((
                    'TEXTCOLOR', (col_idx, row_idx), (col_idx, row_idx),
                    _score_color(v),
                ))
                style_cmds.append((
                    'FONTNAME', (col_idx, row_idx), (col_idx, row_idx),
                    'Helvetica-Bold',
                ))
        if prom_total is None:
            row.append('—')
        else:
            row.append(f'{float(prom_total):.2f}')
            style_cmds.append((
                'TEXTCOLOR', (-1, row_idx), (-1, row_idx),
                _score_color(prom_total),
            ))
            style_cmds.append((
                'FONTNAME', (-1, row_idx), (-1, row_idx), 'Helvetica-Bold',
            ))
        rows.append(row)

    col_widths = [55 * mm] + [18 * mm] * 5 + [22 * mm]
    tabla = Table(rows, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return [tabla, Spacer(1, 8)]


def _build_gaps(evaluacion, st):
    gaps = evaluacion.gaps_auto_manager()
    if not gaps:
        return []

    elementos = [Paragraph('Brechas Autoevaluación vs Manager', st['h2'])]
    explica = Paragraph(
        '<font color="#6b7280" size="8">Gap positivo = el evaluado se autocalifica más alto que su manager. '
        'Gap &ge; 1.5 amerita conversación; &ge; 2 es crítico.</font>',
        st['normal'],
    )
    elementos.append(explica)
    elementos.append(Spacer(1, 4))

    rows = [['Competencia', 'Auto', 'Manager', 'Gap', 'Severidad']]
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), C_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.4, C_GREY_L),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, C_GREY_L),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]

    sev_color = {
        'critical': C_RED,
        'warning': C_AMBER,
        'ok': C_GREEN,
    }
    sev_label = {
        'critical': 'CRÍTICO',
        'warning': 'ALERTA',
        'ok': 'OK',
    }
    for idx, g in enumerate(gaps, start=1):
        rows.append([
            Paragraph(g['competencia'], st['normal']),
            f"{float(g['auto']):.1f}",
            f"{float(g['manager']):.1f}",
            f"{float(g['gap']):+.2f}",
            sev_label[g['severidad']],
        ])
        c = sev_color[g['severidad']]
        style_cmds.append(('TEXTCOLOR', (-1, idx), (-1, idx), c))
        style_cmds.append(('FONTNAME', (-1, idx), (-1, idx), 'Helvetica-Bold'))

    tabla = Table(rows, colWidths=[60 * mm, 20 * mm, 22 * mm, 22 * mm, 26 * mm],
                  repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    elementos.append(tabla)
    elementos.append(Spacer(1, 8))
    return elementos


def _top_keywords(textos, top_n=5):
    """Heurística simple: cuenta líneas / frases comunes en textos."""
    items = []
    for t in textos:
        if not t:
            continue
        # Trata cada bullet/línea como item
        for linea in t.replace(';', '\n').split('\n'):
            linea = linea.strip(' \t-*•·.,').strip()
            if 3 <= len(linea) <= 120:
                items.append(linea)
    if not items:
        return []
    counter = Counter(items)
    return [item for item, _ in counter.most_common(top_n)]


def _build_fortalezas_areas(evaluacion, st):
    participantes_comp = evaluacion.participantes.filter(completada=True)
    fortalezas_textos = [p.fortalezas for p in participantes_comp]
    areas_textos = [p.areas_mejora for p in participantes_comp]

    fortalezas_top = _top_keywords(fortalezas_textos, top_n=5)
    areas_top = _top_keywords(areas_textos, top_n=5)

    elementos = []
    elementos.append(Paragraph('Fortalezas (Top mencionadas)', st['h2']))
    if fortalezas_top:
        for item in fortalezas_top:
            elementos.append(Paragraph(f'• {item}', st['normal']))
    else:
        elementos.append(Paragraph('Sin fortalezas registradas aún.', st['small']))
    elementos.append(Spacer(1, 6))

    elementos.append(Paragraph('Áreas de Mejora', st['h2']))
    if areas_top:
        for item in areas_top:
            elementos.append(Paragraph(f'• {item}', st['normal']))
    else:
        elementos.append(Paragraph('Sin áreas de mejora registradas aún.', st['small']))
    elementos.append(Spacer(1, 6))
    return elementos


def _build_plan_desarrollo(evaluacion, st):
    """Plan sugerido basado en competencias con menor puntaje agregado."""
    matriz = evaluacion.matriz_comparativa()
    rankings = []
    for cod, info in matriz.items():
        valores = [v for v in info['promedios'].values() if v is not None]
        if not valores:
            continue
        prom = sum(Decimal(str(v)) for v in valores) / Decimal(str(len(valores)))
        rankings.append((info['label'], float(prom)))
    rankings.sort(key=lambda x: x[1])
    sugerencias = rankings[:3]

    plan_map = {
        'Liderazgo': 'Programa "Líder Gastronómico" — 4 sesiones + shadowing con chef ejecutivo.',
        'Trabajo en Equipo': 'Taller "Brigada de Cocina" + dinámicas cross-área.',
        'Calidad de Servicio': 'Auditorías de servicio + curso "Service Excellence" del INCAE.',
        'Resolución de Conflictos': 'Mentoring 1:1 + módulo "Mediación en Equipos Operativos".',
        'Iniciativa': 'Proyecto piloto a cargo del evaluado durante el trimestre.',
        'Comunicación': 'Curso comunicación asertiva + role-play con feedback grabado.',
    }

    elementos = [Paragraph('Plan de Desarrollo Sugerido', st['h2'])]
    explica = Paragraph(
        '<font color="#6b7280" size="8">Acciones recomendadas para las competencias con menor puntaje agregado.</font>',
        st['normal'],
    )
    elementos.append(explica)
    elementos.append(Spacer(1, 4))

    if not sugerencias:
        elementos.append(Paragraph('Sin datos suficientes para sugerir un plan.', st['small']))
        elementos.append(Spacer(1, 4))
        return elementos

    rows = [['#', 'Competencia', 'Promedio', 'Acción Sugerida']]
    for i, (label, prom) in enumerate(sugerencias, start=1):
        accion = plan_map.get(label, f'Plan de mejora específico para "{label}" — 60 días.')
        rows.append([str(i), label, f'{prom:.2f}', Paragraph(accion, st['normal'])])

    tabla = Table(rows, colWidths=[8 * mm, 48 * mm, 22 * mm, 92 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_TEAL),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 1), (0, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.4, C_GREY_L),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, C_GREY_L),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 6))
    return elementos


def _build_participantes_anonimos(evaluacion, st):
    """Lista anonimizada: el manager se nombra, peers/subord se enumeran."""
    elementos = [Paragraph('Participantes', st['h2'])]
    peers_count = 0
    subord_count = 0
    rows = [['Tipo', 'Identificador', 'Estado', 'Puntaje global']]
    for p in evaluacion.participantes.all():
        if p.tipo == 'PEER':
            peers_count += 1
            display = f'Peer {peers_count}'
        elif p.tipo == 'SUBORDINADO':
            subord_count += 1
            display = f'Subordinado {subord_count}'
        elif p.tipo == 'AUTOEVALUACION':
            display = 'El propio evaluado'
        elif p.tipo == 'MANAGER':
            display = getattr(p.personal_evaluador, 'apellidos_nombres', 'Manager')
        else:
            display = 'Cliente interno'
        estado = 'Completada' if p.completada else 'Pendiente'
        score = f'{p.puntaje_global:.2f}' if p.puntaje_global is not None else '—'
        rows.append([p.get_tipo_display(), display, estado, score])

    tabla = Table(rows, colWidths=[36 * mm, 60 * mm, 30 * mm, 30 * mm], repeatRows=1)
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), C_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.4, C_GREY_L),
        ('INNERGRID', (0, 0), (-1, -1), 0.3, C_GREY_L),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (3, 1), (3, -1), 'CENTER'),
    ]))
    elementos.append(tabla)
    elementos.append(Spacer(1, 6))
    return elementos


def build_reporte_360_pdf(evaluacion):
    """Genera el PDF y devuelve un BytesIO con el contenido."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title=f'Reporte 360 — {getattr(evaluacion.personal_evaluado, "apellidos_nombres", "")}',
    )
    st = _styles()
    story = []
    story.extend(_build_header(evaluacion, st))
    story.extend(_build_score_block(evaluacion, st))
    story.append(Paragraph('Tabla comparativa por evaluador', st['h2']))
    story.extend(_build_comparativa(evaluacion, st))
    story.extend(_build_gaps(evaluacion, st))
    story.extend(_build_fortalezas_areas(evaluacion, st))
    story.extend(_build_plan_desarrollo(evaluacion, st))
    story.extend(_build_participantes_anonimos(evaluacion, st))

    doc.build(story)
    buffer.seek(0)
    return buffer
