"""Aislamiento multi-empresa de vacantes y PII de candidatos."""
import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_usuario, ids_de, login_en_empresa,
)
from reclutamiento.models import EtapaPipeline, Postulacion, Vacante

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    vacante = Vacante.objects.create(empresa=emp_a, titulo='Jefe de Planta')
    post = Postulacion.objects.create(
        vacante=vacante, nombre_completo='CANDIDATO CONFIDENCIAL',
        email='candidato@privado.pe')
    etapa = EtapaPipeline.objects.create(nombre='Entrevista', orden=1)
    return locals()


def test_vacantes_ajenas_no_aparecen_para_tenant(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/reclutamiento/vacantes/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_postulaciones_ajenas_no_aparecen_para_tenant(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/reclutamiento/postulaciones/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()
    resp = client.get(
        f"/api/v1/reclutamiento/postulaciones/{escenario['post'].pk}/")
    assert resp.status_code == 404


def test_tenant_no_puede_crear_postulacion(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.post('/api/v1/reclutamiento/postulaciones/', {
        'vacante': escenario['vacante'].pk,
        'nombre_completo': 'INTRUSO API',
    })
    assert resp.status_code in (400, 403)


def test_funnel_stats_no_filtra_data_ajena(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/reclutamiento/postulaciones/funnel-stats/')
    assert resp.status_code == 200
    assert all(item['count'] == 0 for item in resp.json())


def test_etapas_son_catalogo_compartido(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    assert escenario['etapa'].pk in ids_de(
        client.get('/api/v1/reclutamiento/etapas/'))


def test_superuser_si_ve_postulaciones(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    session = client.session
    session['modo_consolidado'] = True
    session.pop('empresa_actual_id', None)
    session.save()
    assert escenario['post'].pk in ids_de(
        client.get('/api/v1/reclutamiento/postulaciones/'))


def test_tenant_ve_vacante_y_postulacion_propias(client, escenario):
    vacante = Vacante.objects.create(
        empresa=escenario['emp_b'], titulo='Analista propio')
    post = Postulacion.objects.create(
        vacante=vacante, nombre_completo='CANDIDATO PROPIO')
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])

    assert vacante.pk in ids_de(client.get('/api/v1/reclutamiento/vacantes/'))
    assert post.pk in ids_de(client.get('/api/v1/reclutamiento/postulaciones/'))
