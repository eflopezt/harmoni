"""
Tests para nominas/views_liquidacion.py — funciones de calculo de liquidacion al cese.

Usa SimpleNamespace como mocks para Personal y SaldoVacacional,
sin necesidad de base de datos.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


# Importar funciones bajo test
from nominas.views_liquidacion import (
    _meses_semestre_gratif,
    _meses_semestre_cts,
    _calcular_liquidacion,
    _rd,
    ASIG_FAM,
    AFP_APORTE,
    ONP_TASA,
    ESSALUD,
)
from nominas.engine import AFP_TASAS


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_personal(
    sueldo_base=3000,
    fecha_cese=None,
    asignacion_familiar=False,
    regimen_pension='AFP',
    afp='Prima',
    **kwargs,
):
    """Crea un SimpleNamespace que simula un objeto Personal."""
    ns = SimpleNamespace(
        sueldo_base=Decimal(str(sueldo_base)),
        fecha_cese=fecha_cese,
        asignacion_familiar=asignacion_familiar,
        regimen_pension=regimen_pension,
        afp=afp,
        **kwargs,
    )
    return ns


def _patch_vacaciones(dias_pendientes=0, dias_truncos=0):
    """Retorna un mock de SaldoVacacional.objects.filter(...).order_by(...).first()."""
    sv = SimpleNamespace(
        dias_pendientes=dias_pendientes,
        dias_truncos=dias_truncos,
    )
    mock_qs = MagicMock()
    mock_qs.filter.return_value.order_by.return_value.first.return_value = sv
    return mock_qs


def _patch_vacaciones_none():
    """Retorna un mock donde no hay SaldoVacacional."""
    mock_qs = MagicMock()
    mock_qs.filter.return_value.order_by.return_value.first.return_value = None
    return mock_qs


# ══════════════════════════════════════════════════════════════════════════════
# 1. _meses_semestre_gratif()
# ══════════════════════════════════════════════════════════════════════════════

class TestMesesSemestreGratif:
    """Ley 27735: solo meses integros en el semestre de gratificacion."""

    def test_january_31_hire(self):
        """Enero completo (dia 31) = 1 mes en S1."""
        assert _meses_semestre_gratif(date(2026, 1, 31)) == 1

    def test_january_15_partial(self):
        """Enero parcial (dia 15) = 0 meses completos."""
        assert _meses_semestre_gratif(date(2026, 1, 15)) == 0

    def test_march_31_termination(self):
        """Cese 31 marzo = 3 meses completos (ene, feb, mar)."""
        assert _meses_semestre_gratif(date(2026, 3, 31)) == 3

    def test_march_15_termination(self):
        """Cese 15 marzo = 2 meses completos (ene, feb); marzo parcial excluido."""
        assert _meses_semestre_gratif(date(2026, 3, 15)) == 2

    def test_february_28_non_leap(self):
        """Feb 28 en anio no bisiesto = ultimo dia del mes => cuenta como completo."""
        # 2026 is not a leap year
        assert _meses_semestre_gratif(date(2026, 2, 28)) == 2

    def test_february_28_leap_year(self):
        """Feb 28 en anio bisiesto (29 dias) = NO es ultimo dia => solo ene completo."""
        # 2028 is a leap year
        assert _meses_semestre_gratif(date(2028, 2, 28)) == 1

    def test_february_29_leap_year(self):
        """Feb 29 en anio bisiesto = ultimo dia => ene + feb completos."""
        assert _meses_semestre_gratif(date(2028, 2, 29)) == 2

    def test_june_30_full_semester(self):
        """Junio 30 = 6 meses completos (S1 completo)."""
        assert _meses_semestre_gratif(date(2026, 6, 30)) == 6

    def test_july_s2_starts(self):
        """Julio = S2 empieza. Jul 31 = 1 mes completo."""
        assert _meses_semestre_gratif(date(2026, 7, 31)) == 1

    def test_july_15_partial(self):
        """Julio 15 = 0 meses completos en S2."""
        assert _meses_semestre_gratif(date(2026, 7, 15)) == 0

    def test_december_31_full_s2(self):
        """Diciembre 31 = 6 meses completos (S2 completo)."""
        assert _meses_semestre_gratif(date(2026, 12, 31)) == 6

    def test_december_15_partial(self):
        """Diciembre 15 = 5 meses completos (jul-nov; dic parcial)."""
        assert _meses_semestre_gratif(date(2026, 12, 15)) == 5

    def test_max_capped_at_6(self):
        """Nunca retorna mas de 6."""
        # June 30 is the max for S1
        result = _meses_semestre_gratif(date(2026, 6, 30))
        assert result <= 6


# ══════════════════════════════════════════════════════════════════════════════
# 2. _meses_semestre_cts()
# ══════════════════════════════════════════════════════════════════════════════

class TestMesesSemestreCTS:
    """DL 650: semestres nov-abr (deposito mayo) y may-oct (deposito nov)."""

    # Semestre 1: nov anterior - abril => deposito mayo
    def test_january(self):
        """Enero: nov=1, dic=2, ene=3 => 3 meses."""
        assert _meses_semestre_cts(date(2026, 1, 15)) == 3

    def test_february(self):
        assert _meses_semestre_cts(date(2026, 2, 15)) == 4

    def test_march(self):
        assert _meses_semestre_cts(date(2026, 3, 15)) == 5

    def test_april(self):
        """Abril: nov=1..abr=6 => 6 meses completos."""
        assert _meses_semestre_cts(date(2026, 4, 15)) == 6

    # Semestre 2: mayo - octubre => deposito noviembre
    def test_may(self):
        assert _meses_semestre_cts(date(2026, 5, 15)) == 1

    def test_june(self):
        assert _meses_semestre_cts(date(2026, 6, 15)) == 2

    def test_july(self):
        assert _meses_semestre_cts(date(2026, 7, 15)) == 3

    def test_august(self):
        assert _meses_semestre_cts(date(2026, 8, 15)) == 4

    def test_september(self):
        assert _meses_semestre_cts(date(2026, 9, 15)) == 5

    def test_october(self):
        assert _meses_semestre_cts(date(2026, 10, 15)) == 6

    # Inicio de nuevo periodo: nov-dic
    def test_november(self):
        assert _meses_semestre_cts(date(2026, 11, 15)) == 1

    def test_december(self):
        assert _meses_semestre_cts(date(2026, 12, 15)) == 2


# ══════════════════════════════════════════════════════════════════════════════
# 3. _calcular_liquidacion()
# ══════════════════════════════════════════════════════════════════════════════

class TestCalcularLiquidacion:
    """Tests para el calculo completo de liquidacion."""

    @patch('nominas.views_liquidacion.timezone')
    def _calc(self, personal, mock_tz, vac_mock=None):
        """Helper: ejecuta _calcular_liquidacion con mocks."""
        mock_tz.localdate.return_value = date(2026, 3, 17)

        if vac_mock is None:
            vac_mock = _patch_vacaciones_none()

        with patch('vacaciones.models.SaldoVacacional.objects', vac_mock):
            return _calcular_liquidacion(personal)

    # ── Remuneracion trunca ──────────────────────────────────────────────

    def test_rem_trunca_proportional(self):
        """Rem trunca = sueldo/30 * dias del mes de cese."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 15))
        result = self._calc(p)
        expected = _rd(Decimal('3000') / 30 * 15)
        assert result['rem_trunca'] == expected
        assert result['dias_mes'] == 15

    def test_rem_trunca_full_month(self):
        """Cese el 31 = sueldo completo."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        expected = _rd(Decimal('3000') / 30 * 31)
        assert result['rem_trunca'] == expected

    def test_rem_trunca_day_1(self):
        """Cese el dia 1 = 1/30 del sueldo."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 1))
        result = self._calc(p)
        expected = _rd(Decimal('3000') / 30 * 1)
        assert result['rem_trunca'] == expected

    # ── Gratificacion trunca ─────────────────────────────────────────────

    def test_gratif_trunca_excludes_pension(self):
        """Gratif trunca no descuenta AFP/ONP: es INAFECTA (Ley 29351). El
        descuento pensionario va solo sobre rem_trunca."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        meses = _meses_semestre_gratif(date(2026, 3, 31))  # 3
        expected = _rd(Decimal('3000') / 6 * meses)
        assert result['gratif_trunca'] == expected
        assert result['meses_gratif'] == meses

    def test_gratif_trunca_with_asig_familiar(self):
        """Gratif trunca incluye asignacion familiar en la base."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           asignacion_familiar=True)
        result = self._calc(p)
        base = Decimal('3000') + ASIG_FAM
        meses = 3  # mar 31 in S1
        expected = _rd(base / 6 * meses)
        assert result['gratif_trunca'] == expected

    # ── CTS trunca ───────────────────────────────────────────────────────

    def test_cts_trunca_calculation(self):
        """CTS trunca = (sueldo + asig_fam + sueldo/6) / 12 * meses_cts."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 15))
        result = self._calc(p)

        sueldo = Decimal('3000')
        prov_grat = _rd(sueldo / 6)
        base_cts = sueldo + Decimal('0') + prov_grat  # no asig fam
        meses_cts = _meses_semestre_cts(date(2026, 3, 15))  # 5
        expected = _rd(base_cts / 12 * meses_cts)

        assert result['cts_trunca'] == expected
        assert result['meses_cts'] == meses_cts

    def test_cts_trunca_with_asig_familiar(self):
        """CTS base incluye asignacion familiar + 1/6 de gratif (sobre rem computable)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 6, 30),
                           asignacion_familiar=True)
        result = self._calc(p)

        sueldo = Decimal('3000')
        # prov_gratif se calcula sobre la remuneracion computable (sueldo + asig_fam),
        # no solo sueldo. Es lo legalmente correcto (Ley 25129 + DL 650).
        prov_grat = _rd((sueldo + ASIG_FAM) / 6)
        base_cts = sueldo + ASIG_FAM + prov_grat
        assert result['base_cts'] == base_cts

    # ── Vacaciones pendientes ────────────────────────────────────────────

    def test_vac_pendientes_with_saldo(self):
        """Vac pendientes = sueldo/30 × dias_pendientes (del saldo).
        Truncos = proporcional al período en curso (fecha_alta→cese): 2 meses → 5 días."""
        # alta 30-ene, cese 31-mar → 60 días = 2 meses → 5 días truncos
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           fecha_alta=date(2026, 1, 30))
        vac_mock = _patch_vacaciones(dias_pendientes=15, dias_truncos=0)
        result = self._calc(p, vac_mock=vac_mock)

        assert result['vac_pendientes'] == _rd(Decimal('3000') / 30 * 15)
        assert result['vac_truncas'] == _rd(Decimal('3000') / 30 * 5)
        assert result['dias_pendientes'] == 15

    def test_vac_truncas_primer_anio_sin_saldo(self):
        """Regresión: trabajador que cesa en su PRIMER año (sin SaldoVacacional)
        igual cobra vacaciones truncas proporcionales. Antes daba 0 porque la
        liquidación leía sv.dias_truncos (siempre 0)."""
        # alta 30-ene, cese 31-mar → 2 meses → 5 días truncos (DL 713 Art. 22)
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           fecha_alta=date(2026, 1, 30))
        result = self._calc(p)  # sin SaldoVacacional
        assert result['vac_pendientes'] == Decimal('0')
        assert result['vac_truncas'] == _rd(Decimal('3000') / 30 * 5)

    def test_vac_no_saldo_ni_fecha_alta(self):
        """Sin SaldoVacacional ni fecha_alta, vacaciones = 0."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        assert result['vac_pendientes'] == Decimal('0')
        assert result['vac_truncas'] == Decimal('0')

    # ── AFP rates use employee's actual AFP ──────────────────────────────

    def test_afp_uses_employee_afp_habitat(self):
        """Descuento pension usa tasas de la AFP del empleado (Habitat)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           regimen_pension='AFP', afp='Habitat')
        result = self._calc(p)

        base = result['rem_trunca']  # gratif inafecta (Ley 29351)
        tasas = AFP_TASAS['Habitat']
        aporte = _rd(base * AFP_APORTE)
        comision = _rd(base * tasas['comision_flujo'] / Decimal('100'))
        seguro = _rd(base * tasas['seguro'] / Decimal('100'))
        expected = aporte + comision + seguro

        assert result['descto_pension'] == expected

    def test_afp_uses_employee_afp_profuturo(self):
        """Descuento pension usa tasas de Profuturo."""
        p = _make_personal(sueldo_base=5000, fecha_cese=date(2026, 6, 30),
                           regimen_pension='AFP', afp='Profuturo')
        result = self._calc(p)

        base = result['rem_trunca']  # gratif inafecta (Ley 29351)
        tasas = AFP_TASAS['Profuturo']
        aporte = _rd(base * AFP_APORTE)
        comision = _rd(base * tasas['comision_flujo'] / Decimal('100'))
        seguro = _rd(base * tasas['seguro'] / Decimal('100'))
        expected = aporte + comision + seguro

        assert result['descto_pension'] == expected

    def test_afp_defaults_to_prima_when_none(self):
        """Si afp es None, usa tasas de Prima."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           regimen_pension='AFP', afp=None)
        result = self._calc(p)

        base = result['rem_trunca']  # gratif inafecta (Ley 29351)
        tasas = AFP_TASAS['Prima']
        aporte = _rd(base * AFP_APORTE)
        comision = _rd(base * tasas['comision_flujo'] / Decimal('100'))
        seguro = _rd(base * tasas['seguro'] / Decimal('100'))
        expected = aporte + comision + seguro

        assert result['descto_pension'] == expected

    # ── ONP calculation ──────────────────────────────────────────────────

    def test_onp_calculation(self):
        """ONP = 13% sobre rem_trunca (gratif inafecta)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           regimen_pension='ONP')
        result = self._calc(p)

        base = result['rem_trunca']  # gratif inafecta (Ley 29351)
        expected = _rd(base * ONP_TASA)
        assert result['descto_pension'] == expected
        assert result['regimen_pension'] == 'ONP'

    # ── Bonus extraordinario 9% ──────────────────────────────────────────

    def test_bonus_extraordinario(self):
        """Bonus extraordinario = 9% de gratif trunca (Ley 29351)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        expected = _rd(result['gratif_trunca'] * Decimal('0.09'))
        assert result['bonus_ext'] == expected

    # ── EsSalud empleador ────────────────────────────────────────────────

    def test_essalud_empleador(self):
        """EsSalud = 9% sobre rem_trunca + gratif_trunca."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        expected = _rd((result['rem_trunca'] + result['gratif_trunca']) * ESSALUD)
        assert result['essalud_empleador'] == expected

    # ── Totales ──────────────────────────────────────────────────────────

    def test_total_haberes(self):
        """total_haberes = rem + gratif + cts + vac_pend + vac_trunc + bonus."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        expected = (
            result['rem_trunca'] + result['gratif_trunca'] +
            result['cts_trunca'] + result['vac_pendientes'] +
            result['vac_truncas'] + result['bonus_ext']
        )
        assert result['total_haberes'] == expected

    def test_neto_pagar(self):
        """neto = total_haberes - total_desctos."""
        p = _make_personal(sueldo_base=4000, fecha_cese=date(2026, 6, 30),
                           regimen_pension='AFP', afp='Integra')
        result = self._calc(p)
        assert result['neto_pagar'] == result['total_haberes'] - result['total_desctos']

    def test_total_desctos_equals_pension(self):
        """total_desctos = descto_pension (no hay otros descuentos en liquidacion)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        assert result['total_desctos'] == result['descto_pension']


# ══════════════════════════════════════════════════════════════════════════════
# 4. Edge cases
# ══════════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Casos borde y escenarios atipicos."""

    @patch('nominas.views_liquidacion.timezone')
    def _calc(self, personal, mock_tz, vac_mock=None):
        mock_tz.localdate.return_value = date(2026, 3, 17)
        if vac_mock is None:
            vac_mock = _patch_vacaciones_none()
        with patch('vacaciones.models.SaldoVacacional.objects', vac_mock):
            return _calcular_liquidacion(personal)

    def test_same_day_hire_termination(self):
        """Cese el dia 1 del mes: rem_trunca = 1/30 del sueldo."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 1, 1))
        result = self._calc(p)
        assert result['rem_trunca'] == _rd(Decimal('3000') / 30 * 1)
        assert result['dias_mes'] == 1
        # January 1 is not the last day of month => 0 complete months
        assert result['meses_gratif'] == 0
        assert result['gratif_trunca'] == Decimal('0')

    def test_without_asignacion_familiar(self):
        """Sin asignacion familiar, asig_fam = 0."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           asignacion_familiar=False)
        result = self._calc(p)
        assert result['asig_fam'] == Decimal('0')

    def test_with_asignacion_familiar(self):
        """Con asignacion familiar, asig_fam = 10% RMV."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           asignacion_familiar=True)
        result = self._calc(p)
        assert result['asig_fam'] == ASIG_FAM

    def test_sin_pension_regime(self):
        """Regimen SIN_PENSION: no descuenta AFP ni ONP."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31),
                           regimen_pension='SIN_PENSION')
        result = self._calc(p)
        assert result['descto_pension'] == Decimal('0')
        assert result['total_desctos'] == Decimal('0')
        assert result['neto_pagar'] == result['total_haberes']

    def test_zero_salary(self):
        """Sueldo 0: todo queda en 0."""
        p = _make_personal(sueldo_base=0, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        assert result['rem_trunca'] == Decimal('0')
        assert result['gratif_trunca'] == Decimal('0')
        assert result['cts_trunca'] == Decimal('0')
        assert result['neto_pagar'] == Decimal('0')

    def test_no_fecha_cese_uses_today(self):
        """Sin fecha_cese, usa timezone.localdate() (mocked to 2026-03-17)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=None)
        result = self._calc(p)
        assert result['fecha_cese'] == date(2026, 3, 17)
        assert result['dias_mes'] == 17

    def test_high_salary(self):
        """Sueldo alto: calculos siguen siendo correctos."""
        p = _make_personal(sueldo_base=50000, fecha_cese=date(2026, 6, 30),
                           asignacion_familiar=True, regimen_pension='AFP',
                           afp='Profuturo')
        result = self._calc(p)
        # Basic sanity: neto > 0 and neto < total_haberes
        assert result['neto_pagar'] > 0
        assert result['neto_pagar'] < result['total_haberes']
        assert result['meses_gratif'] == 6

    def test_all_return_keys_present(self):
        """Verifica que _calcular_liquidacion retorna todas las claves esperadas."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))
        result = self._calc(p)
        expected_keys = {
            'fecha_cese', 'sueldo_base', 'asig_fam',
            'rem_trunca', 'dias_mes',
            'gratif_trunca', 'meses_gratif', 'bonus_ext',
            'cts_trunca', 'meses_cts', 'base_cts',
            'vac_pendientes', 'dias_pendientes', 'vac_truncas', 'dias_truncos',
            'regimen_pension', 'descto_pension',
            'essalud_empleador', 'total_haberes', 'total_desctos', 'neto_pagar',
        }
        assert set(result.keys()) == expected_keys

    def test_vacaciones_exception_handled(self):
        """Si vacaciones.models falla, vacaciones = 0 (no crash)."""
        p = _make_personal(sueldo_base=3000, fecha_cese=date(2026, 3, 31))

        # Patch the import to raise an exception
        with patch('nominas.views_liquidacion.timezone') as mock_tz:
            mock_tz.localdate.return_value = date(2026, 3, 17)
            with patch.dict('sys.modules', {'vacaciones': None, 'vacaciones.models': None}):
                # The try/except in _calcular_liquidacion handles ImportError
                result = _calcular_liquidacion(p)
                assert result['vac_pendientes'] == Decimal('0')
                assert result['vac_truncas'] == Decimal('0')
