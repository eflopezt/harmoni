"""
Smoke tests básicos para las vistas de personal.

Cubre:
- personal_list: 200 para admin
- personal_detail: 200 para admin
- personal_detail: 404 si user no-admin intenta ver datos de otro
- personal_detail: 200 cuando un user normal accede a su propio Personal
- búsqueda con strings raros (SQL injection-safe)

Las vistas de personal usan filtrar_personal(user), que:
- superuser → ve TODO
- user con Personal vinculado → ve SOLO su propio registro
- responsable de área → ve su área completa
- nadie más → queryset vacío → 404
"""
from __future__ import annotations

from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from personal.models import Area, Personal, SubArea


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Operaciones")


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def admin(db):
    """Superuser — pasa todos los filtros y middleware billing."""
    return User.objects.create_superuser(
        username="adminer", password="adminpass", email="admin@ex.com"
    )


@pytest.fixture
def user_normal(db):
    # is_staff=True para bypass de WorkerAccessRestrictionMiddleware (no es worker puro)
    # is_superuser=False para que filtrar_personal aplique restricciones por Personal vinculado.
    return User.objects.create_user(
        username="normal", password="testpass123", is_staff=True,
    )


@pytest.fixture
def personal_admin_target(subarea):
    """Personal sin user vinculado — solo accesible vía admin."""
    return Personal.objects.create(
        nro_doc="81111111",
        apellidos_nombres="ADMIN TARGET, JUAN",
        cargo="Operario",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
    )


@pytest.fixture
def personal_propio(user_normal, subarea):
    """Personal vinculado al user_normal."""
    return Personal.objects.create(
        usuario=user_normal,
        nro_doc="82222222",
        apellidos_nombres="USER NORMAL, MARIA",
        cargo="Asistente",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 6, 1),
    )


@pytest.fixture
def client_admin(admin):
    c = Client()
    c.force_login(admin)
    return c


@pytest.fixture
def client_normal(user_normal):
    c = Client()
    c.force_login(user_normal)
    return c


# ═════════════════════════════════════════════════════════════════════════════
# personal_list
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPersonalList:

    def test_admin_ve_listado_200(
        self, client_admin, personal_admin_target, personal_propio
    ):
        url = reverse("personal_list")
        resp = client_admin.get(url)
        assert resp.status_code == 200

    def test_busqueda_con_string_normal(
        self, client_admin, personal_admin_target
    ):
        url = reverse("personal_list") + "?buscar=ADMIN"
        resp = client_admin.get(url)
        assert resp.status_code == 200

    def test_busqueda_sql_injection_safe(self, client_admin, personal_admin_target):
        """El payload SQL injection clásico NO rompe la vista (Django ORM
        parametriza todas las queries)."""
        payload = "'; DROP TABLE personal_personal; --"
        url = reverse("personal_list") + f"?buscar={payload}"
        resp = client_admin.get(url)
        assert resp.status_code == 200
        # La tabla NO fue dropeada
        assert Personal.objects.filter(pk=personal_admin_target.pk).exists()

    def test_busqueda_con_unicode_no_rompe(self, client_admin):
        """Caracteres especiales unicode/emoji no rompen la vista."""
        url = reverse("personal_list") + "?buscar=ñoño%20çñ"
        resp = client_admin.get(url)
        assert resp.status_code == 200

    def test_lista_requiere_login(self, db):
        url = reverse("personal_list")
        resp = Client().get(url)
        assert resp.status_code == 302  # redirect al login


# ═════════════════════════════════════════════════════════════════════════════
# personal_detail
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPersonalDetail:

    def test_admin_ve_detalle_200(self, client_admin, personal_admin_target):
        url = reverse("personal_detail", args=[personal_admin_target.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 200

    def test_user_normal_no_ve_detalle_de_otro(
        self, client_normal, personal_admin_target, personal_propio
    ):
        """User normal NO puede acceder al Personal de otro (404 por filtro)."""
        url = reverse("personal_detail", args=[personal_admin_target.pk])
        resp = client_normal.get(url)
        # filtrar_personal devuelve queryset que no incluye al otro → 404
        assert resp.status_code == 404

    def test_user_normal_ve_su_propio_detalle(
        self, client_normal, personal_propio
    ):
        """User normal SÍ puede ver su propio Personal."""
        url = reverse("personal_detail", args=[personal_propio.pk])
        resp = client_normal.get(url)
        assert resp.status_code == 200

    def test_detalle_404_si_pk_inexistente(self, client_admin):
        url = reverse("personal_detail", args=[999999])
        resp = client_admin.get(url)
        assert resp.status_code == 404
