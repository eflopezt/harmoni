"""El inicio respeta el RUC seleccionado y muestra una acción operativa real."""
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
        creado_por=owner,
        ruc=ruc,
        razon_social=nombre,
        direccion='Av. Prueba 123',
        representante_legal='ANA PRUEBA',
        nro_doc_representante='12345678',
        activa=True,
    )


def _persona(empresa, documento, nombre):
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=documento,
        apellidos_nombres=nombre,
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        fecha_alta=date(2025, 1, 1),
        sueldo_base=Decimal('2500.00'),
    )


def test_home_usa_solo_empresa_seleccionada(client):
    admin = User.objects.create_superuser('admin_home_scope', password='pw12345')
    propia = _empresa(admin, '20123456771', 'Empresa visible')
    ajena = _empresa(admin, '20123456772', 'Empresa fuera de alcance')
    _persona(propia, '71000101', 'PERSONA VISIBLE')
    _persona(ajena, '71000102', 'PERSONA OCULTA')
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session['modo_consolidado'] = False
    session.save()

    response = client.get(reverse('home'))

    assert response.status_code == 200
    assert response.context['total_personal'] == 1
    assert response.context['process_journey']['total_workers'] == 1
    assert 'Siguiente acción' in response.content.decode()


def test_admin_staff_sin_ficha_personal_ve_la_empresa_que_creo(client):
    owner = User.objects.create_user(
        'owner_home_scope', password='pw12345', is_staff=True,
    )
    empresa = _empresa(owner, '20123456773', 'Empresa del administrador')
    _persona(empresa, '71000103', 'PERSONA DEL RUC')
    client.force_login(owner)

    response = client.get(reverse('home'))

    assert response.status_code == 200
    assert response.context['total_personal'] == 1
