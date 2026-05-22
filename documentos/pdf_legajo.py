"""
documentos/pdf_legajo.py
Genera un PDF resumen del Legajo Digital completo de un trabajador.

Contenido:
1. Portada con datos básicos + foto (si existe).
2. Tabla resumen de documentos por categoría con estado de vigencia.
3. Detalle expandido por documento (referencia al archivo, notas, versión).
4. Pie con fecha de generación + firma autorizada.

Uso:
    from documentos.pdf_legajo import build_legajo_pdf
    buffer = build_legajo_pdf(personal)
    return HttpResponse(buffer.getvalue(), content_type='application/pdf')
"""
from __future__ import annotations

import io
import os
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


# ── Paleta Harmoni ────────────────────────────────────────────────
COLOR_PRIMARY = colors.HexColor('#0F766E')
COLOR_DARK    = colors.HexColor('#0D2B27')
COLOR_LIGHT   = colors.HexColor('#F0FDF9')
COLOR_ACCENT  = colors.HexColor('#5EEAD4')
COLOR_VENCIDO    = colors.HexColor('#DC2626')
COLOR_POR_VENCER = colors.HexColor('#D97706')
COLOR_VIGENTE    = colors.HexColor('#059669')
COLOR_MUTED      = colors.HexColor('#6B7280')


def _estilos():
    base = getSampleStyleSheet()
    return {
        'h1': ParagraphStyle(
            'H1', parent=base['Heading1'],
            fontSize=20, textColor=COLOR_DARK, spaceAfter=8, alignment=TA_LEFT,
        ),
        'h2': ParagraphStyle(
            'H2', parent=base['Heading2'],
            fontSize=14, textColor=COLOR_PRIMARY, spaceAfter=4, spaceBefore=12,
        ),
        'h3': ParagraphStyle(
            'H3', parent=base['Heading3'],
            fontSize=11, textColor=COLOR_PRIMARY, spaceAfter=2, spaceBefore=6,
        ),
        'normal': ParagraphStyle(
            'N', parent=base['Normal'], fontSize=9, leading=12,
        ),
        'small': ParagraphStyle(
            'S', parent=base['Normal'], fontSize=8, textColor=COLOR_MUTED, leading=10,
        ),
        'center': ParagraphStyle(
            'C', parent=base['Normal'], fontSize=10, alignment=TA_CENTER,
        ),
        'footer': ParagraphStyle(
            'F', parent=base['Normal'], fontSize=7, textColor=COLOR_MUTED,
            alignment=TA_CENTER, leading=9,
        ),
    }


def _color_estado(estado: str):
    return {
        'VIGENTE':    COLOR_VIGENTE,
        'POR_VENCER': COLOR_POR_VENCER,
        'VENCIDO':    COLOR_VENCIDO,
        'ANULADO':    COLOR_MUTED,
    }.get(estado, COLOR_MUTED)


def _safe_str(x, default='—'):
    if x is None:
        return default
    try:
        return str(x)
    except Exception:
        return default


def _portada(personal, estilos) -> list:
    """Bloque de portada: nombre, foto, datos personales."""
    flow = []

    flow.append(Paragraph('LEGAJO DIGITAL DEL TRABAJADOR', estilos['h1']))
    flow.append(Paragraph(
        f'Generado el {date.today().strftime("%d/%m/%Y")}',
        estilos['small'],
    ))
    flow.append(Spacer(1, 6 * mm))

    # Foto + datos en tabla de dos columnas
    foto_cell = ''
    foto_path = None
    try:
        foto = getattr(personal, 'foto', None)
        if foto and getattr(foto, 'path', None) and os.path.exists(foto.path):
            foto_path = foto.path
    except Exception:
        foto_path = None
    if foto_path:
        try:
            foto_cell = Image(foto_path, width=3.5 * cm, height=4.5 * cm)
        except Exception:
            foto_cell = Paragraph('[Sin foto]', estilos['small'])
    else:
        foto_cell = Paragraph('[Sin foto]', estilos['small'])

    subarea = getattr(personal, 'subarea', None)
    area_nombre = ''
    if subarea is not None:
        try:
            area_nombre = subarea.area.nombre
        except Exception:
            area_nombre = ''

    datos = [
        ['Apellidos y Nombres', _safe_str(getattr(personal, 'apellidos_nombres', ''))],
        ['Documento de Identidad', _safe_str(getattr(personal, 'nro_doc', ''))],
        ['Cargo', _safe_str(getattr(personal, 'cargo', ''))],
        ['Área', _safe_str(area_nombre)],
        ['Sub-área', _safe_str(getattr(subarea, 'nombre', '') if subarea else '')],
        ['Grupo de Tareo', _safe_str(getattr(personal, 'grupo_tareo', ''))],
        ['Estado', _safe_str(getattr(personal, 'estado', ''))],
    ]
    # fecha_ingreso puede ser property o field
    try:
        fi = personal.fecha_ingreso
        if fi:
            datos.append(['Fecha de Ingreso', fi.strftime('%d/%m/%Y') if hasattr(fi, 'strftime') else str(fi)])
    except Exception:
        pass

    datos_tabla = Table(
        [[Paragraph(f'<b>{k}</b>', estilos['normal']),
          Paragraph(_safe_str(v), estilos['normal'])] for k, v in datos],
        colWidths=[5 * cm, 9 * cm],
    )
    datos_tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [COLOR_LIGHT, colors.white]),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    portada_tabla = Table(
        [[foto_cell, datos_tabla]],
        colWidths=[4 * cm, 14 * cm],
    )
    portada_tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    flow.append(portada_tabla)
    flow.append(Spacer(1, 8 * mm))
    return flow


def _tabla_resumen(docs, estilos) -> list:
    """Tabla resumen: una fila por documento."""
    flow = []
    flow.append(Paragraph('Resumen de Documentos', estilos['h2']))

    header = ['Categoría', 'Tipo de Documento', 'Versión', 'Emisión', 'Vencimiento', 'Estado']
    rows = [header]
    for doc in docs:
        cat = getattr(doc.tipo.categoria, 'nombre', '—') if doc.tipo.categoria else '—'
        emision = doc.fecha_emision.strftime('%d/%m/%Y') if doc.fecha_emision else '—'
        vence = doc.fecha_vencimiento.strftime('%d/%m/%Y') if doc.fecha_vencimiento else '—'
        rows.append([
            Paragraph(cat, estilos['small']),
            Paragraph(_safe_str(doc.tipo.nombre), estilos['small']),
            f'v{doc.version}',
            emision,
            vence,
            Paragraph(
                f'<font color="{_color_estado(doc.estado).hexval()}"><b>'
                f'{doc.get_estado_display()}</b></font>',
                estilos['small'],
            ),
        ])

    if len(rows) == 1:
        rows.append(['', 'Sin documentos registrados.', '', '', '', ''])

    t = Table(
        rows,
        colWidths=[3 * cm, 5.5 * cm, 1.4 * cm, 2.2 * cm, 2.2 * cm, 2.5 * cm],
        repeatRows=1,
    )
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_DARK),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, COLOR_LIGHT]),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    flow.append(t)
    flow.append(Spacer(1, 6 * mm))
    return flow


def _detalle_por_categoria(docs, estilos) -> list:
    """Detalle agrupado por categoría con miniaturas/refs."""
    flow = []
    flow.append(PageBreak())
    flow.append(Paragraph('Detalle por Categoría', estilos['h2']))

    # Agrupar
    grupos: dict[str, list] = {}
    for d in docs:
        cat = getattr(d.tipo.categoria, 'nombre', 'Sin Categoría') if d.tipo.categoria else 'Sin Categoría'
        grupos.setdefault(cat, []).append(d)

    if not grupos:
        flow.append(Paragraph(
            '<i>Este trabajador aún no tiene documentos cargados.</i>',
            estilos['normal'],
        ))
        return flow

    for cat_nombre, items in grupos.items():
        flow.append(Paragraph(f'{cat_nombre} ({len(items)})', estilos['h3']))
        for doc in items:
            partes = [f'<b>{doc.tipo.nombre}</b> (v{doc.version})']
            if doc.nombre_archivo:
                partes.append(f'Archivo: <i>{doc.nombre_archivo}</i>')
            if doc.fecha_emision:
                partes.append(f'Emitido: {doc.fecha_emision.strftime("%d/%m/%Y")}')
            if doc.fecha_vencimiento:
                partes.append(f'Vence: {doc.fecha_vencimiento.strftime("%d/%m/%Y")}')
            estado = doc.get_estado_display()
            color_hex = _color_estado(doc.estado).hexval()
            partes.append(f'Estado: <font color="{color_hex}"><b>{estado}</b></font>')
            if doc.subido_por:
                partes.append(f'Subido por: {doc.subido_por}')

            flow.append(Paragraph(' · '.join(partes), estilos['normal']))
            if doc.notas:
                flow.append(Paragraph(
                    f'<i>Notas: {doc.notas}</i>', estilos['small'],
                ))
            # Miniatura si es imagen y existe en disco
            if doc.es_imagen:
                try:
                    if doc.archivo and hasattr(doc.archivo, 'path') and os.path.exists(doc.archivo.path):
                        flow.append(Spacer(1, 2 * mm))
                        flow.append(Image(
                            doc.archivo.path,
                            width=4 * cm, height=5 * cm,
                            kind='proportional',
                        ))
                except Exception:
                    pass
            flow.append(Spacer(1, 3 * mm))
        flow.append(Spacer(1, 3 * mm))

    return flow


def _pie(estilos, autorizado_por: str = 'Recursos Humanos') -> list:
    """Pie de cierre con firma."""
    flow = [Spacer(1, 12 * mm)]
    flow.append(Paragraph(
        '_______________________________________',
        estilos['center'],
    ))
    flow.append(Paragraph(f'{autorizado_por}', estilos['center']))
    flow.append(Paragraph(
        'Firma autorizada · Departamento de RRHH',
        estilos['small'],
    ))
    flow.append(Spacer(1, 8 * mm))
    flow.append(Paragraph(
        f'Documento generado automáticamente por Harmoni ERP — '
        f'{date.today().strftime("%d/%m/%Y")}.',
        estilos['footer'],
    ))
    return flow


def _on_page(canvas, doc):
    """Header/footer en cada página."""
    canvas.saveState()
    # Header
    canvas.setFillColor(COLOR_PRIMARY)
    canvas.rect(0, A4[1] - 12 * mm, A4[0], 12 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.white)
    canvas.setFont('Helvetica-Bold', 10)
    canvas.drawString(15 * mm, A4[1] - 8 * mm, 'HARMONI · LEGAJO DIGITAL')
    # Footer page number
    canvas.setFillColor(COLOR_MUTED)
    canvas.setFont('Helvetica', 7)
    canvas.drawRightString(
        A4[0] - 15 * mm, 8 * mm,
        f'Página {doc.page}',
    )
    canvas.restoreState()


def build_legajo_pdf(personal, autorizado_por: str = 'Recursos Humanos') -> io.BytesIO:
    """Genera el PDF del legajo del trabajador y retorna un BytesIO."""
    from documentos.models import DocumentoTrabajador

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=15 * mm,
        title=f'Legajo - {getattr(personal, "apellidos_nombres", "Trabajador")}',
        author='Harmoni ERP',
    )

    docs = (
        DocumentoTrabajador.objects
        .filter(personal=personal)
        .exclude(estado='ANULADO')
        .select_related('tipo', 'tipo__categoria', 'subido_por')
        .order_by('tipo__categoria__orden', 'tipo__orden', '-version')
    )

    estilos = _estilos()
    flow: list = []
    flow.extend(_portada(personal, estilos))
    flow.extend(_tabla_resumen(docs, estilos))
    flow.extend(_detalle_por_categoria(docs, estilos))
    flow.extend(_pie(estilos, autorizado_por=autorizado_por))

    doc.build(flow, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf
