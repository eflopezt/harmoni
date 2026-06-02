"""
Tests adicionales para `nominas.engine` — cobertura ≥50%.

Cubre:
- Helpers puros (sin DB): valor_hora, calcular_he, subsidios,
  pension alimenticia, embargo civil, escolaridad, prov gratif.
- IR 5ta categoría — escala progresiva completa (4 tramos + exonerado),
  tanto método legacy como método SUNAT (acumulado).
- `calcular_registro` con régimen ONP, AFP, con/sin asignación familiar,
  con horas extra, con IR retención.
- `calcular_gratificacion` semestre completo y fraccional, con/sin EPS.
- `calcular_cts` semestral.
- `generar_periodo` end-to-end — 2 trabajadores, asserts en registros y totales.
"""
from datetime import date
from decimal import Decimal
from time import time

import pytest

from nominas.engine import (
    calcular_bonif_escolaridad,
    calcular_cts,
    calcular_embargo_civil,
    calcular_gratificacion,
    calcular_he,
    calcular_ir_5ta_mensual,
    calcular_pension_alimenticia,
    calcular_prov_gratif,
    calcular_registro,
    calcular_subsidio_incapacidad,
    calcular_subsidio_maternidad,
    generar_periodo,
    valor_hora,
    _calcular_ir_5ta_sunat,
    _ir_anual,
)


# ════════════════════════════════════════════════════════════════════
# Helpers puros — no DB
# ════════════════════════════════════════════════════════════════════

class TestValorHora:
    def test_calculo_estandar_30_dias_8h(self):
        # 2400 / 30 / 8 = 10.00
        assert valor_hora(Decimal('2400')) == Decimal('10.00')

    def test_sueldo_cero_retorna_cero(self):
        assert valor_hora(Decimal('0')) == Decimal('0')

    def test_divisor_invalido_retorna_cero(self):
        assert valor_hora(Decimal('1000'), divisor_dias=0) == Decimal('0')
        assert valor_hora(Decimal('1000'), jornada_horas=0) == Decimal('0')

    def test_jornada_extendida_6h(self):
        # Para half-time: 2400 / 30 / 4 = 20
        assert valor_hora(Decimal('2400'), jornada_horas=4) == Decimal('20.00')


class TestCalcularHE:
    def test_he_25_estandar(self):
        # 2h × (2400/30/8) × 1.25 = 2 × 10 × 1.25 = 25.00
        assert calcular_he(Decimal('2'), Decimal('2400'), tipo='HE_25') == Decimal('25.00')

    def test_he_35(self):
        # 4h × 10 × 1.35 = 54.00
        assert calcular_he(Decimal('4'), Decimal('2400'), tipo='HE_35') == Decimal('54.00')

    def test_he_100_doble(self):
        # 8h × 10 × 2.00 = 160.00 (feriado/domingo)
        assert calcular_he(Decimal('8'), Decimal('2400'), tipo='HE_100') == Decimal('160.00')

    def test_he_50_convenio(self):
        assert calcular_he(Decimal('1'), Decimal('2400'), tipo='HE_50') == Decimal('15.00')

    def test_tipo_desconocido_usa_default_25(self):
        # Tipo no listado cae a factor 1.25 según implementación
        assert calcular_he(Decimal('2'), Decimal('2400'), tipo='HE_XYZ') == Decimal('25.00')

    def test_horas_cero(self):
        assert calcular_he(Decimal('0'), Decimal('2400')) == Decimal('0')

    def test_sueldo_cero(self):
        assert calcular_he(Decimal('5'), Decimal('0')) == Decimal('0')


class TestProvGratif:
    def test_calculo_basico(self):
        # (3000 + 0) / 6 = 500
        assert calcular_prov_gratif(Decimal('3000'), Decimal('0')) == Decimal('500.00')

    def test_con_asig_fam(self):
        # (3000 + 113) / 6 = 518.83 (ROUND_HALF_UP)
        assert calcular_prov_gratif(Decimal('3000'), Decimal('113')) == Decimal('518.83')

    def test_acepta_none_como_cero(self):
        assert calcular_prov_gratif(None, None) == Decimal('0.00')


class TestSubsidioIncapacidad:
    def test_solo_empleador_5_dias(self):
        r = calcular_subsidio_incapacidad(Decimal('3000'), 5)
        # 3000/30 = 100/día × 5 = 500
        assert r['dias_empleador'] == 5
        assert r['monto_empleador'] == Decimal('500.00')
        assert r['dias_essalud'] == 0
        assert r['monto_essalud_subsidio'] == Decimal('0.00')

    def test_split_empleador_y_essalud(self):
        r = calcular_subsidio_incapacidad(Decimal('3000'), 30)
        # 20 días empleador + 10 días essalud
        assert r['dias_empleador'] == 20
        assert r['dias_essalud'] == 10
        assert r['monto_empleador'] == Decimal('2000.00')
        assert r['monto_essalud_subsidio'] == Decimal('1000.00')
        assert r['total_dias'] == 30
        assert r['limite_alcanzado'] is False

    def test_limite_essalud_340_dias(self):
        # 20 (emp) + 400 (incapacidad solicitada) → 340 + flag límite
        r = calcular_subsidio_incapacidad(Decimal('3000'), 20 + 400)
        assert r['dias_essalud'] == 340
        assert r['limite_alcanzado'] is True

    def test_dias_cero_retorna_dict_vacio(self):
        r = calcular_subsidio_incapacidad(Decimal('3000'), 0)
        assert r['total_monto'] == Decimal('0')
        assert r['total_dias'] == 0

    def test_sueldo_cero(self):
        r = calcular_subsidio_incapacidad(Decimal('0'), 10)
        assert r['total_monto'] == Decimal('0')


class TestSubsidioMaternidad:
    def test_default_98_dias(self):
        r = calcular_subsidio_maternidad(Decimal('3000'))
        # 3000/30 = 100 × 98 = 9800
        assert r['dias'] == 98
        assert r['monto'] == Decimal('9800.00')

    def test_custom_dias(self):
        r = calcular_subsidio_maternidad(Decimal('3000'), dias=30)
        assert r['monto'] == Decimal('3000.00')

    def test_sueldo_cero(self):
        r = calcular_subsidio_maternidad(Decimal('0'), 98)
        assert r['monto'] == Decimal('0')


class TestPensionAlimenticia:
    def test_30_porciento_estandar(self):
        # base = 3000 - 400 = 2600 ; 30% = 780.00
        r = calcular_pension_alimenticia(Decimal('3000'), Decimal('400'), Decimal('30'))
        assert r['base_calculo'] == Decimal('2600.00')
        assert r['monto'] == Decimal('780.00')
        assert r['tope_legal_60_alcanzado'] is False

    def test_tope_60_pct_se_aplica(self):
        # Si caller pide 80%, se trunca a 60% (Art. 648 CPC)
        r = calcular_pension_alimenticia(Decimal('3000'), Decimal('0'), Decimal('80'))
        assert r['porcentaje_aplicado'] == Decimal('60')
        assert r['monto'] == Decimal('1800.00')
        assert r['tope_legal_60_alcanzado'] is True

    def test_descuentos_mayores_a_rem_base_cero(self):
        r = calcular_pension_alimenticia(Decimal('1000'), Decimal('2000'), Decimal('30'))
        assert r['base_calculo'] == Decimal('0.00')
        assert r['monto'] == Decimal('0.00')


class TestEmbargoCivil:
    def test_dentro_de_inembargable_no_aplica(self):
        # 5 URP = 5 × (10% UIT 5500) = 2750 ; rem 2500 < 2750 → exceso 0
        r = calcular_embargo_civil(Decimal('2500'), uit=Decimal('5500'))
        assert r['aplica_embargo'] is False
        assert r['monto_max_embargo'] == Decimal('0.00')

    def test_exceso_se_embarga_un_tercio(self):
        # rem 8000, inembargable 5 URP = 2750 → exceso 5250 ; 1/3 = 1750.00
        r = calcular_embargo_civil(Decimal('8000'), uit=Decimal('5500'))
        assert r['inembargable'] == Decimal('2750.00')
        assert r['exceso'] == Decimal('5250.00')
        assert r['monto_max_embargo'] == Decimal('1750.00')
        assert r['aplica_embargo'] is True


class TestBonifEscolaridad:
    def test_multiplicador_default_un_sueldo(self):
        assert calcular_bonif_escolaridad(Decimal('2500')) == Decimal('2500.00')

    def test_medio_sueldo(self):
        assert calcular_bonif_escolaridad(
            Decimal('2500'), multiplicador=Decimal('0.5')
        ) == Decimal('1250.00')

    def test_sueldo_cero(self):
        assert calcular_bonif_escolaridad(Decimal('0')) == Decimal('0')


# ════════════════════════════════════════════════════════════════════
# IR 5ta categoría — escala progresiva 2026 (UIT=5500)
# ════════════════════════════════════════════════════════════════════

class TestIR5ta:
    UIT = Decimal('5500')

    def test_exonerado_menor_a_7_uit(self):
        # rem anual 28000 (< 38500 = 7 UIT) → IR = 0
        assert calcular_ir_5ta_mensual(Decimal('28000'), uit=self.UIT) == Decimal('0')

    def test_tramo_1_primer_5_uit(self):
        # rem 42000 → base 3500 → 8% × 3500 = 280 → /12 = 23.33
        assert calcular_ir_5ta_mensual(Decimal('42000'), uit=self.UIT) == Decimal('23.33')

    def test_tramo_2_hasta_20_uit(self):
        # rem 70000 → base 31500 → 27500×0.08 + 4000×0.14 = 2200+560 = 2760 → /12 = 230.00
        assert calcular_ir_5ta_mensual(Decimal('70000'), uit=self.UIT) == Decimal('230.00')

    def test_tramo_3_hasta_35_uit(self):
        # rem 140000 → base 101500 → 27500×0.08 + 74000×0.14 = 2200+10360 = 12560 → /12 = 1046.67
        assert calcular_ir_5ta_mensual(Decimal('140000'), uit=self.UIT) == Decimal('1046.67')

    def test_tramo_4_hasta_45_uit(self):
        # rem 280000 → base 241500 → 27500×0.08 + 82500×0.14 + 82500×0.17 + 49000×0.20
        # = 2200 + 11550 + 14025 + 9800 = 37575 → /12 = 3131.25
        assert calcular_ir_5ta_mensual(Decimal('280000'), uit=self.UIT) == Decimal('3131.25')

    def test_tramo_5_sobre_45_uit_a_30(self):
        # rem 400000 → base 361500. > 45 UIT (247500)
        # 27500×0.08 + 82500×0.14 + 82500×0.17 + 55000×0.20 + (361500-247500)×0.30
        # = 2200 + 11550 + 14025 + 11000 + 34200 = 72975 → /12 = 6081.25
        assert calcular_ir_5ta_mensual(Decimal('400000'), uit=self.UIT) == Decimal('6081.25')

    def test_deduccion_eps_reduce_base(self):
        # rem 42000 con deducción EPS 3500 → base 0 → IR 0
        assert calcular_ir_5ta_mensual(
            Decimal('42000'), deduccion_eps_anual=Decimal('3500'), uit=self.UIT,
        ) == Decimal('0')

    def test_ir_anual_directo_base_cero(self):
        assert _ir_anual(Decimal('0'), self.UIT) == Decimal('0')

    def test_ir_anual_directo_base_negativa(self):
        assert _ir_anual(Decimal('-100'), self.UIT) == Decimal('0')


class TestIR5taSunat:
    UIT = Decimal('5500')

    def test_metodo_sunat_enero_proyecta_anual(self):
        # Sueldo fijo 5000, asig_fam 0, sin variables, enero (mes=1).
        # Fija anual: 5000×12 = 60000 + 2 gratif × 5000 = 70000.
        # Base = 70000 - 38500 = 31500 → impuesto 2760 / 12 meses = 230.00
        r = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('5000'),
            asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'),
            mes_actual=1,
            uit=self.UIT,
        )
        assert r == Decimal('230.00')

    def test_metodo_sunat_diciembre_ajusta_por_mes_restante(self):
        # En diciembre solo queda 1 mes. Gratif dic se proyecta.
        # 5000×12 (toda fija) + 5000 (gratif dic faltante) = 65000.
        # Base = 26500 → impuesto = 26500 × 0.08 = 2120 → /1 = 2120.00
        r = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('5000'),
            asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'),
            mes_actual=12,
            uit=self.UIT,
        )
        assert r == Decimal('2120.00')

    def test_metodo_sunat_clampea_mes_fuera_de_rango(self):
        # mes_actual=0 debería tratarse como 1 ; mes=13 como 12.
        r_zero = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('5000'), asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'), mes_actual=0, uit=self.UIT,
        )
        r_one = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('5000'), asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'), mes_actual=1, uit=self.UIT,
        )
        assert r_zero == r_one

    def test_metodo_sunat_sueldo_bajo_no_paga(self):
        # 2000 × 14 = 28000 < 7 UIT → 0
        r = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('2000'), asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'), mes_actual=1, uit=self.UIT,
        )
        assert r == Decimal('0')

    def test_metodo_sunat_uit_none_lee_config(self):
        # Cubre el branch `if uit is None: uit = _get_uit()` (línea 510).
        r = _calcular_ir_5ta_sunat(
            sueldo_fijo_mes=Decimal('2000'),
            asig_fam=Decimal('0'),
            variables_acumuladas_ano=Decimal('0'),
            mes_actual=1,
            # uit omitido → usa _get_uit()
        )
        assert r == Decimal('0')


# ════════════════════════════════════════════════════════════════════
# Calcular registro — planilla regular (DB)
# ════════════════════════════════════════════════════════════════════

def _unique_dni() -> str:
    # Delega al helper compartido (counter atómico, no timestamp). Razón:
    # int(time()*1000) % 9999999 colisiona si dos llamadas ocurren en el
    # mismo ms → UNIQUE constraint failed intermitente en suite completa.
    from nominas.tests._helpers import unique_dni
    return unique_dni()


def _crear_personal(empresa, sueldo=Decimal('3000'), regimen='ONP',
                    afp='', asig_fam=False, tiene_eps=False):
    from personal.models import Personal
    return Personal.objects.create(
        tipo_doc='DNI', nro_doc=_unique_dni(),
        apellidos_nombres='Test Engine Worker',
        cargo='Tester', tipo_trab='Empleado', categoria='NORMAL',
        estado='Activo', empresa=empresa,
        sueldo_base=sueldo,
        fecha_alta=date(2024, 1, 1),
        regimen_pension=regimen, afp=afp,
        tiene_eps=tiene_eps,
        asignacion_familiar=asig_fam,
        grupo_tareo='STAFF',
    )


def _crear_periodo(empresa, tipo='REGULAR', mes=5, anio=2026):
    from nominas.models import PeriodoNomina
    p, _ = PeriodoNomina.objects.get_or_create(
        tipo=tipo, anio=anio, mes=mes,
        defaults={
            'fecha_inicio': date(anio, mes, 1),
            'fecha_fin': date(anio, mes, 28),
            'estado': 'BORRADOR', 'empresa': empresa,
        },
    )
    return p


def _empresa_test():
    from empresas.models import Empresa
    emp, _ = Empresa.objects.get_or_create(
        ruc='20888777666',
        defaults={'razon_social': 'Test Engine SAC', 'plan': 'PROFESIONAL'},
    )
    return emp


@pytest.mark.django_db
class TestCalcularRegistroONP:
    def test_sueldo_3000_onp_sin_asig_fam_sin_he(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=5)
        p = _crear_personal(emp, sueldo=Decimal('3000'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('3000'), dias_trabajados=30,
            regimen_pension='ONP',
        )
        r = calcular_registro(reg)

        # Sueldo prop = 3000, sin asig fam → rem computable 3000
        assert r['rem_computable'] == Decimal('3000.00')
        assert r['total_ingresos'] == Decimal('3000.00')
        # ONP 13% de 3000 = 390 ; IR 5ta (42000 → 280/12 = 23.33)
        # Total descuentos = 390 + 23.33 = 413.33
        assert r['total_descuentos'] == Decimal('413.33')
        assert r['neto_a_pagar'] == Decimal('2586.67')
        # ESSALUD 9% de 3000 = 270
        assert r['aporte_essalud'] == Decimal('270.00')

    def test_sueldo_proporcional_dias_15(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=6)
        p = _crear_personal(emp, sueldo=Decimal('3000'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('3000'), dias_trabajados=15,
            regimen_pension='ONP',
        )
        r = calcular_registro(reg)
        # 3000 × 15/30 = 1500
        assert r['rem_computable'] == Decimal('1500.00')


@pytest.mark.django_db
class TestCalcularRegistroAFP:
    def test_afp_aporte_comision_seguro(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=7)
        p = _crear_personal(emp, sueldo=Decimal('3000'), regimen='AFP', afp='Prima')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('3000'), dias_trabajados=30,
            regimen_pension='AFP', afp='Prima',
        )
        r = calcular_registro(reg)

        # Prima: 10% aporte + 1.60% comisión + 1.74% seguro
        # = 300 + 48 + 52.20 = 400.20
        # IR sobre 42000 → 23.33
        # Total descuentos = 400.20 + 23.33 = 423.53
        assert r['rem_computable'] == Decimal('3000.00')
        assert r['total_descuentos'] == Decimal('423.53')
        assert r['neto_a_pagar'] == Decimal('2576.47')

    def test_afp_nombre_invalido_cae_a_prima(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=8)
        p = _crear_personal(emp, sueldo=Decimal('2000'), regimen='AFP', afp='InventadaXYZ')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2000'), dias_trabajados=30,
            regimen_pension='AFP', afp='InventadaXYZ',
        )
        r = calcular_registro(reg)
        # Cae a tasas de Prima (1.60 + 1.74). Aporte 200 + 32 + 34.80 = 266.80
        # IR 5ta: 2000×14 = 28000 < 38500 → 0
        assert r['total_descuentos'] == Decimal('266.80')

    def test_afp_tope_rma_aplica_a_seguro_no_aporte(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=9)
        # Sueldo MUY alto > tope RMA 12131.49 → prima de seguro se trunca
        p = _crear_personal(emp, sueldo=Decimal('20000'), regimen='AFP', afp='Prima')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('20000'), dias_trabajados=30,
            regimen_pension='AFP', afp='Prima',
        )
        r = calcular_registro(reg)
        # Aporte 10% sobre 20000 = 2000 (sin tope)
        # Comisión 1.60% × 20000 = 320 (sin tope)
        # Seguro 1.74% × 12131.49 = 211.09 (CON tope)
        # IR: rem_anual = 20000×14 = 280000 → 37575/12 = 3131.25
        # Total = 2000 + 320 + 211.09 + 3131.25 = 5662.34
        assert r['total_descuentos'] == Decimal('5662.34')


@pytest.mark.django_db
class TestCalcularRegistroAsignacionFamiliar:
    def test_asig_fam_se_suma_a_rem(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=10)
        p = _crear_personal(
            emp, sueldo=Decimal('2000'), regimen='ONP', asig_fam=True,
        )
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2000'), dias_trabajados=30,
            regimen_pension='ONP', asignacion_familiar=True,
        )
        r = calcular_registro(reg)
        # Rem = 2000 + 113 (10% RMV 1130) = 2113
        assert r['rem_computable'] == Decimal('2113.00')
        # ONP 13% × 2113 = 274.69
        # IR: 2113 × 14 = 29582 < 38500 → 0
        assert r['total_descuentos'] == Decimal('274.69')


@pytest.mark.django_db
class TestCalcularRegistroHorasExtra:
    def test_he_25_se_suman_a_rem(self):
        from nominas.models import RegistroNomina
        emp = _empresa_test()
        per = _crear_periodo(emp, mes=11)
        p = _crear_personal(emp, sueldo=Decimal('2400'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2400'), dias_trabajados=30,
            regimen_pension='ONP',
            horas_extra_25=Decimal('4'),  # 4h × 10 × 1.25 = 50
        )
        r = calcular_registro(reg)
        # 2400 + 50 HE25 = 2450
        assert r['rem_computable'] == Decimal('2450.00')


# ════════════════════════════════════════════════════════════════════
# Calcular gratificación
# ════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCalcularGratificacion:
    def test_semestre_completo_full(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=12,
            defaults={
                'fecha_inicio': date(2026, 7, 1), 'fecha_fin': date(2026, 12, 31),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('3000'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('3000'), dias_trabajados=6,
            regimen_pension='ONP',
        )
        r = calcular_gratificacion(reg)
        # 6/6 meses, sin asig fam, sin EPS
        assert r['gratif_bruto'] == Decimal('3000.00')
        assert r['bonif_extra'] == Decimal('270.00')          # 9%
        assert r['aporte_essalud'] == Decimal('270.00')       # 9%
        # Gratif INAFECTA → neto = bruto
        assert r['neto_a_pagar'] == Decimal('3000.00')
        assert r['total_descuentos'] == Decimal('0')
        # Costo = gratif + bonif + essalud = 3540
        assert r['costo_total_empresa'] == Decimal('3540.00')

    def test_semestre_fraccional_3_meses(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=7,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('2400'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2400'), dias_trabajados=3,
            regimen_pension='ONP',
        )
        r = calcular_gratificacion(reg)
        # 2400 × 3/6 = 1200
        assert r['gratif_bruto'] == Decimal('1200.00')
        assert r['bonif_extra'] == Decimal('108.00')           # 9% × 1200
        assert r['meses_trabajados'] == 3

    def test_meses_zero_clampea_a_uno(self):
        """Regresión: dias_trabajados=0 debe interpretarse como 1 mes mínimo,
        no caer al fallback 6 vía `or`. Bug detectado por agente D y corregido
        en engine.py:773 y :885 (commit fix: `dias_trabajados is not None`)."""
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=6,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('1200'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('1200'), dias_trabajados=0,  # debería clamp a 1
            regimen_pension='ONP',
        )
        r = calcular_gratificacion(reg)
        # Esperado: 1200 × 1/6 = 200 ; actual: 1200 (toma 6 meses).
        assert r['meses_trabajados'] == 1
        assert r['gratif_bruto'] == Decimal('200.00')

    def test_meses_mayor_que_6_clampea_a_seis(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=4,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('1500'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('1500'), dias_trabajados=99,  # → clamp 6
            regimen_pension='ONP',
        )
        r = calcular_gratificacion(reg)
        assert r['meses_trabajados'] == 6
        assert r['gratif_bruto'] == Decimal('1500.00')

    def test_con_asignacion_familiar_aumenta_base(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=3,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(
            emp, sueldo=Decimal('2000'), regimen='ONP', asig_fam=True,
        )
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2000'), dias_trabajados=6,
            regimen_pension='ONP', asignacion_familiar=True,
        )
        r = calcular_gratificacion(reg)
        # Rem base = 2000 + 113 = 2113
        assert r['rem_computable'] == Decimal('2113.00')
        assert r['gratif_bruto'] == Decimal('2113.00')


# ════════════════════════════════════════════════════════════════════
# Calcular CTS
# ════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestCalcularCTS:
    def test_semestre_completo(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='CTS', anio=2026, mes=5,
            defaults={
                'fecha_inicio': date(2025, 11, 1), 'fecha_fin': date(2026, 4, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('2400'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2400'), dias_trabajados=6,
            regimen_pension='ONP',
        )
        r = calcular_cts(reg)
        # base = 2400 + 0 + 2400/6 (prov gratif) = 2400 + 400 = 2800
        # CTS = 2800 / 12 × 6 = 1400.00
        assert r['cts_semestral'] == Decimal('1400.00')
        assert r['base_cts'] == Decimal('2800.00')
        assert r['prov_gratif_mes'] == Decimal('400.00')
        # No tiene descuentos
        assert r['total_descuentos'] == Decimal('0')
        assert r['neto_a_pagar'] == Decimal('1400.00')

    def test_cts_fraccional_3_meses(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='CTS', anio=2026, mes=11,
            defaults={
                'fecha_inicio': date(2026, 5, 1), 'fecha_fin': date(2026, 10, 31),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(emp, sueldo=Decimal('3000'), regimen='ONP')
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('3000'), dias_trabajados=3,
            regimen_pension='ONP',
        )
        r = calcular_cts(reg)
        # base = 3000 + 500 = 3500 ; CTS = 3500/12 × 3 = 875.00
        assert r['cts_semestral'] == Decimal('875.00')
        assert r['meses_trabajados'] == 3

    def test_cts_con_asignacion_familiar(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='CTS', anio=2026, mes=8,
            defaults={
                'fecha_inicio': date(2026, 2, 1), 'fecha_fin': date(2026, 7, 31),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        p = _crear_personal(
            emp, sueldo=Decimal('2000'), regimen='ONP', asig_fam=True,
        )
        reg = RegistroNomina.objects.create(
            periodo=per, personal=p,
            sueldo_base=Decimal('2000'), dias_trabajados=6,
            regimen_pension='ONP', asignacion_familiar=True,
        )
        r = calcular_cts(reg)
        # base = 2000 + 113 + (2113/6) = 2113 + 352.1666... = 2465.166...
        # CTS = base / 12 × 6 = base / 2 = 1232.58
        assert r['cts_semestral'] == Decimal('1232.58')


# ════════════════════════════════════════════════════════════════════
# generar_periodo — end-to-end
# ════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestGenerarPeriodo:
    def test_genera_registros_para_2_trabajadores_regular(self):
        from nominas.models import PeriodoNomina, RegistroNomina
        emp = _empresa_test()
        # 2 trabajadores activos
        _crear_personal(emp, sueldo=Decimal('2000'), regimen='ONP')
        _crear_personal(emp, sueldo=Decimal('3000'), regimen='AFP', afp='Prima')

        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='REGULAR', anio=2026, mes=2,
            defaults={
                'fecha_inicio': date(2026, 2, 1), 'fecha_fin': date(2026, 2, 28),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )

        stats = generar_periodo(per)

        # Al menos 2 (puede haber otros creados en tests previos del mismo run en empresa demo)
        assert stats['generados'] >= 2
        assert stats['errores'] == 0
        # Total neto debe ser > 0
        assert stats['total_neto'] > Decimal('0')

        # Refrescar período y verificar totales
        per.refresh_from_db()
        assert per.estado == 'CALCULADO'
        assert per.total_trabajadores >= 2
        assert per.total_neto == stats['total_neto']
        # Registros existen
        assert per.registros.count() >= 2
        # Cada registro está en CALCULADO
        for reg in per.registros.all():
            assert reg.estado == 'CALCULADO'
            assert reg.neto_a_pagar > Decimal('0')

    def test_periodo_gratificacion_usa_calculadora_correcta(self):
        from nominas.models import PeriodoNomina
        emp = _empresa_test()
        _crear_personal(emp, sueldo=Decimal('1800'), regimen='ONP')

        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=2,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        stats = generar_periodo(per)
        assert stats['errores'] == 0
        assert stats['generados'] >= 1
        per.refresh_from_db()
        assert per.estado == 'CALCULADO'

    def test_periodo_cts_usa_calculadora_correcta(self):
        from nominas.models import PeriodoNomina
        emp = _empresa_test()
        _crear_personal(emp, sueldo=Decimal('2100'), regimen='ONP')

        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='CTS', anio=2026, mes=1,
            defaults={
                'fecha_inicio': date(2025, 7, 1), 'fecha_fin': date(2025, 12, 31),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        stats = generar_periodo(per)
        assert stats['errores'] == 0
        per.refresh_from_db()
        assert per.estado == 'CALCULADO'
        # CTS = no tiene descuentos
        assert per.total_descuentos == Decimal('0')

    def test_genera_idempotente_segundo_llamado_actualiza(self):
        from nominas.models import PeriodoNomina
        emp = _empresa_test()
        _crear_personal(emp, sueldo=Decimal('1500'), regimen='ONP')

        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='REGULAR', anio=2026, mes=3,
            defaults={
                'fecha_inicio': date(2026, 3, 1), 'fecha_fin': date(2026, 3, 31),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        stats1 = generar_periodo(per)
        n_generados = stats1['generados']
        stats2 = generar_periodo(per)
        # Segunda corrida: ya existen → todos 'actualizados', 0 generados
        assert stats2['generados'] == 0
        assert stats2['actualizados'] >= n_generados

    def test_filtro_grupo_solo_procesa_personal_del_grupo(self):
        from nominas.models import PeriodoNomina
        emp = _empresa_test()
        # Trabajador en grupo OBRA
        from personal.models import Personal
        Personal.objects.create(
            tipo_doc='DNI', nro_doc=_unique_dni(),
            apellidos_nombres='Obra Worker',
            cargo='Obrero', tipo_trab='Obrero', categoria='NORMAL',
            estado='Activo', empresa=emp,
            sueldo_base=Decimal('1500'),
            fecha_alta=date(2024, 1, 1),
            regimen_pension='ONP', grupo_tareo='OBRA',
        )
        per, _ = PeriodoNomina.objects.get_or_create(
            tipo='REGULAR', anio=2026, mes=4,
            defaults={
                'fecha_inicio': date(2026, 4, 1), 'fecha_fin': date(2026, 4, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        stats = generar_periodo(per, grupo='OBRA')
        assert stats['errores'] == 0
        # Solo procesa los OBRA — debe haber al menos 1
        assert stats['generados'] + stats['actualizados'] >= 1


@pytest.mark.django_db
class TestHENoCompensadasBanco:
    """valor_he_banco_no_compensadas: deuda de HE banqueadas no compensadas al cese."""

    def test_valoriza_saldo_no_compensado_proporcional(self):
        from nominas.engine import valor_he_banco_no_compensadas
        from asistencia.models import BancoHoras
        emp = _empresa_test()
        p = _crear_personal(emp, sueldo=Decimal('3000'))
        BancoHoras.objects.create(
            personal=p, periodo_anio=2026, periodo_mes=2,
            he_25_acumuladas=Decimal('10'), he_35_acumuladas=Decimal('4'),
            he_100_acumuladas=Decimal('0'), he_compensadas=Decimal('4'),
            saldo_horas=Decimal('10'),
        )
        # total_acum=14, saldo=10, ratio=10/14, vh=3000/30/8=12.5
        # ratio*12.5*(10*1.25 + 4*1.35) = (10/14)*12.5*17.9 = 159.82
        r = valor_he_banco_no_compensadas(p, Decimal('3000'))
        assert r == Decimal('159.82')

    def test_sin_banco_es_cero(self):
        from nominas.engine import valor_he_banco_no_compensadas
        emp = _empresa_test()
        p = _crear_personal(emp, sueldo=Decimal('3000'))
        assert valor_he_banco_no_compensadas(p, Decimal('3000')) == Decimal('0')

    def test_saldo_totalmente_compensado_es_cero(self):
        from nominas.engine import valor_he_banco_no_compensadas
        from asistencia.models import BancoHoras
        emp = _empresa_test()
        p = _crear_personal(emp, sueldo=Decimal('3000'))
        BancoHoras.objects.create(
            personal=p, periodo_anio=2026, periodo_mes=2,
            he_25_acumuladas=Decimal('8'), he_compensadas=Decimal('8'),
            saldo_horas=Decimal('0'),
        )
        assert valor_he_banco_no_compensadas(p, Decimal('3000')) == Decimal('0')
