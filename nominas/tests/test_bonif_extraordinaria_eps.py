"""
Tests críticos: bonificación extraordinaria 9% vs 6.75% según EPS.

Verifica que el engine de gratificaciones aplica correctamente:
- 9.00% si trabajador NO tiene EPS (ESSALUD regular)
- 6.75% si trabajador SÍ tiene EPS (Ley 26790 art. 15)

Y simétricamente:
- ESSALUD efectivo del empleador = 6.75% si trabajador con EPS
"""
from decimal import Decimal

import pytest


@pytest.mark.django_db
class TestBonifExtraordinariaEPS:

    def _crear_registro(self, tiene_eps=False, sueldo=Decimal('3000')):
        from empresas.models import Empresa
        from personal.models import Personal
        from nominas.models import PeriodoNomina, RegistroNomina
        from datetime import date

        emp, _ = Empresa.objects.get_or_create(
            ruc='20999111222', defaults={'razon_social': 'Test Bonif EPS SAC', 'plan': 'PROFESIONAL'},
        )
        # DNI único por test (timestamp para evitar colisiones)
        from time import time
        dni = f'8{int(time()*1000) % 9999999:07d}'
        p = Personal.objects.create(
            tipo_doc='DNI', nro_doc=dni,
            apellidos_nombres=f'Test Worker {"EPS" if tiene_eps else "No-EPS"}',
            cargo='Tester',
            tipo_trab='EMPLEADO', categoria='EMPLEADO',
            estado='Activo', empresa=emp,
            sueldo_base=sueldo,
            fecha_alta=date(2024, 1, 1),
            regimen_pension='ONP',
            tiene_eps=tiene_eps,
            asignacion_familiar=False,
        )
        # Use get_or_create + unique mes per worker dni-hash to avoid UNIQUE conflict
        # when same test creates multiple registros
        mes_unique = 7 + (int(dni) % 5)  # 7-11
        periodo, _ = PeriodoNomina.objects.get_or_create(
            tipo='GRATIFICACION', anio=2026, mes=mes_unique,
            defaults={
                'fecha_inicio': date(2026, 1, 1), 'fecha_fin': date(2026, 6, 30),
                'estado': 'BORRADOR', 'empresa': emp,
            },
        )
        # 6 meses completos
        registro = RegistroNomina.objects.create(
            periodo=periodo, personal=p,
            sueldo_base=sueldo, dias_trabajados=6,
            regimen_pension='ONP', afp='',
        )
        return registro, p

    def test_sin_eps_aplica_9_porciento(self):
        from nominas.engine import calcular_gratificacion

        registro, _ = self._crear_registro(tiene_eps=False, sueldo=Decimal('3000'))
        result = calcular_gratificacion(registro)

        # Gratif = sueldo completo (6/6 meses) = 3000
        assert result['gratif_bruto'] == Decimal('3000.00')
        # Bonif extra = 9% de 3000 = 270
        assert result['bonif_extra'] == Decimal('270.00'), \
            f'Sin EPS debe ser 9% = 270, got {result["bonif_extra"]}'

    def test_con_eps_aplica_6_75_porciento(self):
        from nominas.engine import calcular_gratificacion

        registro, _ = self._crear_registro(tiene_eps=True, sueldo=Decimal('3000'))
        result = calcular_gratificacion(registro)

        assert result['gratif_bruto'] == Decimal('3000.00')
        # Bonif extra = 6.75% de 3000 = 202.50
        assert result['bonif_extra'] == Decimal('202.50'), \
            f'Con EPS debe ser 6.75% = 202.50, got {result["bonif_extra"]}'

    def test_essalud_efectivo_baja_con_eps(self):
        """Cuando trabajador tiene EPS, ESSALUD efectivo es 6.75% (no 9%)."""
        from nominas.engine import calcular_gratificacion

        # Sin EPS: ESSALUD 9% de 3000 = 270
        registro_sin, _ = self._crear_registro(tiene_eps=False, sueldo=Decimal('3000'))
        result_sin = calcular_gratificacion(registro_sin)
        assert result_sin['aporte_essalud'] == Decimal('270.00')

        # Con EPS: ESSALUD efectivo 6.75% de 3000 = 202.50
        registro_con, _ = self._crear_registro(tiene_eps=True, sueldo=Decimal('3000'))
        result_con = calcular_gratificacion(registro_con)
        assert result_con['aporte_essalud'] == Decimal('202.50'), \
            f'Con EPS, ESSALUD debe ser 6.75% = 202.50, got {result_con["aporte_essalud"]}'

    def test_diferencia_es_2_25_porciento(self):
        """La diferencia entre 9% y 6.75% es 2.25%, que es lo que va a EPS particular."""
        from nominas.engine import calcular_gratificacion

        registro_sin, _ = self._crear_registro(tiene_eps=False, sueldo=Decimal('4000'))
        registro_con, _ = self._crear_registro(tiene_eps=True, sueldo=Decimal('4000'))

        r_sin = calcular_gratificacion(registro_sin)
        r_con = calcular_gratificacion(registro_con)

        # Diferencia bonif extra
        diff_bonif = r_sin['bonif_extra'] - r_con['bonif_extra']
        # 9% - 6.75% = 2.25% sobre 4000 = 90
        assert diff_bonif == Decimal('90.00'), \
            f'Diferencia bonif debe ser 2.25% = 90, got {diff_bonif}'

        # Diferencia ESSALUD
        diff_essalud = r_sin['aporte_essalud'] - r_con['aporte_essalud']
        assert diff_essalud == Decimal('90.00'), \
            f'Diferencia ESSALUD debe ser 2.25% = 90, got {diff_essalud}'
