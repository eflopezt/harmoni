"""
Tests para _get_plan_cuentas con override por empresa.
"""
from __future__ import annotations
import json
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from integraciones.contables import _get_plan_cuentas, PLAN_CUENTAS_DEFAULT


# ════════════════════════════════════════════════════════════════════════════
# Plan de cuentas con override por empresa
# ════════════════════════════════════════════════════════════════════════════

class TestPlanCuentasPorEmpresa:
    """Verifica la prioridad: empresa > global > default."""

    def test_sin_empresa_ni_global_retorna_default(self):
        """Sin nada configurado, devuelve el PLAN_CUENTAS_DEFAULT."""
        plan = _get_plan_cuentas()
        assert plan["sueldos_debe"] == ("6211", "Sueldos y salarios")
        assert plan["essalud_debe"] == ("6271", "EsSalud - aporte empleador")

    def test_empresa_con_plan_cuentas_sobreescribe(self):
        """Empresa con plan_cuentas custom debe usar esos valores."""
        emp = SimpleNamespace(
            plan_cuentas=json.dumps({
                "sueldos_debe": ["7211", "Sueldos custom Sabores del Sur"],
            }),
        )
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["sueldos_debe"] == ("7211", "Sueldos custom Sabores del Sur")
        # Las cuentas NO sobrescritas mantienen el default
        assert plan["essalud_debe"] == ("6271", "EsSalud - aporte empleador")

    def test_empresa_con_plan_cuentas_dict_directo(self):
        """Empresa con plan_cuentas como dict (no JSON string) tambien funciona."""
        emp = SimpleNamespace(
            plan_cuentas={
                "afp_pagar_haber": ["4072", "AFP por pagar - alternativa"],
            },
        )
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["afp_pagar_haber"] == ("4072", "AFP por pagar - alternativa")

    def test_empresa_plan_cuentas_invalido_no_rompe(self):
        """JSON inválido debe ser ignorado defensivamente."""
        emp = SimpleNamespace(plan_cuentas="not valid json {")
        plan = _get_plan_cuentas(empresa=emp)
        # Devuelve el default sin romper
        assert plan["sueldos_debe"] == ("6211", "Sueldos y salarios")

    def test_empresa_sin_atributo_plan_cuentas(self):
        """Empresa sin atributo plan_cuentas (legacy) no rompe."""
        emp = SimpleNamespace(razon_social="Sabores del Sur Legacy")
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["sueldos_debe"] == ("6211", "Sueldos y salarios")

    def test_empresa_plan_cuentas_none(self):
        """plan_cuentas=None (no configurado) usa default."""
        emp = SimpleNamespace(plan_cuentas=None)
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["sueldos_debe"] == ("6211", "Sueldos y salarios")

    def test_empresa_plan_cuentas_vacio(self):
        """plan_cuentas='' usa default."""
        emp = SimpleNamespace(plan_cuentas="")
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["sueldos_debe"] == ("6211", "Sueldos y salarios")

    def test_sobreescribe_multiples_cuentas(self):
        """Puedo sobreescribir varias cuentas a la vez."""
        emp = SimpleNamespace(
            plan_cuentas=json.dumps({
                "sueldos_debe":   ["8211", "Custom Sueldos"],
                "gratif_debe":    ["8215", "Custom Gratif"],
                "rem_pagar_haber": ["9111", "Custom Rem"],
            }),
        )
        plan = _get_plan_cuentas(empresa=emp)
        assert plan["sueldos_debe"] == ("8211", "Custom Sueldos")
        assert plan["gratif_debe"] == ("8215", "Custom Gratif")
        assert plan["rem_pagar_haber"] == ("9111", "Custom Rem")
        # No tocadas mantienen default
        assert plan["essalud_debe"] == ("6271", "EsSalud - aporte empleador")

    def test_plan_default_intacto_despues_de_override(self):
        """Hacer override no debe mutar PLAN_CUENTAS_DEFAULT global."""
        original = dict(PLAN_CUENTAS_DEFAULT)
        emp = SimpleNamespace(
            plan_cuentas=json.dumps({"sueldos_debe": ["XXX", "Y"]}),
        )
        _get_plan_cuentas(empresa=emp)
        # El default global sigue intacto
        assert PLAN_CUENTAS_DEFAULT == original
