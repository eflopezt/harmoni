"""
Escenarios de demo: resolución de slug + landing (solo en host demo).
"""
import pytest

from core.views_demo_autologin import _resolver_escenario, DEMO_ESCENARIOS


def test_escenarios_definidos():
    # Los 4 escenarios que pidió Edwin
    for k in ('gastronomia', 'mineria', 'construccion', 'agencia'):
        assert k in DEMO_ESCENARIOS
    # gastronomía es multiempresa (consolidado); minera/construcción son única
    assert DEMO_ESCENARIOS['gastronomia'].get('modo') == 'consolidado'
    assert DEMO_ESCENARIOS['mineria'].get('ruc')
    assert DEMO_ESCENARIOS['construccion'].get('ruc')
    assert 'modo' not in DEMO_ESCENARIOS['mineria']


def test_alias_compatibilidad():
    # enlaces viejos siguen resolviendo
    assert _resolver_escenario('enterprise')[0] == 'gastronomia'
    assert _resolver_escenario('starter')[0] == 'agencia'
    assert _resolver_escenario('edo')[0] == 'gastronomia'
    assert _resolver_escenario('mina')[0] == 'mineria'
    # directos
    assert _resolver_escenario('mineria')[1]['label'] == 'Minera'
    # desconocido
    assert _resolver_escenario('noexiste')[1] is None


def test_landing_solo_en_host_demo(client):
    # host no-demo → 404
    r = client.get('/d/', HTTP_HOST='harmoni.pe')
    assert r.status_code == 404
    # host demo → 200 con las tarjetas
    r = client.get('/d/', HTTP_HOST='demo.harmoni.pe')
    assert r.status_code == 200
    assert b'Grupo Gastron' in r.content
    assert b'Minera' in r.content
