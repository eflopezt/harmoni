"""
Tests E2E para todos los features de la jornada extendida:
- Calculadora simulador + pública + comparar + AFP + PDF
- Workflow del mes
- Detector duplicados
- Health endpoint
- Detector anomalías
- Reporte ejecutivo PDF
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from nominas.models import ConceptoRemunerativo


User = get_user_model()


class CalculadoraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calc_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_calculadora_get(self):
        resp = self.client.get('/nominas/calculadora/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Calculadora de Planilla')

    def test_calculadora_post_basico(self):
        resp = self.client.post('/nominas/calculadora/', {
            'sueldo': '3000', 'regimen': 'ONP',
        })
        self.assertEqual(resp.status_code, 200)
        result = resp.context['result']
        self.assertIsNotNone(result)
        self.assertNotIn('error', result)
        # 3000 con ONP 13% → descuento ONP debería ser cerca de 390
        self.assertIn('onp', result['descuentos'])

    def test_calculadora_eps_baja_essalud(self):
        """Con EPS, ESSALUD debe ser 6.75% en vez de 9%."""
        resp = self.client.post('/nominas/calculadora/', {
            'sueldo': '3000', 'regimen': 'ONP', 'tiene_eps': 'on',
        })
        result = resp.context['result']
        essalud_label = result['aportes_empleador']['essalud']['label']
        self.assertIn('6.75', essalud_label)

    def test_calculadora_comparar_dos_escenarios(self):
        resp = self.client.post('/nominas/calculadora/comparar/', {
            'sueldo_a': '2500', 'sueldo_b': '3000', 'regimen': 'ONP',
        })
        self.assertEqual(resp.status_code, 200)
        delta = resp.context['delta']
        self.assertIsNotNone(delta)
        # Sueldo subió 500 → delta positivo
        self.assertGreater(delta['sueldo'], 0)
        self.assertGreater(delta['neto'], 0)

    def test_calculadora_afp_compara_5_opciones(self):
        """AFP recomendador debe devolver ONP + 4 AFPs."""
        resp = self.client.post('/nominas/calculadora/afp/', {
            'sueldo': '3000',
        })
        self.assertEqual(resp.status_code, 200)
        ranking = resp.context['ranking']
        self.assertEqual(len(ranking), 5)  # ONP + Habitat + Integra + Prima + Profuturo
        # El primero debe tener mayor neto
        self.assertEqual(ranking[0]['rank'], 1)
        self.assertGreaterEqual(ranking[0]['neto'], ranking[-1]['neto'])

    def test_calculadora_publica_sin_login(self):
        """Accesible sin autenticación."""
        self.client.logout()
        resp = self.client.get('/calculadora/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Calculadora de Planilla')

    def test_calculadora_api_json_post(self):
        """POST con body JSON devuelve simulación JSON."""
        import json
        self.client.logout()  # API es CSRF-exempt y sin auth
        resp = self.client.post(
            '/api/calculadora/',
            data=json.dumps({'sueldo': '3000', 'regimen': 'ONP'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('neto', data)
        self.assertIn('costo_full_loaded', data)


class WorkflowMesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wf_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_workflow_mes_render(self):
        resp = self.client.get('/nominas/workflow-mes/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Workflow del Mes')
        # Debe haber 11 steps (era 10 antes — commit ada889c añadió AFPNet
        # step #9 entre PLAME y Asiento Contable, renumerando los siguientes).
        self.assertEqual(len(resp.context['steps']), 11)
        # Progreso siempre entre 0 y 100
        self.assertGreaterEqual(resp.context['progreso_pct'], 0)
        self.assertLessEqual(resp.context['progreso_pct'], 100)


class DetectorDuplicadosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dup_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)
        # Crear concepto base
        ConceptoRemunerativo.objects.create(
            codigo='sueldo_basico', nombre='Sueldo Básico', tipo='INGRESO',
        )

    def test_detector_funciona_exacto(self):
        from nominas.views_conceptos import detectar_similares
        sims = detectar_similares('sueldo_basico', 'Otro nombre')
        # Match exacto en codigo
        self.assertTrue(any(s['confianza'] == 'EXACTO' for s in sims))

    def test_detector_bloquea_creacion_duplicada(self):
        """POST sin ignorar_similares con código existente debería redirigir al form con warning."""
        resp = self.client.post('/nominas/conceptos/configurar/nuevo/', {
            'codigo': 'sueldo_basico',
            'nombre': 'Sueldo Básico',
            'tipo': 'INGRESO',
            'subtipo': 'REMUNERATIVO',
            'formula': 'FIJO',
            'categoria': 'SUELDO',
        })
        # Debe re-renderizar el form (no redirigir a lista)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'similares')

    def test_detector_se_puede_ignorar(self):
        """Con ignorar_similares=1, sí se permite crear."""
        # Crear con código distinto pero nombre parecido
        resp = self.client.post('/nominas/conceptos/configurar/nuevo/', {
            'codigo': 'sueldo_extra_v2',
            'nombre': 'Sueldo Extra',
            'tipo': 'INGRESO',
            'subtipo': 'REMUNERATIVO',
            'formula': 'FIJO',
            'categoria': 'SUELDO',
            'ignorar_similares': '1',
        })
        # Si llegó al save y se creó, redirige
        self.assertIn(resp.status_code, [200, 302])
        # Verificar que se creó
        self.assertTrue(ConceptoRemunerativo.objects.filter(codigo='sueldo_extra_v2').exists())


class HealthEndpointTests(TestCase):
    def test_health_publico_sin_auth(self):
        """No requiere auth."""
        resp = self.client.get('/api/health/nominas/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('status', data)
        self.assertIn('service', data)
        self.assertEqual(data['service'], 'harmoni-nominas')

    def test_health_devuelve_score(self):
        resp = self.client.get('/api/health/nominas/')
        data = resp.json()
        # onboarding_score puede ser None si no hay empresa, pero la key debe existir
        self.assertIn('onboarding_score', data)
        self.assertIn('conceptos', data)


class AnomaliasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='anom_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_anomalias_pct_cambio_helper(self):
        from nominas.views_anomalias import _pct_cambio
        # 100 → 130 = +30%
        self.assertEqual(_pct_cambio(Decimal('100'), Decimal('130')), Decimal('30'))
        # 100 → 50 = -50%
        self.assertEqual(_pct_cambio(Decimal('100'), Decimal('50')), Decimal('-50'))
        # 0 → 50 = 100% (defensiva)
        self.assertEqual(_pct_cambio(Decimal('0'), Decimal('50')), Decimal('100'))
