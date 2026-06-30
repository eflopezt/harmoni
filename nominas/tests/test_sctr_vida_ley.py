"""
Tests para los aportes de riesgo del empleador y el pase genérico fórmula-driven
del motor de nómina (nominas/engine.py).

Cubre:
- SCTR Salud / SCTR Pensión: solo para trabajadores afecto_sctr.
- Seguro Vida Ley (D.Leg. 688): para todos los trabajadores.
- Activación/desactivación vía ConfiguracionSistema (_get_aportes_riesgo).
- costo_total_empresa incluye SCTR + Vida Ley.
- Pase genérico: conceptos aplicar_automatico=True calculan solos.

Mock-based (sin DB) salvo donde se indica.
"""
from decimal import Decimal, ROUND_HALF_UP
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from nominas.engine import calcular_registro, UIT_2026, RMV_2026


UIT = UIT_2026
RMV = RMV_2026


def _r(val):
    return Decimal(val).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _make_registro(afecto_sctr=False, **overrides):
    defaults = {
        'sueldo_base': Decimal('3000.00'),
        'dias_trabajados': 30,
        'regimen_pension': 'ONP',
        'afp': '',
        'asignacion_familiar': False,
        'horas_extra_25': Decimal('0'),
        'horas_extra_35': Decimal('0'),
        'horas_extra_100': Decimal('0'),
        'otros_ingresos': Decimal('0'),
        'descuento_prestamo': Decimal('0'),
        'otros_descuentos': Decimal('0'),
        # personal sin pk → el engine no consulta DescuentoPlanilla
        'personal': SimpleNamespace(afecto_sctr=afecto_sctr, pk=None),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _mock_conceptos():
    """Queryset mock: .get(codigo=) devuelve un stub para cualquier código.
    No es iterable → el pase genérico hace no-op (lo cubre otro test)."""
    qs = MagicMock()
    qs.get = lambda codigo=None: SimpleNamespace(codigo=codigo, nombre=codigo)
    return qs


_RIESGO_DEFAULT = {
    'sctr_activo': True, 'sctr_salud_tasa': Decimal('0.80'),
    'sctr_pension_tasa': Decimal('0.73'), 'vida_ley_activo': True,
    'vida_ley_tasa': Decimal('0.71'),
}


@pytest.fixture(autouse=True)
def _patch_config():
    # Parchea las tasas de riesgo a los referenciales por defecto para que los
    # montos sean deterministas (sin depender de la fila ConfiguracionSistema
    # que pueda persistir en la test-DB con --keepdb).
    with patch('nominas.engine._get_uit', return_value=UIT), \
         patch('nominas.engine._get_rmv', return_value=RMV), \
         patch('nominas.engine._get_aportes_riesgo', return_value=dict(_RIESGO_DEFAULT)):
        yield


# ── SCTR ────────────────────────────────────────────────────────────────────

class TestSCTR:
    def test_afecto_sctr_calcula_salud_y_pension(self):
        res = calcular_registro(_make_registro(afecto_sctr=True), _mock_conceptos())
        rem = res['rem_computable']
        assert res['aporte_sctr_salud'] == _r(rem * Decimal('0.0080'))
        assert res['aporte_sctr_pension'] == _r(rem * Decimal('0.0073'))

    def test_no_afecto_sctr_es_cero(self):
        res = calcular_registro(_make_registro(afecto_sctr=False), _mock_conceptos())
        assert res['aporte_sctr_salud'] == Decimal('0')
        assert res['aporte_sctr_pension'] == Decimal('0')

    def test_sctr_desactivado_en_config(self):
        params = {
            'sctr_activo': False, 'sctr_salud_tasa': Decimal('1.55'),
            'sctr_pension_tasa': Decimal('1.30'), 'vida_ley_activo': True,
            'vida_ley_tasa': Decimal('0.53'),
        }
        with patch('nominas.engine._get_aportes_riesgo', return_value=params):
            res = calcular_registro(_make_registro(afecto_sctr=True), _mock_conceptos())
        assert res['aporte_sctr_salud'] == Decimal('0')
        assert res['aporte_sctr_pension'] == Decimal('0')
        # Vida Ley sigue activo
        assert res['aporte_vida_ley'] > 0


# ── Vida Ley ──────────────────────────────────────────────────────────────────

class TestVidaLey:
    def test_vida_ley_aplica_a_todos(self):
        res = calcular_registro(_make_registro(afecto_sctr=False), _mock_conceptos())
        rem = res['rem_computable']
        assert res['aporte_vida_ley'] == _r(rem * Decimal('0.0071'))

    def test_vida_ley_desactivado(self):
        params = {
            'sctr_activo': True, 'sctr_salud_tasa': Decimal('1.55'),
            'sctr_pension_tasa': Decimal('1.30'), 'vida_ley_activo': False,
            'vida_ley_tasa': Decimal('0.53'),
        }
        with patch('nominas.engine._get_aportes_riesgo', return_value=params):
            res = calcular_registro(_make_registro(), _mock_conceptos())
        assert res['aporte_vida_ley'] == Decimal('0')


# ── Costo empresa ─────────────────────────────────────────────────────────────

class TestCostoEmpresa:
    def test_costo_incluye_sctr_y_vida_ley(self):
        res = calcular_registro(_make_registro(afecto_sctr=True), _mock_conceptos())
        rem = res['rem_computable']
        essalud = _r(rem * Decimal('0.09'))
        sctr_s = _r(rem * Decimal('0.0080'))
        sctr_p = _r(rem * Decimal('0.0073'))
        vida = _r(rem * Decimal('0.0071'))
        base_g = res['rem_computable']  # sin asig familiar
        prov_g = _r(base_g / Decimal('6'))
        prov_c = _r((base_g + prov_g) / Decimal('12'))
        esperado = _r(res['total_ingresos'] + essalud + sctr_s + sctr_p + vida
                      + prov_g + prov_c)
        assert res['costo_total_empresa'] == esperado


# ── Pase genérico fórmula-driven ──────────────────────────────────────────────

class _FakeConceptos(list):
    """Soporta .get(codigo=) (para _agregar) e iteración (para el pase genérico)."""
    def get(self, codigo=None):
        from nominas.models import ConceptoRemunerativo
        for c in self:
            if c.codigo == codigo:
                return c
        raise ConceptoRemunerativo.DoesNotExist()


def _concepto(codigo, tipo, formula='PORCENTAJE', porcentaje='0', monto_fijo='0',
              aplicar_automatico=False):
    return SimpleNamespace(
        codigo=codigo, nombre=codigo, tipo=tipo, formula=formula,
        porcentaje=Decimal(str(porcentaje)), monto_fijo=Decimal(str(monto_fijo)),
        aplicar_automatico=aplicar_automatico,
    )


@pytest.mark.django_db
class TestPaseGenerico:
    def test_concepto_automatico_porcentaje_se_calcula(self):
        bono = _concepto('bono-general', 'INGRESO', 'PORCENTAJE',
                         porcentaje='5', aplicar_automatico=True)
        conceptos = _FakeConceptos([bono])
        res = calcular_registro(_make_registro(), conceptos)
        rem = res['rem_computable']
        linea = next((l for l in res['lineas'] if l['concepto'].codigo == 'bono-general'), None)
        assert linea is not None
        assert linea['monto'] == _r(rem * Decimal('0.05'))
        # El ingreso automático sube el bruto
        assert res['total_ingresos'] == rem + linea['monto']

    def test_concepto_sin_flag_no_se_calcula(self):
        bono = _concepto('bono-no-auto', 'INGRESO', 'PORCENTAJE',
                         porcentaje='5', aplicar_automatico=False)
        conceptos = _FakeConceptos([bono])
        res = calcular_registro(_make_registro(), conceptos)
        assert all(l['concepto'].codigo != 'bono-no-auto' for l in res['lineas'])

    def test_descuento_automatico_baja_neto(self):
        cuota = _concepto('aporte-mutual', 'DESCUENTO', 'PORCENTAJE',
                          porcentaje='1', aplicar_automatico=True)
        conceptos = _FakeConceptos([cuota])
        res_con = calcular_registro(_make_registro(), conceptos)
        res_sin = calcular_registro(_make_registro(), _FakeConceptos([]))
        rem = res_con['rem_computable']
        assert res_sin['neto_a_pagar'] - res_con['neto_a_pagar'] == _r(rem * Decimal('0.01'))
