"""
Régimen laboral → estrategia de cálculo de planilla.

`Personal.regimen_laboral` admitió históricamente texto libre ("GENERAL",
"CONSTRUCCION", "D.Leg. 728 — Régimen General", "Minería", etc.). Este módulo
normaliza cualquier valor a uno de los regímenes de cálculo que el motor
conoce. Solo CONSTRUCCION y MINERIA tienen estrategia propia; el resto
(general, MYPE, agrario, vacío o texto libre) se calcula con el régimen general.

Uso:
    from nominas.regimenes import regimen_de_calculo, CALC_CONSTRUCCION
    if regimen_de_calculo(registro) == CALC_CONSTRUCCION: ...
"""
from __future__ import annotations

import unicodedata

CALC_GENERAL = 'GENERAL'
CALC_CONSTRUCCION = 'CONSTRUCCION'
CALC_MINERIA = 'MINERIA'

REGIMENES_CALCULO = (CALC_GENERAL, CALC_CONSTRUCCION, CALC_MINERIA)


def _norm(texto) -> str:
    """Mayúsculas, sin tildes, sin espacios extremos."""
    t = unicodedata.normalize('NFKD', str(texto or ''))
    t = t.encode('ascii', 'ignore').decode('ascii')
    return t.upper().strip()


def regimen_de_calculo(valor) -> str:
    """Devuelve CALC_GENERAL | CALC_CONSTRUCCION | CALC_MINERIA.

    Acepta:
      - un string con el código/etiqueta del régimen,
      - un objeto Personal (usa `.regimen_laboral`),
      - un RegistroNomina u objeto con `.personal` (usa `.personal.regimen_laboral`).
    """
    texto = valor
    if hasattr(valor, 'regimen_laboral'):
        texto = valor.regimen_laboral
    elif getattr(valor, 'personal', None) is not None:
        texto = getattr(valor.personal, 'regimen_laboral', '')

    t = _norm(texto)
    if 'CONSTRUC' in t:
        return CALC_CONSTRUCCION
    if 'MINER' in t:      # MINERIA, MINERA, MINERO
        return CALC_MINERIA
    return CALC_GENERAL
