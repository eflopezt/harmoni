"""Aislamiento multi-empresa de la API /api/v1/analytics/.

KPISnapshot/AlertaRRHH agregan data de todo el deployment sin campo
empresa → deny-by-default. Clave porque IsAdminUser deja pasar a
cualquier is_staff, y los admins trial de /onboarding/starter/ se crean
con is_staff=True.
"""
from datetime import date

import pytest

from analytics.models import AlertaRRHH, KPISnapshot
from core.tests.helpers_api_empresa import (
    crear_empresa, crear_usuario, ids_de, login_en_empresa,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_b = crear_empresa('Empresa B')
    snapshot = KPISnapshot.objects.create(periodo=date(2026, 5, 1))
    alerta = AlertaRRHH.objects.create(
        titulo='Rotación alta', descripcion='x')
    return locals()


def test_staff_trial_no_ve_kpis_globales(client, escenario):
    login_en_empresa(client, crear_usuario(staff=True), escenario['emp_b'])
    resp = client.get('/api/v1/analytics/snapshots/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_staff_trial_no_ve_alertas_globales(client, escenario):
    login_en_empresa(client, crear_usuario(staff=True), escenario['emp_b'])
    resp = client.get('/api/v1/analytics/alertas/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_superuser_si_ve_kpis(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    assert escenario['snapshot'].pk in ids_de(
        client.get('/api/v1/analytics/snapshots/'))
