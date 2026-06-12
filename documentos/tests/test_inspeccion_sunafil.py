"""
Tests del Modo SUNAFIL (documentos/views_inspeccion.py).

Cubre:
- GET muestra el form (solo superuser).
- POST genera un ZIP con índice, planilla CSV del período aprobado del rango
  y boletas PDF; el tareo del rango va como CSV mensual.
- Períodos BORRADOR no entran al paquete.
- Rango > 12 meses se rechaza.
- Sin componentes seleccionados se rechaza.
"""
import io
import zipfile
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from nominas.models import PeriodoNomina, RegistroNomina
from personal.models import Area, Personal, SubArea


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def personal(subarea):
    return Personal.objects.create(
        nro_doc="71000040", apellidos_nombres="SUNAFIL PRUEBA, LUZ",
        cargo="Operario", tipo_trab="Empleado", estado="Activo",
        subarea=subarea, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("2500.00"),
    )


@pytest.fixture
def periodo_aprobado(personal):
    p = PeriodoNomina.objects.create(
        tipo="REGULAR", anio=2026, mes=4,
        fecha_inicio=date(2026, 3, 22), fecha_fin=date(2026, 4, 21),
        estado="APROBADO",
    )
    RegistroNomina.objects.create(
        periodo=p, personal=personal,
        sueldo_base=Decimal("2500.00"), dias_trabajados=30,
        total_ingresos=Decimal("2500.00"), neto_a_pagar=Decimal("2200.00"),
    )
    return p


@pytest.fixture
def admin_client(db, client):
    User.objects.create_superuser("admin", "a@a.com", "x")
    client.login(username="admin", password="x")
    return client


URL = "documentos_inspeccion_sunafil"


class TestAcceso:
    def test_get_form(self, admin_client):
        resp = admin_client.get(reverse(URL))
        assert resp.status_code == 200
        assert b"SUNAFIL" in resp.content

    def test_no_superuser_no_entra(self, client, db):
        User.objects.create_user("comun", "c@c.com", "x")
        client.login(username="comun", password="x")
        resp = client.get(reverse(URL))
        assert resp.status_code in (302, 403)


class TestPaquete:
    def _zip_de(self, resp):
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/zip"
        return zipfile.ZipFile(io.BytesIO(resp.content))

    def test_zip_con_planilla_boletas_e_indice(self, admin_client, periodo_aprobado):
        resp = admin_client.post(reverse(URL), {
            "desde": "2026-04-01", "hasta": "2026-04-30",
            "boletas": "1", "planillas": "1",
        })
        zf = self._zip_de(resp)
        nombres = zf.namelist()

        assert "00_INDICE.txt" in nombres
        assert "02_Planillas/Planilla_2026-04.csv" in nombres
        boletas = [n for n in nombres if n.startswith("01_Boletas/2026-04/")]
        assert len(boletas) == 1
        assert "71000040" in boletas[0]

        csv_text = zf.read("02_Planillas/Planilla_2026-04.csv").decode("utf-8-sig")
        assert "SUNAFIL PRUEBA, LUZ" in csv_text
        assert "2200.00" in csv_text

    def test_periodo_borrador_no_entra(self, admin_client, personal):
        p = PeriodoNomina.objects.create(
            tipo="REGULAR", anio=2026, mes=4,
            fecha_inicio=date(2026, 3, 22), fecha_fin=date(2026, 4, 21),
            estado="BORRADOR",
        )
        RegistroNomina.objects.create(
            periodo=p, personal=personal, sueldo_base=Decimal("2500.00"),
        )
        resp = admin_client.post(reverse(URL), {
            "desde": "2026-04-01", "hasta": "2026-04-30",
            "planillas": "1",
        })
        zf = self._zip_de(resp)
        assert not [n for n in zf.namelist() if n.startswith("02_Planillas/")]

    def test_rango_mayor_a_12_meses_rechazado(self, admin_client):
        resp = admin_client.post(reverse(URL), {
            "desde": "2024-01-01", "hasta": "2026-04-30",
            "planillas": "1",
        })
        assert resp.status_code == 302  # redirect con mensaje de error

    def test_sin_componentes_rechazado(self, admin_client):
        resp = admin_client.post(reverse(URL), {
            "desde": "2026-04-01", "hasta": "2026-04-30",
        })
        assert resp.status_code == 302
