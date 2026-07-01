"""
Estrategia de cálculo de planilla por régimen laboral.

Cada régimen (general, construcción civil, minería) implementa `calcular()`.
El motor histórico (`nominas.engine.calcular_registro`) es la implementación del
régimen general; las estrategias de construcción y minería construyen sobre él
o lo sustituyen según las reglas propias del régimen.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EstrategiaCalculo(ABC):
    """Contrato de una estrategia de cálculo de un RegistroNomina."""

    codigo: str = 'BASE'

    @abstractmethod
    def calcular(self, registro, conceptos_activos=None) -> dict:
        """Calcula la boleta de `registro` y devuelve el dict de resultado.

        El dict tiene la misma forma que retorna `nominas.engine.calcular_registro`
        (líneas, totales de ingresos/descuentos/aportes, neto, costo empresa).
        """
        raise NotImplementedError
