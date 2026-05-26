"""Helpers compartidos para tests de la app nominas.

Razón de existir: varios tests venían generando DNIs y RUCs únicos vía
`int(time()*1000) % N` — patrón que colisiona cuando dos llamadas ocurren
en el mismo milisegundo y dispara `UNIQUE constraint failed` de forma
intermitente en la suite completa (no aislada). Detectado 2026-05-26 como
causa raíz de tests "flaky" en `test_bonif_extraordinaria_eps`,
`test_engine_extra`, `test_agente_ia*`, `test_aislamiento_empresa`.

Estos counters son determinísticos y a nivel proceso, así que garantizan
unicidad estricta a través de toda la corrida de pytest, sin depender
del reloj.

Nota: los counters parten de bases altas para no chocar con DNIs/RUCs
hardcoded en otros tests (ej. `20111111111`, `20222222222`).
"""
from __future__ import annotations

import itertools

# DNI: 8 dígitos, base 80_000_001 (evita choque con DNIs hardcoded "40000001" etc.)
_dni_counter = itertools.count(80_000_001)

# RUC: 11 dígitos. Empresas peruanas tipo "20..." (jurídicas). Base alta para
# no chocar con RUCs de fixtures o tests legacy.
_ruc_counter = itertools.count(20_900_000_001)


def unique_dni() -> str:
    """DNI único determinístico, 8 dígitos."""
    return f'{next(_dni_counter):08d}'


def unique_ruc() -> str:
    """RUC único determinístico, 11 dígitos, formato persona jurídica (20...)."""
    return f'{next(_ruc_counter):011d}'
