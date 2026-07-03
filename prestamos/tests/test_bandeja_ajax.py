"""
Aprobación/rechazo de préstamos vía AJAX desde la bandeja unificada (F2).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from personal.models import Area, Personal
from prestamos.models import Prestamo, TipoPrestamo

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}


class PrestamoBandejaAjaxTest(TestCase):

    def setUp(self):
        Area.objects.get_or_create(nombre='Administracion')
        self.personal = Personal.objects.create(
            nro_doc='45678901',
            apellidos_nombres='PRESTAMO AJAX, SARA',
            cargo='Analista',
            tipo_trab='Empleado',
        )
        self.tipo = TipoPrestamo.objects.create(
            nombre='Prestamo Personal', codigo='personal',
            max_cuotas=12, tasa_interes_mensual=Decimal('0.000'),
            requiere_aprobacion=True, activo=True,
        )
        self.prestamo = Prestamo.objects.create(
            personal=self.personal, tipo=self.tipo,
            monto_solicitado=Decimal('3000.00'), num_cuotas=6,
            estado='PENDIENTE',
        )
        User.objects.create_superuser('admin.pa', 'p@test.pe', 'x')
        self.client.login(username='admin.pa', password='x')

    def test_aprobar_ajax_devuelve_json_y_genera_cuotas(self):
        resp = self.client.post(
            reverse('prestamo_aprobar', args=[self.prestamo.pk]),
            {'monto_aprobado': '3000.00',
             'fecha_descuento': date.today().isoformat()},
            **AJAX,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        self.prestamo.refresh_from_db()
        assert self.prestamo.estado in ('APROBADO', 'EN_CURSO')
        assert self.prestamo.cuotas.count() == 6

    def test_aprobar_ajax_monto_invalido_400(self):
        resp = self.client.post(
            reverse('prestamo_aprobar', args=[self.prestamo.pk]),
            {'monto_aprobado': 'abc'},
            **AJAX,
        )
        assert resp.status_code == 400
        assert resp.json()['ok'] is False

    def test_aprobar_ajax_estado_invalido_400(self):
        self.prestamo.estado = 'RECHAZADO'
        self.prestamo.save(update_fields=['estado'])
        resp = self.client.post(
            reverse('prestamo_aprobar', args=[self.prestamo.pk]), {}, **AJAX)
        assert resp.status_code == 400

    def test_rechazar_ajax(self):
        resp = self.client.post(
            reverse('prestamo_rechazar', args=[self.prestamo.pk]),
            {'motivo_rechazo': 'sin capacidad de descuento'},
            **AJAX,
        )
        assert resp.status_code == 200
        assert resp.json()['ok'] is True
        self.prestamo.refresh_from_db()
        assert self.prestamo.estado == 'RECHAZADO'

    def test_flujo_no_ajax_sigue_redirigiendo(self):
        resp = self.client.post(
            reverse('prestamo_aprobar', args=[self.prestamo.pk]),
            {'monto_aprobado': '3000.00',
             'fecha_descuento': date.today().isoformat()},
        )
        assert resp.status_code == 302
