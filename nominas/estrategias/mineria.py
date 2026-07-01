"""Estrategia del Régimen Minero (D.S. 030-89-TR + convenios colectivos).

Reglas propias: piso de Ingreso Mínimo Minero (RMV +25%), SCTR de nivel de riesgo
minero, y conceptos de convenio configurables (bono por altitud, socavón/
profundidad, alimentación, hospedaje). Jornada acumulativa resuelta por el Roster.

Implementación completa en F4. Hasta entonces hereda del régimen general.
"""
from __future__ import annotations

from .regimen_general import EstrategiaRegimenGeneral


class EstrategiaMinero(EstrategiaRegimenGeneral):
    codigo = 'MINERIA'
    # F4 sobreescribe calcular() con el piso minero y los bonos de convenio.
