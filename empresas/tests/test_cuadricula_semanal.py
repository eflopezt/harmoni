"""
Tests para Cuadrícula Semanal del Local.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from personal.models import Area, Personal, SubArea, Roster


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin_cs", password="x", email="a@a.com")


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def empresa(db):
    return Empresa.objects.create(
        ruc="20100099001", razon_social="Test Local S.A.C.",
        nombre_comercial="Test Local", subdominio="test-cs",
        activa=True,
    )


@pytest.fixture
def workers(db, empresa):
    area = Area.objects.create(nombre="Salón")
    sub = SubArea.objects.create(nombre="Servicio", area=area)
    ws = []
    for i in range(3):
        ws.append(Personal.objects.create(
            nro_doc=f"7{i:07d}",
            apellidos_nombres=f"TRABAJADOR {i}",
            cargo="Mesero",
            tipo_trab="Empleado",
            estado="Activo",
            subarea=sub,
            empresa=empresa,
            fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal("1500.00"),
        ))
    return ws


class TestCuadriculaSemanal:
    def test_render_sin_roster(self, client_admin, empresa, workers):
        resp = client_admin.get(reverse("cuadricula_semanal_local", args=[empresa.pk]))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Cuadrícula Semanal" in body
        assert empresa.nombre_comercial in body
        # 3 workers visibles
        for w in workers:
            assert w.apellidos_nombres in body

    def test_celdas_con_roster(self, client_admin, empresa, workers):
        # Crear roster de hoy para los 3 workers
        hoy = date.today()
        Roster.objects.create(personal=workers[0], fecha=hoy, codigo='M')
        Roster.objects.create(personal=workers[1], fecha=hoy, codigo='T')
        Roster.objects.create(personal=workers[2], fecha=hoy, codigo='D')

        resp = client_admin.get(reverse("cuadricula_semanal_local", args=[empresa.pk]))
        body = resp.content.decode()
        # Las clases de color deben aparecer
        assert "cs-cell manana" in body
        assert "cs-cell tarde" in body
        assert "cs-cell descanso" in body

    def test_navegacion_semana(self, client_admin, empresa, workers):
        # Solicitar la semana anterior por parametro fecha
        ayer = date.today() - timedelta(days=7)
        resp = client_admin.get(
            reverse("cuadricula_semanal_local", args=[empresa.pk]) +
            f"?fecha={ayer.isoformat()}"
        )
        assert resp.status_code == 200

    def test_export_xlsx(self, client_admin, empresa, workers):
        resp = client_admin.get(
            reverse("cuadricula_semanal_local", args=[empresa.pk]) + "?format=xlsx"
        )
        assert resp.status_code == 200
        assert "spreadsheet" in resp["Content-Type"]
        assert "Cuadricula_" in resp["Content-Disposition"]
        # Es archivo zip-magic (xlsx = zip)
        assert resp.content[:2] == b"PK"

    def test_alerta_mas_6_dias_seguidos(self, client_admin, empresa, workers):
        hoy = date.today()
        inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
        # Asignar 7 días de trabajo (todos M) → +6D alerta
        for d in range(7):
            Roster.objects.create(
                personal=workers[0],
                fecha=inicio_semana + timedelta(days=d),
                codigo='M',
            )
        resp = client_admin.get(reverse("cuadricula_semanal_local", args=[empresa.pk]))
        body = resp.content.decode()
        assert "+6D" in body

    def test_404_empresa_no_existe(self, client_admin):
        resp = client_admin.get(reverse("cuadricula_semanal_local", args=[99999]))
        assert resp.status_code == 404

    def test_permisos_no_superuser(self, db, client, empresa):
        u = User.objects.create_user(username="reg", password="x", is_superuser=False)
        client.force_login(u)
        resp = client.get(reverse("cuadricula_semanal_local", args=[empresa.pk]))
        assert resp.status_code in (302, 403)
