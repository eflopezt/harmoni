"""
Modo disponibilidad del calendario (F3): quién está libre el día X.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from personal.models import Personal


@pytest.fixture
def admin_client(client, db):
    User.objects.create_superuser('admin.dispo', 'd@test.pe', 'x')
    client.login(username='admin.dispo', password='x')
    return client


def _personal(dni, nombre):
    return Personal.objects.create(
        nro_doc=dni,
        apellidos_nombres=nombre,
        cargo='Operario',
        tipo_trab='Obrero',
        estado='Activo',
        grupo_tareo='RCO',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('1500.00'),
    )


def test_todos_disponibles_sin_ausencias(admin_client):
    _personal('71110001', 'DISPO UNO, ANA')
    _personal('71110002', 'DISPO DOS, LUIS')

    resp = admin_client.get('/calendario/disponibilidad/?fecha=2026-08-05')
    data = resp.json()
    assert data['total_activos'] == 2
    assert data['disponibles'] == 2
    assert data['ausentes'] == 0


def test_papeleta_descuenta_disponibilidad(admin_client):
    p = _personal('71110003', 'DISPO TRES, EVA')
    _personal('71110004', 'DISPO CUATRO, JON')
    from asistencia.models import RegistroPapeleta
    RegistroPapeleta.objects.create(
        origen='SISTEMA', personal=p, dni=p.nro_doc,
        tipo_permiso='DESCANSO_MEDICO',
        fecha_inicio=date(2026, 8, 4), fecha_fin=date(2026, 8, 6),
        estado='APROBADA',
    )

    resp = admin_client.get('/calendario/disponibilidad/?fecha=2026-08-05')
    data = resp.json()
    assert data['disponibles'] == 1
    assert data['ausentes'] == 1
    assert data['detalle'][0]['nombre'] == p.apellidos_nombres
    assert 'Descanso' in data['detalle'][0]['motivo']

    # Fuera del rango de la papeleta vuelve a estar disponible
    resp = admin_client.get('/calendario/disponibilidad/?fecha=2026-08-10')
    assert resp.json()['disponibles'] == 2


def test_vacacion_aprobada_cuenta_una_sola_vez(admin_client):
    """La solicitud aprobada genera papeleta espejo (P1): el trabajador debe
    contar como UN ausente, no dos."""
    p = _personal('71110005', 'DISPO CINCO, MIA')
    aprobador = User.objects.get(username='admin.dispo')
    from vacaciones.models import SolicitudVacacion
    sol = SolicitudVacacion.objects.create(
        personal=p,
        fecha_inicio=date(2026, 8, 3), fecha_fin=date(2026, 8, 7),
        dias_calendario=0, estado='PENDIENTE',
    )
    sol.aprobar(aprobador)

    resp = admin_client.get('/calendario/disponibilidad/?fecha=2026-08-05')
    data = resp.json()
    assert data['ausentes'] == 1
    assert data['detalle'][0]['motivo'] == 'Vacaciones'


def test_flag_feriado(admin_client):
    from asistencia.models import FeriadoCalendario
    FeriadoCalendario.objects.create(
        fecha=date(2026, 7, 28), nombre='Fiestas Patrias',
        tipo='NACIONAL', activo=True,
    )
    resp = admin_client.get('/calendario/disponibilidad/?fecha=2026-07-28')
    assert resp.json()['es_feriado'] is True
