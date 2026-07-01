"""
Tests de normalización de régimen laboral (nominas/regimenes.py).

No tocan la DB salvo el caso que construye un Personal en memoria.
"""
import pytest

from nominas.regimenes import (
    regimen_de_calculo,
    CALC_GENERAL,
    CALC_CONSTRUCCION,
    CALC_MINERIA,
)


@pytest.mark.parametrize('valor,esperado', [
    ('GENERAL', CALC_GENERAL),
    ('', CALC_GENERAL),
    (None, CALC_GENERAL),
    ('MICROEMPRESA', CALC_GENERAL),
    ('AGRARIO', CALC_GENERAL),
    ('D.Leg. 728 — Régimen General', CALC_GENERAL),
    ('CONSTRUCCION', CALC_CONSTRUCCION),
    ('CONSTRUCCION_CIVIL', CALC_CONSTRUCCION),
    ('Construcción Civil', CALC_CONSTRUCCION),
    ('construccion civil (capeco)', CALC_CONSTRUCCION),
    ('MINERIA', CALC_MINERIA),
    ('Minería', CALC_MINERIA),
    ('minera subterranea', CALC_MINERIA),
])
def test_regimen_de_calculo_desde_string(valor, esperado):
    assert regimen_de_calculo(valor) == esperado


class _FakePersonal:
    def __init__(self, regimen):
        self.regimen_laboral = regimen


class _FakeRegistro:
    def __init__(self, personal):
        self.personal = personal


def test_regimen_de_calculo_desde_personal():
    assert regimen_de_calculo(_FakePersonal('CONSTRUCCION')) == CALC_CONSTRUCCION
    assert regimen_de_calculo(_FakePersonal('MINERIA')) == CALC_MINERIA
    assert regimen_de_calculo(_FakePersonal('GENERAL')) == CALC_GENERAL


def test_regimen_de_calculo_desde_registro():
    reg = _FakeRegistro(_FakePersonal('Construcción Civil'))
    assert regimen_de_calculo(reg) == CALC_CONSTRUCCION


def test_registro_sin_personal_es_general():
    assert regimen_de_calculo(_FakeRegistro(None)) == CALC_GENERAL
