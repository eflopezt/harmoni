"""Offboarding no cruza trabajadores, procesos ni pasos entre empresas."""
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from onboarding.models import (
    PasoOffboarding,
    PlantillaOffboarding,
    ProcesoOffboarding,
)
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre, owner):
    return Empresa.objects.create(
        ruc=ruc,
        razon_social=nombre,
        activa=True,
        creado_por=owner,
    )


def _personal(empresa, doc, nombre):
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=doc,
        apellidos_nombres=nombre,
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        fecha_alta=date(2025, 1, 1),
        sueldo_base=2500,
    )


@pytest.fixture
def tenant_case(client):
    admin = User.objects.create_superuser('off_tenant', 'off@tenant.pe', 'pw')
    propia = _empresa('20711111111', 'Empresa offboarding propia', admin)
    ajena = _empresa('20722222222', 'Empresa offboarding ajena', admin)
    persona_propia = _personal(propia, '73001001', 'OFFBOARDING PROPIO')
    persona_ajena = _personal(ajena, '73001002', 'OFFBOARDING AJENO')
    plantilla = PlantillaOffboarding.objects.create(nombre='Cierre tenant')
    proceso_propio = ProcesoOffboarding.objects.create(
        personal=persona_propia,
        plantilla=plantilla,
        fecha_cese=date(2026, 8, 31),
        motivo_cese='RENUNCIA',
        iniciado_por=admin,
    )
    proceso_ajeno = ProcesoOffboarding.objects.create(
        personal=persona_ajena,
        plantilla=plantilla,
        fecha_cese=date(2026, 8, 31),
        motivo_cese='RENUNCIA',
        iniciado_por=admin,
    )
    paso_ajeno = PasoOffboarding.objects.create(
        proceso=proceso_ajeno,
        orden=1,
        titulo='Devolver activos',
    )
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session.save()
    return client, proceso_propio, proceso_ajeno, paso_ajeno


def test_panel_y_formulario_respetan_empresa_activa(tenant_case):
    client, proceso_propio, proceso_ajeno, _ = tenant_case
    panel = client.get(reverse('offboarding_panel'))
    create = client.get(reverse('offboarding_crear'))

    assert panel.status_code == 200
    process_ids = {row.pk for row in panel.context['procesos']}
    assert proceso_propio.pk in process_ids
    assert proceso_ajeno.pk not in process_ids
    personal_ids = {row.pk for row in create.context['personal_list']}
    assert proceso_propio.personal_id in personal_ids
    assert proceso_ajeno.personal_id not in personal_ids


def test_detalle_y_accion_ajenos_devuelven_404(tenant_case):
    client, _, proceso_ajeno, paso_ajeno = tenant_case
    detail = client.get(reverse('offboarding_detalle', args=[proceso_ajeno.pk]))
    complete = client.post(reverse('paso_off_completar', args=[paso_ajeno.pk]))

    assert detail.status_code == 404
    assert complete.status_code == 404
    paso_ajeno.refresh_from_db()
    assert paso_ajeno.estado == 'PENDIENTE'
