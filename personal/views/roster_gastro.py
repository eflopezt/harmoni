"""
Vistas para el Roster Quincenal Gastronomico.

Grid quincenal con drag&drop + validador 6+1 (DS 003-97-TR Art. 25).
"""
import json
from datetime import date, datetime, timedelta
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import (
    AsignacionRosterQuincena,
    Personal,
    SubArea,
    TurnoGastronomia,
)
from ..roster_validator import quincena_rango, validar_roster_quincena

try:
    from ..permissions import filtrar_personal
except Exception:  # pragma: no cover - fallback en setups parciales
    def filtrar_personal(user):
        return Personal.objects.all()


def _quincena_actual_default():
    hoy = date.today()
    sub_q = 1 if hoy.day <= 15 else 2
    quincena_idx = (hoy.month - 1) * 2 + sub_q
    return hoy.year, quincena_idx


def _quincena_navegacion(anio, quincena):
    """Devuelve (prev_anio, prev_q, next_anio, next_q)."""
    prev_q = quincena - 1
    prev_anio = anio
    if prev_q < 1:
        prev_q = 24
        prev_anio -= 1
    next_q = quincena + 1
    next_anio = anio
    if next_q > 24:
        next_q = 1
        next_anio += 1
    return prev_anio, prev_q, next_anio, next_q


@login_required
def roster_gastro_grid(request):
    """
    Grid quincenal: filas=trabajadores activos, columnas=15-16 dias.

    Query params:
        anio (int) — default ano actual
        quincena (int) — 1..24 (1=ene-q1, 2=ene-q2, 3=feb-q1, ...)
        empresa (int, opcional) — filtra por empresa
        area (int, opcional) — filtra por subarea
        buscar (str, opcional) — filtro nombre/dni
    """
    anio_def, quincena_def = _quincena_actual_default()
    anio = int(request.GET.get('anio') or anio_def)
    quincena = int(request.GET.get('quincena') or quincena_def)
    empresa_id = request.GET.get('empresa') or ''
    subarea_id = request.GET.get('area') or ''
    buscar = (request.GET.get('buscar') or '').strip()

    fecha_ini, fecha_fin, mes, sub_q, anio_ef = quincena_rango(anio, quincena)

    # Lista de fechas
    fechas = []
    f = fecha_ini
    while f <= fecha_fin:
        fechas.append(f)
        f += timedelta(days=1)

    # Personal scope
    personal_qs = filtrar_personal(request.user).filter(estado='Activo').select_related(
        'subarea', 'subarea__area', 'empresa'
    )
    if empresa_id:
        personal_qs = personal_qs.filter(empresa_id=empresa_id)
    if subarea_id:
        personal_qs = personal_qs.filter(subarea_id=subarea_id)
    if buscar:
        personal_qs = personal_qs.filter(
            Q(nro_doc__icontains=buscar) | Q(apellidos_nombres__icontains=buscar)
        )
    personal_qs = personal_qs.order_by('apellidos_nombres')

    # Asignaciones del rango
    asignaciones = (
        AsignacionRosterQuincena.objects
        .filter(personal__in=personal_qs, fecha__gte=fecha_ini, fecha__lte=fecha_fin)
        .select_related('turno', 'personal')
    )
    por_persona_fecha = {}
    for a in asignaciones:
        por_persona_fecha.setdefault(a.personal_id, {})[a.fecha] = a

    # Validacion 6+1 por persona en la quincena
    validaciones_por_persona = {}
    fechas_warning_por_persona = {}
    for p in personal_qs:
        res = validar_roster_quincena(p, fecha_ini, fecha_fin)
        validaciones_por_persona[p.id] = res
        fechas_warning_por_persona[p.id] = {e['fecha'] for e in res['errores']}

    # Construir filas
    filas = []
    for p in personal_qs:
        celdas = []
        for f in fechas:
            asig = por_persona_fecha.get(p.id, {}).get(f)
            es_warning = f in fechas_warning_por_persona.get(p.id, set())
            celdas.append({
                'fecha': f,
                'fecha_iso': f.isoformat(),
                'asig': asig,
                'turno': asig.turno if asig else None,
                'es_libre': bool(asig and asig.turno_id is None),
                'sin_asignar': asig is None,
                'warning': es_warning,
                'dow': f.weekday(),  # 0=lun, 6=dom
            })
        filas.append({
            'personal': p,
            'celdas': celdas,
            'valido': validaciones_por_persona[p.id]['valido'],
            'errores_count': len(validaciones_por_persona[p.id]['errores']),
        })

    # Paleta turnos
    turnos = TurnoGastronomia.objects.filter(activo=True).order_by('hora_entrada', 'codigo')

    # Filtros laterales
    try:
        from empresas.models import Empresa
        empresas = Empresa.objects.all().order_by('razon_social')
    except Exception:
        empresas = []
    subareas = SubArea.objects.filter(activa=True).select_related('area').order_by(
        'area__nombre', 'nombre'
    )

    prev_anio, prev_q, next_anio, next_q = _quincena_navegacion(anio, quincena)

    context = {
        'fechas': fechas,
        'filas': filas,
        'turnos': turnos,
        'anio': anio,
        'quincena': quincena,
        'mes': mes,
        'sub_quincena': sub_q,
        'fecha_ini': fecha_ini,
        'fecha_fin': fecha_fin,
        'empresas': empresas,
        'subareas': subareas,
        'empresa_id': empresa_id,
        'subarea_id': subarea_id,
        'buscar': buscar,
        'prev_anio': prev_anio,
        'prev_q': prev_q,
        'next_anio': next_anio,
        'next_q': next_q,
        'hoy': date.today(),
    }
    return render(request, 'personal/roster_gastro_grid.html', context)


@login_required
@require_POST
def roster_gastro_asignar(request):
    """AJAX: asigna o limpia turno en (personal, fecha)."""
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)

    personal_id = data.get('personal_id')
    fecha_str = data.get('fecha')
    turno_id = data.get('turno_id')  # None o int o 'libre'
    notas = data.get('notas', '')

    if not personal_id or not fecha_str:
        return JsonResponse({'success': False, 'error': 'Faltan personal_id o fecha'}, status=400)

    try:
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'success': False, 'error': 'Fecha invalida'}, status=400)

    personal = get_object_or_404(Personal, pk=personal_id)

    if turno_id in (None, '', 'null'):
        # Borrar asignacion (vuelve a "sin asignar")
        deleted, _ = AsignacionRosterQuincena.objects.filter(
            personal=personal, fecha=fecha
        ).delete()
        return JsonResponse({
            'success': True,
            'accion': 'borrado' if deleted else 'sin_cambio',
        })

    if turno_id == 'libre':
        turno = None
    else:
        turno = get_object_or_404(TurnoGastronomia, pk=turno_id, activo=True)

    asig, created = AsignacionRosterQuincena.objects.update_or_create(
        personal=personal, fecha=fecha,
        defaults={
            'turno': turno,
            'notas': notas,
            'creado_por': request.user if request.user.is_authenticated else None,
        },
    )

    # Revalidar quincena alrededor de la fecha
    fecha_ini = fecha - timedelta(days=6)
    fecha_fin = fecha + timedelta(days=6)
    val = validar_roster_quincena(personal, fecha_ini, fecha_fin)

    return JsonResponse({
        'success': True,
        'accion': 'creado' if created else 'actualizado',
        'asignacion_id': asig.id,
        'turno': {
            'id': turno.id, 'codigo': turno.codigo, 'nombre': turno.nombre,
            'color': turno.color, 'horario': turno.label_horario,
        } if turno else None,
        'es_libre': turno is None,
        'validacion': {
            'valido': val['valido'],
            'errores': [
                {'fecha': e['fecha'].isoformat(), 'mensaje': e['mensaje'],
                 'severidad': e['severidad']}
                for e in val['errores']
            ],
        },
    })


@login_required
@require_POST
def roster_gastro_asignar_bulk(request):
    """
    Bulk assign: asigna un turno (o libre) a multiples trabajadores en un rango.

    Body JSON:
        {
            'personal_ids': [1,2,3,...],
            'fecha_inicio': 'YYYY-MM-DD',
            'fecha_fin': 'YYYY-MM-DD',
            'turno_id': int | 'libre' | null,
            'solo_vacios': bool (opcional, default True),
        }
    """
    try:
        data = json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON invalido'}, status=400)

    personal_ids = data.get('personal_ids') or []
    if not personal_ids:
        return JsonResponse({'success': False, 'error': 'personal_ids vacio'}, status=400)

    try:
        f_ini = datetime.strptime(data['fecha_inicio'], '%Y-%m-%d').date()
        f_fin = datetime.strptime(data['fecha_fin'], '%Y-%m-%d').date()
    except (KeyError, ValueError):
        return JsonResponse({'success': False, 'error': 'Fechas invalidas'}, status=400)

    if f_ini > f_fin:
        return JsonResponse({'success': False, 'error': 'fecha_inicio > fecha_fin'}, status=400)

    turno_id = data.get('turno_id')
    solo_vacios = bool(data.get('solo_vacios', True))

    if turno_id in (None, '', 'libre'):
        turno = None
    else:
        try:
            turno = TurnoGastronomia.objects.get(pk=turno_id, activo=True)
        except TurnoGastronomia.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Turno no existe'}, status=404)

    personas = Personal.objects.filter(pk__in=personal_ids)
    creadas = 0
    actualizadas = 0
    saltadas = 0

    with transaction.atomic():
        for persona in personas:
            f = f_ini
            while f <= f_fin:
                existente = AsignacionRosterQuincena.objects.filter(
                    personal=persona, fecha=f
                ).first()
                if existente and solo_vacios:
                    saltadas += 1
                else:
                    _, created = AsignacionRosterQuincena.objects.update_or_create(
                        personal=persona, fecha=f,
                        defaults={
                            'turno': turno,
                            'creado_por': (
                                request.user if request.user.is_authenticated else None
                            ),
                        },
                    )
                    if created:
                        creadas += 1
                    else:
                        actualizadas += 1
                f += timedelta(days=1)

    return JsonResponse({
        'success': True,
        'creadas': creadas,
        'actualizadas': actualizadas,
        'saltadas': saltadas,
    })


@login_required
def roster_gastro_pdf(request):
    """Genera PDF imprimible del roster quincenal."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        )
    except ImportError:
        return HttpResponse('reportlab no instalado', status=500)

    anio_def, quincena_def = _quincena_actual_default()
    anio = int(request.GET.get('anio') or anio_def)
    quincena = int(request.GET.get('quincena') or quincena_def)
    fecha_ini, fecha_fin, mes, sub_q, _ = quincena_rango(anio, quincena)

    fechas = []
    f = fecha_ini
    while f <= fecha_fin:
        fechas.append(f)
        f += timedelta(days=1)

    personal_qs = filtrar_personal(request.user).filter(estado='Activo').order_by(
        'apellidos_nombres'
    )
    empresa_id = request.GET.get('empresa') or ''
    if empresa_id:
        personal_qs = personal_qs.filter(empresa_id=empresa_id)

    asignaciones = (
        AsignacionRosterQuincena.objects
        .filter(personal__in=personal_qs, fecha__gte=fecha_ini, fecha__lte=fecha_fin)
        .select_related('turno')
    )
    por_persona_fecha = {}
    for a in asignaciones:
        por_persona_fecha.setdefault(a.personal_id, {})[a.fecha] = a

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4),
        leftMargin=10 * mm, rightMargin=10 * mm,
        topMargin=10 * mm, bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    elements = []

    titulo = f'Roster Quincenal Gastronomico — Q{sub_q} {mes:02d}/{anio}'
    elements.append(Paragraph(f'<b>{titulo}</b>', styles['Title']))
    elements.append(Paragraph(
        f'Periodo: {fecha_ini.strftime("%d/%m/%Y")} a {fecha_fin.strftime("%d/%m/%Y")}',
        styles['Normal'],
    ))
    elements.append(Spacer(1, 4 * mm))

    # Tabla
    encabezado = ['Trabajador'] + [f.strftime('%d') for f in fechas]
    data_t = [encabezado]
    cell_colors = []  # (row, col, color)
    for r_idx, persona in enumerate(personal_qs, start=1):
        fila = [persona.apellidos_nombres[:28]]
        for c_idx, f in enumerate(fechas, start=1):
            asig = por_persona_fecha.get(persona.id, {}).get(f)
            if asig is None:
                fila.append('')
            elif asig.turno is None:
                fila.append('—')
            else:
                fila.append(asig.turno.codigo)
                try:
                    hexc = asig.turno.color.lstrip('#')
                    r = int(hexc[0:2], 16) / 255.0
                    g = int(hexc[2:4], 16) / 255.0
                    b = int(hexc[4:6], 16) / 255.0
                    cell_colors.append((r_idx, c_idx, colors.Color(r, g, b, alpha=0.5)))
                except Exception:
                    pass
        data_t.append(fila)

    col_widths = [55 * mm] + [
        (240 * mm - 55 * mm) / max(len(fechas), 1)
    ] * len(fechas)
    tabla = Table(data_t, colWidths=col_widths, repeatRows=1)
    ts = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ])
    for r, c, col in cell_colors:
        ts.add('BACKGROUND', (c, r), (c, r), col)
    tabla.setStyle(ts)
    elements.append(tabla)

    # Leyenda
    elements.append(Spacer(1, 4 * mm))
    leyenda = [['Codigo', 'Nombre', 'Horario']]
    for t in TurnoGastronomia.objects.filter(activo=True).order_by('hora_entrada'):
        leyenda.append([t.codigo, t.nombre, t.label_horario])
    leyenda.append(['—', 'Dia libre', ''])
    tabla_l = Table(leyenda, colWidths=[20 * mm, 60 * mm, 30 * mm])
    tabla_l.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
    ]))
    elements.append(Paragraph('<b>Leyenda de turnos</b>', styles['Heading4']))
    elements.append(tabla_l)

    doc.build(elements)
    pdf = buf.getvalue()
    buf.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="roster_gastro_{anio}_q{quincena}.pdf"'
    )
    return response


@login_required
def roster_gastro_validar(request):
    """AJAX: revalida una quincena entera. Util tras varios cambios."""
    anio_def, quincena_def = _quincena_actual_default()
    anio = int(request.GET.get('anio') or anio_def)
    quincena = int(request.GET.get('quincena') or quincena_def)
    fecha_ini, fecha_fin, _, _, _ = quincena_rango(anio, quincena)

    personal_qs = filtrar_personal(request.user).filter(estado='Activo')
    resultados = []
    for p in personal_qs:
        res = validar_roster_quincena(p, fecha_ini, fecha_fin)
        if not res['valido']:
            resultados.append({
                'personal_id': p.id,
                'personal_nombre': p.apellidos_nombres,
                'errores': [
                    {'fecha': e['fecha'].isoformat(), 'mensaje': e['mensaje'],
                     'severidad': e['severidad']}
                    for e in res['errores']
                ],
            })
    return JsonResponse({'success': True, 'resultados': resultados})
