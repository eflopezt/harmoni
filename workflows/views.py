"""Workflow Engine - Vistas: bandeja de aprobaciones, detalle, decidir."""
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_POST, require_GET

from .models import EtapaFlujo, FlujoTrabajo, InstanciaFlujo, PasoFlujo
from . import services

solo_admin = user_passes_test(lambda u: u.is_superuser or u.is_staff)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_stats_usuario(usuario):
    """Calculates pending/urgent/overdue counts for the given user."""
    ahora = timezone.now()
    en_24h = ahora + timedelta(hours=24)

    qs = services.get_pendientes_usuario(usuario)
    pendientes_total = qs.count()
    urgentes = qs.filter(etapa_vence_en__lte=en_24h, etapa_vence_en__gt=ahora).count()
    vencidos = qs.filter(etapa_vence_en__lt=ahora).count()

    return {
        'pendientes_total': pendientes_total,
        'urgentes': urgentes,
        'vencidos': vencidos,
    }


def _classify_urgency(instancia, ahora=None):
    """Returns 'vencido'|'urgente'|'normal' for a given instancia."""
    if ahora is None:
        ahora = timezone.now()
    if not instancia.etapa_vence_en:
        return 'normal'
    if instancia.etapa_vence_en < ahora:
        return 'vencido'
    if instancia.etapa_vence_en < ahora + timedelta(hours=24):
        return 'urgente'
    return 'normal'


def _dias_esperando(instancia, ahora=None):
    if ahora is None:
        ahora = timezone.now()
    delta = ahora - instancia.iniciado_en
    return delta.days


# ---------------------------------------------------------------------------
# Bandeja de Aprobaciones
# ---------------------------------------------------------------------------

@login_required
def bandeja_aprobaciones(request):
    ahora = timezone.now()
    en_24h = ahora + timedelta(hours=24)

    qs_base = services.get_pendientes_usuario(request.user)

    # ----- Filters -----
    filtro = request.GET.get('filtro', 'todos')
    buscar = request.GET.get('q', '').strip()

    qs = qs_base
    if filtro == 'urgentes':
        qs = qs.filter(etapa_vence_en__lte=en_24h, etapa_vence_en__gt=ahora)
    elif filtro == 'vencidos':
        qs = qs.filter(etapa_vence_en__lt=ahora)
    elif filtro == 'resueltos_hoy':
        inicio_hoy = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        qs = InstanciaFlujo.objects.filter(
            solicitante__isnull=False,
            completado_en__gte=inicio_hoy,
            estado__in=['APROBADO', 'RECHAZADO'],
        ).select_related('flujo', 'etapa_actual', 'solicitante', 'content_type')

    if buscar:
        qs = qs.filter(
            solicitante__first_name__icontains=buscar
        ) | qs.filter(
            solicitante__last_name__icontains=buscar
        ) | qs.filter(
            solicitante__username__icontains=buscar
        )

    # ----- Counts for pills -----
    pendientes_total = qs_base.count()
    urgentes_count = qs_base.filter(etapa_vence_en__lte=en_24h, etapa_vence_en__gt=ahora).count()
    vencidos_count = qs_base.filter(etapa_vence_en__lt=ahora).count()

    # ----- Annotate urgency -----
    pendientes_list = list(qs.order_by('etapa_vence_en', '-iniciado_en'))
    for inst in pendientes_list:
        inst.urgencia = _classify_urgency(inst, ahora)
        inst.dias_esperando = _dias_esperando(inst, ahora)

    # ----- Pagination -----
    paginator = Paginator(pendientes_list, 15)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    # ----- Group by flujo type -----
    grupos = {}
    for inst in pendientes_list:
        key = inst.flujo.nombre
        grupos.setdefault(key, {'icono': inst.flujo.icono, 'count': 0})
        grupos[key]['count'] += 1

    # ----- Mis solicitudes -----
    mis_solicitudes = InstanciaFlujo.objects.filter(
        solicitante=request.user
    ).select_related('flujo', 'etapa_actual').order_by('-iniciado_en')[:20]

    return render(request, 'workflows/bandeja.html', {
        'titulo': 'Bandeja de Aprobaciones',
        'page_obj': page_obj,
        'mis_solicitudes': mis_solicitudes,
        'pendientes_total': pendientes_total,
        'urgentes_count': urgentes_count,
        'vencidos_count': vencidos_count,
        'filtro_activo': filtro,
        'buscar': buscar,
        'grupos': grupos,
        'ahora': ahora,
    })


# ---------------------------------------------------------------------------
# AJAX: Resumen para el notification bell
# ---------------------------------------------------------------------------

@login_required
@require_GET
def bandeja_resumen_ajax(request):
    """Returns {pendientes, urgentes, vencidos} JSON — cacheable 5 min."""
    stats = _get_stats_usuario(request.user)
    return JsonResponse(stats)


# ---------------------------------------------------------------------------
# AJAX: Diagrama de flujo (etapas + progreso)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def flujo_diagrama_ajax(request, pk):
    """Returns workflow stage list + completed step ids for timeline rendering."""
    flujo = get_object_or_404(FlujoTrabajo, pk=pk)

    # Optional: instancia_pk to show progress
    instancia_pk = request.GET.get('instancia')
    pasos_completados = []
    if instancia_pk:
        try:
            instancia = InstanciaFlujo.objects.get(pk=instancia_pk, flujo=flujo)
            pasos_completados = list(
                PasoFlujo.objects.filter(
                    instancia=instancia,
                    decision__in=['APROBADO', 'AUTO_APROBADO', 'DELEGADO'],
                ).values_list('etapa_id', flat=True)
            )
        except InstanciaFlujo.DoesNotExist:
            pass

    etapas = []
    for e in flujo.etapas.order_by('orden'):
        etapas.append({
            'id': e.pk,
            'nombre': e.nombre,
            'orden': e.orden,
            'tipo_aprobador': e.get_tipo_aprobador_display(),
            'tiempo_limite_horas': e.tiempo_limite_horas,
            'accion_vencimiento': e.get_accion_vencimiento_display(),
            'es_final': not flujo.etapas.filter(orden__gt=e.orden).exists(),
        })

    return JsonResponse({
        'flujo': flujo.nombre,
        'etapas': etapas,
        'pasos_completados': pasos_completados,
    })


# ---------------------------------------------------------------------------
# Instancia detalle (enhanced)
# ---------------------------------------------------------------------------

@login_required
def instancia_detalle(request, pk):
    ahora = timezone.now()

    instancia = get_object_or_404(
        InstanciaFlujo.objects.select_related(
            'flujo', 'etapa_actual', 'solicitante'
        ).prefetch_related(
            'pasos__etapa', 'pasos__aprobador',
            'flujo__etapas',
        ),
        pk=pk,
    )

    puede_decidir = instancia.puede_aprobar(request.user)
    pasos = list(instancia.pasos.order_by('fecha'))
    etapas_completadas_ids = {
        p.etapa_id for p in pasos
        if p.decision in ('APROBADO', 'AUTO_APROBADO', 'DELEGADO')
    }

    # Build timeline nodes
    todas_etapas = list(instancia.flujo.etapas.order_by('orden'))
    timeline = []
    for etapa in todas_etapas:
        paso_etapa = next((p for p in pasos if p.etapa_id == etapa.pk), None)
        if etapa.pk in etapas_completadas_ids:
            estado_etapa = 'completado'
        elif instancia.etapa_actual and etapa.pk == instancia.etapa_actual.pk:
            estado_etapa = 'actual'
        else:
            estado_etapa = 'pendiente'

        # Overdue check for current step
        es_vencido = (
            instancia.etapa_vence_en and
            instancia.etapa_vence_en < ahora and
            estado_etapa == 'actual'
        )

        dias_transcurridos = None
        if paso_etapa:
            ref = instancia.iniciado_en if not pasos.index(paso_etapa) else pasos[pasos.index(paso_etapa) - 1].fecha
            dias_transcurridos = (paso_etapa.fecha - instancia.iniciado_en).days

        timeline.append({
            'etapa': etapa,
            'estado': estado_etapa,
            'paso': paso_etapa,
            'es_vencido': es_vencido,
            'dias_transcurridos': dias_transcurridos,
        })

    # Days elapsed since started
    dias_total = (ahora - instancia.iniciado_en).days

    return render(request, 'workflows/detalle.html', {
        'titulo': f'Flujo: {instancia.flujo.nombre}',
        'instancia': instancia,
        'pasos': pasos,
        'timeline': timeline,
        'puede_decidir': puede_decidir,
        'requiere_comentario': (
            instancia.etapa_actual.requiere_comentario
            if instancia.etapa_actual else False
        ),
        'dias_total': dias_total,
        'ahora': ahora,
        'es_vencido_global': instancia.etapa_vence_en and instancia.etapa_vence_en < ahora,
    })


# ---------------------------------------------------------------------------
# Decidir (approve/reject)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def decidir_view(request, pk):
    instancia = get_object_or_404(InstanciaFlujo, pk=pk)
    decision = request.POST.get('decision')
    comentario = request.POST.get('comentario', '').strip()
    es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if decision not in ('APROBADO', 'RECHAZADO'):
        if es_ajax:
            return JsonResponse({'ok': False, 'error': 'Decisión inválida.'}, status=400)
        messages.error(request, 'Decision invalida.')
        return redirect('workflow_detalle', pk=pk)

    try:
        ok = services.decidir(instancia, request.user, decision, comentario)
        if ok:
            instancia.refresh_from_db()
            if decision == 'APROBADO':
                if instancia.estado == 'EN_PROCESO':
                    msg = 'Aprobado. La solicitud continua a la siguiente etapa.'
                else:
                    msg = 'Aprobacion completada. La solicitud fue aprobada definitivamente.'
                if es_ajax:
                    return JsonResponse({'ok': True, 'mensaje': msg, 'estado': instancia.estado})
                messages.success(request, msg)
            else:
                if es_ajax:
                    return JsonResponse({'ok': True, 'mensaje': 'Solicitud rechazada.',
                                         'estado': instancia.estado})
                messages.warning(request, 'Solicitud rechazada. El solicitante sera notificado.')
        else:
            if es_ajax:
                return JsonResponse(
                    {'ok': False, 'error': 'No tienes permiso para aprobar esta solicitud.'},
                    status=403)
            messages.error(request, 'No tienes permiso para aprobar esta solicitud.')
    except ValueError as e:
        if es_ajax:
            return JsonResponse({'ok': False, 'error': str(e)}, status=400)
        messages.error(request, str(e))

    return redirect('workflow_bandeja')


# ---------------------------------------------------------------------------
# Cancelar
# ---------------------------------------------------------------------------

@login_required
@require_POST
def cancelar_view(request, pk):
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, 'Solo administradores pueden cancelar flujos.')
        return redirect('workflow_bandeja')

    instancia = get_object_or_404(InstanciaFlujo, pk=pk)
    motivo = request.POST.get('motivo', '')
    services.cancelar_flujo(instancia, motivo)
    messages.info(request, 'Flujo cancelado.')
    return redirect('workflow_bandeja')


# ---------------------------------------------------------------------------
# Escalar paso vencido
# ---------------------------------------------------------------------------

@login_required
@require_POST
def escalar_paso(request, pk):
    """Manually escalate an overdue workflow instance to the fallback approver."""
    ahora = timezone.now()
    instancia = get_object_or_404(InstanciaFlujo, pk=pk)

    if instancia.estado != 'EN_PROCESO':
        messages.error(request, 'Solo se pueden escalar instancias en proceso.')
        return redirect('workflow_detalle', pk=instancia.pk)

    if not instancia.etapa_actual:
        messages.error(request, 'No hay etapa actual definida.')
        return redirect('workflow_detalle', pk=instancia.pk)

    if instancia.etapa_vence_en and instancia.etapa_vence_en >= ahora:
        messages.warning(request, 'La etapa aun no ha vencido.')
        return redirect('workflow_detalle', pk=instancia.pk)

    etapa = instancia.etapa_actual
    escalar_a = etapa.escalar_a

    if not escalar_a:
        # Fallback: notify all superusers
        from django.contrib.auth.models import User
        admins = User.objects.filter(is_superuser=True, is_active=True)
        nota = 'Escalado a administradores del sistema (sin usuario alterno configurado)'
    else:
        admins = None
        nota = f'Escalado manualmente a {escalar_a.get_full_name() or escalar_a.username} por vencimiento'

    # Log escalation
    PasoFlujo.objects.create(
        instancia=instancia,
        etapa=etapa,
        aprobador=request.user,
        decision='DELEGADO',
        comentario=nota,
    )

    # Extend deadline 24 h
    instancia.etapa_vence_en = ahora + timedelta(hours=24)
    instancia.save(update_fields=['etapa_vence_en'])

    # Notify
    try:
        from comunicaciones.services import NotificacionService
        targets = admins or [escalar_a]
        for dest in targets:
            NotificacionService.crear(
                usuario=dest,
                titulo=f'Escalacion de flujo: {instancia.flujo.nombre}',
                mensaje=(
                    f'La instancia #{instancia.pk} fue escalada a ti porque la etapa '
                    f'"{etapa.nombre}" vencio sin decision.'
                ),
                tipo='APROBACION',
                url=f'/workflows/bandeja/{instancia.pk}/',
            )
    except Exception:
        pass

    messages.success(request, f'Flujo escalado. {nota}')
    return redirect('workflow_detalle', pk=instancia.pk)


# ---------------------------------------------------------------------------
# Config: Flujos
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def flujos_config(request):
    flujos = FlujoTrabajo.objects.prefetch_related('etapas').all()
    from django.contrib.contenttypes.models import ContentType
    content_types = ContentType.objects.all().order_by('app_label', 'model')
    return render(request, 'workflows/config_panel.html', {
        'titulo': 'Configuracion de Flujos',
        'flujos': flujos,
        'content_types': content_types,
    })


@login_required
@solo_admin
def flujo_crear(request):
    from django.contrib.contenttypes.models import ContentType
    if request.method == 'POST':
        ct_id = request.POST.get('content_type')
        nombre = request.POST.get('nombre', '').strip()
        if not ct_id or not nombre:
            messages.error(request, 'Nombre y modelo son requeridos.')
            return redirect('workflow_crear')
        FlujoTrabajo.objects.create(
            nombre=nombre,
            descripcion=request.POST.get('descripcion', ''),
            content_type_id=ct_id,
            campo_trigger=request.POST.get('campo_trigger', 'estado'),
            valor_trigger=request.POST.get('valor_trigger', ''),
            campo_resultado=request.POST.get('campo_resultado', 'estado'),
            valor_aprobado=request.POST.get('valor_aprobado', 'Aprobado'),
            valor_rechazado=request.POST.get('valor_rechazado', 'Rechazado'),
        )
        messages.success(request, f'Flujo "{nombre}" creado. Ahora agrega las etapas.')
        return redirect('workflow_config')
    # Solo modelos del dominio del ERP — ocultamos los internos de Django.
    APPS_OCULTAS = {'admin', 'contenttypes', 'sessions', 'auth', 'sites',
                    'messages', 'staticfiles', 'django_celery_beat',
                    'django_celery_results', 'rest_framework', 'core'}
    MODELOS_RECOMENDADOS = [
        # (app_label, model, etiqueta amigable, valor_trigger sugerido)
        ('vacaciones',    'solicitudvacacion',    'Solicitud de Vacaciones',           'Pendiente'),
        ('vacaciones',    'solicitudpermiso',     'Solicitud de Permiso',              'Pendiente'),
        ('prestamos',     'prestamo',             'Préstamo a Trabajador',             'Solicitado'),
        ('asistencia',    'solicitudhe',          'Autorización de Horas Extra',       'Pendiente'),
        ('asistencia',    'registropapeleta',     'Papeleta de Salida',                'Pendiente'),
        ('disciplinaria', 'medidadisciplinaria',  'Medida Disciplinaria',              'Borrador'),
        ('reclutamiento', 'oferta',               'Oferta Laboral',                    'Pendiente'),
        ('personal',      'contrato',             'Contrato (renovación/cese)',        'Borrador'),
    ]
    cts_all = ContentType.objects.exclude(
        app_label__in=APPS_OCULTAS
    ).order_by('app_label', 'model')
    # Marca recomendados primero
    cts_dict = {(ct.app_label, ct.model): ct for ct in cts_all}
    recomendados = []
    for app, model, label, trigger in MODELOS_RECOMENDADOS:
        ct = cts_dict.pop((app, model), None)
        if ct:
            recomendados.append({'ct': ct, 'label': label, 'valor_trigger': trigger})
    otros = list(cts_dict.values())
    return render(request, 'workflows/flujo_form.html', {
        'titulo': 'Nuevo Flujo',
        'content_types_recomendados': recomendados,
        'content_types_otros': otros,
    })


@login_required
@solo_admin
def etapa_crear(request, flujo_pk):
    from django.contrib.auth.models import User, Group
    from django.db.models import Max
    flujo = get_object_or_404(FlujoTrabajo, pk=flujo_pk)
    if request.method == 'POST':
        try:
            tiempo_limite = int(request.POST.get('tiempo_limite_horas', 72) or 72)
        except (ValueError, TypeError):
            tiempo_limite = 72
        ultimo_orden = flujo.etapas.aggregate(m=Max('orden'))['m'] or 0
        EtapaFlujo.objects.create(
            flujo=flujo,
            orden=ultimo_orden + 1,
            nombre=request.POST.get('nombre', '').strip(),
            tipo_aprobador=request.POST.get('tipo_aprobador', 'SUPERUSER'),
            aprobador_usuario_id=request.POST.get('aprobador_usuario') or None,
            aprobador_grupo_id=request.POST.get('aprobador_grupo') or None,
            tiempo_limite_horas=tiempo_limite,
            accion_vencimiento=request.POST.get('accion_vencimiento', 'ESPERAR'),
            requiere_comentario=request.POST.get('requiere_comentario') == '1',
            notificar_solicitante_al_decidir=True,
        )
        messages.success(request, 'Etapa agregada.')
        return redirect('workflow_config')
    usuarios = User.objects.filter(is_active=True).order_by('username')
    grupos = Group.objects.all().order_by('name')
    return render(request, 'workflows/etapa_form.html', {
        'titulo': f'Nueva etapa - {flujo.nombre}',
        'flujo': flujo,
        'usuarios': usuarios,
        'grupos': grupos,
        'tipo_choices': EtapaFlujo.TIPO_APROBADOR,
        'venc_choices': EtapaFlujo.ACCION_VENCIMIENTO,
    })


@login_required
@solo_admin
@require_POST
def flujo_toggle_activo(request, pk):
    """Activa o desactiva un flujo de trabajo."""
    flujo = get_object_or_404(FlujoTrabajo, pk=pk)
    flujo.activo = not flujo.activo
    flujo.save(update_fields=['activo'])
    try:
        from .signals import conectar_flujos_activos
        conectar_flujos_activos()
    except Exception:
        pass
    estado = 'activado' if flujo.activo else 'desactivado'
    messages.success(request, f'Flujo "{flujo.nombre}" {estado}.')
    return redirect('workflow_config')
