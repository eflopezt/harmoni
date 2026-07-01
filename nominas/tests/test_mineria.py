"""
Tests del régimen minero (nominas/mineria.py + estrategia).
"""
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nominas import mineria as m


@pytest.mark.django_db
def test_seed_mineria_afectaciones():
    from django.core.management import call_command
    from nominas.models import ConceptoRemunerativo
    call_command('seed_mineria', verbosity=0)
    call_command('seed_mineria', verbosity=0)  # idempotente
    assert ConceptoRemunerativo.objects.filter(codigo__startswith='min-').count() == 9

    # FCJMMS es descuento, no afecto a nada
    fc = ConceptoRemunerativo.objects.get(codigo='min-fcjmms')
    assert fc.tipo == 'DESCUENTO'
    assert not (fc.afecto_essalud or fc.afecto_afp or fc.afecto_onp)

    # Bono socavón: remunerativo (afecto); alimentación: no remunerativa
    assert ConceptoRemunerativo.objects.get(codigo='min-bono-socavon').afecto_essalud
    assert not ConceptoRemunerativo.objects.get(codigo='min-alimentacion').afecto_essalud


# ── Helpers puros ──────────────────────────────────────────────────

def test_ingreso_minimo_minero():
    # RMV 1130 → IMM 1412.50
    assert m.ingreso_minimo_minero(Decimal('1130')) == Decimal('1412.50')


def test_fcjmms_trabajador_0_5pct():
    assert m.fcjmms_trabajador(Decimal('3000')) == Decimal('15.00')


def test_nivelacion_imm_por_debajo():
    # computable 1000 < IMM 1412.50 → faltante 412.50
    assert m.nivelacion_imm(Decimal('1000'), Decimal('1130')) == Decimal('412.50')


def test_nivelacion_imm_por_encima_es_cero():
    assert m.nivelacion_imm(Decimal('3000'), Decimal('1130')) == Decimal('0.00')


# ── Ensamblado (motor general mockeado) ────────────────────────────

_RESULT_GENERAL = {
    'lineas': [],
    'total_ingresos':   Decimal('3000.00'),
    'total_descuentos': Decimal('500.00'),
    'neto_a_pagar':     Decimal('2500.00'),
    'rem_computable':   Decimal('3000.00'),
}


def _registro(rmv='1130'):
    return SimpleNamespace(periodo=SimpleNamespace(rmv_snapshot=Decimal(rmv)))


def test_boleta_minera_agrega_fcjmms():
    with patch('nominas.engine.calcular_registro', return_value=dict(_RESULT_GENERAL,
               lineas=[], total_descuentos=Decimal('500.00'), neto_a_pagar=Decimal('2500.00'))):
        r = m.calcular_boleta_minera(_registro())
    # FCJMMS = 0.5% × 3000 = 15
    assert r['descuento_fcjmms'] == Decimal('15.00')
    assert r['total_descuentos'] == Decimal('515.00')
    assert r['neto_a_pagar'] == Decimal('2485.00')
    assert any(l.get('codigo') == 'min-fcjmms' for l in r['lineas'])


def test_boleta_minera_expone_imm():
    with patch('nominas.engine.calcular_registro', return_value=dict(_RESULT_GENERAL)):
        r = m.calcular_boleta_minera(_registro())
    assert r['ingreso_minimo_minero'] == Decimal('1412.50')
    assert r['imm_faltante'] == Decimal('0.00')   # 3000 > IMM


def test_boleta_minera_alerta_imm_si_basico_bajo():
    bajo = dict(_RESULT_GENERAL, rem_computable=Decimal('1000.00'))
    with patch('nominas.engine.calcular_registro', return_value=bajo):
        r = m.calcular_boleta_minera(_registro())
    assert r['imm_faltante'] == Decimal('412.50')


def test_estrategia_minero_dispatch():
    from nominas.estrategias import calcular_por_regimen
    reg = SimpleNamespace(
        personal=SimpleNamespace(regimen_laboral='MINERIA'),
        periodo=SimpleNamespace(rmv_snapshot=Decimal('1130')),
    )
    with patch('nominas.engine.calcular_registro', return_value=dict(_RESULT_GENERAL)):
        out = calcular_por_regimen(reg)
    assert 'descuento_fcjmms' in out
    assert out['descuento_fcjmms'] == Decimal('15.00')
