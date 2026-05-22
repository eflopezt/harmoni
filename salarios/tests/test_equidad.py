"""
Tests del motor de equidad salarial (salarios.analisis_equidad).
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from personal.models import Area, Personal, SubArea
from salarios.analisis_equidad import (
    analizar_equidad_salarial,
    simular_ajuste_outliers,
)
from salarios.models import BandaSalarial

User = get_user_model()


# ──────────────────────────────────────────────────────────────────
# Mixin de fixtures
# ──────────────────────────────────────────────────────────────────
class EquidadFixturesMixin:

    def _crear_area(self, nombre='Salón'):
        area, _ = Area.objects.get_or_create(nombre=nombre)
        subarea, _ = SubArea.objects.get_or_create(
            nombre=f'{nombre}-A', area=area
        )
        return area, subarea

    def _crear_personal(self, **kwargs):
        defaults = {
            'nro_doc': '00000001',
            'apellidos_nombres': 'Test, Empleado',
            'cargo': 'Mesero Junior',
            'tipo_trab': 'Empleado',
            'estado': 'Activo',
            'sexo': 'M',
            'sueldo_base': Decimal('1200.00'),
            'grupo_tareo': 'STAFF',
        }
        defaults.update(kwargs)
        return Personal.objects.create(**defaults)

    def _crear_banda(self, cargo='Mesero Junior', minimo=1100, medio=1250, maximo=1400,
                     nivel='JUNIOR', activa=True):
        return BandaSalarial.objects.create(
            cargo=cargo,
            nivel=nivel,
            minimo=Decimal(str(minimo)),
            medio=Decimal(str(medio)),
            maximo=Decimal(str(maximo)),
            moneda='PEN',
            activa=activa,
        )


# ──────────────────────────────────────────────────────────────────
# Motor — invocación con BD vacía
# ──────────────────────────────────────────────────────────────────
class MotorEquidadEmptyTest(EquidadFixturesMixin, TestCase):

    def test_runs_with_empty_db(self):
        """No debe fallar si no hay personal ni bandas."""
        result = analizar_equidad_salarial()
        assert isinstance(result, dict)
        assert result['stats_generales']['n'] == 0
        assert result['stats_generales']['total_planilla'] == 0.0
        assert result['gap_genero']['gap_pct'] is None
        assert result['outliers_alto'] == []
        assert result['outliers_bajo'] == []
        assert result['sin_banda'] == []
        assert result['por_area'] == []

    def test_runs_with_personal_but_no_bandas(self):
        """Personal sin bandas → todos en sin_banda."""
        self._crear_personal(
            nro_doc='10000001', sueldo_base=Decimal('1500.00'),
        )
        self._crear_personal(
            nro_doc='10000002', sueldo_base=Decimal('2000.00'),
            sexo='F',
        )
        result = analizar_equidad_salarial()
        assert result['stats_generales']['n'] == 2
        assert len(result['sin_banda']) == 2


# ──────────────────────────────────────────────────────────────────
# Motor — Gap de género
# ──────────────────────────────────────────────────────────────────
class GapGeneroTest(EquidadFixturesMixin, TestCase):

    def test_gap_genero_positivo(self):
        """Si los hombres ganan más, gap > 0."""
        # 2 hombres ganando 2000
        self._crear_personal(nro_doc='20000001', sexo='M',
                             sueldo_base=Decimal('2000'))
        self._crear_personal(nro_doc='20000002', sexo='M',
                             sueldo_base=Decimal('2000'))
        # 2 mujeres ganando 1500
        self._crear_personal(nro_doc='20000003', sexo='F',
                             sueldo_base=Decimal('1500'))
        self._crear_personal(nro_doc='20000004', sexo='F',
                             sueldo_base=Decimal('1500'))

        result = analizar_equidad_salarial()
        gap = result['gap_genero']
        assert gap['M'] == 2000.0
        assert gap['F'] == 1500.0
        # (2000 - 1500) / 2000 * 100 = 25.0
        assert gap['gap_pct'] == 25.0
        assert gap['n_m'] == 2
        assert gap['n_f'] == 2

    def test_gap_genero_sin_mujeres(self):
        """Solo hombres → gap_pct = None."""
        self._crear_personal(nro_doc='30000001', sexo='M',
                             sueldo_base=Decimal('2000'))
        result = analizar_equidad_salarial()
        assert result['gap_genero']['gap_pct'] is None
        assert result['gap_genero']['n_f'] == 0

    def test_gap_genero_equitativo(self):
        """Sueldos iguales → gap_pct = 0."""
        self._crear_personal(nro_doc='40000001', sexo='M',
                             sueldo_base=Decimal('2000'))
        self._crear_personal(nro_doc='40000002', sexo='F',
                             sueldo_base=Decimal('2000'))
        result = analizar_equidad_salarial()
        assert result['gap_genero']['gap_pct'] == 0.0


# ──────────────────────────────────────────────────────────────────
# Motor — Outliers
# ──────────────────────────────────────────────────────────────────
class OutliersTest(EquidadFixturesMixin, TestCase):

    def test_outlier_alto(self):
        """Empleado con sueldo > banda.maximo → outlier_alto."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='50000001', cargo='Cocinero',
            sueldo_base=Decimal('3000.00'),
        )
        result = analizar_equidad_salarial()
        assert len(result['outliers_alto']) == 1
        assert len(result['outliers_bajo']) == 0
        # 3000 - 2200 = 800
        assert result['outliers_alto'][0]['exceso'] == Decimal('800.00')

    def test_outlier_bajo(self):
        """Empleado con sueldo < banda.minimo → outlier_bajo."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='60000001', cargo='Cocinero',
            sueldo_base=Decimal('1200.00'),
        )
        result = analizar_equidad_salarial()
        assert len(result['outliers_alto']) == 0
        assert len(result['outliers_bajo']) == 1
        # 1500 - 1200 = 300
        assert result['outliers_bajo'][0]['deficit'] == Decimal('300.00')

    def test_en_banda_no_es_outlier(self):
        """Empleado dentro del rango → no es outlier."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='70000001', cargo='Cocinero',
            sueldo_base=Decimal('1800.00'),
        )
        result = analizar_equidad_salarial()
        assert len(result['outliers_alto']) == 0
        assert len(result['outliers_bajo']) == 0
        assert len(result['sin_banda']) == 0

    def test_sin_banda(self):
        """Cargo sin banda definida → personal va a sin_banda."""
        self._crear_banda(cargo='Mesero', minimo=1100, medio=1250, maximo=1400)
        # Crear empleado con cargo distinto a la única banda existente
        self._crear_personal(
            nro_doc='80000001', cargo='Sommelier',
            sueldo_base=Decimal('2500.00'),
        )
        result = analizar_equidad_salarial()
        assert len(result['sin_banda']) == 1
        assert result['sin_banda'][0]['cargo'] == 'Sommelier'

    def test_outliers_ordenados_por_desviacion(self):
        """Outliers se ordenan por mayor desviación primero."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='90000001', cargo='Cocinero',
            apellidos_nombres='A',
            sueldo_base=Decimal('1400.00'),  # déficit 100
        )
        self._crear_personal(
            nro_doc='90000002', cargo='Cocinero',
            apellidos_nombres='B',
            sueldo_base=Decimal('1100.00'),  # déficit 400
        )
        result = analizar_equidad_salarial()
        # B (déficit 400) debe ir primero
        assert result['outliers_bajo'][0]['personal'].apellidos_nombres == 'B'
        assert result['outliers_bajo'][1]['personal'].apellidos_nombres == 'A'


# ──────────────────────────────────────────────────────────────────
# Motor — Distribución por percentiles
# ──────────────────────────────────────────────────────────────────
class DistribucionPercentilesTest(EquidadFixturesMixin, TestCase):

    def test_distribucion_basica(self):
        """Verifica los conteos de percentiles."""
        sueldos = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500]
        for i, s in enumerate(sueldos):
            self._crear_personal(
                nro_doc=f'9100000{i}', cargo=f'Cargo_{i}',
                apellidos_nombres=f'Emp {i}',
                sueldo_base=Decimal(str(s)),
            )
        result = analizar_equidad_salarial()
        dist = result['distribucion_bandas']
        total = (dist['p25_below'] + dist['p25_p50']
                 + dist['p50_p75'] + dist['p75_above'])
        assert total == 8
        # Stats
        assert result['stats_generales']['n'] == 8
        assert result['stats_generales']['total_planilla'] == 22000.0


# ──────────────────────────────────────────────────────────────────
# Vista — equidad responde 200
# ──────────────────────────────────────────────────────────────────
class VistaEquidadTest(EquidadFixturesMixin, TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_eq', password='pwd', is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_vista_equidad_200(self):
        url = reverse('equidad_salarial')
        resp = self.client.get(url)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────
# Simulador de ajuste
# ──────────────────────────────────────────────────────────────────
class SimuladorAjusteTest(EquidadFixturesMixin, TestCase):

    def test_simular_ajuste_mediana(self):
        """El ajuste a mediana sube los outliers bajos al midpoint."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        # 2 empleados subpagados
        self._crear_personal(
            nro_doc='99000001', cargo='Cocinero',
            apellidos_nombres='Sub1',
            sueldo_base=Decimal('1200.00'),
        )
        self._crear_personal(
            nro_doc='99000002', cargo='Cocinero',
            apellidos_nombres='Sub2',
            sueldo_base=Decimal('1300.00'),
        )

        sim = simular_ajuste_outliers(objetivo='mediana')

        assert sim['objetivo'] == 'mediana'
        assert len(sim['propuestas']) == 2
        # Ambos deben ir a 1800 (medio)
        for p in sim['propuestas']:
            assert p['sueldo_nuevo'] == Decimal('1800.00')
        # incremento total mensual = (1800-1200) + (1800-1300) = 600 + 500 = 1100
        assert sim['impacto']['incremento_mensual_total'] == Decimal('1100.00')
        # anual = 1100 * 12 = 13200
        assert sim['impacto']['incremento_anual_total'] == Decimal('13200.00')
        assert sim['impacto']['n_afectados'] == 2

    def test_simular_ajuste_minimo(self):
        """Ajuste al mínimo de banda."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='99100001', cargo='Cocinero',
            sueldo_base=Decimal('1200.00'),
        )
        sim = simular_ajuste_outliers(objetivo='minimo')
        assert sim['propuestas'][0]['sueldo_nuevo'] == Decimal('1500.00')
        assert sim['impacto']['incremento_mensual_total'] == Decimal('300.00')

    def test_simular_sin_outliers(self):
        """Sin outliers → ningún ajuste."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='99200001', cargo='Cocinero',
            sueldo_base=Decimal('1800.00'),
        )
        sim = simular_ajuste_outliers(objetivo='mediana')
        assert sim['propuestas'] == []
        assert sim['impacto']['n_afectados'] == 0
        assert sim['impacto']['incremento_mensual_total'] == Decimal('0')

    def test_pct_planilla_calcula(self):
        """El % sobre planilla se calcula correctamente."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        # 2 outliers bajos (subirán de 1200 a 1800 = +600 c/u)
        self._crear_personal(
            nro_doc='99300001', cargo='Cocinero',
            sueldo_base=Decimal('1200.00'),
        )
        self._crear_personal(
            nro_doc='99300002', cargo='Cocinero',
            sueldo_base=Decimal('1200.00'),
        )
        # planilla actual = 2400, incremento total = 1200, pct = 50%
        sim = simular_ajuste_outliers(objetivo='mediana')
        assert sim['impacto']['planilla_actual'] == Decimal('2400.00')
        assert sim['impacto']['incremento_mensual_total'] == Decimal('1200.00')
        assert sim['impacto']['incremento_pct_planilla'] == Decimal('50.00')


# ──────────────────────────────────────────────────────────────────
# Vista — simulador de ajuste
# ──────────────────────────────────────────────────────────────────
class VistaSimuladorAjusteTest(EquidadFixturesMixin, TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_sim', password='pwd', is_superuser=True,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_vista_simular_ajuste_200(self):
        """La vista del simulador responde 200 sin datos."""
        url = reverse('simular_ajuste_equidad')
        resp = self.client.get(url)
        assert resp.status_code == 200

    def test_vista_simular_ajuste_con_datos(self):
        """Con outliers, la vista muestra propuestas."""
        self._crear_banda(cargo='Cocinero', minimo=1500, medio=1800, maximo=2200)
        self._crear_personal(
            nro_doc='99400001', cargo='Cocinero',
            sueldo_base=Decimal('1200.00'),
        )
        url = reverse('simular_ajuste_equidad')
        resp = self.client.get(url + '?objetivo=mediana')
        assert resp.status_code == 200
        # Debe contener al menos una propuesta
        content = resp.content.decode('utf-8')
        assert 'Cocinero' in content or '1200' in content or '1800' in content
