"""
Tests para ConceptoAuditLog — captura automática de cambios vía signals.

Cubre:
- CREATE: log generado al crear concepto
- UPDATE: log con diff campo por campo
- DELETE: log que persiste tras eliminación
- ACTIVAR/DESACTIVAR: detecta cambio único de flag activo
- AUTOFIX/TEMPLATE/CSV_IMPORT: accion_override del audit context
- thread-local: usuario/IP capturados correctamente
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from nominas.models import ConceptoAuditLog, ConceptoRemunerativo
from nominas.signals_audit import clear_audit_context, set_audit_context


User = get_user_model()


class ConceptoAuditLogTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='test_admin', password='test123', is_superuser=True,
        )
        # Limpiar audit logs de fixtures
        ConceptoAuditLog.objects.all().delete()

    def tearDown(self):
        clear_audit_context()

    def test_create_genera_log(self):
        """Al crear un concepto se genera log CREATE con snapshot completo."""
        set_audit_context(usuario=self.user, contexto='test:create')
        c = ConceptoRemunerativo.objects.create(
            codigo='test_create',
            nombre='Test Create',
            tipo='INGRESO',
        )
        logs = ConceptoAuditLog.objects.filter(concepto=c)
        self.assertEqual(logs.count(), 1)
        log = logs.first()
        self.assertEqual(log.accion, 'CREATE')
        self.assertEqual(log.usuario, self.user)
        self.assertEqual(log.usuario_username, 'test_admin')
        self.assertGreater(log.num_cambios, 5)
        self.assertEqual(log.contexto, 'test:create')

    def test_update_solo_registra_campos_modificados(self):
        """UPDATE registra solo los campos que cambiaron."""
        c = ConceptoRemunerativo.objects.create(
            codigo='test_upd', nombre='Test', tipo='INGRESO',
        )
        ConceptoAuditLog.objects.all().delete()

        set_audit_context(usuario=self.user)
        c.nombre = 'Test Modificado'
        c.afecto_essalud = True
        c.save()

        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertEqual(log.accion, 'UPDATE')
        self.assertIn('nombre', log.campos_cambiados)
        self.assertIn('afecto_essalud', log.campos_cambiados)
        self.assertNotIn('tipo', log.campos_cambiados)  # no cambió
        self.assertEqual(log.campos_cambiados['nombre']['despues'], 'Test Modificado')

    def test_activar_desactivar_detectados(self):
        """Cambio único de activo → log con accion ACTIVAR o DESACTIVAR."""
        c = ConceptoRemunerativo.objects.create(
            codigo='test_act', nombre='Test', tipo='INGRESO', activo=True,
        )
        ConceptoAuditLog.objects.all().delete()

        set_audit_context(usuario=self.user)
        c.activo = False
        c.save()
        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertEqual(log.accion, 'DESACTIVAR')

        c.activo = True
        c.save()
        log = ConceptoAuditLog.objects.filter(concepto=c).order_by('-fecha').first()
        self.assertEqual(log.accion, 'ACTIVAR')

    def test_delete_persiste_log(self):
        """DELETE crea log y persiste tras eliminar el concepto."""
        c = ConceptoRemunerativo.objects.create(
            codigo='test_del', nombre='Test Delete', tipo='INGRESO',
        )
        codigo = c.codigo
        ConceptoAuditLog.objects.all().delete()

        set_audit_context(usuario=self.user)
        c.delete()

        log = ConceptoAuditLog.objects.filter(concepto_codigo=codigo).first()
        self.assertIsNotNone(log)
        self.assertEqual(log.accion, 'DELETE')
        self.assertIsNone(log.concepto)  # FK SET_NULL
        self.assertEqual(log.concepto_codigo, codigo)

    def test_accion_override_template(self):
        """set_audit_context con accion_override='TEMPLATE' genera log TEMPLATE."""
        set_audit_context(usuario=self.user, accion_override='TEMPLATE')
        c = ConceptoRemunerativo.objects.create(
            codigo='test_tpl', nombre='From Template', tipo='INGRESO',
        )
        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertEqual(log.accion, 'TEMPLATE')

    def test_ip_y_user_agent_capturados(self):
        """IP + User-Agent + URL contexto del request quedan en el log."""
        set_audit_context(
            usuario=self.user,
            ip='192.168.1.42',
            user_agent='Mozilla/5.0 Test',
            contexto='/nominas/conceptos/configurar/nuevo/',
        )
        c = ConceptoRemunerativo.objects.create(
            codigo='test_ctx', nombre='Test', tipo='INGRESO',
        )
        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        self.assertEqual(log.ip, '192.168.1.42')
        self.assertEqual(log.user_agent, 'Mozilla/5.0 Test')
        self.assertIn('/nominas/conceptos', log.contexto)

    def test_resumen_cambios_formato_legible(self):
        """resumen_cambios devuelve strings 'campo: antes → despues'."""
        c = ConceptoRemunerativo.objects.create(
            codigo='test_res', nombre='Original', tipo='INGRESO',
        )
        ConceptoAuditLog.objects.all().delete()

        set_audit_context(usuario=self.user)
        c.nombre = 'Modificado'
        c.save()

        log = ConceptoAuditLog.objects.filter(concepto=c).first()
        resumen = log.resumen_cambios
        self.assertGreater(len(resumen), 0)
        self.assertTrue(any('nombre' in r and 'Original' in r and 'Modificado' in r for r in resumen))


class ConceptoAuditViewsTests(TestCase):
    """Tests de las vistas del audit log."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='audit_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)
        self.c = ConceptoRemunerativo.objects.create(
            codigo='test_view', nombre='Test View', tipo='INGRESO',
        )

    def test_audit_log_view_render(self):
        """GET /nominas/conceptos/configurar/audit-log/ → 200."""
        resp = self.client.get('/nominas/conceptos/configurar/audit-log/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Bitácora de cambios')

    def test_audit_log_filtros(self):
        """Filtro por accion=CREATE."""
        resp = self.client.get('/nominas/conceptos/configurar/audit-log/?accion=CREATE')
        self.assertEqual(resp.status_code, 200)

    def test_historial_concepto(self):
        """GET /nominas/conceptos/configurar/<pk>/historial/ → 200."""
        resp = self.client.get(f'/nominas/conceptos/configurar/{self.c.pk}/historial/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.c.nombre)


class OnboardingValidadorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='onboarding_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_validador_render(self):
        """GET /nominas/onboarding/validador/ → 200 con score."""
        resp = self.client.get('/nominas/onboarding/validador/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Score de configuración')

    def test_validador_score_calculado(self):
        """Score es entero entre 0 y 100."""
        resp = self.client.get('/nominas/onboarding/validador/')
        score = resp.context['score']
        self.assertIsInstance(score, int)
        self.assertGreaterEqual(score, 0)
        self.assertLessEqual(score, 100)


class MiDiaNominasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dia_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_mi_dia_render(self):
        """GET /nominas/mi-dia/ → 200 con saludo."""
        resp = self.client.get('/nominas/mi-dia/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Mi Día Nóminas')

    def test_mi_dia_tareas_no_vacio(self):
        """Siempre hay al menos una tarea (al menos el mensaje 'todo al día')."""
        resp = self.client.get('/nominas/mi-dia/')
        tareas = resp.context['tareas']
        self.assertGreater(len(tareas), 0)
