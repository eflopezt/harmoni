"""
Tests del módulo Pool de Propinas.

Cubre:
  - Configuración (defaults, unique por empresa).
  - PuntosPropinas (unique per (config, cargo)).
  - PoolPropinas.distribuir() en sus 3 modos (POOL_PUNTOS, POOL_PAREJO, INDIVIDUAL).
  - Reglas: incluye_cocina / incluye_admin.
  - Retención casa (porcentaje_casa).
  - Idempotencia.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.db import IntegrityError

from empresas.models import Empresa
from personal.models import Cargo, Personal

from nominas.models_propinas import (
    ConfiguracionPropinas,
    DistribucionPropinas,
    PoolPropinas,
    PuntosPropinas,
)


# ── helpers ──────────────────────────────────────────────────────────────
def _empresa(ruc='20111222333', razon='Pollería Las Mesas'):
    e, _ = Empresa.objects.get_or_create(
        ruc=ruc,
        defaults={'razon_social': razon, 'plan': 'PROFESIONAL'},
    )
    return e


def _cargo(nombre, nivel=5):
    c, _ = Cargo.objects.get_or_create(
        nombre=nombre, defaults={'nivel': nivel},
    )
    return c


_dni_seq = [1000]


def _persona(empresa, cargo_obj, cargo_str=None, estado='Activo',
             fecha_alta=None, fecha_cese=None):
    _dni_seq[0] += 1
    dni = f'7{_dni_seq[0]:07d}'
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=dni,
        apellidos_nombres=f'Trabajador {dni}',
        cargo=cargo_str or cargo_obj.nombre,
        cargo_obj=cargo_obj,
        tipo_trab='Empleado',
        estado=estado,
        fecha_alta=fecha_alta or date(2025, 1, 1),
        fecha_cese=fecha_cese,
        sueldo_base=Decimal('1500'),
    )


# ════════════════════════════════════════════════════════════════════════
# Tests
# ════════════════════════════════════════════════════════════════════════
@pytest.mark.django_db
def test_configuracion_defaults():
    """ConfiguracionPropinas tiene defaults correctos."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(empresa=emp)
    assert cfg.modo == 'POOL_PUNTOS'
    assert cfg.incluye_cocina is True
    assert cfg.incluye_admin is False
    assert cfg.porcentaje_casa == Decimal('0')


@pytest.mark.django_db
def test_configuracion_unique_por_empresa():
    """No se puede tener 2 ConfiguracionPropinas para la misma empresa."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp)
    with pytest.raises(IntegrityError):
        ConfiguracionPropinas.objects.create(empresa=emp)


@pytest.mark.django_db
def test_puntos_unique_per_cargo():
    """PuntosPropinas unique_together = (configuracion, cargo)."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(empresa=emp)
    mozo = _cargo('Mozo')
    PuntosPropinas.objects.create(configuracion=cfg, cargo=mozo, puntos=Decimal('3'))
    with pytest.raises(IntegrityError):
        PuntosPropinas.objects.create(configuracion=cfg, cargo=mozo, puntos=Decimal('5'))


@pytest.mark.django_db
def test_distribuir_modo_pool_puntos_suma_correcta():
    """
    Modo POOL_PUNTOS: la suma de distribuciones == monto_distribuible.
    Cada persona recibe (monto_distribuible * puntos) / suma_puntos.
    """
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PUNTOS',
        incluye_cocina=True, porcentaje_casa=Decimal('0'),
    )
    mozo = _cargo('Mozo')
    cocina = _cargo('Cocina')
    PuntosPropinas.objects.create(configuracion=cfg, cargo=mozo, puntos=Decimal('3'))
    PuntosPropinas.objects.create(configuracion=cfg, cargo=cocina, puntos=Decimal('1'))

    _persona(emp, mozo)
    _persona(emp, mozo)
    _persona(emp, cocina)
    # suma puntos = 3 + 3 + 1 = 7

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('700.00'),
    )
    distribuciones = pool.distribuir()

    assert len(distribuciones) == 3
    # Reparto: 3/7, 3/7, 1/7 de 700 = 300, 300, 100
    montos = sorted(d.monto for d in distribuciones)
    assert montos == [Decimal('100.00'), Decimal('300.00'), Decimal('300.00')]
    total = sum(d.monto for d in distribuciones)
    assert total == Decimal('700.00')

    pool.refresh_from_db()
    assert pool.distribuido is True
    assert pool.distribuido_en is not None


@pytest.mark.django_db
def test_distribuir_modo_pool_parejo_divide_igual():
    """Modo POOL_PAREJO: monto / N."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO', porcentaje_casa=Decimal('0'),
    )
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('400.00'),
    )
    distribuciones = pool.distribuir()
    assert len(distribuciones) == 4
    for d in distribuciones:
        assert d.monto == Decimal('100.00')


@pytest.mark.django_db
def test_distribuir_respeta_incluye_cocina_false():
    """Si incluye_cocina=False, los cargos de cocina quedan excluidos."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
        incluye_cocina=False, porcentaje_casa=Decimal('0'),
    )
    mozo = _cargo('Mozo')
    cocinero = _cargo('Cocinero Principal')

    _persona(emp, mozo, cargo_str='Mozo')
    _persona(emp, mozo, cargo_str='Mozo')
    _persona(emp, cocinero, cargo_str='Cocinero Principal')  # debería quedar fuera
    _persona(emp, cocinero, cargo_str='Lavaplatos')          # debería quedar fuera

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('200.00'),
    )
    distribuciones = pool.distribuir()
    # Solo los 2 mozos participan; pareja → 100 c/u
    assert len(distribuciones) == 2
    for d in distribuciones:
        assert d.monto == Decimal('100.00')
        assert 'cocin' not in d.personal.cargo.lower()
        assert 'lavapl' not in d.personal.cargo.lower()


@pytest.mark.django_db
def test_distribuir_resta_porcentaje_casa():
    """porcentaje_casa retiene del monto bruto antes de distribuir."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
        porcentaje_casa=Decimal('10'),  # 10% queda en casa
    )
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('1000.00'),
    )
    assert pool.monto_casa == Decimal('100.00')
    assert pool.monto_distribuible == Decimal('900.00')

    distribuciones = pool.distribuir()
    assert len(distribuciones) == 2
    for d in distribuciones:
        assert d.monto == Decimal('450.00')


@pytest.mark.django_db
def test_distribuir_idempotente_no_re_distribuye():
    """Llamar distribuir() dos veces no crea distribuciones duplicadas."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
    )
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('200.00'),
    )
    first = pool.distribuir()
    assert len(first) == 2

    second = pool.distribuir()
    assert second == []  # ya distribuido
    assert DistribucionPropinas.objects.filter(pool=pool).count() == 2


@pytest.mark.django_db
def test_distribuir_modo_individual_no_crea_distribuciones():
    """Modo INDIVIDUAL: marca como distribuido sin crear entradas."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(empresa=emp, modo='INDIVIDUAL')
    mozo = _cargo('Mozo')
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('500.00'),
    )
    distribuciones = pool.distribuir()
    assert distribuciones == []
    pool.refresh_from_db()
    assert pool.distribuido is True
    assert DistribucionPropinas.objects.filter(pool=pool).count() == 0


@pytest.mark.django_db
def test_distribuir_excluye_cesados_y_otras_empresas():
    """
    Solo participan trabajadores activos del rango y de la empresa correcta.
    Cesados antes de fecha_inicio o de otra empresa quedan fuera.
    """
    emp_a = _empresa(ruc='20999000001', razon='Local A')
    emp_b = _empresa(ruc='20999000002', razon='Local B')
    cfg_a = ConfiguracionPropinas.objects.create(
        empresa=emp_a, modo='POOL_PAREJO',
    )
    mozo = _cargo('Mozo')

    # Activos en A → entran
    _persona(emp_a, mozo)
    _persona(emp_a, mozo)
    # Activo en B → no entra
    _persona(emp_b, mozo)
    # Cesado antes de fecha_inicio → no entra
    _persona(emp_a, mozo, estado='Cesado',
             fecha_cese=date(2026, 5, 1))
    # Cesado dentro del rango → entra
    _persona(emp_a, mozo, estado='Activo',
             fecha_cese=date(2026, 5, 22))

    pool = PoolPropinas.objects.create(
        empresa=emp_a,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('300.00'),
    )
    distribuciones = pool.distribuir()
    # 2 activos sin cese + 1 con cese dentro del rango = 3
    assert len(distribuciones) == 3
    for d in distribuciones:
        assert d.personal.empresa_id == emp_a.pk
        assert d.monto == Decimal('100.00')
