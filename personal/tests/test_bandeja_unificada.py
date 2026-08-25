"""
Bandeja de aprobaciones unificada (P16): el dashboard /aprobaciones/
agrega también vacaciones, permisos, préstamos y workflows, además de
las 4 fuentes originales (roster, papeletas, HE, justificaciones).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from empresas.models import Empresa
from personal.models import Personal
from vacaciones.models import SaldoVacacional, SolicitudPermiso, SolicitudVacacion, TipoPermiso


@pytest.fixture
def admin_client(client, db):
    User.objects.create_superuser('admin.bandeja', 'a@test.pe', 'x')
    client.login(username='admin.bandeja', password='x')
    return client


@pytest.fixture
def personal(db):
    return Personal.objects.create(
        empresa=Empresa.objects.filter(activa=True).first(),
        nro_doc='78888888',
        apellidos_nombres='BANDEJA TEST, LUIS',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('2500.00'),
    )


def test_bandeja_incluye_vacaciones_y_permisos(admin_client, personal):
    saldo = SaldoVacacional.objects.create(
        personal=personal,
        periodo_inicio=date(2025, 1, 1), periodo_fin=date(2025, 12, 31),
        dias_derecho=30, dias_gozados=0, dias_vendidos=0,
        dias_pendientes=30, estado='PENDIENTE',
    )
    SolicitudVacacion.objects.create(
        personal=personal, saldo=saldo,
        fecha_inicio=date(2026, 8, 3), fecha_fin=date(2026, 8, 7),
        dias_calendario=0, estado='PENDIENTE',
    )
    tipo = TipoPermiso.objects.create(nombre='Permiso Test', codigo='perm-test')
    SolicitudPermiso.objects.create(
        personal=personal, tipo=tipo,
        fecha_inicio=date(2026, 8, 10), fecha_fin=date(2026, 8, 10),
        estado='PENDIENTE',
    )

    resp = admin_client.get('/aprobaciones/')
    assert resp.status_code == 200
    stats = resp.context['stats']
    assert stats['cnt_vacaciones'] == 1
    assert stats['cnt_permisos'] == 1
    assert stats['total_pendientes'] >= 2
    assert len(resp.context['vacacion_items']) == 1
    assert len(resp.context['permiso_items']) == 1
    # Claves de las fuentes nuevas siempre presentes
    for k in ('cnt_prestamos', 'cnt_workflows'):
        assert k in stats


def test_tab_vacaciones_solo_carga_esa_fuente(admin_client, personal):
    SolicitudVacacion.objects.create(
        personal=personal,
        fecha_inicio=date(2026, 8, 3), fecha_fin=date(2026, 8, 7),
        dias_calendario=0, estado='PENDIENTE',
    )
    resp = admin_client.get('/aprobaciones/?tab=vacaciones')
    assert resp.status_code == 200
    assert len(resp.context['vacacion_items']) == 1
    assert resp.context['papeleta_items'] == []


def test_busqueda_filtra_vacaciones(admin_client, personal):
    SolicitudVacacion.objects.create(
        personal=personal,
        fecha_inicio=date(2026, 8, 3), fecha_fin=date(2026, 8, 7),
        dias_calendario=0, estado='PENDIENTE',
    )
    resp = admin_client.get('/aprobaciones/?buscar=BANDEJA')
    assert resp.context['stats']['cnt_vacaciones'] == 1
    resp = admin_client.get('/aprobaciones/?buscar=NOEXISTE')
    assert resp.context['stats']['cnt_vacaciones'] == 0
