"""Aislamiento multi-empresa de la API /api/v1/comunicaciones/."""
import pytest

from comunicaciones.models import ComunicadoMasivo, Notificacion
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
    notif_a = Notificacion.objects.create(
        destinatario=pers_a, asunto='Privado A', cuerpo='x')
    notif_b = Notificacion.objects.create(
        destinatario=pers_b, asunto='Privado B', cuerpo='x')
    comunicado = ComunicadoMasivo.objects.create(
        titulo='Anuncio interno', cuerpo='x')
    return locals()


def test_notificaciones_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/comunicaciones/notificaciones/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['notif_a'].pk not in ids
    assert escenario['notif_b'].pk in ids


def test_comunicados_sin_tenancy_deny_para_tenant(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/comunicaciones/comunicados/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_superuser_ve_todo(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    ids = ids_de(client.get('/api/v1/comunicaciones/notificaciones/'))
    assert {escenario['notif_a'].pk, escenario['notif_b'].pk} <= ids
