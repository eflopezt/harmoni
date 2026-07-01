"""Estrategia del Régimen Minero (D.S. 030-89-TR + convenios colectivos).

Reglas propias: piso de Ingreso Mínimo Minero (RMV +25%), SCTR de nivel de riesgo
minero, y conceptos de convenio configurables (bono por altitud, socavón/
profundidad, alimentación, hospedaje). Jornada acumulativa resuelta por el Roster.

Implementación completa en F4. Hasta entonces hereda del régimen general.
"""
from __future__ import annotations

from .base import EstrategiaCalculo


class EstrategiaMinero(EstrategiaCalculo):
    codigo = 'MINERIA'

    def calcular(self, registro, conceptos_activos=None) -> dict:
        from nominas.mineria import calcular_boleta_minera
        return calcular_boleta_minera(registro, conceptos_activos)
