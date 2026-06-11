"""
Aislamiento multi-empresa de la API /api/v1/personal/.

Un usuario tenant (staff, NO superuser) con Empresa B activa no debe
ver ni crear/asociar datos de Empresa A.
"""
from datetime import date

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from personal.models import Personal, Roster

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    return {
        'emp_a': emp_a,
        'emp_b': emp_b,
        'pers_a': crear_personal(emp_a, 'VICTIMA EMPRESA A'),
        'pers_b': crear_personal(emp_b, 'TRABAJADOR EMPRESA B'),
    }


class TestPersonalAPI:
    def test_usuario_de_b_no_lista_personal_de_a(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.get('/api/v1/personal/personal/')
        assert resp.status_code == 200
        ids = ids_de(resp)
        assert escenario['pers_a'].pk not in ids
        assert escenario['pers_b'].pk in ids

    def test_usuario_de_b_no_recupera_detalle_de_a(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.get(f"/api/v1/personal/personal/{escenario['pers_a'].pk}/")
        assert resp.status_code == 404

    def test_action_activos_tambien_filtra(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.get('/api/v1/personal/personal/activos/')
        assert resp.status_code == 200
        assert escenario['pers_a'].pk not in ids_de(resp)

    def test_superuser_ve_ambas_empresas(self, client, escenario):
        login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
        ids = ids_de(client.get('/api/v1/personal/personal/'))
        assert {escenario['pers_a'].pk, escenario['pers_b'].pk} <= ids

    def test_sin_empresa_activa_deny_by_default(self, client, escenario):
        # Sin empresa en sesión ni empresa principal → queryset.none()
        login_en_empresa(client, crear_usuario(), empresa=None)
        resp = client.get('/api/v1/personal/personal/')
        assert resp.status_code == 200
        assert ids_de(resp) == set()

    def test_create_fuerza_empresa_activa(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.post('/api/v1/personal/personal/', {
            'nro_doc': '99887766',
            'apellidos_nombres': 'NUEVO TRABAJADOR, API',
            'cargo': 'Asistente',
            'tipo_trab': 'Empleado',
            'estado': 'Activo',
        })
        assert resp.status_code == 201, resp.content
        nuevo = Personal.objects.get(nro_doc='99887766')
        assert nuevo.empresa_id == escenario['emp_b'].pk

    def test_create_con_empresa_ajena_en_payload_es_rechazado(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.post('/api/v1/personal/personal/', {
            'nro_doc': '99887755',
            'apellidos_nombres': 'INTRUSO, API',
            'cargo': 'Asistente',
            'tipo_trab': 'Empleado',
            'estado': 'Activo',
            'empresa': escenario['emp_a'].pk,
        })
        assert resp.status_code == 403
        assert not Personal.objects.filter(nro_doc='99887755').exists()


class TestRosterAPI:
    def test_roster_de_a_invisible_para_b(self, client, escenario):
        roster_a = Roster.objects.create(
            personal=escenario['pers_a'], fecha=date(2026, 6, 1), codigo='D')
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.get('/api/v1/personal/roster/')
        assert resp.status_code == 200
        assert roster_a.pk not in ids_de(resp)

    def test_no_crear_roster_para_personal_de_otra_empresa(self, client, escenario):
        login_en_empresa(client, crear_usuario(superuser=False), escenario['emp_b'])
        resp = client.post('/api/v1/personal/roster/', {
            'personal': escenario['pers_a'].pk,
            'fecha': '2026-06-01',
            'codigo': 'D',
        })
        assert resp.status_code == 403
        assert not Roster.objects.filter(personal=escenario['pers_a']).exists()

    def test_bulk_create_cruzado_es_rechazado(self, client, escenario):
        login_en_empresa(client, crear_usuario(), escenario['emp_b'])
        resp = client.post(
            '/api/v1/personal/roster/bulk_create/',
            {'registros': [{
                'personal': escenario['pers_a'].pk,
                'fecha': '2026-06-01',
                'codigo': 'D',
            }]},
            content_type='application/json',
        )
        assert resp.status_code == 403
        assert not Roster.objects.filter(personal=escenario['pers_a']).exists()
