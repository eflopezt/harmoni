"""
Tests del enlace Roster/Tareo → Planilla (nominas/services/asistencia_link.py).
"""
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from nominas.services.asistencia_link import (
    resumen_asistencia_roster,
    poblar_registro_desde_roster,
    jornada_promedio_ciclo,
)


# ── jornada_promedio_ciclo (puro) ──────────────────────────────────

def test_jornada_promedio_21x7():
    # 21x7 → ciclo 28 días, horas_max 192 → 192/28 = 6.86
    reg = SimpleNamespace(ciclo_total_dias=28, horas_max_ciclo=Decimal('192'))
    assert jornada_promedio_ciclo(reg) == Decimal('6.86')


def test_jornada_promedio_none_default_8():
    assert jornada_promedio_ciclo(None) == Decimal('8')


def test_jornada_promedio_ciclo_cero_default_8():
    reg = SimpleNamespace(ciclo_total_dias=0, horas_max_ciclo=Decimal('0'))
    assert jornada_promedio_ciclo(reg) == Decimal('8')


# ── poblar_registro_desde_roster (lógica, con resumen mockeado) ─────

_RESUMEN_FAKE = {
    'dias_periodo': 30, 'trabajados': 14, 'descanso': 14,
    'falta': 2, 'vacaciones': 0, 'licencia': 0, 'sin_registro': 0, 'codigos': {},
}


def _fake_registro():
    periodo = SimpleNamespace(fecha_inicio=date(2026, 1, 1), fecha_fin=date(2026, 1, 30))
    return SimpleNamespace(
        periodo=periodo, personal=object(),
        dias_trabajados=30, dias_descanso=0, dias_falta=0,
    )


def test_poblar_convencion_mensual_descuenta_faltas():
    reg = _fake_registro()
    with patch('nominas.services.asistencia_link.resumen_asistencia_roster',
               return_value=dict(_RESUMEN_FAKE)):
        poblar_registro_desde_roster(reg, convencion='mensual')
    assert reg.dias_trabajados == 28   # 30 − 2 faltas
    assert reg.dias_descanso == 14
    assert reg.dias_falta == 2


def test_poblar_convencion_jornal_usa_trabajados():
    reg = _fake_registro()
    with patch('nominas.services.asistencia_link.resumen_asistencia_roster',
               return_value=dict(_RESUMEN_FAKE)):
        poblar_registro_desde_roster(reg, convencion='jornal')
    assert reg.dias_trabajados == 14   # solo días T/TR
    assert reg.dias_falta == 2


# ── resumen_asistencia_roster (con DB) ─────────────────────────────

@pytest.mark.django_db
def test_resumen_cuenta_por_categoria():
    from personal.models import Area, SubArea, Personal, Roster

    area = Area.objects.create(nombre='AREA X')
    subarea = SubArea.objects.create(nombre='SUB X', area=area)
    p = Personal.objects.create(
        nro_doc='81000001', apellidos_nombres='ROSTER TEST',
        cargo='OBRERO', tipo_trab='Obrero', subarea=subarea, estado='Activo',
    )

    ini = date(2026, 1, 1)
    # 30 días: 14 T, 7 D, 7 DS, ... construimos 14 T + 14 D + 2 F = 30
    codigos = ['T'] * 14 + ['D'] * 14 + ['F'] * 2
    for i, cod in enumerate(codigos):
        Roster.objects.create(personal=p, fecha=ini + timedelta(days=i), codigo=cod)

    r = resumen_asistencia_roster(p, ini, ini + timedelta(days=29))
    assert r['dias_periodo'] == 30
    assert r['trabajados'] == 14
    assert r['descanso'] == 14
    assert r['falta'] == 2
    assert r['sin_registro'] == 0


@pytest.mark.django_db
def test_resumen_dias_sin_registro():
    from personal.models import Area, SubArea, Personal, Roster

    area = Area.objects.create(nombre='AREA Y')
    subarea = SubArea.objects.create(nombre='SUB Y', area=area)
    p = Personal.objects.create(
        nro_doc='81000002', apellidos_nombres='ROSTER HUECO',
        cargo='OBRERO', tipo_trab='Obrero', subarea=subarea, estado='Activo',
    )
    ini = date(2026, 2, 1)
    for i in range(10):                        # solo 10 días con registro
        Roster.objects.create(personal=p, fecha=ini + timedelta(days=i), codigo='T')

    r = resumen_asistencia_roster(p, ini, ini + timedelta(days=27))  # 28 días
    assert r['trabajados'] == 10
    assert r['dias_periodo'] == 28
    assert r['sin_registro'] == 18
