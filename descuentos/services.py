"""
Integración descuentos ↔ cierre de planilla.

El engine descuenta los judiciales (embargo/pensión) y los internos
(herramienta, uniforme, multa, etc. con consentimiento firmado) en cada
cálculo, pero hasta ahora NADA registraba la aplicación: `saldo_pendiente`
nunca bajaba y un embargo de monto fijo se descontaba indefinidamente (mismo
anti-patrón que las cuotas de préstamo antes del marcado al cierre).

`registrar_aplicaciones_cierre(periodo)` se llama desde periodo_cerrar
(planilla REGULAR) y, por cada registro del período con líneas de descuento:

  1. crea `AplicacionDescuento` (idempotente: unique descuento+período),
  2. transiciona APROBADO → EN_CURSO en la primera aplicación,
  3. transiciona → PAGADO cuando el saldo llega a 0 (el embargo se detiene;
     una pensión "indefinida" se modela renovando el descuento).

Si una misma persona tiene varios descuentos de la misma causal, el monto
de la línea se reparte consumiendo en el mismo orden en que itera el engine
(Meta.ordering); el total aplicado siempre coincide con lo descontado.
"""
import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)

# código de ConceptoRemunerativo (línea de nómina) → causal del descuento
CODIGO_A_CAUSAL = {
    'pension-alimenticia': 'PENSION_ALIMENTICIA',
    'embargo-judicial':    'EMBARGO_JUDICIAL',
}

# Código genérico bajo el que el engine emite TODOS los descuentos internos
# (causales no judiciales); la causal específica viaja en la observación.
CODIGO_INTERNO = 'descuento-interno'
CAUSALES_JUDICIALES = tuple(CODIGO_A_CAUSAL.values())

# Marcador de grupo para "cualquier causal interna" en el reparto por persona.
_INTERNO = '__INTERNO__'


@transaction.atomic
def registrar_aplicaciones_cierre(periodo):
    """Registra las aplicaciones de descuentos (judiciales e internos) del período.

    Devuelve la cantidad de AplicacionDescuento creadas. Re-ejecutar sobre
    un período ya procesado no duplica (get_or_create por descuento+período).
    """
    from nominas.models import LineaNomina

    from .models import AplicacionDescuento, DescuentoPlanilla

    codigos = list(CODIGO_A_CAUSAL.keys()) + [CODIGO_INTERNO]
    lineas = (
        LineaNomina.objects
        .filter(registro__periodo=periodo, concepto__codigo__in=codigos)
        .select_related('registro', 'concepto')
    )

    # (personal_id, causal | _INTERNO) → [(registro, monto_linea), ...]
    por_persona = {}
    for linea in lineas:
        causal = CODIGO_A_CAUSAL.get(linea.concepto.codigo, _INTERNO)
        key = (linea.registro.personal_id, causal)
        por_persona.setdefault(key, []).append((linea.registro, linea.monto))

    creadas = 0
    for (personal_id, causal), items in por_persona.items():
        registro = items[0][0]
        restante = sum((m for _, m in items), Decimal('0'))

        descuentos = DescuentoPlanilla.objects.filter(
            personal_id=personal_id,
            estado__in=['APROBADO', 'EN_CURSO'],
        )  # mismo ordering del engine (Meta.ordering)
        if causal == _INTERNO:
            descuentos = descuentos.exclude(causal__in=CAUSALES_JUDICIALES)
        else:
            descuentos = descuentos.filter(causal=causal)

        for d in descuentos:
            if restante <= 0:
                break
            monto = min(
                d.cuota_mensual or Decimal('0'),
                d.saldo_pendiente,
                restante,
            )
            if monto <= 0:
                continue
            _, created = AplicacionDescuento.objects.get_or_create(
                descuento=d,
                periodo_anio=periodo.anio,
                periodo_mes=periodo.mes,
                defaults={
                    'monto_aplicado': monto,
                    'registro_nomina': registro,
                },
            )
            if not created:
                continue  # cierre re-ejecutado: no duplicar ni re-transicionar
            creadas += 1
            restante -= monto

            # Transiciones de estado
            if d.estado == 'APROBADO':
                d.estado = 'EN_CURSO'
                d.save(update_fields=['estado'])
            if d.saldo_pendiente <= 0:
                d.estado = 'PAGADO'
                d.save(update_fields=['estado'])
                logger.info('Descuento %s completado al cierre %s/%s',
                            d.pk, periodo.anio, periodo.mes)

    return creadas
