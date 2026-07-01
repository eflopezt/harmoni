"""
Tests del cruce Tareo↔Roster y topes de jornada (asistencia/services/cruce_roster.py).
Lógica pura (sin DB).
"""
from decimal import Decimal

from asistencia.services.cruce_roster import (
    categoria_roster, categoria_tareo, clasificar_variacion,
    promedio_jornada, excede_tope,
)


# ── Categorías ─────────────────────────────────────────────────────

def test_categoria_roster():
    assert categoria_roster('T') == 'trabajo'
    assert categoria_roster('TR') == 'trabajo'
    assert categoria_roster('D') == 'descanso'
    assert categoria_roster('DL') == 'descanso'
    assert categoria_roster('F') == 'falta'
    assert categoria_roster('V') == 'vacaciones'


def test_categoria_tareo():
    assert categoria_tareo('A') == 'trabajo'
    assert categoria_tareo('NOR') == 'trabajo'
    assert categoria_tareo('DL') == 'descanso'
    assert categoria_tareo('FL') == 'falta'
    assert categoria_tareo('VAC') == 'vacaciones'


# ── Clasificación de variación ─────────────────────────────────────

def test_variacion_coincide():
    assert clasificar_variacion('trabajo', 'trabajo') == 'COINCIDE'
    assert clasificar_variacion('descanso', 'descanso') == 'COINCIDE'


def test_variacion_trabajo_sin_roster():
    # roster decía descanso, pero trabajó
    assert clasificar_variacion('trabajo', 'descanso') == 'TRABAJO_SIN_ROSTER'


def test_variacion_ausente_proyectado():
    # roster decía trabajo, pero faltó
    assert clasificar_variacion('falta', 'trabajo') == 'AUSENTE_PROYECTADO'


def test_variacion_no_en_roster():
    # marcó asistencia pero no había roster
    assert clasificar_variacion('trabajo', None) == 'NO_EN_ROSTER'


def test_variacion_licencia_no_proyectada():
    assert clasificar_variacion('licencia', 'trabajo') == 'LICENCIA_NO_PROYECTADA'


# ── Topes de jornada acumulativa ───────────────────────────────────

def test_promedio_jornada_14x7():
    # 14 días × 12h = 168h ÷ 21 días de ciclo = 8.00 h/día
    assert promedio_jornada(Decimal('168'), 21) == Decimal('8.00')


def test_no_excede_tope_14x7_a_12h():
    # 14x7 a 12h/día promedia exactamente 8h → NO excede
    assert excede_tope(Decimal('168'), 21) is False


def test_excede_tope_si_promedio_mayor_a_8():
    # 14 días × 13h = 182h ÷ 21 = 8.67 h/día → excede
    assert excede_tope(Decimal('182'), 21) is True


def test_promedio_cero_dias():
    assert promedio_jornada(Decimal('100'), 0) == Decimal('0')
