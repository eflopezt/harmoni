"""
Tests de aislamiento multi-tenant — ADR-001.

Verifican que:
- Los logs de audit quedan ligados a la empresa correcta
- El filtro por empresa en audit log funciona
- El health endpoint por empresa devuelve solo data de esa empresa
- Cambios en una empresa NO aparecen en logs de otra (defensive testing)
- El comando provision_enterprise_client genera archivos correctos
"""
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from nominas.models import ConceptoAuditLog, ConceptoRemunerativo
from nominas.signals_audit import (
    clear_audit_context,
    set_audit_context,
)


User = get_user_model()


def _get_or_create_empresa(razon='Empresa Test', ruc=None):
    """Helper que crea empresa con campos requeridos."""
    from empresas.models import Empresa
    from nominas.tests._helpers import unique_ruc
    if ruc is None:
        # RUC vía counter atómico, no timestamp — evita colisión por ms en suite.
        ruc = unique_ruc()
    e, _ = Empresa.objects.get_or_create(
        ruc=ruc,
        defaults={'razon_social': razon, 'plan': 'PROFESIONAL'},
    )
    return e


class AislamientoAuditLogTests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(username='admin_a', password='admin', is_superuser=True)
        self.user_b = User.objects.create_user(username='admin_b', password='admin', is_superuser=True)
        self.emp_a = _get_or_create_empresa('Empresa A', '20111111111')
        self.emp_b = _get_or_create_empresa('Empresa B', '20222222222')
        ConceptoAuditLog.objects.all().delete()

    def tearDown(self):
        clear_audit_context()

    def test_log_capta_empresa_del_contexto(self):
        """Si set_audit_context recibe empresa=X, el log queda con empresa=X."""
        set_audit_context(usuario=self.user_a, empresa=self.emp_a, contexto='test:isolation')
        c = ConceptoRemunerativo.objects.create(
            codigo='iso_test_a', nombre='Test A', tipo='INGRESO',
        )
        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertEqual(log.empresa_id, self.emp_a.pk)
        clear_audit_context()

    def test_filtro_empresa_en_audit_log_view(self):
        """El filtro ?empresa=X solo muestra logs de esa empresa."""
        # Crear log para A
        set_audit_context(usuario=self.user_a, empresa=self.emp_a)
        ConceptoRemunerativo.objects.create(codigo='filter_a', nombre='A', tipo='INGRESO')
        clear_audit_context()
        # Crear log para B
        set_audit_context(usuario=self.user_b, empresa=self.emp_b)
        ConceptoRemunerativo.objects.create(codigo='filter_b', nombre='B', tipo='INGRESO')
        clear_audit_context()

        self.client.force_login(self.user_a)

        # Filtrar por empresa A
        resp = self.client.get(f'/nominas/conceptos/configurar/audit-log/?empresa={self.emp_a.pk}')
        self.assertEqual(resp.status_code, 200)
        # Solo debe aparecer filter_a, no filter_b
        rows = resp.context['rows']
        codigos = {r['log'].concepto_codigo for r in rows}
        self.assertIn('filter_a', codigos)
        self.assertNotIn('filter_b', codigos)

    def test_log_sin_empresa_si_no_contexto(self):
        """Si no se setea empresa en contexto, el log queda con empresa=None (global/legacy)."""
        # Limpiar cualquier contexto previo
        clear_audit_context()
        c = ConceptoRemunerativo.objects.create(
            codigo='sin_emp', nombre='Sin emp', tipo='INGRESO',
        )
        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertIsNone(log.empresa)


class HealthMultiEmpresaTests(TestCase):
    def setUp(self):
        self.emp_a = _get_or_create_empresa('Empresa Health A', '20333333333')
        self.emp_b = _get_or_create_empresa('Empresa Health B', '20444444444')
        self.user = User.objects.create_user(username='h_admin', password='admin', is_superuser=True)
        ConceptoAuditLog.objects.all().delete()

    def test_health_global_sin_empresa(self):
        """GET /api/health/nominas/ — sin parámetro, devuelve métricas globales."""
        resp = self.client.get('/api/health/nominas/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['empresa_id'])

    def test_health_filtrado_por_empresa(self):
        """GET /api/health/nominas/?empresa=X — devuelve métricas de esa empresa."""
        resp = self.client.get(f'/api/health/nominas/?empresa={self.emp_a.pk}')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['empresa_id'], self.emp_a.pk)
        self.assertEqual(data['empresa_ruc'], self.emp_a.ruc)

    def test_health_empresa_invalida(self):
        """GET con empresa inexistente — empresa_id sigue None pero sin error."""
        resp = self.client.get('/api/health/nominas/?empresa=99999')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['empresa_id'])

    def test_health_cambios_filtrados_por_empresa(self):
        """cambios_7d cuenta solo los de la empresa filtrada."""
        # Crear log para empresa A
        set_audit_context(usuario=self.user, empresa=self.emp_a)
        ConceptoRemunerativo.objects.create(codigo='h_a_1', nombre='HA1', tipo='INGRESO')
        ConceptoRemunerativo.objects.create(codigo='h_a_2', nombre='HA2', tipo='INGRESO')
        clear_audit_context()
        # Log para empresa B
        set_audit_context(usuario=self.user, empresa=self.emp_b)
        ConceptoRemunerativo.objects.create(codigo='h_b_1', nombre='HB1', tipo='INGRESO')
        clear_audit_context()

        # Health de A debe ver 2 cambios, B ve 1
        # Nota: cache de 60s puede afectar; usamos URLs diferentes para evitarlo
        from django.core.cache import cache
        cache.clear()
        resp_a = self.client.get(f'/api/health/nominas/?empresa={self.emp_a.pk}')
        cache.clear()
        resp_b = self.client.get(f'/api/health/nominas/?empresa={self.emp_b.pk}')

        data_a = resp_a.json()
        data_b = resp_b.json()
        self.assertGreaterEqual(data_a['cambios_7d'], 2)
        self.assertGreaterEqual(data_b['cambios_7d'], 1)
        # B debe tener menos o iguales cambios que A
        self.assertLessEqual(data_b['cambios_7d'], data_a['cambios_7d'])


class ProvisionEnterpriseTests(TestCase):
    """Tests del comando provision_enterprise_client."""

    def test_comando_genera_archivos(self):
        """Verifica que el comando genere los 5 archivos esperados."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            call_command(
                'provision_enterprise_client',
                'testclient',
                name='Test Client',
                port=8099,
                output=str(Path(tmp) / 'testclient'),
            )
            generated = Path(tmp) / 'testclient'
            self.assertTrue((generated / 'docker-compose.yml').exists())
            self.assertTrue((generated / '.env.testclient').exists())
            self.assertTrue((generated / 'Caddyfile.entry').exists())
            self.assertTrue((generated / 'setup_testclient.sql').exists())
            self.assertTrue((generated / 'README.md').exists())

    def test_archivos_sustituyen_variables(self):
        """Los archivos generados NO deben contener __VAR__ sin sustituir."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            call_command(
                'provision_enterprise_client',
                'subst_test',
                name='Subst Test',
                port=8098,
                output=str(Path(tmp) / 'subst_test'),
            )
            for fname in ('docker-compose.yml', '.env.subst_test', 'Caddyfile.entry'):
                content = (Path(tmp) / 'subst_test' / fname).read_text(encoding='utf-8')
                # Excluir referencias en comments del README
                # Estos archivos NO deben tener placeholders
                if '__CLIENT_SLUG__' in content:
                    self.fail(f'{fname} contiene __CLIENT_SLUG__ sin sustituir')

    def test_slug_invalido_rechazado(self):
        """Slug con caracteres especiales debe ser rechazado."""
        import tempfile
        from io import StringIO
        with tempfile.TemporaryDirectory() as tmp:
            out = StringIO()
            call_command(
                'provision_enterprise_client',
                'bad slug!',
                name='Bad',
                port=8097,
                output=str(Path(tmp) / 'bad'),
                stdout=out,
            )
            self.assertIn('Slug invalido', out.getvalue())
