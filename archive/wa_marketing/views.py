"""
Views de WhatsApp Marketing.

- webhook_incoming: recibe mensajes del sidecar Baileys (sin sesión, autenticado por token)
- inbox / conversacion_detalle / responder / broadcast: UI staff-only
- status_sidecar / qr_sidecar: vista de estado y QR de pareo
"""
import json
import logging
from datetime import timezone as dt_tz
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from . import client, bot
from .models import WaConversacion, WaMensaje, WaLead

logger = logging.getLogger('wa_marketing')


# ── Webhook (sidecar → Django) ────────────────────────────────

@csrf_exempt
@require_POST
def webhook_incoming(request):
    """
    Recibe del sidecar:
      { phone, body, pushName, messageId, timestamp }
    Autenticado por Bearer token (settings.WA_WEBHOOK_TOKEN).
    """
    expected = getattr(settings, 'WA_WEBHOOK_TOKEN', '')
    if expected:
        auth = request.headers.get('Authorization', '')
        if auth != f'Bearer {expected}':
            return JsonResponse({'ok': False, 'error': 'unauthorized'}, status=401)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'invalid json'}, status=400)

    phone = (payload.get('phone') or '').strip()
    body = (payload.get('body') or '').strip()
    push_name = (payload.get('pushName') or '').strip()
    wa_msg_id = (payload.get('messageId') or '').strip()
    ts = payload.get('timestamp')

    if not phone or not body:
        return JsonResponse({'ok': False, 'error': 'phone y body requeridos'}, status=400)

    # Conversación + mensaje
    conv, created = WaConversacion.objects.get_or_create(
        telefono=phone,
        defaults={'nombre_wa': push_name},
    )
    if push_name and conv.nombre_wa != push_name:
        conv.nombre_wa = push_name

    ts_dt = _ts_to_datetime(ts)
    conv.ultimo_mensaje_at = ts_dt
    conv.no_leidos = (conv.no_leidos or 0) + 1
    conv.save(update_fields=['nombre_wa', 'ultimo_mensaje_at', 'no_leidos', 'actualizado_en'])

    msg_in = WaMensaje.objects.create(
        conversacion=conv,
        direccion=WaMensaje.DIR_IN,
        tipo=WaMensaje.TIPO_TEXTO,
        cuerpo=body,
        wa_message_id=wa_msg_id,
    )

    # Procesa con el bot (no responde si está en HANDOFF)
    try:
        bot.procesar_entrante(conv, msg_in)
    except Exception as e:
        logger.exception('bot.procesar_entrante falló para %s', phone)

    return JsonResponse({'ok': True, 'conversacion_id': conv.id, 'created': created})


def _ts_to_datetime(ts) -> datetime:
    try:
        if ts is None:
            return timezone.now()
        return datetime.fromtimestamp(int(ts), tz=dt_tz.utc)
    except (TypeError, ValueError):
        return timezone.now()


# ── UI staff ──────────────────────────────────────────────────

@staff_member_required
def inbox(request):
    filtro = request.GET.get('filtro', 'todos')
    q = request.GET.get('q', '').strip()

    qs = WaConversacion.objects.all()
    if filtro == 'bot':
        qs = qs.filter(estado=WaConversacion.ESTADO_BOT)
    elif filtro == 'handoff':
        qs = qs.filter(estado=WaConversacion.ESTADO_HANDOFF)
    elif filtro == 'no_leidos':
        qs = qs.filter(no_leidos__gt=0)
    if q:
        qs = qs.filter(Q(telefono__icontains=q) | Q(nombre_wa__icontains=q))

    conversaciones = qs.order_by('-ultimo_mensaje_at')[:200]

    contadores = WaConversacion.objects.aggregate(
        total=Count('id'),
        no_leidos=Count('id', filter=Q(no_leidos__gt=0)),
        en_handoff=Count('id', filter=Q(estado=WaConversacion.ESTADO_HANDOFF)),
    )

    return render(request, 'wa_marketing/inbox.html', {
        'conversaciones': conversaciones,
        'filtro': filtro,
        'q': q,
        'contadores': contadores,
        'sidecar_status': client.status(),
    })


@staff_member_required
def conversacion_detalle(request, pk):
    conv = get_object_or_404(WaConversacion, pk=pk)
    if conv.no_leidos:
        conv.no_leidos = 0
        conv.save(update_fields=['no_leidos'])
    mensajes = conv.mensajes.all().order_by('creado_en')
    return render(request, 'wa_marketing/conversacion.html', {
        'conv': conv,
        'mensajes': mensajes,
    })


@staff_member_required
@require_POST
def responder(request, pk):
    conv = get_object_or_404(WaConversacion, pk=pk)
    texto = (request.POST.get('texto') or '').strip()
    if not texto:
        messages.error(request, 'Mensaje vacío')
        return redirect('wa_conversacion', pk=pk)

    resultado = client.send_text(conv.telefono, texto)
    WaMensaje.objects.create(
        conversacion=conv,
        direccion=WaMensaje.DIR_OUT,
        tipo=WaMensaje.TIPO_TEXTO,
        cuerpo=texto,
        wa_message_id=resultado.get('id') or '',
        enviado_por=request.user,
    )
    if not resultado.get('ok'):
        messages.error(request, f'No se pudo enviar: {resultado.get("error")}')
    return redirect('wa_conversacion', pk=pk)


@staff_member_required
@require_POST
def cambiar_estado(request, pk):
    """Cambiar estado: tomar (HANDOFF), devolver al bot (BOT), o cerrar (CERRADO)."""
    conv = get_object_or_404(WaConversacion, pk=pk)
    accion = request.POST.get('accion')
    if accion == 'tomar':
        conv.estado = WaConversacion.ESTADO_HANDOFF
        conv.asignado_a = request.user
    elif accion == 'devolver_bot':
        conv.estado = WaConversacion.ESTADO_BOT
        conv.menu_state = WaConversacion.MENU_INICIO
    elif accion == 'cerrar':
        conv.estado = WaConversacion.ESTADO_CERRADO
    conv.save()
    return redirect('wa_conversacion', pk=pk)


@staff_member_required
def broadcast(request):
    """
    Envía un mensaje a una lista de teléfonos (separados por coma o línea).
    Riesgo: con Baileys, broadcasts masivos disparan baneo. Usar con calma.
    """
    if request.method == 'POST':
        texto = (request.POST.get('texto') or '').strip()
        destinos_raw = (request.POST.get('destinos') or '').strip()
        if not texto or not destinos_raw:
            messages.error(request, 'Texto y destinos son obligatorios')
            return redirect('wa_broadcast')

        telefonos = [t.strip() for t in destinos_raw.replace(',', '\n').split('\n') if t.strip()]
        enviados, errores = 0, 0
        for tel in telefonos:
            r = client.send_text(tel, texto)
            conv, _ = WaConversacion.objects.get_or_create(telefono=tel)
            WaMensaje.objects.create(
                conversacion=conv,
                direccion=WaMensaje.DIR_OUT,
                tipo=WaMensaje.TIPO_TEXTO,
                cuerpo=texto,
                wa_message_id=r.get('id') or '',
                enviado_por=request.user,
            )
            if r.get('ok'):
                enviados += 1
            else:
                errores += 1

        messages.success(request, f'Broadcast: {enviados} enviados, {errores} errores')
        return redirect('wa_broadcast')

    return render(request, 'wa_marketing/broadcast.html', {
        'sidecar_status': client.status(),
    })


@staff_member_required
def leads(request):
    qs = WaLead.objects.all().order_by('-creado_en')[:500]
    return render(request, 'wa_marketing/leads.html', {'leads': qs})


@staff_member_required
@require_GET
def sidecar_status(request):
    return JsonResponse(client.status())


@staff_member_required
@require_GET
def sidecar_qr(request):
    """Proxy al QR del sidecar (para pareo inicial)."""
    import requests as rq
    try:
        base = getattr(settings, 'WA_BOT_URL', 'http://127.0.0.1:3001').rstrip('/')
        headers = {}
        token = getattr(settings, 'WA_BOT_API_TOKEN', '')
        if token:
            headers['Authorization'] = f'Bearer {token}'
        r = rq.get(f'{base}/qr', headers=headers, timeout=5)
        return HttpResponse(r.content, content_type=r.headers.get('Content-Type', 'image/png'),
                            status=r.status_code)
    except rq.RequestException as e:
        return HttpResponse(f'Sidecar inalcanzable: {e}', status=502)
