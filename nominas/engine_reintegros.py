"""
Engine de Reintegros — Corrección de planillas anteriores.

Cuando hay un error en planilla pasada (sueldo mal, HE no pagadas,
asignación familiar omitida, etc.), se calcula la diferencia y se
aplica como REINTEGRO en la planilla del período actual.

Impactos a recalcular cuando hay reintegro:
- IR 5ta categoría (el reintegro suma a la base imponible del año actual,
  no del año original — criterio SUNAT)
- AFP / ONP (sobre el monto reintegrado, mismo régimen del trabajador)
- ESSALUD empleador (sobre el monto reintegrado)

Base legal:
- TUO LIR Art. 79°: "Las rentas se imputan al período en que se
  perciben" — por eso el reintegro afecta el año actual fiscalmente,
  aunque el origen sea de un período anterior.
- D.Leg. 728: Reintegros son remunerativos si el origen también lo era.
- Ley 26790: ESSALUD se aporta sobre el reintegro si era remunerativo.
"""
from decimal import Decimal, ROUND_HALF_UP
from datetime import date

from .engine import (
    AFP_APORTE,
    AFP_TASAS,
    AFP_TOPE_REM_ASEGURABLE,
    ESSALUD_TASA,
    ONP_TASA,
    _redondear,
    _get_tasas_afp,
    _get_uit,
)


def calcular_diferencia_sueldo(
    sueldo_pagado: Decimal,
    sueldo_correcto: Decimal,
) -> dict:
    """
    Caso típico: "Le pagamos S/2500 cuando debió ser S/3000".

    Returns:
        {
            'sueldo_pagado': 2500,
            'sueldo_correcto': 3000,
            'diferencia': 500,
            'tipo': 'A_FAVOR_TRABAJADOR',  # o 'DESCUENTO'
        }
    """
    sueldo_pagado = Decimal(sueldo_pagado or 0)
    sueldo_correcto = Decimal(sueldo_correcto or 0)
    diferencia = sueldo_correcto - sueldo_pagado

    return {
        'sueldo_pagado':    sueldo_pagado,
        'sueldo_correcto':  sueldo_correcto,
        'diferencia':       diferencia,
        'tipo':             'A_FAVOR_TRABAJADOR' if diferencia > 0 else
                            ('DESCUENTO' if diferencia < 0 else 'SIN_CAMBIO'),
        'es_relevante':     abs(diferencia) >= Decimal('0.01'),
    }


def simular_impacto_aportes(
    monto_reintegro: Decimal,
    regimen: str = 'ONP',
    afp_nombre: str = 'Habitat',
    tiene_eps: bool = False,
    es_remunerativo: bool = True,
) -> dict:
    """
    Simula los aportes y descuentos que aplican al reintegro.

    Args:
        monto_reintegro: Monto bruto del reintegro.
        regimen:         'ONP' o 'AFP'.
        afp_nombre:      Nombre AFP si régimen=AFP.
        tiene_eps:       Si tiene EPS, ESSALUD baja a 6.75%.
        es_remunerativo: Si False (ej: bonif extraordinaria) → no afecta aportes.

    Returns:
        {
            'descuentos': {
                'ONP': 65.00,            # o
                'AFP_aporte': 50.00, ...
                'IR_5ta_ajuste': 12.50,  # ajuste estimado
            },
            'aportes_empleador': {
                'ESSALUD': 45.00,
                # SCTR si construcción civil
            },
            'monto_bruto': 500,
            'total_descuentos': 65 (o suma AFP),
            'monto_neto': 435,
        }
    """
    monto = Decimal(monto_reintegro or 0)
    if monto == 0 or not es_remunerativo:
        return {
            'descuentos':         {},
            'aportes_empleador':  {},
            'monto_bruto':        monto,
            'total_descuentos':   Decimal('0'),
            'monto_neto':         monto,
            'es_remunerativo':    es_remunerativo,
            'nota':               'No remunerativo — sin aportes' if not es_remunerativo else 'Monto cero',
        }

    descuentos = {}
    aportes_emp = {}

    # ── Régimen pensionario ──
    if regimen == 'AFP':
        tasas = _get_tasas_afp(afp_nombre)
        aporte = _redondear(monto * AFP_APORTE / Decimal('100'))
        comision = _redondear(monto * tasas['comision_flujo'] / Decimal('100'))
        # Seguro: aplica solo hasta el tope RMA
        base_seguro = min(monto, AFP_TOPE_REM_ASEGURABLE)
        seguro = _redondear(base_seguro * tasas['seguro'] / Decimal('100'))
        descuentos[f'AFP_{afp_nombre}_aporte_10pct']      = aporte
        descuentos[f'AFP_{afp_nombre}_comision']          = comision
        descuentos[f'AFP_{afp_nombre}_seguro']            = seguro
    else:
        # ONP 13%
        descuentos['ONP_13pct'] = _redondear(monto * ONP_TASA / Decimal('100'))

    # ── IR 5ta estimado (impacto marginal — el agente puede recalcular full) ──
    # Aplicamos tasa marginal aproximada: si el trabajador ya está en escala 14%, suma 14% del reintegro.
    # Esto es estimado — el cálculo exacto requiere reproyectar IR anual.
    # Para simplicidad: si el monto > 0, ajuste estimado 14% (tasa promedio 2da escala)
    if monto > Decimal('1000'):
        ir_estimado = _redondear(monto * Decimal('14') / Decimal('100'))
        descuentos['IR_5ta_ajuste_estimado'] = ir_estimado

    # ── ESSALUD empleador ──
    essalud_tasa = Decimal('6.75') if tiene_eps else ESSALUD_TASA
    aportes_emp['ESSALUD'] = _redondear(monto * essalud_tasa / Decimal('100'))

    total_descuentos = sum(descuentos.values(), Decimal('0'))
    monto_neto = _redondear(monto - total_descuentos)

    return {
        'descuentos':         {k: _redondear(v) for k, v in descuentos.items()},
        'aportes_empleador':  {k: _redondear(v) for k, v in aportes_emp.items()},
        'monto_bruto':        monto,
        'total_descuentos':   _redondear(total_descuentos),
        'monto_neto':         monto_neto,
        'regimen':            regimen,
        'tiene_eps':          tiene_eps,
        'es_remunerativo':    True,
    }


def calcular_reintegro_he_no_pagadas(
    horas_extra_no_pagadas: Decimal,
    sueldo_mensual: Decimal,
    tipo_he: str = 'HE_25',
) -> dict:
    """
    Reintegro por HE no pagadas en período anterior.

    Args:
        horas_extra_no_pagadas: Cantidad de HE pendientes.
        sueldo_mensual:         Sueldo base del trabajador.
        tipo_he:                'HE_25', 'HE_35', 'HE_100'.
    """
    from .engine import calcular_he

    monto = calcular_he(horas_extra_no_pagadas, sueldo_mensual, tipo_he)
    return {
        'horas':         Decimal(horas_extra_no_pagadas or 0),
        'sueldo':        Decimal(sueldo_mensual or 0),
        'tipo_he':       tipo_he,
        'monto':         monto,
        'descripcion':   f'{horas_extra_no_pagadas}h × {tipo_he} no pagadas',
    }


def calcular_reintegro_asignacion_familiar(
    meses_pendientes: int,
    asig_fam_mensual: Decimal = Decimal('113.00'),
) -> dict:
    """
    Reintegro por asignación familiar omitida.

    Args:
        meses_pendientes:  Cuántos meses no se pagó.
        asig_fam_mensual:  Monto mensual de asig fam (10% RMV).
    """
    monto = _redondear(asig_fam_mensual * Decimal(meses_pendientes or 0))
    return {
        'meses_pendientes': int(meses_pendientes or 0),
        'monto_mensual':    asig_fam_mensual,
        'monto_total':      monto,
        'descripcion':      f'Asignación familiar de {meses_pendientes} mes(es) omitidos',
    }


def calcular_reintegro_gratificacion(
    monto_pagado: Decimal,
    monto_correcto: Decimal,
    tiene_eps: bool = False,
) -> dict:
    """
    Reintegro por gratificación mal calculada.

    Recordar: la bonificación extraordinaria 9% (o 6.75% EPS) se calcula
    sobre la diferencia, NO sobre el monto original (Ley 30334).
    """
    monto_pagado = Decimal(monto_pagado or 0)
    monto_correcto = Decimal(monto_correcto or 0)
    diferencia = monto_correcto - monto_pagado

    if diferencia <= 0:
        return {
            'monto_pagado':       monto_pagado,
            'monto_correcto':     monto_correcto,
            'diferencia':         diferencia,
            'bonif_extra':        Decimal('0'),
            'monto_reintegro':    Decimal('0'),
            'descripcion':        'Sin diferencia a favor del trabajador',
        }

    bonif_tasa = Decimal('6.75') if tiene_eps else Decimal('9.00')
    bonif = _redondear(diferencia * bonif_tasa / Decimal('100'))
    total = diferencia + bonif

    return {
        'monto_pagado':       monto_pagado,
        'monto_correcto':     monto_correcto,
        'diferencia':         diferencia,
        'bonif_tasa':         bonif_tasa,
        'bonif_extra':        bonif,
        'monto_reintegro':    total,
        'descripcion':        f'Reintegro gratif: dif S/{diferencia} + bonif {bonif_tasa}%',
    }


def calcular_impacto_total_reintegro(
    monto_reintegro: Decimal,
    personal=None,
    regimen: str = 'ONP',
    afp_nombre: str = 'Habitat',
    tiene_eps: bool = False,
    es_remunerativo: bool = True,
) -> dict:
    """
    Función central — calcula TODOS los impactos de un reintegro.

    Devuelve un dict listo para crear ReintegroNomina:
        - monto_reintegro
        - impacto_ir_5ta
        - impacto_aportes (dict con AFP/ONP/ESSALUD)
        - monto_neto_reintegro
        - costo_empresa_total (reintegro + aportes empleador)

    Si recibe personal, intenta leer su régimen y EPS automáticamente.
    """
    if personal is not None:
        regimen_p = getattr(personal, 'regimen_pension', None) or getattr(personal, 'sistema_pensionario', None)
        if regimen_p:
            if 'AFP' in str(regimen_p).upper():
                regimen = 'AFP'
                afp_nombre = (
                    getattr(personal, 'afp', None) or
                    str(regimen_p).replace('AFP_', '').replace('AFP ', '').title() or
                    afp_nombre
                )
            else:
                regimen = 'ONP'
        tiene_eps = bool(getattr(personal, 'tiene_eps', tiene_eps))

    impacto = simular_impacto_aportes(
        monto_reintegro=monto_reintegro,
        regimen=regimen,
        afp_nombre=afp_nombre,
        tiene_eps=tiene_eps,
        es_remunerativo=es_remunerativo,
    )

    # Estimación IR 5ta (impacto marginal)
    impacto_ir = impacto['descuentos'].get('IR_5ta_ajuste_estimado', Decimal('0'))

    # Aportes empleador (costo adicional para la empresa)
    aportes_emp_total = sum(impacto['aportes_empleador'].values(), Decimal('0'))
    costo_empresa_total = _redondear(Decimal(monto_reintegro or 0) + aportes_emp_total)

    return {
        'monto_reintegro':       Decimal(monto_reintegro or 0),
        'impacto_ir_5ta':        impacto_ir,
        'impacto_aportes':       {
            **impacto['descuentos'],
            **{f'EMP_{k}': v for k, v in impacto['aportes_empleador'].items()},
        },
        'monto_neto_reintegro':  impacto['monto_neto'],
        'costo_empresa_total':   costo_empresa_total,
        'regimen':               regimen,
        'tiene_eps':             tiene_eps,
        'es_remunerativo':       es_remunerativo,
    }
