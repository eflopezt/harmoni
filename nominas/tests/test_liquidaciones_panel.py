"""
Panel de liquidaciones unificado (cola de P6): lista LiquidacionLaboral
por estado y separa los cesados legacy sin liquidación.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from nominas.models import LiquidacionLaboral
from personal.models import Personal


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser('admin.liq', 'l@test.pe', 'x')


@pytest.fixture
def admin_client(client, admin_user):
    client.login(username='admin.liq', password='x')
    return client


@pytest.fixture
def cesado(db, admin_user):
    """Crear Personal ya Cesado dispara el signal que auto-crea la LL."""
    empresa = Empresa.objects.create(
        ruc='20987654321',
        razon_social='Empresa Panel Liquidaciones',
        activa=True,
        creado_por=admin_user,
    )
    return Personal.objects.create(
        empresa=empresa,
        nro_doc='70012345',
        apellidos_nombres='CESADO PANEL, IVAN',
        cargo='Operario',
        tipo_trab='Obrero',
        estado='Cesado',
        grupo_tareo='RCO',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        fecha_cese=date(2026, 6, 30),
        motivo_cese='RENUNCIA',
        sueldo_base=Decimal('1500.00'),
    )


def test_panel_lista_liquidacion_abierta(admin_client, cesado):
    assert LiquidacionLaboral.objects.filter(personal=cesado).exists()

    resp = admin_client.get(reverse('nominas_liquidaciones'))
    assert resp.status_code == 200
    abiertas = resp.context['abiertas']
    assert any(l.personal_id == cesado.pk for l in abiertas)
    assert resp.context['sin_liquidacion'] == []


def test_panel_separa_cerradas(admin_client, cesado):
    liq = LiquidacionLaboral.objects.get(personal=cesado)
    liq.estado = 'PAGADA'
    liq.save(update_fields=['estado'])

    resp = admin_client.get(reverse('nominas_liquidaciones'))
    assert resp.context['abiertas'] == []
    assert any(l.pk == liq.pk for l in resp.context['cerradas'])


def test_panel_detecta_cesado_legacy_sin_liquidacion(admin_client, cesado):
    LiquidacionLaboral.objects.filter(personal=cesado).delete()

    resp = admin_client.get(reverse('nominas_liquidaciones'))
    assert resp.context['abiertas'] == []
    assert any(p.pk == cesado.pk for p in resp.context['sin_liquidacion'])
