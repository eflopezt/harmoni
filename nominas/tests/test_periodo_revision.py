"""
Tests de la revisión pre-aprobación (variance review + flags descartables)
y del snapshot completo de parámetros legales.

Cubre:
- variance_conceptos: Δ y Δ% por concepto vs mes anterior, conceptos
  nuevos/desaparecidos, resaltado por umbral.
- Pantalla /revision/: 200, cifra hero, flags del detector con clave.
- Descartar flag: persiste quién/cuándo en PeriodoNomina.flags_descartados;
  segundo POST lo restaura.
- snapshot_parametros_legales: incluye RMV/UIT/tasas AFP/ONP/EsSalud/tope.
- generar_periodo llena parametros_snapshot si está vacío.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from nominas import engine
from nominas.models import (
    ConceptoRemunerativo,
    LineaNomina,
    PeriodoNomina,
    RegistroNomina,
)
from nominas.views_variance import variance_conceptos
from personal.models import Area, Personal, SubArea


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


def _personal(subarea, doc, nombre):
    return Personal.objects.create(
        nro_doc=doc, apellidos_nombres=nombre, cargo="Operario",
        tipo_trab="Empleado", estado="Activo", subarea=subarea,
        fecha_alta=date(2024, 1, 1), sueldo_base=Decimal("3000.00"),
    )


@pytest.fixture
def conceptos(db):
    sueldo = ConceptoRemunerativo.objects.filter(codigo="sueldo-basico").first()
    if not sueldo:
        sueldo = ConceptoRemunerativo.objects.create(
            codigo="sueldo-basico", nombre="Sueldo Básico",
            tipo="INGRESO", categoria="SUELDO", formula="DIAS_TRABAJADOS",
        )
    bono = ConceptoRemunerativo.objects.create(
        codigo="bono-var-test", nombre="Bono Variable Test",
        tipo="INGRESO", categoria="BONIFICACION", formula="MANUAL",
    )
    return {"sueldo": sueldo, "bono": bono}


def _periodo(anio, mes, estado="CALCULADO", **kw):
    return PeriodoNomina.objects.create(
        tipo="REGULAR", anio=anio, mes=mes,
        fecha_inicio=date(anio, mes, 1), fecha_fin=date(anio, mes, 28),
        estado=estado, **kw,
    )


def _registro_con_lineas(periodo, personal, conceptos_montos, neto):
    reg = RegistroNomina.objects.create(
        periodo=periodo, personal=personal,
        sueldo_base=Decimal("3000.00"),
        total_ingresos=sum(conceptos_montos.values(), Decimal("0")),
        neto_a_pagar=neto,
    )
    for concepto, monto in conceptos_montos.items():
        LineaNomina.objects.create(
            registro=reg, concepto=concepto, monto=monto,
            base_calculo=monto, porcentaje_aplicado=Decimal("0"),
        )
    return reg


@pytest.fixture
def admin_client(db, client):
    User.objects.create_superuser("admin", "a@a.com", "x")
    client.login(username="admin", password="x")
    return client


# ─── variance_conceptos ───────────────────────────────────────────────────────

class TestVarianceConceptos:
    def test_delta_y_pct_por_concepto(self, subarea, conceptos):
        p1 = _periodo(2026, 4, estado="CERRADO")
        p2 = _periodo(2026, 5)
        juan = _personal(subarea, "71000020", "VAR UNO")
        _registro_con_lineas(p1, juan, {conceptos["sueldo"]: Decimal("3000")}, Decimal("2600"))
        _registro_con_lineas(
            p2, juan,
            {conceptos["sueldo"]: Decimal("3000"), conceptos["bono"]: Decimal("500")},
            Decimal("3050"),
        )

        rows = variance_conceptos(p2, p1)
        por_codigo = {r["codigo"]: r for r in rows}

        sueldo = por_codigo["sueldo-basico"]
        assert sueldo["delta"] == Decimal("0")
        assert not sueldo["resaltar"]

        bono = por_codigo["bono-var-test"]
        assert bono["nuevo"] is True
        assert bono["total_act"] == Decimal("500")
        assert bono["resaltar"] is True

    def test_sin_anterior_no_resalta(self, subarea, conceptos):
        p = _periodo(2026, 5)
        juan = _personal(subarea, "71000021", "VAR DOS")
        _registro_con_lineas(p, juan, {conceptos["sueldo"]: Decimal("3000")}, Decimal("2600"))
        rows = variance_conceptos(p, None)
        assert all(not r["resaltar"] for r in rows)


# ─── Pantalla de revisión ─────────────────────────────────────────────────────

class TestPantallaRevision:
    def test_render_y_hero(self, admin_client, subarea, conceptos):
        p = _periodo(2026, 5, total_neto=Decimal("12345.67"))
        juan = _personal(subarea, "71000022", "REV UNO")
        _registro_con_lineas(p, juan, {conceptos["sueldo"]: Decimal("3000")}, Decimal("2600"))

        resp = admin_client.get(reverse("nominas_periodo_revision", args=[p.pk]))
        assert resp.status_code == 200
        html = resp.content.decode()
        assert "12345.67" in html or "12,345.67" in html
        assert "Revisar y" in html

    def test_flag_descartar_y_restaurar(self, admin_client, subarea, conceptos):
        # Mes anterior con neto 3000, actual 1000 → flag NETO_CAMBIO
        p1 = _periodo(2026, 4, estado="CERRADO")
        p2 = _periodo(2026, 5)
        juan = _personal(subarea, "71000023", "REV DOS")
        _registro_con_lineas(p1, juan, {conceptos["sueldo"]: Decimal("3000")}, Decimal("3000"))
        _registro_con_lineas(p2, juan, {conceptos["sueldo"]: Decimal("1000")}, Decimal("1000"))

        key = f"NETO_CAMBIO:{juan.pk}"
        url = reverse("nominas_periodo_flag_descartar", args=[p2.pk])

        resp = admin_client.post(url, {"flag_key": key, "mensaje": "baja autorizada"})
        assert resp.status_code == 302
        p2.refresh_from_db()
        assert key in p2.flags_descartados
        assert p2.flags_descartados[key]["por"] == "admin"
        assert p2.flags_descartados[key]["mensaje"] == "baja autorizada"

        # Segundo POST → restaurar
        admin_client.post(url, {"flag_key": key})
        p2.refresh_from_db()
        assert key not in p2.flags_descartados

    def test_periodo_cerrado_no_permite_descartar(self, admin_client, subarea):
        p = _periodo(2026, 5, estado="CERRADO")
        url = reverse("nominas_periodo_flag_descartar", args=[p.pk])
        admin_client.post(url, {"flag_key": "X:1"})
        p.refresh_from_db()
        assert p.flags_descartados == {}


# ─── Snapshot de parámetros legales ───────────────────────────────────────────

class TestSnapshotParametros:
    def test_snapshot_incluye_todo(self, db):
        snap = engine.snapshot_parametros_legales()
        assert Decimal(snap["rmv"]) > 0
        assert Decimal(snap["uit"]) > 0
        assert Decimal(snap["onp_tasa"]) == Decimal("13.00")
        assert Decimal(snap["essalud_tasa"]) == Decimal("9.00")
        assert Decimal(snap["afp_tope_rma"]) > 0
        assert set(snap["afp_tasas"]) == {"Habitat", "Integra", "Prima", "Profuturo"}
        for t in snap["afp_tasas"].values():
            assert Decimal(t["comision_flujo"]) > 0
            assert Decimal(t["seguro"]) > 0

    def test_generar_periodo_congela_parametros(self, db):
        p = _periodo(2026, 5, estado="BORRADOR")
        assert p.parametros_snapshot == {}
        engine.generar_periodo(p)
        p.refresh_from_db()
        assert Decimal(p.parametros_snapshot["rmv"]) > 0
        assert "afp_tasas" in p.parametros_snapshot

        # Idempotente: regenerar no pisa el snapshot existente
        snap_antes = p.parametros_snapshot
        engine.generar_periodo(p)
        p.refresh_from_db()
        assert p.parametros_snapshot == snap_antes
