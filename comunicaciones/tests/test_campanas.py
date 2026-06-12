"""
Tests para CampanaComunicacion + segmentación + WhatsApp stub + workflow.
"""
from unittest.mock import patch

import pytest

from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse

from comunicaciones.models import CampanaComunicacion, Notificacion
from comunicaciones.segmentacion import (
    resolver_destinatarios, contar_destinatarios, vista_previa_destinatarios,
)
from comunicaciones.campana_service import enviar_campana
from comunicaciones.whatsapp_service import WhatsAppService
from personal.models import Area, SubArea, Personal


class _CampanaBase(TestCase):
    """Crea 2 áreas, 3 subáreas y 6 trabajadores con cargos/grupos variados."""

    @classmethod
    def setUpTestData(cls):
        cls.area_admin = Area.objects.create(nombre='Administración')
        cls.area_cocina = Area.objects.create(nombre='Cocina')

        cls.sub_rrhh = SubArea.objects.create(nombre='RRHH', area=cls.area_admin)
        cls.sub_contab = SubArea.objects.create(nombre='Contabilidad', area=cls.area_admin)
        cls.sub_caliente = SubArea.objects.create(nombre='Cocina caliente', area=cls.area_cocina)

        def mk(nro, nombre, sub, cargo, grupo, activo=True, email='', cel=''):
            return Personal.objects.create(
                nro_doc=nro,
                apellidos_nombres=nombre,
                cargo=cargo,
                tipo_trab='Empleado',
                subarea=sub,
                grupo_tareo=grupo,
                estado='Activo' if activo else 'Cesado',
                correo_corporativo=email,
                celular=cel,
            )

        cls.p_rrhh1 = mk('10000001', 'Garcia, Ana', cls.sub_rrhh,
                         'Analista de RRHH', 'STAFF',
                         email='ana@harmoni.test', cel='51999000001')
        cls.p_rrhh2 = mk('10000002', 'Lopez, Luis', cls.sub_rrhh,
                         'Asistente RRHH', 'STAFF', email='luis@harmoni.test')
        cls.p_contab = mk('10000003', 'Perez, Maria', cls.sub_contab,
                          'Contadora', 'STAFF', email='maria@harmoni.test')
        cls.p_cocinero1 = mk('10000004', 'Diaz, Pedro', cls.sub_caliente,
                              'Cocinero senior', 'RCO',
                              email='pedro@harmoni.test', cel='51999000004')
        cls.p_cocinero2 = mk('10000005', 'Ramos, Jose', cls.sub_caliente,
                              'Cocinero', 'RCO')
        cls.p_cesado = mk('10000006', 'Inactivo, Juan', cls.sub_rrhh,
                          'Cocinero', 'RCO', activo=False)


# ─────────────────────────────────────────────────────────────
# 1. Segmentación
# ─────────────────────────────────────────────────────────────

class TestSegmentacion(_CampanaBase):

    def test_solo_activos_default(self):
        camp = CampanaComunicacion(filtro_solo_activos=True)
        qs = resolver_destinatarios(camp)
        self.assertEqual(qs.count(), 5)  # 6 menos el cesado
        self.assertNotIn(self.p_cesado, qs)

    def test_filtro_area(self):
        camp = CampanaComunicacion(
            filtro_area_ids=[self.area_admin.pk],
            filtro_solo_activos=True,
        )
        qs = resolver_destinatarios(camp)
        # 3 activos en Administración (rrhh1, rrhh2, contab)
        self.assertEqual(qs.count(), 3)
        self.assertIn(self.p_rrhh1, qs)
        self.assertNotIn(self.p_cocinero1, qs)

    def test_filtro_subarea(self):
        camp = CampanaComunicacion(
            filtro_subarea_ids=[self.sub_caliente.pk],
            filtro_solo_activos=True,
        )
        qs = resolver_destinatarios(camp)
        self.assertEqual(qs.count(), 2)
        self.assertIn(self.p_cocinero1, qs)
        self.assertIn(self.p_cocinero2, qs)

    def test_filtro_cargo_substring(self):
        camp = CampanaComunicacion(
            filtro_cargo='cocinero',
            filtro_solo_activos=True,
        )
        qs = resolver_destinatarios(camp)
        # 2 cocineros activos (p_cesado se excluye por activos)
        self.assertEqual(qs.count(), 2)

    def test_filtro_grupo_tareo(self):
        camp = CampanaComunicacion(
            filtro_grupo_tareo='STAFF',
            filtro_solo_activos=True,
        )
        self.assertEqual(resolver_destinatarios(camp).count(), 3)

        camp_rco = CampanaComunicacion(
            filtro_grupo_tareo='RCO',
            filtro_solo_activos=True,
        )
        self.assertEqual(resolver_destinatarios(camp_rco).count(), 2)

    def test_filtros_combinados(self):
        """Cocineros activos del área Cocina."""
        camp = CampanaComunicacion(
            filtro_area_ids=[self.area_cocina.pk],
            filtro_cargo='cocinero',
            filtro_solo_activos=True,
        )
        self.assertEqual(resolver_destinatarios(camp).count(), 2)

    def test_vista_previa(self):
        camp = CampanaComunicacion(filtro_solo_activos=True)
        preview = vista_previa_destinatarios(camp, sample_size=3)
        self.assertEqual(preview['total'], 5)
        self.assertEqual(len(preview['sample']), 3)


# ─────────────────────────────────────────────────────────────
# 2. WhatsApp stub
# ─────────────────────────────────────────────────────────────

class TestWhatsAppStub(TestCase):

    def test_phone_normalization(self):
        self.assertEqual(WhatsAppService._normalize_phone('+51 999 888 777'), '51999888777')
        self.assertEqual(WhatsAppService._normalize_phone('999888777'), '51999888777')
        self.assertEqual(WhatsAppService._normalize_phone(''), '')
        self.assertEqual(WhatsAppService._normalize_phone('abc'), '')

    def test_send_no_provider_returns_error(self):
        """Sin provider configurado, intenta OpenClaw como fallback y falla limpio."""
        with patch('comunicaciones.whatsapp_service.WhatsAppService._get_config') as mock_cfg:
            mock_cfg.return_value = {
                'provider': 'NONE',
                'meta_phone_id': '', 'meta_access_token': '',
                'openclaw_url': 'http://localhost:19000', 'openclaw_token': '',
            }
            # OpenClaw no está corriendo en tests → debe devolver ok=False sin excepción
            result = WhatsAppService.send_message('51999000001', 'Test stub')
            self.assertIn('ok', result)
            self.assertFalse(result['ok'])  # no real gateway
            self.assertEqual(result['provider'], 'OPENCLAW')

    def test_send_meta_mocked(self):
        """Con provider=META_CLOUD y requests mockeado, retorna ok=True."""
        mock_response = type('R', (), {
            'status_code': 200,
            'json': lambda self: {'messages': [{'id': 'wamid.test'}]},
        })()
        with patch('comunicaciones.whatsapp_service.WhatsAppService._get_config') as mock_cfg, \
             patch('comunicaciones.whatsapp_service.requests.post', return_value=mock_response):
            mock_cfg.return_value = {
                'provider': 'META_CLOUD',
                'meta_phone_id': '12345', 'meta_access_token': 'tk',
                'openclaw_url': '', 'openclaw_token': '',
            }
            result = WhatsAppService.send_message('51999000001', 'Hola')
            self.assertTrue(result['ok'])
            self.assertEqual(result['provider'], 'META_CLOUD')
            self.assertEqual(result['message_id'], 'wamid.test')


# ─────────────────────────────────────────────────────────────
# 3. Workflow campaña
# ─────────────────────────────────────────────────────────────

class TestCampanaWorkflow(_CampanaBase):

    def test_modelo_str_y_propiedades(self):
        c = CampanaComunicacion.objects.create(
            nombre='Test', asunto='X', cuerpo='Y',
            canal='IN_APP', estado='BORRADOR',
        )
        self.assertIn('Test', str(c))
        self.assertTrue(c.es_editable)
        self.assertEqual(c.tasa_exito, 0)

        c.destinatarios_count = 10
        c.enviados_ok = 8
        c.save()
        self.assertEqual(c.tasa_exito, 80.0)

    def test_enviar_campana_in_app_actualiza_stats(self):
        c = CampanaComunicacion.objects.create(
            nombre='Cocineros', asunto='Capacitación',
            cuerpo='<p>Asistir el viernes</p>',
            canal='IN_APP',
            filtro_cargo='cocinero',
            filtro_solo_activos=True,
        )
        resultado = enviar_campana(c)
        self.assertEqual(resultado['total'], 2)
        self.assertEqual(resultado['ok'], 2)
        self.assertEqual(resultado['fallidos'], 0)

        c.refresh_from_db()
        self.assertEqual(c.estado, 'ENVIADA')
        self.assertIsNotNone(c.enviada_en)
        self.assertEqual(c.destinatarios_count, 2)
        self.assertEqual(c.enviados_ok, 2)

        # Verifica que se crearon Notificaciones IN_APP con campana_id en metadata
        notifs = Notificacion.objects.filter(
            metadata__campana_id=c.pk, tipo='IN_APP'
        )
        self.assertEqual(notifs.count(), 2)

    def test_enviar_no_reenvia_si_ya_enviada(self):
        c = CampanaComunicacion.objects.create(
            nombre='X', asunto='Y', cuerpo='Z',
            canal='IN_APP', estado='ENVIADA',
        )
        resultado = enviar_campana(c)
        self.assertEqual(resultado['total'], 0)


# ─────────────────────────────────────────────────────────────
# 4. Vistas HTTP
# ─────────────────────────────────────────────────────────────

class TestCampanaViews(_CampanaBase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin = User.objects.create_superuser(
            'admin_camp', 'a@a.com', 'pass12345'
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='admin_camp', password='pass12345')

    def test_panel_responde_200(self):
        r = self.client.get(reverse('com_campanas_panel'))
        self.assertEqual(r.status_code, 200)

    def test_crear_form_responde_200(self):
        r = self.client.get(reverse('com_campana_crear'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Vista previa destinatarios')

    def test_crear_borrador_post(self):
        r = self.client.post(reverse('com_campana_crear'), {
            'nombre': 'Test campaña',
            'asunto': 'Asunto X',
            'cuerpo': '<p>Cuerpo</p>',
            'canal': 'IN_APP',
            'filtro_cargo': 'cocinero',
            'filtro_solo_activos': 'on',
            'accion': 'borrador',
        })
        # Redirige a detalle
        self.assertEqual(r.status_code, 302)
        c = CampanaComunicacion.objects.get(nombre='Test campaña')
        self.assertEqual(c.estado, 'BORRADOR')
        self.assertEqual(c.filtro_cargo, 'cocinero')
        # Pre-cuenta destinatarios
        self.assertEqual(c.destinatarios_count, 2)

    def test_crear_y_enviar_actualiza_estado(self):
        r = self.client.post(reverse('com_campana_crear'), {
            'nombre': 'Envío directo',
            'asunto': 'X', 'cuerpo': '<p>Y</p>',
            'canal': 'IN_APP',
            'filtro_grupo_tareo': 'STAFF',
            'filtro_solo_activos': 'on',
            'accion': 'enviar',
        })
        self.assertEqual(r.status_code, 302)
        c = CampanaComunicacion.objects.get(nombre='Envío directo')
        self.assertEqual(c.estado, 'ENVIADA')
        self.assertEqual(c.enviados_ok, 3)  # 3 STAFF activos

    def test_preview_ajax(self):
        r = self.client.post(reverse('com_campana_preview'), {
            'filtro_cargo': 'cocinero',
            'filtro_solo_activos': 'on',
        })
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data['total'], 2)
        self.assertEqual(len(data['sample']), 2)

    def test_detalle_responde_200(self):
        c = CampanaComunicacion.objects.create(
            nombre='Test', asunto='X', cuerpo='Y', canal='IN_APP',
        )
        r = self.client.get(reverse('com_campana_detalle', args=[c.pk]))
        self.assertEqual(r.status_code, 200)
