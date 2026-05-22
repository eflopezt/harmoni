"""
Integración Préstamos ↔ Descuentos por Planilla.

Para cada cuota PENDIENTE / VENCIDA cuya fecha cae dentro del período
(anio, mes), se crea un DescuentoPlanilla vinculado y se marca la cuota
como DESCONTADA.

Si la app ``descuentos`` no estuviera disponible, degrada a no-op.
"""
from datetime import date
from decimal import Decimal

from django.db import transaction

from .models import CuotaPrestamo, Prestamo


def _ultimo_dia_mes(anio, mes):
    from calendar import monthrange
    return date(anio, mes, monthrange(anio, mes)[1])


@transaction.atomic
def aplicar_cuotas_a_planilla(periodo_anio, periodo_mes, usuario=None,
                              dry_run=False):
    """Aplica cuotas de préstamo a Descuentos del período.

    Returns dict con: cuotas_aplicadas, descuentos_creados,
    cuotas_no_aplicables, total_aplicado, descuentos_disponible.
    """
    resumen = {
        'cuotas_aplicadas': [],
        'descuentos_creados': [],
        'cuotas_no_aplicables': [],
        'total_aplicado': Decimal('0.00'),
        'descuentos_disponible': True,
    }

    try:
        from descuentos.models import DescuentoPlanilla
    except Exception:
        resumen['descuentos_disponible'] = False
        return resumen

    fin_periodo = _ultimo_dia_mes(periodo_anio, periodo_mes)

    candidatas = (
        CuotaPrestamo.objects
        .select_related('prestamo', 'prestamo__personal', 'prestamo__tipo')
        .filter(
            estado__in=['PENDIENTE', 'VENCIDA'],
            periodo__lte=fin_periodo,
            descuento_planilla__isnull=True,
            prestamo__estado='EN_CURSO',
        )
        .order_by('prestamo__personal_id', 'periodo')
    )

    for cuota in candidatas:
        personal = cuota.prestamo.personal
        detalle = (
            f'Cuota {cuota.numero}/{cuota.prestamo.num_cuotas} préstamo '
            f'#{cuota.prestamo_id} ({cuota.prestamo.tipo.nombre})'
        )

        if dry_run:
            resumen['cuotas_aplicadas'].append(cuota)
            resumen['total_aplicado'] += cuota.monto
            continue

        descuento = DescuentoPlanilla.objects.create(
            personal=personal,
            causal='ADELANTO_EFECTIVO',
            detalle=detalle,
            monto_total=cuota.monto,
            num_cuotas=1,
            cuota_mensual=cuota.monto,
            fecha_inicio_descuento=date(periodo_anio, periodo_mes, 1),
            estado='EN_CURSO',
            requiere_consentimiento=False,
            consentimiento_firmado=True,
            solicitado_por=usuario,
            observaciones=(
                f'Generado automáticamente desde Préstamo #{cuota.prestamo_id} — '
                f'Cuota {cuota.numero}/{cuota.prestamo.num_cuotas}'
            ),
        )
        cuota.descuento_planilla = descuento
        cuota.estado = 'DESCONTADA'
        cuota.referencia_nomina = (
            cuota.referencia_nomina
            or f'PLA-{periodo_anio}{periodo_mes:02d}-DESC{descuento.pk}'
        )
        cuota.save(update_fields=['descuento_planilla', 'estado',
                                  'referencia_nomina'])

        resumen['cuotas_aplicadas'].append(cuota)
        resumen['descuentos_creados'].append(descuento)
        resumen['total_aplicado'] += cuota.monto

    return resumen


def marcar_cuotas_vencidas(referencia=None):
    """Marca cuotas pendientes vencidas. Devuelve cantidad cambiada."""
    referencia = referencia or date.today()
    pendientes = CuotaPrestamo.objects.filter(
        estado='PENDIENTE',
        periodo__lt=referencia,
        prestamo__estado='EN_CURSO',
    )
    return pendientes.update(estado='VENCIDA')


def saldo_total_empleado(personal):
    """Suma saldos pendientes de préstamos EN_CURSO del trabajador."""
    total = Decimal('0.00')
    for p in Prestamo.objects.filter(personal=personal, estado='EN_CURSO'):
        total += p.saldo_pendiente
    return total
