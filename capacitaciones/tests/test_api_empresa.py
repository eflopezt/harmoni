"""Aislamiento multi-empresa de la API /api/v1/capacitaciones/."""
from datetime import date

import pytest

from capacitaciones.models import (
    Capacitacion, CertificacionTrabajador, RequerimientoCapacitacion,
)
from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    req = RequerimientoCapacitacion.objects.create(nombre='SST Anual')
    cert_a = CertificacionTrabajador.objects.create(
        personal=pers_a, requerimiento=req, fecha_obtencion=date(2026, 1, 15))
    cert_b = CertificacionTrabajador.objects.create(
        personal=pers_b, requerimiento=req, fecha_obtencion=date(2026, 2, 20))
    curso = Capacitacion.objects.create(
        titulo='Curso Interno A', horas=4,
        fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 2))
    return locals()


def test_certificaciones_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/capacitaciones/certificaciones/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['cert_a'].pk not in ids
    assert escenario['cert_b'].pk in ids


def test_capacitaciones_sin_tenancy_deny_para_tenant(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/capacitaciones/capacitaciones/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_requerimientos_son_catalogo_compartido(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/capacitaciones/requerimientos/')
    assert resp.status_code == 200
    assert escenario['req'].pk in ids_de(resp)
