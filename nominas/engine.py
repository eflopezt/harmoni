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

    # ── 5. Remuneración computable (base para AFP/ONP/IR) ──
    rem_computable = sueldo_prop + asig_fam + monto_he_25 + monto_he_35 + monto_he_100

    # Total ingresos (incluyendo no remunerativos)
    total_ingresos_bruto = rem_computable + otros_ing

    # ── 6. Descuentos pensionarios ──
    afp_aporte   = Decimal('0')
    afp_comision = Decimal('0')
    afp_seguro   = Decimal('0')
    onp          = Decimal('0')

    if pension == 'AFP':
        tasas = AFP_TASAS.get(afp_nombre, AFP_TASAS['Prima'])
        # Aporte obligatorio 10% — sin tope, sobre remuneración asegurable total
        afp_aporte   = _redondear(rem_computable * AFP_APORTE / Decimal('100'))
        # Comisión por flujo — sin tope, sobre remuneración total
        afp_comision = _redondear(rem_computable * tasas['comision_flujo'] / Decimal('100'))
        # Prima de seguro — CON tope de Remuneración Máxima Asegurable (RMA)
        # publicado por SBS. Si gana más del tope, la prima se calcula
        # solo sobre el tope (la aseguradora no cubre por encima).
        base_seguro = min(rem_computable, AFP_TOPE_REM_ASEGURABLE)
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

    # ── 9. Totales ──
    total_desc_trabajador = afp_aporte + afp_comision + afp_seguro + onp + ir_5ta + descto_prestamo + otros_descuentos
    neto                  = _redondear(total_ingresos_bruto - total_desc_trabajador)

    # ── 10. Aportes empleador (costo empresa) ──
    essalud = _redondear(rem_computable * ESSALUD_TASA / Decimal('100'))

    # ── 11. Provisiones (informativas en planilla regular) ──
    # Gratificación = 1/6 de (sueldo + asig_fam) — HE no computan (Ley 27735)
    base_gratif = sueldo_prop + asig_fam
    prov_gratif = calcular_prov_gratif(sueldo_prop, asig_fam)
    # CTS = 1/12 de (sueldo + asig_fam + 1/6 gratif) — DL 650
    prov_cts    = _redondear((base_gratif + prov_gratif) / Decimal('12'))

    # ── 12. Costo total empresa ──
    costo_empresa = _redondear(total_ingresos_bruto + essalud + prov_gratif + prov_cts)

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

    # Aportes empleador
    _agregar('essalud',             rem_computable, ESSALUD_TASA, essalud)

    # Provisiones (informativas)
    _agregar('prov-gratificacion',  rem_computable, Decimal('0'), prov_gratif,   '1/6 sueldo mensual')
    _agregar('prov-cts',            rem_computable, Decimal('0'), prov_cts,      '1/12 (sueldo+gratif)')

    return {
        'lineas':             lineas,
        'total_ingresos':     total_ingresos_bruto,
        'total_descuentos':   total_desc_trabajador,
        'neto_a_pagar':       neto,
        'aporte_essalud':     essalud,
        'costo_total_empresa': costo_empresa,
        'rem_computable':     rem_computable,
    }


BONIF_EXTRAORDINARIA_TASA = Decimal('9')   # % Ley 29351 — vigente


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
    # meses trabajados en el semestre (usamos dias_trabajados como proxy)
    meses      = max(1, min(int(p.dias_trabajados or 6), 6))
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

    # ── 3. Bonificación extraordinaria 9% (Ley 29351) ───────────────────
    #    Este monto LO PAGA EL EMPLEADOR, no descuenta al trabajador.
    bonif_extra = _redondear(gratif * BONIF_EXTRAORDINARIA_TASA / Decimal('100'))

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
    essalud     = _redondear(gratif * ESSALUD_TASA / Decimal('100'))
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
    _ag('bonif-extraordinaria',  gratif,     BONIF_EXTRAORDINARIA_TASA, bonif_extra,
        'Ley 29351 — aporte empleador')

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
    meses      = max(1, min(int(p.dias_trabajados or 6), 6))

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
        _calcular = calcular_registro
        dias_default = 30  # Mes completo

    # Performance audit fix: envolver en transaction.atomic para batch atomico
    # y usar bulk_create para LineaNomina. Para 800 trabajadores x ~18 lineas
    # cada uno, esto reduce de ~14400 INSERTs individuales a 800 bulk_creates,
    # bajando tiempo de minutos a segundos.
    from django.db import transaction as _txn
    with _txn.atomic():
        # cargo_obj es la FK (cargo es CharField legacy retenido por backcompat)
        for emp in qs.select_related('cargo_obj', 'subarea', 'empresa'):
            try:
                registro, created = RegistroNomina.objects.update_or_create(
                    periodo=periodo, personal=emp,
                    defaults={
                        'sueldo_base':      emp.sueldo_base or Decimal('0'),
                        'regimen_pension':  emp.regimen_pension or 'AFP',
                        'afp':              emp.afp or '',
                        'grupo':            emp.grupo_tareo or '',
                        'asignacion_familiar': getattr(emp, 'asignacion_familiar', False),
                        'dias_trabajados':  dias_default,
                    },
                )
                # Recalcular con el calculador apropiado
                resultado = _calcular(registro, conceptos)

                # Limpiar líneas previas y bulk_create las nuevas
                registro.lineas.all().delete()
                LineaNomina.objects.bulk_create([
                    LineaNomina(
                        registro=registro,
                        concepto=l['concepto'],
                        base_calculo=l['base_calculo'],
                        porcentaje_aplicado=l['porcentaje_aplicado'],
                        monto=l['monto'],
                        observacion=l['observacion'],
                    )
                    for l in resultado['lineas']
                ])

                # Actualizar totales
                registro.total_ingresos      = resultado['total_ingresos']
                registro.total_descuentos    = resultado['total_descuentos']
                registro.neto_a_pagar        = resultado['neto_a_pagar']
                registro.aporte_essalud      = resultado['aporte_essalud']
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
