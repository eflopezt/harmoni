"""
Tests de la integración descuentos ↔ planilla (fixes de esta sesión):

1. El engine ahora incluye descuentos judiciales en estado APROBADO
   (antes solo EN_CURSO → un embargo aprobado jamás se descontaba).
2. fecha_inicio_descuento futura → no se descuenta todavía.
3. registrar_aplicaciones_cierre: crea AplicacionDescuento, baja el saldo,
   transiciona APROBADO→EN_CURSO y →PAGADO al completar; es idempotente.
"""
from datetime import date
from decimal import Decimal

import pytest

from descuentos.models import AplicacionDescuento, DescuentoPlanilla
from descuentos.services import registrar_aplicaciones_cierre
from nominas.models import ConceptoRemunerativo, LineaNomina, PeriodoNomina, RegistroNomina
from personal.models import Area, Personal, SubArea


@pytest.fixture
def trabajador(db):
    area = Area.objects.create(nombre="Operaciones")
    sub = SubArea.objects.create(nombre="Campo", area=area)
    return Personal.objects.create(
        nro_doc="71234567", apellidos_nombres="LOPEZ, CARLOS",
        cargo="Operario", tipo_trab="Empleado", estado="Activo",
        subarea=sub, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("3000.00"), regimen_pension="ONP",
    )


@pytest.fixture
def periodo(db):
    return PeriodoNomina.objects.create(
        tipo="REGULAR", anio=2026, mes=6,
        fecha_inicio=date(2026, 5, 22), fecha_fin=date(2026, 6, 21),
        estado="APROBADO",
    )


@pytest.fixture
def registro(trabajador, periodo):
    return RegistroNomina.objects.create(
        periodo=periodo, personal=trabajador,
        sueldo_base=Decimal("3000.00"), regimen_pension="ONP",
        dias_trabajados=30,
    )


def _pension(trabajador, **extra):
    base = dict(
        personal=trabajador, causal="PENSION_ALIMENTICIA",
        detalle="Orden judicial", monto_total=Decimal("1200.00"),
        num_cuotas=2, cuota_mensual=Decimal("600.00"), estado="APROBADO",
    )
    base.update(extra)
    return DescuentoPlanilla.objects.create(**base)


# ─── Engine: APROBADO también se descuenta ────────────────────────────────────

class TestEngineIncluyeAprobado:
    def test_aprobado_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _pension(trabajador, estado="APROBADO")
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"] + Decimal("600.00")

    def test_fecha_inicio_futura_no_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _pension(trabajador, fecha_inicio_descuento=date(2026, 8, 1))  # tras el período
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"]

    def test_fecha_inicio_dentro_del_periodo_si_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _pension(trabajador, fecha_inicio_descuento=date(2026, 6, 1))
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"] + Decimal("600.00")


# ─── Servicio de cierre ──────────────────────────────────────────────────────

def _linea_judicial(registro, codigo, monto):
    concepto, _ = ConceptoRemunerativo.objects.get_or_create(
        codigo=codigo, defaults={"nombre": codigo, "tipo": "DESCUENTO"},
    )
    return LineaNomina.objects.create(
        registro=registro, concepto=concepto, monto=Decimal(str(monto)),
    )


class TestRegistrarAplicacionesCierre:
    def test_crea_aplicacion_y_transiciona_en_curso(self, registro, periodo, trabajador):
        d = _pension(trabajador, estado="APROBADO")
        _linea_judicial(registro, "pension-alimenticia", "600.00")

        creadas = registrar_aplicaciones_cierre(periodo)
        assert creadas == 1
        d.refresh_from_db()
        assert d.estado == "EN_CURSO"
        assert d.saldo_pendiente == Decimal("600.00")
        app = AplicacionDescuento.objects.get(descuento=d)
        assert app.monto_aplicado == Decimal("600.00")
        assert app.registro_nomina == registro
        assert (app.periodo_anio, app.periodo_mes) == (2026, 6)

    def test_completa_y_pasa_a_pagado(self, registro, periodo, trabajador):
        d = _pension(trabajador, estado="EN_CURSO")
        # Ya se aplicó una cuota el mes pasado
        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=5,
            monto_aplicado=Decimal("600.00"),
        )
        _linea_judicial(registro, "pension-alimenticia", "600.00")

        registrar_aplicaciones_cierre(periodo)
        d.refresh_from_db()
        assert d.saldo_pendiente == Decimal("0")
        assert d.estado == "PAGADO"

    def test_idempotente(self, registro, periodo, trabajador):
        d = _pension(trabajador, estado="EN_CURSO")
        _linea_judicial(registro, "pension-alimenticia", "600.00")

        assert registrar_aplicaciones_cierre(periodo) == 1
        assert registrar_aplicaciones_cierre(periodo) == 0  # re-cierre no duplica
        assert AplicacionDescuento.objects.filter(descuento=d).count() == 1
        d.refresh_from_db()
        assert d.saldo_pendiente == Decimal("600.00")

    def test_embargo_capado_aplica_lo_descontado(self, registro, periodo, trabajador):
        # El engine capó la cuota de 300 a 100 (tope legal) → la línea dice 100.
        d = DescuentoPlanilla.objects.create(
            personal=trabajador, causal="EMBARGO_JUDICIAL",
            detalle="Embargo", monto_total=Decimal("3000.00"),
            num_cuotas=10, cuota_mensual=Decimal("300.00"), estado="EN_CURSO",
        )
        _linea_judicial(registro, "embargo-judicial", "100.00")

        registrar_aplicaciones_cierre(periodo)
        app = AplicacionDescuento.objects.get(descuento=d)
        assert app.monto_aplicado == Decimal("100.00")  # lo realmente descontado
        assert d.saldo_pendiente == Decimal("2900.00")

    def test_sin_lineas_no_hace_nada(self, registro, periodo, trabajador):
        _pension(trabajador, estado="EN_CURSO")
        assert registrar_aplicaciones_cierre(periodo) == 0
        assert AplicacionDescuento.objects.count() == 0


def _interno(trabajador, **extra):
    base = dict(
        personal=trabajador, causal="ROTURA_HERRAMIENTA",
        detalle="Taladro dañado", monto_total=Decimal("400.00"),
        num_cuotas=2, cuota_mensual=Decimal("200.00"), estado="APROBADO",
        consentimiento_firmado=True,
    )
    base.update(extra)
    return DescuentoPlanilla.objects.create(**base)


class TestEngineDescuentosInternos:
    """8c: causales NO judiciales entran solas al cálculo si hay consentimiento."""

    def test_interno_con_consentimiento_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _interno(trabajador)
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"] + Decimal("200.00")

    def test_interno_sin_consentimiento_no_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _interno(trabajador, consentimiento_firmado=False)
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"]

    def test_interno_no_requiere_consentimiento_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _interno(trabajador, consentimiento_firmado=False,
                 requiere_consentimiento=False)
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"] + Decimal("200.00")

    def test_interno_fecha_inicio_futura_no_se_descuenta(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        _interno(trabajador, fecha_inicio_descuento=date(2026, 8, 1))
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"]

    def test_interno_capado_por_saldo(self, registro, trabajador):
        from nominas.engine import calcular_registro
        sin = calcular_registro(registro)
        d = _interno(trabajador, estado="EN_CURSO")
        # Ya se aplicó una cuota: queda saldo 200; y una cuota "gorda" de 300
        d.cuota_mensual = Decimal("300.00")
        d.save(update_fields=["cuota_mensual"])
        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=5,
            monto_aplicado=Decimal("200.00"),
        )
        con = calcular_registro(registro)
        assert con["total_descuentos"] == sin["total_descuentos"] + Decimal("200.00")


class TestCierreDescuentosInternos:
    def test_interno_crea_aplicacion_y_transiciona(self, registro, periodo, trabajador):
        d = _interno(trabajador, estado="APROBADO")
        _linea_judicial(registro, "descuento-interno", "200.00")

        creadas = registrar_aplicaciones_cierre(periodo)
        assert creadas == 1
        d.refresh_from_db()
        assert d.estado == "EN_CURSO"
        assert d.saldo_pendiente == Decimal("200.00")

    def test_interno_completa_y_pasa_a_pagado(self, registro, periodo, trabajador):
        d = _interno(trabajador, estado="EN_CURSO")
        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=5,
            monto_aplicado=Decimal("200.00"),
        )
        _linea_judicial(registro, "descuento-interno", "200.00")

        registrar_aplicaciones_cierre(periodo)
        d.refresh_from_db()
        assert d.saldo_pendiente == Decimal("0")
        assert d.estado == "PAGADO"

    def test_interno_reparte_entre_varias_causales(self, registro, periodo, trabajador):
        d1 = _interno(trabajador, causal="ROTURA_HERRAMIENTA")
        d2 = _interno(trabajador, causal="REPOSICION_UNIFORME",
                      monto_total=Decimal("100.00"), num_cuotas=1,
                      cuota_mensual=Decimal("100.00"))
        # El engine emitió una línea por cada descuento bajo el mismo concepto
        _linea_judicial(registro, "descuento-interno", "200.00")
        _linea_judicial(registro, "descuento-interno", "100.00")

        creadas = registrar_aplicaciones_cierre(periodo)
        assert creadas == 2
        assert AplicacionDescuento.objects.get(descuento=d1).monto_aplicado == Decimal("200.00")
        assert AplicacionDescuento.objects.get(descuento=d2).monto_aplicado == Decimal("100.00")


class TestCierreEndToEnd:
    def test_periodo_cerrar_registra_aplicaciones(self, client, registro, periodo, trabajador):
        from django.contrib.auth.models import User
        from django.urls import reverse
        admin = User.objects.create_user(
            "cierre_admin", password="x", is_superuser=True, is_staff=True)
        client.force_login(admin)

        d = _pension(trabajador, estado="EN_CURSO")
        _linea_judicial(registro, "pension-alimenticia", "600.00")

        resp = client.post(reverse("nominas_periodo_cerrar", args=[periodo.pk]))
        assert resp.status_code == 302
        periodo.refresh_from_db()
        assert periodo.estado == "CERRADO"
        assert AplicacionDescuento.objects.filter(descuento=d).count() == 1
