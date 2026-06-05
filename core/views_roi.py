"""
Calculadora ROI — Harmoni vs proceso actual.

URL: /roi/

Form: # trabajadores, horas/mes en planilla, costo hora RRHH.
Calcula:
- Ahorro mensual y anual (S/.)
- Payback en meses
- ROI % anual

Sirve para que el cliente vea NÚMEROS, no promesas.
"""
from decimal import Decimal

from django.shortcuts import render
from django.views.decorators.http import require_http_methods


# Precios Harmoni por plan (derivados de core/planes.py).
from core.planes import PLANES as _PLANES

PRECIOS_PLAN = {
    code: {
        'mensual':     meta['precio'] or 1500,          # estimado para tope sin precio
        'max_workers': meta['max_trab'] or 9999,
        'nombre':      meta['nombre'],
    }
    for code, meta in _PLANES.items()
}


def _recomendar_plan(n_workers):
    """Devuelve la key del plan recomendado según headcount (por tope de cada plan)."""
    for code, meta in sorted(_PLANES.items(), key=lambda kv: kv[1]['nivel']):
        tope = meta['max_trab']
        if tope is None or n_workers <= tope:
            return code
    return 'SUITE'


@require_http_methods(['GET', 'POST'])
def calculadora_roi(request):
    """Vista pública (sin login) — calculadora interactiva."""

    # Defaults (cliente típico grupo gastronómico mediano)
    defaults = {
        'n_workers':     100,
        'horas_mes':     40,
        'costo_hora':    35,
        'errores_mes':   3,
        'costo_error':   200,
    }

    if request.method == 'POST':
        try:
            n_workers   = int(request.POST.get('n_workers', defaults['n_workers']))
            horas_mes   = float(request.POST.get('horas_mes', defaults['horas_mes']))
            costo_hora  = float(request.POST.get('costo_hora', defaults['costo_hora']))
            errores_mes = float(request.POST.get('errores_mes', defaults['errores_mes']))
            costo_error = float(request.POST.get('costo_error', defaults['costo_error']))
        except Exception:
            n_workers, horas_mes, costo_hora = (defaults['n_workers'], defaults['horas_mes'], defaults['costo_hora'])
            errores_mes, costo_error = defaults['errores_mes'], defaults['costo_error']
    else:
        n_workers, horas_mes, costo_hora = (defaults['n_workers'], defaults['horas_mes'], defaults['costo_hora'])
        errores_mes, costo_error = defaults['errores_mes'], defaults['costo_error']

    # ── Cálculos ──
    # Costo actual del proceso manual
    costo_horas_mes      = horas_mes * costo_hora
    costo_errores_mes    = errores_mes * costo_error
    costo_actual_mes     = costo_horas_mes + costo_errores_mes
    costo_actual_anual   = costo_actual_mes * 12

    # Plan recomendado
    plan_key = _recomendar_plan(n_workers)
    plan = PRECIOS_PLAN[plan_key]
    harmoni_mes   = plan['mensual']
    harmoni_anual = harmoni_mes * 12 * 1.18   # + IGV

    # Ahorro: Harmoni reduce 80% de las horas + 90% de errores
    horas_ahorradas_mes = horas_mes * 0.80
    errores_ahorrados_mes = errores_mes * 0.90
    ahorro_mes_bruto = (horas_ahorradas_mes * costo_hora) + (errores_ahorrados_mes * costo_error)
    ahorro_neto_mes = ahorro_mes_bruto - harmoni_mes * 1.18
    ahorro_neto_anual = ahorro_neto_mes * 12

    # Payback (meses para recuperar 1 año de Harmoni si pagara upfront)
    if ahorro_mes_bruto > 0:
        payback_meses = round((harmoni_mes * 1.18) / ahorro_mes_bruto * 12, 1)
    else:
        payback_meses = 999

    # ROI %
    if harmoni_anual > 0:
        roi_pct = round((ahorro_neto_anual / harmoni_anual) * 100, 0)
    else:
        roi_pct = 0

    ctx = {
        # Inputs
        'n_workers':            n_workers,
        'horas_mes':            horas_mes,
        'costo_hora':           costo_hora,
        'errores_mes':          errores_mes,
        'costo_error':          costo_error,
        # Cálculos
        'costo_horas_mes':      round(costo_horas_mes, 2),
        'costo_errores_mes':    round(costo_errores_mes, 2),
        'costo_actual_mes':     round(costo_actual_mes, 2),
        'costo_actual_anual':   round(costo_actual_anual, 2),
        # Harmoni
        'plan':                 plan,
        'harmoni_mes':          round(harmoni_mes * 1.18, 2),
        'harmoni_anual':        round(harmoni_anual, 2),
        # Ahorros
        'horas_ahorradas_mes':  round(horas_ahorradas_mes, 1),
        'ahorro_mes_bruto':     round(ahorro_mes_bruto, 2),
        'ahorro_neto_mes':      round(ahorro_neto_mes, 2),
        'ahorro_neto_anual':    round(ahorro_neto_anual, 2),
        'payback_meses':        payback_meses,
        'roi_pct':              roi_pct,
        # Flag
        'has_results':          True,
    }

    return render(request, 'roi/calculadora.html', ctx)
