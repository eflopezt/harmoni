"""
Landing por rol (rec. 16): cada usuario elige su pantalla de inicio en
Preferencias; el home redirige allí, con /?landing=home como escape.
"""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from core.models import PreferenciaUsuario


@pytest.fixture
def superuser(db):
    return User.objects.create_superuser('root.landing', 'r@test.pe', 'x')


def test_sin_preferencia_muestra_dashboard(client, superuser):
    client.login(username='root.landing', password='x')
    resp = client.get('/')
    assert resp.status_code == 200


def test_landing_preferido_redirige(client, superuser):
    PreferenciaUsuario.objects.create(
        usuario=superuser, landing_default='mi_dia_nominas')
    client.login(username='root.landing', password='x')
    resp = client.get('/')
    assert resp.status_code == 302
    assert resp.url == reverse('mi_dia_nominas')


def test_landing_home_fuerza_dashboard(client, superuser):
    PreferenciaUsuario.objects.create(
        usuario=superuser, landing_default='mi_dia_nominas')
    client.login(username='root.landing', password='x')
    resp = client.get('/?landing=home')
    assert resp.status_code == 200


def test_staff_no_superuser_no_redirige_a_destinos_solo_admin(client, db):
    staff = User.objects.create_user(
        'staff.landing', 's@test.pe', 'x', is_staff=True)
    PreferenciaUsuario.objects.create(
        usuario=staff, landing_default='mi_dia_reclutador')
    client.login(username='staff.landing', password='x')
    resp = client.get('/')
    # El guard bloquea destinos solo-superuser → se queda en el dashboard
    assert resp.status_code == 200


def test_preferencias_guarda_landing(client, superuser):
    client.login(username='root.landing', password='x')
    resp = client.post(reverse('preferencias_usuario'), {
        'tema': 'AUTO', 'idioma': 'es', 'items_por_pagina': '20',
        'landing_default': 'aprobaciones',
    })
    assert resp.status_code in (200, 302)
    pref = PreferenciaUsuario.objects.get(usuario=superuser)
    assert pref.landing_default == 'aprobaciones'


def test_preferencias_rechaza_landing_invalido(client, superuser):
    client.login(username='root.landing', password='x')
    client.post(reverse('preferencias_usuario'), {
        'tema': 'AUTO', 'idioma': 'es', 'items_por_pagina': '20',
        'landing_default': 'javascript:alert(1)',
    })
    pref = PreferenciaUsuario.objects.get(usuario=superuser)
    assert pref.landing_default == 'home'
