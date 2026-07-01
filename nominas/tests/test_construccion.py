"""
Tests del régimen de construcción civil:
- helpers puros de cálculo (nominas/construccion.py)
- lookup de jornal vigente y seed CAPECO 2026
"""
from datetime import date
from decimal import Decimal

import pytest

from nominas import construccion as cc


# ── Helpers puros (sin DB) ─────────────────────────────────────────

def test_jornal_basico():
    assert cc.jornal_basico(Decimal('87.30'), 26) == Decimal('2269.80')


def test_dominical():
    assert cc.dominical(Decimal('87.30'), Decimal('4')) == Decimal('349.20')


def test_buc_operario_32pct():
    assert cc.buc(Decimal('2269.80'), Decimal('32')) == Decimal('726.34')


def test_bono_altura_8pct():
    assert cc.bono_altura(Decimal('2269.80'), Decimal('8')) == Decimal('181.58')


def test_cts_15pct():
    assert cc.cts(Decimal('2269.80')) == Decimal('340.47')


def test_gratificacion_anio_completo():
    # 40 jornales
    assert cc.gratificacion(Decimal('87.30'), Decimal('5')) == Decimal('3492.00')


def test_gratificacion_proporcional():
    # 2 meses → 40 * 2/5 = 16 jornales
    assert cc.gratificacion(Decimal('87.30'), Decimal('2')) == Decimal('1396.80')


def test_asignacion_escolar_dos_hijos():
    assert cc.asignacion_escolar(Decimal('87.30'), 2) == Decimal('5238.00')


def test_compensacion_vacacional():
    assert cc.compensacion_vacacional(Decimal('87.30'), 26) == Decimal('226.98')


def test_conafovicer_2pct():
    assert cc.conafovicer(Decimal('2619.00')) == Decimal('52.38')


# ── Lookup + seed (con DB) ─────────────────────────────────────────

@pytest.mark.django_db
def test_seed_y_jornal_vigente():
    from django.core.management import call_command
    call_command('seed_construccion', verbosity=0)

    op = cc.jornal_vigente('OPERARIO', date(2026, 7, 15))
    assert op is not None
    assert op.jornal_diario == Decimal('87.30')
    assert op.buc_pct == Decimal('32.00')
    assert op.bono_altura_pct == Decimal('8.00')

    peon = cc.jornal_vigente('PEON', date(2026, 12, 1))
    assert peon.jornal_diario == Decimal('61.65')

    # Antes de la vigencia no hay jornal
    assert cc.jornal_vigente('OPERARIO', date(2026, 1, 1)) is None


@pytest.mark.django_db
def test_seed_idempotente():
    from django.core.management import call_command
    from nominas.models import JornalConstruccion, ConceptoRemunerativo

    call_command('seed_construccion', verbosity=0)
    call_command('seed_construccion', verbosity=0)

    assert JornalConstruccion.objects.filter(vigencia_desde=date(2026, 6, 1)).count() == 3
    assert ConceptoRemunerativo.objects.filter(codigo__startswith='cc-').count() == 16


@pytest.mark.django_db
def test_afectaciones_conceptos():
    """Las afectaciones sembradas coinciden con la matriz real."""
    from django.core.management import call_command
    from nominas.models import ConceptoRemunerativo
    call_command('seed_construccion', verbosity=0)

    def _c(cod):
        return ConceptoRemunerativo.objects.get(codigo=cod)

    # Jornal: computable y afecto a CTS y gratificación
    j = _c('cc-jornal-basico')
    assert j.afecto_essalud and j.afecto_afp and j.afecto_onp
    assert j.afecto_cts and j.afecto_gratif

    # BUC: computable pero NO afecto a CTS ni gratificación
    b = _c('cc-buc')
    assert b.afecto_essalud and b.afecto_afp
    assert not b.afecto_cts and not b.afecto_gratif

    # Movilidad: NO remunerativa (fuera de todo)
    m = _c('cc-movilidad')
    assert not m.afecto_essalud and not m.afecto_afp and not m.afecto_onp
    assert m.subtipo == 'NO_REMUNERATIVO'

    # Gratificación: inafecta a ESSALUD/AFP/ONP, afecta a IR 5ta
    g = _c('cc-gratif-julio')
    assert not g.afecto_essalud and not g.afecto_afp and not g.afecto_onp
    assert g.afecto_renta

    # CTS: beneficio social, inafecto a todo
    c = _c('cc-cts')
    assert not (c.afecto_essalud or c.afecto_afp or c.afecto_onp or c.afecto_renta)
