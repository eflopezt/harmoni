"""
Papeleta como fuente única de ausencias (P1 del análisis de flujo):
aprobar una SolicitudVacacion crea automáticamente la RegistroPapeleta
VACACIONES (que a su vez sincroniza el tareo) y marca VAC en el Roster.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from asistencia.models import ConfiguracionSistema, RegistroPapeleta, RegistroTareo
from personal.models import Personal, Roster
from vacaciones.models import SaldoVacacional, SolicitudVacacion


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def aprobador(db):
    return User.objects.create_user('jefe.rrhh', 'rrhh@test.pe', 'x')


@pytest.fixture
def personal(db):
    return Personal.objects.create(
        nro_doc='76666666',
        apellidos_nombres='VACACIONISTA TEST, ANA',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('3000.00'),
    )


@pytest.fixture
def saldo(personal):
    return SaldoVacacional.objects.create(
        personal=personal,
        periodo_inicio=date(2025, 1, 1),
        periodo_fin=date(2025, 12, 31),
        dias_derecho=30,
        dias_gozados=0,
        dias_vendidos=0,
        dias_pendientes=30,
        estado='PENDIENTE',
    )


@pytest.fixture
def config_roster_on(db):
    cfg = ConfiguracionSistema.get()
    cfg.mod_roster = True
    cfg.save()
    return cfg


def _solicitud(personal, saldo, ini=date(2026, 7, 6), fin=date(2026, 7, 10)):
    return SolicitudVacacion.objects.create(
        personal=personal,
        saldo=saldo,
        fecha_inicio=ini,
        fecha_fin=fin,
        dias_calendario=0,   # recalculado en save()
        estado='PENDIENTE',
    )


# ═════════════════════════════════════════════════════════════════════════════
# Papeleta automática
# ═════════════════════════════════════════════════════════════════════════════


def test_aprobar_crea_papeleta_vacaciones(personal, saldo, aprobador):
    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)

    pap = RegistroPapeleta.objects.get(
        personal=personal, tipo_permiso='VACACIONES')
    assert pap.estado == 'APROBADA'
    assert pap.origen == 'SISTEMA'
    assert (pap.fecha_inicio, pap.fecha_fin) == (sol.fecha_inicio, sol.fecha_fin)
    assert pap.aprobado_por == aprobador
    assert f'#{sol.pk}' in pap.detalle


def test_aprobar_sincroniza_tareo_vac(personal, saldo, aprobador):
    """La papeleta auto-creada dispara su propio signal → tareo del rango en VAC."""
    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)

    codigos = set(
        RegistroTareo.objects.filter(
            personal=personal,
            fecha__gte=sol.fecha_inicio, fecha__lte=sol.fecha_fin,
        ).values_list('codigo_dia', flat=True)
    )
    assert codigos == {'VAC'}


def test_no_duplica_papeleta_si_ya_hay_solapada(personal, saldo, aprobador):
    RegistroPapeleta.objects.create(
        origen='SISTEMA',
        personal=personal,
        dni=personal.nro_doc,
        tipo_permiso='VACACIONES',
        fecha_inicio=date(2026, 7, 8),
        fecha_fin=date(2026, 7, 12),
        estado='APROBADA',
    )
    sol = _solicitud(personal, saldo)   # 6→10 jul: solapa con la existente
    sol.aprobar(aprobador)

    assert RegistroPapeleta.objects.filter(
        personal=personal, tipo_permiso='VACACIONES').count() == 1


def test_reaprobar_no_duplica(personal, saldo, aprobador):
    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)
    sol.save()   # re-save en estado APROBADA no debe re-sincronizar

    assert RegistroPapeleta.objects.filter(
        personal=personal, tipo_permiso='VACACIONES').count() == 1


def test_rechazar_no_crea_papeleta(personal, saldo, aprobador):
    sol = _solicitud(personal, saldo)
    sol.rechazar(aprobador, 'cobertura insuficiente')

    assert not RegistroPapeleta.objects.filter(
        personal=personal, tipo_permiso='VACACIONES').exists()


def test_saldo_sigue_descontandose(personal, saldo, aprobador):
    sol = _solicitud(personal, saldo)   # 5 días calendario
    sol.aprobar(aprobador)

    saldo.refresh_from_db()
    assert saldo.dias_gozados == 5
    assert saldo.dias_pendientes == 25


# ═════════════════════════════════════════════════════════════════════════════
# Roster VAC
# ═════════════════════════════════════════════════════════════════════════════


def test_aprobar_marca_vac_en_roster(personal, saldo, aprobador, config_roster_on):
    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)

    dias = Roster.objects.filter(
        personal=personal,
        fecha__gte=sol.fecha_inicio, fecha__lte=sol.fecha_fin,
    )
    assert dias.count() == sol.dias_calendario
    assert set(dias.values_list('codigo', flat=True)) == {'VAC'}
    assert set(dias.values_list('estado', flat=True)) == {'aprobado'}


def test_roster_existente_se_sobrescribe_a_vac(personal, saldo, aprobador, config_roster_on):
    """Un turno T ya programado en el rango pasa a VAC (la ausencia gana)."""
    Roster.objects.create(personal=personal, fecha=date(2026, 7, 7), codigo='T')

    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)

    r = Roster.objects.get(personal=personal, fecha=date(2026, 7, 7))
    assert r.codigo == 'VAC'


def test_roster_no_se_toca_si_modulo_apagado(personal, saldo, aprobador):
    cfg = ConfiguracionSistema.get()
    cfg.mod_roster = False
    cfg.save()

    sol = _solicitud(personal, saldo)
    sol.aprobar(aprobador)

    assert not Roster.objects.filter(personal=personal).exists()
    # La papeleta sí se crea igual (no depende del módulo roster)
    assert RegistroPapeleta.objects.filter(
        personal=personal, tipo_permiso='VACACIONES').exists()
