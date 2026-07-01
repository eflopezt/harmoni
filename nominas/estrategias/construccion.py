"""Estrategia del Régimen de Construcción Civil (CAPECO-FTCCP).

Reglas propias: jornal por categoría (Operario/Oficial/Peón), BUC, BAE, bono por
altura, dominical, CTS 15%, gratificación de 40 jornales, asignación escolar,
compensación vacacional 10% y CONAFOVICER 2%. Pago semanal.

Implementación completa en F3. Hasta entonces hereda del régimen general para no
alterar el cálculo de trabajadores mal etiquetados.
"""
from __future__ import annotations

from .regimen_general import EstrategiaRegimenGeneral


class EstrategiaConstructor(EstrategiaRegimenGeneral):
    codigo = 'CONSTRUCCION'
    # F3 sobreescribe calcular() con las reglas de construcción civil.
