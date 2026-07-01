"""
Tests del selector de estrategia por régimen (nominas/estrategias/).
"""
from types import SimpleNamespace
from unittest.mock import patch

from nominas.estrategias import (
    get_estrategia, calcular_por_regimen,
    EstrategiaRegimenGeneral, EstrategiaConstructor, EstrategiaMinero,
)


def _registro(regimen):
    return SimpleNamespace(personal=SimpleNamespace(regimen_laboral=regimen))


def test_get_estrategia_general():
    assert isinstance(get_estrategia(_registro('GENERAL')), EstrategiaRegimenGeneral)


def test_get_estrategia_construccion():
    est = get_estrategia(_registro('CONSTRUCCION'))
    assert isinstance(est, EstrategiaConstructor)
    assert est.codigo == 'CONSTRUCCION'


def test_get_estrategia_mineria():
    est = get_estrategia(_registro('Minería'))
    assert isinstance(est, EstrategiaMinero)
    assert est.codigo == 'MINERIA'


def test_regimen_desconocido_cae_a_general():
    assert isinstance(get_estrategia(_registro('CUALQUIER_COSA')), EstrategiaRegimenGeneral)


def test_calcular_por_regimen_delega_al_motor():
    reg = _registro('GENERAL')
    with patch('nominas.engine.calcular_registro', return_value={'neto_a_pagar': 123}) as m:
        out = calcular_por_regimen(reg)
    m.assert_called_once_with(reg, None)
    assert out == {'neto_a_pagar': 123}


def test_construccion_hoy_delega_al_general():
    """F2: construcción aún no tiene reglas propias; hereda del general."""
    reg = _registro('CONSTRUCCION')
    with patch('nominas.engine.calcular_registro', return_value={'ok': True}) as m:
        calcular_por_regimen(reg)
    m.assert_called_once()
