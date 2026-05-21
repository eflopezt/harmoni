"""
Tests para nominas.views.comparativo_mensual.

Cubre:
- Empty state (0 períodos REGULAR)
- 1 período (deltas = None / "—")
- Múltiples períodos (deltas calculados correctamente)
- Parámetro ?n= con validación (clamp 2-12)
- Filtra solo tipo='REGULAR' y estado ∈ {CALCULADO, APROBADO, CERRADO}
- Export CSV (?format=csv) — headers, BOM, filas, RESUMEN VENTANA
- Permisos: superuser/staff pasan, anónimo redirige a login
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from nominas.models import PeriodoNomina


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin_test", password="x", email="a@a.com",
    )


@pytest.fixture
def client_logged(client, admin_user):
    client.force_login(admin_user)
    return client


def _crear_periodo(anio, mes, *, estado="APROBADO", tipo="REGULAR",
                   trabajadores=70, neto="145000.00", bruto="172000.00",
                   descuentos="27000.00", costo="233000.00"):
    """Helper para crear PeriodoNomina con valores realistas."""
    return PeriodoNomina.objects.create(
        tipo=tipo,
        anio=anio,
        mes=mes,
        fecha_inicio=date(anio, mes, 1),
        fecha_fin=date(anio, mes, 28),
        estado=estado,
        total_trabajadores=trabajadores,
        total_bruto=Decimal(bruto),
        total_descuentos=Decimal(descuentos),
        total_neto=Decimal(neto),
        total_costo_empresa=Decimal(costo),
    )


# ─── Empty state ──────────────────────────────────────────────────────────────

class TestEmptyState:
    def test_sin_periodos_renderiza_empty(self, client_logged):
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        assert resp.status_code == 200
        # Empty state explicit message
        assert "Aún no hay períodos comparables" in resp.content.decode("utf-8")

    def test_sin_periodos_no_crashea(self, client_logged):
        """No debe haber 500 cuando filas=[] y resumen=None."""
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        assert resp.status_code == 200


# ─── 1 período ────────────────────────────────────────────────────────────────

class TestUnPeriodo:
    def test_un_periodo_muestra_fila_sin_delta(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        assert resp.status_code == 200
        # Período visible
        assert b"May 2026" in resp.content
        # Deltas para el primer período son "—" (None → texto)
        # (verificación indirecta: existe class delta-flat)
        assert b"delta-flat" in resp.content


# ─── Múltiples períodos + deltas ──────────────────────────────────────────────

class TestMultiplesPeriodos:
    def test_tres_periodos_calcula_deltas(self, client_logged):
        # Mar: 65 trab, 140k neto, 225k costo
        _crear_periodo(2026, 3, trabajadores=65,
                       neto="140000.00", costo="225000.00")
        # Abr: 68 trab, 142k neto, 228k costo
        _crear_periodo(2026, 4, trabajadores=68,
                       neto="142000.00", costo="228000.00")
        # May: 70 trab, 145k neto, 233k costo
        _crear_periodo(2026, 5, trabajadores=70,
                       neto="145000.00", costo="233000.00")

        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?n=6"
        )
        assert resp.status_code == 200
        body = resp.content.decode()

        # Los 3 períodos aparecen
        assert "Mar 2026" in body
        assert "Abr 2026" in body
        assert "May 2026" in body

        # Deltas positivos (crecimiento) deben aparecer con "+"
        assert "+3" in body or "+2" in body  # workers delta

    def test_resumen_ventana_calcula_deltas_totales(self, client_logged):
        _crear_periodo(2026, 3, trabajadores=60, neto="130000.00",
                       costo="210000.00")
        _crear_periodo(2026, 5, trabajadores=72, neto="148000.00",
                       costo="240000.00")

        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        body = resp.content.decode()

        # Δ trabajadores total: 72 - 60 = +12
        assert "+12" in body
        # Δ neto %: (148k - 130k)/130k = 13.8%
        assert "13.8" in body or "+13" in body


# ─── Ventana ?n= ─────────────────────────────────────────────────────────────

class TestVentanaParam:
    def test_n_default_es_6(self, client_logged):
        for m in range(1, 8):  # 7 períodos
            _crear_periodo(2026, m)
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        body = resp.content.decode()
        # Default ventana=6: el período más antiguo (Ene 2026) NO debe aparecer
        # en la tabla principal
        # (verifica por el selector de ventana selected)
        assert 'value="6"  selected' in body or 'value="6" selected' in body

    def test_n_clamp_minimo_2(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?n=1"
        )
        assert resp.status_code == 200
        # n=1 se eleva a 2 (clamp); no crash

    def test_n_clamp_maximo_12(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?n=99"
        )
        assert resp.status_code == 200
        # n=99 se reduce a 12; no crash

    def test_n_invalid_string_usa_default(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?n=foo"
        )
        assert resp.status_code == 200


# ─── Filtros de tipo/estado ───────────────────────────────────────────────────

class TestFiltros:
    def test_excluye_no_regulares(self, client_logged):
        _crear_periodo(2026, 5, tipo="REGULAR")
        _crear_periodo(2026, 7, tipo="GRATIFICACION")
        _crear_periodo(2026, 11, tipo="CTS")
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        body = resp.content.decode()
        # El REGULAR de mayo aparece
        assert "May 2026" in body
        # Los GRATIFICACION/CTS NO deben aparecer (view filtra tipo=REGULAR)
        assert "Jul 2026" not in body
        assert "Nov 2026" not in body

    def test_excluye_borrador(self, client_logged):
        _crear_periodo(2026, 4, estado="BORRADOR")
        _crear_periodo(2026, 5, estado="APROBADO")
        resp = client_logged.get(reverse("nominas_comparativo_mensual"))
        body = resp.content.decode()
        # BORRADOR no debe aparecer
        assert "Abr 2026" not in body
        assert "May 2026" in body


# ─── Export CSV ───────────────────────────────────────────────────────────────

class TestExportCSV:
    def test_csv_descarga_content_type_y_disposition(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?format=csv"
        )
        assert resp.status_code == 200
        assert "text/csv" in resp["Content-Type"]
        assert "attachment" in resp["Content-Disposition"]
        assert ".csv" in resp["Content-Disposition"]

    def test_csv_tiene_bom_utf8(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?format=csv"
        )
        # Primer caracter (3 bytes en UTF-8) debe ser BOM (EF BB BF)
        assert resp.content.startswith(b"\xef\xbb\xbf")

    def test_csv_headers_correctos(self, client_logged):
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?format=csv"
        )
        body = resp.content.decode("utf-8-sig")
        primera_linea = body.split("\r\n")[0]
        # Delimitador es ;
        assert primera_linea.count(";") >= 10
        # Columnas clave (usa-tilde y caracteres especiales)
        assert "Per" in primera_linea  # "Período" puede romper match exacto
        assert "Trabajadores" in primera_linea
        assert "Neto" in primera_linea
        assert "Costo Total" in primera_linea

    def test_csv_incluye_resumen_ventana(self, client_logged):
        _crear_periodo(2026, 4)
        _crear_periodo(2026, 5)
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?format=csv"
        )
        body = resp.content.decode("utf-8-sig")
        assert "RESUMEN VENTANA" in body

    def test_csv_sin_datos_no_tiene_resumen(self, client_logged):
        resp = client_logged.get(
            reverse("nominas_comparativo_mensual") + "?format=csv"
        )
        assert resp.status_code == 200
        body = resp.content.decode("utf-8-sig")
        # Sin filas → no resumen
        assert "RESUMEN VENTANA" not in body


# ─── Permisos ─────────────────────────────────────────────────────────────────

class TestPermisos:
    def test_anonimo_redirige_a_login(self, client):
        resp = client.get(reverse("nominas_comparativo_mensual"))
        # 302 redirect a /login/ (login_required decorator)
        assert resp.status_code == 302
        assert "/login" in resp["Location"]

    def test_usuario_no_staff_no_pasa(self, db, client):
        user = User.objects.create_user(
            username="worker", password="x", is_staff=False, is_superuser=False,
        )
        client.force_login(user)
        resp = client.get(reverse("nominas_comparativo_mensual"))
        # user_passes_test → redirige a login con mensaje (302) o 403
        assert resp.status_code in (302, 403)

    def test_staff_no_superuser_pasa(self, db, client):
        user = User.objects.create_user(
            username="staff_test", password="x", is_staff=True,
        )
        client.force_login(user)
        resp = client.get(reverse("nominas_comparativo_mensual"))
        assert resp.status_code == 200
