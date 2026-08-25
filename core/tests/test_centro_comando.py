"""Centro de Comando: permisos, alcance y datos verificables."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre, owner):
    return Empresa.objects.create(
        ruc=ruc,
        razon_social=nombre,
        direccion='Av. Prueba 123',
        representante_legal='ANA PRUEBA',
        nro_doc_representante='12345678',
        activa=True,
        creado_por=owner,
    )


def _personal(empresa, doc, nombre, sueldo):
    return Personal.objects.create(
        empresa=empresa, nro_doc=doc, apellidos_nombres=nombre,
        cargo='Analista', tipo_trab='Empleado', estado='Activo',
        fecha_alta=date(2025, 1, 1), sueldo_base=Decimal(sueldo),
    )


def test_usuario_regular_no_accede(client):
    user = User.objects.create_user('worker_cmd', password='pw12345')
    client.force_login(user)
    response = client.get(reverse('centro_comando'))
    assert response.status_code == 302


def test_staff_ve_solo_su_empresa(client):
    owner = User.objects.create_user('manager_cmd', password='pw12345', is_staff=True)
    other = User.objects.create_user('other_cmd', password='pw12345', is_staff=True)
    propia = _empresa('20123456781', 'Operacion autorizada', owner)
    ajena = _empresa('20123456782', 'Operacion confidencial', other)
    _personal(propia, '71000001', 'PERSONA AUTORIZADA', '2500.00')
    _personal(ajena, '71000002', 'PERSONA CONFIDENCIAL', '9000.00')
    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session.save()

    response = client.get(reverse('centro_comando'))

    assert response.status_code == 200
    assert response.context['total_workers'] == 1
    assert response.context['base_salarial'] == Decimal('2500.00')
    content = response.content.decode()
    assert 'Operacion autorizada' in content
    assert 'Operacion confidencial' not in content
    assert 'salud por local' not in content.lower()
    assert 'cmd-local-score' not in content.lower()


def test_centro_expone_seis_etapas(client):
    admin = User.objects.create_superuser('admin_cmd', 'admin@cmd.pe', 'pw12345')
    _empresa('20123456783', 'Empresa de prueba', admin)
    client.force_login(admin)
    session = client.session
    session['modo_consolidado'] = True
    session.save()

    response = client.get(reverse('centro_comando'))

    assert response.status_code == 200
    assert [stage['key'] for stage in response.context['stages']] == [
        'setup', 'recruitment', 'onboarding', 'operations', 'payroll', 'offboarding',
    ]
