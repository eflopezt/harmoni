"""
Cálculo del Régimen Minero (D.S. 030-89-TR + Ley 29741 + convenios colectivos).

A diferencia de construcción civil (esquema rígido con tabla de jornales), la
minería es el **régimen general** con estos añadidos propios del sector:

  1. **Ingreso Mínimo Minero (IMM)** — D.S. 030-89-TR: piso remunerativo no
     menor a RMV + 25% (RMV × 1.25). Si la remuneración computable del
     trabajador es menor, se nivela.
  2. **FCJMMS** — Ley 29741 / D.S. 006-2012-TR: Fondo Complementario de
     Jubilación Minera. El **trabajador** aporta **0.5% mensual de su
     remuneración bruta** (descuento en boleta). El empleador aporta 0.5% de
     la renta neta anual (a nivel empresa, NO va en la boleta mensual).
  3. **SCTR** obligatorio — actividad de alto riesgo (Anexo 5 D.S. 009-97-SA).
  4. **Bonos de convenio colectivo** (altitud, socavón/subsuelo, profundidad,
     alimentación, vivienda/hospedaje): variables por empresa; se modelan como
     conceptos configurables. Las bonificaciones por condición de riesgo son
     remunerativas (afectas); alimentación/vivienda como condición de trabajo
     (D.S. 014-92-EM, zonas alejadas) suelen ser NO remunerativas.
  5. **Jornada atípica/acumulativa** (14x7): el promedio de horas del ciclo no
     puede exceder 8h/día ni 48h/semana. Los días y horas los provee el Roster.

Helpers PUROS (Decimals) para los conceptos que SÍ son fórmula fija. Los bonos
de convenio llegan como monto por trabajador (conceptos_manuales).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# ── Constantes del régimen ─────────────────────────────────────────
IMM_FACTOR = Decimal('1.25')          # Ingreso Mínimo Minero = RMV × 1.25
FCJMMS_TRABAJADOR_PCT = Decimal('0.5')  # aporte del trabajador al FCJMMS (%)


def _r(val) -> Decimal:
    return Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def ingreso_minimo_minero(rmv: Decimal) -> Decimal:
    """Piso de Ingreso Mínimo Minero = RMV × 1.25 (D.S. 030-89-TR).

    Ej. RMV S/ 1,130 → IMM S/ 1,412.50.
    """
    return _r(Decimal(rmv) * IMM_FACTOR)


def nivelacion_imm(remuneracion_computable: Decimal, rmv: Decimal) -> Decimal:
    """Monto de nivelación para alcanzar el Ingreso Mínimo Minero.

    Si la remuneración computable ya iguala o supera el IMM, devuelve 0.
    """
    imm = ingreso_minimo_minero(rmv)
    faltante = imm - Decimal(remuneracion_computable)
    return _r(faltante) if faltante > 0 else Decimal('0.00')


def fcjmms_trabajador(remuneracion_bruta: Decimal) -> Decimal:
    """Aporte del trabajador al FCJMMS = 0.5% de la remuneración bruta mensual.

    (Ley 29741). Es un DESCUENTO del trabajador. El aporte del empleador (0.5%
    de la renta anual) es a nivel empresa y NO se calcula en la boleta mensual.
    """
    return _r(Decimal(remuneracion_bruta) * FCJMMS_TRABAJADOR_PCT / Decimal('100'))


# ── Conceptos mineros (para seed / afectaciones) ───────────────────
# Bonos de convenio por condición de riesgo → remunerativos (afectos).
# Alimentación / vivienda como condición de trabajo → no remunerativos.
CODIGOS_MINEROS_COMPUTABLES = {
    'min-imm-nivelacion', 'min-bono-altitud', 'min-bono-socavon',
    'min-bono-profundidad', 'min-bono-riesgo',
}
CODIGOS_MINEROS_NO_COMPUTABLES = {
    'min-alimentacion', 'min-hospedaje', 'min-movilidad',
}


# ── Ensamblado de la boleta minera ─────────────────────────────────

def calcular_boleta_minera(registro, conceptos_activos=None) -> dict:
    """Boleta minera = régimen general + FCJMMS (0.5% descuento) + info IMM.

    Delega el grueso del cálculo al motor general (que ya maneja sueldo, HHEE,
    AFP/ONP, IR 5ta, EsSalud, SCTR, gratif/CTS) y añade los conceptos propios
    del régimen minero:
      - FCJMMS: descuento 0.5% de la remuneración bruta (Ley 29741).
      - Ingreso Mínimo Minero: se expone como alerta (imm_faltante); si el
        básico es menor al IMM, el admin debe nivelarlo (no se auto-inyecta
        para no distorsionar aportes sin recálculo completo).

    Los bonos de convenio (altitud, socavón, alimentación, hospedaje) se cargan
    como conceptos por trabajador y ya los procesa el motor general.
    """
    from nominas.engine import calcular_registro

    result = calcular_registro(registro, conceptos_activos)
    total_ingresos = result.get('total_ingresos', Decimal('0'))

    # FCJMMS — descuento del trabajador (0.5% de la bruta)
    fcjmms = fcjmms_trabajador(total_ingresos)
    linea = {
        'base_calculo':        _r(total_ingresos),
        'porcentaje_aplicado': FCJMMS_TRABAJADOR_PCT,
        'monto':               fcjmms,
        'observacion':         'Aporte trabajador FCJMMS (Ley 29741)',
        'codigo':              'min-fcjmms',
    }
    try:
        from nominas.models import ConceptoRemunerativo
        c = ConceptoRemunerativo.objects.filter(codigo='min-fcjmms').first()
        if c:
            linea['concepto'] = c
    except Exception:
        pass
    result.setdefault('lineas', []).append(linea)
    result['total_descuentos'] = _r(result.get('total_descuentos', Decimal('0')) + fcjmms)
    result['neto_a_pagar'] = _r(result.get('neto_a_pagar', Decimal('0')) - fcjmms)
    result['descuento_fcjmms'] = fcjmms

    # Ingreso Mínimo Minero (informativo)
    periodo = getattr(registro, 'periodo', None)
    rmv = getattr(periodo, 'rmv_snapshot', None) or Decimal('1130')
    result['ingreso_minimo_minero'] = ingreso_minimo_minero(rmv)
    result['imm_faltante'] = nivelacion_imm(
        result.get('rem_computable', total_ingresos), rmv,
    )
    return result
