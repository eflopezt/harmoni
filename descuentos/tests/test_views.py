"""
Tests de vistas de descuentos: permisos admin, crear/aprobar/anular,
y la vista del portal del trabajador.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from descuentos.models import DescuentoPlanilla
from personal.models import Area, Personal, SubArea


@pytest.fixture
def trabajador(db):
    area = Area.objects.create(nombre="Operaciones")
    sub = SubArea.objects.create(nombre="Campo", area=area)
    return Personal.objects.create(
        nro_doc="71234567", apellidos_nombres="LOPEZ, CARLOS",
        cargo="Operario", tipo_trab="Empleado", estado="Activo",
        subarea=sub, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("3000.00"),
    )


@pytest.fixture
def admin_client(db, client):
    User.objects.create_user("admin", password="x", is_superuser=True, is_staff=True)
    client.login(username="admin", password="x")
    return client


def _descuento(trabajador, **extra):
    base = dict(
        personal=trabajador, causal="ROTURA_HERRAMIENTA",
        detalle="Taladro dañado", monto_total=Decimal("1000.00"),
        num_cuotas=4, estado="PENDIENTE",
    )
    base.update(extra)
    return DescuentoPlanilla.objects.create(**base)


class TestPermisos:
    def test_panel_requiere_admin(self, client, db):
        User.objects.create_user("normal", password="x")
        client.login(username="normal", password="x")
        assert client.get(reverse("descuentos_panel")).status_code == 403

    def test_panel_admin_ok(self, admin_client, trabajador):
        _descuento(trabajador)
        resp = admin_client.get(reverse("descuentos_panel"))
        assert resp.status_code == 200
        assert b"LOPEZ" in resp.content


class TestFlujo:
    def test_crear_asigna_solicitante(self, admin_client, trabajador):
        resp = admin_client.post(reverse("descuentos_crear"), {
            "personal": trabajador.pk,
            "causal": "REPOSICION_UNIFORME",
            "detalle": "Uniforme nuevo",
            "monto_total": "120.00",
            "num_cuotas": 2,
        })
        assert resp.status_code == 302
        d = DescuentoPlanilla.objects.get(personal=trabajador)
        assert d.solicitado_por.username == "admin"
        assert d.cuota_mensual == Decimal("60.00")

    def test_aprobar_pendiente(self, admin_client, trabajador):
        d = _descuento(trabajador)
        resp = admin_client.post(reverse("descuentos_aprobar", args=[d.pk]))
        assert resp.status_code == 302
        d.refresh_from_db()
        assert d.estado == "APROBADO"
        assert d.fecha_aprobacion == date.today()
        assert d.fecha_inicio_descuento is not None

    def test_aprobar_no_pendiente_no_cambia(self, admin_client, trabajador):
        d = _descuento(trabajador, estado="EN_CURSO")
        admin_client.post(reverse("descuentos_aprobar", args=[d.pk]))
        d.refresh_from_db()
        assert d.estado == "EN_CURSO"

    def test_anular_con_motivo(self, admin_client, trabajador):
        d = _descuento(trabajador)
        admin_client.post(reverse("descuentos_anular", args=[d.pk]), {"motivo": "error de registro"})
        d.refresh_from_db()
        assert d.estado == "ANULADO"
        assert "error de registro" in d.observaciones


class TestPortal:
    def test_mis_descuentos(self, client, trabajador):
        user = User.objects.create_user("carlos", password="x")
        trabajador.usuario = user
        trabajador.save(update_fields=["usuario"])
        _descuento(trabajador, estado="EN_CURSO")
        _descuento(trabajador, estado="ANULADO")  # no debe aparecer

        client.login(username="carlos", password="x")
        resp = client.get(reverse("mis_descuentos"))
        assert resp.status_code == 200
        # Solo el EN_CURSO cuenta para el resumen
        assert resp.context["en_curso_count"] == 1
        assert resp.context["saldo"] == Decimal("1000.00")

    def test_sin_vinculo_redirige(self, client, db):
        User.objects.create_user("suelto", password="x")
        client.login(username="suelto", password="x")
        resp = client.get(reverse("mis_descuentos"))
        assert resp.status_code == 302
