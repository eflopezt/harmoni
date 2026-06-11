"""
Cobro online de suscripciones — MercadoPago Checkout Pro.

URLs:
  POST /cuenta/plan/pagar/          → crea el checkout y redirige a MercadoPago
  GET  /cuenta/plan/pago/retorno/   → vuelta del checkout (mensaje al usuario)
  POST /webhooks/mercadopago/       → notificación de pago (anónima, csrf-exempt)

El acceso se extiende SOLO desde el webhook (tras re-consultar la API).
El retorno del navegador es informativo: el usuario puede cerrar la pestaña
del checkout y el cobro igual se aplica.
"""
import json
import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.pagos import mercadopago, service
from core.planes import PLANES

logger = logging.getLogger(__name__)

MESES_PERMITIDOS = (1, 3, 6, 12)


def _empresa_de(request):
    try:
        personal = getattr(request.user, 'personal', None)
        if personal and personal.empresa:
            return personal.empresa
    except Exception:
        pass
    return getattr(request, 'empresa_actual', None)


@login_required
@require_POST
def iniciar_pago(request):
    """Crea la preference y redirige al checkout alojado de MercadoPago."""
    if not mercadopago.esta_configurado():
        messages.warning(request, 'El pago online no está habilitado. Contáctanos por WhatsApp para renovar.')
        return redirect('mi_cuenta_plan')

    empresa = _empresa_de(request)
    if empresa is None:
        messages.error(request, 'No se encontró la empresa de tu cuenta.')
        return redirect('mi_cuenta_plan')

    plan_code = request.POST.get('plan') or empresa.plan or ''
    if plan_code not in PLANES or not PLANES[plan_code]['precio']:
        messages.error(request, 'Plan inválido.')
        return redirect('mi_cuenta_plan')

    try:
        meses = int(request.POST.get('meses', 1))
    except (TypeError, ValueError):
        meses = 1
    if meses not in MESES_PERMITIDOS:
        meses = 1

    base_url = f'{request.scheme}://{request.get_host()}'
    try:
        init_point = mercadopago.crear_checkout(
            empresa, plan_code, meses, base_url,
            payer_email=request.user.email or '',
        )
    except mercadopago.PagoError as exc:
        messages.error(request, str(exc))
        return redirect('mi_cuenta_plan')

    return redirect(init_point)


@login_required
def retorno_pago(request):
    """Vuelta del checkout. El cobro real lo confirma el webhook."""
    status = request.GET.get('collection_status') or request.GET.get('status') or ''
    if status == 'approved':
        messages.success(
            request,
            '¡Pago recibido! Tu suscripción se extenderá en cuanto MercadoPago '
            'confirme la operación (normalmente segundos).',
        )
    elif status in ('pending', 'in_process'):
        messages.info(request, 'Tu pago está en proceso. Te avisaremos cuando se confirme.')
    elif status:
        messages.warning(request, 'El pago no se completó. Puedes intentarlo de nuevo cuando quieras.')
    return redirect('mi_cuenta_plan')


@csrf_exempt
@require_POST
def webhook_mercadopago(request):
    """Notificación de MercadoPago. Responde 200 salvo error transitorio
    nuestro (500 → MercadoPago reintenta) o firma inválida (403)."""
    if not mercadopago.firma_valida(request):
        logger.warning('MercadoPago webhook: firma inválida desde %s', request.META.get('REMOTE_ADDR'))
        return HttpResponseForbidden('firma inválida')

    # El id del pago puede venir por query (?type=payment&data.id=...) o en el body JSON.
    tipo = request.GET.get('type') or request.GET.get('topic') or ''
    payment_id = request.GET.get('data.id') or ''
    if not payment_id:
        try:
            body = json.loads(request.body.decode() or '{}')
            tipo = tipo or body.get('type') or body.get('action', '')
            payment_id = str((body.get('data') or {}).get('id', ''))
        except (ValueError, UnicodeDecodeError):
            pass

    if 'payment' not in tipo or not payment_id:
        return HttpResponse('ignorado')  # merchant_order, plan, etc.

    try:
        pago = mercadopago.obtener_pago(payment_id)
        ok, detalle = service.aplicar_pago_aprobado(pago)
        logger.info('MercadoPago webhook: %s', detalle)
    except mercadopago.PagoError:
        return HttpResponse('error consultando pago', status=500)
    except Exception:
        logger.exception('MercadoPago webhook: error aplicando pago %s', payment_id)
        return HttpResponse('error interno', status=500)

    return HttpResponse('ok')
