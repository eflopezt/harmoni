"""Aislamiento multi-empresa de la API /api/v1/salarios/."""
from datetime import date
from decimal import Decimal

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from salarios.models import BandaSalarial, HistorialSalarial, SimulacionIncremento

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    hist_a = HistorialSalarial.objects.create(
        personal=pers_a, fecha_efectiva=date(2026, 1, 1),
        remuneracion_anterior=Decimal('2000'), remuneracion_nueva=Decimal('2500'))
    hist_b = HistorialSalarial.objects.create(
        personal=pers_b, fecha_efectiva=date(2026, 1, 1),
        remuneracion_anterior=Decimal('3000'), remuneracion_nueva=Decimal('3500'))
    banda = BandaSalarial.objects.create(
        cargo='Gerente', minimo=Decimal('8000'), medio=Decimal('10000'),
        maximo=Decimal('15000'))
    sim = SimulacionIncremento.objects.create(
        nombre='Simulación Q3', fecha=date(2026, 6, 1))
    return locals()


def test_historial_de_a_invisible_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/salarios/historial/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['hist_a'].pk not in ids
    assert escenario['hist_b'].pk in ids


def test_bandas_sin_tenancy_deny_para_tenant(client, escenario):
    """BandaSalarial no tiene ruta a Empresa → deny-by-default."""
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/salarios/bandas/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_simulaciones_sin_tenancy_deny_para_tenant(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/salarios/simulaciones/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_superuser_si_ve_bandas_y_simulaciones(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    assert escenario['banda'].pk in ids_de(client.get('/api/v1/salarios/bandas/'))
    assert escenario['sim'].pk in ids_de(client.get('/api/v1/salarios/simulaciones/'))
