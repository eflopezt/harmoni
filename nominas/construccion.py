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


def conafovicer(base: Decimal) -> Decimal:
    """CONAFOVICER = 2% (descuento) sobre básico + dominical."""
    return _r(Decimal(base) * CONAFOVICER_PCT / Decimal('100'))
