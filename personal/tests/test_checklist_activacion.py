"""
Tests del checklist de activación de 5 pasos en el home.

- Cuenta nueva (BD vacía): card visible con 0/5 y los 5 flags en contexto.
- Con empleados cargados: empleados_ok pasa a True y la card sigue
  (persistente hasta 5/5 — ya no desaparece al cargar el primer empleado).
- Home renderiza 200 con la card.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area, Personal, SubArea


@pytest.fixture
def admin_client(db, client):
    User.objects.create_superuser("admin", "a@a.com", "x")
    client.login(username="admin", password="x")
    return client


class TestChecklistActivacion:
    def test_cuenta_nueva_muestra_card(self, admin_client):
        resp = admin_client.get(reverse("home"))
        assert resp.status_code == 200
        pasos = resp.context.get("primeros_pasos")
        assert pasos is not None
        assert pasos["completados"] < 5
        for k in ("rep_ok", "empleados_ok", "conceptos_ok", "planilla_ok", "portal_ok"):
            assert k in pasos
        assert "Activa tu cuenta" in resp.content.decode()

    def test_con_empleados_sigue_visible_y_marca_paso(self, admin_client):
        area = Area.objects.create(nombre="Ops")
        sa = SubArea.objects.create(nombre="Campo", area=area)
        Personal.objects.create(
            nro_doc="71000090", apellidos_nombres="CHECK, LISTA",
            cargo="Op", tipo_trab="Empleado", estado="Activo",
            subarea=sa, fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal("2000.00"),
        )
        resp = admin_client.get(reverse("home"))
        pasos = resp.context.get("primeros_pasos")
        assert pasos is not None  # persistente: aún no 5/5
        assert pasos["empleados_ok"] is True
        assert pasos["completados"] >= 1
