"""
Cronograma de cuotas para préstamos.

En gastronomía peruana lo común es el "préstamo blanco" (sin interés). Si se
pasa una tasa mensual > 0 se calcula la cuota fija con la fórmula clásica
de amortización tipo francés.
"""
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta

CENTAVO = Decimal('0.01')


def _to_date(value):
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return datetime.strptime(value, '%Y-%m-%d').date()
    raise TypeError(f'Fecha inválida: {value!r}')


def _q(x):
    return Decimal(x).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def calcular_cronograma(monto, num_cuotas, fecha_desembolso, tasa_interes=0):
    """Calcula cronograma de cuotas mensuales.

    Args:
        monto: Decimal | str | int — capital a prestar.
        num_cuotas: int >= 1
        fecha_desembolso: date | str — primera fecha de vencimiento.
        tasa_interes: tasa mensual en porcentaje (0 = sin interés).

    Returns:
        list[dict] con keys: numero, fecha_vencimiento, monto, capital,
        interes, saldo.
    """
    if num_cuotas <= 0:
        raise ValueError('num_cuotas debe ser >= 1')
    monto = Decimal(str(monto))
    if monto <= 0:
        raise ValueError('monto debe ser > 0')
    tasa = Decimal(str(tasa_interes or 0))
    fecha_desembolso = _to_date(fecha_desembolso)

    cronograma = []

    if tasa == 0:
        cuota_base = _q(monto / Decimal(num_cuotas))
        acumulado = Decimal('0.00')
        saldo = monto
        for i in range(1, num_cuotas + 1):
            if i == num_cuotas:
                cap = monto - acumulado
            else:
                cap = cuota_base
                acumulado += cap
            saldo = saldo - cap
            cronograma.append({
                'numero': i,
                'fecha_vencimiento': fecha_desembolso + relativedelta(months=i - 1),
                'monto': _q(cap),
                'capital': _q(cap),
                'interes': Decimal('0.00'),
                'saldo': _q(max(saldo, Decimal('0.00'))),
            })
        return cronograma

    i = tasa / Decimal('100')
    factor = (Decimal('1') + i) ** num_cuotas
    cuota_teorica = monto * i * factor / (factor - Decimal('1'))
    cuota_fija = _q(cuota_teorica)

    saldo = monto
    for n in range(1, num_cuotas + 1):
        interes_cuota = _q(saldo * i)
        if n == num_cuotas:
            capital_cuota = saldo
            cuota_total = capital_cuota + interes_cuota
        else:
            capital_cuota = cuota_fija - interes_cuota
            cuota_total = cuota_fija
        saldo = saldo - capital_cuota
        cronograma.append({
            'numero': n,
            'fecha_vencimiento': fecha_desembolso + relativedelta(months=n - 1),
            'monto': _q(cuota_total),
            'capital': _q(capital_cuota),
            'interes': _q(interes_cuota),
            'saldo': _q(max(saldo, Decimal('0.00'))),
        })
    return cronograma


def generar_cuotas_desde_cronograma(prestamo, fecha_desembolso=None):
    """Genera y persiste las CuotaPrestamo del préstamo."""
    from .models import CuotaPrestamo

    fecha = fecha_desembolso or prestamo.fecha_desembolso \
        or prestamo.fecha_primer_descuento or date.today().replace(day=1)
    if isinstance(fecha, str):
        fecha = _to_date(fecha)

    cronograma = calcular_cronograma(
        monto=prestamo.monto_efectivo,
        num_cuotas=prestamo.num_cuotas,
        fecha_desembolso=fecha,
        tasa_interes=prestamo.tasa_interes,
    )

    CuotaPrestamo.objects.filter(prestamo=prestamo).delete()
    objs = [
        CuotaPrestamo(
            prestamo=prestamo,
            numero=row['numero'],
            periodo=row['fecha_vencimiento'],
            monto=row['monto'],
        )
        for row in cronograma
    ]
    CuotaPrestamo.objects.bulk_create(objs)

    if cronograma:
        prestamo.cuota_mensual = cronograma[0]['monto']
        prestamo.save(update_fields=['cuota_mensual'])

    return cronograma
