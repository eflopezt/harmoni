"""Centro de Saneamiento: alcance, colas y acciones verificables."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre, owner, *, completa=True):
    kwargs = {
        'ruc': ruc,
        'razon_social': nombre,
        'activa': True,
        'creado_por': owner,
    }
    if completa:
        kwargs.update({
            'direccion': 'Av. Operacion 123',
            'representante_legal': 'ANA PRUEBA',
            'nro_doc_representante': '12345678',
        })
    return Empresa.objects.create(**kwargs)


def _personal(empresa, doc, nombre, *, estado='Activo', sueldo=None):
    kwargs = {
        'empresa': empresa,
        'nro_doc': doc,
        'apellidos_nombres': nombre,
        'cargo': 'Analista',
        'tipo_trab': 'Empleado',
        'estado': estado,
        'fecha_alta': date(2025, 1, 1),
        'sueldo_base': sueldo,
    }
    if estado == 'Cesado':
        kwargs.update({
            'fecha_cese': date(2026, 6, 30),
            'motivo_cese': 'RENUNCIA',
        })
    return Personal.objects.create(**kwargs)


def test_staff_solo_ve_la_empresa_autorizada(client):
    owner = User.objects.create_user('quality_owner', password='pw', is_staff=True)
    other = User.objects.create_user('quality_other', password='pw', is_staff=True)
    propia = _empresa('20111111111', 'Empresa autorizada', owner, completa=False)
    ajena = _empresa('20222222222', 'Empresa confidencial', other, completa=False)
    _personal(propia, '71001001', 'PERSONA AUTORIZADA', sueldo=None)
    _personal(ajena, '71001002', 'PERSONA CONFIDENCIAL', sueldo=None)
    _personal(propia, '71001003', 'CESE AUTORIZADO', estado='Cesado', sueldo=Decimal('2500'))
    _personal(ajena, '71001004', 'CESE CONFIDENCIAL', estado='Cesado', sueldo=Decimal('2600'))

    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session.save()
    response = client.get(reverse('data_quality_center'))

    assert response.status_code == 200
    assert response.context['legajo_total'] == 1
    assert response.context['liquidacion_total'] == 1
    content = response.content.decode()
    assert 'Empresa autorizada' in content
    assert 'PERSONA AUTORIZADA' in content
    assert 'Empresa confidencial' not in content
    assert 'PERSONA CONFIDENCIAL' not in content
    assert 'Registros historicos sin empresa' not in content


def test_superuser_consolidado_ve_cola_huerfanos(client):
    admin = User.objects.create_superuser('quality_admin', 'q@harmoni.pe', 'pw')
    _empresa('20333333333', 'Empresa consolidada', admin)
    _personal(None, '71001005', 'PERSONA SIN EMPRESA', sueldo=None)

    client.force_login(admin)
    session = client.session
    session['modo_consolidado'] = True
    session.save()
    response = client.get(reverse('data_quality_center') + '?cola=huerfanos')

    assert response.status_code == 200
    assert response.context['orphan_total'] == 1
    assert response.context['orphan_active'] == 1
    assert 'PERSONA SIN EMPRESA' in response.content.decode()


def test_legajo_muestra_causas_y_accion_directa(client):
    admin = User.objects.create_superuser('quality_action', 'a@harmoni.pe', 'pw')
    empresa = _empresa('20444444444', 'Empresa de accion', admin)
    personal = Personal.objects.create(
        empresa=empresa,
        nro_doc='71001006',
        apellidos_nombres='LEGAJO INCOMPLETO',
        cargo='',
        tipo_trab='',
        estado='Activo',
        fecha_alta=None,
        sueldo_base=Decimal('0'),
    )
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = empresa.pk
    session.save()

    response = client.get(reverse('data_quality_center') + '?cola=legajos')
    row = response.context['legajo_rows'][0]

    assert {item['campo'] for item in row['incidencias']} == {
        'fecha_alta', 'sueldo_base', 'cargo', 'tipo_trab',
    }
    assert row['url'] == reverse('personal_update', args=[personal.pk])
    assert response.context['legajo_critical'] == 1


def test_usuario_regular_no_accede(client):
    user = User.objects.create_user('quality_worker', password='pw')
    client.force_login(user)
    response = client.get(reverse('data_quality_center'))
    assert response.status_code == 302


def test_recorrido_dirige_bloqueos_al_saneamiento(client):
    admin = User.objects.create_superuser('quality_journey', 'j@harmoni.pe', 'pw')
    empresa = _empresa('20555555555', 'Empresa recorrido', admin)
    _personal(empresa, '71001007', 'SUELDO PENDIENTE', sueldo=None)
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = empresa.pk
    session.save()

    response = client.get(reverse('centro_comando'))

    setup = next(stage for stage in response.context['stages'] if stage['key'] == 'setup')
    assert setup['action_url'] == reverse('data_quality_center')
    assert any(
        issue['url'].endswith('?cola=legajos')
        for issue in response.context['issues']
        if issue['stage'] == 'Preparacion'
    )
