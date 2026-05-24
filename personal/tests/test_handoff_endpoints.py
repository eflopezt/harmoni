"""Tests para los endpoints del rediseño handoff Empleados Cockpit:
- personal_drawer_data → JSON con basic + documentos + histórico + IA
- personal_inline_edit → whitelist strict de campos editables doble-click
- personal_cesar_batch → bulk cese transaccional con permisos
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from personal.models import Area, Personal, SubArea


# ═══════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════

@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Operaciones Test")


@pytest.fixture
def subarea_a(area):
    return SubArea.objects.create(nombre="Campo A", area=area)


@pytest.fixture
def subarea_b(area):
    return SubArea.objects.create(nombre="Oficina B", area=area)


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(
        username="adm_handoff", password="x", email="adm@ex.com",
    )


@pytest.fixture
def user_normal(db):
    return User.objects.create_user(username="normal_handoff", password="x")


@pytest.fixture
def trabajador(subarea_a):
    """Personal activo de prueba con todos los fields populados."""
    return Personal.objects.create(
        nro_doc="40123456",
        apellidos_nombres="LOPEZ TORRES, JUAN",
        cargo="Operario",
        tipo_trab="Empleado",
        categoria="EMPLEADO",
        estado="Activo",
        subarea=subarea_a,
        fecha_alta=date(2024, 1, 1),
        sueldo_base=2500,
        regimen_pension="ONP",
        tiene_eps=False,
        celular="987654321",
        correo_corporativo="juan@ex.com",
        grupo_tareo="STAFF",
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


# ═══════════════════════════════════════════════════════════════════════
# personal_drawer_data
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDrawerData:

    def test_admin_recibe_json_completo(self, client_admin, trabajador):
        url = reverse("personal_drawer_data", args=[trabajador.pk])
        r = client_admin.get(url)
        assert r.status_code == 200
        data = r.json()
        # Las 4 secciones del handoff
        assert "basic" in data
        assert "documentos" in data
        assert "historico" in data
        assert "ia" in data

    def test_basic_tiene_campos_handoff(self, client_admin, trabajador):
        r = client_admin.get(reverse("personal_drawer_data", args=[trabajador.pk]))
        b = r.json()["basic"]
        assert b["dni"] == "40123456"
        assert b["nombre"] == "LOPEZ TORRES, JUAN"
        assert b["cargo"] == "Operario"
        assert b["grupo"] == "STAFF"
        assert b["regimen"] == "ONP"
        assert b["tiene_eps"] is False
        assert b["sueldo_base"] == 2500.0
        assert b["estado"] == "Activo"
        assert b["iniciales"]  # algo no vacío
        assert b["url_detail"].endswith(f"/{trabajador.pk}/")
        assert b["url_editar"].endswith(f"/{trabajador.pk}/editar/")

    def test_ia_tiene_4_metricas_handoff(self, client_admin, trabajador):
        r = client_admin.get(reverse("personal_drawer_data", args=[trabajador.pk]))
        ia = r.json()["ia"]
        # Las 4 métricas del handoff (algunas pueden ser None/—)
        for k in ("score_rotacion", "asistencia_90d_pct", "salario_vs_banda", "score_desempeno"):
            assert k in ia
        # Recomendaciones siempre presentes (al menos 1 línea)
        assert isinstance(ia["recomendaciones"], list)
        assert len(ia["recomendaciones"]) >= 1

    def test_score_rotacion_alto_si_cesado(self, client_admin, trabajador):
        """La heurística clave: si está Cesado, score_rotacion = 100."""
        trabajador.estado = "Cesado"
        trabajador.fecha_cese = date.today()
        trabajador.save()
        r = client_admin.get(reverse("personal_drawer_data", args=[trabajador.pk]))
        assert r.json()["ia"]["score_rotacion"] == 100

    def test_historico_incluye_alta(self, client_admin, trabajador):
        r = client_admin.get(reverse("personal_drawer_data", args=[trabajador.pk]))
        eventos = r.json()["historico"]
        # Al menos un evento con la fecha de alta
        assert any(e["titulo"] == "Ingreso a la empresa" for e in eventos)

    def test_no_existe_404(self, client_admin):
        r = client_admin.get(reverse("personal_drawer_data", args=[9999999]))
        assert r.status_code == 404

    def test_anonimo_redirige_login(self, client, trabajador):
        r = client.get(reverse("personal_drawer_data", args=[trabajador.pk]))
        assert r.status_code in (302, 403)


# ═══════════════════════════════════════════════════════════════════════
# personal_inline_edit
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestInlineEdit:

    def _post(self, c, pid, field, value):
        return c.post(
            reverse("personal_inline_edit", args=[pid]),
            data=json.dumps({"field": field, "value": value}),
            content_type="application/json",
        )

    def test_edita_cargo_ok(self, client_admin, trabajador):
        r = self._post(client_admin, trabajador.pk, "cargo", "Supervisor")
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["old_value"] == "Operario"
        assert d["new_value"] == "Supervisor"
        # Persistido
        trabajador.refresh_from_db()
        assert trabajador.cargo == "Supervisor"

    def test_cargo_vacio_devuelve_error(self, client_admin, trabajador):
        r = self._post(client_admin, trabajador.pk, "cargo", "")
        assert r.status_code == 400
        assert "vacío" in r.json()["error"]
        # No cambió
        trabajador.refresh_from_db()
        assert trabajador.cargo == "Operario"

    def test_cargo_muy_largo_devuelve_error(self, client_admin, trabajador):
        r = self._post(client_admin, trabajador.pk, "cargo", "x" * 200)
        assert r.status_code == 400

    def test_edita_subarea_ok(self, client_admin, trabajador, subarea_b):
        r = self._post(client_admin, trabajador.pk, "subarea", subarea_b.pk)
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["new_value_display"] == subarea_b.nombre
        trabajador.refresh_from_db()
        assert trabajador.subarea_id == subarea_b.pk

    def test_subarea_inexistente_404(self, client_admin, trabajador):
        r = self._post(client_admin, trabajador.pk, "subarea", 99999)
        assert r.status_code == 404

    def test_subarea_vacia_limpia_field(self, client_admin, trabajador):
        r = self._post(client_admin, trabajador.pk, "subarea", "")
        assert r.status_code == 200
        trabajador.refresh_from_db()
        assert trabajador.subarea_id is None

    def test_field_no_permitido_rechaza(self, client_admin, trabajador):
        """Whitelist strict: sueldo NO se puede editar inline (liquidación-sensible)."""
        r = self._post(client_admin, trabajador.pk, "sueldo_base", 99999)
        assert r.status_code == 400
        assert "no permitido" in r.json()["error"]
        # Sueldo intacto
        trabajador.refresh_from_db()
        assert float(trabajador.sueldo_base) == 2500.0

    def test_get_no_permitido(self, client_admin, trabajador):
        r = client_admin.get(reverse("personal_inline_edit", args=[trabajador.pk]))
        assert r.status_code == 405  # require_POST

    def test_json_invalido_devuelve_400(self, client_admin, trabajador):
        r = client_admin.post(
            reverse("personal_inline_edit", args=[trabajador.pk]),
            data="not json at all",
            content_type="application/json",
        )
        assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════
# personal_cesar_batch
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCesarBatch:

    @pytest.fixture
    def trio(self, subarea_a):
        """3 trabajadores activos para tests de batch."""
        return [
            Personal.objects.create(
                nro_doc=f"4090000{i}",
                apellidos_nombres=f"WORKER {i}",
                cargo="Op",
                tipo_trab="Empleado",
                categoria="EMPLEADO",
                estado="Activo",
                subarea=subarea_a,
                fecha_alta=date(2024, 1, 1),
                sueldo_base=2000,
            )
            for i in range(3)
        ]

    def test_admin_cesa_3_en_batch(self, client_admin, trio):
        ids = [p.pk for p in trio]
        r = client_admin.post(
            reverse("personal_cesar_batch"),
            data={"ids": ids, "fecha_cese": "2026-05-31", "motivo": "DESPIDO"},
        )
        assert r.status_code == 200
        d = r.json()
        assert d["ok"] is True
        assert d["cesados"] == 3
        assert d["fecha_cese"] == "2026-05-31"
        # Persistido
        for p in trio:
            p.refresh_from_db()
            assert p.estado == "Cesado"
            assert p.fecha_cese == date(2026, 5, 31)

    def test_no_superuser_403(self, client_normal, trio):
        ids = [p.pk for p in trio]
        r = client_normal.post(
            reverse("personal_cesar_batch"),
            data={"ids": ids, "fecha_cese": "2026-05-31"},
        )
        assert r.status_code == 403
        # No cambió ningún estado
        for p in trio:
            p.refresh_from_db()
            assert p.estado == "Activo"

    def test_sin_ids_devuelve_400(self, client_admin):
        r = client_admin.post(reverse("personal_cesar_batch"), data={"fecha_cese": "2026-05-31"})
        assert r.status_code == 400

    def test_ids_invalidos_400(self, client_admin):
        r = client_admin.post(reverse("personal_cesar_batch"), data={"ids": "no-int"})
        assert r.status_code == 400

    def test_fecha_invalida_400(self, client_admin, trio):
        r = client_admin.post(
            reverse("personal_cesar_batch"),
            data={"ids": [trio[0].pk], "fecha_cese": "31-05-2026"},
        )
        assert r.status_code == 400

    def test_fecha_default_es_hoy(self, client_admin, trio):
        r = client_admin.post(
            reverse("personal_cesar_batch"),
            data={"ids": [trio[0].pk]},
        )
        assert r.status_code == 200
        assert r.json()["fecha_cese"] == date.today().isoformat()

    def test_ya_cesados_se_excluyen(self, client_admin, trio):
        """Si los 3 ya están cesados, devuelve 400 'ninguno elegible'."""
        for p in trio:
            p.estado = "Cesado"
            p.save()
        r = client_admin.post(
            reverse("personal_cesar_batch"),
            data={"ids": [p.pk for p in trio], "fecha_cese": "2026-06-01"},
        )
        assert r.status_code == 400
        assert "elegible" in r.json()["error"]

    def test_mezcla_activos_y_cesados_solo_cesa_activos(self, client_admin, trio):
        # El primero ya está cesado, los otros 2 activos
        trio[0].estado = "Cesado"
        trio[0].save()
        r = client_admin.post(
            reverse("personal_cesar_batch"),
            data={"ids": [p.pk for p in trio], "fecha_cese": "2026-06-01"},
        )
        assert r.status_code == 200
        assert r.json()["cesados"] == 2  # solo los 2 activos

    def test_get_no_permitido(self, client_admin):
        r = client_admin.get(reverse("personal_cesar_batch"))
        assert r.status_code == 405
