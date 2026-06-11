"""
Permisos de escritura del API de conceptos (/api/v1/nominas/conceptos/).

ConceptoRemunerativo es configuración GLOBAL del deployment (sin campo
empresa): la comparten las planillas de todas las empresas. Un admin
tenant (staff, no superuser — como los trial de /onboarding/starter/)
puede leer pero NO crear/editar/borrar conceptos.
"""
import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_usuario, login_en_empresa,
)
from nominas.models import ConceptoRemunerativo

pytestmark = pytest.mark.django_db


@pytest.fixture
def concepto():
    return ConceptoRemunerativo.objects.create(
        codigo='test-concepto-api', nombre='Concepto Test', tipo='INGRESO')


def test_tenant_puede_leer_conceptos(client, concepto):
    login_en_empresa(client, crear_usuario(), crear_empresa())
    resp = client.get('/api/v1/nominas/conceptos/')
    assert resp.status_code == 200


def test_tenant_no_puede_crear_concepto(client, concepto):
    login_en_empresa(client, crear_usuario(), crear_empresa())
    resp = client.post('/api/v1/nominas/conceptos/', {
        'codigo': 'hackeo', 'nombre': 'Hackeo', 'tipo': 'INGRESO',
    })
    assert resp.status_code == 403
    assert not ConceptoRemunerativo.objects.filter(codigo='hackeo').exists()


def test_tenant_no_puede_editar_ni_borrar_concepto(client, concepto):
    login_en_empresa(client, crear_usuario(), crear_empresa())
    resp = client.patch(
        f'/api/v1/nominas/conceptos/{concepto.pk}/',
        {'nombre': 'Alterado'}, content_type='application/json')
    assert resp.status_code == 403
    resp = client.delete(f'/api/v1/nominas/conceptos/{concepto.pk}/')
    assert resp.status_code == 403
    concepto.refresh_from_db()
    assert concepto.nombre == 'Concepto Test'


def test_superuser_si_puede_escribir(client, concepto):
    login_en_empresa(client, crear_usuario(superuser=True), crear_empresa())
    resp = client.post('/api/v1/nominas/conceptos/', {
        'codigo': 'nuevo-su', 'nombre': 'Nuevo SU', 'tipo': 'INGRESO',
    })
    assert resp.status_code == 201, resp.content
