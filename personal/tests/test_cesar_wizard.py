"""
Tests Sprint 2 — Wizard "Cesar trabajador" (3 pasos).

Cubre:
  1. GET paso 1 muestra el form (admin → 200)
  2. POST preview devuelve JSON con conceptos calculados (sin persistir)
  3. POST confirmar persiste cese + signal crea LiquidacionLaboral
  4. GET paso 1 con trabajador ya cesado → redirige a la liquidación
  5. Permisos: solo superuser puede acceder al wizard
  6. Validaciones: fecha futura / fecha inválida son rechazadas en preview
  7. Idempotencia: confirmar dos veces sobre el mismo trabajador no duplica LL
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area, Personal, SubArea
from nominas.models import LiquidacionLaboral


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_wiz', password='x', email='wiz@a.com',
    )


@pytest.fixture
def normal_user(db):
    return User.objects.create_user(
        username='normal_wiz', password='x', is_staff=True,
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def client_normal(client, normal_user):
    client.force_login(normal_user)
    return client


@pytest.fixture
def area(db):
    return Area.objects.create(nombre='Operaciones Wizard')


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre='Sub Wizard', area=area)


@pytest.fixture
def worker_activo(db, subarea):
    """Trabajador activo: sueldo S/3000, alta 2024-01-15."""
    return Personal.objects.create(
        nro_doc='45000001',
        apellidos_nombres='WIZARD ACTIVO, JUAN',
        cargo='Operario',
        tipo_trab='Empleado',
        estado='Activo',
        subarea=subarea,
        fecha_alta=date(2024, 1, 15),
        sueldo_base=Decimal('3000.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


@pytest.fixture
def worker_cesado(db, subarea):
    """Trabajador YA cesado."""
    return Personal.objects.create(
        nro_doc='45000002',
        apellidos_nombres='WIZARD CESADO, MARIA',
        cargo='Mozo',
        tipo_trab='Empleado',
        estado='Cesado',
        subarea=subarea,
        fecha_alta=date(2024, 1, 15),
        fecha_cese=date(2026, 3, 31),
        motivo_cese='RENUNCIA',
        sueldo_base=Decimal('3000.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


# ═════════════════════════════════════════════════════════════════════════════
# 1. Paso 1 — Form (GET)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaso1Form:
    def test_get_paso1_admin_render_200(self, client_admin, worker_activo):
        url = reverse('personal_cesar_paso1', args=[worker_activo.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 200
        # El template del wizard usa la palabra "Datos del cese" en el card
        assert b'Datos del cese' in resp.content
        # Y muestra el nombre del trabajador
        assert worker_activo.apellidos_nombres.encode() in resp.content

    def test_get_paso1_personal_inexistente_404(self, client_admin):
        url = reverse('personal_cesar_paso1', args=[999999])
        resp = client_admin.get(url)
        assert resp.status_code == 404

    def test_get_paso1_con_personal_cesado_redirige(self, client_admin, worker_cesado):
        """Si el trabajador ya está cesado y tiene LL, redirige a la liquidación."""
        # Crear LL para que tenga a dónde redirigir
        liq = LiquidacionLaboral.objects.filter(personal=worker_cesado).first()
        if not liq:
            liq = LiquidacionLaboral.objects.create(
                personal=worker_cesado,
                fecha_cese=worker_cesado.fecha_cese,
                motivo_cese='RENUNCIA',
            )
        url = reverse('personal_cesar_paso1', args=[worker_cesado.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 302
        # Redirige a la LL o al detalle
        assert ('/liquidacion/' in resp.url) or (f'/personal/{worker_cesado.pk}/' in resp.url)


# ═════════════════════════════════════════════════════════════════════════════
# 2. Paso 2 — Preview AJAX (POST)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaso2Preview:
    def test_post_preview_devuelve_json_con_conceptos(self, client_admin, worker_activo):
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':    '2026-03-31',
            'motivo_cese':   'RENUNCIA',
            'observaciones': 'Renuncia voluntaria con preaviso.',
        })
        assert resp.status_code == 200
        assert resp['Content-Type'].startswith('application/json')
        data = json.loads(resp.content)
        assert data['success'] is True
        assert data['personal']['nro_doc'] == worker_activo.nro_doc
        assert data['fecha_cese'] == '2026-03-31'
        assert data['motivo'] == 'RENUNCIA'

        # Estructura completa de conceptos
        assert 'haberes' in data and 'descuentos' in data and 'totales' in data
        for k in ('vacaciones_truncas', 'gratif_trunca', 'cts_trunca',
                  'sueldo_mes_curso', 'he_no_compensadas',
                  'indemnizacion', 'otros_pagos'):
            assert k in data['haberes']
        for k in ('prestamos_pendientes', 'adelantos_pendientes',
                  'embargo', 'otros_descuentos'):
            assert k in data['descuentos']
        assert 'total_bruto' in data['totales']
        assert 'total_neto'  in data['totales']

    def test_preview_NO_persiste_cese(self, client_admin, worker_activo):
        """El preview NO debe cambiar el estado del trabajador ni crear LL."""
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        client_admin.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'RENUNCIA',
        })
        worker_activo.refresh_from_db()
        assert worker_activo.estado == 'Activo'
        assert not LiquidacionLaboral.objects.filter(personal=worker_activo).exists()

    def test_preview_calculo_consistente_con_modelo(self, client_admin, worker_activo):
        """El preview debe arrojar exactamente lo mismo que calcular() persistido."""
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'RENUNCIA',
        })
        data = json.loads(resp.content)

        # Cesar manualmente y comparar
        ll = LiquidacionLaboral(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        ll.calcular(persist=False)
        assert Decimal(data['haberes']['sueldo_mes_curso']) == ll.sueldo_mes_curso
        assert Decimal(data['haberes']['gratif_trunca'])    == ll.gratif_trunca
        assert Decimal(data['totales']['total_neto'])       == ll.total_neto

    def test_preview_fecha_futura_400(self, client_admin, worker_activo):
        futura = (date.today() + timedelta(days=10)).isoformat()
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':  futura,
            'motivo_cese': 'RENUNCIA',
        })
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert 'futura' in data['error'].lower()

    def test_preview_motivo_invalido_400(self, client_admin, worker_activo):
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'INVENTADO_X',
        })
        assert resp.status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
# 3. Paso 3 — Confirmar (POST)
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPaso3Confirmar:
    def test_confirmar_persiste_cese_y_crea_liquidacion(self, client_admin, worker_activo):
        url = reverse('personal_cesar_confirmar', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':    '2026-03-31',
            'motivo_cese':   'RENUNCIA',
            'observaciones': 'Renuncia con carta firmada el 20/03/2026.',
        })
        # Redirect a /nominas/liquidacion/<id>/
        assert resp.status_code == 302
        assert '/liquidacion/' in resp.url

        # Personal actualizado
        worker_activo.refresh_from_db()
        assert worker_activo.estado == 'Cesado'
        assert worker_activo.fecha_cese == date(2026, 3, 31)

        # LL creada por el signal y conservada
        liq = LiquidacionLaboral.objects.get(personal=worker_activo)
        assert liq.fecha_cese == date(2026, 3, 31)
        assert liq.motivo_cese == 'RENUNCIA'
        assert liq.estado == 'CALCULADA'  # calcular() lo deja así
        assert liq.total_bruto > Decimal('0')

    def test_confirmar_despido_arbitrario_calcula_indemnizacion(self, client_admin, worker_activo):
        """Para motivo DESPIDO_ARB, la indemnización (Art. 38 DS 003-97-TR) > 0."""
        url = reverse('personal_cesar_confirmar', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'DESPIDO_ARB',
        })
        assert resp.status_code == 302
        liq = LiquidacionLaboral.objects.get(personal=worker_activo)
        assert liq.motivo_cese == 'DESPIDO_ARB'
        assert liq.indemnizacion > Decimal('0')

    def test_confirmar_idempotente_no_duplica_liquidacion(self, client_admin, worker_activo):
        """Reintentar el confirm sobre el mismo trabajador no crea LL duplicada."""
        url = reverse('personal_cesar_confirmar', args=[worker_activo.pk])
        client_admin.post(url, {'fecha_cese': '2026-03-31', 'motivo_cese': 'RENUNCIA'})
        # Segundo POST sobre trabajador ya cesado
        resp2 = client_admin.post(url, {'fecha_cese': '2026-03-31', 'motivo_cese': 'RENUNCIA'})
        assert resp2.status_code == 302
        assert LiquidacionLaboral.objects.filter(personal=worker_activo).count() == 1

    def test_confirmar_sin_fecha_rechaza(self, client_admin, worker_activo):
        url = reverse('personal_cesar_confirmar', args=[worker_activo.pk])
        resp = client_admin.post(url, {
            'fecha_cese':  '',
            'motivo_cese': 'RENUNCIA',
        })
        # Redirige a paso 1 con mensaje de error
        assert resp.status_code == 302
        worker_activo.refresh_from_db()
        assert worker_activo.estado == 'Activo'  # NO se cesó


# ═════════════════════════════════════════════════════════════════════════════
# 4. Permisos — solo superuser
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPermisos:
    def test_usuario_normal_no_puede_paso1(self, client_normal, worker_activo):
        url = reverse('personal_cesar_paso1', args=[worker_activo.pk])
        resp = client_normal.get(url)
        # user_passes_test redirige a login (302) si falla el test
        assert resp.status_code == 302

    def test_usuario_normal_no_puede_preview(self, client_normal, worker_activo):
        url = reverse('personal_cesar_preview', args=[worker_activo.pk])
        resp = client_normal.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'RENUNCIA',
        })
        assert resp.status_code == 302

    def test_usuario_normal_no_puede_confirmar(self, client_normal, worker_activo):
        url = reverse('personal_cesar_confirmar', args=[worker_activo.pk])
        resp = client_normal.post(url, {
            'fecha_cese':  '2026-03-31',
            'motivo_cese': 'RENUNCIA',
        })
        assert resp.status_code == 302
        worker_activo.refresh_from_db()
        assert worker_activo.estado == 'Activo'

    def test_anonimo_redirect_login(self, client, worker_activo):
        url = reverse('personal_cesar_paso1', args=[worker_activo.pk])
        resp = client.get(url)
        assert resp.status_code == 302
