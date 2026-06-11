"""
Cliente mínimo de MercadoPago (Checkout Pro) para cobro de suscripciones.

Flujo:
  1. `crear_checkout()` crea una "preference" y devuelve la URL del checkout
     alojado de MercadoPago (init_point). El cliente paga ahí (tarjeta, Yape).
  2. MercadoPago notifica a /webhooks/mercadopago/ (notification_url).
  3. El webhook re-consulta el pago con `obtener_pago()` — la fuente de verdad
     es SIEMPRE la API autenticada, nunca el body del webhook — y si está
     aprobado lo aplica vía core.pagos.service.aplicar_pago_aprobado().

Config (.env):
  MERCADOPAGO_ACCESS_TOKEN   — token privado (APP_USR-... / TEST-... sandbox)
  MERCADOPAGO_WEBHOOK_SECRET — clave de firma del webhook (recomendada;
                               se genera en Panel → Webhooks de MercadoPago)

Sin token configurado, el flujo online se oculta de la UI y el cobro sigue
siendo manual (Yape/transferencia registrados por el dueño).

Para añadir otra pasarela (p.ej. Culqi): módulo hermano con la misma interfaz
(crear_checkout / obtener_pago) y su propio webhook; service.py es agnóstico.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

API_BASE = 'https://api.mercadopago.com'
TIMEOUT = 15

REF_PREFIX = 'harmoni'


class PagoError(Exception):
    """Error al comunicarse con la pasarela."""


def esta_configurado():
    return bool(getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', ''))


def _headers():
    return {'Authorization': f'Bearer {settings.MERCADOPAGO_ACCESS_TOKEN}'}


def build_external_reference(empresa_id, plan_code, meses):
    return f'{REF_PREFIX}|{empresa_id}|{plan_code}|{meses}'


def parse_external_reference(ref):
    """'harmoni|12|PLANILLA|3' → (12, 'PLANILLA', 3) o None si no es nuestro."""
    try:
        prefix, empresa_id, plan_code, meses = (ref or '').split('|')
        if prefix != REF_PREFIX:
            return None
        return int(empresa_id), plan_code, int(meses)
    except (ValueError, AttributeError):
        return None


def crear_checkout(empresa, plan_code, meses, base_url, payer_email=''):
    """Crea la preference de Checkout Pro y devuelve la URL de pago (init_point).

    `base_url` = origen absoluto (https://harmoni.pe) para back_urls y webhook.
    Lanza PagoError si la API falla.
    """
    from core.planes import PLANES

    plan = PLANES[plan_code]
    monto = plan['precio'] * meses
    payload = {
        'items': [{
            'id': f'plan-{plan_code.lower()}',
            'title': f"Harmoni — Plan {plan['nombre']} × {meses} mes{'es' if meses > 1 else ''}",
            'quantity': 1,
            'unit_price': float(monto),
            'currency_id': 'PEN',
        }],
        'external_reference': build_external_reference(empresa.pk, plan_code, meses),
        'metadata': {'empresa_id': empresa.pk, 'plan': plan_code, 'meses': meses},
        'back_urls': {
            'success': f'{base_url}/cuenta/plan/pago/retorno/',
            'failure': f'{base_url}/cuenta/plan/pago/retorno/',
            'pending': f'{base_url}/cuenta/plan/pago/retorno/',
        },
        'auto_return': 'approved',
        'notification_url': f'{base_url}/webhooks/mercadopago/',
        'statement_descriptor': 'HARMONI',
    }
    if payer_email:
        payload['payer'] = {'email': payer_email}

    try:
        r = requests.post(
            f'{API_BASE}/checkout/preferences',
            json=payload, headers=_headers(), timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as exc:
        logger.error('MercadoPago: error creando preference para empresa %s: %s', empresa.pk, exc)
        raise PagoError('No se pudo iniciar el pago. Intenta de nuevo en unos minutos.') from exc

    init_point = data.get('init_point') or data.get('sandbox_init_point')
    if not init_point:
        logger.error('MercadoPago: preference sin init_point: %s', data)
        raise PagoError('La pasarela no devolvió la URL de pago.')
    return init_point


def obtener_pago(payment_id):
    """Consulta autoritativa del pago: GET /v1/payments/{id}. Lanza PagoError."""
    try:
        r = requests.get(
            f'{API_BASE}/v1/payments/{payment_id}',
            headers=_headers(), timeout=TIMEOUT,
        )
        r.raise_for_status()
        return r.json()
    except requests.RequestException as exc:
        logger.error('MercadoPago: error consultando pago %s: %s', payment_id, exc)
        raise PagoError(f'No se pudo consultar el pago {payment_id}.') from exc


def firma_valida(request):
    """Valida el header x-signature del webhook (HMAC-SHA256).

    Manifest según docs MP: 'id:{data.id};request-id:{x-request-id};ts:{ts};'
    Si no hay MERCADOPAGO_WEBHOOK_SECRET configurado devuelve True (la
    verificación real igual ocurre al re-consultar la API autenticada).
    """
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '')
    if not secret:
        return True

    firma = request.headers.get('x-signature', '')
    partes = dict(
        p.strip().split('=', 1) for p in firma.split(',') if '=' in p
    )
    ts, v1 = partes.get('ts'), partes.get('v1')
    if not ts or not v1:
        return False

    data_id = str(request.GET.get('data.id', '') or request.GET.get('id', '')).lower()
    request_id = request.headers.get('x-request-id', '')
    manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
    esperado = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, v1)
