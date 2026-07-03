"""
Decisión de workflows vía AJAX desde la bandeja unificada (F2).
"""
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse

from workflows.models import EtapaFlujo, FlujoTrabajo, InstanciaFlujo

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class DecidirAjaxTest(TestCase):

    def setUp(self):
        ct = ContentType.objects.get_for_model(User)
        self.flujo = FlujoTrabajo.objects.create(
            nombre='Flujo AJAX',
            content_type=ct,
            campo_trigger='first_name',
            valor_trigger='Pendiente',
            campo_resultado='first_name',
            valor_aprobado='Aprobado',
            valor_rechazado='Rechazado',
        )
        self.etapa1 = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='Etapa 1',
            tipo_aprobador='SUPERUSER',
        )
        self.solicitante = User.objects.create_user('sol.wf', 's@test.pe', 'x')
        self.target = User.objects.create_user('target.wf', 't@test.pe', 'x',
                                               first_name='Pendiente')
        self.instancia = InstanciaFlujo.objects.create(
            flujo=self.flujo,
            content_type=ct,
            object_id=self.target.pk,
            etapa_actual=self.etapa1,
            estado='EN_PROCESO',
            solicitante=self.solicitante,
        )
        User.objects.create_superuser('admin.wf', 'a@test.pe', 'x')
        self.client.login(username='admin.wf', password='x')

    def test_aprobar_ajax(self):
        resp = self.client.post(
            reverse('workflow_decidir', args=[self.instancia.pk]),
            {'decision': 'APROBADO', 'comentario': 'ok'},
            **AJAX,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert 'estado' in data
        self.instancia.refresh_from_db()
        assert self.instancia.estado in ('APROBADO', 'EN_PROCESO')

    def test_rechazar_ajax(self):
        resp = self.client.post(
            reverse('workflow_decidir', args=[self.instancia.pk]),
            {'decision': 'RECHAZADO', 'comentario': 'no procede'},
            **AJAX,
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        self.instancia.refresh_from_db()
        assert self.instancia.estado == 'RECHAZADO'

    def test_decision_invalida_400(self):
        resp = self.client.post(
            reverse('workflow_decidir', args=[self.instancia.pk]),
            {'decision': 'TALVEZ'},
            **AJAX,
        )
        assert resp.status_code == 400

    def test_sin_permiso_403(self):
        self.client.logout()
        User.objects.create_user('staff.wf', 'st@test.pe', 'x', is_staff=True)
        self.client.login(username='staff.wf', password='x')
        resp = self.client.post(
            reverse('workflow_decidir', args=[self.instancia.pk]),
            {'decision': 'APROBADO'},
            **AJAX,
        )
        assert resp.status_code == 403

    def test_flujo_no_ajax_sigue_redirigiendo(self):
        resp = self.client.post(
            reverse('workflow_decidir', args=[self.instancia.pk]),
            {'decision': 'APROBADO'},
        )
        assert resp.status_code == 302
