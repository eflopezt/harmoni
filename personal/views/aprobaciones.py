"""
Vistas para el dashboard unificado de aprobaciones.
Agrega: Roster, Papeletas, Solicitudes HE, Justificaciones.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import date, timedelta
import json

from ..models import Area, Roster
from ..permissions import get_areas_responsable


@login_required
def dashboard_aprobaciones(request):
    """Dashboard unificado de aprobaciones para admin y responsables."""
    from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje

    # ── Permisos ──
    areas_responsable = Area.objects.none()
    is_admin = request.user.is_superuser

    if not is_admin:
        areas_responsable = get_areas_responsable(request.user)
        if not areas_responsable.exists():
            messages.error(request, 'No tiene permisos para ver el dashboard de aprobaciones.')
            return redirect('home')

    def filtro_area(qs, field='personal__subarea__area__in'):
        if is_admin:
            return qs
        return qs.filter(**{field: areas_responsable})

    # ── Filtros desde GET ──
    tab = request.GET.get('tab', 'todos')
    buscar = request.GET.get('buscar', '')

    # ── Querysets base (PENDIENTE) ──
    roster_qs = filtro_area(Roster.objects.filter(estado='pendiente'))
    papeletas_qs = filtro_area(RegistroPapeleta.objects.filter(estado='PENDIENTE'))
    solicitudes_qs = filtro_area(SolicitudHE.objects.filter(estado='PENDIENTE'))
    justificaciones_qs = filtro_area(JustificacionNoMarcaje.objects.filter(estado='PENDIENTE'))

    # Filtro de búsqueda
    if buscar:
        q_nombre = Q(personal__apellidos_nombres__icontains=buscar)
        q_doc = Q(personal__nro_doc__icontains=buscar)
        roster_qs = roster_qs.filter(q_nombre | q_doc)
        papeletas_qs = papeletas_qs.filter(q_nombre | q_doc)
        solicitudes_qs = solicitudes_qs.filter(q_nombre | q_doc)
        justificaciones_qs = justificaciones_qs.filter(q_nombre | q_doc)

    # ── Counts para badges de tabs ──
    cnt_roster = roster_qs.count()
    cnt_papeletas = papeletas_qs.count()
    cnt_solicitudes = solicitudes_qs.count()
    cnt_justificaciones = justificaciones_qs.count()
    cnt_total = cnt_roster + cnt_papeletas + cnt_solicitudes + cnt_justificaciones

    # ── Stats generales ──
    hoy = date.today()
    inicio_semana = hoy - timedelta(days=hoy.weekday())

    aprobados_hoy_roster = filtro_area(
        Roster.objects.filter(estado='aprobado', aprobado_en__date=hoy)
    ).count()
    aprobados_hoy_pap = filtro_area(
        RegistroPapeleta.objects.filter(estado='APROBADA', fecha_aprobacion=hoy)
    ).count()
    aprobados_hoy_sol = filtro_area(
        SolicitudHE.objects.filter(estado='APROBADA', fecha_aprobacion=hoy)
    ).count()
    aprobados_hoy_just = filtro_area(
        JustificacionNoMarcaje.objects.filter(estado='APROBADA', fecha_revision=hoy)
    ).count()

    stats = {
        'total_pendientes': cnt_total,
        'aprobados_hoy': aprobados_hoy_roster + aprobados_hoy_pap + aprobados_hoy_sol + aprobados_hoy_just,
        'cnt_roster': cnt_roster,
        'cnt_papeletas': cnt_papeletas,
        'cnt_solicitudes': cnt_solicitudes,
        'cnt_justificaciones': cnt_justificaciones,
    }

    # ── Cargar datos según tab ──
    roster_items = []
    papeleta_items = []
    solicitud_items = []
    justificacion_items = []

    if tab in ('todos', 'roster'):
        roster_items = list(roster_qs.select_related(
            'personal', 'personal__subarea__area', 'modificado_por',
        ).order_by('-actualizado_en')[:100])

    if tab in ('todos', 'papeletas'):
        papeleta_items = list(papeletas_qs.select_related(
            'personal', 'personal__subarea__area',
        ).order_by('-creado_en')[:100])

    if tab in ('todos', 'solicitudes'):
        solicitud_items = list(solicitudes_qs.select_related(
            'personal', 'personal__subarea__area',
        ).order_by('-creado_en')[:100])

    if tab in ('todos', 'justificaciones'):
        justificacion_items = list(justificaciones_qs.select_related(
            'personal', 'personal__subarea__area',
        ).order_by('-creado_en')[:100])

    context = {
        'stats': stats,
        'tab': tab,
        'buscar': buscar,
        'areas_responsable': areas_responsable,
        'roster_items': roster_items,
        'papeleta_items': papeleta_items,
        'solicitud_items': solicitud_items,
        'justificacion_items': justificacion_items,
    }
    return render(request, 'personal/dashboard_aprobaciones.html', context)


@login_required
def cambios_pendientes(request):
    """Vista simplificada - redirige al dashboard."""
    return redirect('dashboard_aprobaciones')


@login_required
@require_http_methods(["POST"])
def aprobar_cambio(request, pk):
    """Aprobar un cambio de roster pendiente."""
    roster = get_object_or_404(Roster, pk=pk)

    if not roster.puede_aprobar(request.user):
        return JsonResponse({
            'success': False,
            'error': 'No tiene permisos para aprobar este cambio'
        }, status=403)

    roster.estado = 'aprobado'
    roster.aprobado_por = request.user
    roster.aprobado_en = timezone.now()
    roster.save()

    messages.success(request, f'Cambio aprobado para {roster.personal} en {roster.fecha}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'mensaje': 'Cambio aprobado'})

    return redirect('cambios_pendientes')


@login_required
@require_http_methods(["POST"])
def rechazar_cambio(request, pk):
    """Rechazar un cambio de roster pendiente (elimina el cambio)."""
    roster = get_object_or_404(Roster, pk=pk)

    if not roster.puede_aprobar(request.user):
        return JsonResponse({
            'success': False,
            'error': 'No tiene permisos para rechazar este cambio'
        }, status=403)

    personal_nombre = str(roster.personal)
    fecha = roster.fecha

    roster.delete()

    messages.warning(request, f'Cambio rechazado y eliminado para {personal_nombre} en {fecha}')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'mensaje': 'Cambio rechazado'})

    return redirect('cambios_pendientes')


@login_required
@require_http_methods(["POST"])
def enviar_cambios_aprobacion(request):
    """Enviar cambios en borrador para aprobación."""
    if hasattr(request.user, 'personal_data'):
        personal = request.user.personal_data
        borradores = Roster.objects.filter(
            personal=personal,
            estado='borrador'
        )

        count = borradores.update(estado='pendiente')

        if count > 0:
            messages.success(request, f'{count} cambio(s) enviado(s) para aprobación')
        else:
            messages.info(request, 'No hay cambios pendientes de enviar')
    else:
        messages.error(request, 'No se pudo identificar su perfil de personal')

    return redirect('roster_matricial')


@login_required
@require_http_methods(["POST"])
def aprobar_lote(request):
    """Aprobar múltiples cambios en lote."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        if not ids:
            return JsonResponse({'success': False, 'error': 'No se proporcionaron IDs'}, status=400)

        rosters = Roster.objects.filter(pk__in=ids, estado='pendiente')

        aprobados = 0
        for roster in rosters:
            if roster.puede_aprobar(request.user):
                roster.estado = 'aprobado'
                roster.aprobado_por = request.user
                roster.aprobado_en = timezone.now()
                roster.save()
                aprobados += 1

        return JsonResponse({
            'success': True,
            'aprobados': aprobados,
            'mensaje': f'{aprobados} cambio(s) aprobado(s)'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def rechazar_lote(request):
    """Rechazar múltiples cambios en lote."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])

        if not ids:
            return JsonResponse({'success': False, 'error': 'No se proporcionaron IDs'}, status=400)

        rosters = Roster.objects.filter(pk__in=ids, estado='pendiente')

        rechazados = 0
        for roster in rosters:
            if roster.puede_aprobar(request.user):
                roster.delete()
                rechazados += 1

        return JsonResponse({
            'success': True,
            'rechazados': rechazados,
            'mensaje': f'{rechazados} cambio(s) rechazado(s)'
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
