"""
Aplicación de pagos de pasarela a la suscripción (agnóstico de la pasarela).

`aplicar_pago_aprobado(pago)` recibe el dict del pago YA CONSULTADO a la API
de MercadoPago (nunca el body crudo del webhook) y, si corresponde:
  - extiende Empresa.suscripcion_hasta desde max(hoy, vencimiento actual),
  - actualiza Empresa.plan al plan pagado,
  - registra el cobro en el ledger HistorialPago (estado PAGADO).

Idempotente por payment_id: reintentos del webhook no duplican ni re-extienden.
"""
import logging
from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from django.db import transaction

from core.pagos.mercadopago import parse_external_reference

logger = logging.getLogger(__name__)


def aplicar_pago_aprobado(pago):
    """Aplica un pago de MercadoPago. Devuelve (ok: bool, detalle: str).

    ok=True también para el caso "ya aplicado" (idempotencia): el webhook
    debe responder 200 para que MercadoPago deje de reintentar.
    """
    from core.planes import PLANES
    from empresas.models import Empresa
    from empresas.models_billing import HistorialPago

    payment_id = str(pago.get('id', ''))
    status = pago.get('status', '')
    if status != 'approved':
        return False, f'pago {payment_id} con status={status}, no se aplica'

    ref = parse_external_reference(pago.get('external_reference', ''))
    if not ref:
        return False, f'pago {payment_id} sin external_reference de Harmoni'
    empresa_id, plan_code, meses = ref

    plan = PLANES.get(plan_code)
    if not plan or not plan['precio'] or meses < 1:
        return False, f'pago {payment_id} con plan/meses inválidos: {plan_code}×{meses}'

    esperado = Decimal(plan['precio'] * meses)
    recibido = Decimal(str(pago.get('transaction_amount', 0)))
    if recibido < esperado:
        logger.error(
            'MercadoPago: pago %s por S/ %s < esperado S/ %s (%s×%s) — NO se aplica',
            payment_id, recibido, esperado, plan_code, meses,
        )
        return False, f'pago {payment_id} con monto S/ {recibido} menor al esperado S/ {esperado}'

    with transaction.atomic():
        try:
            empresa = Empresa.objects.select_for_update().get(pk=empresa_id)
        except Empresa.DoesNotExist:
            return False, f'pago {payment_id} para empresa inexistente {empresa_id}'

        # Idempotencia: reintento del webhook sobre un pago ya aplicado.
        if HistorialPago.objects.filter(
            metodo_pago='MERCADOPAGO', referencia=payment_id,
        ).exists():
            return True, f'pago {payment_id} ya estaba aplicado'

        hoy = date.today()
        base = max(hoy, empresa.suscripcion_hasta) if empresa.suscripcion_hasta else hoy
        hasta = base + relativedelta(months=meses)

        empresa.plan = plan_code
        empresa.suscripcion_hasta = hasta
        empresa.suscripcion_nota = (
            f'MercadoPago {payment_id}: {plan_code} × {meses} mes(es) '
            f'pagado el {hoy:%d/%m/%Y}'
        )
        empresa.save(update_fields=['plan', 'suscripcion_hasta', 'suscripcion_nota'])

        HistorialPago.objects.create(
            empresa=empresa,
            monto=recibido,
            fecha_pago=hoy,
            metodo_pago='MERCADOPAGO',
            referencia=payment_id,
            estado='PAGADO',
            periodo_desde=base,
            periodo_hasta=hasta,
            notas=f'Cobro automático vía MercadoPago (plan {plan_code}, {meses} mes/es).',
        )

    logger.info(
        'MercadoPago: pago %s aplicado — empresa %s plan %s hasta %s',
        payment_id, empresa_id, plan_code, hasta,
    )
    return True, f'pago {payment_id} aplicado: {plan_code} hasta {hasta:%d/%m/%Y}'
