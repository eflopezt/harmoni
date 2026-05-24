"""
Calculadoras especializadas:

1. **Reversa** (neto → bruto): "¿qué sueldo debo poner para que reciba S/X neto?"
2. **Gratificación** (jul/dic): Ley 27735 + bonif extraord 9% / 6.75% EPS
3. **CTS** (may/nov): D.Leg. 650 — 1/12 sueldo + 1/12 × 1/6 (1/72) por gratif
4. **Liquidación al cese**: vacaciones + CTS + gratif truncas + sueldo pendiente

URLs:
- /nominas/calculadora/reversa/
- /nominas/calculadora/gratificacion/
- /nominas/calculadora/cts/
- /nominas/calculadora/liquidacion/
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from .engine import (
    AFP_APORTE,
    AFP_TASAS,
    AFP_TOPE_REM_ASEGURABLE,
    ASIG_FAM,
    ESSALUD_TASA,
    ONP_TASA,
    RMV_2026,
    UIT_2026,
)
from .views_calculadora import _simular, _redondear


# ────────────────────────────────────────────────────────────────
# 1. Reversa: neto → bruto (búsqueda binaria)
# ────────────────────────────────────────────────────────────────

def _bruto_para_neto(neto_objetivo: Decimal, params: dict, tolerancia=Decimal('0.50')) -> Decimal:
    """
    Búsqueda binaria: encuentra el sueldo bruto que produce el neto deseado.

    Garantía: el resultado da neto entre [objetivo-tolerancia, objetivo+tolerancia]
    """
    lo = Decimal('100')
    hi = neto_objetivo * Decimal('3')  # Margen para encontrar el bruto
    for _ in range(40):
        mid = ((lo + hi) / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        r = _simular(mid, params)
        neto = r['neto']
        diff = neto - neto_objetivo
        if abs(diff) <= tolerancia:
            return mid, r
        if neto < neto_objetivo:
            lo = mid
        else:
            hi = mid
    return mid, r


@login_required
@require_http_methods(['GET', 'POST'])
def calc_reversa(request):
    """¿Qué bruto debo poner para que reciba S/X neto?"""
    result = None
    params = {}
    if request.method == 'POST':
        try:
            neto_objetivo = Decimal(request.POST.get('neto_objetivo', '0'))
            if neto_objetivo <= 0:
                raise ValueError('Neto objetivo debe ser positivo')
            params = {
                'asig_familiar': request.POST.get('asig_familiar') == 'on',
                'horas_extra':   '0', 'comisiones': '0',
                'regimen':       request.POST.get('regimen', 'ONP'),
                'afp':           request.POST.get('afp', 'Habitat'),
                'tiene_eps':     request.POST.get('tiene_eps') == 'on',
                'sctr_tasa':     '0',
            }
            bruto, detalle = _bruto_para_neto(neto_objetivo, params)
            result = {
                'neto_objetivo': neto_objetivo,
                'bruto_sugerido': bruto,
                'detalle': detalle,
                'diferencia_neto': detalle['neto'] - neto_objetivo,
                'costo_empresa': detalle['costo_full_loaded'],
            }
        except Exception as e:
            result = {'error': str(e)}

    return render(request, 'nominas/calc_reversa.html', {
        'result': result, 'params': params,
        'afp_options': list(AFP_TASAS.keys()),
    })


# ────────────────────────────────────────────────────────────────
# 2. Gratificación standalone
# ────────────────────────────────────────────────────────────────

def _calcular_gratificacion(sueldo: Decimal, meses_computables: int, tiene_eps: bool):
    """
    Ley 27735 + DS 005-2002-TR.
    Gratif = sueldo × meses_computables / 6
    Bonif extra = gratif × 9% (o 6.75% si tiene EPS)
    """
    if meses_computables < 0 or meses_computables > 6:
        raise ValueError('Meses computables entre 0 y 6')
    gratif = _redondear(sueldo * Decimal(meses_computables) / Decimal('6'))
    bonif_tasa = Decimal('6.75') if tiene_eps else Decimal('9.00')
    bonif_extra = _redondear(gratif * bonif_tasa / Decimal('100'))
    total = gratif + bonif_extra
    return {
        'gratif':       gratif,
        'bonif_tasa':   bonif_tasa,
        'bonif_extra':  bonif_extra,
        'total':        total,
        'meses':        meses_computables,
        'tiene_eps':    tiene_eps,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def calc_gratificacion(request):
    """Calcula gratificación julio o diciembre."""
    result = None
    params = {}
    if request.method == 'POST':
        try:
            sueldo = Decimal(request.POST.get('sueldo', '0'))
            meses = int(request.POST.get('meses', '6'))
            tiene_eps = request.POST.get('tiene_eps') == 'on'
            if sueldo <= 0:
                raise ValueError('Sueldo debe ser positivo')
            params = {'sueldo': sueldo, 'meses': meses, 'tiene_eps': tiene_eps}
            result = _calcular_gratificacion(sueldo, meses, tiene_eps)
        except Exception as e:
            result = {'error': str(e)}

    return render(request, 'nominas/calc_gratificacion.html', {
        'result': result, 'params': params,
    })


# ────────────────────────────────────────────────────────────────
# 3. CTS standalone
# ────────────────────────────────────────────────────────────────

def _calcular_cts(sueldo: Decimal, meses_computables: int, dias_extra: int = 0):
    """
    D.Leg. 650 + DS 004-97-TR.
    CTS = (sueldo × meses + sueldo × días/30 + 1/6 gratif × meses) / 12

    Para semestre completo (6 meses): 1/12 sueldo + 1/12 × (gratif/6)
    """
    if meses_computables < 0 or meses_computables > 6:
        raise ValueError('Meses computables entre 0 y 6 por semestre')

    # Remuneración computable mensual = sueldo + 1/6 de gratificación
    gratif_mensual = sueldo / Decimal('6')  # 1/6 de la gratificación de 1 sueldo
    rem_computable = sueldo + gratif_mensual

    # CTS mensual = rem_computable / 12
    # CTS días = (rem_computable / 12) / 30 × días

    cts_meses = _redondear(rem_computable * Decimal(meses_computables) / Decimal('12'))
    cts_dias  = _redondear(rem_computable * Decimal(dias_extra) / Decimal('12') / Decimal('30'))
    cts_total = cts_meses + cts_dias

    return {
        'sueldo':         sueldo,
        'gratif_mensual': gratif_mensual,
        'rem_computable': _redondear(rem_computable),
        'meses':          meses_computables,
        'dias_extra':     dias_extra,
        'cts_meses':      cts_meses,
        'cts_dias':       cts_dias,
        'total':          cts_total,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def calc_cts(request):
    """Calcula CTS mayo o noviembre."""
    result = None
    params = {}
    if request.method == 'POST':
        try:
            sueldo = Decimal(request.POST.get('sueldo', '0'))
            meses = int(request.POST.get('meses', '6'))
            dias = int(request.POST.get('dias_extra', '0'))
            if sueldo <= 0:
                raise ValueError('Sueldo debe ser positivo')
            params = {'sueldo': sueldo, 'meses': meses, 'dias_extra': dias}
            result = _calcular_cts(sueldo, meses, dias)
        except Exception as e:
            result = {'error': str(e)}

    return render(request, 'nominas/calc_cts.html', {
        'result': result, 'params': params,
    })


# ────────────────────────────────────────────────────────────────
# 4. Liquidación al cese
# ────────────────────────────────────────────────────────────────

def _calcular_liquidacion(sueldo: Decimal, fecha_ingreso: date, fecha_cese: date,
                          dias_vacaciones_pendientes: int = 0):
    """
    Calcula liquidación al cese: vacaciones truncas + CTS truncas +
    gratif truncas + sueldo del mes (proporcional).

    Vacaciones: 30 días sueldo / año proporcional
    CTS: por semestre corriente (mayo o noviembre)
    Gratif: por semestre corriente (jul o dic), incluye bonif 9%
    """
    if fecha_cese < fecha_ingreso:
        raise ValueError('Fecha de cese debe ser >= fecha de ingreso')

    # Días trabajados en el periodo de servicio
    dias_servicio = (fecha_cese - fecha_ingreso).days
    if dias_servicio < 0:
        dias_servicio = 0

    # ── Vacaciones truncas ──
    # 30 días sueldo / 365 días × días trabajados (proporcional)
    # Si tiene días vacacionales pendientes acumulados, suma esos también
    vac_truncas_dias = min(30 * dias_servicio / 365, 30 * 10)  # max 10 años récord
    vac_truncas_monto = _redondear(
        sueldo * Decimal(vac_truncas_dias) / Decimal('30')
    )
    vac_pendientes_monto = _redondear(
        sueldo * Decimal(dias_vacaciones_pendientes) / Decimal('30')
    )
    total_vacaciones = vac_truncas_monto + vac_pendientes_monto

    # ── Gratif trunca del semestre actual ──
    # Determinar semestre: ene-jun (jul) o jul-dic (dic)
    if fecha_cese.month <= 6:
        sem_inicio = date(fecha_cese.year, 1, 1)
    else:
        sem_inicio = date(fecha_cese.year, 7, 1)
    sem_inicio_efectivo = max(sem_inicio, fecha_ingreso)
    meses_sem = max(0, (fecha_cese.year - sem_inicio_efectivo.year) * 12 +
                       (fecha_cese.month - sem_inicio_efectivo.month))
    meses_sem = min(meses_sem, 6)
    gratif_resultado = _calcular_gratificacion(sueldo, meses_sem, tiene_eps=False)

    # ── CTS trunca del semestre CTS actual ──
    # Semestres CTS: nov-abr (depósito mayo) y may-oct (depósito nov)
    if fecha_cese.month <= 4:
        cts_sem_inicio = date(fecha_cese.year - 1, 11, 1)
    elif fecha_cese.month <= 10:
        cts_sem_inicio = date(fecha_cese.year, 5, 1)
    else:
        cts_sem_inicio = date(fecha_cese.year, 11, 1)
    cts_sem_efectivo = max(cts_sem_inicio, fecha_ingreso)
    meses_cts = max(0, (fecha_cese.year - cts_sem_efectivo.year) * 12 +
                       (fecha_cese.month - cts_sem_efectivo.month))
    meses_cts = min(meses_cts, 6)
    cts_resultado = _calcular_cts(sueldo, meses_cts)

    # ── Sueldo del mes de cese (proporcional) ──
    dias_mes_cese = fecha_cese.day
    sueldo_mes_cese = _redondear(sueldo * Decimal(dias_mes_cese) / Decimal('30'))

    # ── Total ──
    total = total_vacaciones + gratif_resultado['total'] + cts_resultado['total'] + sueldo_mes_cese

    return {
        'sueldo':             sueldo,
        'fecha_ingreso':      fecha_ingreso,
        'fecha_cese':         fecha_cese,
        'dias_servicio':      dias_servicio,
        'anios_servicio':     round(dias_servicio / 365.25, 2),
        'vacaciones': {
            'dias_truncos':   round(vac_truncas_dias, 1),
            'monto_truncos':  vac_truncas_monto,
            'dias_pendientes': dias_vacaciones_pendientes,
            'monto_pendientes': vac_pendientes_monto,
            'total':          total_vacaciones,
        },
        'gratificacion':      gratif_resultado,
        'cts':                cts_resultado,
        'sueldo_mes_cese':    sueldo_mes_cese,
        'dias_mes_cese':      dias_mes_cese,
        'total':              total,
    }


@login_required
@require_http_methods(['GET', 'POST'])
def calc_liquidacion(request):
    """Calcula liquidación al cese."""
    from datetime import datetime
    result = None
    params = {}
    if request.method == 'POST':
        try:
            sueldo = Decimal(request.POST.get('sueldo', '0'))
            fecha_ingreso = datetime.strptime(request.POST.get('fecha_ingreso', ''), '%Y-%m-%d').date()
            fecha_cese = datetime.strptime(request.POST.get('fecha_cese', ''), '%Y-%m-%d').date()
            dias_vac = int(request.POST.get('dias_vacaciones_pendientes', '0'))
            if sueldo <= 0:
                raise ValueError('Sueldo debe ser positivo')
            params = {
                'sueldo': sueldo,
                'fecha_ingreso': fecha_ingreso.isoformat(),
                'fecha_cese':    fecha_cese.isoformat(),
                'dias_vacaciones_pendientes': dias_vac,
            }
            result = _calcular_liquidacion(sueldo, fecha_ingreso, fecha_cese, dias_vac)
        except Exception as e:
            result = {'error': str(e)}

    return render(request, 'nominas/calc_liquidacion.html', {
        'result': result, 'params': params,
    })
