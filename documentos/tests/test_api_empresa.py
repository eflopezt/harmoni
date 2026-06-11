"""Aislamiento multi-empresa de la API /api/v1/documentos/ (boletas/legajo)."""
from datetime import date

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from documentos.models import BoletaPago

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    boleta_a = BoletaPago.objects.create(
        personal=pers_a, periodo=date(2026, 5, 1), archivo='boletas/test_a.pdf')
    boleta_b = BoletaPago.objects.create(
        personal=pers_b, periodo=date(2026, 5, 1), archivo='boletas/test_b.pdf')
    return locals()


def test_boletas_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/documentos/boletas/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['boleta_a'].pk not in ids
    assert escenario['boleta_b'].pk in ids


def test_detalle_boleta_ajena_404(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get(f"/api/v1/documentos/boletas/{escenario['boleta_a'].pk}/")
    assert resp.status_code == 404


def test_superuser_ve_todo(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    ids = ids_de(client.get('/api/v1/documentos/boletas/'))
    assert {escenario['boleta_a'].pk, escenario['boleta_b'].pk} <= ids
