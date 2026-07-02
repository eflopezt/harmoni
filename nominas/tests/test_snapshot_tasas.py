"""
P12: el snapshot legal congelado (PeriodoNomina.parametros_snapshot) es la
fuente de verdad durante el cálculo. Antes solo RMV/UIT lo respetaban;
AFP/ONP/EsSalud/SCTR/tope RMA/método IR leían live de ConfiguracionSistema,
así que recalcular un período viejo tras editar tasas cambiaba montos.
"""
from decimal import Decimal
from types import SimpleNamespace

import pytest

from nominas.engine import (
    _aportes_riesgo_efectivos,
    _param_snap_decimal,
    _tasas_afp_efectivas,
    _usar_sunat_efectivo,
    snapshot_parametros_legales,
    AFP_TASAS,
    ONP_TASA,
)


@pytest.fixture(autouse=True)
def _limpiar_cache_config():
    """ConfiguracionSistema.get() cachea en Django cache: el rollback de la
    transacción del test NO limpia el cache, así que hay que vaciarlo para
    no contaminar otros tests del proceso."""
    from django.core.cache import cache
    cache.delete('harmoni_config_v1')
    yield
    cache.delete('harmoni_config_v1')


def _periodo_con_snapshot(**extra):
    snap = {
        'onp_tasa': '12.50',
        'essalud_tasa': '8.00',
        'afp_aporte': '9.50',
        'afp_tope_rma': '13000.00',
        'usar_metodo_sunat_ir5ta': True,
        'afp_tasas': {
            'Prima': {'comision_flujo': '1.99', 'seguro': '1.50'},
        },
        'aportes_riesgo': {
            'sctr_activo': True,
            'sctr_salud_tasa': '1.10',
            'sctr_pension_tasa': '0.90',
            'vida_ley_activo': False,
            'vida_ley_tasa': '0.71',
        },
    }
    snap.update(extra)
    return SimpleNamespace(parametros_snapshot=snap)


# ── Lectura snapshot-first (sin DB) ─────────────────────────────────


def test_param_decimal_lee_snapshot():
    periodo = _periodo_con_snapshot()
    assert _param_snap_decimal(periodo, 'onp_tasa', lambda: ONP_TASA) == Decimal('12.50')
    assert _param_snap_decimal(periodo, 'essalud_tasa', lambda: Decimal('9')) == Decimal('8.00')
    assert _param_snap_decimal(periodo, 'afp_aporte', lambda: Decimal('10')) == Decimal('9.50')


def test_param_decimal_fallback_sin_snapshot():
    periodo = SimpleNamespace(parametros_snapshot=None)
    assert _param_snap_decimal(periodo, 'onp_tasa', lambda: Decimal('13')) == Decimal('13')
    assert _param_snap_decimal(None, 'onp_tasa', lambda: Decimal('13')) == Decimal('13')


def test_tasas_afp_desde_snapshot():
    periodo = _periodo_con_snapshot()
    t = _tasas_afp_efectivas('Prima', periodo)
    assert t['comision_flujo'] == Decimal('1.99')
    assert t['seguro'] == Decimal('1.50')


@pytest.mark.django_db
def test_tasas_afp_fallback_para_afp_no_congelada():
    """AFP que no está en el snapshot cae al camino live/hardcoded."""
    periodo = _periodo_con_snapshot()
    t = _tasas_afp_efectivas('Habitat', periodo)
    assert t['comision_flujo'] == AFP_TASAS['Habitat']['comision_flujo']


def test_aportes_riesgo_desde_snapshot():
    periodo = _periodo_con_snapshot()
    r = _aportes_riesgo_efectivos(periodo)
    assert r['sctr_salud_tasa'] == Decimal('1.10')
    assert r['sctr_pension_tasa'] == Decimal('0.90')
    assert r['vida_ley_activo'] is False


def test_metodo_ir_congelado_en_snapshot():
    periodo = _periodo_con_snapshot()
    assert _usar_sunat_efectivo(periodo) is True
    periodo_legacy = _periodo_con_snapshot(usar_metodo_sunat_ir5ta=False)
    assert _usar_sunat_efectivo(periodo_legacy) is False


# ── El snapshot nuevo congela el método IR ──────────────────────────


@pytest.mark.django_db
def test_snapshot_incluye_metodo_ir():
    snap = snapshot_parametros_legales()
    assert 'usar_metodo_sunat_ir5ta' in snap
    assert isinstance(snap['usar_metodo_sunat_ir5ta'], bool)


# ── Integración: recálculo no cambia si el admin edita tasas ───────


@pytest.mark.django_db
def test_recalculo_usa_snapshot_no_config_live():
    """Cambiar afp_tasas_override en ConfiguracionSistema NO altera un
    período cuyo snapshot ya congeló las tasas."""
    from asistencia.models import ConfiguracionSistema

    periodo = _periodo_con_snapshot()

    cfg = ConfiguracionSistema.get()
    cfg.afp_tasas_override = {
        'Prima': {'comision_flujo': '2.50', 'seguro': '2.00'},
    }
    cfg.save()

    t = _tasas_afp_efectivas('Prima', periodo)
    assert t['comision_flujo'] == Decimal('1.99')   # sigue el snapshot

    # Sin snapshot sí se usa el override live
    t_live = _tasas_afp_efectivas('Prima', None)
    assert t_live['comision_flujo'] == Decimal('2.50')
