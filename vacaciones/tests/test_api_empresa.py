"""Aislamiento multi-empresa de la API /api/v1/vacaciones/."""
from datetime import date

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from vacaciones.models import SaldoVacacional, SolicitudVacacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    saldo_a = SaldoVacacional.objects.create(
        personal=pers_a,
        periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 12, 31))
    saldo_b = SaldoVacacional.objects.create(
        personal=pers_b,
        periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 12, 31))
    return locals()


def test_saldos_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/vacaciones/saldos/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['saldo_a'].pk not in ids
    assert escenario['saldo_b'].pk in ids


def test_no_crear_solicitud_para_personal_de_otra_empresa(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.post('/api/v1/vacaciones/solicitudes/', {
        'personal': escenario['pers_a'].pk,
        'saldo': escenario['saldo_a'].pk,
        'fecha_inicio': '2026-07-01',
        'fecha_fin': '2026-07-15',
        'dias_calendario': 15,
        'motivo': 'intento cruzado',
    })
    assert resp.status_code == 403
    assert not SolicitudVacacion.objects.filter(
        personal=escenario['pers_a']).exists()


def test_crear_solicitud_misma_empresa_si_funciona(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.post('/api/v1/vacaciones/solicitudes/', {
        'personal': escenario['pers_b'].pk,
        'saldo': escenario['saldo_b'].pk,
        'fecha_inicio': '2026-07-01',
        'fecha_fin': '2026-07-15',
        'dias_calendario': 15,
        'motivo': 'vacaciones normales',
    })
    assert resp.status_code == 201, resp.content
