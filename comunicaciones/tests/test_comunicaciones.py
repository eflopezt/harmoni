"""
Tests for the comunicaciones module.

Covers:
- Notificacion model: creation, estado transitions
- NotificacionService.enviar(): creates notification, EMAIL type attempts send
- NotificacionService.enviar_desde_plantilla(): renders template with context
- PlantillaNotificacion: template rendering with variables
"""
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from comunicaciones.models import (
    Notificacion,
    PlantillaNotificacion,
    ConfiguracionSMTP,
)
from comunicaciones.services import NotificacionService
from personal.models import Area, SubArea, Personal


class _BaseTestCase(TestCase):
    """Shared fixture: creates a Personal record for use as destinatario."""

    @classmethod
    def setUpTestData(cls):
        cls.area = Area.objects.create(nombre="Administracion")
        cls.subarea = SubArea.objects.create(nombre="RRHH", area=cls.area)
        cls.personal = Personal.objects.create(
            nro_doc="12345678",
            apellidos_nombres="Lopez Garcia, Juan",
            cargo="Analista",
            tipo_trab="Empleado",
            subarea=cls.subarea,
            correo_corporativo="juan@harmoni.test",
            estado="Activo",
        )


# ─────────────────────────────────────────────────────────────
# 1. Notificacion model
# ─────────────────────────────────────────────────────────────

class TestNotificacionModel(_BaseTestCase):
    """Notificacion creation and estado transitions."""

    def test_create_in_app_notification(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Bienvenido",
            cuerpo="<p>Hola</p>",
            tipo="IN_APP",
            estado="PENDIENTE",
        )
        self.assertEqual(notif.tipo, "IN_APP")
        self.assertEqual(notif.estado, "PENDIENTE")
        self.assertIn("Bienvenido", str(notif))

    def test_create_email_notification(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            destinatario_email="juan@harmoni.test",
            asunto="Aviso",
            cuerpo="<p>Contenido</p>",
            tipo="EMAIL",
            estado="PENDIENTE",
        )
        self.assertEqual(notif.tipo, "EMAIL")
        self.assertEqual(notif.destinatario_email, "juan@harmoni.test")

    def test_estado_transition_pendiente_to_enviada(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
            tipo="IN_APP",
            estado="PENDIENTE",
        )
        notif.estado = "ENVIADA"
        notif.enviada_en = timezone.now()
        notif.save(update_fields=["estado", "enviada_en"])

        notif.refresh_from_db()
        self.assertEqual(notif.estado, "ENVIADA")
        self.assertIsNotNone(notif.enviada_en)

    def test_estado_transition_enviada_to_leida(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
            tipo="IN_APP",
            estado="ENVIADA",
            enviada_en=timezone.now(),
        )
        notif.estado = "LEIDA"
        notif.leida_en = timezone.now()
        notif.save(update_fields=["estado", "leida_en"])

        notif.refresh_from_db()
        self.assertEqual(notif.estado, "LEIDA")
        self.assertIsNotNone(notif.leida_en)

    def test_estado_fallida_stores_error(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
            tipo="EMAIL",
            estado="FALLIDA",
            error_detalle="SMTP timeout",
        )
        self.assertEqual(notif.estado, "FALLIDA")
        self.assertEqual(notif.error_detalle, "SMTP timeout")

    def test_str_with_destinatario(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Memo",
            cuerpo="body",
        )
        result = str(notif)
        self.assertIn("Memo", result)

    def test_str_without_destinatario_uses_email(self):
        notif = Notificacion.objects.create(
            destinatario=None,
            destinatario_email="ext@test.com",
            asunto="Externo",
            cuerpo="body",
        )
        self.assertIn("ext@test.com", str(notif))

    def test_ordering_is_newest_first(self):
        n1 = Notificacion.objects.create(
            destinatario=self.personal, asunto="First", cuerpo="a",
        )
        n2 = Notificacion.objects.create(
            destinatario=self.personal, asunto="Second", cuerpo="b",
        )
        qs = list(Notificacion.objects.all())
        self.assertEqual(qs[0].pk, n2.pk)
        self.assertEqual(qs[1].pk, n1.pk)

    def test_metadata_default_is_empty_dict(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
        )
        self.assertEqual(notif.metadata, {})

    def test_metadata_stores_json(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
            metadata={"url": "/vacaciones/", "icono": "fa-plane"},
        )
        notif.refresh_from_db()
        self.assertEqual(notif.metadata["url"], "/vacaciones/")


# ─────────────────────────────────────────────────────────────
# 2. NotificacionService.enviar()
# ─────────────────────────────────────────────────────────────

class TestNotificacionServiceEnviar(_BaseTestCase):
    """NotificacionService.enviar() behaviour."""

    def test_enviar_in_app_creates_with_estado_enviada(self):
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="Hola",
            cuerpo="<p>Texto</p>",
            tipo="IN_APP",
        )
        self.assertIsInstance(notif, Notificacion)
        self.assertEqual(notif.estado, "ENVIADA")
        self.assertIsNotNone(notif.enviada_en)
        self.assertEqual(notif.tipo, "IN_APP")

    def test_enviar_in_app_resolves_email_from_personal(self):
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="Test",
            cuerpo="body",
            tipo="IN_APP",
        )
        self.assertEqual(notif.destinatario_email, "juan@harmoni.test")

    @patch("comunicaciones.services.NotificacionService._enviar_email")
    def test_enviar_email_calls_enviar_email(self, mock_send):
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="Email Test",
            cuerpo="<p>Body</p>",
            tipo="EMAIL",
        )
        self.assertEqual(notif.estado, "PENDIENTE")
        mock_send.assert_called_once_with(notif)

    @patch("comunicaciones.services.NotificacionService._enviar_email")
    def test_enviar_ambos_creates_two_notifications(self, mock_send):
        result = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="Dual",
            cuerpo="<p>Both</p>",
            tipo="AMBOS",
        )
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        tipos = {n.tipo for n in result}
        self.assertEqual(tipos, {"IN_APP", "EMAIL"})
        mock_send.assert_called_once()

    def test_enviar_with_plantilla_codigo_links_plantilla(self):
        plantilla = PlantillaNotificacion.objects.create(
            nombre="Test",
            codigo="test-link",
            asunto_template="Subject",
            cuerpo_template="Body",
            tipo="IN_APP",
            modulo="SISTEMA",
        )
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="S",
            cuerpo="B",
            tipo="IN_APP",
            plantilla_codigo="test-link",
        )
        self.assertEqual(notif.plantilla, plantilla)

    def test_enviar_with_nonexistent_plantilla_sets_none(self):
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="S",
            cuerpo="B",
            tipo="IN_APP",
            plantilla_codigo="does-not-exist",
        )
        self.assertIsNone(notif.plantilla)

    def test_enviar_stores_contexto_in_metadata(self):
        ctx = {"modulo": "vacaciones", "dias": 15}
        notif = NotificacionService.enviar(
            destinatario=self.personal,
            asunto="Vac",
            cuerpo="body",
            tipo="IN_APP",
            contexto=ctx,
        )
        self.assertEqual(notif.metadata, ctx)

    def test_enviar_with_destinatario_email_override(self):
        notif = NotificacionService.enviar(
            destinatario=None,
            asunto="Ext",
            cuerpo="body",
            tipo="IN_APP",
            destinatario_email="override@test.com",
        )
        self.assertEqual(notif.destinatario_email, "override@test.com")
        self.assertIsNone(notif.destinatario)


# ─────────────────────────────────────────────────────────────
# 3. NotificacionService._enviar_email() — SMTP inactive path
# ─────────────────────────────────────────────────────────────

class TestEnviarEmailSmtpInactive(_BaseTestCase):
    """When SMTP is inactive, email notifications become FALLIDA."""

    def test_smtp_inactive_marks_fallida(self):
        # Ensure SMTP config exists and is inactive
        config = ConfiguracionSMTP.get()
        config.activa = False
        config.save()

        notif = Notificacion.objects.create(
            destinatario=self.personal,
            destinatario_email="juan@harmoni.test",
            asunto="Fail",
            cuerpo="body",
            tipo="EMAIL",
            estado="PENDIENTE",
        )
        NotificacionService._enviar_email(notif)

        notif.refresh_from_db()
        self.assertEqual(notif.estado, "FALLIDA")
        self.assertIn("SMTP no está activa", notif.error_detalle)

    def test_email_without_address_marks_fallida(self):
        config = ConfiguracionSMTP.get()
        config.activa = True
        config.save()

        personal_no_email = Personal.objects.create(
            nro_doc="99999999",
            apellidos_nombres="Sin Email, Pedro",
            cargo="Auxiliar",
            tipo_trab="Empleado",
            estado="Activo",
            correo_corporativo="",
            correo_personal="",
        )
        notif = Notificacion.objects.create(
            destinatario=personal_no_email,
            destinatario_email="",
            asunto="No email",
            cuerpo="body",
            tipo="EMAIL",
            estado="PENDIENTE",
        )
        NotificacionService._enviar_email(notif)

        notif.refresh_from_db()
        self.assertEqual(notif.estado, "FALLIDA")
        self.assertIn("sin dirección", notif.error_detalle)


# ─────────────────────────────────────────────────────────────
# 4. NotificacionService.enviar_desde_plantilla()
# ─────────────────────────────────────────────────────────────

class TestEnviarDesdePlantilla(_BaseTestCase):
    """enviar_desde_plantilla renders template and sends."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.plantilla = PlantillaNotificacion.objects.create(
            nombre="Vacaciones Aprobadas",
            codigo="vacaciones-aprobadas",
            asunto_template="Vacaciones aprobadas para {{ nombre }}",
            cuerpo_template="<p>Hola {{ nombre }}, tus vacaciones del {{ fecha_inicio }} fueron aprobadas.</p>",
            tipo="IN_APP",
            modulo="VACACIONES",
            activa=True,
        )

    def test_renders_asunto_with_context(self):
        notif = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="vacaciones-aprobadas",
            contexto_dict={"nombre": "Juan", "fecha_inicio": "01/04/2026"},
        )
        self.assertIn("Juan", notif.asunto)
        self.assertEqual(notif.asunto, "Vacaciones aprobadas para Juan")

    def test_renders_cuerpo_with_context(self):
        notif = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="vacaciones-aprobadas",
            contexto_dict={"nombre": "Juan", "fecha_inicio": "01/04/2026"},
        )
        self.assertIn("01/04/2026", notif.cuerpo)
        self.assertIn("Juan", notif.cuerpo)

    def test_uses_plantilla_tipo(self):
        notif = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="vacaciones-aprobadas",
            contexto_dict={"nombre": "Juan", "fecha_inicio": "01/04/2026"},
        )
        self.assertEqual(notif.tipo, "IN_APP")

    def test_nonexistent_plantilla_returns_none(self):
        result = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="no-existe",
            contexto_dict={"nombre": "X"},
        )
        self.assertIsNone(result)

    def test_inactive_plantilla_returns_none(self):
        PlantillaNotificacion.objects.create(
            nombre="Inactiva",
            codigo="plantilla-inactiva",
            asunto_template="Asunto",
            cuerpo_template="Cuerpo",
            tipo="IN_APP",
            modulo="SISTEMA",
            activa=False,
        )
        result = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="plantilla-inactiva",
            contexto_dict={},
        )
        self.assertIsNone(result)

    def test_stores_context_dict_in_metadata(self):
        ctx = {"nombre": "Juan", "fecha_inicio": "01/04/2026"}
        notif = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="vacaciones-aprobadas",
            contexto_dict=ctx,
        )
        self.assertEqual(notif.metadata, ctx)

    @patch("comunicaciones.services.NotificacionService._enviar_email")
    def test_email_plantilla_triggers_send(self, mock_send):
        PlantillaNotificacion.objects.create(
            nombre="Email Template",
            codigo="email-tpl",
            asunto_template="Asunto {{ nombre }}",
            cuerpo_template="<p>{{ nombre }}</p>",
            tipo="EMAIL",
            modulo="SISTEMA",
            activa=True,
        )
        notif = NotificacionService.enviar_desde_plantilla(
            destinatario=self.personal,
            plantilla_codigo="email-tpl",
            contexto_dict={"nombre": "Pedro"},
        )
        mock_send.assert_called_once()
        self.assertEqual(notif.tipo, "EMAIL")


# ─────────────────────────────────────────────────────────────
# 5. PlantillaNotificacion model
# ─────────────────────────────────────────────────────────────

class TestPlantillaNotificacion(TestCase):
    """PlantillaNotificacion model behaviour."""

    def test_create_plantilla(self):
        p = PlantillaNotificacion.objects.create(
            nombre="Bienvenida Onboarding",
            codigo="bienvenida-onboarding",
            asunto_template="Bienvenido {{ nombre }}",
            cuerpo_template="<h1>Hola {{ nombre }}</h1><p>Tu cargo es {{ cargo }}.</p>",
            tipo="AMBOS",
            modulo="ONBOARDING",
        )
        self.assertTrue(p.activa)
        self.assertEqual(p.tipo, "AMBOS")

    def test_str_format(self):
        p = PlantillaNotificacion.objects.create(
            nombre="Alerta Contrato",
            codigo="alerta-contrato",
            asunto_template="Sub",
            cuerpo_template="Body",
            modulo="RRHH",
        )
        self.assertEqual(str(p), "[RRHH] Alerta Contrato")

    def test_ordering_by_modulo_then_nombre(self):
        p_sistema = PlantillaNotificacion.objects.create(
            nombre="AAA", codigo="aaa", asunto_template="s", cuerpo_template="b",
            modulo="SISTEMA",
        )
        p_asist = PlantillaNotificacion.objects.create(
            nombre="ZZZ", codigo="zzz", asunto_template="s", cuerpo_template="b",
            modulo="ASISTENCIA",
        )
        qs = list(PlantillaNotificacion.objects.all())
        # ASISTENCIA < SISTEMA alphabetically
        self.assertEqual(qs[0].pk, p_asist.pk)
        self.assertEqual(qs[1].pk, p_sistema.pk)

    def test_codigo_is_unique(self):
        PlantillaNotificacion.objects.create(
            nombre="First", codigo="unique-code",
            asunto_template="s", cuerpo_template="b",
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            PlantillaNotificacion.objects.create(
                nombre="Second", codigo="unique-code",
                asunto_template="s", cuerpo_template="b",
            )

    def test_template_rendering_with_django_syntax(self):
        """Verify that asunto_template and cuerpo_template support Django template variables."""
        from django.template import Template, Context

        p = PlantillaNotificacion.objects.create(
            nombre="Render Test",
            codigo="render-test",
            asunto_template="Hola {{ nombre }}, tu solicitud #{{ numero }}",
            cuerpo_template="<p>{{ nombre }}, tu {{ tipo }} fue procesado el {{ fecha }}.</p>",
        )
        ctx = Context({
            "nombre": "Maria",
            "numero": "42",
            "tipo": "permiso",
            "fecha": "15/03/2026",
        })

        asunto = Template(p.asunto_template).render(ctx)
        cuerpo = Template(p.cuerpo_template).render(ctx)

        self.assertEqual(asunto, "Hola Maria, tu solicitud #42")
        self.assertIn("Maria", cuerpo)
        self.assertIn("15/03/2026", cuerpo)

    def test_inactive_plantilla_excluded_by_filter(self):
        PlantillaNotificacion.objects.create(
            nombre="Active", codigo="active-tpl",
            asunto_template="s", cuerpo_template="b", activa=True,
        )
        PlantillaNotificacion.objects.create(
            nombre="Inactive", codigo="inactive-tpl",
            asunto_template="s", cuerpo_template="b", activa=False,
        )
        activas = PlantillaNotificacion.objects.filter(activa=True)
        self.assertEqual(activas.count(), 1)
        self.assertEqual(activas.first().codigo, "active-tpl")


# ─────────────────────────────────────────────────────────────
# 6. NotificacionService.marcar_leida()
# ─────────────────────────────────────────────────────────────

class TestMarcarLeida(_BaseTestCase):
    """NotificacionService.marcar_leida() transitions."""

    def test_marcar_leida_from_enviada(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Read me",
            cuerpo="body",
            tipo="IN_APP",
            estado="ENVIADA",
            enviada_en=timezone.now(),
        )
        result = NotificacionService.marcar_leida(notif.pk)
        self.assertTrue(result)

        notif.refresh_from_db()
        self.assertEqual(notif.estado, "LEIDA")
        self.assertIsNotNone(notif.leida_en)

    def test_marcar_leida_nonexistent_returns_false(self):
        result = NotificacionService.marcar_leida(999999)
        self.assertFalse(result)

    def test_marcar_leida_already_leida_returns_false(self):
        notif = Notificacion.objects.create(
            destinatario=self.personal,
            asunto="Already read",
            cuerpo="body",
            tipo="IN_APP",
            estado="LEIDA",
            leida_en=timezone.now(),
        )
        result = NotificacionService.marcar_leida(notif.pk)
        self.assertFalse(result)


# ─────────────────────────────────────────────────────────────
# 7. NotificacionService.notificaciones_pendientes()
# ─────────────────────────────────────────────────────────────

class TestNotificacionesPendientes(_BaseTestCase):
    """Count of unread IN_APP notifications."""

    def test_counts_only_in_app_enviada(self):
        # Two ENVIADA IN_APP
        Notificacion.objects.create(
            destinatario=self.personal, asunto="A", cuerpo="b",
            tipo="IN_APP", estado="ENVIADA", enviada_en=timezone.now(),
        )
        Notificacion.objects.create(
            destinatario=self.personal, asunto="B", cuerpo="b",
            tipo="IN_APP", estado="ENVIADA", enviada_en=timezone.now(),
        )
        # One LEIDA (should not count)
        Notificacion.objects.create(
            destinatario=self.personal, asunto="C", cuerpo="b",
            tipo="IN_APP", estado="LEIDA",
        )
        # One EMAIL (should not count)
        Notificacion.objects.create(
            destinatario=self.personal, asunto="D", cuerpo="b",
            tipo="EMAIL", estado="ENVIADA",
        )

        count = NotificacionService.notificaciones_pendientes(self.personal)
        self.assertEqual(count, 2)
