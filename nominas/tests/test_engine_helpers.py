"""
Tests para los nuevos helpers del engine:
- valor_hora / calcular_he (HE 25/35/100/50)
- calcular_subsidio_incapacidad (Ley 26790, días 1-20 vs día 21+)
- calcular_subsidio_maternidad (98 días Ley 30367)
- calcular_pension_alimenticia (Art. 648 CPC, tope 60%)
- calcular_embargo_civil (5 URP inembargable, 1/3 exceso)
- calcular_bonif_escolaridad
"""
from decimal import Decimal

from django.test import TestCase

from nominas.engine import (
    calcular_bonif_escolaridad,
    calcular_embargo_civil,
    calcular_he,
    calcular_pension_alimenticia,
    calcular_subsidio_incapacidad,
    calcular_subsidio_maternidad,
    valor_hora,
)


class ValorHoraTests(TestCase):
    def test_valor_hora_standard(self):
        """2400/30/8 = 10.00"""
        self.assertEqual(valor_hora(Decimal('2400')), Decimal('10.00'))

    def test_valor_hora_distinto_jornada(self):
        """Si la jornada es 6h: 2400/30/6 = 13.33"""
        self.assertEqual(valor_hora(Decimal('2400'), jornada_horas=6), Decimal('13.33'))

    def test_valor_hora_cero_o_negativo_defensiva(self):
        """Defensiva: sueldo <= 0 → devuelve 0 (no permite negativos)."""
        self.assertEqual(valor_hora(Decimal('0')), Decimal('0'))
        self.assertEqual(valor_hora(Decimal('-100')), Decimal('0'))


class CalcularHETests(TestCase):
    def test_he_25_basico(self):
        """4h × 10 × 1.25 = 50.00"""
        self.assertEqual(calcular_he(Decimal('4'), Decimal('2400'), 'HE_25'), Decimal('50.00'))

    def test_he_35_basico(self):
        """4h × 10 × 1.35 = 54.00"""
        self.assertEqual(calcular_he(Decimal('4'), Decimal('2400'), 'HE_35'), Decimal('54.00'))

    def test_he_100_feriado(self):
        """8h × 12.50 × 2 = 200.00 con sueldo 3000"""
        self.assertEqual(calcular_he(Decimal('8'), Decimal('3000'), 'HE_100'), Decimal('200.00'))

    def test_he_50_custom_convenio(self):
        """Sobretasa 50% — convenio mejor que ley"""
        self.assertEqual(calcular_he(Decimal('2'), Decimal('2400'), 'HE_50'), Decimal('30.00'))

    def test_he_tipo_invalido_fallback_25(self):
        """Tipo inválido → fallback HE_25"""
        self.assertEqual(
            calcular_he(Decimal('4'), Decimal('2400'), 'HE_XYZ'),
            calcular_he(Decimal('4'), Decimal('2400'), 'HE_25'),
        )

    def test_he_horas_cero(self):
        self.assertEqual(calcular_he(Decimal('0'), Decimal('2400')), Decimal('0'))


class SubsidioIncapacidadTests(TestCase):
    def test_dias_1_a_20_empleador_paga(self):
        """20 días × 100 = 2000 paga empleador, 0 ESSALUD"""
        r = calcular_subsidio_incapacidad(Decimal('3000'), 20)
        self.assertEqual(r['dias_empleador'], 20)
        self.assertEqual(r['monto_empleador'], Decimal('2000.00'))
        self.assertEqual(r['dias_essalud'], 0)
        self.assertEqual(r['monto_essalud_subsidio'], Decimal('0'))

    def test_dia_21_essalud_paga(self):
        """30 días: 20 emp (2000) + 10 ESSALUD (1000) = 3000"""
        r = calcular_subsidio_incapacidad(Decimal('3000'), 30)
        self.assertEqual(r['monto_empleador'], Decimal('2000.00'))
        self.assertEqual(r['monto_essalud_subsidio'], Decimal('1000.00'))
        self.assertEqual(r['total_monto'], Decimal('3000.00'))

    def test_tope_340_dias(self):
        """ESSALUD paga hasta 340 días (11m10d). Más: no pagable."""
        r = calcular_subsidio_incapacidad(Decimal('3000'), 400)
        self.assertEqual(r['dias_empleador'], 20)
        self.assertEqual(r['dias_essalud'], 340)
        self.assertTrue(r['limite_alcanzado'])

    def test_dias_cero(self):
        r = calcular_subsidio_incapacidad(Decimal('3000'), 0)
        self.assertEqual(r['total_monto'], Decimal('0'))


class SubsidioMaternidadTests(TestCase):
    def test_98_dias_default(self):
        """3000/30 × 98 = 100 × 98 = 9800"""
        r = calcular_subsidio_maternidad(Decimal('3000'))
        self.assertEqual(r['dias'], 98)
        self.assertEqual(r['valor_diario'], Decimal('100.00'))
        self.assertEqual(r['monto'], Decimal('9800.00'))

    def test_dias_custom(self):
        """Caso atípico — primer hijo + complicaciones (149 días?)"""
        r = calcular_subsidio_maternidad(Decimal('3000'), dias=149)
        self.assertEqual(r['dias'], 149)
        self.assertEqual(r['monto'], Decimal('14900.00'))

    def test_sueldo_invalido(self):
        r = calcular_subsidio_maternidad(Decimal('0'))
        self.assertEqual(r['monto'], Decimal('0'))


class PensionAlimenticiaTests(TestCase):
    def test_30_pct_sobre_3000_menos_600_desc(self):
        """Base = 3000-600 = 2400. 30% = 720"""
        r = calcular_pension_alimenticia(
            Decimal('3000'), Decimal('600'), Decimal('30'),
        )
        self.assertEqual(r['base_calculo'], Decimal('2400.00'))
        self.assertEqual(r['monto'], Decimal('720.00'))
        self.assertFalse(r['tope_legal_60_alcanzado'])

    def test_tope_60_pct_aplicado(self):
        """Si el juez ordena 80% → se trunca a 60% (Art. 648 CPC)"""
        r = calcular_pension_alimenticia(
            Decimal('3000'), Decimal('0'), Decimal('80'),
        )
        self.assertEqual(r['porcentaje_aplicado'], Decimal('60'))
        self.assertTrue(r['tope_legal_60_alcanzado'])

    def test_descuentos_mayores_que_rem(self):
        """Base = max(0, rem - desc). Si desc > rem → base = 0"""
        r = calcular_pension_alimenticia(
            Decimal('1000'), Decimal('1500'), Decimal('30'),
        )
        self.assertEqual(r['base_calculo'], Decimal('0'))
        self.assertEqual(r['monto'], Decimal('0'))


class EmbargoCivilTests(TestCase):
    def test_inembargable_si_no_excede_5_urp(self):
        """5 URP = 5 × (10% UIT 5500) = 2750 inembargable. Sueldo 2500 → no aplica."""
        r = calcular_embargo_civil(Decimal('2500'), uit=Decimal('5500'))
        self.assertEqual(r['exceso'], Decimal('0'))
        self.assertEqual(r['monto_max_embargo'], Decimal('0'))
        self.assertFalse(r['aplica_embargo'])

    def test_sobre_5_urp_un_tercio_embargable(self):
        """Sueldo 8000, inembargable 5 URP = 2750, exceso 5250, embargo max = 5250/3 = 1750.00"""
        r = calcular_embargo_civil(Decimal('8000'), uit=Decimal('5500'))
        self.assertEqual(r['inembargable'], Decimal('2750.00'))
        self.assertEqual(r['exceso'], Decimal('5250.00'))
        self.assertEqual(r['monto_max_embargo'], Decimal('1750.00'))
        self.assertTrue(r['aplica_embargo'])


class BonifEscolaridadTests(TestCase):
    def test_1_sueldo(self):
        self.assertEqual(
            calcular_bonif_escolaridad(Decimal('2400')),
            Decimal('2400.00'),
        )

    def test_multiplicador_05(self):
        """Algunos convenios pagan 50% sueldo"""
        self.assertEqual(
            calcular_bonif_escolaridad(Decimal('2400'), Decimal('0.5')),
            Decimal('1200.00'),
        )

    def test_sueldo_cero(self):
        self.assertEqual(calcular_bonif_escolaridad(Decimal('0')), Decimal('0'))


class TemplatesNuevosTests(TestCase):
    """Verificar que los 12 nuevos templates existen y están bien estructurados."""

    def test_nuevos_templates_en_diccionario(self):
        from nominas.views_conceptos import TEMPLATES_CONCEPTOS
        nuevos = [
            'horas_extras_100', 'horas_extras_nocturnas',
            'bonif_feriado_trabajado', 'subsidio_incapacidad',
            'subsidio_maternidad', 'subsidio_lactancia',
            'bonif_escolaridad', 'pension_alimenticia',
            'embargo_civil', 'cuota_sindical',
            'seguro_vida_ley', 'estimulo_educacional',
        ]
        for codigo in nuevos:
            self.assertIn(codigo, TEMPLATES_CONCEPTOS, f'Falta template: {codigo}')
            t = TEMPLATES_CONCEPTOS[codigo]
            # Cada uno debe tener campos obligatorios
            self.assertIn('nombre', t)
            self.assertIn('categoria', t)
            self.assertIn('tipo', t)
            self.assertIn('subtipo', t)

    def test_subsidios_son_no_remunerativos(self):
        """Por norma, subsidios maternidad e incapacidad >20d son no remunerativos."""
        from nominas.views_conceptos import TEMPLATES_CONCEPTOS
        for codigo in ['subsidio_incapacidad', 'subsidio_maternidad', 'estimulo_educacional']:
            t = TEMPLATES_CONCEPTOS[codigo]
            self.assertEqual(t['subtipo'], 'NO_REMUNERATIVO')
            self.assertFalse(t.get('afecto_essalud', False))
            self.assertFalse(t.get('afecto_afp', False))

    def test_pension_alimenticia_es_descuento(self):
        from nominas.views_conceptos import TEMPLATES_CONCEPTOS
        t = TEMPLATES_CONCEPTOS['pension_alimenticia']
        self.assertEqual(t['tipo'], 'DESCUENTO')
        self.assertEqual(t['categoria'], 'DESCUENTO')

    def test_he_nocturnas_y_100_tienen_formula_correcta(self):
        from nominas.views_conceptos import TEMPLATES_CONCEPTOS
        self.assertEqual(TEMPLATES_CONCEPTOS['horas_extras_100']['formula'], 'HE_100')
        self.assertEqual(TEMPLATES_CONCEPTOS['horas_extras_nocturnas']['formula'], 'HE_35')
