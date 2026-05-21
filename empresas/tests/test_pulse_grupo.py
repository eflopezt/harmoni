"""
Tests para Pulse del Grupo + drill-down a detalle de local.
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
    return User.objects.create_superuser(username="admin_pulse", password="x", email="a@a.com")


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def empresas_grupo(db):
    out = []
    for i in range(3):
        out.append(Empresa.objects.create(
            ruc=f"2010000{i:04d}",
            razon_social=f"Local {i} S.A.C.",
            nombre_comercial=f"Local {i}",
            subdominio=f"local{i}",
            activa=True,
        ))
    return out


@pytest.fixture
def workers_in_empresas(db, empresas_grupo):
    area = Area.objects.create(nombre="Salón")
    sub = SubArea.objects.create(nombre="Servicio", area=area)
    workers = []
    for i, emp in enumerate(empresas_grupo):
        for j in range(5):
            workers.append(Personal.objects.create(
                nro_doc=f"7{i}{j:06d}",
                apellidos_nombres=f"TRABAJADOR {i}-{j}",
                cargo="Mesero",
                tipo_trab="Empleado",
                estado="Activo",
                subarea=sub,
                empresa=emp,
                fecha_alta=date(2024, 1, 1),
                sueldo_base=Decimal("1500.00"),
            ))
    return workers


# ─── Pulse del Grupo (lista) ──────────────────────────────────────────────────

class TestPulseGrupo:
    def test_render_sin_empresas(self, client_admin):
        resp = client_admin.get(reverse("pulse_del_grupo"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Pulse del Grupo" in body

    def test_lista_empresas_activas(self, client_admin, empresas_grupo, workers_in_empresas):
        resp = client_admin.get(reverse("pulse_del_grupo"))
        body = resp.content.decode()
        for e in empresas_grupo:
            assert e.nombre_comercial in body

    def test_excluye_empresas_inactivas(self, client_admin, empresas_grupo):
        empresas_grupo[0].activa = False
        empresas_grupo[0].save()
        resp = client_admin.get(reverse("pulse_del_grupo"))
        body = resp.content.decode()
        assert empresas_grupo[0].nombre_comercial not in body
        assert empresas_grupo[1].nombre_comercial in body


# ─── Drill-down a detalle ─────────────────────────────────────────────────────

class TestPulseDetalle:
    def test_detalle_local(self, client_admin, empresas_grupo, workers_in_empresas):
        emp = empresas_grupo[0]
        resp = client_admin.get(reverse("pulse_local_detalle", args=[emp.pk]))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert emp.nombre_comercial in body
        # Trabajadores del local
        for w in workers_in_empresas[:5]:  # primeros 5 son del local 0
            if w.empresa_id == emp.pk:
                assert w.apellidos_nombres in body

    def test_detalle_404_si_no_existe(self, client_admin):
        resp = client_admin.get(reverse("pulse_local_detalle", args=[9999]))
        assert resp.status_code == 404

    def test_kpis_visibles(self, client_admin, empresas_grupo, workers_in_empresas):
        emp = empresas_grupo[0]
        resp = client_admin.get(reverse("pulse_local_detalle", args=[emp.pk]))
        body = resp.content.decode()
        # Headcount KPI = 5 workers en este local
        assert "Headcount" in body
        assert ">5<" in body or "5 trabajador" in body


# ─── Permisos ─────────────────────────────────────────────────────────────────

class TestPermisos:
    def test_pulse_anonimo_redirige(self, client):
        resp = client.get(reverse("pulse_del_grupo"))
        assert resp.status_code == 302

    def test_pulse_detalle_anonimo_redirige(self, client, empresas_grupo):
        resp = client.get(reverse("pulse_local_detalle", args=[empresas_grupo[0].pk]))
        assert resp.status_code == 302

    def test_no_superuser_no_pasa(self, db, client, empresas_grupo):
        u = User.objects.create_user(username="reg", password="x", is_superuser=False)
        client.force_login(u)
        resp = client.get(reverse("pulse_del_grupo"))
        assert resp.status_code in (302, 403)
