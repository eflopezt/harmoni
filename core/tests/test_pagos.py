"""
Tests del cobro online de suscripciones (core/pagos/ + core/views_pagos.py).

Sin HTTP real: la API de MercadoPago se simula con monkeypatch. Lo que se
verifica es NUESTRA lógica: parsing de referencia, extensión de suscripción,
idempotencia, validación de monto, firma del webhook y el flujo de las views.
"""
import hashlib
import hmac
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

from core.pagos import service
from core.pagos.mercadopago import build_external_reference, parse_external_reference
from empresas.models import Empresa
from empresas.models_billing import HistorialPago

User = get_user_model()

HOY = date.today()


def _empresa(**kwargs):
    defaults = {
        'ruc': '20555666777',
        'razon_social': 'Pagos Test S.A.C.',
        'plan': 'PLANILLA',
        'fecha_fin_prueba': HOY + timedelta(days=10),
    }
    defaults.update(kwargs)
    return Empresa.objects.create(**defaults)


def _pago_mp(empresa, payment_id='12345', plan='PLANILLA', meses=1,
             monto=None, status='approved'):
    """Dict como lo devuelve GET /v1/payments/{id} (campos que usamos)."""
    from core.planes import PLANES
    if monto is None:
        monto = PLANES[plan]['precio'] * meses
    return {
        'id': payment_id,
        'status': status,
        'transaction_amount': float(monto),
        'external_reference': build_external_reference(empresa.pk, plan, meses),
    }


# ════════════════════════════════════════════════════════════════
# external_reference
# ════════════════════════════════════════════════════════════════


class TestExternalReference:

    def test_round_trip(self):
        assert parse_external_reference(build_external_reference(7, 'TALENTO', 12)) == (7, 'TALENTO', 12)

    def test_basura_devuelve_none(self):
        assert parse_external_reference('') is None
        assert parse_external_reference(None) is None
        assert parse_external_reference('otra-cosa|1|X|1') is None
        assert parse_external_reference('harmoni|uno|X|1') is None


# ════════════════════════════════════════════════════════════════
# service.aplicar_pago_aprobado
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAplicarPago:

    def test_aplica_y_extiende_desde_hoy(self):
        emp = _empresa()
        ok, detalle = service.aplicar_pago_aprobado(_pago_mp(emp, meses=1))

        assert ok, detalle
        emp.refresh_from_db()
        assert emp.suscripcion_hasta is not None
        assert emp.suscripcion_hasta > HOY + timedelta(days=27)  # ~1 mes

        pago = HistorialPago.objects.get(metodo_pago='MERCADOPAGO', referencia='12345')
        assert pago.empresa_id == emp.pk
        assert pago.estado == 'PAGADO'
        assert pago.monto == Decimal('199')

    def test_extiende_desde_vencimiento_futuro(self):
        # Pagar antes de vencer NO regala ni quita días: suma desde el vencimiento.
        vence = HOY + timedelta(days=10)
        emp = _empresa(suscripcion_hasta=vence)
        ok, _ = service.aplicar_pago_aprobado(_pago_mp(emp, meses=3))

        assert ok
        emp.refresh_from_db()
        assert emp.suscripcion_hasta >= vence + timedelta(days=88)  # ~3 meses desde `vence`

    def test_idempotente_en_reintentos_del_webhook(self):
        emp = _empresa()
        pago = _pago_mp(emp, payment_id='777', meses=1)

        ok1, _ = service.aplicar_pago_aprobado(pago)
        emp.refresh_from_db()
        hasta_primera = emp.suscripcion_hasta

        ok2, detalle2 = service.aplicar_pago_aprobado(pago)  # reintento MP
        emp.refresh_from_db()

        assert ok1 and ok2  # ambos 200 para que MP deje de reintentar
        assert 'ya estaba aplicado' in detalle2
        assert emp.suscripcion_hasta == hasta_primera  # NO doble extensión
        assert HistorialPago.objects.filter(referencia='777').count() == 1

    def test_monto_insuficiente_no_aplica(self):
        emp = _empresa()
        ok, detalle = service.aplicar_pago_aprobado(_pago_mp(emp, meses=3, monto=199))

        assert not ok
        assert 'monto' in detalle
        emp.refresh_from_db()
        assert emp.suscripcion_hasta is None
        assert not HistorialPago.objects.exists()

    def test_status_no_aprobado_no_aplica(self):
        emp = _empresa()
        ok, _ = service.aplicar_pago_aprobado(_pago_mp(emp, status='rejected'))
        assert not ok
        assert not HistorialPago.objects.exists()

    def test_empresa_inexistente(self):
        emp = _empresa()
        pago = _pago_mp(emp)
        emp.delete()
        ok, detalle = service.aplicar_pago_aprobado(pago)
        assert not ok
        assert 'inexistente' in detalle

    def test_pago_actualiza_plan(self):
        # Upgrade vía pago: paga TALENTO teniendo ASISTENCIA → plan sube.
        emp = _empresa(plan='ASISTENCIA')
        ok, _ = service.aplicar_pago_aprobado(_pago_mp(emp, plan='TALENTO', meses=1))
        assert ok
        emp.refresh_from_db()
        assert emp.plan == 'TALENTO'


# ════════════════════════════════════════════════════════════════
# Webhook /webhooks/mercadopago/
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestWebhook:

    def setup_method(self):
        cache.clear()
        self.client = Client()

    def test_pago_aprobado_se_aplica(self, monkeypatch):
        emp = _empresa()
        monkeypatch.setattr(
            'core.pagos.mercadopago.obtener_pago',
            lambda pid: _pago_mp(emp, payment_id=pid),
        )
        r = self.client.post('/webhooks/mercadopago/?type=payment&data.id=999')

        assert r.status_code == 200
        emp.refresh_from_db()
        assert emp.suscripcion_hasta is not None
        assert HistorialPago.objects.filter(referencia='999').exists()

    def test_id_en_body_json(self, monkeypatch):
        emp = _empresa()
        monkeypatch.setattr(
            'core.pagos.mercadopago.obtener_pago',
            lambda pid: _pago_mp(emp, payment_id=pid),
        )
        r = self.client.post(
            '/webhooks/mercadopago/',
            data='{"type": "payment", "data": {"id": "555"}}',
            content_type='application/json',
        )
        assert r.status_code == 200
        assert HistorialPago.objects.filter(referencia='555').exists()

    def test_topic_no_payment_se_ignora(self, monkeypatch):
        def explota(pid):
            raise AssertionError('no debería consultar la API')
        monkeypatch.setattr('core.pagos.mercadopago.obtener_pago', explota)

        r = self.client.post('/webhooks/mercadopago/?topic=merchant_order&id=123')
        assert r.status_code == 200

    def test_firma_invalida_403(self, settings):
        settings.MERCADOPAGO_WEBHOOK_SECRET = 'testsecret'
        r = self.client.post('/webhooks/mercadopago/?type=payment&data.id=777')
        assert r.status_code == 403

    def test_firma_valida_pasa(self, settings, monkeypatch):
        settings.MERCADOPAGO_WEBHOOK_SECRET = 'testsecret'
        emp = _empresa()
        monkeypatch.setattr(
            'core.pagos.mercadopago.obtener_pago',
            lambda pid: _pago_mp(emp, payment_id=pid),
        )
        ts, request_id, data_id = '1718000000', 'req-abc', '777'
        manifest = f'id:{data_id};request-id:{request_id};ts:{ts};'
        v1 = hmac.new(b'testsecret', manifest.encode(), hashlib.sha256).hexdigest()

        r = self.client.post(
            f'/webhooks/mercadopago/?type=payment&data.id={data_id}',
            HTTP_X_SIGNATURE=f'ts={ts},v1={v1}',
            HTTP_X_REQUEST_ID=request_id,
        )
        assert r.status_code == 200
        assert HistorialPago.objects.filter(referencia='777').exists()

    def test_get_no_permitido(self):
        r = self.client.get('/webhooks/mercadopago/')
        assert r.status_code == 405


# ════════════════════════════════════════════════════════════════
# Vista iniciar_pago
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestIniciarPago:

    def setup_method(self):
        cache.clear()
        self.client = Client()

    def _login_con_empresa(self, **emp_kwargs):
        # Sin Personal asociado, EmpresaMiddleware resuelve la empresa principal.
        emp = _empresa(es_principal=True, **emp_kwargs)
        user = User.objects.create_user('pagador', 'p@x.pe', 'clave-larga-123')
        self.client.force_login(user)
        return emp

    def test_redirige_al_checkout(self, settings, monkeypatch):
        settings.MERCADOPAGO_ACCESS_TOKEN = 'TEST-token'
        self._login_con_empresa()
        capturado = {}

        def fake_checkout(empresa, plan_code, meses, base_url, payer_email=''):
            capturado.update(plan=plan_code, meses=meses)
            return 'https://mp.test/checkout/abc'

        monkeypatch.setattr('core.pagos.mercadopago.crear_checkout', fake_checkout)

        r = self.client.post('/cuenta/plan/pagar/', {'plan': 'PLANILLA', 'meses': '3'})
        assert r.status_code == 302
        assert r['Location'] == 'https://mp.test/checkout/abc'
        assert capturado == {'plan': 'PLANILLA', 'meses': 3}

    def test_sin_pasarela_configurada_redirige_con_aviso(self, settings):
        settings.MERCADOPAGO_ACCESS_TOKEN = ''
        self._login_con_empresa()
        r = self.client.post('/cuenta/plan/pagar/', {'meses': '1'})
        assert r.status_code == 302
        assert '/cuenta/plan/' in r['Location']

    def test_meses_invalidos_caen_a_1(self, settings, monkeypatch):
        settings.MERCADOPAGO_ACCESS_TOKEN = 'TEST-token'
        self._login_con_empresa()
        capturado = {}
        monkeypatch.setattr(
            'core.pagos.mercadopago.crear_checkout',
            lambda e, p, m, b, payer_email='': capturado.update(meses=m) or 'https://mp.test/x',
        )
        self.client.post('/cuenta/plan/pagar/', {'plan': 'PLANILLA', 'meses': '99'})
        assert capturado['meses'] == 1

    def test_anonimo_no_accede(self):
        r = self.client.post('/cuenta/plan/pagar/', {'meses': '1'})
        assert r.status_code == 302
        assert 'login' in r['Location']
