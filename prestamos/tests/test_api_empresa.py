"""Aislamiento multi-empresa de la API /api/v1/prestamos/."""
from datetime import date
from decimal import Decimal

import pytest

from core.tests.helpers_api_empresa import (
    crear_empresa, crear_personal, crear_usuario, ids_de, login_en_empresa,
)
from prestamos.models import CuotaPrestamo, Prestamo, TipoPrestamo

pytestmark = pytest.mark.django_db


@pytest.fixture
def escenario():
    emp_a = crear_empresa('Empresa A')
    emp_b = crear_empresa('Empresa B')
    pers_a = crear_personal(emp_a)
    pers_b = crear_personal(emp_b)
    tipo = TipoPrestamo.objects.create(nombre='Préstamo Test', codigo='prestamo-test')
    prestamo_a = Prestamo.objects.create(
        personal=pers_a, tipo=tipo, monto_solicitado=Decimal('1000'),
        num_cuotas=2)
    prestamo_b = Prestamo.objects.create(
        personal=pers_b, tipo=tipo, monto_solicitado=Decimal('2000'),
        num_cuotas=2)
    cuota_a = CuotaPrestamo.objects.create(
        prestamo=prestamo_a, numero=1, periodo=date(2026, 7, 1),
        monto=Decimal('500'))
    return locals()


def test_prestamos_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/prestamos/prestamos/')
    assert resp.status_code == 200
    ids = ids_de(resp)
    assert escenario['prestamo_a'].pk not in ids
    assert escenario['prestamo_b'].pk in ids


def test_cuotas_de_a_invisibles_para_b(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/prestamos/cuotas/')
    assert resp.status_code == 200
    assert escenario['cuota_a'].pk not in ids_de(resp)


def test_tipos_son_catalogo_compartido(client, escenario):
    login_en_empresa(client, crear_usuario(), escenario['emp_b'])
    resp = client.get('/api/v1/prestamos/tipos/')
    assert resp.status_code == 200
    assert escenario['tipo'].pk in ids_de(resp)
