"""
saldo_generar_masivo cuenta papeletas VACACIONES importadas (fuente b),
sin duplicar las espejo de SolicitudVacacion (cola de P1).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from asistencia.models import RegistroPapeleta
from personal.models import Personal
from vacaciones.models import SaldoVacacional, SolicitudVacacion


@pytest.fixture
def admin_client(client, db):
    User.objects.create_superuser('admin.saldo', 's@test.pe', 'x')
    client.login(username='admin.saldo', password='x')
    return client


@pytest.fixture
def empleado(db):
    return Personal.objects.create(
        nro_doc='71234321',
        apellidos_nombres='SALDO TEST, RAUL',
        cargo='Operario',
        tipo_trab='Obrero',
        estado='Activo',
        grupo_tareo='RCO',
        condicion='LOCAL',
        fecha_alta=date(2024, 3, 1),
        sueldo_base=Decimal('1500.00'),
    )


def _papeleta_vac(personal, ini, fin, detalle=''):
    return RegistroPapeleta.objects.create(
        origen='IMPORTACION',
        personal=personal,
        dni=personal.nro_doc,
        tipo_permiso='VACACIONES',
        fecha_inicio=ini,
        fecha_fin=fin,
        estado='APROBADA',
        detalle=detalle,
    )


def _gozados_total(personal):
    from django.db.models import Sum
    return (SaldoVacacional.objects.filter(personal=personal)
            .aggregate(t=Sum('dias_gozados'))['t'] or 0)


def test_papeleta_importada_descuenta_saldo(admin_client, empleado):
    """Papeleta VAC de Synkro sin solicitud: 5 días gozados."""
    _papeleta_vac(empleado, date(2026, 2, 2), date(2026, 2, 6))

    admin_client.post(reverse('saldo_generar_masivo'))

    assert _gozados_total(empleado) == 5


def test_solicitud_y_papeleta_importada_se_suman(admin_client, empleado):
    """Antes la fuente tareo solo corría sin solicitudes: un empleado con
    ambas quedaba subcontado. Ahora 5 (solicitud) + 3 (importada) = 8."""
    SolicitudVacacion.objects.create(
        personal=empleado,
        fecha_inicio=date(2025, 7, 7), fecha_fin=date(2025, 7, 11),
        dias_calendario=0, estado='APROBADA',
    )
    _papeleta_vac(empleado, date(2026, 2, 2), date(2026, 2, 4))

    admin_client.post(reverse('saldo_generar_masivo'))

    assert _gozados_total(empleado) == 8


def test_papeleta_espejo_no_duplica(admin_client, empleado):
    """Aprobar una solicitud crea su papeleta espejo (P1); el masivo debe
    contar 5, no 10."""
    aprobador = User.objects.get(username='admin.saldo')
    sol = SolicitudVacacion.objects.create(
        personal=empleado,
        fecha_inicio=date(2026, 3, 2), fecha_fin=date(2026, 3, 6),
        dias_calendario=0, estado='PENDIENTE',
    )
    sol.aprobar(aprobador)   # crea papeleta 'Auto: SolicitudVacacion #...'
    assert RegistroPapeleta.objects.filter(
        personal=empleado, tipo_permiso='VACACIONES').count() == 1

    admin_client.post(reverse('saldo_generar_masivo'))

    assert _gozados_total(empleado) == 5
