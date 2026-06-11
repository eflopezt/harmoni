"""Aislamiento multi-empresa de la API /api/v1/evaluaciones/."""
from datetime import date

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from evaluaciones.models import CicloEvaluacion, Evaluacion

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    ciclo = CicloEvaluacion.objects.create(
        nombre='Ciclo 2026', fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2026, 12, 31))
    eval_a = Evaluacion.objects.create(
        ciclo=ciclo, evaluado=pers_a, evaluador=pers_a)
    eval_b = Evaluacion.objects.create(
        ciclo=ciclo, evaluado=pers_b, evaluador=pers_b)
    return locals()


def test_evaluaciones_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/evaluaciones/evaluaciones/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['eval_a'].pk not in ids
    assert escenario['eval_b'].pk in ids


def test_ciclos_sin_tenancy_deny_para_tenant(client, escenario):
    """CicloEvaluacion no tiene ruta a Empresa → deny-by-default."""
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/evaluaciones/ciclos/')
    assert resp.status_code == 200
    assert ids_de(resp) == set()


def test_superuser_ve_todo(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    ids = ids_de(client.get('/api/v1/evaluaciones/evaluaciones/'))
    assert {escenario['eval_a'].pk, escenario['eval_b'].pk} <= ids
    assert escenario['ciclo'].pk in ids_de(
        client.get('/api/v1/evaluaciones/ciclos/'))
