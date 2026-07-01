"""
Selector de estrategia de cálculo de planilla por régimen laboral.

Uso:
    from nominas.estrategias import calcular_por_regimen
    resultado = calcular_por_regimen(registro)   # elige la estrategia por régimen

El motor histórico sigue siendo la fuente de verdad del régimen general; este
paquete solo enruta hacia la estrategia correcta según Personal.regimen_laboral.
"""
from __future__ import annotations

from nominas.regimenes import (
    regimen_de_calculo, CALC_GENERAL, CALC_CONSTRUCCION, CALC_MINERIA,
)
from .base import EstrategiaCalculo
from .regimen_general import EstrategiaRegimenGeneral
from .construccion import EstrategiaConstructor
from .mineria import EstrategiaMinero

_ESTRATEGIAS = {
    CALC_GENERAL:      EstrategiaRegimenGeneral,
    CALC_CONSTRUCCION: EstrategiaConstructor,
    CALC_MINERIA:      EstrategiaMinero,
}


def get_estrategia(registro) -> EstrategiaCalculo:
    """Devuelve la instancia de estrategia para el régimen de `registro`."""
    cls = _ESTRATEGIAS.get(regimen_de_calculo(registro), EstrategiaRegimenGeneral)
    return cls()


def calcular_por_regimen(registro, conceptos_activos=None) -> dict:
    """Calcula la boleta de `registro` usando la estrategia de su régimen."""
    return get_estrategia(registro).calcular(registro, conceptos_activos)


__all__ = [
    'EstrategiaCalculo', 'EstrategiaRegimenGeneral',
    'EstrategiaConstructor', 'EstrategiaMinero',
    'get_estrategia', 'calcular_por_regimen',
]
