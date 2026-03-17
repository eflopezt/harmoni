"""
Tests for the Prestamos (Loans) module.
Covers: Prestamo model, CuotaPrestamo, TipoPrestamo, business logic,
cuota generation, estado transitions, edge cases, and payroll integration.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from personal.models import Area, Personal
from prestamos.models import CuotaPrestamo, Prestamo, TipoPrestamo

User = get_user_model()


class PrestamoTestMixin:
    """Shared setup for prestamo tests."""

    def _create_area(self, nombre="Administracion"):
        return Area.objects.create(nombre=nombre)

    def _create_personal(self, nro_doc="12345678", nombre="Lopez Torres, Edwin"):
        area = self._create_area()
        return Personal.objects.create(
            nro_doc=nro_doc,
            apellidos_nombres=nombre,
            cargo="Analista",
            tipo_trab="Empleado",
        )

    def _create_tipo_prestamo(self, **kwargs):
        defaults = {
            "nombre": "Prestamo Personal",
            "codigo": "personal",
            "max_cuotas": 12,
            "tasa_interes_mensual": Decimal("0.000"),
            "requiere_aprobacion": True,
            "activo": True,
        }
        defaults.update(kwargs)
        return TipoPrestamo.objects.create(**defaults)

    def _create_user(self, username="admin", is_superuser=True):
        return User.objects.create_user(
            username=username,
            password="testpass123",
            is_superuser=is_superuser,
        )


# ---------------------------------------------------------------------------
# TipoPrestamo tests
# ---------------------------------------------------------------------------
class TipoPrestamoModelTest(PrestamoTestMixin, TestCase):

    def test_create_tipo_prestamo(self):
        tipo = self._create_tipo_prestamo()
        assert tipo.pk is not None
        assert str(tipo) == "Prestamo Personal"

    def test_tipo_prestamo_unique_codigo(self):
        self._create_tipo_prestamo()
        with pytest.raises(Exception):
            self._create_tipo_prestamo()

    def test_tipo_prestamo_defaults(self):
        tipo = self._create_tipo_prestamo()
        assert tipo.max_cuotas == 12
        assert tipo.tasa_interes_mensual == Decimal("0.000")
        assert tipo.requiere_aprobacion is True
        assert tipo.activo is True
        assert tipo.monto_maximo is None

    def test_tipo_with_monto_maximo(self):
        tipo = self._create_tipo_prestamo(
            nombre="Adelanto Sueldo",
            codigo="adelanto-sueldo",
            monto_maximo=Decimal("5000.00"),
            max_cuotas=1,
        )
        assert tipo.monto_maximo == Decimal("5000.00")
        assert tipo.max_cuotas == 1

    def test_tipo_con_interes(self):
        tipo = self._create_tipo_prestamo(
            nombre="Emergencia",
            codigo="emergencia",
            tasa_interes_mensual=Decimal("1.500"),
        )
        assert tipo.tasa_interes_mensual == Decimal("1.500")


# ---------------------------------------------------------------------------
# Prestamo creation tests
# ---------------------------------------------------------------------------
class PrestamoCreationTest(PrestamoTestMixin, TestCase):

    def test_create_prestamo_basic(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("3000.00"),
            num_cuotas=6,
        )
        assert prestamo.pk is not None
        assert prestamo.estado == "BORRADOR"
        assert prestamo.fecha_solicitud == date.today()

    def test_str_representation(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("2000.00"),
            num_cuotas=4,
        )
        expected = f"Prestamo Personal — Lopez Torres, Edwin — S/ 2000.00"
        assert str(prestamo) == expected

    def test_monto_efectivo_without_aprobado(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("5000.00"),
            num_cuotas=10,
        )
        assert prestamo.monto_efectivo == Decimal("5000.00")

    def test_monto_efectivo_with_aprobado(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("5000.00"),
            monto_aprobado=Decimal("3000.00"),
            num_cuotas=6,
        )
        assert prestamo.monto_efectivo == Decimal("3000.00")

    def test_default_saldo_pendiente_equals_monto(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1200.00"),
            num_cuotas=3,
        )
        assert prestamo.saldo_pendiente == Decimal("1200.00")

    def test_cuotas_pagadas_initially_zero(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=2,
        )
        assert prestamo.cuotas_pagadas == 0

    def test_porcentaje_avance_initially_zero(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=4,
        )
        assert prestamo.porcentaje_avance == 0


# ---------------------------------------------------------------------------
# Cuota generation tests
# ---------------------------------------------------------------------------
class CuotaGenerationTest(PrestamoTestMixin, TestCase):

    def test_generar_cuotas_count(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("6000.00"),
            num_cuotas=6,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        assert prestamo.cuotas.count() == 6

    def test_cuotas_sum_equals_monto(self):
        """Sum of all cuotas must equal the approved amount exactly."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=3,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        total = sum(c.monto for c in prestamo.cuotas.all())
        assert total == Decimal("1000.00")

    def test_cuotas_sum_with_indivisible_amount(self):
        """When amount is not evenly divisible, last cuota absorbs residual."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=7,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        total = sum(c.monto for c in prestamo.cuotas.all())
        assert total == Decimal("1000.00")

    def test_cuota_mensual_is_set(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1200.00"),
            num_cuotas=4,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        prestamo.refresh_from_db()
        assert prestamo.cuota_mensual == Decimal("300.00")

    def test_cuotas_have_sequential_numbers(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("2400.00"),
            num_cuotas=4,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        nums = list(prestamo.cuotas.values_list("numero", flat=True).order_by("numero"))
        assert nums == [1, 2, 3, 4]

    def test_cuotas_have_monthly_periods(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        fecha_desc = date(2026, 4, 1)
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("3000.00"),
            num_cuotas=3,
            estado="PENDIENTE",
            fecha_primer_descuento=fecha_desc,
        )
        prestamo.aprobar(user)
        periodos = list(
            prestamo.cuotas.order_by("numero").values_list("periodo", flat=True)
        )
        assert periodos == [date(2026, 4, 1), date(2026, 5, 1), date(2026, 6, 1)]

    def test_generar_cuotas_replaces_existing(self):
        """Calling generar_cuotas again replaces old cuotas."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1200.00"),
            num_cuotas=3,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        assert prestamo.cuotas.count() == 3
        # Regenerate
        prestamo.generar_cuotas()
        assert prestamo.cuotas.count() == 3

    def test_single_cuota(self):
        """A one-cuota loan (adelanto de sueldo style)."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo(
            nombre="Adelanto", codigo="adelanto", max_cuotas=1
        )
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("500.00"),
            num_cuotas=1,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        assert prestamo.cuotas.count() == 1
        cuota = prestamo.cuotas.first()
        assert cuota.monto == Decimal("500.00")


# ---------------------------------------------------------------------------
# Estado transition tests
# ---------------------------------------------------------------------------
class PrestamoEstadoTransitionTest(PrestamoTestMixin, TestCase):

    def test_aprobar_sets_estado_en_curso(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("2000.00"),
            num_cuotas=4,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        prestamo.refresh_from_db()
        assert prestamo.estado == "EN_CURSO"

    def test_aprobar_sets_aprobado_por(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("2000.00"),
            num_cuotas=4,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        prestamo.refresh_from_db()
        assert prestamo.aprobado_por == user
        assert prestamo.fecha_aprobacion == date.today()

    def test_aprobar_with_custom_monto(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("5000.00"),
            num_cuotas=5,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user, monto_aprobado=Decimal("3000.00"))
        prestamo.refresh_from_db()
        assert prestamo.monto_aprobado == Decimal("3000.00")
        assert prestamo.monto_efectivo == Decimal("3000.00")
        # Cuotas should be based on approved amount
        total = sum(c.monto for c in prestamo.cuotas.all())
        assert total == Decimal("3000.00")

    def test_aprobar_inherits_tasa_from_tipo(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo(
            nombre="Con Interes",
            codigo="con-interes",
            tasa_interes_mensual=Decimal("2.500"),
        )
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=2,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        prestamo.refresh_from_db()
        assert prestamo.tasa_interes == Decimal("2.500")

    def test_cancel_prestamo(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=2,
            estado="PENDIENTE",
        )
        prestamo.estado = "CANCELADO"
        prestamo.save(update_fields=["estado"])
        prestamo.refresh_from_db()
        assert prestamo.estado == "CANCELADO"

    def test_full_lifecycle_borrador_to_pagado(self):
        """BORRADOR -> PENDIENTE -> EN_CURSO -> PAGADO."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("600.00"),
            num_cuotas=2,
            estado="BORRADOR",
        )
        assert prestamo.estado == "BORRADOR"

        # Move to PENDIENTE
        prestamo.estado = "PENDIENTE"
        prestamo.save(update_fields=["estado"])

        # Approve
        prestamo.aprobar(user)
        prestamo.refresh_from_db()
        assert prestamo.estado == "EN_CURSO"

        # Pay all cuotas
        for cuota in prestamo.cuotas.order_by("numero"):
            cuota.registrar_pago()

        prestamo.refresh_from_db()
        assert prestamo.estado == "PAGADO"
        assert prestamo.saldo_pendiente == Decimal("0.00")
        assert prestamo.porcentaje_avance == 100


# ---------------------------------------------------------------------------
# CuotaPrestamo payment tests
# ---------------------------------------------------------------------------
class CuotaPagoTest(PrestamoTestMixin, TestCase):

    def _create_approved_prestamo(self, monto="1200.00", cuotas=3):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal(monto),
            num_cuotas=cuotas,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        return prestamo

    def test_registrar_pago_full(self):
        prestamo = self._create_approved_prestamo()
        cuota = prestamo.cuotas.order_by("numero").first()
        cuota.registrar_pago()
        cuota.refresh_from_db()
        assert cuota.estado == "PAGADO"
        assert cuota.monto_pagado == cuota.monto
        assert cuota.fecha_pago == date.today()

    def test_registrar_pago_partial(self):
        prestamo = self._create_approved_prestamo()
        cuota = prestamo.cuotas.order_by("numero").first()
        cuota.registrar_pago(monto=Decimal("100.00"))
        cuota.refresh_from_db()
        assert cuota.estado == "PARCIAL"
        assert cuota.monto_pagado == Decimal("100.00")

    def test_registrar_pago_with_referencia(self):
        prestamo = self._create_approved_prestamo()
        cuota = prestamo.cuotas.order_by("numero").first()
        cuota.registrar_pago(referencia="NOM-2026-03")
        cuota.refresh_from_db()
        assert cuota.referencia_nomina == "NOM-2026-03"

    def test_saldo_decreases_after_payment(self):
        prestamo = self._create_approved_prestamo(monto="1200.00", cuotas=3)
        cuota1 = prestamo.cuotas.order_by("numero").first()
        cuota1.registrar_pago()
        # 1200 / 3 = 400 per cuota, saldo should be 800
        assert prestamo.saldo_pendiente == Decimal("800.00")

    def test_porcentaje_avance_after_payments(self):
        prestamo = self._create_approved_prestamo(monto="800.00", cuotas=4)
        cuotas = list(prestamo.cuotas.order_by("numero"))
        cuotas[0].registrar_pago()
        assert prestamo.porcentaje_avance == 25
        cuotas[1].registrar_pago()
        assert prestamo.porcentaje_avance == 50

    def test_auto_close_prestamo_on_final_payment(self):
        """Prestamo should auto-transition to PAGADO when all cuotas are paid."""
        prestamo = self._create_approved_prestamo(monto="600.00", cuotas=2)
        for cuota in prestamo.cuotas.order_by("numero"):
            cuota.registrar_pago()
        prestamo.refresh_from_db()
        assert prestamo.estado == "PAGADO"

    def test_auto_close_with_condonado_cuotas(self):
        """Condonado cuotas should also count towards closing the loan."""
        prestamo = self._create_approved_prestamo(monto="900.00", cuotas=3)
        cuotas = list(prestamo.cuotas.order_by("numero"))
        cuotas[0].registrar_pago()
        # Condonar cuota 2
        cuotas[1].estado = "CONDONADO"
        cuotas[1].save()
        # Pay last cuota
        cuotas[2].registrar_pago()
        prestamo.refresh_from_db()
        assert prestamo.estado == "PAGADO"

    def test_cuota_str(self):
        prestamo = self._create_approved_prestamo(monto="1000.00", cuotas=5)
        cuota = prestamo.cuotas.order_by("numero").first()
        expected = f"Cuota 1/5 — S/ {cuota.monto}"
        assert str(cuota) == expected


# ---------------------------------------------------------------------------
# Payroll integration / deduction tests
# ---------------------------------------------------------------------------
class PayrollDeductionTest(PrestamoTestMixin, TestCase):
    """Test cuota as payroll deduction (referencia_nomina linking)."""

    def test_cuota_referencia_nomina_empty_by_default(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("600.00"),
            num_cuotas=2,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        cuota = prestamo.cuotas.first()
        assert cuota.referencia_nomina == ""

    def test_pago_via_nomina(self):
        """Simulate payroll deduction by registering payment with nomina reference."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=2,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        cuota = prestamo.cuotas.order_by("numero").first()
        cuota.registrar_pago(
            monto=cuota.monto,
            fecha=date(2026, 3, 30),
            referencia="NOMINA-2026-03-001",
        )
        cuota.refresh_from_db()
        assert cuota.estado == "PAGADO"
        assert cuota.referencia_nomina == "NOMINA-2026-03-001"
        assert cuota.fecha_pago == date(2026, 3, 30)

    def test_pending_cuotas_for_period(self):
        """Query pending cuotas for a given payroll period."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1200.00"),
            num_cuotas=4,
            fecha_primer_descuento=date(2026, 3, 1),
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        # Query cuotas pending for March 2026
        pending = CuotaPrestamo.objects.filter(
            prestamo__personal=personal,
            estado="PENDIENTE",
            periodo__year=2026,
            periodo__month=3,
        )
        assert pending.count() == 1
        assert pending.first().monto == Decimal("300.00")


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class PrestamoEdgeCasesTest(PrestamoTestMixin, TestCase):

    def test_minimum_monto_validator(self):
        """Monto solicitado must be at least 1.00 (model validator)."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("0.50"),
            num_cuotas=1,
        )
        with pytest.raises(ValidationError):
            prestamo.full_clean()

    def test_zero_monto_fails_validation(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("0.00"),
            num_cuotas=1,
        )
        with pytest.raises(ValidationError):
            prestamo.full_clean()

    def test_negative_monto_fails_validation(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("-100.00"),
            num_cuotas=1,
        )
        with pytest.raises(ValidationError):
            prestamo.full_clean()

    def test_max_cuotas_validator(self):
        """num_cuotas cannot exceed 60 (MaxValueValidator)."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("10000.00"),
            num_cuotas=61,
        )
        with pytest.raises(ValidationError):
            prestamo.full_clean()

    def test_zero_cuotas_fails_validation(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=0,
        )
        with pytest.raises(ValidationError):
            prestamo.full_clean()

    def test_large_monto_prestamo(self):
        """Large loan amount should still generate correct cuotas."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("99999.99"),
            num_cuotas=12,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        total = sum(c.monto for c in prestamo.cuotas.all())
        assert total == Decimal("99999.99")

    def test_monto_maximo_tipo_validation_in_view_logic(self):
        """TipoPrestamo.monto_maximo is enforced in view, but model stores it."""
        tipo = self._create_tipo_prestamo(
            nombre="Limitado",
            codigo="limitado",
            monto_maximo=Decimal("2000.00"),
        )
        assert tipo.monto_maximo == Decimal("2000.00")
        # The model itself does not enforce it, the view does the check
        personal = self._create_personal()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("5000.00"),  # exceeds max
            num_cuotas=5,
        )
        # Model allows it (validation is in the view layer)
        assert prestamo.pk is not None

    def test_porcentaje_avance_zero_cuotas_edge(self):
        """porcentaje_avance handles zero num_cuotas gracefully."""
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo()
        prestamo = Prestamo(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1000.00"),
            num_cuotas=0,
        )
        # num_cuotas=0 would fail validation, but property handles it
        assert prestamo.porcentaje_avance == 0


# ---------------------------------------------------------------------------
# Adelanto (advance) type tests
# ---------------------------------------------------------------------------
class AdelantoTypeTest(PrestamoTestMixin, TestCase):
    """Tests specific to adelanto-type loans (single cuota, special limits)."""

    def test_adelanto_sueldo_type(self):
        tipo = self._create_tipo_prestamo(
            nombre="Adelanto de Sueldo",
            codigo="adelanto-sueldo",
            max_cuotas=1,
            requiere_aprobacion=False,
            monto_maximo=Decimal("3000.00"),
        )
        assert tipo.max_cuotas == 1
        assert tipo.requiere_aprobacion is False

    def test_adelanto_gratificacion_type(self):
        tipo = self._create_tipo_prestamo(
            nombre="Adelanto de Gratificacion",
            codigo="adelanto-grati",
            max_cuotas=1,
            monto_maximo=Decimal("5000.00"),
        )
        assert tipo.monto_maximo == Decimal("5000.00")

    def test_adelanto_single_cuota_payment(self):
        personal = self._create_personal()
        tipo = self._create_tipo_prestamo(
            nombre="Adelanto Rapido",
            codigo="adelanto-rapido",
            max_cuotas=1,
            requiere_aprobacion=False,
        )
        user = self._create_user()
        prestamo = Prestamo.objects.create(
            personal=personal,
            tipo=tipo,
            monto_solicitado=Decimal("1500.00"),
            num_cuotas=1,
            estado="PENDIENTE",
        )
        prestamo.aprobar(user)
        assert prestamo.cuotas.count() == 1
        cuota = prestamo.cuotas.first()
        assert cuota.monto == Decimal("1500.00")
        cuota.registrar_pago()
        prestamo.refresh_from_db()
        assert prestamo.estado == "PAGADO"

    def test_multiple_adelanto_types_coexist(self):
        """Multiple loan types can exist simultaneously."""
        types_data = [
            ("Adelanto Sueldo", "adel-sueldo", 1, Decimal("3000.00")),
            ("Adelanto Grati", "adel-grati", 1, Decimal("5000.00")),
            ("Prestamo Emergencia", "emergencia", 6, None),
            ("Prestamo Personal", "personal-lp", 24, None),
        ]
        for nombre, codigo, cuotas, maximo in types_data:
            TipoPrestamo.objects.create(
                nombre=nombre,
                codigo=codigo,
                max_cuotas=cuotas,
                monto_maximo=maximo,
            )
        assert TipoPrestamo.objects.count() == 4
