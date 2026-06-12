"""
Tests de modelos de descuentos (la app tenía 0 tests y toca planilla).

Cubre DescuentoPlanilla: cálculo automático de cuota, consentimiento
judicial, saldo/progreso con aplicaciones, y el filtro de activos.
"""
from datetime import date
from decimal import Decimal

import pytest

from descuentos.models import AplicacionDescuento, DescuentoPlanilla
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


def _descuento(trabajador, **extra):
    base = dict(
        personal=trabajador,
        causal="ROTURA_HERRAMIENTA",
        detalle="Taladro dañado",
        monto_total=Decimal("1000.00"),
        num_cuotas=4,
        estado="PENDIENTE",
    )
    base.update(extra)
    return DescuentoPlanilla.objects.create(**base)


class TestDescuentoPlanilla:
    def test_cuota_mensual_se_autocalcula(self, trabajador):
        d = _descuento(trabajador)  # 1000 / 4
        assert d.cuota_mensual == Decimal("250.00")

    def test_cuota_mensual_explicita_se_respeta(self, trabajador):
        d = _descuento(trabajador, cuota_mensual=Decimal("100.00"))
        assert d.cuota_mensual == Decimal("100.00")

    def test_cuota_con_redondeo(self, trabajador):
        d = _descuento(trabajador, monto_total=Decimal("100.00"), num_cuotas=3)
        assert d.cuota_mensual == Decimal("33.33")

    @pytest.mark.parametrize("causal", ["EMBARGO_JUDICIAL", "PENSION_ALIMENTICIA"])
    def test_judicial_no_requiere_consentimiento(self, trabajador, causal):
        d = _descuento(trabajador, causal=causal, requiere_consentimiento=True)
        assert d.requiere_consentimiento is False

    def test_no_judicial_si_requiere_consentimiento(self, trabajador):
        d = _descuento(trabajador)
        assert d.requiere_consentimiento is True

    def test_saldo_y_progreso_con_aplicaciones(self, trabajador):
        d = _descuento(trabajador, estado="EN_CURSO")
        assert d.saldo_pendiente == Decimal("1000.00")
        assert d.cuotas_pendientes == 4
        assert d.progreso_pct == 0

        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=6,
            monto_aplicado=Decimal("250.00"),
        )
        assert d.saldo_pendiente == Decimal("750.00")
        assert d.cuotas_aplicadas == 1
        assert d.cuotas_pendientes == 3
        assert d.progreso_pct == 25.0

    def test_saldo_no_negativo(self, trabajador):
        d = _descuento(trabajador, estado="EN_CURSO")
        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=6,
            monto_aplicado=Decimal("1500.00"),  # más que el total
        )
        assert d.saldo_pendiente == Decimal("0")

    def test_aplicacion_unica_por_periodo(self, trabajador):
        from django.db import IntegrityError
        d = _descuento(trabajador, estado="EN_CURSO")
        AplicacionDescuento.objects.create(
            descuento=d, periodo_anio=2026, periodo_mes=6,
            monto_aplicado=Decimal("250.00"),
        )
        with pytest.raises(IntegrityError):
            AplicacionDescuento.objects.create(
                descuento=d, periodo_anio=2026, periodo_mes=6,
                monto_aplicado=Decimal("250.00"),
            )

    def test_descuentos_activos_para(self, trabajador):
        _descuento(trabajador, estado="PENDIENTE")
        _descuento(trabajador, estado="ANULADO")
        aprobado = _descuento(trabajador, estado="APROBADO")
        en_curso = _descuento(trabajador, estado="EN_CURSO")
        activos = set(DescuentoPlanilla.descuentos_activos_para(trabajador))
        assert activos == {aprobado, en_curso}
