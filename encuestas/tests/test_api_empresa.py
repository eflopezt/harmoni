"""Aislamiento multi-empresa de la API /api/v1/encuestas/."""
from datetime import date

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_usuario, ids_de, login_en_empresa,
)
from encuestas.models import Encuesta

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_b = crear_empresa('Empresa B')
    encuesta = Encuesta.objects.create(
        titulo='Clima 2026', fecha_inicio=date(2026, 6, 1),
        fecha_fin=date(2026, 6, 30))
    return locals()


def test_encuestas_sin_tenancy_deny_para_tenant(client, escenario):
    """Encuesta no tiene ruta a Empresa → deny-by-default para tenants."""
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/encuestas/encuestas/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_superuser_si_ve_encuestas(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    assert escenario['encuesta'].pk in ids_de(
        client.get('/api/v1/encuestas/encuestas/'))
