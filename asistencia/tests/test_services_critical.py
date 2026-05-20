"""
Tests críticos para los services más usados de asistencia.

Cubre:
- periodo_helper.get_periodo() — casos edge bisiesto, febrero de 28, cruce de año
- _helpers.calcular_almuerzo_h — descuento de refrigerio
- _helpers.cap_horas_dia — tope sanitario 16h/día
- _helpers.calcular_horas_marcadas_desde_horarios — incluye turno nocturno (overnight)
- processor.redondear_media_hora — redondeo a 0.5h
- processor module — importable y constantes esperadas

Estos servicios son llamados en cada importación de tareo y en cada edición
manual, así que un bug aquí explota silenciosamente en planilla.
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from asistencia.services.periodo_helper import (
    TIPO_MES,
    TIPO_MES_CORTE,
    get_periodo,
)
from asistencia.services._helpers import (
    HORAS_MAX_DIA,
    calcular_almuerzo_h,
    calcular_horas_marcadas_desde_horarios,
    cap_horas_dia,
)
from asistencia.services.processor import redondear_media_hora


# ═════════════════════════════════════════════════════════════════════════════
# periodo_helper.get_periodo — casos edge
# ═════════════════════════════════════════════════════════════════════════════

class TestPeriodoEdgeCases:

    def test_mes_julio_2024_tiene_31_dias_en_bisiesto(self):
        """Julio 2024 (año bisiesto) tiene 31 días — no aplica el bisiesto pero
        verificamos que el cálculo es estable."""
        p = get_periodo("MES", 2024, 7)
        assert p.fecha_inicio == date(2024, 7, 1)
        assert p.fecha_fin == date(2024, 7, 31)
        assert p.dias == 31

    def test_mes_febrero_2024_bisiesto_29_dias(self):
        p = get_periodo("MES", 2024, 2)
        assert p.fecha_fin == date(2024, 2, 29)
        assert p.dias == 29

    def test_mes_febrero_2025_no_bisiesto_28_dias(self):
        p = get_periodo("MES", 2025, 2)
        assert p.fecha_fin == date(2025, 2, 28)
        assert p.dias == 28

    def test_mes_diciembre_2026_31_dias(self):
        p = get_periodo("MES", 2026, 12)
        assert p.fecha_fin == date(2026, 12, 31)
        assert p.dias == 31

    def test_mes_invalido_lanza_value_error(self):
        with pytest.raises(ValueError):
            get_periodo("MES", 2026, 0)
        with pytest.raises(ValueError):
            get_periodo("MES", 2026, 13)

    @pytest.mark.django_db
    def test_mes_corte_cruce_diciembre_enero(self):
        """Mes de corte ENERO debe arrancar el 22 de diciembre del año previo."""
        p = get_periodo("MES_CORTE", 2027, 1)
        assert p.tipo == TIPO_MES_CORTE
        assert p.fecha_inicio == date(2026, 12, 22)
        assert p.fecha_fin == date(2027, 1, 21)

    @pytest.mark.django_db
    def test_mes_corte_mes_normal_22_al_21(self):
        """Junio: ciclo arranca el 22-mayo y termina el 21-junio."""
        p = get_periodo("MES_CORTE", 2026, 6)
        assert p.fecha_inicio == date(2026, 5, 22)
        assert p.fecha_fin == date(2026, 6, 21)


# ═════════════════════════════════════════════════════════════════════════════
# processor.redondear_media_hora
# ═════════════════════════════════════════════════════════════════════════════

class TestRedondearMediaHora:

    def test_redondea_0_24_a_cero(self):
        assert redondear_media_hora(Decimal("0.24")) == Decimal("0.0")

    def test_redondea_0_25_a_media(self):
        """0.25 con ROUND_HALF_UP redondea hacia arriba."""
        assert redondear_media_hora(Decimal("0.25")) == Decimal("0.5")

    def test_redondea_0_78_a_uno(self):
        assert redondear_media_hora(Decimal("0.78")) == Decimal("1.0")

    def test_redondea_2_08_a_dos(self):
        assert redondear_media_hora(Decimal("2.08")) == Decimal("2.0")

    def test_redondea_1_62_a_1_5(self):
        assert redondear_media_hora(Decimal("1.62")) == Decimal("1.5")

    def test_acepta_float(self):
        assert redondear_media_hora(3.75) == Decimal("4.0")

    def test_acepta_int(self):
        assert redondear_media_hora(2) == Decimal("2.0")

    def test_none_retorna_cero(self):
        assert redondear_media_hora(None) == Decimal("0")


# ═════════════════════════════════════════════════════════════════════════════
# _helpers.calcular_almuerzo_h
# ═════════════════════════════════════════════════════════════════════════════

class TestCalcularAlmuerzo:

    def test_jornada_estandar_descuenta_1h_almuerzo(self):
        """Marcado 9h con jornada 8h: aplica descuento de 1h almuerzo."""
        r = calcular_almuerzo_h(
            horas_marcadas=Decimal("9"),
            jornada_h=Decimal("8"),
            almuerzo_manual=None,
        )
        assert r == Decimal("1")

    def test_jornada_corta_no_descuenta(self):
        """Jornada 5.5h (sábado LOCAL): no descuenta almuerzo."""
        r = calcular_almuerzo_h(
            horas_marcadas=Decimal("5.5"),
            jornada_h=Decimal("5.5"),
            almuerzo_manual=None,
        )
        assert r == Decimal("0")

    def test_override_manual_tiene_prioridad(self):
        """Si admin seteó 0.5h, ignora la regla automática."""
        r = calcular_almuerzo_h(
            horas_marcadas=Decimal("9"),
            jornada_h=Decimal("8"),
            almuerzo_manual=Decimal("0.5"),
        )
        assert r == Decimal("0.5")

    def test_override_manual_cero_se_respeta(self):
        """Override 0 (sin descuento) NO se confunde con None."""
        r = calcular_almuerzo_h(
            horas_marcadas=Decimal("9"),
            jornada_h=Decimal("8"),
            almuerzo_manual=Decimal("0"),
        )
        assert r == Decimal("0")

    def test_jornada_7h_no_dispara_almuerzo(self):
        """Threshold es horas_marcadas > 7, no >=. Exactamente 7 NO descuenta."""
        r = calcular_almuerzo_h(
            horas_marcadas=Decimal("7"),
            jornada_h=Decimal("8"),
            almuerzo_manual=None,
        )
        assert r == Decimal("0")


# ═════════════════════════════════════════════════════════════════════════════
# _helpers.cap_horas_dia
# ═════════════════════════════════════════════════════════════════════════════

class TestCapHorasDia:

    def test_horas_normales_pasan_sin_cambio(self):
        assert cap_horas_dia(Decimal("8")) == Decimal("8")

    def test_horas_extremas_se_topean(self):
        """20h marcadas → tope sanitario 16h."""
        r = cap_horas_dia(Decimal("20"))
        assert r == HORAS_MAX_DIA
        assert r == Decimal("16")

    def test_horas_en_el_borde_no_se_topean(self):
        """Exactamente 16h pasa sin tope (> 16 sí se topea)."""
        assert cap_horas_dia(Decimal("16")) == Decimal("16")


# ═════════════════════════════════════════════════════════════════════════════
# _helpers.calcular_horas_marcadas_desde_horarios
# ═════════════════════════════════════════════════════════════════════════════

class TestCalcularHorasMarcadasDesdeHorarios:

    def test_jornada_estandar_8h(self):
        """Entrada 08:00, salida 17:00 → 9h marcadas."""
        r = calcular_horas_marcadas_desde_horarios(
            fecha=date(2026, 5, 20),
            hora_entrada=time(8, 0),
            hora_salida=time(17, 0),
        )
        assert r == Decimal("9")

    def test_entrada_igual_salida_devuelve_cero(self):
        r = calcular_horas_marcadas_desde_horarios(
            fecha=date(2026, 5, 20),
            hora_entrada=time(8, 0),
            hora_salida=time(8, 0),
        )
        assert r == Decimal("0")

    def test_turno_overnight_suma_dia(self):
        """Entrada 22:00, salida 06:00 → 8h (cruza medianoche)."""
        r = calcular_horas_marcadas_desde_horarios(
            fecha=date(2026, 5, 20),
            hora_entrada=time(22, 0),
            hora_salida=time(6, 0),
        )
        assert r == Decimal("8")

    def test_sin_horas_usa_fallback(self):
        r = calcular_horas_marcadas_desde_horarios(
            fecha=date(2026, 5, 20),
            hora_entrada=None,
            hora_salida=None,
            horas_marcadas_fallback=Decimal("7.5"),
        )
        assert r == Decimal("7.5")

    def test_sin_horas_sin_fallback_devuelve_cero(self):
        r = calcular_horas_marcadas_desde_horarios(
            fecha=date(2026, 5, 20),
            hora_entrada=None,
            hora_salida=None,
        )
        assert r == Decimal("0")


# ═════════════════════════════════════════════════════════════════════════════
# Smoke tests: services importables y módulos clave existen
# ═════════════════════════════════════════════════════════════════════════════

class TestServicesImportables:

    def test_processor_module_importable(self):
        from asistencia.services import processor
        # constantes y funciones clave existen
        assert hasattr(processor, "redondear_media_hora")
        assert hasattr(processor, "TIPO_PERMISO_MAP")
        assert hasattr(processor, "CODIGOS_SIN_HE")
        assert hasattr(processor, "CODIGOS_ASISTENCIA")

    def test_processor_class_TareoProcessor_existe(self):
        from asistencia.services.processor import TareoProcessor
        assert TareoProcessor is not None

    def test_helpers_module_importable(self):
        from asistencia.services import _helpers
        assert hasattr(_helpers, "calcular_almuerzo_h")
        assert hasattr(_helpers, "cap_horas_dia")
        assert hasattr(_helpers, "HORAS_MAX_DIA")
        assert _helpers.HORAS_MAX_DIA == Decimal("16")

    def test_codigos_sin_he_incluye_vacaciones_y_falta(self):
        """VAC y FA no deben generar HE (regla de negocio)."""
        from asistencia.services.processor import CODIGOS_SIN_HE
        assert "VAC" in CODIGOS_SIN_HE
        assert "FA" in CODIGOS_SIN_HE
        assert "LSG" in CODIGOS_SIN_HE

    def test_codigos_asistencia_incluye_T_y_TR(self):
        """T (trabajo) y TR (trabajo remoto) cuentan como día trabajado."""
        from asistencia.services.processor import CODIGOS_ASISTENCIA
        assert "T" in CODIGOS_ASISTENCIA
        assert "TR" in CODIGOS_ASISTENCIA
