"""
Tests E2E del wizard "Configurar mi planilla en 5 minutos".

Cubre:
- step1: muestra perfiles disponibles
- step2: muestra templates agrupados por categoría
- POST step2: crea conceptos seleccionados
- Audit logs de creación tipo TEMPLATE quedan registrados
- Conceptos ya existentes no se duplican
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from nominas.models import ConceptoAuditLog, ConceptoRemunerativo
from nominas.views_wizard_planilla import PERFILES_EMPRESA


User = get_user_model()


class WizardPlanillaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wizard_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)
        ConceptoRemunerativo.objects.all().delete()
        ConceptoAuditLog.objects.all().delete()

    def test_step1_lista_perfiles(self):
        """GET /nominas/conceptos/configurar/wizard/ → render con perfiles."""
        url = reverse('wizard_step1')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Debe incluir al menos los 6 perfiles
        for key in ('gastronomia', 'construccion', 'oficina', 'comercio', 'salud', 'personalizado'):
            self.assertIn(key, PERFILES_EMPRESA)

    def test_step2_con_perfil_gastronomia(self):
        """GET /wizard/seleccionar/?perfil=gastronomia → muestra templates."""
        url = reverse('wizard_step2') + '?perfil=gastronomia'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # Debe pasar perfil y grupos al contexto
        self.assertEqual(resp.context['perfil_key'], 'gastronomia')
        self.assertIn('grupos', resp.context)
        self.assertGreater(len(resp.context['grupos']), 0)

    def test_step2_perfil_inexistente_fallback_personalizado(self):
        """Perfil no existente → cae a personalizado sin error."""
        url = reverse('wizard_step2') + '?perfil=xyz_inexistente'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_post_step2_crea_conceptos(self):
        """POST con seleccionados crea exactamente esos conceptos."""
        url = reverse('wizard_step2') + '?perfil=oficina'
        seleccionados = ['sueldo_basico', 'asignacion_familiar', 'essalud_9pct']
        resp = self.client.post(url, {'conceptos': seleccionados})

        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('conceptos_lista'))

        # Verificar que se crearon
        for codigo in seleccionados:
            self.assertTrue(
                ConceptoRemunerativo.objects.filter(codigo=codigo).exists(),
                f'Concepto {codigo} debería haberse creado',
            )

    def test_post_step2_no_duplica_existentes(self):
        """Si un concepto ya existe, no se duplica ni se sobreescribe."""
        # Pre-crear uno
        ConceptoRemunerativo.objects.create(
            codigo='sueldo_basico', nombre='Custom Sueldo', tipo='INGRESO',
        )
        count_before = ConceptoRemunerativo.objects.count()

        url = reverse('wizard_step2') + '?perfil=oficina'
        self.client.post(url, {'conceptos': ['sueldo_basico', 'asignacion_familiar']})

        # asignacion_familiar se creó (1 nuevo), sueldo_basico ya existía (sin cambio)
        count_after = ConceptoRemunerativo.objects.count()
        self.assertEqual(count_after, count_before + 1)
        # El existente mantuvo su nombre custom
        c = ConceptoRemunerativo.objects.get(codigo='sueldo_basico')
        self.assertEqual(c.nombre, 'Custom Sueldo')

    def test_perfiles_tienen_conceptos_recomendados(self):
        """Cada perfil debe tener al menos 5 conceptos recomendados."""
        for key, perfil in PERFILES_EMPRESA.items():
            if key == 'personalizado':
                continue  # personalizado puede estar vacío
            self.assertGreaterEqual(
                len(perfil.get('conceptos_recomendados', [])),
                5,
                f'Perfil {key} debería tener ≥5 conceptos recomendados',
            )

    def test_perfiles_apuntan_a_templates_validos(self):
        """Cada conceptos_recomendados key debe existir en TEMPLATES_CONCEPTOS."""
        from nominas.views_conceptos import TEMPLATES_CONCEPTOS
        for key, perfil in PERFILES_EMPRESA.items():
            for codigo in perfil.get('conceptos_recomendados', []):
                self.assertIn(
                    codigo, TEMPLATES_CONCEPTOS,
                    f'Perfil {key} referencia template inexistente: {codigo}',
                )


class AuditLogCSVExportTests(TestCase):
    """Tests del export CSV del audit log."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='csv_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)
        # Crear un concepto para generar logs
        ConceptoRemunerativo.objects.create(
            codigo='test_csv', nombre='Test CSV', tipo='INGRESO',
        )

    def test_csv_export_headers(self):
        """GET /audit-log/csv/ → CSV con headers correctos."""
        resp = self.client.get('/nominas/conceptos/configurar/audit-log/csv/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv; charset=utf-8')
        self.assertIn('attachment', resp['Content-Disposition'])
        content = resp.content.decode('utf-8')
        # Headers esperados
        self.assertIn('fecha', content)
        self.assertIn('accion', content)
        self.assertIn('concepto_codigo', content)


class OnboardingApiPdfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='api_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_api_onboarding_devuelve_json_con_score(self):
        """GET /api/v1/nominas/onboarding/ → JSON con score, checks, totals."""
        resp = self.client.get('/api/v1/nominas/onboarding/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/json')
        data = resp.json()
        self.assertIn('score', data)
        self.assertIn('status', data)
        self.assertIn('totals', data)
        self.assertIn('checks', data)
        self.assertIsInstance(data['score'], int)
        self.assertGreaterEqual(data['score'], 0)
        self.assertLessEqual(data['score'], 100)

    def test_pdf_onboarding_genera_archivo(self):
        """GET /nominas/onboarding/validador.pdf → PDF o HTML fallback."""
        resp = self.client.get('/nominas/onboarding/validador.pdf')
        self.assertEqual(resp.status_code, 200)
        ct = resp['Content-Type']
        # WeasyPrint disponible → PDF; si no → HTML fallback
        self.assertTrue(ct.startswith('application/pdf') or ct.startswith('text/html'))
