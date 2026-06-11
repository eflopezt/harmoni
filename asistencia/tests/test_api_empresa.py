"""Aislamiento multi-empresa de la API /api/v1/asistencia/."""
from datetime import date

import pytest

from asistencia.models import BancoHoras, RegistroTareo, TareoImportacion
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
    imp = TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 5, 22),
        periodo_fin=date(2026, 6, 21),
    )
    tareo_a = RegistroTareo.objects.create(
        importacion=imp, personal=pers_a, dni=pers_a.nro_doc,
        grupo='STAFF', fecha=date(2026, 6, 1))
    tareo_b = RegistroTareo.objects.create(
        importacion=imp, personal=pers_b, dni=pers_b.nro_doc,
        grupo='STAFF', fecha=date(2026, 6, 1))
    banco_a = BancoHoras.objects.create(
        personal=pers_a, periodo_anio=2026, periodo_mes=5)
    return locals()


def test_tareos_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/asistencia/tareos/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['tareo_a'].pk not in ids
    assert escenario['tareo_b'].pk in ids


def test_banco_horas_de_a_invisible_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/asistencia/banco-horas/')
    assert resp.status_code == 200
    assert escenario['banco_a'].pk not in ids_de(resp)


def test_superuser_ve_todo(client, escenario):
    login_en_empresa(client, crear_usuario(superuser=True), escenario['emp_b'])
    ids = ids_de(client.get('/api/v1/asistencia/tareos/'))
    assert {escenario['tareo_a'].pk, escenario['tareo_b'].pk} <= ids
