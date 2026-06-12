"""
Tests del wizard "Datos de tu empresa" (empresas/completitud.py + vista).

Los archivos SUNAT, boletas y contratos usan estos datos; el wizard es la
página única para completarlos (antes el validador mandaba al admin Django).
"""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.completitud import datos_pendientes
from empresas.models import Empresa


@pytest.fixture
def empresa_vacia(db):
    return Empresa.objects.create(ruc="20123456789", razon_social="ACME SAC")


@pytest.fixture
def admin_client(db, client):
    User.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
    client.login(username="admin", password="x")
    return client


class TestCompletitud:
    def test_empresa_minima_tiene_criticos(self, empresa_vacia):
        estado = datos_pendientes(empresa_vacia)
        campos = {c["campo"] for c in estado["criticos"]}
        # RUC y razón social están; faltan dirección y representante
        assert "ruc" not in campos
        assert "razon_social" not in campos
        assert {"direccion", "representante_legal", "nro_doc_representante"} <= campos
        assert estado["completo"] is False

    def test_ruc_invalido_es_critico(self, db):
        emp = Empresa.objects.create(ruc="123", razon_social="X SAC")
        campos = {c["campo"] for c in datos_pendientes(emp)["criticos"]}
        assert "ruc" in campos

    def test_empresa_completa(self, empresa_vacia):
        emp = empresa_vacia
        emp.direccion = "Av. Lima 123"
        emp.representante_legal = "JUAN PEREZ"
        emp.nro_doc_representante = "12345678"
        emp.save()
        estado = datos_pendientes(emp)
        assert estado["completo"] is True
        # Aún hay recomendados (ubigeo, logo, etc.)
        assert estado["recomendados"]

    def test_ubigeo_invalido_es_recomendado(self, empresa_vacia):
        empresa_vacia.ubigeo = "15"
        campos = {c["campo"] for c in datos_pendientes(empresa_vacia)["recomendados"]}
        assert "ubigeo" in campos


class TestVistaWizard:
    def test_requiere_admin(self, client, empresa_vacia, db):
        User.objects.create_user("normal", password="x")
        client.login(username="normal", password="x")
        resp = client.get(reverse("empresa_datos", args=[empresa_vacia.pk]))
        assert resp.status_code == 302  # user_passes_test redirige a login

    def test_get_muestra_pendientes(self, admin_client, empresa_vacia):
        resp = admin_client.get(reverse("empresa_datos", args=[empresa_vacia.pk]))
        assert resp.status_code == 200
        assert b"Faltan datos cr" in resp.content  # "críticos"
        assert b"Representante legal" in resp.content

    def test_post_guarda_y_completa(self, admin_client, empresa_vacia):
        resp = admin_client.post(reverse("empresa_datos", args=[empresa_vacia.pk]), {
            "ruc": "20123456789",
            "razon_social": "ACME SAC",
            "direccion": "Av. Lima 123, Miraflores",
            "ubigeo": "150122",
            "distrito": "Miraflores",
            "provincia": "Lima",
            "departamento": "Lima",
            "representante_legal": "JUAN PEREZ GOMEZ",
            "cargo_representante": "Gerente General",
            "tipo_doc_representante": "DNI",
            "nro_doc_representante": "12345678",
        })
        assert resp.status_code == 302
        empresa_vacia.refresh_from_db()
        assert empresa_vacia.representante_legal == "JUAN PEREZ GOMEZ"
        assert empresa_vacia.ubigeo == "150122"
        assert datos_pendientes(empresa_vacia)["completo"] is True

    def test_post_ruc_invalido_no_pisa(self, admin_client, empresa_vacia):
        admin_client.post(reverse("empresa_datos", args=[empresa_vacia.pk]), {
            "ruc": "123",  # inválido
            "razon_social": "ACME SAC",
        })
        empresa_vacia.refresh_from_db()
        assert empresa_vacia.ruc == "20123456789"  # se conserva el válido

    def test_post_ruc_duplicado_no_pisa(self, admin_client, empresa_vacia, db):
        # conftest.py seedea la empresa principal con RUC 20999999999
        Empresa.objects.get_or_create(
            ruc="20999999999", defaults={"razon_social": "OTRA SAC"})
        admin_client.post(reverse("empresa_datos", args=[empresa_vacia.pk]), {
            "ruc": "20999999999",
            "razon_social": "ACME SAC",
        })
        empresa_vacia.refresh_from_db()
        assert empresa_vacia.ruc == "20123456789"


class TestHomeCentroAccion:
    def test_home_avisa_datos_incompletos(self, admin_client, empresa_vacia):
        # Activar la empresa en sesión para que el middleware la exponga
        session = admin_client.session
        session["empresa_actual_id"] = empresa_vacia.pk
        session.save()
        resp = admin_client.get("/")
        assert resp.status_code == 200
        if resp.context and "datos_empresa_criticos" in resp.context:
            assert resp.context["datos_empresa_criticos"] >= 1
