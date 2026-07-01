"""Estrategia del Régimen de Construcción Civil (CAPECO-FTCCP).

Reglas propias: jornal por categoría (Operario/Oficial/Peón), BUC, BAE, bono por
altura, dominical, CTS 15%, gratificación de 40 jornales, asignación escolar,
compensación vacacional 10% y CONAFOVICER 2%. Pago semanal.

Implementación completa en F3. Hasta entonces hereda del régimen general para no
alterar el cálculo de trabajadores mal etiquetados.
"""
from __future__ import annotations

from .base import EstrategiaCalculo


class EstrategiaConstructor(EstrategiaCalculo):
    codigo = 'CONSTRUCCION'

    def calcular(self, registro, conceptos_activos=None) -> dict:
        from nominas.construccion import calcular_boleta_construccion
        return calcular_boleta_construccion(registro)
