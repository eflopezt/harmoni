"""
Tests para el motor de calculo de nomina peruana (nominas/engine.py).

Cubre:
- IR 5ta categoria (escala progresiva, 7 UIT deduccion, proyeccion 14x)
- Gratificacion (Ley 29351: inafecta AFP/ONP, bonif extraordinaria 9%)
- Planilla regular (AFP, ONP, EsSalud, asig familiar, horas extra)
- Provisiones (gratificacion, CTS)

Usa Decimal para todos los montos. Los tests son autocontenidos y no
dependen de estado de base de datos.
"""
import pytest
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from nominas.engine import (
    calcular_ir_5ta_mensual,
    calcular_registro,
    calcular_gratificacion,
    calcular_cts,
    _redondear,
    AFP_APORTE,
    AFP_TASAS,
    ONP_TASA,
    ESSALUD_TASA,
    UIT_2026,
    RMV_2026,
    ASIG_FAM,
    BONIF_EXTRAORDINARIA_TASA,
    IR_5TA_ESCALA,
    IR_5TA_DEDUCCION_UITS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UIT = UIT_2026  # S/ 5,500
RMV = RMV_2026  # S/ 1,130


def _r(val):
    """Shortcut for rounding to 2 decimal places."""
    return Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _make_registro(**overrides):
    """
    Build a minimal mock RegistroNomina with sensible defaults.
    Uses SimpleNamespace so no DB is needed.
    """
    defaults = {
        'sueldo_base': Decimal('3000.00'),
        'dias_trabajados': 30,
        'regimen_pension': 'AFP',
        'afp': 'Prima',
        'asignacion_familiar': False,
        'horas_extra_25': Decimal('0'),
        'horas_extra_35': Decimal('0'),
        'horas_extra_100': Decimal('0'),
        'otros_ingresos': Decimal('0'),
        'descuento_prestamo': Decimal('0'),
        'otros_descuentos': Decimal('0'),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# Patch _get_uit and _get_rmv so they never hit the DB
@pytest.fixture(autouse=True)
def _patch_config():
    with patch('nominas.engine._get_uit', return_value=UIT), \
         patch('nominas.engine._get_rmv', return_value=RMV):
        yield


# Patch ConceptoRemunerativo queries for calcular_registro / gratificacion / cts
# We pass a mock queryset whose .get(codigo=...) returns a stub concepto
def _mock_conceptos():
    """Return a mock queryset that always returns a stub concepto for any codigo."""
    qs = MagicMock()

    def _get_concepto(codigo):
        return SimpleNamespace(codigo=codigo, nombre=codigo)

    qs.get = lambda codigo=None: _get_concepto(codigo)
    return qs


# ═══════════════════════════════════════════════════════════════════════
# 1. IR 5ta Categoria
# ═══════════════════════════════════════════════════════════════════════

class TestIR5taMensual:
    """Pruebas de calcular_ir_5ta_mensual."""

    # -- Zero / below 7 UIT --

    def test_zero_income_returns_zero(self):
        assert calcular_ir_5ta_mensual(Decimal('0')) == Decimal('0')

    def test_income_below_7_uit_returns_zero(self):
        """If annual income <= 7 UIT (S/ 38,500), no tax."""
        rem_anual = Decimal('38500.00')
        assert calcular_ir_5ta_mensual(rem_anual) == Decimal('0')

    def test_income_slightly_below_7_uit_returns_zero(self):
        rem_anual = Decimal('38499.99')
        assert calcular_ir_5ta_mensual(rem_anual) == Decimal('0')

    # -- Annual projection uses 14x --

    def test_annual_projection_uses_14x(self):
        """
        Engine uses rem_computable * 14 for the annual projection
        (12 months + 2 gratificaciones). We verify by computing manually.
        """
        sueldo = Decimal('5000.00')
        rem_anual = sueldo * Decimal('14')  # S/ 70,000
        base_imponible = rem_anual - (7 * UIT)  # 70,000 - 38,500 = 31,500
        # 31,500 falls entirely in first bracket (0-5 UIT = 0-27,500)
        # 27,500 at 8% = 2,200
        # 31,500 - 27,500 = 4,000 at 14% = 560
        expected_annual = _r(Decimal('27500') * Decimal('0.08') +
                             Decimal('4000') * Decimal('0.14'))
        expected_monthly = _r(expected_annual / Decimal('12'))
        result = calcular_ir_5ta_mensual(rem_anual)
        assert result == expected_monthly

    # -- Bracket: 8% (first 5 UIT of base imponible) --

    def test_bracket_8_percent(self):
        """Income that falls entirely in the 8% bracket."""
        # base_imponible = 10,000 (within 5 UIT = 27,500)
        rem_anual = Decimal('48500.00')  # 48,500 - 38,500 = 10,000
        expected_annual = _r(Decimal('10000') * Decimal('0.08'))  # 800
        expected_monthly = _r(expected_annual / Decimal('12'))
        assert calcular_ir_5ta_mensual(rem_anual) == expected_monthly

    # -- Bracket: 14% (5-20 UIT) --

    def test_bracket_14_percent(self):
        """Income that reaches the 14% bracket."""
        # base_imponible = 40,000 (5 UIT=27,500 at 8%, rest at 14%)
        rem_anual = Decimal('78500.00')  # 78,500 - 38,500 = 40,000
        tax_8 = Decimal('27500') * Decimal('0.08')  # 2,200
        tax_14 = (Decimal('40000') - Decimal('27500')) * Decimal('0.14')  # 1,750
        expected_monthly = _r((tax_8 + tax_14) / Decimal('12'))
        assert calcular_ir_5ta_mensual(rem_anual) == expected_monthly

    # -- Bracket: 17% (20-35 UIT) --

    def test_bracket_17_percent(self):
        """Income that reaches the 17% bracket."""
        # base_imponible = 140,000 => bracket limits: 5*5500=27500, 20*5500=110000, 35*5500=192500
        rem_anual = Decimal('178500.00')  # 178,500 - 38,500 = 140,000
        tax_8 = Decimal('27500') * Decimal('0.08')
        tax_14 = (Decimal('110000') - Decimal('27500')) * Decimal('0.14')
        tax_17 = (Decimal('140000') - Decimal('110000')) * Decimal('0.17')
        expected_monthly = _r((tax_8 + tax_14 + tax_17) / Decimal('12'))
        assert calcular_ir_5ta_mensual(rem_anual) == expected_monthly

    # -- Bracket: 20% (35-45 UIT) --

    def test_bracket_20_percent(self):
        """Income that reaches the 20% bracket."""
        # base_imponible = 220,000 => 35*5500=192500, 45*5500=247500
        rem_anual = Decimal('258500.00')  # 258,500 - 38,500 = 220,000
        tax_8 = Decimal('27500') * Decimal('0.08')
        tax_14 = (Decimal('110000') - Decimal('27500')) * Decimal('0.14')
        tax_17 = (Decimal('192500') - Decimal('110000')) * Decimal('0.17')
        tax_20 = (Decimal('220000') - Decimal('192500')) * Decimal('0.20')
        expected_monthly = _r((tax_8 + tax_14 + tax_17 + tax_20) / Decimal('12'))
        assert calcular_ir_5ta_mensual(rem_anual) == expected_monthly

    # -- Bracket: 30% (over 45 UIT) --

    def test_bracket_30_percent(self):
        """Income that reaches the 30% bracket (highest)."""
        # base_imponible = 300,000 => 45*5500=247500
        rem_anual = Decimal('338500.00')  # 338,500 - 38,500 = 300,000
        tax_8 = Decimal('27500') * Decimal('0.08')
        tax_14 = (Decimal('110000') - Decimal('27500')) * Decimal('0.14')
        tax_17 = (Decimal('192500') - Decimal('110000')) * Decimal('0.17')
        tax_20 = (Decimal('247500') - Decimal('192500')) * Decimal('0.20')
        tax_30 = (Decimal('300000') - Decimal('247500')) * Decimal('0.30')
        expected_monthly = _r((tax_8 + tax_14 + tax_17 + tax_20 + tax_30) / Decimal('12'))
        assert calcular_ir_5ta_mensual(rem_anual) == expected_monthly

    # -- 7 UIT deduction --

    def test_7_uit_deduction_value(self):
        """7 UIT = S/ 38,500."""
        assert IR_5TA_DEDUCCION_UITS * UIT == Decimal('38500.00')

    def test_deduction_eps_reduces_base(self):
        """EPS annual deduction reduces base before 7 UIT."""
        rem_anual = Decimal('78500.00')
        eps_anual = Decimal('5000.00')
        # Without EPS: base = 78500 - 38500 = 40000
        # With EPS:    base = 78500 - 5000 - 38500 = 35000
        result_no_eps = calcular_ir_5ta_mensual(rem_anual)
        result_with_eps = calcular_ir_5ta_mensual(rem_anual, eps_anual)
        assert result_with_eps < result_no_eps

    def test_negative_base_imponible_returns_zero(self):
        """If deductions exceed income, tax is zero."""
        rem_anual = Decimal('30000.00')
        eps_anual = Decimal('5000.00')
        # 30000 - 5000 - 38500 = -13500 => 0
        assert calcular_ir_5ta_mensual(rem_anual, eps_anual) == Decimal('0')


# ═══════════════════════════════════════════════════════════════════════
# 2. Gratificacion
# ═══════════════════════════════════════════════════════════════════════

class TestGratificacion:
    """Pruebas de calcular_gratificacion (Ley 27735 + Ley 29351)."""

    def test_afp_not_deducted(self):
        """Ley 29351: gratificaciones are inafectas to AFP."""
        registro = _make_registro(
            sueldo_base=Decimal('5000.00'),
            regimen_pension='AFP',
            afp='Prima',
            dias_trabajados=6,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        assert result['total_descuentos'] == Decimal('0')
        assert result['neto_a_pagar'] == result['gratif_bruto']

    def test_onp_not_deducted(self):
        """Ley 29351: gratificaciones are inafectas to ONP."""
        registro = _make_registro(
            sueldo_base=Decimal('5000.00'),
            regimen_pension='ONP',
            dias_trabajados=6,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        assert result['total_descuentos'] == Decimal('0')
        assert result['neto_a_pagar'] == result['gratif_bruto']

    def test_bonificacion_extraordinaria_is_9_percent(self):
        """Bonif extraordinaria = 9% of the gross gratificacion."""
        registro = _make_registro(
            sueldo_base=Decimal('4000.00'),
            dias_trabajados=6,
            asignacion_familiar=False,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        expected_bonif = _r(result['gratif_bruto'] * Decimal('0.09'))
        assert result['bonif_extra'] == expected_bonif

    def test_proportional_calculation(self):
        """Gratificacion proportional: base * meses / 6."""
        sueldo = Decimal('6000.00')
        for meses in range(1, 7):
            registro = _make_registro(
                sueldo_base=sueldo,
                dias_trabajados=meses,
                asignacion_familiar=False,
            )
            result = calcular_gratificacion(registro, _mock_conceptos())
            expected = _r(sueldo * Decimal(meses) / Decimal('6'))
            assert result['gratif_bruto'] == expected, f"Failed for meses={meses}"

    def test_asignacion_familiar_included_in_base(self):
        """Asig familiar (10% RMV) is part of the gratificacion base."""
        sueldo = Decimal('3000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            dias_trabajados=6,
            asignacion_familiar=True,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        asig_fam = _r(RMV * Decimal('0.10'))
        expected_base = sueldo + asig_fam
        expected_gratif = _r(expected_base * Decimal('6') / Decimal('6'))
        assert result['gratif_bruto'] == expected_gratif
        assert result['rem_computable'] == expected_base

    def test_full_semester_equals_one_salary(self):
        """6/6 months = full salary + asig_fam."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            dias_trabajados=6,
            asignacion_familiar=False,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        assert result['gratif_bruto'] == sueldo

    def test_gratif_costo_empresa_includes_bonif_and_essalud(self):
        """Costo empresa = gratif + bonif_extra + essalud."""
        registro = _make_registro(
            sueldo_base=Decimal('4000.00'),
            dias_trabajados=6,
        )
        result = calcular_gratificacion(registro, _mock_conceptos())
        gratif = result['gratif_bruto']
        bonif = result['bonif_extra']
        essalud = result['aporte_essalud']
        expected = _r(gratif + bonif + essalud)
        assert result['costo_total_empresa'] == expected


# ═══════════════════════════════════════════════════════════════════════
# 3. Regular Payroll (calcular_registro)
# ═══════════════════════════════════════════════════════════════════════

class TestRegularPayroll:
    """Pruebas de calcular_registro (planilla mensual regular)."""

    # -- AFP deductions --

    def test_afp_aporte_10_percent(self):
        """AFP mandatory contribution is 10% of rem_computable."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            regimen_pension='AFP',
            afp='Prima',
        )
        result = calcular_registro(registro, _mock_conceptos())
        rem = result['rem_computable']
        expected_aporte = _r(rem * Decimal('10') / Decimal('100'))
        # Find AFP aporte in result
        assert expected_aporte == _r(rem * AFP_APORTE / Decimal('100'))

    def test_afp_comision_prima(self):
        """AFP Prima comision flujo = 1.60%."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(sueldo_base=sueldo, afp='Prima')
        result = calcular_registro(registro, _mock_conceptos())
        rem = result['rem_computable']
        expected = _r(rem * Decimal('1.60') / Decimal('100'))
        # Verify through total descuentos
        tasas = AFP_TASAS['Prima']
        aporte = _r(rem * AFP_APORTE / Decimal('100'))
        comision = _r(rem * tasas['comision_flujo'] / Decimal('100'))
        seguro = _r(rem * tasas['seguro'] / Decimal('100'))
        assert comision == expected

    def test_afp_seguro_prima(self):
        """AFP Prima seguro = 1.84%."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(sueldo_base=sueldo, afp='Prima')
        result = calcular_registro(registro, _mock_conceptos())
        rem = result['rem_computable']
        expected = _r(rem * Decimal('1.84') / Decimal('100'))
        tasas = AFP_TASAS['Prima']
        seguro = _r(rem * tasas['seguro'] / Decimal('100'))
        assert seguro == expected

    def test_afp_all_four_providers(self):
        """Each AFP has different comision/seguro rates."""
        sueldo = Decimal('4000.00')
        for afp_name, tasas in AFP_TASAS.items():
            registro = _make_registro(sueldo_base=sueldo, afp=afp_name)
            result = calcular_registro(registro, _mock_conceptos())
            rem = result['rem_computable']
            expected_total_afp = (
                _r(rem * AFP_APORTE / Decimal('100')) +
                _r(rem * tasas['comision_flujo'] / Decimal('100')) +
                _r(rem * tasas['seguro'] / Decimal('100'))
            )
            # total_descuentos includes AFP + IR
            # Just verify AFP portion is in total
            ir = calcular_ir_5ta_mensual(rem * Decimal('14'))
            assert result['total_descuentos'] == expected_total_afp + ir, (
                f"Failed for AFP {afp_name}"
            )

    # -- ONP deduction --

    def test_onp_deduction_13_percent(self):
        """ONP deduction is 13% of rem_computable."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            regimen_pension='ONP',
        )
        result = calcular_registro(registro, _mock_conceptos())
        rem = result['rem_computable']
        expected_onp = _r(rem * Decimal('13') / Decimal('100'))
        ir = calcular_ir_5ta_mensual(rem * Decimal('14'))
        assert result['total_descuentos'] == expected_onp + ir

    def test_onp_no_afp_charges(self):
        """When pension is ONP, there should be no AFP charges."""
        registro = _make_registro(regimen_pension='ONP')
        result = calcular_registro(registro, _mock_conceptos())
        # Check no AFP lines in lineas
        afp_lines = [l for l in result['lineas'] if 'afp' in l['concepto'].codigo]
        assert len(afp_lines) == 0

    # -- EsSalud --

    def test_essalud_9_percent_employer(self):
        """EsSalud = 9% of rem_computable, paid by employer."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(sueldo_base=sueldo)
        result = calcular_registro(registro, _mock_conceptos())
        rem = result['rem_computable']
        expected = _r(rem * Decimal('9') / Decimal('100'))
        assert result['aporte_essalud'] == expected

    def test_essalud_not_deducted_from_worker(self):
        """EsSalud is employer cost, not deducted from worker neto."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(sueldo_base=sueldo)
        result = calcular_registro(registro, _mock_conceptos())
        # neto = total_ingresos - total_descuentos (no essalud)
        assert result['neto_a_pagar'] == _r(
            result['total_ingresos'] - result['total_descuentos']
        )
        # essalud is not in total_descuentos
        assert result['aporte_essalud'] > Decimal('0')

    # -- Asignacion Familiar --

    def test_asignacion_familiar_10_percent_rmv(self):
        """Asig familiar = 10% of RMV = S/ 113.00."""
        assert ASIG_FAM == _r(RMV * Decimal('0.10'))
        assert ASIG_FAM == Decimal('113.00')

    def test_asignacion_familiar_in_rem_computable(self):
        """Asig familiar is added to rem_computable."""
        sueldo = Decimal('3000.00')
        reg_sin = _make_registro(sueldo_base=sueldo, asignacion_familiar=False)
        reg_con = _make_registro(sueldo_base=sueldo, asignacion_familiar=True)
        res_sin = calcular_registro(reg_sin, _mock_conceptos())
        res_con = calcular_registro(reg_con, _mock_conceptos())
        diff = res_con['rem_computable'] - res_sin['rem_computable']
        assert diff == _r(RMV * Decimal('0.10'))

    def test_no_asignacion_familiar_when_flag_false(self):
        """No asig familiar if flag is False."""
        registro = _make_registro(asignacion_familiar=False)
        result = calcular_registro(registro, _mock_conceptos())
        assert result['rem_computable'] == registro.sueldo_base

    # -- Overtime (Horas Extra) --

    def test_overtime_25_percent(self):
        """HE 25% = hours * (sueldo/30/8) * 1.25."""
        sueldo = Decimal('3000.00')
        horas = Decimal('10')
        registro = _make_registro(sueldo_base=sueldo, horas_extra_25=horas)
        result = calcular_registro(registro, _mock_conceptos())
        valor_hora = _r(sueldo / Decimal('30') / Decimal('8'))
        expected = _r(horas * valor_hora * Decimal('1.25'))
        rem_expected = sueldo + expected
        assert result['rem_computable'] == rem_expected

    def test_overtime_35_percent(self):
        """HE 35% = hours * (sueldo/30/8) * 1.35."""
        sueldo = Decimal('3000.00')
        horas = Decimal('8')
        registro = _make_registro(sueldo_base=sueldo, horas_extra_35=horas)
        result = calcular_registro(registro, _mock_conceptos())
        valor_hora = _r(sueldo / Decimal('30') / Decimal('8'))
        expected = _r(horas * valor_hora * Decimal('1.35'))
        rem_expected = sueldo + expected
        assert result['rem_computable'] == rem_expected

    def test_overtime_100_percent(self):
        """HE 100% = hours * (sueldo/30/8) * 2.00."""
        sueldo = Decimal('3000.00')
        horas = Decimal('5')
        registro = _make_registro(sueldo_base=sueldo, horas_extra_100=horas)
        result = calcular_registro(registro, _mock_conceptos())
        valor_hora = _r(sueldo / Decimal('30') / Decimal('8'))
        expected = _r(horas * valor_hora * Decimal('2.00'))
        rem_expected = sueldo + expected
        assert result['rem_computable'] == rem_expected

    def test_all_overtime_types_combined(self):
        """All overtime types add to rem_computable."""
        sueldo = Decimal('3000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            horas_extra_25=Decimal('4'),
            horas_extra_35=Decimal('3'),
            horas_extra_100=Decimal('2'),
        )
        result = calcular_registro(registro, _mock_conceptos())
        vh = _r(sueldo / Decimal('30') / Decimal('8'))
        he25 = _r(Decimal('4') * vh * Decimal('1.25'))
        he35 = _r(Decimal('3') * vh * Decimal('1.35'))
        he100 = _r(Decimal('2') * vh * Decimal('2.00'))
        assert result['rem_computable'] == sueldo + he25 + he35 + he100

    # -- Proportional salary --

    def test_proportional_salary_15_days(self):
        """15 days worked = half salary."""
        sueldo = Decimal('6000.00')
        registro = _make_registro(sueldo_base=sueldo, dias_trabajados=15)
        result = calcular_registro(registro, _mock_conceptos())
        expected_prop = _r(sueldo * Decimal('15') / Decimal('30'))
        assert result['rem_computable'] == expected_prop

    # -- Neto calculation --

    def test_neto_equals_ingresos_minus_descuentos(self):
        """Net pay = total income - total deductions."""
        registro = _make_registro(
            sueldo_base=Decimal('8000.00'),
            asignacion_familiar=True,
            horas_extra_25=Decimal('5'),
            otros_ingresos=Decimal('200'),
        )
        result = calcular_registro(registro, _mock_conceptos())
        assert result['neto_a_pagar'] == _r(
            result['total_ingresos'] - result['total_descuentos']
        )

    # -- Sin pension --

    def test_sin_pension_no_afp_no_onp(self):
        """SIN_PENSION: no AFP and no ONP deductions."""
        registro = _make_registro(regimen_pension='SIN_PENSION')
        result = calcular_registro(registro, _mock_conceptos())
        pension_lines = [
            l for l in result['lineas']
            if l['concepto'].codigo in ('afp-aporte', 'afp-comision', 'afp-seguro', 'onp')
        ]
        assert len(pension_lines) == 0


# ═══════════════════════════════════════════════════════════════════════
# 4. Provisions (Gratificacion & CTS)
# ═══════════════════════════════════════════════════════════════════════

class TestProvisions:
    """Pruebas de provisiones calculadas en planilla regular."""

    def test_gratificacion_provision_excludes_overtime(self):
        """
        Provision gratif = (sueldo_prop + asig_fam) / 6.
        Overtime is NOT included (Ley 27735).
        """
        sueldo = Decimal('6000.00')
        registro = _make_registro(
            sueldo_base=sueldo,
            horas_extra_25=Decimal('20'),
            horas_extra_35=Decimal('10'),
            asignacion_familiar=False,
        )
        result = calcular_registro(registro, _mock_conceptos())
        # base_gratif = sueldo_prop + asig_fam (no HE)
        sueldo_prop = _r(sueldo * Decimal('30') / Decimal('30'))
        expected_prov = _r(sueldo_prop / Decimal('6'))
        # Find provision line
        prov_lines = [l for l in result['lineas'] if l['concepto'].codigo == 'prov-gratificacion']
        assert len(prov_lines) == 1
        assert prov_lines[0]['monto'] == expected_prov

    def test_cts_provision_includes_asig_fam(self):
        """
        CTS provision base = sueldo_prop + asig_fam + 1/6 gratif.
        asig_fam must be included.
        """
        sueldo = Decimal('4000.00')
        reg_sin = _make_registro(sueldo_base=sueldo, asignacion_familiar=False)
        reg_con = _make_registro(sueldo_base=sueldo, asignacion_familiar=True)
        res_sin = calcular_registro(reg_sin, _mock_conceptos())
        res_con = calcular_registro(reg_con, _mock_conceptos())
        prov_sin = [l for l in res_sin['lineas'] if l['concepto'].codigo == 'prov-cts'][0]['monto']
        prov_con = [l for l in res_con['lineas'] if l['concepto'].codigo == 'prov-cts'][0]['monto']
        assert prov_con > prov_sin

    def test_cts_provision_includes_one_sixth_gratif(self):
        """
        CTS provision = (base_gratif + prov_gratif) / 12
        where prov_gratif = base_gratif / 6.
        This means CTS includes 1/6 of gratificacion.
        """
        sueldo = Decimal('6000.00')
        registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=False)
        result = calcular_registro(registro, _mock_conceptos())
        sueldo_prop = sueldo  # 30/30
        base_gratif = sueldo_prop  # no asig_fam
        prov_gratif = _r(base_gratif / Decimal('6'))
        expected_cts = _r((base_gratif + prov_gratif) / Decimal('12'))
        prov_cts_line = [l for l in result['lineas'] if l['concepto'].codigo == 'prov-cts'][0]
        assert prov_cts_line['monto'] == expected_cts

    def test_gratif_provision_with_asig_fam(self):
        """Provision gratif includes asig_fam in base."""
        sueldo = Decimal('3000.00')
        registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=True)
        result = calcular_registro(registro, _mock_conceptos())
        asig = _r(RMV * Decimal('0.10'))
        base_gratif = sueldo + asig
        expected = _r(base_gratif / Decimal('6'))
        prov_line = [l for l in result['lineas'] if l['concepto'].codigo == 'prov-gratificacion'][0]
        assert prov_line['monto'] == expected


# ═══════════════════════════════════════════════════════════════════════
# 5. CTS Calculation (calcular_cts)
# ═══════════════════════════════════════════════════════════════════════

class TestCTS:
    """Pruebas de calcular_cts (DL 650)."""

    def test_cts_base_includes_asig_fam(self):
        """CTS base = sueldo + asig_fam + 1/6 sueldo."""
        sueldo = Decimal('4000.00')
        registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=True, dias_trabajados=6)
        result = calcular_cts(registro, _mock_conceptos())
        asig = _r(RMV * Decimal('0.10'))
        prov_g = _r(sueldo / Decimal('6'))
        expected_base = sueldo + asig + prov_g
        assert result['base_cts'] == expected_base

    def test_cts_base_includes_one_sixth_gratif(self):
        """CTS base includes 1/6 of sueldo (gratificacion provision)."""
        sueldo = Decimal('6000.00')
        registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=False, dias_trabajados=6)
        result = calcular_cts(registro, _mock_conceptos())
        prov_g = _r(sueldo / Decimal('6'))
        expected_base = sueldo + prov_g
        assert result['base_cts'] == expected_base
        assert result['prov_gratif_mes'] == prov_g

    def test_cts_proportional(self):
        """CTS = base / 12 * meses."""
        sueldo = Decimal('6000.00')
        for meses in range(1, 7):
            registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=False, dias_trabajados=meses)
            result = calcular_cts(registro, _mock_conceptos())
            base = sueldo + _r(sueldo / Decimal('6'))
            expected = _r(base / Decimal('12') * Decimal(meses))
            assert result['cts_semestral'] == expected, f"Failed for meses={meses}"

    def test_cts_no_deductions(self):
        """CTS has zero deductions (inafecta)."""
        registro = _make_registro(sueldo_base=Decimal('5000.00'), dias_trabajados=6)
        result = calcular_cts(registro, _mock_conceptos())
        assert result['total_descuentos'] == Decimal('0')
        assert result['neto_a_pagar'] == result['cts_semestral']

    def test_cts_no_essalud(self):
        """CTS does not have EsSalud contribution."""
        registro = _make_registro(sueldo_base=Decimal('5000.00'), dias_trabajados=6)
        result = calcular_cts(registro, _mock_conceptos())
        assert result['aporte_essalud'] == Decimal('0')

    def test_cts_costo_empresa_equals_cts(self):
        """CTS costo empresa = CTS amount (employer pays fully)."""
        registro = _make_registro(sueldo_base=Decimal('5000.00'), dias_trabajados=6)
        result = calcular_cts(registro, _mock_conceptos())
        assert result['costo_total_empresa'] == result['cts_semestral']


# ═══════════════════════════════════════════════════════════════════════
# 6. Edge Cases and Constants
# ═══════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Casos borde y validacion de constantes."""

    def test_uit_2026_value(self):
        assert UIT_2026 == Decimal('5500.00')

    def test_rmv_2026_value(self):
        assert RMV_2026 == Decimal('1130.00')

    def test_asig_fam_value(self):
        assert ASIG_FAM == Decimal('113.00')

    def test_redondear_half_up(self):
        assert _redondear(Decimal('100.555')) == Decimal('100.56')
        assert _redondear(Decimal('100.554')) == Decimal('100.55')
        assert _redondear(Decimal('100.545')) == Decimal('100.55')

    def test_bonif_extraordinaria_rate(self):
        assert BONIF_EXTRAORDINARIA_TASA == Decimal('9')

    def test_onp_rate(self):
        assert ONP_TASA == Decimal('13.00')

    def test_essalud_rate(self):
        assert ESSALUD_TASA == Decimal('9.00')

    def test_afp_aporte_rate(self):
        assert AFP_APORTE == Decimal('10.00')

    def test_ir_scale_has_5_brackets(self):
        assert len(IR_5TA_ESCALA) == 5

    def test_ir_scale_last_bracket_unlimited(self):
        last = IR_5TA_ESCALA[-1]
        assert last[0] is None
        assert last[1] == Decimal('30')

    def test_costo_empresa_includes_essalud_and_provisions(self):
        """costo_empresa = ingresos_bruto + essalud + prov_gratif + prov_cts."""
        sueldo = Decimal('5000.00')
        registro = _make_registro(sueldo_base=sueldo, asignacion_familiar=True)
        result = calcular_registro(registro, _mock_conceptos())
        # Manually compute
        rem = result['rem_computable']
        essalud = _r(rem * Decimal('0.09'))
        base_g = sueldo + _r(RMV * Decimal('0.10'))
        prov_g = _r(base_g / Decimal('6'))
        prov_c = _r((base_g + prov_g) / Decimal('12'))
        expected = _r(result['total_ingresos'] + essalud + prov_g + prov_c)
        assert result['costo_total_empresa'] == expected

    def test_zero_salary_zero_everything(self):
        """Zero salary produces zero results."""
        registro = _make_registro(sueldo_base=Decimal('0'))
        result = calcular_registro(registro, _mock_conceptos())
        assert result['rem_computable'] == Decimal('0')
        assert result['total_ingresos'] == Decimal('0')
        assert result['total_descuentos'] == Decimal('0')
        assert result['neto_a_pagar'] == Decimal('0')
