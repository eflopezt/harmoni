"""
Cálculo del Régimen de Construcción Civil (CAPECO-FTCCP).

Funciones PURAS (reciben Decimals, devuelven Decimals) para los conceptos
propios del régimen, más un lookup del jornal vigente por categoría. Están
separadas del motor para poder testearlas de forma aislada y auditarlas contra
la convención colectiva.

Base legal 2026: Convención Colectiva CAPECO-FTCCP (R.M. 197-2025-TR).
Categorías y jornal básico diario 2026:
    OPERARIO S/ 87.30 (BUC 32%) · OFICIAL S/ 68.50 (BUC 30%) · PEÓN S/ 61.65 (BUC 30%)

Conceptos:
  - Jornal básico   = jornal_diario × días trabajados.
  - Dominical       = 1 jornal por semana laborada (descanso remunerado).
  - BUC             = % del jornal básico según categoría (32% / 30%).
  - Bono por altura = 8% del jornal básico (2026), si el trabajador aplica.
  - CTS             = 15% del total de jornales básicos percibidos.
  - Gratificación   = 40 jornales básicos (proporcional 1/5 por mes).
  - Asig. escolar   = 30 jornales/año por hijo en edad escolar.
  - Comp. vacacional= 10% del jornal por día efectivo trabajado.
  - CONAFOVICER     = 2% (descuento) sobre el básico + dominical.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ── Tasas/constantes del régimen (2026) ────────────────────────────
CTS_CC_PCT              = Decimal('15')   # % del total de jornales básicos
GRATIF_CC_JORNALES      = Decimal('40')   # jornales por gratificación (año completo)
ASIG_ESCOLAR_JORNALES   = Decimal('30')   # jornales/año por hijo
COMP_VACACIONAL_PCT     = Decimal('10')   # % del jornal por día trabajado
CONAFOVICER_PCT         = Decimal('2')    # % descuento (aporte vivienda)
BONO_ALTURA_PCT_DEFAULT = Decimal('8')    # % del básico (2026)


def _r(val) -> Decimal:
    return Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ── Lookup del jornal vigente (DB) ─────────────────────────────────

def jornal_vigente(categoria: str, fecha):
    """Devuelve el JornalConstruccion vigente para `categoria` en `fecha`.

    Vigente = el de mayor `vigencia_desde` <= fecha (y sin vigencia_hasta o
    vigencia_hasta >= fecha). Devuelve None si no hay tabla cargada.
    """
    from django.db.models import Q
    from nominas.models import JornalConstruccion

    return (
        JornalConstruccion.objects
        .filter(categoria=categoria, vigencia_desde__lte=fecha)
        .filter(Q(vigencia_hasta__isnull=True) | Q(vigencia_hasta__gte=fecha))
        .order_by('-vigencia_desde')
        .first()
    )


# ── Conceptos (puros) ──────────────────────────────────────────────

def jornal_basico(jornal_diario: Decimal, dias_trabajados: int) -> Decimal:
    """Jornal básico del período = jornal diario × días efectivamente trabajados."""
    return _r(Decimal(jornal_diario) * Decimal(dias_trabajados))


def dominical(jornal_diario: Decimal, semanas: Decimal) -> Decimal:
    """Descanso dominical: 1 jornal por semana laborada."""
    return _r(Decimal(jornal_diario) * Decimal(semanas))


def buc(jornal_basico_total: Decimal, buc_pct: Decimal) -> Decimal:
    """BUC = % del jornal básico según categoría."""
    return _r(Decimal(jornal_basico_total) * Decimal(buc_pct) / Decimal('100'))


def bono_altura(jornal_basico_total: Decimal, pct: Decimal = BONO_ALTURA_PCT_DEFAULT) -> Decimal:
    """Bono por altura = % del jornal básico (8% en 2026)."""
    return _r(Decimal(jornal_basico_total) * Decimal(pct) / Decimal('100'))


def cts(jornales_basicos_total: Decimal) -> Decimal:
    """CTS de construcción = 15% del total de jornales básicos percibidos."""
    return _r(Decimal(jornales_basicos_total) * CTS_CC_PCT / Decimal('100'))


def gratificacion(jornal_diario: Decimal, meses_laborados: Decimal = Decimal('5')) -> Decimal:
    """Gratificación = 40 jornales por año, proporcional (1/5 por mes del semestre).

    meses_laborados: meses del semestre (0-5). Año completo = 5 → 40 jornales.
    """
    proporcion = min(Decimal(meses_laborados), Decimal('5')) / Decimal('5')
    return _r(Decimal(jornal_diario) * GRATIF_CC_JORNALES * proporcion)


def asignacion_escolar(jornal_diario: Decimal, num_hijos: int) -> Decimal:
    """Asignación escolar anual = 30 jornales por hijo en edad escolar."""
    return _r(Decimal(jornal_diario) * ASIG_ESCOLAR_JORNALES * Decimal(num_hijos))


def compensacion_vacacional(jornal_diario: Decimal, dias_trabajados: int) -> Decimal:
    """Compensación vacacional = 10% del jornal por día efectivo trabajado."""
    return _r(Decimal(jornal_diario) * COMP_VACACIONAL_PCT / Decimal('100') * Decimal(dias_trabajados))


# Bonificación por movilidad: tarifa diaria fija (CAPECO 2024-2026: S/ 8.60/día,
# igual para las tres categorías). No es porcentaje del jornal.
MOVILIDAD_DIARIA = Decimal('8.60')


def movilidad(dias_trabajados: int, diaria: Decimal = MOVILIDAD_DIARIA) -> Decimal:
    """Bonificación por movilidad = tarifa diaria × días trabajados."""
    return _r(Decimal(diaria) * Decimal(dias_trabajados))


def valor_hora(jornal_diario: Decimal) -> Decimal:
    """Valor de la hora ordinaria = jornal diario / 8."""
    return Decimal(jornal_diario) / Decimal('8')


def hora_extra(jornal_diario: Decimal, horas: Decimal, factor: Decimal) -> Decimal:
    """Monto de horas extra en construcción.

    En construcción las HHEE se pagan al 60% (primeras) y 100%. El recargo se
    aplica sobre el valor hora ordinario (jornal/8):
        monto = (jornal/8) × (1 + factor) × horas
    factor: 0.60 para HE 60%, 1.00 para HE 100%.

    Verificado contra tabla CAPECO 2026 (Operario: hora 60% = 17.86, 100% = 22.33).
    """
    return _r(valor_hora(jornal_diario) * (Decimal('1') + Decimal(str(factor))) * Decimal(horas))


def conafovicer(base: Decimal) -> Decimal:
    """CONAFOVICER = 2% (descuento) sobre básico + dominical."""
    return _r(Decimal(base) * CONAFOVICER_PCT / Decimal('100'))


# ── Afectaciones ───────────────────────────────────────────────────
#
# Matriz derivada de una boleta real (Consorcio Stiler-Ripconciv-Tecnoedil,
# sem 2026-10) + convención CAPECO-FTCCP:
#
#   Concepto            ESSALUD/AFP/ONP/SCTR   CTS   Gratif
#   ------------------  --------------------   ---   ------
#   Jornal básico              ✔                ✔      ✔
#   Dominical                  ✔                ✘      ✘
#   Horas extra (60/100)       ✔                ✘      ✘
#   BUC                        ✔                ✘      ✘
#   Bonif. altitud             ✔                ✘      ✘
#   Compensación vacacional    ✔                ✘      ✘
#   Movilidad                  ✘  (no remun.)   ✘      ✘
#   Gratificación              ✘  (Ley 29351)   ✘      —
#   Bonif. extraordinaria      ✘                ✘      ✘
#   CTS                        ✘                —      ✘
#
# La base computable (para ESSALUD 9%, AFP/ONP, SCTR, Vida Ley, Fondo Capacit.)
# es la suma de los conceptos afectos a ESSALUD.

# Códigos de concepto afectos a la base computable (afecto ESSALUD/AFP/ONP/SCTR).
CODIGOS_COMPUTABLES = {
    'cc-jornal-basico', 'cc-dominical',
    'cc-hhee-60', 'cc-hhee-100', 'cc-hhee-100-dom',
    'cc-buc', 'cc-bae', 'cc-bono-altura', 'cc-bono-altitud',
    'cc-comp-vacacional',
}
# Conceptos NO afectos (fuera de la base computable).
CODIGOS_NO_COMPUTABLES = {
    'cc-movilidad', 'cc-gratif-julio', 'cc-bonif-extraord',
    'cc-cts', 'cc-asig-escolar',
}


def base_computable(lineas: dict) -> Decimal:
    """Suma los conceptos afectos (ESSALUD/AFP/ONP/SCTR).

    Args:
        lineas: dict {codigo_concepto: monto}.
    Returns:
        Suma de los montos cuyos códigos están en CODIGOS_COMPUTABLES.
    """
    return _r(sum(
        (Decimal(m) for cod, m in lineas.items() if cod in CODIGOS_COMPUTABLES),
        Decimal('0'),
    ))


# ── Ensamblado de la boleta de construcción civil ──────────────────

# Tasas por defecto (verificadas contra boleta real; SCTR/Vida Ley pueden
# variar por póliza — se pueden sobreescribir vía `tasas`).
TASAS_CC_DEFAULT = {
    'essalud':            Decimal('9'),
    'afp_aporte':         Decimal('10'),
    'onp':                Decimal('13'),
    'sctr_salud':         Decimal('0.65'),
    'sctr_pension':       Decimal('0.65'),
    'vida_ley':           Decimal('0.45'),
    'fondo_capacitacion': Decimal('0.45'),
    'essalud_vida_fijo':  Decimal('5.00'),
}

# Conceptos de INGRESO que llegan como monto ya calculado por trabajador
# (horas extra, movilidad, bonos de convenio, gratif/CTS prorrateadas).
INGRESO_INPUT_CODES = [
    'cc-hhee-60', 'cc-hhee-100', 'cc-hhee-100-dom', 'cc-movilidad',
    'cc-bono-altitud', 'cc-bono-altura', 'cc-bae',
    'cc-gratif-julio', 'cc-bonif-extraord', 'cc-cts', 'cc-asig-escolar',
]
# Conceptos de DESCUENTO que llegan como monto ya calculado (IR 5ta, AFP
# comisión+seguro, cuota sindical, otros).
DESCUENTO_INPUT_CODES = [
    'cc-ir-5ta', 'cc-afp-comseg', 'cc-cuota-sindical', 'cc-otros-descuentos',
]


def _jornal_diario(registro) -> Decimal:
    """Jornal diario del trabajador: de la tabla CAPECO por categoría, o del
    sueldo_base del registro como fallback."""
    personal = getattr(registro, 'personal', None)
    categoria = getattr(personal, 'categoria_construccion', '') if personal else ''
    periodo = getattr(registro, 'periodo', None)
    fecha = getattr(periodo, 'fecha_fin', None) if periodo is not None else None
    if categoria and fecha:
        j = jornal_vigente(categoria, fecha)
        if j:
            return Decimal(j.jornal_diario)
    return Decimal(getattr(registro, 'sueldo_base', 0) or 0)


def _buc_pct(registro) -> Decimal:
    """% de BUC del trabajador (de la tabla por categoría, o 32% por defecto)."""
    personal = getattr(registro, 'personal', None)
    categoria = getattr(personal, 'categoria_construccion', '') if personal else ''
    periodo = getattr(registro, 'periodo', None)
    fecha = getattr(periodo, 'fecha_fin', None) if periodo is not None else None
    if categoria and fecha:
        j = jornal_vigente(categoria, fecha)
        if j:
            return Decimal(j.buc_pct)
    return Decimal('32')


def calcular_boleta_construccion(registro, *, tasas=None) -> dict:
    """Ensambla la boleta de un trabajador de construcción civil.

    Conceptos por FÓRMULA: jornal, dominical, BUC, compensación vacacional,
    CONAFOVICER, ESSALUD, SCTR, Vida Ley, Fondo Capacitación, y AFP aporte (10%)
    u ONP (13%) sobre la base computable.
    Conceptos por INPUT (registro.conceptos_manuales, montos en S/): horas extra,
    movilidad, bonos de convenio, gratificación/CTS prorrateadas, IR 5ta, AFP
    comisión+seguro, cuota sindical.

    Devuelve un dict con `lineas` (por código) y los totales/aportes, compatible
    con el flujo de nómina. Validado al céntimo contra una boleta real.
    """
    t = dict(TASAS_CC_DEFAULT)
    if tasas:
        t.update(tasas)

    manuales = getattr(registro, 'conceptos_manuales', None) or {}
    dias = int(getattr(registro, 'dias_trabajados', 0) or 0)
    jornal = _jornal_diario(registro)
    es_onp = (getattr(registro, 'regimen_pension', 'AFP') == 'ONP')

    lineas = []

    def _add(codigo, monto, *, base=Decimal('0'), pct=Decimal('0'), obs=''):
        m = _r(monto)
        lineas.append({'codigo': codigo, 'base_calculo': _r(base),
                       'porcentaje_aplicado': pct, 'monto': m, 'observacion': obs})
        return m

    # ── INGRESOS por fórmula ──
    jornal_sem = _add('cc-jornal-basico', jornal_basico(jornal, dias),
                      base=jornal, obs=f'{dias} jornales')
    dom = _add('cc-dominical', dominical(jornal, Decimal(dias) / Decimal('6')), base=jornal)
    buc_pct = _buc_pct(registro)
    _add('cc-buc', buc(jornal_sem, buc_pct), base=jornal_sem, pct=buc_pct)
    _add('cc-comp-vacacional', compensacion_vacacional(jornal, dias), base=jornal)

    # ── INGRESOS por input ──
    for cod in INGRESO_INPUT_CODES:
        if cod in manuales:
            _add(cod, Decimal(str(manuales[cod])))

    # Mapa {codigo: monto} de ingresos para la base computable.
    ing = {l['codigo']: l['monto'] for l in lineas}
    total_ingresos = _r(sum((l['monto'] for l in lineas), Decimal('0')))
    base_comp = base_computable(ing)

    # ── DESCUENTOS del trabajador ──
    if es_onp:
        _add('cc-onp', base_comp * t['onp'] / Decimal('100'),
             base=base_comp, pct=t['onp'])
    else:
        _add('cc-afp-aporte', base_comp * t['afp_aporte'] / Decimal('100'),
             base=base_comp, pct=t['afp_aporte'])
    # CONAFOVICER 2% sobre jornal básico + dominical
    _add('cc-conafovicer', conafovicer(jornal_sem + dom), base=jornal_sem + dom, pct=CONAFOVICER_PCT)
    for cod in DESCUENTO_INPUT_CODES:
        if cod in manuales:
            _add(cod, Decimal(str(manuales[cod])))

    total_descuentos = _r(sum(
        (l['monto'] for l in lineas if l['codigo'] in
         (['cc-onp', 'cc-afp-aporte', 'cc-conafovicer'] + DESCUENTO_INPUT_CODES)),
        Decimal('0'),
    ))
    neto = _r(total_ingresos - total_descuentos)

    # ── APORTES del empleador ──
    essalud     = _r(base_comp * t['essalud'] / Decimal('100'))
    sctr_salud  = _r(base_comp * t['sctr_salud'] / Decimal('100'))
    sctr_pension = _r(base_comp * t['sctr_pension'] / Decimal('100'))
    vida_ley    = _r(base_comp * t['vida_ley'] / Decimal('100'))
    fondo_capac = _r((jornal_sem + dom) * t['fondo_capacitacion'] / Decimal('100'))
    essalud_vida = _r(t['essalud_vida_fijo'])
    total_aportaciones = _r(essalud + sctr_salud + sctr_pension + vida_ley + fondo_capac + essalud_vida)

    costo_total_empresa = _r(total_ingresos + total_aportaciones)

    return {
        'lineas':               lineas,
        'total_ingresos':       total_ingresos,
        'total_descuentos':     total_descuentos,
        'neto_a_pagar':         neto,
        'rem_computable':       base_comp,
        'aporte_essalud':       essalud,
        'aporte_sctr_salud':    sctr_salud,
        'aporte_sctr_pension':  sctr_pension,
        'aporte_vida_ley':      vida_ley,
        'aporte_fondo_capacitacion': fondo_capac,
        'aporte_essalud_vida':  essalud_vida,
        'total_aportaciones':   total_aportaciones,
        'costo_total_empresa':  costo_total_empresa,
    }
