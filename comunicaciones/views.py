"""
Vistas del módulo Comunicaciones Inteligentes.

- Admin: panel de notificaciones, plantillas CRUD, comunicados masivos, config SMTP
- Portal: mis notificaciones, mis comunicados
"""
import json
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from comunicaciones.models import (
    ComunicadoMasivo, ConfiguracionSMTP, ConfirmacionLectura,
    Notificacion, PlantillaNotificacion, PreferenciaNotificacion,
)
from comunicaciones.services import NotificacionService
from core.audit import log_create, log_update
from personal.models import Area, Personal

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


def _get_empleado(user):
    """Retorna el Personal vinculado al usuario, o None."""
    return getattr(user, 'personal_data', None)


# ═══════════════════════════════════════════════════════════════
# ADMIN — NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def notificaciones_panel(request):
    """Dashboard de notificaciones: stats + analítica + tabla reciente con filtros."""
    ahora = timezone.now()
    hoy = ahora.date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    inicio_mes = hoy.replace(day=1)

    # ── Stats base ──────────────────────────────────────────────────────────────
    qs_all = Notificacion.objects.all()
    total_notifs = qs_all.count()
    enviadas_hoy = qs_all.filter(enviada_en__date=hoy, estado='ENVIADA').count()
    enviadas_semana = qs_all.filter(enviada_en__date__gte=inicio_semana, estado='ENVIADA').count()
    enviadas_mes = qs_all.filter(enviada_en__date__gte=inicio_mes, estado='ENVIADA').count()
    fallidas = qs_all.filter(estado='FALLIDA').count()
    pendientes_in_app = qs_all.filter(tipo='IN_APP', estado='ENVIADA').count()

    # ── Tasa de lectura ─────────────────────────────────────────────────────────
    tasa_lectura_pct = 0
    try:
        total_enviadas = qs_all.filter(estado__in=['ENVIADA', 'LEIDA']).count()
        leidas = qs_all.filter(estado='LEIDA').count()
        if total_enviadas > 0:
            tasa_lectura_pct = round(leidas / total_enviadas * 100, 1)
    except Exception:
        pass

    # ── Comunicados recientes ────────────────────────────────────────────────────
    comunicados_recientes = []
    total_comunicados = 0
    try:
        comunicados_recientes = list(ComunicadoMasivo.objects.select_related('creado_por').order_by('-creado_en')[:5])
        total_comunicados = ComunicadoMasivo.objects.filter(estado='ENVIADO').count()
    except Exception:
        pass

    # ── Distribución por tipo (Email vs In-App) ──────────────────────────────────
    notifs_por_tipo_json = '[]'
    try:
        TIPO_COLORS = {'EMAIL': '#0f766e', 'IN_APP': '#5eead4'}
        tipo_qs = (
            qs_all.values('tipo')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        notifs_por_tipo_json = json.dumps([
            {
                'label': item['tipo'],
                'value': item['total'],
                'color': TIPO_COLORS.get(item['tipo'], '#94a3b8'),
            }
            for item in tipo_qs
        ])
    except Exception:
        pass

    # ── Tendencia últimos 6 meses ────────────────────────────────────────────────
    notifs_trend_json = '[]'
    try:
        MESES_ES = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
        trend_data = []
        # Build 6 month buckets without dateutil (use calendar arithmetic)
        import calendar
        for i in range(5, -1, -1):
            # Walk back i months from current month
            year = ahora.year
            month = ahora.month - i
            while month <= 0:
                month += 12
                year -= 1
            # First day of that month (aware)
            first_day = ahora.replace(
                year=year, month=month, day=1,
                hour=0, minute=0, second=0, microsecond=0
            )
            # Last day of that month
            last_day_num = calendar.monthrange(year, month)[1]
            if i == 0:
                last_day = ahora
            else:
                last_day = ahora.replace(
                    year=year, month=month, day=last_day_num,
                    hour=23, minute=59, second=59, microsecond=999999
                )
            count = qs_all.filter(creado_en__gte=first_day, creado_en__lte=last_day).count()
            trend_data.append({'label': MESES_ES[month - 1], 'total': count})
        notifs_trend_json = json.dumps(trend_data)
    except Exception:
        pass

    # ── Top 5 destinatarios más notificados ─────────────────────────────────────
    destinatarios_top = []
    try:
        top_qs = (
            qs_all.filter(destinatario__isnull=False)
            .values('destinatario__id', 'destinatario__apellidos_nombres')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )
        destinatarios_top = [
            {
                'nombre': item['destinatario__apellidos_nombres'] or '(sin nombre)',
                'total': item['total'],
            }
            for item in top_qs
        ]
    except Exception:
        pass

    # ── Filtros / tabla ──────────────────────────────────────────────────────────
    filtro_tipo = request.GET.get('tipo', '')
    filtro_estado = request.GET.get('estado', '')
    buscar = request.GET.get('q', '')

    qs = qs_all.select_related('destinatario', 'plantilla')
    if filtro_tipo:
        qs = qs.filter(tipo=filtro_tipo)
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)
    if buscar:
        qs = qs.filter(
            Q(asunto__icontains=buscar) |
            Q(destinatario__apellidos_nombres__icontains=buscar) |
            Q(destinatario_email__icontains=buscar)
        )

    notificaciones = qs[:100]

    return render(request, 'comunicaciones/notificaciones_panel.html', {
        'titulo': 'Notificaciones',
        # stats
        'total_notifs': total_notifs,
        'enviadas_hoy': enviadas_hoy,
        'enviadas_semana': enviadas_semana,
        'enviadas_mes': enviadas_mes,
        'fallidas': fallidas,
        'pendientes_in_app': pendientes_in_app,
        'total_comunicados': total_comunicados,
        'tasa_lectura_pct': tasa_lectura_pct,
        # analytics JSON
        'notifs_por_tipo_json': notifs_por_tipo_json,
        'notifs_trend_json': notifs_trend_json,
        # tables
        'comunicados_recientes': comunicados_recientes,
        'destinatarios_top': destinatarios_top,
        # filters
        'filtro_tipo': filtro_tipo,
        'filtro_estado': filtro_estado,
        'buscar': buscar,
        'notificaciones': notificaciones,
    })


# ═══════════════════════════════════════════════════════════════
# ADMIN — PLANTILLAS
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def plantillas_panel(request):
    """Lista de plantillas de notificación."""
    plantillas = PlantillaNotificacion.objects.all()

    filtro_modulo = request.GET.get('modulo', '')
    if filtro_modulo:
        plantillas = plantillas.filter(modulo=filtro_modulo)

    return render(request, 'comunicaciones/plantillas_panel.html', {
        'titulo': 'Plantillas de Notificación',
        'plantillas': plantillas,
        'filtro_modulo': filtro_modulo,
        'modulos': PlantillaNotificacion.MODULO_CHOICES,
    })


@login_required
@solo_admin
def plantilla_crear(request):
    """Crear nueva plantilla de notificación."""
    if request.method == 'POST':
        plantilla = PlantillaNotificacion.objects.create(
            nombre=request.POST.get('nombre', ''),
            codigo=request.POST.get('codigo', ''),
            asunto_template=request.POST.get('asunto_template', ''),
            cuerpo_template=request.POST.get('cuerpo_template', ''),
            tipo=request.POST.get('tipo', 'IN_APP'),
            modulo=request.POST.get('modulo', 'SISTEMA'),
            activa=request.POST.get('activa') == 'on',
            variables_disponibles=request.POST.get('variables_disponibles', ''),
        )
        log_create(request, plantilla)
        messages.success(request, f'Plantilla "{plantilla.nombre}" creada.')
        return redirect('com_plantillas_panel')

    return render(request, 'comunicaciones/plantilla_form.html', {
        'titulo': 'Nueva Plantilla',
        'modulos': PlantillaNotificacion.MODULO_CHOICES,
        'tipos': PlantillaNotificacion.TIPO_CHOICES,
        'es_nuevo': True,
    })


@login_required
@solo_admin
def plantilla_editar(request, pk):
    """Editar plantilla existente."""
    plantilla = get_object_or_404(PlantillaNotificacion, pk=pk)

    if request.method == 'POST':
        cambios = {}
        campos = ['nombre', 'codigo', 'asunto_template', 'cuerpo_template',
                   'tipo', 'modulo', 'variables_disponibles']
        for campo in campos:
            nuevo_val = request.POST.get(campo, '')
            viejo_val = getattr(plantilla, campo)
            if nuevo_val != viejo_val:
                cambios[campo] = {'old': viejo_val, 'new': nuevo_val}
            setattr(plantilla, campo, nuevo_val)

        nueva_activa = request.POST.get('activa') == 'on'
        if nueva_activa != plantilla.activa:
            cambios['activa'] = {'old': plantilla.activa, 'new': nueva_activa}
        plantilla.activa = nueva_activa

        plantilla.save()
        if cambios:
            log_update(request, plantilla, cambios)
        messages.success(request, f'Plantilla "{plantilla.nombre}" actualizada.')
        return redirect('com_plantillas_panel')

    # Preview: renderizar con datos de ejemplo
    preview_asunto = ''
    preview_cuerpo = ''
    try:
        from django.template import Template, Context
        sample = {
            'nombre': 'Juan Pérez',
            'fecha': '01/03/2026',
            'cargo': 'Analista',
            'empresa': 'Harmoni Corp',
            'titulo': 'Ejemplo de comunicado',
            'url': '#',
            'fecha_inicio': '15/03/2026',
            'fecha_fin': '22/03/2026',
            'motivo': 'Motivo de ejemplo',
            'monto': 'S/ 1,500.00',
        }
        ctx = Context(sample)
        preview_asunto = Template(plantilla.asunto_template).render(ctx)
        preview_cuerpo = Template(plantilla.cuerpo_template).render(ctx)
    except Exception:
        pass

    return render(request, 'comunicaciones/plantilla_form.html', {
        'titulo': f'Editar: {plantilla.nombre}',
        'plantilla': plantilla,
        'modulos': PlantillaNotificacion.MODULO_CHOICES,
        'tipos': PlantillaNotificacion.TIPO_CHOICES,
        'es_nuevo': False,
        'preview_asunto': preview_asunto,
        'preview_cuerpo': preview_cuerpo,
    })


# ═══════════════════════════════════════════════════════════════
# ADMIN — COMUNICADOS MASIVOS
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def comunicados_panel(request):
    """Lista de comunicados masivos con stats y filtros."""
    qs = ComunicadoMasivo.objects.select_related('creado_por').all()

    filtro_tipo = request.GET.get('tipo', '')
    filtro_estado = request.GET.get('estado', '')
    if filtro_tipo:
        qs = qs.filter(tipo=filtro_tipo)
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)

    # Stats globales
    total = ComunicadoMasivo.objects.count()
    enviados = ComunicadoMasivo.objects.filter(estado='ENVIADO').count()
    borradores = ComunicadoMasivo.objects.filter(estado='BORRADOR').count()

    return render(request, 'comunicaciones/comunicados_panel.html', {
        'titulo': 'Comunicados Masivos',
        'comunicados': qs[:50],
        'total': total,
        'enviados': enviados,
        'borradores': borradores,
        'filtro_tipo': filtro_tipo,
        'filtro_estado': filtro_estado,
    })


@login_required
@solo_admin
def comunicado_crear(request):
    """Crear nuevo comunicado masivo."""
    if request.method == 'POST':
        comunicado = ComunicadoMasivo(
            titulo=request.POST.get('titulo', ''),
            cuerpo=request.POST.get('cuerpo', ''),
            tipo=request.POST.get('tipo', 'COMUNICADO'),
            destinatarios_tipo=request.POST.get('destinatarios_tipo', 'TODOS'),
            grupo=request.POST.get('grupo', ''),
            requiere_confirmacion=request.POST.get('requiere_confirmacion') == 'on',
            creado_por=request.user,
        )

        # Programar envío
        programado = request.POST.get('programado_para', '')
        if programado:
            from django.utils.dateparse import parse_datetime
            dt = parse_datetime(programado)
            if dt:
                comunicado.programado_para = dt
                comunicado.estado = 'PROGRAMADO'

        comunicado.save()

        # M2M: áreas
        area_ids = request.POST.getlist('areas')
        if area_ids:
            comunicado.areas.set(area_ids)

        # M2M: personal individual
        personal_ids = request.POST.getlist('personal_individual')
        if personal_ids:
            comunicado.personal_individual.set(personal_ids)

        # Adjunto
        if request.FILES.get('adjunto'):
            comunicado.adjunto = request.FILES['adjunto']
            comunicado.save(update_fields=['adjunto'])

        log_create(request, comunicado)
        messages.success(request, f'Comunicado "{comunicado.titulo}" creado.')
        return redirect('com_comunicado_detalle', pk=comunicado.pk)

    return render(request, 'comunicaciones/comunicado_crear.html', {
        'titulo': 'Nuevo Comunicado',
        'areas': Area.objects.filter(activa=True).order_by('nombre'),
        'personal': Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
        'tipos': ComunicadoMasivo.TIPO_CHOICES,
        'dest_tipos': ComunicadoMasivo.DESTINATARIOS_TIPO_CHOICES,
        'grupos': ComunicadoMasivo.GRUPO_CHOICES,
    })


@login_required
@solo_admin
def comunicado_detalle(request, pk):
    """Detalle de comunicado con estadísticas de distribución."""
    comunicado = get_object_or_404(
        ComunicadoMasivo.objects.prefetch_related('areas'),
        pk=pk,
    )
    confirmaciones = comunicado.confirmaciones.select_related('personal').order_by('-fecha_lectura')

    return render(request, 'comunicaciones/comunicado_detalle.html', {
        'titulo': comunicado.titulo,
        'comunicado': comunicado,
        'confirmaciones': confirmaciones,
        'total_dest': comunicado.total_destinatarios,
        'confirmados': comunicado.confirmaciones_recibidas,
        'tasa': comunicado.tasa_lectura,
    })


@login_required
@solo_admin
@require_POST
def comunicado_enviar(request, pk):
    """Envía el comunicado a todos los destinatarios."""
    comunicado = get_object_or_404(ComunicadoMasivo, pk=pk)

    if comunicado.estado == 'ENVIADO':
        messages.warning(request, 'Este comunicado ya fue enviado.')
        return redirect('com_comunicado_detalle', pk=pk)

    total = NotificacionService.enviar_masivo(comunicado)
    log_update(request, comunicado, {
        'estado': {'old': 'BORRADOR', 'new': 'ENVIADO'},
    })
    messages.success(request, f'Comunicado enviado a {total} destinatarios.')
    return redirect('com_comunicado_detalle', pk=pk)


# ═══════════════════════════════════════════════════════════════
# ADMIN — CONFIGURACIÓN SMTP
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def config_smtp(request):
    """Formulario de configuración SMTP."""
    config = ConfiguracionSMTP.get()

    if request.method == 'POST':
        cambios = {}
        campos_str = ['smtp_host', 'smtp_user', 'smtp_password',
                       'email_from', 'email_reply_to', 'firma_html']
        for campo in campos_str:
            nuevo = request.POST.get(campo, '')
            viejo = getattr(config, campo)
            if nuevo != viejo:
                cambios[campo] = {
                    'old': '***' if 'password' in campo else viejo,
                    'new': '***' if 'password' in campo else nuevo,
                }
            setattr(config, campo, nuevo)

        puerto = request.POST.get('smtp_port', '587')
        try:
            puerto_int = int(puerto)
        except ValueError:
            puerto_int = 587
        if puerto_int != config.smtp_port:
            cambios['smtp_port'] = {'old': config.smtp_port, 'new': puerto_int}
        config.smtp_port = puerto_int

        tls = request.POST.get('smtp_use_tls') == 'on'
        if tls != config.smtp_use_tls:
            cambios['smtp_use_tls'] = {'old': config.smtp_use_tls, 'new': tls}
        config.smtp_use_tls = tls

        activa = request.POST.get('activa') == 'on'
        if activa != config.activa:
            cambios['activa'] = {'old': config.activa, 'new': activa}
        config.activa = activa

        config.save()
        if cambios:
            log_update(request, config, cambios)
        messages.success(request, 'Configuración SMTP guardada.')
        return redirect('com_config_smtp')

    return render(request, 'comunicaciones/config_smtp.html', {
        'titulo': 'Configuración SMTP',
        'config': config,
    })


@login_required
@solo_admin
@require_POST
def test_smtp(request):
    """Prueba de conexión SMTP (AJAX)."""
    config = ConfiguracionSMTP.get()
    ok, mensaje = config.test_connection()
    return JsonResponse({'ok': ok, 'mensaje': mensaje})


# ═══════════════════════════════════════════════════════════════
# PORTAL — MIS NOTIFICACIONES
# ═══════════════════════════════════════════════════════════════

@login_required
def mis_notificaciones(request):
    """Portal: bandeja de notificaciones in-app del colaborador con paginación y agrupación."""
    from django.core.paginator import Paginator

    empleado = _get_empleado(request.user)
    if not empleado:
        messages.warning(request, 'No tienes un perfil de empleado vinculado.')
        return redirect('portal_home')

    qs_all = Notificacion.objects.filter(
        destinatario=empleado,
        tipo='IN_APP',
    ).order_by('-creado_en')

    # Filtro por tipo (desde metadata)
    filtro_tipo = request.GET.get('tipo', '')

    # Marcar todas como leídas
    if request.method == 'POST' and request.POST.get('accion') == 'marcar_todas':
        qs_all.filter(estado__in=['ENVIADA', 'PENDIENTE']).update(
            estado='LEIDA', leida_en=timezone.now()
        )
        messages.success(request, 'Todas las notificaciones marcadas como leídas.')
        return redirect(request.path)

    no_leidas = qs_all.filter(estado__in=['ENVIADA', 'PENDIENTE']).count()

    # Agrupar: extraemos tipo_notificacion de metadata para separar grupos
    GRUPOS_CONFIG = {
        'ALERTA': {
            'label': 'Alertas',
            'icono': 'fa-triangle-exclamation',
            'color': '#dc2626',
            'bg': '#fef2f2',
            'badge': 'bg-danger',
        },
        'SISTEMA': {
            'label': 'Sistema',
            'icono': 'fa-gear',
            'color': '#0f766e',
            'bg': '#f0fdfa',
            'badge': 'bg-info text-dark',
        },
        'INFO': {
            'label': 'Información',
            'icono': 'fa-circle-info',
            'color': '#2563eb',
            'bg': '#eff6ff',
            'badge': 'bg-primary',
        },
    }

    # Paginación
    paginator = Paginator(qs_all, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    # Enriquecer notificaciones con config de tipo
    notifs_enriquecidas = []
    for n in page_obj:
        meta = n.metadata or {}
        tipo_notif = meta.get('tipo_notificacion', 'INFO')
        cfg = GRUPOS_CONFIG.get(tipo_notif, GRUPOS_CONFIG['INFO'])
        notifs_enriquecidas.append({
            'notif': n,
            'tipo_notif': tipo_notif,
            'cfg': cfg,
            'icono': meta.get('icono', cfg['icono']),
            'color': meta.get('color', cfg['color']),
            'url': meta.get('url', '#'),
        })

    return render(request, 'comunicaciones/mis_notificaciones.html', {
        'titulo': 'Mis Notificaciones',
        'page_obj': page_obj,
        'notificaciones': notifs_enriquecidas,
        'no_leidas': no_leidas,
        'empleado': empleado,
        'grupos_config': GRUPOS_CONFIG,
        'filtro_tipo': filtro_tipo,
        'total': qs_all.count(),
    })


@login_required
@require_POST
def notificacion_leer(request, pk):
    """AJAX: marca una notificación in-app como leída."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil'})

    notif = get_object_or_404(Notificacion, pk=pk, destinatario=empleado)
    ok = NotificacionService.marcar_leida(notif.pk)
    return JsonResponse({'ok': ok})


# ═══════════════════════════════════════════════════════════════
# PORTAL — MIS COMUNICADOS
# ═══════════════════════════════════════════════════════════════

@login_required
def mis_comunicados(request):
    """Portal: comunicados masivos recibidos por el colaborador."""
    empleado = _get_empleado(request.user)
    if not empleado:
        messages.warning(request, 'No tienes un perfil de empleado vinculado.')
        return redirect('portal_home')

    # Comunicados enviados donde el empleado es destinatario
    # Filter at the DB level to avoid N+1 (one query per comunicado)
    area_id = empleado.subarea.area_id if empleado.subarea else None
    grupo = empleado.grupo_tareo

    q_todos = Q(destinatarios_tipo='TODOS')
    q_individual = Q(destinatarios_tipo='INDIVIDUAL', personal_individual=empleado)
    q_grupo = Q(destinatarios_tipo='GRUPO', grupo=grupo) if grupo else Q(pk__in=[])
    q_area = Q(destinatarios_tipo='AREA', areas__pk=area_id) if area_id else Q(pk__in=[])

    comunicados_enviados = (
        ComunicadoMasivo.objects
        .filter(estado='ENVIADO')
        .filter(q_todos | q_individual | q_grupo | q_area)
        .distinct()
        .order_by('-creado_en')
    )

    # Prefetch confirmaciones for this employee in bulk
    confirmados_ids = set(
        ConfirmacionLectura.objects
        .filter(personal=empleado, confirmado=True, comunicado__in=comunicados_enviados)
        .values_list('comunicado_id', flat=True)
    )

    mis = []
    for com in comunicados_enviados:
        com.ya_confirmado = com.pk in confirmados_ids
        mis.append(com)

    return render(request, 'comunicaciones/mis_comunicados.html', {
        'titulo': 'Mis Comunicados',
        'comunicados': mis,
        'empleado': empleado,
    })


@login_required
@require_POST
def comunicado_confirmar(request, pk):
    """AJAX: registra confirmación de lectura de un comunicado."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil'})

    comunicado = get_object_or_404(ComunicadoMasivo, pk=pk, estado='ENVIADO')

    # Obtener IP
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded.split(',')[0].strip() if x_forwarded else request.META.get('REMOTE_ADDR')

    confirmacion, created = ConfirmacionLectura.objects.get_or_create(
        comunicado=comunicado,
        personal=empleado,
        defaults={'ip': ip, 'confirmado': True},
    )
    if not created and not confirmacion.confirmado:
        confirmacion.confirmado = True
        confirmacion.ip = ip
        confirmacion.save(update_fields=['confirmado', 'ip'])

    return JsonResponse({'ok': True, 'created': created})
