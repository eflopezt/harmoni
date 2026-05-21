"""
Tests para Onboarding Express del trabajador.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from personal.models import Area, Personal, SubArea


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin_exp", password="x", email="a@a.com")


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def empresa(db):
    return Empresa.objects.create(
        ruc="20100099900", razon_social="Test Express S.A.C.",
        nombre_comercial="Test Express", subdominio="test-exp",
        activa=True,
    )


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Salón")
    return SubArea.objects.create(nombre="Servicio", area=area, activa=True)


class TestOnboardingExpress:
    def test_render_form(self, client_admin, empresa):
        resp = client_admin.get(reverse("personal_create_express"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Onboarding Express" in body
        assert "45 segundos" in body
        assert empresa.nombre_comercial in body

    def test_crear_trabajador_completo(self, client_admin, empresa, subarea):
        resp = client_admin.post(reverse("personal_create_express"), {
            "nro_doc":           "71999888",
            "apellidos_nombres": "TEST QUISPE, MARIA",
            "cargo":             "Mesera",
            "tipo_trab":         "Empleado",
            "grupo_tareo":       "STAFF",
            "empresa_id":        empresa.pk,
            "subarea_id":        subarea.pk,
            "sueldo_base":       "1800",
            "fecha_alta":        date.today().isoformat(),
            "email":             "maria.test@empresa.com",
            "tipo_contrato":     "plazo_fijo",
            "regimen_pension":   "ONP",
            "password_inicial":  "demo123test",
        })
        # Redirect a exito
        assert resp.status_code == 302
        # Personal creado
        p = Personal.objects.get(nro_doc="71999888")
        assert p.apellidos_nombres == "TEST QUISPE, MARIA"
        assert p.empresa == empresa
        assert p.subarea == subarea
        assert p.cargo == "Mesera"
        assert p.estado == "Activo"
        # Usuario creado y vinculado
        assert p.usuario is not None
        assert p.usuario.username == "71999888"
        assert p.usuario.check_password("demo123test")
        assert p.usuario.is_active
        # Saldo apertura creado
        from nominas.models import SaldoAperturaTrabajador
        assert SaldoAperturaTrabajador.objects.filter(personal=p).exists()

    def test_crear_dni_duplicado_falla(self, client_admin, empresa):
        Personal.objects.create(
            nro_doc="71999888", apellidos_nombres="EXISTENTE, TEST",
            cargo="x", estado="Activo", empresa=empresa,
        )
        resp = client_admin.post(reverse("personal_create_express"), {
            "nro_doc":           "71999888",
            "apellidos_nombres": "TEST QUISPE, MARIA",
            "cargo":             "Mesera",
            "empresa_id":        empresa.pk,
        })
        # No crea nuevo trabajador
        assert Personal.objects.filter(nro_doc="71999888").count() == 1

    def test_password_autogenerado(self, client_admin, empresa):
        resp = client_admin.post(reverse("personal_create_express"), {
            "nro_doc":           "71999887",
            "apellidos_nombres": "AUTO PASS, TEST",
            "cargo":             "Cocinero",
            "empresa_id":        empresa.pk,
            # sin password_inicial → debe autogenerarse
        })
        assert resp.status_code == 302
        p = Personal.objects.get(nro_doc="71999887")
        # User existe y tiene password no vacío
        assert p.usuario is not None
        # No es la contraseña "vacía" (set_password con '' genera un hash igual)
        from django.contrib.auth.hashers import check_password
        assert not check_password('', p.usuario.password)

    def test_pantalla_exito(self, client_admin, empresa):
        p = Personal.objects.create(
            nro_doc="71999886", apellidos_nombres="EXITO, TEST",
            cargo="x", estado="Activo", empresa=empresa,
        )
        resp = client_admin.get(
            reverse("personal_express_exito", args=[p.pk])
        )
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "EXITO, TEST" in body
        assert "contratado" in body.lower()

    def test_permisos_no_login(self, client):
        resp = client.get(reverse("personal_create_express"))
        # @login_required → redirige a login
        assert resp.status_code == 302
        assert "/login" in resp["Location"]
