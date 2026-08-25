"""El asistente RR. HH. exige rol operativo y respeta el RUC activo."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(owner, ruc, nombre):
    return Empresa.objects.create(
        creado_por=owner, ruc=ruc, razon_social=nombre, activa=True,
    )


def _persona(empresa, documento):
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=documento,
        apellidos_nombres=f'PERSONA {documento}',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        fecha_alta=date(2025, 1, 1),
        sueldo_base=Decimal('2500.00'),
    )


def test_hr_ask_headcount_usa_empresa_seleccionada(client):
    admin = User.objects.create_superuser('admin_hr_ask', password='pw12345')
    propia = _empresa(admin, '20123456751', 'Empresa consultada')
    ajena = _empresa(admin, '20123456752', 'Empresa no consultada')
    _persona(propia, '71000301')
    _persona(ajena, '71000302')
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session['modo_consolidado'] = False
    session.save()

    response = client.get(reverse('hr_ask'), {'q': 'cuantos empleados hay'})

    assert response.status_code == 200
    assert response.json()['datos']['total'] == 1


def test_hr_ask_rechaza_trabajador_sin_rol_operativo(client):
    worker = User.objects.create_user('worker_hr_ask', password='pw12345')
    client.force_login(worker)

    response = client.get(reverse('hr_ask'), {'q': 'cuantos empleados hay'})

    assert response.status_code == 302
