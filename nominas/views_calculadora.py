"""
Calculadora Simulador de Planilla — Perú 2026.

Tool web pública (sin DB) que ingresa sueldo + perfil del trabajador
y devuelve el desglose completo: AFP/ONP, ESSALUD empleador, IR 5ta,
asignación familiar, neto a pagar, y costo total para la empresa.

Útil para:
- Vendedores explicando ROI al prospecto
- Trabajadores estimando su recibo antes del cierre
- Onboarding de cliente nuevo ("muéstrame cómo va a calcular Y")
- Demos rápidos sin necesidad de cargar trabajador real

URL: /nominas/calculadora/  (login required, no superuser — accesible a trabajadores)
"""
from decimal import Decimal, ROUND_HALF_UP

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


def _redondear(v: Decimal) -> Decimal:
    return v.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _ir5ta_anual(rem_anual: Decimal, uit: Decimal = UIT_2026) -> Decimal:
    """IR 5ta progresional con escala 2026.

    Escala vigente (sobre lo que excede 7 UIT):
      - hasta 5 UIT:     8%
      - hasta 20 UIT:    14%
      - hasta 35 UIT:    17%
      - hasta 45 UIT:    20%
      - más de 45 UIT:   30%
    """
    base = max(rem_anual - 7 * uit, Decimal('0'))
    if base <= 0:
        return Decimal('0')

    tramos = [
        (5 * uit,  Decimal('8')),
        (15 * uit, Decimal('14')),  # 20-5=15
        (15 * uit, Decimal('17')),  # 35-20=15
        (10 * uit, Decimal('20')),  # 45-35=10
        (None,     Decimal('30')),
    ]
    impuesto = Decimal('0')
    restante = base
    for tope, tasa in tramos:
        if tope is None:
            tramo = restante
        else:
            tramo = min(restante, tope)
        impuesto += tramo * tasa / Decimal('100')
        restante -= tramo
        if restante <= 0:
            break
    return _redondear(impuesto)


def _simular(sueldo: Decimal, params: dict) -> dict:
    """Núcleo: dado sueldo + params, devuelve dict con todo el desglose."""
    asig_familiar     = ASIG_FAM if params.get('asig_familiar') else Decimal('0')
    horas_extra       = Decimal(params.get('horas_extra') or '0')
    comisiones        = Decimal(params.get('comisiones') or '0')

    # ── INGRESOS ──────────────────────────────────────────────────
    rem_basico        = sueldo
    rem_total         = rem_basico + asig_familiar + horas_extra + comisiones

    # ── DESCUENTOS (trabajador) ───────────────────────────────────
    regimen = params.get('regimen', 'ONP')  # ONP / AFP
    afp_nombre = params.get('afp', 'Habitat')
    tiene_eps = bool(params.get('tiene_eps', False))

    descuentos = {}

    if regimen == 'AFP':
        tasas = AFP_TASAS.get(afp_nombre, AFP_TASAS['Habitat'])
        # Aporte 10% sobre rem total (sin tope)
        aporte = _redondear(rem_total * AFP_APORTE / Decimal('100'))
        # Comisión flujo sobre rem total (sin tope)
        comision = _redondear(rem_total * tasas['comision_flujo'] / Decimal('100'))
        # Prima seguro: hasta tope RMA
        base_seguro = min(rem_total, AFP_TOPE_REM_ASEGURABLE)
        seguro = _redondear(base_seguro * tasas['seguro'] / Decimal('100'))

        descuentos['afp_aporte']   = {'label': f'AFP {afp_nombre} aporte 10%',                   'monto': aporte}
        descuentos['afp_comision'] = {'label': f'AFP {afp_nombre} comisión {tasas["comision_flujo"]}%', 'monto': comision}
        descuentos['afp_seguro']   = {'label': f'AFP {afp_nombre} prima seguro {tasas["seguro"]}%',     'monto': seguro}
    else:
        onp = _redondear(rem_total * ONP_TASA / Decimal('100'))
        descuentos['onp'] = {'label': f'ONP 13%', 'monto': onp}

    # IR 5ta — proyección anual / 12 (simplificado)
    # Anualizado: rem * 14 (12 sueldos + 2 gratifs)
    rem_anual_proj = rem_basico * Decimal('14')  # solo sueldo básico para proyección base
    if params.get('asig_familiar'):
        rem_anual_proj += asig_familiar * 12  # asignación familiar no entra en gratif (es no remunerativo si está exonerado, pero es REM en realidad)
    ir_anual = _ir5ta_anual(rem_anual_proj)
    ir_mensual = _redondear(ir_anual / Decimal('12'))
    if ir_mensual > 0:
        descuentos['ir_5ta'] = {'label': 'IR 5ta Categoría (mensual)', 'monto': ir_mensual}

    # EPS empleado (si tiene EPS, aporta 2.25% adicional opcional)
    # Lo dejamos fuera por simplicidad (es opcional según el plan EPS)

    total_descuentos = sum(d['monto'] for d in descuentos.values()) or Decimal('0')
    neto = _redondear(rem_total - total_descuentos)

    # ── APORTES EMPLEADOR ─────────────────────────────────────────
    # ESSALUD 9% sobre rem total (o 6.75% si tiene EPS por crédito 25%)
    if tiene_eps:
        essalud_tasa_efectiva = Decimal('6.75')  # 9% - (9% × 25%) = 6.75%
    else:
        essalud_tasa_efectiva = ESSALUD_TASA
    essalud = _redondear(rem_total * essalud_tasa_efectiva / Decimal('100'))

    # SCTR (opcional, default 1.50% para construcción)
    sctr_tasa = Decimal(params.get('sctr_tasa') or '0')
    sctr = _redondear(rem_total * sctr_tasa / Decimal('100'))

    aportes_empleador = {
        'essalud': {'label': f'ESSALUD {essalud_tasa_efectiva}%', 'monto': essalud},
    }
    if sctr > 0:
        aportes_empleador['sctr'] = {'label': f'SCTR {sctr_tasa}%', 'monto': sctr}

    total_aportes_empleador = sum(a['monto'] for a in aportes_empleador.values()) or Decimal('0')
    costo_total = _redondear(rem_total + total_aportes_empleador)

    # ── PROVISIONES (estimadas mensuales) ─────────────────────────
    # Para mostrar costo "fully loaded"
    grat_mensual = _redondear(rem_total / Decimal('6'))   # 1 sueldo cada 6 meses
    bonif_grat_tasa = Decimal('6.75') if tiene_eps else Decimal('9.00')
    bonif_grat_mensual = _redondear(grat_mensual * bonif_grat_tasa / Decimal('100'))
    cts_mensual = _redondear(rem_total * Decimal('1.0833') / Decimal('100'))  # 1/12 + 1/12*1/6

    provisiones = {
        'gratif':       {'label': 'Provisión gratificación (1/6)',         'monto': grat_mensual},
        'bonif_grat':   {'label': f'Provisión bonif. extra grat. ({bonif_grat_tasa}%)', 'monto': bonif_grat_mensual},
        'cts':          {'label': 'Provisión CTS (1/12 + 1/72)',           'monto': cts_mensual},
        'vacaciones':   {'label': 'Provisión vacaciones (1/12 sueldo)',    'monto': _redondear(rem_total / Decimal('12'))},
    }
    total_provisiones = sum(p['monto'] for p in provisiones.values())
    costo_full_loaded = _redondear(costo_total + total_provisiones)

    return {
        # Inputs
        'sueldo':              rem_basico,
        'asig_familiar':       asig_familiar,
        'horas_extra':         horas_extra,
        'comisiones':          comisiones,
        'rem_total':           rem_total,
        'regimen':             regimen,
        'afp_nombre':          afp_nombre if regimen == 'AFP' else None,
        'tiene_eps':           tiene_eps,

        # Resultados
        'descuentos':          descuentos,
        'total_descuentos':    _redondear(total_descuentos),
        'neto':                neto,
        'aportes_empleador':   aportes_empleador,
        'total_aportes':       _redondear(total_aportes_empleador),
        'costo_total':         costo_total,
        'provisiones':         provisiones,
        'total_provisiones':   _redondear(total_provisiones),
        'costo_full_loaded':   costo_full_loaded,

        # Métricas útiles
        'pct_descuentos':      _redondear(total_descuentos / rem_total * 100) if rem_total else Decimal('0'),
        'pct_carga_empleador': _redondear(total_aportes_empleador / rem_total * 100) if rem_total else Decimal('0'),
    }


@login_required
@require_http_methods(['GET', 'POST'])
def calculadora_planilla(request):
    """Calculadora simulador — no toca DB."""
    result = None
    params = {}

    if request.method == 'POST':
        try:
            sueldo = Decimal(request.POST.get('sueldo', '0'))
            if sueldo <= 0:
                raise ValueError('Sueldo debe ser positivo')
            params = {
                'asig_familiar':  request.POST.get('asig_familiar') == 'on',
                'horas_extra':    request.POST.get('horas_extra') or '0',
                'comisiones':     request.POST.get('comisiones') or '0',
                'regimen':        request.POST.get('regimen', 'ONP'),
                'afp':            request.POST.get('afp', 'Habitat'),
                'tiene_eps':      request.POST.get('tiene_eps') == 'on',
                'sctr_tasa':      request.POST.get('sctr_tasa') or '0',
            }
            result = _simular(sueldo, params)
        except (ValueError, Exception) as e:
            result = {'error': str(e)}

    return render(request, 'nominas/calculadora.html', {
        'result':       result,
        'params':       params,
        'afp_options':  list(AFP_TASAS.keys()),
        'rmv_2026':     RMV_2026,
        'uit_2026':     UIT_2026,
        'asig_fam':     ASIG_FAM,
        'tope_rma':     AFP_TOPE_REM_ASEGURABLE,
    })
