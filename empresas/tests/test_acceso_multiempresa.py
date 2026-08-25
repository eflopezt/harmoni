"""Regresiones de autorizacion del selector y middleware multiempresa."""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.acceso import empresas_accesibles
from empresas.models import Empresa

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre, creador=None):
    return Empresa.objects.create(
        ruc=ruc, razon_social=nombre, activa=True, creado_por=creador,
    )


def test_tenant_solo_lista_sus_empresas(client):
    owner = User.objects.create_user('owner_scope', password='pw12345', is_staff=True)
    otra_owner = User.objects.create_user('other_scope', password='pw12345', is_staff=True)
    propia = _empresa('20111111111', 'Empresa propia', owner)
    _empresa('20222222222', 'Empresa ajena', otra_owner)

    assert list(empresas_accesibles(owner)) == [propia]


def test_selector_no_permite_empresa_ajena(client):
    owner = User.objects.create_user('owner_select', password='pw12345', is_staff=True)
    otra_owner = User.objects.create_user('other_select', password='pw12345', is_staff=True)
    propia = _empresa('20333333333', 'Empresa propia', owner)
    ajena = _empresa('20444444444', 'Empresa ajena', otra_owner)
    client.force_login(owner)

    response = client.post(reverse('empresa_seleccionar'), {
        'empresa_id': ajena.pk, 'next': '/',
    })

    assert response.status_code == 302
    assert client.session.get('empresa_actual_id') != ajena.pk
    assert client.session.get('empresa_actual_id') in (None, propia.pk)


def test_tenant_no_activa_consolidado(client):
    owner = User.objects.create_user('owner_all', password='pw12345', is_staff=True)
    propia = _empresa('20555555555', 'Empresa propia', owner)
    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session.save()

    client.post(reverse('empresa_seleccionar'), {'empresa_id': 'all', 'next': '/'})

    assert client.session.get('modo_consolidado') is not True
    assert client.session.get('empresa_actual_id') == propia.pk


def test_middleware_descarta_empresa_forjada(client):
    owner = User.objects.create_user('owner_forged', password='pw12345', is_staff=True)
    otra_owner = User.objects.create_user('other_forged', password='pw12345', is_staff=True)
    propia = _empresa('20666666666', 'Empresa propia', owner)
    ajena = _empresa('20777777777', 'Empresa ajena', otra_owner)
    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = ajena.pk
    session.save()

    response = client.get('/')

    assert response.status_code == 200
    assert response.wsgi_request.empresa_actual == propia
    assert client.session.get('empresa_actual_id') == propia.pk


def test_superuser_conserva_vista_consolidada(client):
    admin = User.objects.create_superuser('platform_scope', 'p@test.pe', 'pw12345')
    _empresa('20888888888', 'Empresa uno')
    _empresa('20999999998', 'Empresa dos')
    client.force_login(admin)

    client.post(reverse('empresa_seleccionar'), {'empresa_id': 'all', 'next': '/'})
    response = client.get('/')

    assert response.wsgi_request.modo_consolidado is True
    assert response.wsgi_request.empresa_actual is None
