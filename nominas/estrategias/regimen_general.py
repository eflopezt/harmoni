"""Estrategia del Régimen General (D.Leg. 728).

Delega en el motor histórico `nominas.engine.calcular_registro`, que ya está
probado con 50+ tests. No reimplementa nada: preserva el comportamiento exacto.
"""
from __future__ import annotations

from .base import EstrategiaCalculo


class EstrategiaRegimenGeneral(EstrategiaCalculo):
    codigo = 'GENERAL'

    def calcular(self, registro, conceptos_activos=None) -> dict:
        from nominas.engine import calcular_registro
        return calcular_registro(registro, conceptos_activos)
