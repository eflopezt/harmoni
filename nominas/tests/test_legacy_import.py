"""
Tests para el comando importar_planilla_legacy.

Cubre los helpers puros (sin DB):
- _to_decimal: conversion defensiva de cualquier valor a Decimal
- _normaliza_columna: lowercase + sin tildes + sin espacios extra
- _detectar_columnas: auto-detect case-insensitive con aliases
"""
from __future__ import annotations

from decimal import Decimal

from nominas.management.commands.importar_planilla_legacy import (
    _to_decimal,
    _normaliza_columna,
    _detectar_columnas,
    COLUMN_ALIASES,
)


# ════════════════════════════════════════════════════════════════════════════
# _to_decimal
# ════════════════════════════════════════════════════════════════════════════

class TestToDecimal:
    """Conversion defensiva: cualquier basura -> Decimal."""

    def test_decimal_pasa_directo(self):
        assert _to_decimal(Decimal("100.50")) == Decimal("100.50")

    def test_int_se_convierte(self):
        assert _to_decimal(100) == Decimal("100")

    def test_float_se_convierte(self):
        assert _to_decimal(100.50) == Decimal("100.5")

    def test_string_simple(self):
        assert _to_decimal("100.50") == Decimal("100.50")

    def test_string_con_simbolo_sol(self):
        """Limpia 'S/' del string antes de convertir."""
        assert _to_decimal("S/ 2,200.00") == Decimal("2200.00")
        assert _to_decimal("S/. 1,500.50") == Decimal("1500.50")

    def test_string_con_comas_de_miles(self):
        assert _to_decimal("1,234,567.89") == Decimal("1234567.89")

    def test_none_devuelve_cero(self):
        assert _to_decimal(None) == Decimal("0")

    def test_string_vacio_devuelve_cero(self):
        assert _to_decimal("") == Decimal("0")
        assert _to_decimal("  ") == Decimal("0")

    def test_string_basura_devuelve_cero(self):
        """Strings sin numero retornan 0 silenciosamente."""
        assert _to_decimal("abc") == Decimal("0")
        assert _to_decimal("xyz") == Decimal("0")
        assert _to_decimal("NaN") == Decimal("0")
        assert _to_decimal("none") == Decimal("0")
        assert _to_decimal("-") == Decimal("0")

    def test_negativo(self):
        assert _to_decimal("-500") == Decimal("-500")
        assert _to_decimal("-100.50") == Decimal("-100.50")


# ════════════════════════════════════════════════════════════════════════════
# _normaliza_columna
# ════════════════════════════════════════════════════════════════════════════

class TestNormalizaColumna:
    """Normaliza nombres de columna para comparacion case-insensitive."""

    def test_lowercase(self):
        assert _normaliza_columna("DNI") == "dni"
        assert _normaliza_columna("Total Bruto") == "total bruto"

    def test_quita_tildes(self):
        assert _normaliza_columna("Año") == "ano"
        assert _normaliza_columna("Razón Social") == "razon social"
        assert _normaliza_columna("Cédula") == "cedula"

    def test_strip_espacios(self):
        assert _normaliza_columna("  DNI  ") == "dni"
        assert _normaliza_columna("Total\tBruto") == "total bruto"

    def test_colapsa_espacios_multiples(self):
        assert _normaliza_columna("Total    Bruto") == "total bruto"

    def test_vacio(self):
        assert _normaliza_columna("") == ""
        assert _normaliza_columna(None) == ""

    def test_acepta_numeros(self):
        assert _normaliza_columna("Mes_2024") == "mes_2024"


# ════════════════════════════════════════════════════════════════════════════
# _detectar_columnas
# ════════════════════════════════════════════════════════════════════════════

class TestDetectarColumnas:
    """Auto-detect de columnas con aliases."""

    def test_detecta_columnas_estandar(self):
        cols = ["DNI", "Apellidos y Nombres", "Año", "Mes", "Total Bruto", "Total Neto"]
        mapping = _detectar_columnas(cols)
        assert mapping["dni"] == "DNI"
        assert mapping["nombre"] == "Apellidos y Nombres"
        assert mapping["anio"] == "Año"
        assert mapping["mes"] == "Mes"
        assert mapping["bruto"] == "Total Bruto"
        assert mapping["neto"] == "Total Neto"

    def test_detecta_documento_como_dni(self):
        """'Documento' es alias de 'DNI'."""
        mapping = _detectar_columnas(["Documento", "Nombre", "Anio", "Mes",
                                      "Bruto", "Neto"])
        assert mapping["dni"] == "Documento"

    def test_detecta_year_como_anio(self):
        mapping = _detectar_columnas(["DNI", "Nombre", "Year", "Mes",
                                      "Bruto", "Neto"])
        assert mapping["anio"] == "Year"

    def test_detecta_gross_como_bruto(self):
        mapping = _detectar_columnas(["DNI", "Year", "Month", "Gross", "Net pay"])
        assert mapping["bruto"] == "Gross"
        assert mapping["neto"] == "Net pay"

    def test_columnas_ausentes_no_aparecen(self):
        """Si una columna no esta en el archivo, no aparece en el mapping."""
        mapping = _detectar_columnas(["DNI", "Bruto"])
        assert "dni" in mapping
        assert "bruto" in mapping
        assert "mes" not in mapping
        assert "neto" not in mapping

    def test_columnas_opcionales_detectadas(self):
        cols = ["DNI", "Anio", "Mes", "Bruto", "Neto",
                "AFP", "ONP", "EsSalud", "RUC"]
        mapping = _detectar_columnas(cols)
        assert mapping["afp"] == "AFP"
        assert mapping["onp"] == "ONP"
        assert mapping["essalud"] == "EsSalud"
        assert mapping["empresa"] == "RUC"

    def test_case_insensitive(self):
        """Detecta sin importar capitalizacion."""
        mapping = _detectar_columnas(["dni", "AÑO", "Mes", "BRUTO", "neto"])
        assert mapping["dni"] == "dni"
        assert mapping["anio"] == "AÑO"
        assert mapping["bruto"] == "BRUTO"

    def test_columnas_extra_se_ignoran(self):
        """Columnas que no son aliases conocidos se ignoran sin error."""
        mapping = _detectar_columnas(["DNI", "Bruto", "Comentarios", "Z123"])
        assert mapping["dni"] == "DNI"
        assert mapping["bruto"] == "Bruto"
        assert "comentarios" not in mapping

    def test_column_aliases_no_vacio(self):
        """COLUMN_ALIASES define listas finitas de aliases."""
        for canon, aliases in COLUMN_ALIASES.items():
            assert len(aliases) >= 1
