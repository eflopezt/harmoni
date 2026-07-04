"""
RBAC central (WS1): helpers de core/permisos.py + matriz de roles sobre una
vista real de reclutamiento (el módulo piloto).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import AnonymousUser, User

from core.models import PerfilAcceso
from core.permisos import (
    perfil_de, puede_aprobar, tiene_modulo,
)
from personal.models import Personal


def _perfil(codigo, **mods):
    base = {'nombre': codigo.title(), 'codigo': codigo, 'es_sistema': False}
    base.update(mods)
    return PerfilAcceso.objects.create(**base)


def _usuario_con_perfil(username, perfil, is_staff=True):
    user = User.objects.create_user(username, f'{username}@t.pe', 'x',
                                    is_staff=is_staff)
    Personal.objects.create(
        nro_doc=str(abs(hash(username)) % 90000000 + 10000000),
        apellidos_nombres=f'{username.upper()}, TEST',
        cargo='Analista', tipo_trab='Empleado', estado='Activo',
        fecha_alta=date(2024, 1, 1), sueldo_base=Decimal('2500'),
        usuario=user, perfil_acceso=perfil,
    )
    return user


# ── helpers unitarios ───────────────────────────────────────────────────────

@pytest.mark.django_db
def test_superuser_tiene_todos_los_modulos():
    su = User.objects.create_superuser('root.rbac', 'r@t.pe', 'x')
    assert tiene_modulo(su, 'reclutamiento') is True
    assert tiene_modulo(su, 'salarios') is True
    assert puede_aprobar(su) is True


@pytest.mark.django_db
def test_staff_con_modulo_activo():
    perfil = _perfil('RECLUTADOR', mod_reclutamiento=True)
    user = _usuario_con_perfil('recluta1', perfil)
    assert tiene_modulo(user, 'reclutamiento') is True
    # Un módulo que su perfil NO tiene
    assert tiene_modulo(user, 'salarios') is False


@pytest.mark.django_db
def test_staff_sin_el_modulo_no_pasa():
    perfil = _perfil('EMPLEADO_X', mod_reclutamiento=False)
    user = _usuario_con_perfil('emple1', perfil)
    assert tiene_modulo(user, 'reclutamiento') is False


@pytest.mark.django_db
def test_no_staff_no_pasa_aunque_tenga_modulo():
    """Sin is_staff no accede a gestión aunque el perfil marque el módulo."""
    perfil = _perfil('RARO', mod_reclutamiento=True)
    user = _usuario_con_perfil('nostaff1', perfil, is_staff=False)
    assert tiene_modulo(user, 'reclutamiento') is False


@pytest.mark.django_db
def test_usuario_sin_personal_ni_perfil():
    user = User.objects.create_user('suelto', 's@t.pe', 'x', is_staff=True)
    assert perfil_de(user) is None
    assert tiene_modulo(user, 'reclutamiento') is False


def test_anonimo_no_pasa():
    anon = AnonymousUser()
    assert tiene_modulo(anon, 'reclutamiento') is False
    assert puede_aprobar(anon) is False


@pytest.mark.django_db
def test_puede_aprobar_flag():
    perfil = _perfil('APROBADOR', mod_vacaciones=True, puede_aprobar=True)
    user = _usuario_con_perfil('aprob1', perfil)
    assert puede_aprobar(user) is True
    perfil2 = _perfil('NOAPRUEBA', mod_vacaciones=True, puede_aprobar=False)
    user2 = _usuario_con_perfil('noaprob1', perfil2)
    assert puede_aprobar(user2) is False


# ── asignar perfil sincroniza is_staff (para que el RBAC funcione) ──────────

@pytest.mark.django_db
def test_asignar_perfil_marca_is_staff(client):
    """Asignar un PerfilAcceso desde la UI debe marcar is_staff en el usuario
    vinculado; quitarlo lo desmarca. Sin esto, requiere_modulo bloquearía a
    los RECLUTADOR creados por la UI."""
    from django.urls import reverse

    _perfil('RECLUTADOR', mod_reclutamiento=True)
    # target: usuario vinculado, aún sin perfil ni staff
    target = User.objects.create_user('target.staff', 't2@t.pe', 'x',
                                      is_staff=False)
    personal = Personal.objects.create(
        nro_doc='60000001', apellidos_nombres='TARGET, STAFF',
        cargo='Analista', tipo_trab='Empleado', estado='Activo',
        fecha_alta=date(2024, 1, 1), sueldo_base=Decimal('2500'),
        usuario=target,
    )

    # requester: superuser (puede gestionar accesos)
    User.objects.create_superuser('root.asig', 'ra@t.pe', 'x')
    client.login(username='root.asig', password='x')

    # Asignar RECLUTADOR
    resp = client.post(reverse('accesos_asignar_perfil'),
                       {'personal_id': personal.pk, 'perfil_codigo': 'RECLUTADOR'})
    assert resp.status_code == 200 and resp.json()['success'] is True
    target.refresh_from_db()
    assert target.is_staff is True
    assert tiene_modulo(target, 'reclutamiento') is True

    # Quitar perfil → deja de ser staff
    resp = client.post(reverse('accesos_asignar_perfil'),
                       {'personal_id': personal.pk, 'perfil_codigo': ''})
    assert resp.status_code == 200
    target.refresh_from_db()
    assert target.is_staff is False


@pytest.mark.django_db
def test_asignar_perfil_no_degrada_superuser(client):
    """Un superuser vinculado nunca pierde is_staff al quitarle el perfil."""
    from django.urls import reverse
    su = User.objects.create_superuser('su.link', 'sl@t.pe', 'x')
    personal = Personal.objects.create(
        nro_doc='60000002', apellidos_nombres='SUPER, LINK',
        cargo='Gerente', tipo_trab='Empleado', estado='Activo',
        fecha_alta=date(2024, 1, 1), sueldo_base=Decimal('9000'),
        usuario=su,
    )
    User.objects.create_superuser('root.asig2', 'ra2@t.pe', 'x')
    client.login(username='root.asig2', password='x')
    client.post(reverse('accesos_asignar_perfil'),
                {'personal_id': personal.pk, 'perfil_codigo': ''})
    su.refresh_from_db()
    assert su.is_staff is True   # intacto


# ── integración sobre una vista real de reclutamiento ───────────────────────

@pytest.mark.django_db
def test_vista_reclutamiento_matriz_roles(client):
    """La misma vista: superuser y RECLUTADOR entran (200); EMPLEADO y
    anónimo son redirigidos al login (302)."""
    from django.urls import reverse
    url = reverse('vacantes_panel')   # @solo_admin → ahora requiere_modulo

    # anónimo → redirect a login
    assert client.get(url).status_code == 302

    # superuser → 200
    User.objects.create_superuser('root.v', 'rv@t.pe', 'x')
    client.login(username='root.v', password='x')
    assert client.get(url).status_code == 200
    client.logout()

    # RECLUTADOR → 200
    perfil_r = _perfil('RECLUTADOR', mod_reclutamiento=True)
    _usuario_con_perfil('recluta2', perfil_r)
    client.login(username='recluta2', password='x')
    assert client.get(url).status_code == 200
    client.logout()

    # EMPLEADO (sin mod_reclutamiento) → redirect
    perfil_e = _perfil('EMPLEADO_Y', mod_reclutamiento=False)
    _usuario_con_perfil('emple2', perfil_e)
    client.login(username='emple2', password='x')
    assert client.get(url).status_code == 302
