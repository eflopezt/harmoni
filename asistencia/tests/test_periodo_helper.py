"""
Tests para asistencia.services.periodo_helper.
"""
from datetime import date

import pytest

from asistencia.services.periodo_helper import (
    Periodo,
    TIPO_MES,
    TIPO_MES_CORTE,
    TIPO_SEMANA,
    get_periodo,
)


# ────────────────────────────────────────────────────────────────────
# MES (calendario completo)
# ────────────────────────────────────────────────────────────────────

def test_mes_mayo_2026():
    p = get_periodo('MES', 2026, 5)
    assert p.tipo == TIPO_MES
    assert p.fecha_inicio == date(2026, 5, 1)
    assert p.fecha_fin == date(2026, 5, 31)
    assert p.label == 'Mayo 2026'
    assert p.dias == 31


def test_mes_febrero_no_bisiesto():
    p = get_periodo('MES', 2026, 2)
    assert p.fecha_inicio == date(2026, 2, 1)
    assert p.fecha_fin == date(2026, 2, 28)
    assert p.dias == 28


def test_mes_febrero_bisiesto():
    p = get_periodo('MES', 2024, 2)
    assert p.fecha_fin == date(2024, 2, 29)
    assert p.dias == 29


def test_mes_requiere_mes_param():
    with pytest.raises(ValueError):
        get_periodo('MES', 2026)


def test_mes_invalido():
    with pytest.raises(ValueError):
        get_periodo('MES', 2026, 13)


# ────────────────────────────────────────────────────────────────────
# MES_CORTE (ciclo 22→21)
# ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db
def test_mes_corte_mayo_2026():
    """Mayo 2026 → 22-Abr-2026 al 21-May-2026."""
    p = get_periodo('MES_CORTE', 2026, 5)
    assert p.tipo == TIPO_MES_CORTE
    # Sin ConfiguracionSistema configurada, fallback es 22→21.
    assert p.fecha_inicio == date(2026, 4, 22)
    assert p.fecha_fin == date(2026, 5, 21)
    assert '22-Abr' in p.label and '21-May' in p.label and '2026' in p.label


@pytest.mark.django_db
def test_mes_corte_enero_cruza_anio():
    """Enero 2026 → 22-Dic-2025 al 21-Ene-2026."""
    p = get_periodo('MES_CORTE', 2026, 1)
    assert p.fecha_inicio == date(2025, 12, 22)
    assert p.fecha_fin == date(2026, 1, 21)


# ────────────────────────────────────────────────────────────────────
# SEMANA (lunes-domingo)
# ────────────────────────────────────────────────────────────────────

def test_semana_es_lunes_a_domingo():
    p = get_periodo('SEMANA', 2026, 5, 0)
    assert p.tipo == TIPO_SEMANA
    assert p.fecha_inicio.weekday() == 0  # lunes
    assert p.fecha_fin.weekday() == 6     # domingo
    assert p.dias == 7


def test_semana_offset_retrocede_7_dias():
    p0 = get_periodo('SEMANA', 2026, 5, 0)
    p_prev = get_periodo('SEMANA', 2026, 5, -1)
    assert (p0.fecha_inicio - p_prev.fecha_inicio).days == 7


def test_semana_offset_avanza_7_dias():
    p0 = get_periodo('SEMANA', 2026, 5, 0)
    p_next = get_periodo('SEMANA', 2026, 5, 1)
    assert (p_next.fecha_inicio - p0.fecha_inicio).days == 7


# ────────────────────────────────────────────────────────────────────
# Validaciones
# ────────────────────────────────────────────────────────────────────

def test_tipo_invalido():
    with pytest.raises(ValueError):
        get_periodo('TRIMESTRE', 2026, 5)


def test_unpacking_funciona():
    p = get_periodo('MES', 2026, 5)
    ini, fin = p
    assert ini == date(2026, 5, 1)
    assert fin == date(2026, 5, 31)


def test_dataclass_es_frozen():
    """Periodo es inmutable para evitar mutación accidental."""
    p = get_periodo('MES', 2026, 5)
    with pytest.raises(Exception):
        p.fecha_inicio = date(2026, 1, 1)  # type: ignore[misc]
