"""
Webhook de Telegram para aprobaciones.

Seguridad: Telegram manda el header X-Telegram-Bot-Api-Secret-Token con el
secret registrado en setWebhook. Sin TELEGRAM_WEBHOOK_SECRET en el entorno,
el endpoint rechaza TODO (la feature queda apagada hasta configurarla).
"""
import json
import logging
import os

from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def telegram_webhook(request):
    secret = (os.environ.get('TELEGRAM_WEBHOOK_SECRET') or '').strip()
    if not secret:
        return HttpResponseForbidden('webhook deshabilitado')
    if request.headers.get('X-Telegram-Bot-Api-Secret-Token', '') != secret:
        logger.warning('Telegram webhook: secret inválido desde %s',
                       request.META.get('REMOTE_ADDR'))
        return HttpResponseForbidden('secret inválido')

    try:
        update = json.loads(request.body.decode('utf-8'))
    except (ValueError, UnicodeDecodeError):
        return HttpResponse(status=400)

    from .telegram_aprobaciones import procesar_update
    resultado = procesar_update(update)
    # Siempre 200 a Telegram (si no, reintenta el mismo update en loop)
    return JsonResponse({'ok': True, **resultado})
