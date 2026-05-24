"""
Tests para las 4 calculadoras especializadas + comparativa interanual.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase


User = get_user_model()


class CalculadoraReversaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='rev_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_reversa_get(self):
        resp = self.client.get('/nominas/calculadora/reversa/')
        self.assertEqual(resp.status_code, 200)

    def test_reversa_post_encuentra_bruto(self):
        """Para neto 2000 con ONP, el bruto sugerido debe dar neto cercano."""
        resp = self.client.post('/nominas/calculadora/reversa/', {
            'neto_objetivo': '2000',
            'regimen': 'ONP',
        })
        self.assertEqual(resp.status_code, 200)
        result = resp.context['result']
        self.assertNotIn('error', result)
        # El neto resultante debe estar a ≤ S/0.50 del objetivo
        self.assertLessEqual(abs(result['detalle']['neto'] - Decimal('2000')), Decimal('0.50'))


class CalculadoraGratificacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='grt_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_gratif_get(self):
        resp = self.client.get('/nominas/calculadora/gratificacion/')
        self.assertEqual(resp.status_code, 200)

    def test_gratif_semestre_completo_sin_eps(self):
        """Sueldo 2500, 6 meses, sin EPS: gratif=2500, bonif 9%=225, total=2725."""
        resp = self.client.post('/nominas/calculadora/gratificacion/', {
            'sueldo': '2500', 'meses': '6',
        })
        result = resp.context['result']
        self.assertEqual(result['gratif'], Decimal('2500.00'))
        self.assertEqual(result['bonif_extra'], Decimal('225.00'))
        self.assertEqual(result['total'], Decimal('2725.00'))

    def test_gratif_con_eps_bonif_675(self):
        """Con EPS, bonif baja de 9% a 6.75%."""
        resp = self.client.post('/nominas/calculadora/gratificacion/', {
            'sueldo': '2500', 'meses': '6', 'tiene_eps': 'on',
        })
        result = resp.context['result']
        self.assertEqual(result['bonif_tasa'], Decimal('6.75'))
        # 2500 * 6.75% = 168.75
        self.assertEqual(result['bonif_extra'], Decimal('168.75'))
        self.assertEqual(result['total'], Decimal('2668.75'))

    def test_gratif_3_meses_proporcional(self):
        """3 meses = mitad de gratif."""
        resp = self.client.post('/nominas/calculadora/gratificacion/', {
            'sueldo': '2400', 'meses': '3',
        })
        result = resp.context['result']
        # 2400 × 3/6 = 1200, bonif 9% = 108, total 1308
        self.assertEqual(result['gratif'], Decimal('1200.00'))
        self.assertEqual(result['total'], Decimal('1308.00'))


class CalculadoraCTSTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='cts_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_cts_get(self):
        resp = self.client.get('/nominas/calculadora/cts/')
        self.assertEqual(resp.status_code, 200)

    def test_cts_semestre_completo(self):
        """Sueldo 2400, 6 meses, sin días extra.
        Rem computable = 2400 + 400 = 2800.
        CTS = 2800 × 6/12 = 1400.
        """
        resp = self.client.post('/nominas/calculadora/cts/', {
            'sueldo': '2400', 'meses': '6', 'dias_extra': '0',
        })
        result = resp.context['result']
        self.assertEqual(result['rem_computable'], Decimal('2800.00'))
        self.assertEqual(result['cts_meses'], Decimal('1400.00'))
        self.assertEqual(result['total'], Decimal('1400.00'))

    def test_cts_con_dias_extra(self):
        """Sueldo 2400, 4 meses + 15 días."""
        resp = self.client.post('/nominas/calculadora/cts/', {
            'sueldo': '2400', 'meses': '4', 'dias_extra': '15',
        })
        result = resp.context['result']
        # cts_meses = 2800 × 4/12 = 933.33
        # cts_dias = 2800 × 15/12/30 = 116.67
        # total = 1050
        self.assertAlmostEqual(float(result['cts_meses']), 933.33, places=2)
        self.assertAlmostEqual(float(result['cts_dias']), 116.67, places=2)
        self.assertAlmostEqual(float(result['total']), 1050.00, places=2)


class CalculadoraLiquidacionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='liq_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_liq_get(self):
        resp = self.client.get('/nominas/calculadora/liquidacion/')
        self.assertEqual(resp.status_code, 200)

    def test_liq_calcula_componentes(self):
        """Test liquidación con datos típicos."""
        resp = self.client.post('/nominas/calculadora/liquidacion/', {
            'sueldo': '3000',
            'fecha_ingreso': '2023-01-01',
            'fecha_cese':    '2026-05-15',
            'dias_vacaciones_pendientes': '0',
        })
        result = resp.context['result']
        self.assertNotIn('error', result)
        # Debe tener todos los componentes
        self.assertIn('vacaciones', result)
        self.assertIn('gratificacion', result)
        self.assertIn('cts', result)
        self.assertIn('sueldo_mes_cese', result)
        # Total > 0
        self.assertGreater(result['total'], Decimal('0'))

    def test_liq_fecha_invalida(self):
        """Fecha cese < ingreso → error."""
        resp = self.client.post('/nominas/calculadora/liquidacion/', {
            'sueldo': '3000',
            'fecha_ingreso': '2026-05-01',
            'fecha_cese':    '2024-01-01',
            'dias_vacaciones_pendientes': '0',
        })
        result = resp.context['result']
        self.assertIn('error', result)


class ComparativoInteranualTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='int_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_interanual_renderiza(self):
        resp = self.client.get('/nominas/interanual/?anio=2026&mes=5')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Comparativa Interanual')

    def test_interanual_helper_delta_pct(self):
        from nominas.views_interanual import _delta_pct
        # 100 → 130 = +30%
        self.assertEqual(_delta_pct(Decimal('100'), Decimal('130')), 30.0)
        # 0 → 50 = None (defensiva)
        self.assertIsNone(_delta_pct(Decimal('0'), Decimal('50')))


class CalcEspecializadasMatTests(TestCase):
    """Tests directos al motor matemático (rápidos, sin HTTP)."""

    def test_gratif_sin_eps_exacto(self):
        from nominas.views_calc_especializadas import _calcular_gratificacion
        g = _calcular_gratificacion(Decimal('2500'), 6, tiene_eps=False)
        self.assertEqual(g['gratif'],     Decimal('2500.00'))
        self.assertEqual(g['bonif_extra'], Decimal('225.00'))  # 2500 × 9%
        self.assertEqual(g['total'],      Decimal('2725.00'))

    def test_gratif_eps_reduce_bonif(self):
        from nominas.views_calc_especializadas import _calcular_gratificacion
        g = _calcular_gratificacion(Decimal('2500'), 6, tiene_eps=True)
        self.assertEqual(g['bonif_tasa'], Decimal('6.75'))
        self.assertEqual(g['bonif_extra'], Decimal('168.75'))

    def test_cts_helper(self):
        from nominas.views_calc_especializadas import _calcular_cts
        cts = _calcular_cts(Decimal('2400'), 6)
        self.assertEqual(cts['rem_computable'], Decimal('2800.00'))
        self.assertEqual(cts['total'], Decimal('1400.00'))

    def test_reversa_helper(self):
        """Búsqueda binaria converge a la solución correcta."""
        from nominas.views_calc_especializadas import _bruto_para_neto
        bruto, det = _bruto_para_neto(Decimal('1500'), {
            'asig_familiar': False, 'horas_extra': '0', 'comisiones': '0',
            'regimen': 'ONP', 'tiene_eps': False, 'sctr_tasa': '0',
        })
        # Neto resultante debe estar a ±S/ 0.50 del objetivo
        self.assertLessEqual(abs(det['neto'] - Decimal('1500')), Decimal('0.50'))
