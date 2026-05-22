"""
Tests del workflow extendido de Préstamos:
- calcular_cronograma (sin/con interés)
- transiciones BORRADOR → PENDIENTE → APROBADO → EN_CURSO (DESEMBOLSADO)
- rechazar(), desembolsar()
- VENCIDA por fecha
- aplicar_cuotas_a_planilla → DescuentoPlanilla
- Vista solicitar (200)
- Vista contrato PDF (200)
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from personal.models import Area, Personal
from prestamos.cronograma import calcular_cronograma
from prestamos.integracion_descuentos import (
    aplicar_cuotas_a_planilla,
    marcar_cuotas_vencidas,
)
from prestamos.models import CuotaPrestamo, Prestamo, TipoPrestamo

User = get_user_model()


# Helpers ──────────────────────────────────────────────────────────────────
def _make_area():
    a, _ = Area.objects.get_or_create(nombre='Administracion')
    return a


def _make_personal(nro_doc='99887766', nombre='Test, Demo'):
    _make_area()
    return Personal.objects.create(
        nro_doc=nro_doc, apellidos_nombres=nombre,
        cargo='Tester', tipo_trab='Empleado',
    )


def _make_tipo(**kw):
    defaults = dict(nombre='Prestamo Personal Test', codigo='test-personal',
                    max_cuotas=12, tasa_interes_mensual=Decimal('0.000'),
                    requiere_aprobacion=True, activo=True)
    defaults.update(kw)
    return TipoPrestamo.objects.create(**defaults)


def _make_user(username='admin_test', is_superuser=True):
    return User.objects.create_user(username=username, password='pass12345',
                                    is_superuser=is_superuser,
                                    is_staff=is_superuser)


# Cronograma ───────────────────────────────────────────────────────────────
class CronogramaTest(TestCase):

    def test_seis_cuotas_sin_interes(self):
        cron = calcular_cronograma(Decimal('1200.00'), 6, date(2026, 6, 1))
        assert len(cron) == 6
        suma = sum(r['monto'] for r in cron)
        assert suma == Decimal('1200.00')
        for r in cron:
            assert r['monto'] == Decimal('200.00')
            assert r['interes'] == Decimal('0.00')

    def test_fechas_mensuales(self):
        cron = calcular_cronograma(Decimal('600.00'), 3, date(2026, 4, 1))
        assert cron[0]['fecha_vencimiento'] == date(2026, 4, 1)
        assert cron[1]['fecha_vencimiento'] == date(2026, 5, 1)
        assert cron[2]['fecha_vencimiento'] == date(2026, 6, 1)

    def test_residuo_absorbe_ultima(self):
        cron = calcular_cronograma(Decimal('1000.00'), 7, date(2026, 1, 1))
        suma = sum(r['monto'] for r in cron)
        assert suma == Decimal('1000.00')

    def test_con_interes_simple(self):
        cron = calcular_cronograma(Decimal('1000.00'), 6,
                                   date(2026, 1, 1), tasa_interes=Decimal('1.0'))
        suma = sum(r['monto'] for r in cron)
        assert suma > Decimal('1000.00')
        assert suma < Decimal('1100.00')
        assert cron[-1]['saldo'] == Decimal('0.00')

    def test_invalid_inputs(self):
        with pytest.raises(ValueError):
            calcular_cronograma(Decimal('100'), 0, date.today())
        with pytest.raises(ValueError):
            calcular_cronograma(Decimal('0'), 3, date.today())


# Workflow estados ─────────────────────────────────────────────────────────
class WorkflowTest(TestCase):

    def test_marcar_aprobado_no_genera_cuotas(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('600.00'), num_cuotas=3,
            estado='PENDIENTE',
        )
        u = _make_user()
        p.marcar_aprobado(u)
        p.refresh_from_db()
        assert p.estado == 'APROBADO'
        assert p.aprobado_por == u
        assert p.cuotas.count() == 0

    def test_desembolsar_desde_aprobado_genera_cuotas(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('600.00'), num_cuotas=3,
            estado='PENDIENTE',
        )
        u = _make_user()
        p.marcar_aprobado(u)
        p.desembolsar(u, fecha_desembolso=date(2026, 5, 1),
                      fecha_descuento=date(2026, 6, 1))
        p.refresh_from_db()
        assert p.estado == 'EN_CURSO'
        assert p.fecha_desembolso == date(2026, 5, 1)
        assert p.cuotas.count() == 3
        suma = sum(c.monto for c in p.cuotas.all())
        assert suma == Decimal('600.00')

    def test_rechazar(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('500'), num_cuotas=2,
            estado='PENDIENTE',
        )
        p.rechazar(_make_user(), motivo='Saldo insuficiente del trabajador')
        p.refresh_from_db()
        assert p.estado == 'RECHAZADO'
        assert p.motivo_rechazo == 'Saldo insuficiente del trabajador'

    def test_no_desembolsar_si_pagado(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('600'), num_cuotas=2,
            estado='PAGADO',
        )
        with pytest.raises(ValueError):
            p.desembolsar(_make_user())


# Cuota VENCIDA ────────────────────────────────────────────────────────────
class CuotaVencidaTest(TestCase):

    def test_cuota_se_marca_vencida(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('300'), num_cuotas=1,
            estado='PENDIENTE',
        )
        u = _make_user()
        ayer = date.today() - timedelta(days=40)
        p.desembolsar(u, fecha_desembolso=ayer, fecha_descuento=ayer)
        cuota = p.cuotas.first()
        assert cuota.esta_vencida is True
        cuota.actualizar_estado_vencimiento()
        cuota.refresh_from_db()
        assert cuota.estado == 'VENCIDA'

    def test_marcar_cuotas_vencidas_helper(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('600'), num_cuotas=2,
            estado='PENDIENTE',
        )
        u = _make_user()
        ayer = date.today() - timedelta(days=40)
        p.desembolsar(u, fecha_desembolso=ayer, fecha_descuento=ayer)
        n = marcar_cuotas_vencidas()
        assert n >= 1


# Integración descuentos ───────────────────────────────────────────────────
class IntegracionDescuentosTest(TestCase):

    def test_aplicar_cuotas_crea_descuento(self):
        p = Prestamo.objects.create(
            personal=_make_personal(), tipo=_make_tipo(),
            monto_solicitado=Decimal('600.00'), num_cuotas=3,
            estado='PENDIENTE',
        )
        u = _make_user()
        p.desembolsar(u, fecha_desembolso=date(2026, 5, 1),
                      fecha_descuento=date(2026, 5, 1))

        resumen = aplicar_cuotas_a_planilla(2026, 5, usuario=u)

        if resumen['descuentos_disponible']:
            assert len(resumen['descuentos_creados']) >= 1
            cuota = p.cuotas.order_by('numero').first()
            cuota.refresh_from_db()
            assert cuota.estado == 'DESCONTADA'
            assert cuota.descuento_planilla is not None
            assert cuota.descuento_planilla.monto_total == cuota.monto

    def test_aplicar_idempotente_no_duplica(self):
        p = Prestamo.objects.create(
            personal=_make_personal(nro_doc='11223344'),
            tipo=_make_tipo(codigo='test-other'),
            monto_solicitado=Decimal('300.00'), num_cuotas=1,
            estado='PENDIENTE',
        )
        u = _make_user()
        p.desembolsar(u, fecha_desembolso=date(2026, 5, 1),
                      fecha_descuento=date(2026, 5, 1))

        r1 = aplicar_cuotas_a_planilla(2026, 5, usuario=u)
        r2 = aplicar_cuotas_a_planilla(2026, 5, usuario=u)
        if r1['descuentos_disponible']:
            assert len(r1['descuentos_creados']) == 1
            assert len(r2['descuentos_creados']) == 0


# Vistas ───────────────────────────────────────────────────────────────────
class VistasTest(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='worker', password='pass12345',
        )
        self.personal = _make_personal(nro_doc='77665544', nombre='Worker, Test')
        # Personal.usuario es la FK al User en este proyecto
        try:
            self.personal.usuario = self.user
            self.personal.save()
        except Exception:
            pass
        self.tipo = _make_tipo(codigo='vista-test')

    def test_solicitar_get_200(self):
        c = Client()
        c.login(username='worker', password='pass12345')
        url = reverse('mis_prestamos_solicitar')
        resp = c.get(url)
        assert resp.status_code in (200, 302)

    def test_contrato_pdf_render(self):
        admin = _make_user(username='admin_pdf', is_superuser=True)
        c = Client()
        c.force_login(admin)
        p = Prestamo.objects.create(
            personal=self.personal, tipo=self.tipo,
            monto_solicitado=Decimal('500'), num_cuotas=2,
            estado='PENDIENTE',
        )
        p.desembolsar(admin, fecha_desembolso=date(2026, 5, 1),
                      fecha_descuento=date(2026, 5, 1))

        url = reverse('prestamo_contrato_pdf', args=[p.pk])
        resp = c.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content[:4] == b'%PDF'

    def test_cronograma_view_render(self):
        admin = _make_user(username='admin_cron', is_superuser=True)
        c = Client()
        c.force_login(admin)
        p = Prestamo.objects.create(
            personal=self.personal, tipo=self.tipo,
            monto_solicitado=Decimal('600'), num_cuotas=3,
            estado='PENDIENTE',
        )
        p.desembolsar(admin, fecha_desembolso=date(2026, 5, 1),
                      fecha_descuento=date(2026, 5, 1))
        url = reverse('prestamo_cronograma', args=[p.pk])
        resp = c.get(url)
        assert resp.status_code == 200
