"""
Tests for the Salarios (Salary Structure) module.
Covers: BandaSalarial, HistorialSalarial, SimulacionIncremento, DetalleSimulacion.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from personal.models import Area, Personal
from salarios.models import (
    BandaSalarial,
    DetalleSimulacion,
    HistorialSalarial,
    SimulacionIncremento,
)

User = get_user_model()


class SalariosTestMixin:
    """Shared setup for salarios tests."""

    def _create_area(self, nombre="Operaciones"):
        return Area.objects.create(nombre=nombre)

    def _create_personal(self, nro_doc="87654321", nombre="Garcia Ramos, Ana"):
        self._create_area()
        return Personal.objects.create(
            nro_doc=nro_doc,
            apellidos_nombres=nombre,
            cargo="Ingeniero",
            tipo_trab="Empleado",
        )

    def _create_user(self, username="admin"):
        return User.objects.create_user(
            username=username,
            password="testpass123",
            is_superuser=True,
        )

    def _create_banda(self, **kwargs):
        defaults = {
            "cargo": "Analista",
            "nivel": "JUNIOR",
            "minimo": Decimal("2000.00"),
            "medio": Decimal("3000.00"),
            "maximo": Decimal("4000.00"),
            "moneda": "PEN",
            "activa": True,
        }
        defaults.update(kwargs)
        return BandaSalarial.objects.create(**defaults)


# ---------------------------------------------------------------------------
# BandaSalarial tests
# ---------------------------------------------------------------------------
class BandaSalarialModelTest(SalariosTestMixin, TestCase):

    def test_create_banda(self):
        banda = self._create_banda()
        assert banda.pk is not None
        assert banda.cargo == "Analista"
        assert banda.nivel == "JUNIOR"

    def test_str_representation(self):
        banda = self._create_banda()
        result = str(banda)
        assert "Analista" in result
        assert "Junior" in result
        assert "2000.00" in result
        assert "4000.00" in result

    def test_unique_together_cargo_nivel(self):
        self._create_banda(cargo="Desarrollador", nivel="SENIOR")
        with pytest.raises(IntegrityError):
            self._create_banda(cargo="Desarrollador", nivel="SENIOR")

    def test_all_nivel_choices(self):
        niveles = ["JUNIOR", "SEMI_SENIOR", "SENIOR", "LEAD", "GERENTE"]
        for i, nivel in enumerate(niveles):
            banda = self._create_banda(
                cargo=f"Cargo_{i}",
                nivel=nivel,
                minimo=Decimal(str(2000 + i * 1000)),
                medio=Decimal(str(3000 + i * 1000)),
                maximo=Decimal(str(4000 + i * 1000)),
            )
            assert banda.nivel == nivel

    def test_moneda_default_pen(self):
        banda = self._create_banda()
        assert banda.moneda == "PEN"

    def test_moneda_usd(self):
        banda = self._create_banda(
            cargo="Consultor", nivel="SENIOR", moneda="USD"
        )
        assert banda.moneda == "USD"

    def test_activa_default_true(self):
        banda = self._create_banda()
        assert banda.activa is True

    def test_inactive_banda(self):
        banda = self._create_banda(
            cargo="Cargo Obsoleto", nivel="SENIOR", activa=False
        )
        assert banda.activa is False


# ---------------------------------------------------------------------------
# BandaSalarial range and calculation tests
# ---------------------------------------------------------------------------
class BandaSalarialCalculationsTest(SalariosTestMixin, TestCase):

    def test_amplitud(self):
        """Amplitud = (max - min) / min * 100."""
        banda = self._create_banda(
            minimo=Decimal("2000.00"),
            medio=Decimal("3000.00"),
            maximo=Decimal("4000.00"),
        )
        # (4000 - 2000) / 2000 * 100 = 100.0
        assert banda.amplitud == 100.0

    def test_amplitud_narrow_band(self):
        banda = self._create_banda(
            cargo="Auxiliar",
            nivel="JUNIOR",
            minimo=Decimal("1800.00"),
            medio=Decimal("2000.00"),
            maximo=Decimal("2200.00"),
        )
        # (2200 - 1800) / 1800 * 100 = 22.2
        assert banda.amplitud == 22.2

    def test_amplitud_zero_minimo(self):
        banda = self._create_banda(
            cargo="Test",
            nivel="LEAD",
            minimo=Decimal("0.00"),
            medio=Decimal("1000.00"),
            maximo=Decimal("2000.00"),
        )
        assert banda.amplitud == Decimal("0")

    def test_compa_ratio_at_midpoint(self):
        banda = self._create_banda(medio=Decimal("3000.00"))
        assert banda.compa_ratio(Decimal("3000.00")) == Decimal("1.000")

    def test_compa_ratio_below_midpoint(self):
        banda = self._create_banda(medio=Decimal("4000.00"))
        assert banda.compa_ratio(Decimal("3000.00")) == Decimal("0.750")

    def test_compa_ratio_above_midpoint(self):
        banda = self._create_banda(medio=Decimal("3000.00"))
        assert banda.compa_ratio(Decimal("3600.00")) == Decimal("1.200")

    def test_compa_ratio_zero_medio(self):
        banda = self._create_banda(
            cargo="Edge",
            nivel="LEAD",
            medio=Decimal("0.00"),
        )
        assert banda.compa_ratio(Decimal("5000.00")) == Decimal("0")

    def test_posicion_en_banda_at_minimo(self):
        banda = self._create_banda(
            minimo=Decimal("2000.00"),
            maximo=Decimal("4000.00"),
        )
        assert banda.posicion_en_banda(Decimal("2000.00")) == 0.0

    def test_posicion_en_banda_at_maximo(self):
        banda = self._create_banda(
            minimo=Decimal("2000.00"),
            maximo=Decimal("4000.00"),
        )
        assert banda.posicion_en_banda(Decimal("4000.00")) == 100.0

    def test_posicion_en_banda_midpoint(self):
        banda = self._create_banda(
            minimo=Decimal("2000.00"),
            maximo=Decimal("4000.00"),
        )
        assert banda.posicion_en_banda(Decimal("3000.00")) == 50.0

    def test_posicion_en_banda_below_minimo(self):
        banda = self._create_banda(
            minimo=Decimal("2000.00"),
            maximo=Decimal("4000.00"),
        )
        # Below min gives negative position
        result = banda.posicion_en_banda(Decimal("1000.00"))
        assert result == -50.0

    def test_posicion_en_banda_zero_range(self):
        banda = self._create_banda(
            cargo="Flat",
            nivel="LEAD",
            minimo=Decimal("3000.00"),
            medio=Decimal("3000.00"),
            maximo=Decimal("3000.00"),
        )
        assert banda.posicion_en_banda(Decimal("3000.00")) == Decimal("0")


# ---------------------------------------------------------------------------
# BandaSalarial ordering tests
# ---------------------------------------------------------------------------
class BandaSalarialOrderingTest(SalariosTestMixin, TestCase):

    def test_ordering_by_cargo_then_nivel(self):
        self._create_banda(cargo="Analista", nivel="SENIOR",
                           minimo=Decimal("4000"), medio=Decimal("5000"), maximo=Decimal("6000"))
        self._create_banda(cargo="Analista", nivel="JUNIOR",
                           minimo=Decimal("2000"), medio=Decimal("3000"), maximo=Decimal("4000"))
        self._create_banda(cargo="Auxiliar", nivel="JUNIOR",
                           minimo=Decimal("1500"), medio=Decimal("2000"), maximo=Decimal("2500"))

        bandas = list(BandaSalarial.objects.values_list("cargo", "nivel"))
        # Default ordering: ['cargo', 'nivel']
        assert bandas[0] == ("Analista", "JUNIOR")
        assert bandas[1] == ("Analista", "SENIOR")
        assert bandas[2] == ("Auxiliar", "JUNIOR")

    def test_filter_active_bands(self):
        self._create_banda(cargo="Vigente", nivel="JUNIOR", activa=True)
        self._create_banda(cargo="Obsoleta", nivel="SENIOR", activa=False)
        active = BandaSalarial.objects.filter(activa=True)
        assert active.count() == 1
        assert active.first().cargo == "Vigente"


# ---------------------------------------------------------------------------
# HistorialSalarial tests
# ---------------------------------------------------------------------------
class HistorialSalarialModelTest(SalariosTestMixin, TestCase):

    def test_create_historial(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("3000.00"),
            remuneracion_nueva=Decimal("3500.00"),
            motivo="INCREMENTO",
        )
        assert historial.pk is not None

    def test_str_representation(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("3000.00"),
            remuneracion_nueva=Decimal("3500.00"),
            motivo="INCREMENTO",
        )
        result = str(historial)
        assert "Garcia Ramos, Ana" in result
        assert "Incremento Anual" in result

    def test_porcentaje_incremento(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 3, 1),
            remuneracion_anterior=Decimal("4000.00"),
            remuneracion_nueva=Decimal("4400.00"),
            motivo="INCREMENTO",
        )
        # (4400 - 4000) / 4000 * 100 = 10.0
        assert historial.porcentaje_incremento == Decimal("10.00")

    def test_porcentaje_incremento_zero_anterior(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("0.00"),
            remuneracion_nueva=Decimal("2000.00"),
            motivo="INGRESO",
        )
        assert historial.porcentaje_incremento == Decimal("0")

    def test_diferencia(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 6, 1),
            remuneracion_anterior=Decimal("5000.00"),
            remuneracion_nueva=Decimal("5800.00"),
            motivo="PROMOCION",
        )
        assert historial.diferencia == Decimal("800.00")

    def test_diferencia_negative(self):
        """Salary reduction (ajuste) produces negative diferencia."""
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 6, 1),
            remuneracion_anterior=Decimal("5000.00"),
            remuneracion_nueva=Decimal("4500.00"),
            motivo="AJUSTE",
        )
        assert historial.diferencia == Decimal("-500.00")

    def test_all_motivo_choices(self):
        personal = self._create_personal()
        motivos = ["INGRESO", "INCREMENTO", "PROMOCION", "AJUSTE", "REVALORACION"]
        for i, motivo in enumerate(motivos):
            HistorialSalarial.objects.create(
                personal=personal,
                fecha_efectiva=date(2026, 1 + i, 1),
                remuneracion_anterior=Decimal("3000.00"),
                remuneracion_nueva=Decimal("3100.00"),
                motivo=motivo,
            )
        assert HistorialSalarial.objects.filter(personal=personal).count() == 5


# ---------------------------------------------------------------------------
# HistorialSalarial tracking tests
# ---------------------------------------------------------------------------
class HistorialSalarialTrackingTest(SalariosTestMixin, TestCase):

    def test_ordering_most_recent_first(self):
        personal = self._create_personal()
        HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2025, 1, 1),
            remuneracion_anterior=Decimal("2000.00"),
            remuneracion_nueva=Decimal("2500.00"),
            motivo="INGRESO",
        )
        HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("2500.00"),
            remuneracion_nueva=Decimal("3000.00"),
            motivo="INCREMENTO",
        )
        historial = list(
            HistorialSalarial.objects.filter(personal=personal).values_list(
                "fecha_efectiva", flat=True
            )
        )
        assert historial[0] == date(2026, 1, 1)
        assert historial[1] == date(2025, 1, 1)

    def test_salary_progression_chain(self):
        """Verify that a chain of salary changes tracks correctly."""
        personal = self._create_personal()
        changes = [
            (date(2024, 1, 1), Decimal("0"), Decimal("2500.00"), "INGRESO"),
            (date(2025, 1, 1), Decimal("2500.00"), Decimal("2800.00"), "INCREMENTO"),
            (date(2025, 7, 1), Decimal("2800.00"), Decimal("3500.00"), "PROMOCION"),
            (date(2026, 1, 1), Decimal("3500.00"), Decimal("3700.00"), "AJUSTE"),
        ]
        for fecha, anterior, nueva, motivo in changes:
            HistorialSalarial.objects.create(
                personal=personal,
                fecha_efectiva=fecha,
                remuneracion_anterior=anterior,
                remuneracion_nueva=nueva,
                motivo=motivo,
            )
        count = HistorialSalarial.objects.filter(personal=personal).count()
        assert count == 4
        latest = HistorialSalarial.objects.filter(personal=personal).first()
        assert latest.remuneracion_nueva == Decimal("3700.00")
        assert latest.motivo == "AJUSTE"

    def test_historial_with_aprobado_por(self):
        personal = self._create_personal()
        user = self._create_user()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 3, 1),
            remuneracion_anterior=Decimal("3000.00"),
            remuneracion_nueva=Decimal("3300.00"),
            motivo="INCREMENTO",
            aprobado_por=user,
        )
        assert historial.aprobado_por == user

    def test_historial_with_observaciones(self):
        personal = self._create_personal()
        historial = HistorialSalarial.objects.create(
            personal=personal,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("3000.00"),
            remuneracion_nueva=Decimal("3300.00"),
            motivo="INCREMENTO",
            observaciones="Incremento anual por desempeno destacado",
        )
        assert "desempeno" in historial.observaciones

    def test_multiple_employees_independent_histories(self):
        emp1 = self._create_personal(nro_doc="11111111", nombre="Perez, Juan")
        emp2 = self._create_personal(nro_doc="22222222", nombre="Diaz, Maria")
        HistorialSalarial.objects.create(
            personal=emp1,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("2000.00"),
            remuneracion_nueva=Decimal("2200.00"),
            motivo="INCREMENTO",
        )
        HistorialSalarial.objects.create(
            personal=emp2,
            fecha_efectiva=date(2026, 1, 1),
            remuneracion_anterior=Decimal("5000.00"),
            remuneracion_nueva=Decimal("5500.00"),
            motivo="PROMOCION",
        )
        assert HistorialSalarial.objects.filter(personal=emp1).count() == 1
        assert HistorialSalarial.objects.filter(personal=emp2).count() == 1


# ---------------------------------------------------------------------------
# SimulacionIncremento tests
# ---------------------------------------------------------------------------
class SimulacionIncrementoTest(SalariosTestMixin, TestCase):

    def test_create_simulacion(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Incremento Anual 2026",
            fecha=date(2026, 4, 1),
            estado="BORRADOR",
            tipo="PORCENTAJE",
            creado_por=user,
        )
        assert sim.pk is not None
        assert sim.estado == "BORRADOR"

    def test_total_empleados(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Sim Test",
            fecha=date(2026, 4, 1),
            creado_por=user,
        )
        emp1 = self._create_personal(nro_doc="33333333", nombre="Uno, Test")
        emp2 = self._create_personal(nro_doc="44444444", nombre="Dos, Test")
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp1,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("300.00"),
        )
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp2,
            remuneracion_actual=Decimal("4000.00"),
            incremento_propuesto=Decimal("400.00"),
        )
        assert sim.total_empleados == 2

    def test_costo_total(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Sim Costo",
            fecha=date(2026, 4, 1),
            creado_por=user,
        )
        emp = self._create_personal()
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("300.00"),
            aprobado=True,
        )
        assert sim.costo_total == Decimal("300.00")
        assert sim.costo_anual == Decimal("3600.00")

    def test_dentro_presupuesto_true(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Sim Budget OK",
            fecha=date(2026, 4, 1),
            presupuesto_total=Decimal("50000.00"),
            creado_por=user,
        )
        emp = self._create_personal()
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("200.00"),
            aprobado=True,
        )
        # Annual cost = 200 * 12 = 2400 < 50000
        assert sim.dentro_presupuesto is True

    def test_dentro_presupuesto_false(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Sim Over Budget",
            fecha=date(2026, 4, 1),
            presupuesto_total=Decimal("1000.00"),
            creado_por=user,
        )
        emp = self._create_personal()
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("500.00"),
            aprobado=True,
        )
        # Annual cost = 500 * 12 = 6000 > 1000
        assert sim.dentro_presupuesto is False

    def test_dentro_presupuesto_no_limit(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Sim No Limit",
            fecha=date(2026, 4, 1),
            presupuesto_total=None,
            creado_por=user,
        )
        assert sim.dentro_presupuesto is True


# ---------------------------------------------------------------------------
# DetalleSimulacion tests
# ---------------------------------------------------------------------------
class DetalleSimulacionTest(SalariosTestMixin, TestCase):

    def test_remuneracion_nueva(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Det Test", fecha=date(2026, 4, 1), creado_por=user
        )
        emp = self._create_personal()
        detalle = DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("450.00"),
        )
        assert detalle.remuneracion_nueva == Decimal("3450.00")

    def test_porcentaje_incremento(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Det Pct", fecha=date(2026, 4, 1), creado_por=user
        )
        emp = self._create_personal()
        detalle = DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("4000.00"),
            incremento_propuesto=Decimal("400.00"),
        )
        assert detalle.porcentaje_incremento == Decimal("10.00")

    def test_unique_together_simulacion_personal(self):
        user = self._create_user()
        sim = SimulacionIncremento.objects.create(
            nombre="Det Unique", fecha=date(2026, 4, 1), creado_por=user
        )
        emp = self._create_personal()
        DetalleSimulacion.objects.create(
            simulacion=sim,
            personal=emp,
            remuneracion_actual=Decimal("3000.00"),
            incremento_propuesto=Decimal("300.00"),
        )
        with pytest.raises(IntegrityError):
            DetalleSimulacion.objects.create(
                simulacion=sim,
                personal=emp,
                remuneracion_actual=Decimal("3000.00"),
                incremento_propuesto=Decimal("500.00"),
            )
