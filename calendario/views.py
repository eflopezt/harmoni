"""
Vistas del Calendario Laboral Compartido.
Vista admin con todos los eventos y vista portal con eventos personales.
"""
import json
from datetime import date, datetime, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from personal.models import Area, Personal, Roster
from portal.views import _get_empleado

from .models import EventoCalendario

solo_admin = user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='login')


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _parse_date(value, default=None):
    """Convierte un string ISO a date. Retorna default si falla."""
    if not value:
        return default
    try:
        return datetime.strptime(value[:10], '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def _build_events(start, end, area_id=None, tipo_filter=None, personal_obj=None):
    """
    Construye la lista de eventos mezclando datos de multiples fuentes.
    Si personal_obj se proporciona, filtra solo eventos de ese trabajador.
    Retorna una lista de dicts listos para JSON.
    """
    events = []

    # Filtros de tipo (si se especifica)
    tipos_activos = set()
    if tipo_filter:
        tipos_activos = set(tipo_filter.split(','))
    else:
        tipos_activos = {'vacacion', 'permiso', 'feriado', 'cumpleanos', 'turno',
                         'reunion', 'otro', 'ausencia'}

    # ── 1. Eventos personalizados ──
    if tipos_activos & {'reunion', 'otro', 'vacacion', 'permiso', 'feriado', 'cumpleanos', 'turno'}:
        qs = EventoCalendario.objects.filter(
            fecha_inicio__lte=end,
            fecha_fin__gte=start,
        )
        if personal_obj:
            qs = qs.filter(
                Q(personal=personal_obj) | Q(personal__isnull=True, privado=False)
            )
        if area_id:
            qs = qs.filter(Q(area_id=area_id) | Q(area__isnull=True))
        if tipo_filter:
            tipo_upper = [t.upper() for t in tipos_activos]
            qs = qs.filter(tipo__in=tipo_upper)

        for ev in qs.select_related('personal', 'area'):
            personal_name = ev.personal.apellidos_nombres if ev.personal else ''
            events.append({
                'id': f'custom-{ev.pk}',
                'title': ev.titulo,
                'start': ev.fecha_inicio.isoformat(),
                'end': ev.fecha_fin.isoformat(),
                'color': ev.get_color(),
                'type': ev.tipo.lower(),
                'allDay': ev.todo_el_dia,
                'personal_name': personal_name,
                'description': ev.descripcion,
                'deletable': True,
                'pk': ev.pk,
            })

    # ── 2. Vacaciones aprobadas ──
    if 'vacacion' in tipos_activos:
        try:
            from vacaciones.models import SolicitudVacacion
            vac_qs = SolicitudVacacion.objects.filter(
                estado='APROBADA',
                fecha_inicio__lte=end,
                fecha_fin__gte=start,
            ).select_related('personal')
            if personal_obj:
                vac_qs = vac_qs.filter(personal=personal_obj)
            if area_id:
                vac_qs = vac_qs.filter(personal__subarea__area_id=area_id)

            for v in vac_qs:
                events.append({
                    'id': f'vac-{v.pk}',
                    'title': f'Vacaciones - {v.personal.apellidos_nombres}',
                    'start': v.fecha_inicio.isoformat(),
                    'end': v.fecha_fin.isoformat(),
                    'color': '#3b82f6',
                    'type': 'vacacion',
                    'allDay': True,
                    'personal_name': v.personal.apellidos_nombres,
                    'description': v.motivo or '',
                    'deletable': False,
                })
        except Exception:
            pass

    # ── 3. Permisos aprobados ──
    if 'permiso' in tipos_activos:
        try:
            from vacaciones.models import SolicitudPermiso
            perm_qs = SolicitudPermiso.objects.filter(
                estado='APROBADA',
                fecha_inicio__lte=end,
                fecha_fin__gte=start,
            ).select_related('personal', 'tipo')
            if personal_obj:
                perm_qs = perm_qs.filter(personal=personal_obj)
            if area_id:
                perm_qs = perm_qs.filter(personal__subarea__area_id=area_id)

            for p in perm_qs:
                events.append({
                    'id': f'perm-{p.pk}',
                    'title': f'{p.tipo.nombre} - {p.personal.apellidos_nombres}',
                    'start': p.fecha_inicio.isoformat(),
                    'end': p.fecha_fin.isoformat(),
                    'color': '#f59e0b',
                    'type': 'permiso',
                    'allDay': True,
                    'personal_name': p.personal.apellidos_nombres,
                    'description': p.motivo or '',
                    'deletable': False,
                })
        except Exception:
            pass

    # ── 3b. Ausencias reales: papeletas aprobadas (DM, licencias, DL, etc.) ──
    # Fuente única de ausencias (P1). Se excluyen las papeletas espejo de
    # SolicitudVacacion (ya pintadas por la capa 'vacacion').
    if 'ausencia' in tipos_activos:
        try:
            from asistencia.models import RegistroPapeleta
            pap_qs = RegistroPapeleta.objects.filter(
                estado__in=['APROBADA', 'EJECUTADA'],
                fecha_inicio__lte=end,
                fecha_fin__gte=start,
                personal__isnull=False,
            ).exclude(
                detalle__startswith='Auto: SolicitudVacacion',
            ).select_related('personal')
            if personal_obj:
                pap_qs = pap_qs.filter(personal=personal_obj)
            if area_id:
                pap_qs = pap_qs.filter(personal__subarea__area_id=area_id)

            for pa in pap_qs:
                events.append({
                    'id': f'pap-{pa.pk}',
                    'title': f'{pa.get_tipo_permiso_display()} - {pa.personal.apellidos_nombres}',
                    'start': pa.fecha_inicio.isoformat(),
                    'end': pa.fecha_fin.isoformat(),
                    'color': '#db2777',
                    'type': 'ausencia',
                    'allDay': True,
                    'personal_name': pa.personal.apellidos_nombres,
                    'description': pa.detalle or pa.get_origen_display(),
                    'deletable': False,
                })
        except Exception:
            pass

    # ── 4. Feriados ──
    if 'feriado' in tipos_activos:
        try:
            from asistencia.models import FeriadoCalendario
            fer_qs = FeriadoCalendario.objects.filter(
                fecha__gte=start,
                fecha__lte=end,
                activo=True,
            )
            for f in fer_qs:
                events.append({
                    'id': f'fer-{f.pk}',
                    'title': f.nombre,
                    'start': f.fecha.isoformat(),
                    'end': f.fecha.isoformat(),
                    'color': '#ef4444',
                    'type': 'feriado',
                    'allDay': True,
                    'personal_name': '',
                    'description': f.get_tipo_display(),
                    'deletable': False,
                })
        except Exception:
            pass

    # ── 5. Cumpleanos ──
    if 'cumpleanos' in tipos_activos:
        personal_qs = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__isnull=False,
        )
        if personal_obj:
            personal_qs = personal_qs.filter(pk=personal_obj.pk)
        if area_id:
            personal_qs = personal_qs.filter(subarea__area_id=area_id)

        current_year = start.year
        years_to_check = {current_year}
        if end.year != current_year:
            years_to_check.add(end.year)

        for p in personal_qs:
            for year in years_to_check:
                try:
                    birthday_this_year = p.fecha_nacimiento.replace(year=year)
                except ValueError:
                    # Feb 29 en ano no bisiesto
                    birthday_this_year = p.fecha_nacimiento.replace(year=year, day=28)

                if start <= birthday_this_year <= end:
                    edad = year - p.fecha_nacimiento.year
                    events.append({
                        'id': f'bday-{p.pk}-{year}',
                        'title': f'Cumpleanos - {p.apellidos_nombres}',
                        'start': birthday_this_year.isoformat(),
                        'end': birthday_this_year.isoformat(),
                        'color': '#22c55e',
                        'type': 'cumpleanos',
                        'allDay': True,
                        'personal_name': p.apellidos_nombres,
                        'description': f'Cumple {edad} anos',
                        'deletable': False,
                    })

    # ── 6. Roster (turnos) ──
    if 'turno' in tipos_activos:
        roster_qs = Roster.objects.filter(
            fecha__gte=start,
            fecha__lte=end,
        ).select_related('personal')
        if personal_obj:
            roster_qs = roster_qs.filter(personal=personal_obj)
        if area_id:
            roster_qs = roster_qs.filter(personal__subarea__area_id=area_id)

        # Agrupar registros consecutivos del mismo personal con el mismo codigo
        roster_list = list(roster_qs.order_by('personal', 'fecha'))
        grouped = []
        i = 0
        while i < len(roster_list):
            r = roster_list[i]
            group_start = r.fecha
            group_end = r.fecha
            personal_id = r.personal_id
            codigo = r.codigo

            j = i + 1
            while j < len(roster_list):
                rn = roster_list[j]
                if (rn.personal_id == personal_id
                        and rn.codigo == codigo
                        and rn.fecha == group_end + timedelta(days=1)):
                    group_end = rn.fecha
                    j += 1
                else:
                    break

            grouped.append({
                'personal': r.personal,
                'codigo': codigo,
                'start': group_start,
                'end': group_end,
            })
            i = j

        for g in grouped:
            color = '#8b5cf6'
            if g['codigo'] in ('DL', 'DLA'):
                color = '#06b6d4'
            elif g['codigo'] == 'TR':
                color = '#a855f7'

            events.append({
                'id': f'roster-{g["personal"].pk}-{g["start"].isoformat()}',
                'title': f'{g["codigo"]} - {g["personal"].apellidos_nombres}',
                'start': g['start'].isoformat(),
                'end': g['end'].isoformat(),
                'color': color,
                'type': 'turno',
                'allDay': True,
                'personal_name': g['personal'].apellidos_nombres,
                'description': f'Turno: {g["codigo"]}',
                'deletable': False,
            })

    return events


# ---------------------------------------------------------------------------
#  Admin views
# ---------------------------------------------------------------------------

def _get_stats_mes(year=None, month=None):
    """Calcula estadísticas rápidas del mes para el dashboard del calendario."""
    today = date.today()
    year = year or today.year
    month = month or today.month
    mes_inicio = date(year, month, 1)
    # Último día del mes
    if month == 12:
        mes_fin = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        mes_fin = date(year, month + 1, 1) - timedelta(days=1)

    stats = {
        'feriados_mes': 0,
        'vacaciones_activas': 0,
        'permisos_mes': 0,
        'cumpleanos_mes': 0,
        'eventos_custom': 0,
        'proximos_7': [],  # próximos 7 días: list de {titulo, fecha, tipo, color}
    }

    # Feriados del mes
    try:
        from asistencia.models import FeriadoCalendario
        stats['feriados_mes'] = FeriadoCalendario.objects.filter(
            fecha__gte=mes_inicio, fecha__lte=mes_fin, activo=True
        ).count()
    except Exception:
        pass

    # Vacaciones activas (estado APROBADA, EN_GOCE, solapan el mes)
    try:
        from vacaciones.models import SolicitudVacacion
        stats['vacaciones_activas'] = SolicitudVacacion.objects.filter(
            estado__in=('APROBADA', 'EN_GOCE'),
            fecha_inicio__lte=mes_fin,
            fecha_fin__gte=mes_inicio,
        ).count()
    except Exception:
        pass

    # Permisos del mes
    try:
        from vacaciones.models import SolicitudPermiso
        stats['permisos_mes'] = SolicitudPermiso.objects.filter(
            estado='APROBADA',
            fecha_inicio__lte=mes_fin,
            fecha_fin__gte=mes_inicio,
        ).count()
    except Exception:
        pass

    # Cumpleaños del mes
    try:
        stats['cumpleanos_mes'] = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__month=month,
        ).count()
    except Exception:
        pass

    # Eventos personalizados del mes
    stats['eventos_custom'] = EventoCalendario.objects.filter(
        fecha_inicio__lte=mes_fin, fecha_fin__gte=mes_inicio
    ).count()

    # Próximos 7 días de eventos
    prox_start = today
    prox_end = today + timedelta(days=7)
    proximos = _build_events(prox_start, prox_end)
    # Deduplicar por id, ordenar por start, tomar primeros 8
    seen = set()
    for ev in sorted(proximos, key=lambda e: e['start']):
        if ev['id'] not in seen:
            seen.add(ev['id'])
            stats['proximos_7'].append({
                'titulo': ev['title'],
                'fecha': ev['start'],
                'tipo': ev['type'],
                'color': ev['color'],
            })
        if len(stats['proximos_7']) >= 8:
            break

    return stats


@login_required
@solo_admin
def calendario_view(request):
    """Pagina principal del calendario (admin)."""
    areas = Area.objects.filter(activa=True).order_by('nombre')
    tipos = EventoCalendario.TIPO_CHOICES
    stats = _get_stats_mes()
    return render(request, 'calendario/calendario.html', {
        'areas': areas,
        'tipos': tipos,
        'stats': stats,
    })


@login_required
@solo_admin
@require_GET
def calendario_stats(request):
    """Endpoint AJAX para estadísticas del mes actual o solicitado."""
    try:
        year = int(request.GET.get('year', date.today().year))
        month = int(request.GET.get('month', date.today().month))
    except (ValueError, TypeError):
        year, month = date.today().year, date.today().month
    stats = _get_stats_mes(year, month)
    return JsonResponse(stats)


@login_required
@solo_admin
@require_GET
def calendario_eventos(request):
    """Endpoint AJAX que retorna eventos en formato JSON."""
    start = _parse_date(request.GET.get('start'), date.today().replace(day=1))
    end = _parse_date(request.GET.get('end'), (start + timedelta(days=42)))
    area_id = request.GET.get('area')
    tipo = request.GET.get('tipo')

    if area_id:
        try:
            area_id = int(area_id)
        except (ValueError, TypeError):
            area_id = None

    events = _build_events(start, end, area_id=area_id, tipo_filter=tipo)
    return JsonResponse(events, safe=False)


@login_required
@solo_admin
@require_GET
def calendario_disponibilidad(request):
    """Modo disponibilidad (F3): ¿quién está disponible el día X?

    Disponible = activo sin vacación aprobada, ni permiso aprobado, ni
    papeleta de ausencia aprobada/ejecutada que cubra la fecha.
    """
    fecha = _parse_date(request.GET.get('fecha'), date.today())
    area_id = request.GET.get('area') or None

    personal_qs = Personal.objects.filter(estado='Activo')
    if area_id:
        try:
            personal_qs = personal_qs.filter(subarea__area_id=int(area_id))
        except (ValueError, TypeError):
            pass
    total = personal_qs.count()
    ids_activos = set(personal_qs.values_list('pk', flat=True))

    ausentes = {}   # personal_id -> motivo (primera fuente encontrada)

    def _marcar(pares):
        for pid, motivo in pares:
            if pid in ids_activos and pid not in ausentes:
                ausentes[pid] = motivo

    try:
        from vacaciones.models import SolicitudVacacion
        _marcar(
            (v.personal_id, 'Vacaciones')
            for v in SolicitudVacacion.objects.filter(
                estado__in=['APROBADA', 'EN_GOCE'],
                fecha_inicio__lte=fecha, fecha_fin__gte=fecha,
            ).only('personal_id')
        )
    except Exception:
        pass
    try:
        from vacaciones.models import SolicitudPermiso
        _marcar(
            (p.personal_id,
             f'Permiso: {p.tipo.nombre}' if p.tipo_id else 'Permiso')
            for p in SolicitudPermiso.objects.filter(
                estado='APROBADA',
                fecha_inicio__lte=fecha, fecha_fin__gte=fecha,
            ).select_related('tipo')
        )
    except Exception:
        pass
    try:
        from asistencia.models import RegistroPapeleta
        _marcar(
            (pa.personal_id, pa.get_tipo_permiso_display())
            for pa in RegistroPapeleta.objects.filter(
                estado__in=['APROBADA', 'EJECUTADA'],
                fecha_inicio__lte=fecha, fecha_fin__gte=fecha,
                personal__isnull=False,
            )
        )
    except Exception:
        pass

    es_feriado = False
    try:
        from asistencia.services.feriados import feriados_efectivos
        es_feriado = fecha in feriados_efectivos(fecha, fecha)
    except Exception:
        pass

    nombres = {
        p.pk: p.apellidos_nombres
        for p in Personal.objects.filter(pk__in=list(ausentes)[:60])
    }
    detalle = sorted(
        ({'nombre': nombres[pid], 'motivo': motivo}
         for pid, motivo in ausentes.items() if pid in nombres),
        key=lambda x: x['nombre'],
    )

    return JsonResponse({
        'fecha': fecha.isoformat(),
        'total_activos': total,
        'ausentes': len(ausentes),
        'disponibles': total - len(ausentes),
        'es_feriado': es_feriado,
        'detalle': detalle,
    })


@login_required
@solo_admin
@require_POST
def evento_crear(request):
    """Crea un evento personalizado via AJAX."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON invalido'}, status=400)

    titulo = data.get('titulo', '').strip()
    if not titulo:
        return JsonResponse({'error': 'El titulo es obligatorio'}, status=400)

    fecha_inicio = _parse_date(data.get('fecha_inicio'))
    fecha_fin = _parse_date(data.get('fecha_fin'))
    if not fecha_inicio:
        return JsonResponse({'error': 'La fecha de inicio es obligatoria'}, status=400)
    if not fecha_fin:
        fecha_fin = fecha_inicio

    tipo = data.get('tipo', 'OTRO').upper()
    valid_types = [c[0] for c in EventoCalendario.TIPO_CHOICES]
    if tipo not in valid_types:
        tipo = 'OTRO'

    personal_id = data.get('personal_id')
    area_id = data.get('area_id')
    personal = None
    area = None

    if personal_id:
        try:
            personal = Personal.objects.get(pk=int(personal_id))
        except (Personal.DoesNotExist, ValueError, TypeError):
            pass

    if area_id:
        try:
            area = Area.objects.get(pk=int(area_id))
        except (Area.DoesNotExist, ValueError, TypeError):
            pass

    evento = EventoCalendario.objects.create(
        titulo=titulo,
        descripcion=data.get('descripcion', ''),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo=tipo,
        todo_el_dia=data.get('todo_el_dia', True),
        personal=personal,
        area=area,
        color=data.get('color', ''),
        recurrente=data.get('recurrente', False),
        creado_por=request.user,
        privado=data.get('privado', False),
    )

    return JsonResponse({
        'ok': True,
        'id': f'custom-{evento.pk}',
        'pk': evento.pk,
        'title': evento.titulo,
        'start': evento.fecha_inicio.isoformat(),
        'end': evento.fecha_fin.isoformat(),
        'color': evento.get_color(),
        'type': evento.tipo.lower(),
    })


@login_required
@solo_admin
@require_POST
def evento_eliminar(request, pk):
    """Elimina un evento personalizado via AJAX."""
    evento = get_object_or_404(EventoCalendario, pk=pk)
    evento.delete()
    return JsonResponse({'ok': True})


@login_required
@solo_admin
@require_GET
def calendario_export_ical(request):
    """Exporta eventos como archivo iCalendar (.ics)."""
    start = _parse_date(request.GET.get('start'), date.today().replace(day=1))
    end = _parse_date(request.GET.get('end'), (start + timedelta(days=42)))
    tipo = request.GET.get('tipo')

    events = _build_events(start, end, tipo_filter=tipo)

    lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Harmoni ERP//Calendario Laboral//ES',
        'CALSCALE:GREGORIAN',
        'METHOD:PUBLISH',
        'X-WR-CALNAME:Harmoni - Calendario Laboral',
        'X-WR-TIMEZONE:America/Lima',
    ]

    for ev in events:
        uid = ev['id'].replace(' ', '_')
        dtstart = ev['start'].replace('-', '')
        # Para fecha fin en iCal, DTEND es exclusivo, asi que sumamos 1 dia
        try:
            end_date = datetime.strptime(ev['end'][:10], '%Y-%m-%d').date() + timedelta(days=1)
            dtend = end_date.strftime('%Y%m%d')
        except (ValueError, TypeError):
            dtend = dtstart

        summary = ev['title'].replace(',', '\\,').replace(';', '\\;')
        desc = ev.get('description', '').replace('\n', '\\n').replace(',', '\\,').replace(';', '\\;')

        lines.extend([
            'BEGIN:VEVENT',
            f'UID:{uid}@harmoni.local',
            f'DTSTART;VALUE=DATE:{dtstart}',
            f'DTEND;VALUE=DATE:{dtend}',
            f'SUMMARY:{summary}',
            f'DESCRIPTION:{desc}',
            f'CATEGORIES:{ev["type"].upper()}',
            'TRANSP:TRANSPARENT',
            'END:VEVENT',
        ])

    lines.append('END:VCALENDAR')

    content = '\r\n'.join(lines)
    response = HttpResponse(content, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="harmoni_calendario.ics"'
    return response


# ---------------------------------------------------------------------------
#  Portal views
# ---------------------------------------------------------------------------

@login_required
def mi_calendario(request):
    """Vista de calendario para el portal del colaborador."""
    empleado = _get_empleado(request.user)
    return render(request, 'calendario/mi_calendario.html', {
        'empleado': empleado,
    })


@login_required
@require_GET
def mi_calendario_eventos(request):
    """Endpoint AJAX para eventos del colaborador."""
    empleado = _get_empleado(request.user)
    start = _parse_date(request.GET.get('start'), date.today().replace(day=1))
    end = _parse_date(request.GET.get('end'), (start + timedelta(days=42)))
    tipo = request.GET.get('tipo')

    events = _build_events(start, end, personal_obj=empleado, tipo_filter=tipo)
    return JsonResponse(events, safe=False)
