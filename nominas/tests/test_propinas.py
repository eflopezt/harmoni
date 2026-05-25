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
    HorasTrabajadasPropinas,
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


# ════════════════════════════════════════════════════════════════════════
# Mejoras 2026-05-25 — best practices mundiales
# Ref: docs/internal/PROPINAS_BEST_PRACTICES_2026.md
# ════════════════════════════════════════════════════════════════════════

# ── 1) cash + card → bruto autoconsistente ──────────────────────────────
@pytest.mark.django_db
def test_pool_recompone_bruto_desde_cash_y_card():
    """Si se setea monto_cash y monto_card, monto_bruto = cash + card."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PAREJO')
    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_cash=Decimal('300.00'),
        monto_card=Decimal('700.00'),
    )
    pool.refresh_from_db()
    assert pool.monto_bruto == Decimal('1000.00')


@pytest.mark.django_db
def test_pool_bruto_legacy_solo_funciona_sin_cash_card():
    """Compat: pools antiguos que solo seteen monto_bruto siguen sirviendo."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PAREJO')
    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('500.00'),
    )
    pool.refresh_from_db()
    assert pool.monto_bruto == Decimal('500.00')
    assert pool.monto_cash == Decimal('0')
    assert pool.monto_card == Decimal('0')


# ── 2) Modo POOL_HORAS ──────────────────────────────────────────────────
@pytest.mark.django_db
def test_distribuir_modo_pool_horas_per_hour_rate():
    """POOL_HORAS: reparte proporcional a horas trabajadas (per-hour rate)."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_HORAS')
    mozo = _cargo('Mozo')
    p1 = _persona(emp, mozo)
    p2 = _persona(emp, mozo)
    p3 = _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('1000.00'),
    )
    # Horas: 40 + 30 + 30 = 100 → tasa 10/h
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p1, horas=Decimal('40'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p2, horas=Decimal('30'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p3, horas=Decimal('30'))

    distribuciones = pool.distribuir()
    assert len(distribuciones) == 3
    montos = {d.personal_id: d.monto for d in distribuciones}
    assert montos[p1.pk] == Decimal('400.00')
    assert montos[p2.pk] == Decimal('300.00')
    assert montos[p3.pk] == Decimal('300.00')
    total = sum(d.monto for d in distribuciones)
    assert total == Decimal('1000.00')


@pytest.mark.django_db
def test_distribuir_pool_horas_fallback_si_no_hay_horas():
    """POOL_HORAS sin registros de horas → fallback a reparto parejo."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_HORAS')
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('200.00'),
    )
    # No hay HorasTrabajadasPropinas → todos quedan con DEFAULT 1.00h c/u → parejo
    distribuciones = pool.distribuir()
    assert len(distribuciones) == 2
    for d in distribuciones:
        assert d.monto == Decimal('100.00')


# ── 3) Modo POOL_PUNTOS_HORAS (híbrido — best practice) ─────────────────
@pytest.mark.django_db
def test_distribuir_modo_pool_puntos_horas_hibrido():
    """POOL_PUNTOS_HORAS: peso = puntos × horas.

    Server (3pts) × 40h = 120
    Server (3pts) × 20h = 60
    Cocina (1pt)  × 40h = 40
    Total = 220
    Pool S/ 1100 → tasa 5/unidad
    Resultado: 600, 300, 200
    """
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PUNTOS_HORAS')
    mozo = _cargo('Mozo')
    cocina = _cargo('Cocina')
    PuntosPropinas.objects.create(configuracion=cfg, cargo=mozo, puntos=Decimal('3'))
    PuntosPropinas.objects.create(configuracion=cfg, cargo=cocina, puntos=Decimal('1'))

    p_mozo_full = _persona(emp, mozo)
    p_mozo_half = _persona(emp, mozo)
    p_cocina = _persona(emp, cocina)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('1100.00'),
    )
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_mozo_full, horas=Decimal('40'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_mozo_half, horas=Decimal('20'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_cocina,    horas=Decimal('40'))

    distribuciones = pool.distribuir()
    montos = {d.personal_id: d.monto for d in distribuciones}
    assert montos[p_mozo_full.pk] == Decimal('600.00')
    assert montos[p_mozo_half.pk] == Decimal('300.00')
    assert montos[p_cocina.pk]    == Decimal('200.00')


# ── 4) Tip-out FOH → BOH ────────────────────────────────────────────────
@pytest.mark.django_db
def test_tipout_boh_separa_15_por_ciento_para_cocina():
    """Si incluye_cocina=False y porcentaje_tipout_boh=15, BOH recibe 15% parejo.

    Bruto 1000, cocina excluida del pool principal, tip-out 15% → S/ 150 a BOH
    Pool FOH = 850 entre 2 mozos = 425 c/u
    BOH = 150 entre 1 cocinero = 150
    """
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
        incluye_cocina=False,
        porcentaje_tipout_boh=Decimal('15'),
    )
    mozo = _cargo('Mozo')
    cocina = _cargo('Cocinero Principal')
    _persona(emp, mozo)
    _persona(emp, mozo)
    cocinero = _persona(emp, cocina, cargo_str='Cocinero Principal')

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('1000.00'),
    )
    assert pool.monto_tipout_boh == Decimal('150.00')
    assert pool.monto_distribuible_foh == Decimal('850.00')

    distribuciones = pool.distribuir()
    foh = [d for d in distribuciones if not d.es_tipout_boh]
    boh = [d for d in distribuciones if d.es_tipout_boh]
    assert len(foh) == 2
    assert len(boh) == 1
    assert all(d.monto == Decimal('425.00') for d in foh)
    assert boh[0].personal_id == cocinero.pk
    assert boh[0].monto == Decimal('150.00')


@pytest.mark.django_db
def test_tipout_boh_se_ignora_si_cocina_ya_incluida():
    """Si incluye_cocina=True, el porcentaje_tipout_boh es 0 (cocina ya en pool)."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
        incluye_cocina=True,
        porcentaje_tipout_boh=Decimal('15'),  # debe ignorarse
    )
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('600.00'),
    )
    assert pool.monto_tipout_boh == Decimal('0.00')
    assert pool.monto_distribuible_foh == Decimal('600.00')


@pytest.mark.django_db
def test_tipout_boh_sin_cocina_disponible_regresa_al_foh():
    """Si tip-out activado pero no hay BOH detectable, el monto regresa al FOH."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(
        empresa=emp, modo='POOL_PAREJO',
        incluye_cocina=False,
        porcentaje_tipout_boh=Decimal('20'),
    )
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)
    # No hay cocinero/chef en la empresa

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('500.00'),
    )
    distribuciones = pool.distribuir()
    # Todo el monto debe ir al FOH (sin tip-out)
    foh = [d for d in distribuciones if not d.es_tipout_boh]
    boh = [d for d in distribuciones if d.es_tipout_boh]
    assert len(foh) == 2
    assert len(boh) == 0
    for d in foh:
        assert d.monto == Decimal('250.00')


# ── 5) Detección de anomalías ───────────────────────────────────────────
@pytest.mark.django_db
def test_anomalia_se_marca_cuando_monto_es_menor_50pct_del_cargo():
    """Si un mozo recibe < 50% del promedio de mozos → anomalia=True."""
    emp = _empresa()
    cfg = ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PUNTOS_HORAS')
    mozo = _cargo('Mozo')
    PuntosPropinas.objects.create(configuracion=cfg, cargo=mozo, puntos=Decimal('3'))

    p_alto1 = _persona(emp, mozo)
    p_alto2 = _persona(emp, mozo)
    p_bajo = _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('1000.00'),
    )
    # 2 mozos con 40h, 1 con 2h → muy desigual
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_alto1, horas=Decimal('40'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_alto2, horas=Decimal('40'))
    HorasTrabajadasPropinas.objects.create(pool=pool, personal=p_bajo,  horas=Decimal('2'))

    pool.distribuir()
    d_alto1 = DistribucionPropinas.objects.get(pool=pool, personal=p_alto1)
    d_alto2 = DistribucionPropinas.objects.get(pool=pool, personal=p_alto2)
    d_bajo = DistribucionPropinas.objects.get(pool=pool, personal=p_bajo)

    assert d_alto1.anomalia is False
    assert d_alto2.anomalia is False
    assert d_bajo.anomalia is True  # mucho menor que los otros mozos


@pytest.mark.django_db
def test_anomalia_no_se_marca_si_solo_un_trabajador_en_cargo():
    """Con un único trabajador en su cargo, no se puede calcular anomalía."""
    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PAREJO')
    mozo = _cargo('Mozo')
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_bruto=Decimal('100.00'),
    )
    distribuciones = pool.distribuir()
    assert len(distribuciones) == 1
    assert distribuciones[0].anomalia is False


# ── 6) PDF reporte distribución ─────────────────────────────────────────
@pytest.mark.django_db
def test_acta_distribucion_pdf_genera_bytes():
    """El generador de PDF de Acta de Distribución produce bytes válidos."""
    from nominas.pdf_propinas import generar_acta_distribucion_pdf

    emp = _empresa()
    ConfiguracionPropinas.objects.create(empresa=emp, modo='POOL_PAREJO')
    mozo = _cargo('Mozo')
    _persona(emp, mozo)
    _persona(emp, mozo)

    pool = PoolPropinas.objects.create(
        empresa=emp,
        fecha_inicio=date(2026, 5, 18),
        fecha_fin=date(2026, 5, 24),
        monto_cash=Decimal('200.00'),
        monto_card=Decimal('300.00'),
    )
    pool.distribuir()

    pdf_bytes = generar_acta_distribucion_pdf(pool)
    assert isinstance(pdf_bytes, (bytes, bytearray))
    assert pdf_bytes.startswith(b'%PDF')
    assert len(pdf_bytes) > 1000  # PDF no trivial
