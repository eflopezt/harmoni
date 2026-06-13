"""
Aprobaciones por Telegram (patrón Rippling-Slack: la acción va a donde
el admin ya está, con botones inline Aprobar/Rechazar).

Flujo:
  1. Al crearse una SolicitudVacacion o Prestamo en PENDIENTE, se envía
     un mensaje al chat configurado (ConfiguracionSistema.telegram_chat_aprobaciones)
     con botones inline.
  2. Telegram entrega el callback al webhook
     POST /comunicaciones/telegram/webhook/ (validado con el header
     X-Telegram-Bot-Api-Secret-Token == settings TELEGRAM_WEBHOOK_SECRET).
  3. Se ejecuta obj.aprobar(usuario)/rechazar(usuario) con el primer
     superuser activo, se responde el callback y se edita el mensaje.

Seguridad:
  - Sin TELEGRAM_WEBHOOK_SECRET configurado, el webhook rechaza todo (403).
  - Solo se aceptan callbacks del chat configurado para aprobaciones.
  - La acción queda en aprobado_por (User real) como cualquier aprobación.

Registro del webhook (una vez, tras configurar el secret):
  python manage.py telegram_registrar_webhook
"""
import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

API_BASE = 'https://api.telegram.org'
TIMEOUT_SEG = 10

# tipo → (app_label, model, etiqueta humana)
TIPOS = {
    'vac': ('vacaciones', 'SolicitudVacacion', 'Vacaciones'),
    'pre': ('prestamos', 'Prestamo', 'Préstamo/Adelanto'),
}


def _config():
    """(bot_token, chat_aprobaciones) o (None, None) si no está configurado."""
    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.get()
        token = (cfg.telegram_bot_token or '').strip()
        chat = (cfg.telegram_chat_aprobaciones or '').strip()
        if token and chat:
            return token, chat
    except Exception:
        logger.warning('Telegram aprobaciones: sin configuración', exc_info=True)
    return None, None


def _post(metodo: str, payload: dict, token: str):
    """POST a la Bot API. Devuelve el dict de respuesta o None si falla."""
    try:
        req = urllib.request.Request(
            f'{API_BASE}/bot{token}/{metodo}',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_SEG) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (urllib.error.URLError, OSError, ValueError) as e:
        logger.warning('Telegram %s falló: %s', metodo, e)
        return None


def _descripcion(tipo: str, obj) -> str:
    if tipo == 'vac':
        return (
            f'🏖 <b>Vacaciones</b> — {obj.personal}\n'
            f'Del {obj.fecha_inicio:%d/%m/%Y} al {obj.fecha_fin:%d/%m/%Y}'
            f' ({obj.dias_calendario} día(s) calendario)'
        )
    if tipo == 'pre':
        etiqueta = 'Adelanto de sueldo' if getattr(obj.tipo, 'codigo', '') == 'adelanto-sueldo-ewa' \
            else f'Préstamo {obj.tipo}'
        return (
            f'💵 <b>{etiqueta}</b> — {obj.personal}\n'
            f'Monto: S/ {obj.monto_solicitado:,.2f} en {obj.num_cuotas} cuota(s)'
        )
    return str(obj)


def enviar_solicitud_aprobacion(tipo: str, obj) -> bool:
    """Envía la solicitud con botones al chat de aprobaciones. Best-effort."""
    token, chat = _config()
    if not token:
        return False
    texto = _descripcion(tipo, obj) + '\n\n¿Apruebas?'
    data = _post('sendMessage', {
        'chat_id': chat,
        'text': texto,
        'parse_mode': 'HTML',
        'reply_markup': {
            'inline_keyboard': [[
                {'text': '✅ Aprobar', 'callback_data': f'apr:{tipo}:{obj.pk}'},
                {'text': '❌ Rechazar', 'callback_data': f'rec:{tipo}:{obj.pk}'},
            ]],
        },
    }, token)
    return bool(data and data.get('ok'))


def _usuario_aprobador():
    from django.contrib.auth.models import User
    return User.objects.filter(is_active=True, is_superuser=True).order_by('pk').first()


def procesar_update(update: dict) -> dict:
    """
    Procesa un update del webhook. Solo callbacks del chat configurado.
    Returns dict con 'resultado' para logging/tests.
    """
    cb = update.get('callback_query')
    if not cb:
        return {'resultado': 'ignorado_no_callback'}

    token, chat_autorizado = _config()
    if not token:
        return {'resultado': 'sin_config'}

    chat_origen = str(cb.get('message', {}).get('chat', {}).get('id', ''))
    if chat_origen != str(chat_autorizado):
        logger.warning('Telegram callback de chat NO autorizado: %s', chat_origen)
        return {'resultado': 'chat_no_autorizado'}

    datos = (cb.get('data') or '').split(':')
    if len(datos) != 3 or datos[0] not in ('apr', 'rec') or datos[1] not in TIPOS:
        _responder(cb, 'Acción no reconocida.', token)
        return {'resultado': 'data_invalida'}

    accion, tipo, pk = datos
    from django.apps import apps as django_apps
    app_label, model_name, etiqueta = TIPOS[tipo]
    Modelo = django_apps.get_model(app_label, model_name)
    obj = Modelo.objects.filter(pk=pk).first()
    if obj is None:
        _responder(cb, 'La solicitud ya no existe.', token)
        return {'resultado': 'no_existe'}

    if obj.estado != 'PENDIENTE':
        _responder(cb, f'Ya fue resuelta ({obj.estado}).', token)
        _editar_mensaje(cb, f'{_descripcion(tipo, obj)}\n\nℹ️ Ya estaba: {obj.estado}', token)
        return {'resultado': 'ya_resuelta'}

    usuario = _usuario_aprobador()
    if usuario is None:
        _responder(cb, 'No hay usuario aprobador configurado.', token)
        return {'resultado': 'sin_aprobador'}

    try:
        if accion == 'apr':
            obj.aprobar(usuario)
            verbo, emoji = 'APROBADA', '✅'
        else:
            obj.rechazar(usuario, motivo='Rechazado vía Telegram')
            verbo, emoji = 'RECHAZADA', '❌'
    except Exception as e:
        logger.warning('Telegram aprobación falló (%s %s %s): %s', accion, tipo, pk, e)
        _responder(cb, f'Error: {e}', token)
        return {'resultado': 'error_accion', 'error': str(e)}

    _responder(cb, f'{emoji} {verbo}', token)
    _editar_mensaje(
        cb,
        f'{_descripcion(tipo, obj)}\n\n{emoji} <b>{verbo}</b> por {usuario.get_username()} (vía Telegram)',
        token,
    )
    logger.info('Telegram: %s %s #%s por %s', verbo, etiqueta, pk, usuario.get_username())
    return {'resultado': 'ok', 'accion': verbo, 'tipo': tipo, 'pk': pk}


def _responder(cb, texto, token):
    _post('answerCallbackQuery', {'callback_query_id': cb.get('id', ''), 'text': texto[:190]}, token)


def _editar_mensaje(cb, texto, token):
    msg = cb.get('message') or {}
    if msg.get('message_id'):
        _post('editMessageText', {
            'chat_id': msg['chat']['id'],
            'message_id': msg['message_id'],
            'text': texto,
            'parse_mode': 'HTML',
        }, token)
