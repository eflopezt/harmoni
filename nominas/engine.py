"""
Motor de Cálculo de Nómina — Perú 2026.

Implementa:
- AFP (aporte 10% + comisión flujo + prima seguro) por AFP
- ONP 13%
- EsSalud 9% (aporte empleador)
- Asignación familiar (10% RMV)
- Horas extra (25% / 35% / 100%)
- IR 5ta Categoría (retención mensual anualizada)
- Gratificación (julio/diciembre)
- CTS (mayo/noviembre)

Referencia legal:
- AFP: Resolución SBS N° 2026-xxx (tasas vigentes 2026)
- ONP: DL 19990 — 13% sin tope desde 2013
- EsSalud: Ley 26790 Art. 6 — 9%
- IR 5ta: Art. 53° + 75° TUO LIR — escala progresional, 7 UIT deducción
- Gratif: Ley 27735 Art. 2 — 1 sueldo en julio y 1 en diciembre
- CTS: DL 650 Art. 21 — 1/12 sueldo por mes trabajado
"""
import logging
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)


# ── Tasas AFP vigentes Q2 2026 (Circular SBS) ───────────────────────
# Comisión por flujo y prima de seguro fijadas por SBS cada cuatrimestre.
# La prima de seguro es **tope común** publicado por SBS y es igual para
# las 4 AFP. Las comisiones por flujo varían por AFP.
#
# Vigencia: abril-julio 2026 (Resolución SBS).
#   - Habitat:   1.47% comisión / 1.74% prima seguro
#   - Integra:   1.55% comisión / 1.74% prima seguro
#   - Prima:     1.60% comisión / 1.74% prima seguro
#   - Profuturo: 1.69% comisión / 1.74% prima seguro
#
# El admin puede sobreescribir por período en ConfiguracionSistema si
# la SBS publica nuevos valores antes del próximo release.
AFP_TASAS = {
    'Habitat':   {'comision_flujo': Decimal('1.47'), 'seguro': Decimal('1.74')},
    'Integra':   {'comision_flujo': Decimal('1.55'), 'seguro': Decimal('1.74')},
    'Prima':     {'comision_flujo': Decimal('1.60'), 'seguro': Decimal('1.74')},
    'Profuturo': {'comision_flujo': Decimal('1.69'), 'seguro': Decimal('1.74')},
}
AFP_APORTE    = Decimal('10.00')   # % obligatorio sobre rem. asegurable
ONP_TASA      = Decimal('13.00')   # % — DL 19990, sin tope
ESSALUD_TASA  = Decimal('9.00')    # % aporte empleador

# Aportes/primas de riesgo del empleador — fallbacks (editables en
# ConfiguracionSistema sin redeploy).
#   SCTR: Ley 26790 + DS 003-98-SA. Solo trabajadores en actividad de riesgo
#         (Anexo 5 DS 009-97-SA) → gobernado por Personal.afecto_sctr.
#   Vida Ley: D.Leg. 688 + Ley 31408 — todos los trabajadores desde el día 1.
SCTR_SALUD_TASA   = Decimal('0.80')   # % aporte empleador (referencial; ≈ Nivel III combinado 1.53%)
SCTR_PENSION_TASA = Decimal('0.73')   # % aporte empleador (referencial)
VIDA_LEY_TASA     = Decimal('0.71')   # % prima empleador (referencial de mercado)

# Tope de Remuneración Máxima Asegurable (RMA) — Q2 2026.
# La prima de seguro AFP se calcula HASTA este monto. Si el trabajador
# gana más, la prima se trunca al tope (la aseguradora no cubre por
# encima de ese ingreso). El aporte obligatorio (10%) y la comisión por
# flujo SÍ se cobran sobre la remuneración total, sin tope.
# Referencia: SBS publica cuatrimestralmente.
AFP_TOPE_REM_ASEGURABLE = Decimal('12131.49')

UIT_2026      = Decimal('5500.00')   # DS 233-2025-EF (vigente 2026) — fallback
RMV_2026      = Decimal('1130.00')   # DS 006-2024-TR vigente ene-2025 — fallback
ASIG_FAM      = RMV_2026 * Decimal('0.10')   # S/ 113.00


def _get_tasas_afp(afp_nombre: str) -> dict:
    """
    Devuelve tasas AFP (comisión y seguro) para una AFP específica.
    Prioridad: ConfiguracionSistema.afp_tasas_override > AFP_TASAS hardcoded.
    """
    try:
        from asistencia.models import ConfiguracionSistema
        override = ConfiguracionSistema.get().afp_tasas_override
        if override and afp_nombre in override:
            t = override[afp_nombre]
            return {
                'comision_flujo': Decimal(str(t.get('comision_flujo', '0'))),
                'seguro': Decimal(str(t.get('seguro', '0'))),
            }
    except Exception:
        pass
    return AFP_TASAS.get(afp_nombre, AFP_TASAS['Prima'])


def snapshot_parametros_legales() -> dict:
    """
    Captura los parámetros legales vigentes (con overrides de
    ConfiguracionSistema aplicados) para congelarlos en
    PeriodoNomina.parametros_snapshot al generar la planilla.
    Todos los valores como str para serialización JSON estable.
    """
    from django.utils import timezone

    return {
        'capturado_en': timezone.now().isoformat(),
        'rmv': str(_get_rmv()),
        'uit': str(_get_uit()),
        'asignacion_familiar': str(_redondear(_get_rmv() * Decimal('0.10'))),
        'onp_tasa': str(ONP_TASA),
        'essalud_tasa': str(ESSALUD_TASA),
        'afp_aporte': str(AFP_APORTE),
        'afp_tope_rma': str(_get_tope_rma()),
        'aportes_riesgo': {
            k: (str(v) if isinstance(v, Decimal) else v)
            for k, v in _get_aportes_riesgo().items()
        },
        'afp_tasas': {
            nombre: {
                'comision_flujo': str(_get_tasas_afp(nombre)['comision_flujo']),
                'seguro': str(_get_tasas_afp(nombre)['seguro']),
            }
            for nombre in AFP_TASAS
        },
    }


def _get_aportes_riesgo() -> dict:
    """
    Lee los parámetros de SCTR y Vida Ley desde ConfiguracionSistema, con
    fallback a las constantes del engine. Devuelve flags de activación y tasas.
    """
    params = {
        'sctr_activo':       True,
        'sctr_salud_tasa':   SCTR_SALUD_TASA,
        'sctr_pension_tasa': SCTR_PENSION_TASA,
        'vida_ley_activo':   True,
        'vida_ley_tasa':     VIDA_LEY_TASA,
    }
    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.get()
        params['sctr_activo']     = bool(getattr(cfg, 'sctr_activo', True))
        params['vida_ley_activo'] = bool(getattr(cfg, 'vida_ley_activo', True))
        for k, attr in (
            ('sctr_salud_tasa', 'sctr_salud_tasa'),
            ('sctr_pension_tasa', 'sctr_pension_tasa'),
            ('vida_ley_tasa', 'vida_ley_tasa'),
        ):
            v = getattr(cfg, attr, None)
            if v is not None:
                params[k] = Decimal(str(v))
    except Exception:
        pass
    return params


def _get_tope_rma() -> Decimal:
    """Lee el tope RMA AFP. Prioridad: ConfiguracionSistema > constante."""
    try:
        from asistencia.models import ConfiguracionSistema
        tope = ConfiguracionSistema.get().afp_tope_rma
        if tope is not None and tope > 0:
            return tope
    except Exception:
        pass
    return AFP_TOPE_REM_ASEGURABLE


def _get_uit() -> Decimal:
    """Lee la UIT desde ConfiguracionSistema (configurable por admin). Fallback a constante."""
    try:
        from asistencia.models import ConfiguracionSistema
        return ConfiguracionSistema.get().uit_valor
    except Exception:
        return UIT_2026


def _get_rmv() -> Decimal:
    """Lee la RMV desde ConfiguracionSistema (configurable por admin). Fallback a constante."""
    try:
        from asistencia.models import ConfiguracionSistema
        return ConfiguracionSistema.get().rmv_valor
    except Exception:
        return RMV_2026


def _get_usar_metodo_sunat_ir5ta() -> bool:
    """Lee el flag de método SUNAT IR 5ta desde ConfiguracionSistema. Fallback False."""
    try:
        from asistencia.models import ConfiguracionSistema
        return bool(getattr(ConfiguracionSistema.get(), 'usar_metodo_sunat_ir5ta', False))
    except Exception:
        return False


def _rmv_efectivo(periodo=None) -> Decimal:
    """
    Devuelve el RMV a usar para un cálculo.
    - Si hay período con `rmv_snapshot`, usa ese valor (congelado).
    - Sino, lee live de ConfiguracionSistema.
    """
    if periodo is not None:
        snap = getattr(periodo, 'rmv_snapshot', None)
        if snap is not None and Decimal(snap) > 0:
            return Decimal(snap)
    return _get_rmv()


def _uit_efectivo(periodo=None) -> Decimal:
    """
    Devuelve la UIT a usar para un cálculo.
    - Si hay período con `uit_snapshot`, usa ese valor (congelado).
    - Sino, lee live de ConfiguracionSistema.
    """
    if periodo is not None:
        snap = getattr(periodo, 'uit_snapshot', None)
        if snap is not None and Decimal(snap) > 0:
            return Decimal(snap)
    return _get_uit()


# Tope HE auditoría: 4 h/día × 15 días útiles = 60 h/mes (bandera, no bloqueante)
TOPE_HE_MES = Decimal('60')

# Escala IR 5ta Categoría 2026 (en UITs)
# Tramos: (limite_uits, tasa%)
IR_5TA_ESCALA = [
    (Decimal('5'),   Decimal('8')),
    (Decimal('20'),  Decimal('14')),
    (Decimal('35'),  Decimal('17')),
    (Decimal('45'),  Decimal('20')),
    (None,           Decimal('30')),
]
IR_5TA_DEDUCCION_UITS = Decimal('7')   # 7 UIT deducción anual


def _redondear(valor: Decimal) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_UP (estándar planilla)."""
    return Decimal(valor).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calcular_prov_gratif(sueldo: Decimal, asig_fam: Decimal) -> Decimal:
    """
    Provisión de gratificación = (sueldo + asig_fam) / 6.

    Helper centralizado para evitar duplicación entre planilla regular,
    CTS y liquidación. Usa Decimal exacto, redondea al final.
    """
    sueldo = Decimal(sueldo or 0)
    asig_fam = Decimal(asig_fam or 0)
    return _redondear((sueldo + asig_fam) / Decimal('6'))


# ─── Horas Extra (helpers expuestos públicamente) ──────────────────────

def valor_hora(sueldo_mensual: Decimal, divisor_dias: int = 30, jornada_horas: int = 8) -> Decimal:
    """
    Calcula el valor hora ordinario.

    Default: sueldo / 30 días / 8 h. Para jornadas distintas (medio tiempo,
    construcción civil con 48h semanales, etc.) ajustar parámetros.

    Args:
        sueldo_mensual: Remuneración mensual base.
        divisor_dias:   Días del mes para cálculo (default 30 — práctica laboral).
        jornada_horas:  Horas diarias de jornada legal (default 8).
    """
    if sueldo_mensual <= 0 or divisor_dias <= 0 or jornada_horas <= 0:
        return Decimal('0')
    return _redondear(Decimal(sueldo_mensual) / Decimal(divisor_dias) / Decimal(jornada_horas))


def calcular_he(horas: Decimal, sueldo_mensual: Decimal, tipo: str = 'HE_25',
                jornada_horas: int = 8) -> Decimal:
    """
    Calcula el monto a pagar por horas extra.

    Args:
        horas:          Cantidad de horas extra del período.
        sueldo_mensual: Sueldo base mensual.
        tipo:           'HE_25' (primeras 2h sobretiempo), 'HE_35' (3h+ y
                        nocturno), 'HE_100' (descanso/feriado), 'HE_50'
                        (custom convenio mejor).
        jornada_horas:  Horas diarias jornada legal (default 8).

    Returns:
        Monto a pagar redondeado a 2 decimales.

    Base legal:
    - Ley 27671 Art. 10: 25% primeras 2h, 35% siguientes.
    - DS 004-2006-TR: nocturno (22:00-06:00) recargo 35% sobre RMV nocturna.
    - DL 713 Art. 9: feriado/domingo trabajado = doble (100% sobretasa).
    """
    if horas <= 0 or sueldo_mensual <= 0:
        return Decimal('0')

    factores = {
        'HE_25':  Decimal('1.25'),
        'HE_35':  Decimal('1.35'),
        'HE_50':  Decimal('1.50'),  # custom convenio mejor que ley
        'HE_100': Decimal('2.00'),
    }
    factor = factores.get(tipo, Decimal('1.25'))
    vh = valor_hora(sueldo_mensual, jornada_horas=jornada_horas)
    return _redondear(Decimal(horas) * vh * factor)


def valor_he_banco_no_compensadas(personal, sueldo_mensual: Decimal) -> Decimal:
    """Valor en soles de las HE banqueadas (BancoHoras) NO compensadas.

    Las HE de personal STAFF se acumulan en el banco para compensarse con
    descanso; el saldo NO compensado es deuda del empleador que se paga al cese
    (ver BancoHoras.__doc__ y MovimientoBancoHoras tipo LIQUIDACION).

    Valorización: se agregan todos los períodos del trabajador. La compensación
    (`he_compensadas`) es un total sin desglose por tasa → se distribuye de forma
    PROPORCIONAL entre las tasas acumuladas (criterio neutral). Cada hora
    remanente se valora a la hora ordinaria (sueldo/30/8) × sobretasa
    (1.25 / 1.35 / 2.00). Devuelve 0 si no hay banco o el saldo es ≤ 0.
    """
    if not personal or sueldo_mensual is None or Decimal(sueldo_mensual) <= 0:
        return Decimal('0')
    from django.db.models import Sum
    from asistencia.models import BancoHoras

    agg = BancoHoras.objects.filter(personal=personal).aggregate(
        a25=Sum('he_25_acumuladas'), a35=Sum('he_35_acumuladas'),
        a100=Sum('he_100_acumuladas'), comp=Sum('he_compensadas'))
    a25 = Decimal(str(agg['a25'] or 0))
    a35 = Decimal(str(agg['a35'] or 0))
    a100 = Decimal(str(agg['a100'] or 0))
    comp = Decimal(str(agg['comp'] or 0))
    total_acum = a25 + a35 + a100
    saldo = total_acum - comp
    if total_acum <= 0 or saldo <= 0:
        return Decimal('0')
    ratio = saldo / total_acum  # proporción no compensada
    vh = valor_hora(sueldo_mensual)  # sueldo / 30 / 8
    monto = (a25 * ratio * vh * Decimal('1.25')
             + a35 * ratio * vh * Decimal('1.35')
             + a100 * ratio * vh * Decimal('2.00'))
    return _redondear(monto)


# ─── Subsidios ESSALUD ─────────────────────────────────────────────────

def calcular_subsidio_incapacidad(
    sueldo_mensual: Decimal,
    dias_incapacidad: int,
) -> dict:
    """
    Subsidio por incapacidad temporal — Ley 26790 + Reglamento.

    Reglas:
    - Días 1-20: empleador paga remuneración íntegra (afecta normal — REMUNERATIVA).
    - Día 21 hasta máximo 11 meses 10 días: ESSALUD paga subsidio (NO REMUNERATIVO).
    - Subsidio diario = (rem 12 meses anteriores / 360) — promedio diario.
      Simplificación: valor_diario = sueldo_mensual / 30.

    Args:
        sueldo_mensual:   Remuneración promedio del trabajador.
        dias_incapacidad: Cantidad TOTAL de días de incapacidad.

    Returns:
        dict con:
        - dias_empleador, monto_empleador (afecto)
        - dias_essalud, monto_essalud_subsidio (NO afecto, paga ESSALUD)
        - total_dias, total_monto
        - dia_max_essalud (340 días = 11m10d)
    """
    if dias_incapacidad <= 0 or sueldo_mensual <= 0:
        return {
            'dias_empleador': 0, 'monto_empleador': Decimal('0'),
            'dias_essalud': 0,  'monto_essalud_subsidio': Decimal('0'),
            'total_dias': 0,    'total_monto': Decimal('0'),
        }

    valor_diario = Decimal(sueldo_mensual) / Decimal('30')

    dias_empleador = min(int(dias_incapacidad), 20)
    monto_empleador = _redondear(valor_diario * Decimal(dias_empleador))

    dias_essalud_potenciales = max(int(dias_incapacidad) - 20, 0)
    # Tope: 11 meses 10 días = 340 días
    dias_essalud = min(dias_essalud_potenciales, 340)
    monto_essalud = _redondear(valor_diario * Decimal(dias_essalud))

    return {
        'valor_diario':            _redondear(valor_diario),
        'dias_empleador':          dias_empleador,
        'monto_empleador':         monto_empleador,
        'dias_essalud':            dias_essalud,
        'monto_essalud_subsidio':  monto_essalud,
        'total_dias':              dias_empleador + dias_essalud,
        'total_monto':             monto_empleador + monto_essalud,
        'limite_alcanzado':        dias_essalud_potenciales > 340,
    }


def calcular_subsidio_maternidad(sueldo_mensual: Decimal, dias: int = 98) -> dict:
    """
    Subsidio por maternidad — Ley 26790 + Ley 30367.

    98 días de licencia pre y post natal (49+49). Paga ESSALUD.
    Subsidio diario = promedio remuneraciones últimos 12 meses / 360.
    Simplificación: sueldo_mensual / 30.

    NO REMUNERATIVO — no afecto a aportes ni descuentos.
    """
    if sueldo_mensual <= 0 or dias <= 0:
        return {'monto': Decimal('0'), 'dias': 0, 'valor_diario': Decimal('0')}

    valor_diario = Decimal(sueldo_mensual) / Decimal('30')
    monto = _redondear(valor_diario * Decimal(dias))

    return {
        'valor_diario': _redondear(valor_diario),
        'dias':         int(dias),
        'monto':        monto,
    }


# ─── Pensión alimenticia (Art. 648 CPC) ────────────────────────────────

def calcular_pension_alimenticia(
    rem_total: Decimal,
    descuentos_legales: Decimal,
    porcentaje: Decimal,
) -> dict:
    """
    Pensión alimenticia por orden judicial.

    Base de cálculo: remuneración total menos descuentos legales (AFP/ONP, IR).
    Límite: 60% (Art. 648 CPC).

    Args:
        rem_total:          Ingresos totales del trabajador.
        descuentos_legales: AFP/ONP + IR 5ta (descuentos obligatorios).
        porcentaje:         Porcentaje ordenado por juez (ej: 30 = 30%).

    Returns:
        dict con base_calculo, monto, porcentaje_aplicado.
    """
    rem_total = Decimal(rem_total or 0)
    descuentos_legales = Decimal(descuentos_legales or 0)
    porcentaje = min(Decimal(porcentaje or 0), Decimal('60'))  # Tope legal

    base = max(rem_total - descuentos_legales, Decimal('0'))
    monto = _redondear(base * porcentaje / Decimal('100'))

    return {
        'base_calculo':        _redondear(base),
        'porcentaje_aplicado': porcentaje,
        'monto':               monto,
        'tope_legal_60_alcanzado': porcentaje >= Decimal('60'),
    }


# ─── Embargo civil (Art. 648 CPC) ──────────────────────────────────────

def calcular_embargo_civil(
    rem_total: Decimal,
    uit: Decimal = None,
) -> dict:
    """
    Embargo civil sobre remuneración — Art. 648 inc. 6 CPC.

    Reglas:
    - Inembargable hasta 5 URP. La URP (Unidad de Referencia Procesal) equivale
      al 10% de la UIT (fijada por el Poder Judicial). 2026: UIT 5.500 → URP 550
      → 5 URP = 2.750.
    - Sobre el exceso: hasta 1/3 (33.33%) embargable.

    Para deudas alimentarias el tope sube a 60% — usar calcular_pension_alimenticia
    en su lugar.

    Returns: dict con urp, inembargable, exceso, monto_max_embargo, aplica_embargo
    """
    rem_total = Decimal(rem_total or 0)
    uit_efectivo = Decimal(uit) if uit else _get_uit()

    urp = uit_efectivo * Decimal('0.10')      # URP = 10% UIT
    inembargable = urp * Decimal('5')         # 5 URP (Art. 648 inc. 6 CPC)
    exceso = max(rem_total - inembargable, Decimal('0'))
    monto_max = _redondear(exceso / Decimal('3'))

    return {
        'rem_total':         rem_total,
        'urp':               _redondear(urp),
        'inembargable':      _redondear(inembargable),
        'exceso':            _redondear(exceso),
        'monto_max_embargo': monto_max,
        'aplica_embargo':    monto_max > 0,
    }


# ─── Bonificación escolaridad ──────────────────────────────────────────

def calcular_bonif_escolaridad(
    sueldo: Decimal,
    multiplicador: Decimal = Decimal('1'),
) -> Decimal:
    """
    Bonificación escolaridad (convencional — D.Leg. 728 Art. 8).

    Típicamente 1 sueldo (multiplicador=1). En sector público es típicamente
    S/400 fijo, en privado es convenido.

    REMUNERATIVO — afecta gratif, CTS, vacaciones.
    """
    if sueldo <= 0:
        return Decimal('0')
    return _redondear(Decimal(sueldo) * Decimal(multiplicador))


def _ir_anual(base_imponible: Decimal, uit: Decimal) -> Decimal:
    """
    Aplica la escala progresiva de IR 5ta a una base imponible anual.
    Retorna el impuesto anual SIN dividir por meses (Decimal exacto).
    """
    if base_imponible <= 0:
        return Decimal('0')

    impuesto = Decimal('0')
    anterior = Decimal('0')

    for limite_uits, tasa in IR_5TA_ESCALA:
        if limite_uits is None:
            exceso = base_imponible - anterior
        else:
            limite = limite_uits * uit
            if base_imponible <= anterior:
                break
            exceso = min(base_imponible, limite) - anterior
            if exceso <= 0:
                break

        impuesto += exceso * (tasa / Decimal('100'))

        if limite_uits is None:
            break
        anterior = limite_uits * uit
        if base_imponible <= anterior:
            break

    return impuesto


def calcular_ir_5ta_mensual(
    rem_anual_proyectada: Decimal,
    deduccion_eps_anual: Decimal = Decimal('0'),
    uit: Decimal = None,
) -> Decimal:
    """
    Calcula la retención mensual de IR 5ta categoría (método legacy).
    Proyección anual → escala progresiva → dividir por 12.

    Args:
        rem_anual_proyectada: Remuneración anual proyectada (sueldo × 14 + HE).
        deduccion_eps_anual:  Aporte anual del trabajador a EPS (si aplica).
                              Reduce la base imponible antes de las 7 UIT.
        uit:                  UIT a usar (si None, lee de ConfiguracionSistema).
    """
    if uit is None:
        uit = _get_uit()
    # Deducción EPS trabajador + 7 UIT (base legal: Art. 46° TUO LIR)
    base_imponible = max(
        rem_anual_proyectada - deduccion_eps_anual - (IR_5TA_DEDUCCION_UITS * uit),
        Decimal('0'),
    )
    impuesto_anual = _ir_anual(base_imponible, uit)
    if impuesto_anual <= 0:
        return Decimal('0')
    return _redondear(impuesto_anual / Decimal('12'))


# Alias explícito para que el código consumidor pueda elegir el método.
_calcular_ir_5ta_legacy = calcular_ir_5ta_mensual


def _calcular_ir_5ta_sunat(
    sueldo_fijo_mes: Decimal,
    asig_fam: Decimal,
    variables_acumuladas_ano: Decimal,
    mes_actual: int,
    deduccion_eps_anual: Decimal = Decimal('0'),
    uit: Decimal = None,
) -> Decimal:
    """
    Método oficial SUNAT de retención mensual acumulada (IR 5ta).

    Referencia: https://orientacion.sunat.gob.pe/3071-02-calculo-del-impuesto

    Estrategia (resumen del método de proyección con ajuste por variables):
      1. Tomar la remuneración FIJA proyectada en el año:
         (sueldo + asig_fam) × meses_restantes_en_año
         + gratificaciones que falten cobrar (julio y/o diciembre).
      2. SUMAR variables (HE, bonos) YA PERCIBIDAS en lo que va del año
         (no se proyectan a futuro — sólo lo cobrado).
      3. Restar 7 UIT + deducción EPS → base imponible.
      4. Aplicar escala progresiva → impuesto anual proyectado.
      5. Dividir entre los meses RESTANTES (incluyendo el actual) para
         obtener la retención del mes.

    Args:
        sueldo_fijo_mes:           Sueldo base mensual (sin HE/bonos).
        asig_fam:                  Asignación familiar (fija) del mes.
        variables_acumuladas_ano:  HE + bonos percibidos en lo que va del año
                                   (sin incluir el mes actual aún si querés —
                                   convención del caller).
        mes_actual:                Mes 1..12 del cálculo.
        deduccion_eps_anual:       Aporte anual EPS (si aplica).
        uit:                       UIT vigente.

    Notes:
        - Esta implementación es una versión simplificada del método SUNAT
          (que tiene un cuadro por mes con bases distintas). Para producción
          ver R.S. 010-2006/SUNAT y modificatorias.
        - Si `mes_actual` está fuera de 1..12 se ajusta al rango.
    """
    if uit is None:
        uit = _get_uit()

    mes = max(1, min(int(mes_actual or 1), 12))
    sueldo_fijo_mes = Decimal(sueldo_fijo_mes or 0)
    asig_fam = Decimal(asig_fam or 0)
    variables_acumuladas_ano = Decimal(variables_acumuladas_ano or 0)
    deduccion_eps_anual = Decimal(deduccion_eps_anual or 0)

    rem_fija_mes = sueldo_fijo_mes + asig_fam
    meses_restantes = Decimal(12 - mes + 1)  # incluye el mes actual

    # Meses ya transcurridos antes del actual (1..12 → 0..11)
    meses_transcurridos = Decimal(mes - 1)

    # Gratificaciones que faltan cobrar en el año
    # Julio (mes 7) y diciembre (mes 12) → 1 sueldo computable cada una.
    gratif_faltantes = Decimal('0')
    if mes <= 7:
        gratif_faltantes += rem_fija_mes  # gratif de julio
    if mes <= 12:
        gratif_faltantes += rem_fija_mes  # gratif de diciembre

    # Proyección anual:
    # - Fija ya cobrada (meses transcurridos completos, sin contar mes actual)
    # - Fija a cobrar (mes actual + restantes)
    # - Variables ya percibidas (HE/bonos) — no se proyectan
    # - Gratificaciones futuras
    fija_cobrada = rem_fija_mes * meses_transcurridos
    fija_a_cobrar = rem_fija_mes * meses_restantes
    rem_anual_proyectada = (
        fija_cobrada + fija_a_cobrar + variables_acumuladas_ano + gratif_faltantes
    )

    base_imponible = max(
        rem_anual_proyectada - deduccion_eps_anual - (IR_5TA_DEDUCCION_UITS * uit),
        Decimal('0'),
    )
    impuesto_anual = _ir_anual(base_imponible, uit)
    if impuesto_anual <= 0:
        return Decimal('0')

    # Retención del mes = impuesto anual proyectado / meses restantes
    return _redondear(impuesto_anual / meses_restantes)


def calcular_registro(registro, conceptos_activos=None) -> dict:
    """
    Motor principal: calcula la nómina de un RegistroNomina.
    Retorna dict con todas las líneas calculadas.
    Persiste las líneas y actualiza el registro.
    """
    from .models import ConceptoRemunerativo

    if conceptos_activos is None:
        conceptos_activos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')

    p = registro
    sueldo    = _redondear(p.sueldo_base)
    dias      = p.dias_trabajados
    pension   = p.regimen_pension  # AFP / ONP / SIN_PENSION
    afp_nombre= p.afp or 'Prima'

    # Snapshots: si el registro pertenece a un período con snapshot, usar ese valor.
    periodo = getattr(p, 'periodo', None)
    rmv = _rmv_efectivo(periodo)
    uit = _uit_efectivo(periodo)

    # ── 1. Sueldo proporcional a días trabajados (D.Leg. 713 Art. 12) ──
    sueldo_prop = _redondear(sueldo * Decimal(dias) / Decimal('30'))

    # ── 2. Asignación familiar (10% RMV si tiene hijos) ──
    asig_fam = _redondear(rmv * Decimal('0.10')) if p.asignacion_familiar else Decimal('0')

    # ── 3. Valor hora y horas extra ──
    valor_hora   = _redondear(sueldo / Decimal('30') / Decimal('8'))
    monto_he_25  = _redondear(p.horas_extra_25  * valor_hora * Decimal('1.25'))
    monto_he_35  = _redondear(p.horas_extra_35  * valor_hora * Decimal('1.35'))
    monto_he_100 = _redondear(p.horas_extra_100 * valor_hora * Decimal('2.00'))

    # ── 3b. Validación de tope HE (bandera de auditoría, no bloqueante) ──
    #     DL 713: máximo 4h/día — referenciamos 60h/mes como umbral de alerta.
    total_he_horas = (
        Decimal(p.horas_extra_25 or 0)
        + Decimal(p.horas_extra_35 or 0)
        + Decimal(p.horas_extra_100 or 0)
    )
    if total_he_horas > TOPE_HE_MES:
        logger.warning(
            "HE excedidas para %s: %sh > tope mensual %sh (DL 713 4h/día). "
            "Se permite registrar para auditoría.",
            getattr(p, 'personal', '?'), total_he_horas, TOPE_HE_MES,
        )

    # ── 4. Otros ingresos manuales ──
    otros_ing = _redondear(p.otros_ingresos)

    # ── 4b. Conceptos manuales importados (Excel masivo o edición individual) ──
    # Estructura: {"CODIGO": "monto_str", ...} en p.conceptos_manuales
    # Cada par (codigo, monto) genera una LineaNomina propia preservando el detalle.
    conceptos_manuales_data = {}  # codigo -> (concepto_obj, monto, es_ingreso)
    cm_ing_total  = Decimal('0')
    cm_desc_total = Decimal('0')
    raw_cm = getattr(p, 'conceptos_manuales', None) or {}
    if isinstance(raw_cm, dict) and raw_cm:
        for cod, monto_raw in raw_cm.items():
            try:
                monto = _redondear(Decimal(str(monto_raw or '0')))
            except (ValueError, ArithmeticError):
                continue
            if monto == 0:
                continue
            try:
                c_obj = conceptos_activos.get(codigo=cod)
            except ConceptoRemunerativo.DoesNotExist:
                continue
            es_ingreso = c_obj.tipo == 'INGRESO'
            conceptos_manuales_data[cod] = (c_obj, monto, es_ingreso)
            if es_ingreso:
                cm_ing_total += monto
            else:
                cm_desc_total += monto

    # ── 5. Remuneración computable (base para AFP/ONP/IR) ──
    rem_computable = sueldo_prop + asig_fam + monto_he_25 + monto_he_35 + monto_he_100

    # Total ingresos (incluyendo no remunerativos + conceptos manuales)
    total_ingresos_bruto = rem_computable + otros_ing + cm_ing_total

    # ── 6. Descuentos pensionarios ──
    afp_aporte   = Decimal('0')
    afp_comision = Decimal('0')
    afp_seguro   = Decimal('0')
    onp          = Decimal('0')

    if pension == 'AFP':
        # Tasas dinámicas (override por ConfiguracionSistema o hardcoded fallback)
        tasas = _get_tasas_afp(afp_nombre)
        tope_rma = _get_tope_rma()
        # Aporte obligatorio 10% — sin tope, sobre remuneración asegurable total
        afp_aporte   = _redondear(rem_computable * AFP_APORTE / Decimal('100'))
        # Comisión por flujo — sin tope, sobre remuneración total
        afp_comision = _redondear(rem_computable * tasas['comision_flujo'] / Decimal('100'))
        # Prima de seguro — CON tope de Remuneración Máxima Asegurable (RMA)
        # publicado por SBS. Si gana más del tope, la prima se calcula
        # solo sobre el tope (la aseguradora no cubre por encima).
        base_seguro = min(rem_computable, tope_rma)
        afp_seguro   = _redondear(base_seguro * tasas['seguro'] / Decimal('100'))
    elif pension == 'ONP':
        # ONP 13% — sin tope, sobre remuneración total (DL 19990)
        onp = _redondear(rem_computable * ONP_TASA / Decimal('100'))

    # ── 7. IR 5ta categoría ──
    # Dos métodos disponibles:
    #   - SUNAT (default opt-in): proyección con fija + variables percibidas
    #   - Legacy: rem × 14 (sobre-estima con HE variables o cese a mitad de año)
    usar_sunat = _get_usar_metodo_sunat_ir5ta()
    if usar_sunat and periodo is not None:
        # Variables percibidas: HE + otros_ing del mes actual (proxy mínimo;
        # el caller puede pasar lo acumulado-año por otro canal en el futuro).
        variables_mes = monto_he_25 + monto_he_35 + monto_he_100
        mes_actual = getattr(periodo, 'mes', 1) or 1
        ir_5ta = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=sueldo_prop,
            asig_fam=asig_fam,
            variables_acumuladas_ano=variables_mes,
            mes_actual=mes_actual,
            uit=uit,
        )
        rem_anual = rem_computable * Decimal('14')  # info en lineas
    else:
        # Proyección: 12 sueldos + 2 gratificaciones = 14 remuneraciones
        rem_anual = rem_computable * Decimal('14')
        ir_5ta = calcular_ir_5ta_mensual(rem_anual, uit=uit)

    # ── 8. Otros descuentos manuales ──
    descto_prestamo  = _redondear(p.descuento_prestamo)
    otros_descuentos = _redondear(p.otros_descuentos)

    # ── 8b. Descuentos judiciales (embargo/pensión) desde DescuentoPlanilla ──
    # Decisión Edwin: auto-cargar con VALIDACIÓN DE TOPE legal. Pensión ≤ 60% de
    # (rem − descuentos legales); embargo civil ≤ 1/3 del exceso sobre 5 URP
    # (Art. 648 CPC). Si la cuota ordenada excede el tope, se capa y se alerta.
    judicial_total = Decimal('0')
    judicial_lineas = []  # (codigo_concepto, monto, observacion)
    _pers = getattr(p, 'personal', None)
    if _pers is not None and getattr(_pers, 'pk', None):
        try:
            from django.db.models import Q as _Q

            from descuentos.models import DescuentoPlanilla
            _desc_legales = afp_aporte + afp_comision + afp_seguro + onp + ir_5ta
            # APROBADO también cuenta: el flujo de aprobación deja el descuento
            # en APROBADO y nadie lo movía a EN_CURSO, así que un embargo
            # aprobado jamás llegaba a la planilla. Se respeta fecha_inicio si
            # está en el futuro (aún no empieza).
            _fin_periodo = getattr(getattr(p, 'periodo', None), 'fecha_fin', None)
            _qs_jud = DescuentoPlanilla.objects.filter(
                personal=_pers, estado__in=['APROBADO', 'EN_CURSO'],
                causal__in=['EMBARGO_JUDICIAL', 'PENSION_ALIMENTICIA'])
            if _fin_periodo is not None:
                _qs_jud = _qs_jud.filter(
                    _Q(fecha_inicio_descuento__isnull=True)
                    | _Q(fecha_inicio_descuento__lte=_fin_periodo))
            for d in _qs_jud:
                _cuota = _redondear(d.cuota_mensual or 0)
                _saldo = _redondear(getattr(d, 'saldo_pendiente', None) or _cuota)
                if _saldo > 0:
                    _cuota = min(_cuota, _saldo)
                if _cuota <= 0:
                    continue
                if d.causal == 'PENSION_ALIMENTICIA':
                    _tope = calcular_pension_alimenticia(
                        total_ingresos_bruto, _desc_legales, Decimal('60'))['monto']
                    _cod, _obs = 'pension-alimenticia', 'Pensión alimenticia (tope 60%)'
                else:
                    _tope = calcular_embargo_civil(
                        total_ingresos_bruto, uit=uit)['monto_max_embargo']
                    _cod, _obs = 'embargo-judicial', 'Embargo civil (tope 1/3 sobre 5 URP)'
                _monto = min(_cuota, _tope)
                if _monto < _cuota:
                    logger.warning('Descuento judicial %s capado por tope legal: %s → %s (rem %s)',
                                   d.causal, _cuota, _monto, total_ingresos_bruto)
                if _monto > 0:
                    judicial_total += _monto
                    judicial_lineas.append((_cod, _monto, _obs))
        except Exception:
            logger.warning('No se pudieron consolidar descuentos judiciales', exc_info=True)
            judicial_total = Decimal('0')
            judicial_lineas = []

    # ── 8c. Descuentos internos (herramienta/uniforme/multa/etc.) ──
    # Mismo patrón que 8b pero para causales NO judiciales de DescuentoPlanilla.
    # Requisito legal (DS 003-97-TR): consentimiento escrito del trabajador,
    # salvo que el descuento esté marcado como no-requerido. Sin consentimiento
    # firmado el descuento NO entra a planilla. Cap por saldo pendiente; la
    # aplicación se registra al cierre (descuentos.services).
    interno_total = Decimal('0')
    interno_lineas = []  # (monto, observacion)
    if _pers is not None and getattr(_pers, 'pk', None):
        try:
            from django.db.models import Q as _Q

            from descuentos.models import DescuentoPlanilla
            _fin_periodo = getattr(getattr(p, 'periodo', None), 'fecha_fin', None)
            _qs_int = (DescuentoPlanilla.objects
                       .filter(personal=_pers, estado__in=['APROBADO', 'EN_CURSO'])
                       .exclude(causal__in=['EMBARGO_JUDICIAL', 'PENSION_ALIMENTICIA'])
                       .filter(_Q(requiere_consentimiento=False)
                               | _Q(consentimiento_firmado=True)))
            if _fin_periodo is not None:
                _qs_int = _qs_int.filter(
                    _Q(fecha_inicio_descuento__isnull=True)
                    | _Q(fecha_inicio_descuento__lte=_fin_periodo))
            for d in _qs_int:
                _cuota = _redondear(d.cuota_mensual or 0)
                _saldo = _redondear(getattr(d, 'saldo_pendiente', None) or _cuota)
                if _saldo > 0:
                    _cuota = min(_cuota, _saldo)
                if _cuota <= 0:
                    continue
                interno_total += _cuota
                interno_lineas.append((_cuota, d.get_causal_display()))
        except Exception:
            logger.warning('No se pudieron consolidar descuentos internos', exc_info=True)
            interno_total = Decimal('0')
            interno_lineas = []

    # ── 9. Totales ──
    total_desc_trabajador = (afp_aporte + afp_comision + afp_seguro + onp + ir_5ta
                             + descto_prestamo + otros_descuentos + judicial_total
                             + interno_total + cm_desc_total)
    neto                  = _redondear(total_ingresos_bruto - total_desc_trabajador)

    # ── 10. Aportes empleador (costo empresa) ──
    essalud = _redondear(rem_computable * ESSALUD_TASA / Decimal('100'))

    # ── 10b. Aportes/primas de riesgo del empleador ──
    # SCTR (Ley 26790): solo trabajadores en actividad de riesgo (afecto_sctr).
    # Vida Ley (D.Leg. 688): todos los trabajadores. Base: remuneración computable.
    _riesgo = _get_aportes_riesgo()
    _afecto_sctr = bool(getattr(getattr(p, 'personal', None), 'afecto_sctr', False))
    sctr_salud   = Decimal('0')
    sctr_pension = Decimal('0')
    vida_ley     = Decimal('0')
    if _riesgo['sctr_activo'] and _afecto_sctr:
        sctr_salud   = _redondear(rem_computable * _riesgo['sctr_salud_tasa'] / Decimal('100'))
        sctr_pension = _redondear(rem_computable * _riesgo['sctr_pension_tasa'] / Decimal('100'))
    if _riesgo['vida_ley_activo']:
        vida_ley = _redondear(rem_computable * _riesgo['vida_ley_tasa'] / Decimal('100'))

    # ── 11. Provisiones (informativas en planilla regular) ──
    # Gratificación = 1/6 de (sueldo + asig_fam) — HE no computan (Ley 27735)
    base_gratif = sueldo_prop + asig_fam
    prov_gratif = calcular_prov_gratif(sueldo_prop, asig_fam)
    # CTS = 1/12 de (sueldo + asig_fam + 1/6 gratif) — DL 650
    prov_cts    = _redondear((base_gratif + prov_gratif) / Decimal('12'))

    # ── 12. Costo total empresa ──
    costo_empresa = _redondear(
        total_ingresos_bruto + essalud + sctr_salud + sctr_pension + vida_ley
        + prov_gratif + prov_cts)

    # ── Construir lista de líneas ──
    lineas = []

    def _agregar(codigo, base, pct, monto, obs=''):
        try:
            c = conceptos_activos.get(codigo=codigo)
            lineas.append({
                'concepto': c, 'base_calculo': base,
                'porcentaje_aplicado': pct, 'monto': monto,
                'observacion': obs,
            })
        except ConceptoRemunerativo.DoesNotExist:
            pass

    # Ingresos
    _agregar('sueldo-basico',       sueldo,        Decimal('0'), sueldo_prop,
             f'{dias} días trabajados')
    if asig_fam > 0:
        _agregar('asig-familiar',   rmv,           Decimal('10'), asig_fam)
    if monto_he_25 > 0:
        _agregar('he-25',           valor_hora,    Decimal('25'), monto_he_25,
                 f'{p.horas_extra_25}h × S/{valor_hora} × 1.25')
    if monto_he_35 > 0:
        _agregar('he-35',           valor_hora,    Decimal('35'), monto_he_35,
                 f'{p.horas_extra_35}h × S/{valor_hora} × 1.35')
    if monto_he_100 > 0:
        _agregar('he-100',          valor_hora,    Decimal('100'), monto_he_100,
                 f'{p.horas_extra_100}h × S/{valor_hora} × 2.00')
    if otros_ing > 0:
        _agregar('otros-ingresos',  Decimal('0'),  Decimal('0'), otros_ing)

    # Conceptos manuales tipo INGRESO (importados Excel o edición individual)
    for cod, (c_obj, monto, es_ing) in conceptos_manuales_data.items():
        if es_ing:
            lineas.append({
                'concepto': c_obj, 'base_calculo': Decimal('0'),
                'porcentaje_aplicado': Decimal('0'), 'monto': monto,
                'observacion': 'Importado / edición manual',
            })

    # Descuentos trabajador
    if afp_aporte > 0:
        _agregar('afp-aporte',      rem_computable, AFP_APORTE,   afp_aporte,    f'AFP {afp_nombre}')
    if afp_comision > 0:
        tasas2 = AFP_TASAS.get(afp_nombre, AFP_TASAS['Prima'])
        _agregar('afp-comision',    rem_computable, tasas2['comision_flujo'], afp_comision, f'AFP {afp_nombre}')
    if afp_seguro > 0:
        _agregar('afp-seguro',      rem_computable, tasas2['seguro'], afp_seguro, f'AFP {afp_nombre}')
    if onp > 0:
        _agregar('onp',             rem_computable, ONP_TASA,     onp)
    if ir_5ta > 0:
        _agregar('ir-5ta',          rem_anual,      Decimal('0'), ir_5ta,        'Retención mensual')
    if descto_prestamo > 0:
        _agregar('descto-prestamo', Decimal('0'),   Decimal('0'), descto_prestamo)
    if otros_descuentos > 0:
        _agregar('otros-descuentos',Decimal('0'),   Decimal('0'), otros_descuentos)
    # Descuentos judiciales (embargo/pensión) — código PLAME 0703 vía concepto.
    for _cod, _monto, _obs in judicial_lineas:
        _agregar(_cod, Decimal('0'), Decimal('0'), _monto, _obs)
    # Descuentos internos consolidados desde DescuentoPlanilla (causal en obs).
    for _monto, _obs in interno_lineas:
        _agregar('descuento-interno', Decimal('0'), Decimal('0'), _monto, _obs)

    # Conceptos manuales tipo DESCUENTO
    for cod, (c_obj, monto, es_ing) in conceptos_manuales_data.items():
        if not es_ing:
            lineas.append({
                'concepto': c_obj, 'base_calculo': Decimal('0'),
                'porcentaje_aplicado': Decimal('0'), 'monto': monto,
                'observacion': 'Importado / edición manual',
            })

    # Aportes empleador
    _agregar('essalud',             rem_computable, ESSALUD_TASA, essalud)
    if sctr_salud > 0:
        _agregar('sctr-salud',      rem_computable, _riesgo['sctr_salud_tasa'],   sctr_salud,
                 'SCTR Salud (Ley 26790)')
    if sctr_pension > 0:
        _agregar('sctr-pension',    rem_computable, _riesgo['sctr_pension_tasa'], sctr_pension,
                 'SCTR Pensión (invalidez/sepelio)')
    if vida_ley > 0:
        _agregar('vida-ley',        rem_computable, _riesgo['vida_ley_tasa'],     vida_ley,
                 'Seguro Vida Ley (D.Leg. 688)')

    # Provisiones (informativas)
    _agregar('prov-gratificacion',  rem_computable, Decimal('0'), prov_gratif,   '1/6 sueldo mensual')
    _agregar('prov-cts',            rem_computable, Decimal('0'), prov_cts,      '1/12 (sueldo+gratif)')

    # ── Pase genérico fórmula-driven (conceptos marcados "aplicar_automatico") ──
    # Históricamente el engine solo emitía conceptos por lista blanca de códigos,
    # así que cualquier concepto activado por el admin nacía en 0. Este pase emite
    # los conceptos activos con aplicar_automatico=True y fórmula PORCENTAJE/FIJO
    # que no se hayan emitido arriba, calculándolos sobre la remuneración
    # computable (PORCENTAJE) o su monto_fijo (FIJO). Opt-in por concepto para no
    # alterar planillas existentes. SCTR/Vida Ley se manejan explícitamente arriba.
    _emitidos = {l['concepto'].codigo for l in lineas}
    _ing_auto = Decimal('0')
    _desc_auto = Decimal('0')
    _aporte_auto = Decimal('0')
    try:
        for c in conceptos_activos:
            if not getattr(c, 'aplicar_automatico', False):
                continue
            if c.codigo in _emitidos:
                continue
            if c.formula == 'PORCENTAJE' and (c.porcentaje or 0) > 0:
                _monto = _redondear(rem_computable * Decimal(str(c.porcentaje)) / Decimal('100'))
                _pct = Decimal(str(c.porcentaje))
                _base = rem_computable
            elif c.formula == 'FIJO' and (c.monto_fijo or 0) > 0:
                _monto = _redondear(Decimal(str(c.monto_fijo)))
                _pct = Decimal('0')
                _base = Decimal('0')
            else:
                continue
            if _monto <= 0:
                continue
            lineas.append({
                'concepto': c, 'base_calculo': _base,
                'porcentaje_aplicado': _pct, 'monto': _monto,
                'observacion': 'Automático (configuración del concepto)',
            })
            _emitidos.add(c.codigo)
            if c.tipo == 'INGRESO':
                _ing_auto += _monto
            elif c.tipo == 'DESCUENTO':
                _desc_auto += _monto
            elif c.tipo == 'APORTE_EMPLEADOR':
                _aporte_auto += _monto
    except Exception:
        logger.warning('Pase genérico de conceptos automáticos falló', exc_info=True)
        _ing_auto = Decimal('0')
        _desc_auto = Decimal('0')
        _aporte_auto = Decimal('0')

    # Reflejar los conceptos automáticos en los totales (ingresos suben el bruto y
    # el neto; descuentos bajan el neto). Los aportes empleador automáticos no
    # tocan el neto del trabajador pero sí el costo empresa.
    if _ing_auto:
        total_ingresos_bruto += _ing_auto
        neto = _redondear(neto + _ing_auto)
    if _desc_auto:
        total_desc_trabajador += _desc_auto
        neto = _redondear(neto - _desc_auto)
    costo_empresa = _redondear(costo_empresa + _ing_auto + _aporte_auto)

    return {
        'lineas':             lineas,
        'total_ingresos':     total_ingresos_bruto,
        'total_descuentos':   total_desc_trabajador,
        'neto_a_pagar':       neto,
        'aporte_essalud':     essalud,
        'aporte_sctr_salud':  sctr_salud,
        'aporte_sctr_pension': sctr_pension,
        'aporte_vida_ley':    vida_ley,
        'costo_total_empresa': costo_empresa,
        'rem_computable':     rem_computable,
    }


BONIF_EXTRAORDINARIA_TASA     = Decimal('9.00')    # % Ley 29351 — trabajadores en ESSALUD regular
BONIF_EXTRAORDINARIA_TASA_EPS = Decimal('6.75')    # % cuando trabajador tiene EPS (Ley 26790)


def calcular_gratificacion(registro, conceptos_activos=None) -> dict:
    """
    Calcula la gratificación semestral (julio o diciembre).

    Base legal: Ley 27735 + Ley 29351
    - Computable: sueldo_base + asig_familiar  (HE no computan)
    - Proporcional: base × (meses_trabajados / 6)
      → usa registro.dias_trabajados como 'meses trabajados en el semestre' (1-6)
    - Bonificación extraordinaria 9% (empleador → no descuenta al trabajador)
    - AFP/ONP: INAFECTOS (Ley 29351) — trabajador recibe 100%
    - EsSalud 9%: aporte empleador (pero se paga como bonif extraordinaria)
    - IR 5ta: INAFECTA (Art. 18° TUO LIR)

    Para generar un período tipo GRATIFICACION, establece:
        registro.dias_trabajados = meses trabajados en el semestre (1-6)
    """
    from .models import ConceptoRemunerativo

    if conceptos_activos is None:
        conceptos_activos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')

    p = registro
    sueldo     = _redondear(p.sueldo_base)
    # meses trabajados en el semestre (usamos dias_trabajados como proxy).
    # Importante: 0 es un valor válido (trabajador con cero meses) → no debe
    # caer al fallback 6 vía `or`. Solo cuando es None se asume semestre completo.
    dias_trab  = p.dias_trabajados if p.dias_trabajados is not None else 6
    meses      = max(1, min(int(dias_trab), 6))
    pension    = p.regimen_pension
    afp_nombre = p.afp or 'Prima'

    # Snapshot RMV del período si existe
    periodo = getattr(p, 'periodo', None)
    rmv = _rmv_efectivo(periodo)

    # ── 1. Remuneración computable (solo sueldo + asig_fam) ──────────────
    asig_fam   = _redondear(rmv * Decimal('0.10')) if p.asignacion_familiar else Decimal('0')
    rem_base   = sueldo + asig_fam

    # ── 2. Gratificación proporcional ────────────────────────────────────
    gratif     = _redondear(rem_base * Decimal(meses) / Decimal('6'))

    # ── 3. Bonificación extraordinaria (Ley 29351 + Ley 26790) ──────────
    #    Este monto LO PAGA EL EMPLEADOR, no descuenta al trabajador.
    #    Tasa:
    #      - 9.00% si trabajador está en ESSALUD regular (sin EPS)
    #      - 6.75% si trabajador está afiliado a EPS — porque la diferencia (2.25%)
    #        ya está cubierta por el aporte a la EPS particular (Ley 26790 art. 15)
    _personal_obj = getattr(p, 'personal', None)
    tiene_eps = bool(getattr(_personal_obj, 'tiene_eps', False)) if _personal_obj else False
    bonif_tasa = BONIF_EXTRAORDINARIA_TASA_EPS if tiene_eps else BONIF_EXTRAORDINARIA_TASA
    bonif_extra = _redondear(gratif * bonif_tasa / Decimal('100'))

    total_ingreso = gratif  # Lo que recibe el trabajador (gratif neta)

    # ── 4. Descuentos pensionarios ─────────────────────────────────────
    #    Ley 29351: Gratificaciones INAFECTAS a aportes pensionarios
    #    (AFP/ONP). El trabajador recibe el 100% de la gratificación.
    afp_aporte   = Decimal('0')
    afp_comision = Decimal('0')
    afp_seguro   = Decimal('0')
    onp          = Decimal('0')
    total_desc   = Decimal('0')
    neto         = gratif

    # ── 5. Aportes empleador ─────────────────────────────────────────────
    #    Si tiene EPS, ESSALUD efectivo se reduce a 6.75% (los 2.25% se van a EPS).
    essalud_tasa = (Decimal('9.00') - Decimal('2.25')) if tiene_eps else ESSALUD_TASA
    essalud     = _redondear(gratif * essalud_tasa / Decimal('100'))
    costo_total = _redondear(gratif + bonif_extra + essalud)

    # ── Construir líneas ──────────────────────────────────────────────────
    lineas = []

    def _ag(codigo, base, pct, monto, obs=''):
        try:
            c = conceptos_activos.get(codigo=codigo)
            lineas.append({
                'concepto': c, 'base_calculo': base,
                'porcentaje_aplicado': pct, 'monto': monto, 'observacion': obs,
            })
        except ConceptoRemunerativo.DoesNotExist:
            pass

    # Ingreso
    _ag('gratificacion',         rem_base,   Decimal('0'), gratif,
        f'{meses}/6 meses — base S/{rem_base}')
    _ag('bonif-extraordinaria',  gratif,     bonif_tasa, bonif_extra,
        f'Ley 29351 — {"6.75% (EPS)" if tiene_eps else "9% (ESSALUD reg.)"}')

    # Descuentos
    if afp_aporte > 0:
        _ag('afp-aporte',   gratif, AFP_APORTE,                afp_aporte,   f'AFP {afp_nombre}')
    if afp_comision > 0:
        tasas2 = AFP_TASAS.get(afp_nombre, AFP_TASAS['Prima'])
        _ag('afp-comision', gratif, tasas2['comision_flujo'],  afp_comision, f'AFP {afp_nombre}')
    if afp_seguro > 0:
        _ag('afp-seguro',   gratif, tasas2['seguro'],          afp_seguro,   f'AFP {afp_nombre}')
    if onp > 0:
        _ag('onp',          gratif, ONP_TASA,                  onp)

    # Aportes empleador
    _ag('essalud',              gratif, ESSALUD_TASA,           essalud)

    return {
        'lineas':              lineas,
        'total_ingresos':      total_ingreso,
        'total_descuentos':    total_desc,
        'neto_a_pagar':        neto,
        'aporte_essalud':      essalud,
        'costo_total_empresa': costo_total,
        'rem_computable':      rem_base,
        # Extras para la UI
        'gratif_bruto':        gratif,
        'bonif_extra':         bonif_extra,
        'meses_trabajados':    meses,
    }


def calcular_cts(registro, conceptos_activos=None) -> dict:
    """
    Calcula CTS semestral (mayo o noviembre).

    Base legal: DL 650 Art. 21, Art. 9 + Ley 30334
    - Base CTS = sueldo_base + asig_familiar + (1/6 sueldo = prov. gratif)
    - CTS = base / 12 × meses_trabajados_semestre
    - NO aplican descuentos AFP/ONP ni IR 5ta (CTS es inafecta a pensiones y renta)
    - Empleador deposita directamente en cuenta CTS del banco del trabajador

    Para generar un período tipo CTS, establece:
        registro.dias_trabajados = meses trabajados en el semestre (1-6)
    """
    from .models import ConceptoRemunerativo

    if conceptos_activos is None:
        conceptos_activos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')

    p          = registro
    sueldo     = _redondear(p.sueldo_base)
    # 0 es un valor válido — no caer al fallback 6 vía `or`. Solo None se asume completo.
    dias_trab  = p.dias_trabajados if p.dias_trabajados is not None else 6
    meses      = max(1, min(int(dias_trab), 6))

    # Snapshot RMV del período si existe
    periodo = getattr(p, 'periodo', None)
    rmv = _rmv_efectivo(periodo)

    asig_fam   = _redondear(rmv * Decimal('0.10')) if p.asignacion_familiar else Decimal('0')

    # ── Base computable CTS ───────────────────────────────────────────────
    # Incluye: sueldo + asig_fam + 1/6 (sueldo + asig_fam) (gratificación proporcional)
    # IMPORTANTE: trabajamos con Decimal exacto y redondeamos SOLO al final
    # del cálculo de cts_semestral para evitar pérdida por redondeo en cascada.
    prov_gratif_exacto   = (sueldo + asig_fam) / Decimal('6')   # NO redondear aún
    base_cts_exacta      = sueldo + asig_fam + prov_gratif_exacto

    # ── CTS proporcional al semestre ─────────────────────────────────────
    cts_semestral = _redondear(base_cts_exacta / Decimal('12') * Decimal(meses))

    # Versiones redondeadas para mostrar en UI/lineas (informativas)
    prov_gratif = _redondear(prov_gratif_exacto)
    base_cts    = _redondear(base_cts_exacta)

    # ── Sin descuentos al trabajador (CTS inafecta) ──────────────────────
    # El depósito va íntegro al banco designado
    neto           = cts_semestral
    total_ingresos = cts_semestral
    total_desc     = Decimal('0')

    # Costo empresa = CTS (lo paga el empleador completamente)
    costo_total    = cts_semestral

    # ── Construir líneas ──────────────────────────────────────────────────
    lineas = []

    def _ag(codigo, base, pct, monto, obs=''):
        try:
            c = conceptos_activos.get(codigo=codigo)
            lineas.append({
                'concepto': c, 'base_calculo': base,
                'porcentaje_aplicado': pct, 'monto': monto, 'observacion': obs,
            })
        except ConceptoRemunerativo.DoesNotExist:
            pass

    _ag('cts-semestral',  base_cts, Decimal('0'), cts_semestral,
        f'{meses}/6 meses — base S/{base_cts} (sueldo + asig.fam + 1/6 gratif)')

    return {
        'lineas':              lineas,
        'total_ingresos':      total_ingresos,
        'total_descuentos':    total_desc,
        'neto_a_pagar':        neto,
        'aporte_essalud':      Decimal('0'),
        'costo_total_empresa': costo_total,
        'rem_computable':      base_cts,
        # Extras para la UI
        'cts_semestral':       cts_semestral,
        'base_cts':            base_cts,
        'prov_gratif_mes':     prov_gratif,
        'meses_trabajados':    meses,
    }


@transaction.atomic
def generar_periodo(periodo, usuario=None, grupo=None) -> dict:
    """
    Genera todos los RegistroNomina + LineaNomina de un período.
    Idempotente: si ya existen registros, los recalcula.

    Args:
        periodo: PeriodoNomina instance
        usuario: usuario que ejecuta (para auditoría)
        grupo: 'STAFF' | 'RCO' | None (todos)
    Returns:
        dict con stats del proceso
    """
    from personal.models import Personal
    from .models import RegistroNomina, LineaNomina, ConceptoRemunerativo

    conceptos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')

    # ── Snapshot de RMV/UIT al inicio del cálculo ──────────────────────
    # Si el período aún no tiene snapshot (recién creado), lo congelamos
    # ahora con el valor live de ConfiguracionSistema. Recalculos futuros
    # del MISMO período reutilizan este snapshot, garantizando consistencia
    # frente a cambios posteriores de la configuración.
    if not getattr(periodo, 'rmv_snapshot', None) or Decimal(periodo.rmv_snapshot or 0) <= 0:
        periodo.rmv_snapshot = _get_rmv()
    if not getattr(periodo, 'uit_snapshot', None) or Decimal(periodo.uit_snapshot or 0) <= 0:
        periodo.uit_snapshot = _get_uit()
    if not getattr(periodo, 'parametros_snapshot', None):
        periodo.parametros_snapshot = snapshot_parametros_legales()

    qs = Personal.objects.filter(estado='Activo')
    if grupo:
        qs = qs.filter(grupo_tareo=grupo)

    stats = {'generados': 0, 'actualizados': 0, 'errores': 0, 'total_neto': Decimal('0')}

    # Seleccionar calculador según tipo de período
    tipo = periodo.tipo
    if tipo == 'GRATIFICACION':
        _calcular = calcular_gratificacion
        dias_default = 6   # Asume semestre completo
    elif tipo == 'CTS':
        _calcular = calcular_cts
        dias_default = 6   # Asume semestre completo
    else:
        from nominas.estrategias import calcular_por_regimen
        _calcular = calcular_por_regimen   # enruta por régimen (general/construcción/minería)
        dias_default = 30  # Mes completo

    # Mapa codigo→concepto para persistir líneas de estrategias que devuelven
    # 'codigo' (construcción/minería) en lugar del objeto 'concepto'.
    _cmap = {c.codigo: c for c in ConceptoRemunerativo.objects.all()}

    # ── Consolidación de ASISTENCIA → NÓMINA (solo planilla REGULAR) ──────
    # Ciclo de tareo 22→21 (MES_CORTE, el mismo que el banco de horas). Por cada
    # trabajador se traen del RegistroTareo del ciclo:
    #   • HE 25/35/100 PAGABLES (he_al_banco=False) → las de STAFF van al banco,
    #     no se pagan en la planilla mensual, por eso se excluyen.
    #   • días NO laborados = FA/LSG/SAI (CODIGOS_DESCUENTO) → dias_trabajados = 30 − no_lab.
    # Trabajadores SIN tareo en el ciclo quedan en el default (30 días, HE 0) → sin cambio.
    tareo_map = {}
    if tipo not in ('GRATIFICACION', 'CTS'):
        try:
            from django.db.models import Sum, Count, Q
            from asistencia.models import RegistroTareo
            from asistencia.services.periodo_helper import get_periodo, TIPO_MES_CORTE
            ciclo = get_periodo(TIPO_MES_CORTE, periodo.anio, periodo.mes)
            _agg = (RegistroTareo.objects
                    .filter(fecha__gte=ciclo.fecha_inicio, fecha__lte=ciclo.fecha_fin,
                            personal__isnull=False)
                    .values('personal_id')
                    .annotate(
                        he25=Sum('he_25', filter=Q(he_al_banco=False)),
                        he35=Sum('he_35', filter=Q(he_al_banco=False)),
                        he100=Sum('he_100', filter=Q(he_al_banco=False)),
                        no_lab=Count('id', filter=Q(codigo_dia__in=['FA', 'LSG', 'SAI'])),
                    ))
            tareo_map = {r['personal_id']: r for r in _agg}
        except Exception:
            logger.warning('No se pudo consolidar asistencia→nómina del período %s',
                           getattr(periodo, 'pk', '?'), exc_info=True)
            tareo_map = {}

    # ── PRÉSTAMOS → planilla (auto-descuento desde el cronograma, decisión Edwin) ──
    # Suma la(s) cuota(s) del MES (cuota.periodo del mes/año del período) de los
    # préstamos EN_CURSO, estado PENDIENTE/VENCIDA. Cada mes descuenta su propia
    # cuota → idempotente y sin doble cobro entre meses. Reemplaza la digitación
    # manual de descuento_prestamo (la fuente de verdad es el cronograma).
    prestamo_map = {}
    if tipo not in ('GRATIFICACION', 'CTS'):
        try:
            from django.db.models import Sum
            from prestamos.models import CuotaPrestamo
            _cuotas = (CuotaPrestamo.objects
                       .filter(prestamo__estado='EN_CURSO',
                               estado__in=['PENDIENTE', 'VENCIDA'],
                               periodo__year=periodo.anio, periodo__month=periodo.mes,
                               prestamo__personal__isnull=False)
                       .values('prestamo__personal_id')
                       .annotate(total=Sum('monto')))
            prestamo_map = {c['prestamo__personal_id']: (c['total'] or Decimal('0'))
                            for c in _cuotas}
        except Exception:
            logger.warning('No se pudieron consolidar las cuotas de préstamo del período %s',
                           getattr(periodo, 'pk', '?'), exc_info=True)
            prestamo_map = {}

    # Performance audit fix: envolver en transaction.atomic para batch atomico
    # y usar bulk_create para LineaNomina. Para 800 trabajadores x ~18 lineas
    # cada uno, esto reduce de ~14400 INSERTs individuales a 800 bulk_creates,
    # bajando tiempo de minutos a segundos.
    from django.db import transaction as _txn
    with _txn.atomic():
        # cargo_obj es la FK (cargo es CharField legacy retenido por backcompat)
        for emp in qs.select_related('cargo_obj', 'subarea', 'empresa'):
            try:
                _defaults = {
                    'sueldo_base':      emp.sueldo_base or Decimal('0'),
                    'regimen_pension':  emp.regimen_pension or 'AFP',
                    'afp':              emp.afp or '',
                    'grupo':            emp.grupo_tareo or '',
                    'asignacion_familiar': getattr(emp, 'asignacion_familiar', False),
                    'dias_trabajados':  dias_default,
                }
                # Poblar días/HE desde la asistencia consolidada (planilla REGULAR).
                _t = tareo_map.get(emp.pk)
                if _t is not None:
                    _no_lab = int(_t['no_lab'] or 0)
                    _defaults['dias_falta']      = _no_lab
                    _defaults['dias_trabajados'] = max(0, dias_default - _no_lab)
                    _defaults['horas_extra_25']  = _t['he25'] or Decimal('0')
                    _defaults['horas_extra_35']  = _t['he35'] or Decimal('0')
                    _defaults['horas_extra_100'] = _t['he100'] or Decimal('0')
                elif tipo not in ('GRATIFICACION', 'CTS'):
                    # Sin marcación real (foráneos 14x7): usar el Roster (proyección)
                    # como fuente de días. Guardado: solo aplica si el trabajador
                    # TIENE roster en el período; si no, queda el default (30 días).
                    try:
                        from nominas.services.asistencia_link import resumen_asistencia_roster
                        _rs = resumen_asistencia_roster(
                            emp, periodo.fecha_inicio, periodo.fecha_fin)
                        _con = (_rs['trabajados'] + _rs['descanso'] + _rs['falta']
                                + _rs['vacaciones'] + _rs['licencia'])
                        if _con > 0:
                            _defaults['dias_falta']      = _rs['falta']
                            _defaults['dias_trabajados'] = max(0, dias_default - _rs['falta'])
                    except Exception:
                        logger.warning('No se pudo poblar días desde el Roster (emp %s)',
                                       getattr(emp, 'pk', '?'), exc_info=True)
                # Cuota de préstamo del mes (auto desde el cronograma).
                if tipo not in ('GRATIFICACION', 'CTS'):
                    _defaults['descuento_prestamo'] = prestamo_map.get(emp.pk, Decimal('0')) or Decimal('0')
                registro, created = RegistroNomina.objects.update_or_create(
                    periodo=periodo, personal=emp, defaults=_defaults,
                )
                # Recalcular con el calculador apropiado
                resultado = _calcular(registro, conceptos)

                # Limpiar líneas previas y bulk_create las nuevas
                registro.lineas.all().delete()
                LineaNomina.objects.bulk_create([
                    LineaNomina(
                        registro=registro,
                        concepto=l.get('concepto') or _cmap.get(l.get('codigo')),
                        base_calculo=l['base_calculo'],
                        porcentaje_aplicado=l['porcentaje_aplicado'],
                        monto=l['monto'],
                        observacion=l['observacion'],
                    )
                    for l in resultado['lineas']
                    if l.get('concepto') or _cmap.get(l.get('codigo'))
                ])

                # Actualizar totales
                registro.total_ingresos      = resultado['total_ingresos']
                registro.total_descuentos    = resultado['total_descuentos']
                registro.neto_a_pagar        = resultado['neto_a_pagar']
                registro.aporte_essalud      = resultado['aporte_essalud']
                registro.aporte_sctr_salud   = resultado.get('aporte_sctr_salud', Decimal('0'))
                registro.aporte_sctr_pension = resultado.get('aporte_sctr_pension', Decimal('0'))
                registro.aporte_vida_ley     = resultado.get('aporte_vida_ley', Decimal('0'))
                registro.costo_total_empresa = resultado['costo_total_empresa']
                registro.estado = 'CALCULADO'
                registro.save()

                stats['total_neto'] += resultado['neto_a_pagar']
                if created:
                    stats['generados'] += 1
                else:
                    stats['actualizados'] += 1

            except Exception as e:
                stats['errores'] += 1
                stats.setdefault('detalle_errores', []).append(f'{emp}: {e}')

    # Actualizar totales del período
    from django.db.models import Sum
    agg = periodo.registros.aggregate(
        t_bruto=Sum('total_ingresos'),
        t_desc=Sum('total_descuentos'),
        t_neto=Sum('neto_a_pagar'),
        t_costo=Sum('costo_total_empresa'),
    )
    periodo.total_trabajadores  = periodo.registros.count()
    periodo.total_bruto         = agg['t_bruto'] or Decimal('0')
    periodo.total_descuentos    = agg['t_desc'] or Decimal('0')
    periodo.total_neto          = agg['t_neto'] or Decimal('0')
    periodo.total_costo_empresa = agg['t_costo'] or Decimal('0')
    periodo.estado              = 'CALCULADO'
    periodo.generado_por        = usuario
    periodo.generado_en         = timezone.now()
    periodo.save()

    return stats
