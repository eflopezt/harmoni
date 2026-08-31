from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from empresas.models import Empresa
from nominas.context_processors import _calcular_alertas
from nominas.models import ConceptoRemunerativo, PeriodoNomina, RegistroNomina
from personal.models import Personal


User = get_user_model()


class NominasAlertsContextTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='alertas_admin',
            password='admin',
            is_superuser=True,
        )

    def tearDown(self):
        cache.clear()

    def _empresa(self):
        return Empresa.objects.create(
            ruc='20990011001',
            razon_social='Empresa Alertas SAC',
            activa=True,
            es_principal=True,
        )

    def _without_onboarding_noise(self):
        return patch(
            'nominas.views_onboarding_validator.build_onboarding_report',
            return_value={'score': 100, 'n_error': 0, 'n_warn': 0},
        )

    def test_cuenta_acuses_pendientes_desde_documentos(self):
        empresa = self._empresa()
        trabajador = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc='49991122',
            apellidos_nombres='ALERTAS CONTEXTO, ANA',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa,
            sueldo_base=Decimal('2500.00'),
            fecha_alta=date(2026, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        periodo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
            empresa=empresa,
        )
        RegistroNomina.objects.create(periodo=periodo, personal=trabajador)

        with self._without_onboarding_noise():
            alertas = _calcular_alertas(empresa)

        self.assertEqual(alertas['acuses_pendientes'], 1)
        self.assertEqual(alertas['count'], 1)
        self.assertEqual(alertas['severidad'], 'warn')

    def test_conceptos_sin_plame_activan_banner_con_diagnostico(self):
        for idx in range(6):
            ConceptoRemunerativo.objects.create(
                codigo=f'sin_plame_{idx}',
                nombre=f'Sin PLAME {idx}',
                tipo='INGRESO',
                codigo_plame='',
                activo=True,
            )

        with self._without_onboarding_noise():
            alertas = _calcular_alertas()

        self.assertEqual(alertas['sin_plame'], 6)
        self.assertGreater(alertas['count'], 0)
        self.assertEqual(alertas['severidad'], 'warn')

    def test_banner_muestra_motivo_de_alerta_sin_plame(self):
        self.client.force_login(self.user)
        for idx in range(6):
            ConceptoRemunerativo.objects.create(
                codigo=f'banner_sin_plame_{idx}',
                nombre=f'Banner Sin PLAME {idx}',
                tipo='INGRESO',
                codigo_plame='',
                activo=True,
            )

        with self._without_onboarding_noise():
            resp = self.client.get('/nominas/mi-dia/')

        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Atención de nóminas')
        self.assertContains(resp, 'conceptos sin código PLAME')
        self.assertContains(resp, 'completar')
