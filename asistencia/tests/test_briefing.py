"""
Tests para Briefing del Día — modelo + views + AJAX leído.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from empresas.models import Empresa
from personal.models import Area, Personal, SubArea
from asistencia.models import BriefingServicio, BriefingLectura


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin_brf", password="x", email="a@a.com")


@pytest.fixture
def empresa(db):
    return Empresa.objects.create(
        ruc="20100000999",
        razon_social="Restaurante Test S.A.C.",
        nombre_comercial="Test Resto",
        subdominio="test-resto",
        activa=True,
    )


@pytest.fixture
def worker_user(db):
    return User.objects.create_user(username="71234567", password="demo123")


@pytest.fixture
def worker(db, empresa, worker_user):
    area = Area.objects.create(nombre="Salón")
    sub = SubArea.objects.create(nombre="Servicio", area=area)
    return Personal.objects.create(
        nro_doc="71234567",
        apellidos_nombres="QUISPE TEST, MARIA",
        cargo="Mesera",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=sub,
        empresa=empresa,
        usuario=worker_user,
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("1500.00"),
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


# ─── Modelo ──────────────────────────────────────────────────────────────────

class TestModelo:
    def test_crear_briefing(self, empresa):
        b = BriefingServicio.objects.create(
            empresa=empresa,
            fecha=date.today(),
            servicio="ALMUERZO",
            covers_esperados=50,
            estado="BORRADOR",
        )
        assert b.estado == "BORRADOR"
        assert not b.is_publicado
        assert "ALMUERZO" in str(b) or "Almuerzo" in str(b)

    def test_unique_empresa_fecha_servicio(self, empresa):
        BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
        )
        with pytest.raises(Exception):
            BriefingServicio.objects.create(
                empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
            )

    def test_publicar_setea_timestamp(self, empresa, admin_user):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="CENA",
        )
        assert b.estado == "BORRADOR"
        assert b.publicado_en is None
        b.publicar(admin_user)
        assert b.estado == "PUBLICADO"
        assert b.publicado_en is not None
        assert b.publicado_por == admin_user
        assert b.is_publicado


# ─── Views admin ──────────────────────────────────────────────────────────────

class TestViewsAdmin:
    def test_panel_lista_briefings(self, client_admin, empresa):
        BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
        )
        resp = client_admin.get(reverse("briefing_panel"))
        assert resp.status_code == 200
        assert "Briefing" in resp.content.decode()

    def test_crear_briefing_form(self, client_admin):
        resp = client_admin.get(reverse("briefing_crear"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Nuevo Briefing" in body or "briefing" in body.lower()

    def test_crear_briefing_post_borrador(self, client_admin, empresa):
        resp = client_admin.post(reverse("briefing_crear"), {
            "empresa":          empresa.pk,
            "fecha":            date.today().isoformat(),
            "servicio":         "ALMUERZO",
            "covers_esperados": 30,
            "notas_chef":       "test notes",
            "especiales":       "plato 1",
            "items_86":         "",
            "vips_alergias":    "",
            "dress_code":       "",
            "notas_operativas": "",
            "publicar":         "0",
        })
        # Redirect a detalle
        assert resp.status_code == 302
        b = BriefingServicio.objects.get(empresa=empresa, fecha=date.today(), servicio="ALMUERZO")
        assert b.estado == "BORRADOR"
        assert b.covers_esperados == 30

    def test_crear_briefing_post_publicado(self, client_admin, empresa):
        resp = client_admin.post(reverse("briefing_crear"), {
            "empresa":          empresa.pk,
            "fecha":            date.today().isoformat(),
            "servicio":         "CENA",
            "covers_esperados": 80,
            "publicar":         "1",
        })
        assert resp.status_code == 302
        b = BriefingServicio.objects.get(empresa=empresa, servicio="CENA")
        assert b.estado == "PUBLICADO"
        assert b.publicado_en is not None

    def test_detalle_briefing(self, client_admin, empresa):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="DESAYUNO",
        )
        resp = client_admin.get(reverse("briefing_detalle", args=[b.pk]))
        assert resp.status_code == 200
        assert "Desayuno" in resp.content.decode() or "DESAYUNO" in resp.content.decode()

    def test_publicar_via_post(self, client_admin, empresa):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="CONTINUO",
        )
        resp = client_admin.post(reverse("briefing_detalle", args=[b.pk]), {
            "accion": "publicar",
        })
        assert resp.status_code == 302
        b.refresh_from_db()
        assert b.estado == "PUBLICADO"

    def test_cerrar_via_post(self, client_admin, empresa, admin_user):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
        )
        b.publicar(admin_user)
        resp = client_admin.post(reverse("briefing_detalle", args=[b.pk]), {
            "accion": "cerrar",
        })
        assert resp.status_code == 302
        b.refresh_from_db()
        assert b.estado == "CERRADO"


# ─── AJAX leído ──────────────────────────────────────────────────────────────

class TestAjaxLeido:
    def test_marcar_leido_crea_lectura(self, client, worker, empresa, admin_user):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
        )
        b.publicar(admin_user)

        client.force_login(worker.usuario)
        resp = client.post(reverse("briefing_marcar_leido", args=[b.pk]))
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"]
        assert data["created"]
        assert BriefingLectura.objects.filter(briefing=b, personal=worker).exists()

    def test_marcar_leido_idempotente(self, client, worker, empresa, admin_user):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
        )
        b.publicar(admin_user)
        client.force_login(worker.usuario)
        client.post(reverse("briefing_marcar_leido", args=[b.pk]))
        resp = client.post(reverse("briefing_marcar_leido", args=[b.pk]))
        data = resp.json()
        assert data["ok"]
        assert not data["created"]  # ya existía
        assert BriefingLectura.objects.filter(briefing=b, personal=worker).count() == 1

    def test_no_se_puede_marcar_leido_borrador(self, client, worker, empresa):
        b = BriefingServicio.objects.create(
            empresa=empresa, fecha=date.today(), servicio="ALMUERZO",
            estado="BORRADOR",
        )
        client.force_login(worker.usuario)
        resp = client.post(reverse("briefing_marcar_leido", args=[b.pk]))
        # Solo PUBLICADO acepta lecturas — 404 si no está publicado
        assert resp.status_code == 404
