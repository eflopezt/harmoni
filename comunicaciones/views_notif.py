"""
Vistas AJAX para notificaciones in-app (header badge + dropdown + toasts).

Endpoints:
  - notificaciones_json         — latest 10 + unread count (dropdown)
  - notificaciones_api_count    — {unread: N} for badge polling
  - notificaciones_api_recientes — latest 10 as JSON (does NOT auto-mark read)
  - notificacion_marcar_leida   — mark single as read (POST)
  - notificaciones_marcar_todas — mark all as read (POST)
  - notificaciones_nuevas       — only NEW since a given timestamp (for toasts)
  - preferencias_notificacion   — preferences page (GET/POST)
  - preferencias_notificacion_api — preferences as JSON (GET/POST)
"""
import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Notificacion, PreferenciaNotificacion


def _get_personal(request):
    """Return the Personal linked to request.user, or None."""
    try:
        return request.user.personal_data
    except Exception:
        return None


def _tiempo_relativo(dt) -> str:
    """Retorna string legible 'hace X min/hora/dias'."""
    delta = timezone.now() - dt
    s = int(delta.total_seconds())
    if s < 60:
        return 'ahora'
    elif s < 3600:
        m = s // 60
        return f'hace {m} min' if m > 1 else 'hace 1 min'
    elif s < 86400:
        h = s // 3600
        return f'hace {h}h'
    elif s < 172800:
        return 'ayer'
    elif s < 604800:
        return f'hace {delta.days} días'
    else:
        return dt.strftime('%d/%m/%Y')


def _notif_to_dict(n):
    """Serialize a Notificacion to a dict for JSON responses."""
    meta = n.metadata or {}
    return {
        'id':       n.pk,
        'asunto':   n.asunto,
        'cuerpo':   (n.cuerpo or '')[:200],
        'leida':    n.estado == 'LEIDA',
        'icono':    meta.get('icono', 'fa-bell'),
        'color':    meta.get('color', '#0f766e'),
        'url':      meta.get('url', '#'),
        'tipo':     meta.get('tipo_notificacion', 'INFO'),
        'tiempo':   _tiempo_relativo(n.creado_en),
        'creado_en': n.creado_en.isoformat(),
        'snoozed_until': n.snoozed_until.isoformat() if n.snoozed_until else None,
        'archivada':     bool(n.archivada_en),
    }


# ═══════════════════════════════════════════════════════════════
# DROPDOWN — latest 10 + count
# ═══════════════════════════════════════════════════════════════

@login_required
def notificaciones_json(request):
    """
    Retorna notificaciones IN_APP del usuario según el tab.
    Incluye conteo de no leídas para el badge.

    Query params:
      tab=todas (default) | no_leidas | snoozed | archivadas

    Reglas:
      - Tab "todas": excluye snoozed activos y archivadas
      - Tab "no_leidas": solo PENDIENTE/ENVIADA, excluye snoozed/archivadas
      - Tab "snoozed": solo las con snoozed_until > now, no archivadas
      - Tab "archivadas": solo las con archivada_en seteado
    """
    from django.db.models import Q

    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'count': 0, 'items': []})

    tab = (request.GET.get('tab') or 'todas').lower()
    now = timezone.now()

    base = Notificacion.objects.filter(destinatario=personal, tipo='IN_APP')

    if tab == 'archivadas':
        qs = base.filter(archivada_en__isnull=False).order_by('-archivada_en')[:30]
    elif tab == 'snoozed':
        qs = base.filter(
            archivada_en__isnull=True,
            snoozed_until__gt=now,
        ).order_by('snoozed_until')[:30]
    else:
        # todas / no_leidas: excluir archivadas y snoozed activos
        qs = base.filter(archivada_en__isnull=True).filter(
            Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now)
        )
        if tab == 'no_leidas':
            qs = qs.filter(estado__in=['PENDIENTE', 'ENVIADA'])
        qs = qs.order_by('-creado_en')[:15]

    # Badge count: siempre no leídas visibles (no snoozed, no archivadas)
    no_leidas = base.filter(
        archivada_en__isnull=True,
        estado__in=['PENDIENTE', 'ENVIADA'],
    ).filter(Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=now)).count()

    items = [_notif_to_dict(n) for n in qs]
    return JsonResponse({'count': no_leidas, 'items': items, 'tab': tab})


@login_required
@require_POST
def notificacion_snooze(request, pk):
    """Snooze una notificación. Body o query: ?hours=24 (default 24)."""
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'ok': False, 'error': 'No personal'}, status=403)

    try:
        hours = int(request.POST.get('hours') or request.GET.get('hours') or 24)
        hours = max(1, min(hours, 24 * 30))  # 1h a 30 días
    except (ValueError, TypeError):
        hours = 24

    from datetime import timedelta
    until = timezone.now() + timedelta(hours=hours)
    updated = Notificacion.objects.filter(
        pk=pk, destinatario=personal, archivada_en__isnull=True,
    ).update(snoozed_until=until)
    return JsonResponse({'ok': bool(updated), 'snoozed_until': until.isoformat(), 'hours': hours})


@login_required
@require_POST
def notificacion_archive(request, pk):
    """Archiva una notificación. La oculta del inbox principal."""
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'ok': False, 'error': 'No personal'}, status=403)

    updated = Notificacion.objects.filter(
        pk=pk, destinatario=personal,
    ).update(archivada_en=timezone.now(), snoozed_until=None)
    return JsonResponse({'ok': bool(updated)})


@login_required
@require_POST
def notificacion_unarchive(request, pk):
    """Restaura una notificación archivada al inbox principal."""
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'ok': False, 'error': 'No personal'}, status=403)

    updated = Notificacion.objects.filter(
        pk=pk, destinatario=personal, archivada_en__isnull=False,
    ).update(archivada_en=None)
    return JsonResponse({'ok': bool(updated)})


# ═══════════════════════════════════════════════════════════════
# BADGE COUNT — lightweight polling endpoint
# ═══════════════════════════════════════════════════════════════

@login_required
def notificaciones_api_count(request):
    """
    API: retorna {unread: N} — cantidad de notificaciones IN_APP no leídas.
    Also returns 'count' for backward compat.
    """
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'unread': 0, 'count': 0})

    count = Notificacion.objects.filter(
        destinatario=personal,
        tipo='IN_APP',
        estado__in=['PENDIENTE', 'ENVIADA'],
    ).count()
    return JsonResponse({'unread': count, 'count': count})


# ═══════════════════════════════════════════════════════════════
# RECIENTES — latest 10 (no auto-mark)
# ═══════════════════════════════════════════════════════════════

@login_required
def notificaciones_api_recientes(request):
    """
    API: retorna las últimas 10 notificaciones IN_APP.
    Does NOT auto-mark as read (that was a bad UX pattern).
    """
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'items': []})

    qs = Notificacion.objects.filter(
        destinatario=personal,
        tipo='IN_APP',
    ).order_by('-creado_en')[:10]

    items = [_notif_to_dict(n) for n in qs]
    return JsonResponse({'items': items})


# ═══════════════════════════════════════════════════════════════
# NEW SINCE — for toast notifications (only unread after timestamp)
# ═══════════════════════════════════════════════════════════════

@login_required
def notificaciones_nuevas(request):
    """
    API: retorna notificaciones IN_APP creadas después de ?since=<ISO timestamp>.
    Used by the toast system to show new notifications only.
    Returns {items: [...], server_time: <ISO>}.
    """
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'items': [], 'server_time': timezone.now().isoformat()})

    since_str = request.GET.get('since', '')
    since = None
    if since_str:
        try:
            from django.utils.dateparse import parse_datetime
            since = parse_datetime(since_str)
            if since and timezone.is_naive(since):
                since = timezone.make_aware(since)
        except (ValueError, TypeError):
            pass

    qs = Notificacion.objects.filter(
        destinatario=personal,
        tipo='IN_APP',
        estado__in=['PENDIENTE', 'ENVIADA'],
    )
    if since:
        qs = qs.filter(creado_en__gt=since)

    qs = qs.order_by('-creado_en')[:5]
    items = [_notif_to_dict(n) for n in qs]

    return JsonResponse({
        'items': items,
        'server_time': timezone.now().isoformat(),
    })


# ═══════════════════════════════════════════════════════════════
# MARK READ — single
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def notificacion_marcar_leida(request, pk):
    """Marca una notificación como leída."""
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'ok': False})

    updated = Notificacion.objects.filter(
        pk=pk, destinatario=personal,
    ).exclude(estado='LEIDA').update(
        estado='LEIDA', leida_en=timezone.now()
    )
    return JsonResponse({'ok': bool(updated)})


# ═══════════════════════════════════════════════════════════════
# MARK ALL READ
# ═══════════════════════════════════════════════════════════════

@login_required
@require_POST
def notificaciones_marcar_todas(request):
    """Marca todas las notificaciones pendientes como leídas."""
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({'ok': False})

    count = Notificacion.objects.filter(
        destinatario=personal,
        tipo='IN_APP',
        estado__in=['PENDIENTE', 'ENVIADA'],
    ).update(estado='LEIDA', leida_en=timezone.now())
    return JsonResponse({'ok': True, 'count': count})


# ═══════════════════════════════════════════════════════════════
# PREFERENCES — page + API
# ═══════════════════════════════════════════════════════════════

@login_required
def preferencias_notificacion(request):
    """
    Página de preferencias de notificación del usuario.
    GET: muestra formulario. POST: guarda y redirige.
    """
    personal = _get_personal(request)
    if not personal:
        messages.warning(request, 'No tienes un perfil de empleado vinculado.')
        return redirect('home')

    pref, _ = PreferenciaNotificacion.objects.get_or_create(personal=personal)

    if request.method == 'POST':
        # Canales
        pref.recibir_email = request.POST.get('recibir_email') == 'on'
        pref.recibir_in_app = request.POST.get('recibir_in_app') == 'on'
        pref.recibir_whatsapp = request.POST.get('recibir_whatsapp') == 'on'
        pref.recibir_push = request.POST.get('recibir_push') == 'on'

        # Per-type
        for field in [
            'notif_vacaciones', 'notif_nominas', 'notif_workflows',
            'notif_asistencia', 'notif_comunicados', 'notif_sistema',
            'notif_evaluaciones', 'notif_capacitaciones',
            'notif_disciplinaria', 'notif_onboarding',
        ]:
            setattr(pref, field, request.POST.get(field) == 'on')

        # Behavior
        pref.frecuencia_resumen = request.POST.get('frecuencia_resumen', 'INMEDIATO')
        pref.sonido_habilitado = request.POST.get('sonido_habilitado') == 'on'
        pref.toast_habilitado = request.POST.get('toast_habilitado') == 'on'

        # Silent hours
        h_inicio = request.POST.get('horario_silencio_inicio', '')
        h_fin = request.POST.get('horario_silencio_fin', '')
        pref.horario_silencio_inicio = h_inicio if h_inicio else None
        pref.horario_silencio_fin = h_fin if h_fin else None

        pref.save()
        messages.success(request, 'Preferencias de notificación actualizadas.')
        return redirect('preferencias_notificacion')

    # Type toggle config for template rendering
    type_toggles = [
        ('notif_vacaciones', 'Vacaciones', 'fa-umbrella-beach', '#0f766e'),
        ('notif_nominas', 'Nóminas / Boletas', 'fa-file-invoice-dollar', '#2563eb'),
        ('notif_workflows', 'Aprobaciones', 'fa-check-double', '#7c3aed'),
        ('notif_asistencia', 'Asistencia', 'fa-clock', '#ea580c'),
        ('notif_comunicados', 'Comunicados', 'fa-bullhorn', '#0891b2'),
        ('notif_sistema', 'Sistema / Alertas', 'fa-gear', '#64748b'),
        ('notif_evaluaciones', 'Evaluaciones', 'fa-star', '#eab308'),
        ('notif_capacitaciones', 'Capacitaciones', 'fa-graduation-cap', '#059669'),
        ('notif_disciplinaria', 'Disciplinaria', 'fa-gavel', '#dc2626'),
        ('notif_onboarding', 'Onboarding', 'fa-user-plus', '#8b5cf6'),
    ]

    return render(request, 'comunicaciones/preferencias_notificacion.html', {
        'titulo': 'Preferencias de Notificación',
        'pref': pref,
        'type_toggles': type_toggles,
        'frecuencias': PreferenciaNotificacion.FRECUENCIA_CHOICES,
    })


@login_required
def preferencias_notificacion_api(request):
    """
    API: GET returns preferences as JSON. POST updates them.
    Used by the JS notification system to know if sound/toast are enabled.
    """
    personal = _get_personal(request)
    if not personal:
        return JsonResponse({
            'sonido_habilitado': True,
            'toast_habilitado': True,
            'recibir_push': True,
        })

    pref, _ = PreferenciaNotificacion.objects.get_or_create(personal=personal)

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for key in ['sonido_habilitado', 'toast_habilitado', 'recibir_push']:
                if key in data:
                    setattr(pref, key, bool(data[key]))
            pref.save()
        except (json.JSONDecodeError, Exception):
            pass

    return JsonResponse({
        'sonido_habilitado': pref.sonido_habilitado,
        'toast_habilitado': pref.toast_habilitado,
        'recibir_push': pref.recibir_push,
        'recibir_in_app': pref.recibir_in_app,
    })
