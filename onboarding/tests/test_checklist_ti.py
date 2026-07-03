"""
Checklist TI del onboarding (provisioning mínimo, rec. 18 del análisis).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from onboarding.models import ChecklistTI, PlantillaOnboarding, ProcesoOnboarding
from personal.models import ActivoAsignado, Personal


@pytest.fixture
def admin_client(client, db):
    User.objects.create_superuser('admin.ti', 'ti@test.pe', 'x')
    client.login(username='admin.ti', password='x')
    return client


@pytest.fixture
def proceso(db):
    personal = Personal.objects.create(
        nro_doc='72220001',
        apellidos_nombres='NUEVO TI, PABLO',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2026, 7, 1),
        sueldo_base=Decimal('2500.00'),
    )
    plantilla = PlantillaOnboarding.objects.create(
        nombre='Onboarding TI Test', aplica_grupo='TODOS')
    return ProcesoOnboarding.objects.create(
        personal=personal, plantilla=plantilla,
        fecha_ingreso=date(2026, 7, 1), estado='EN_CURSO',
    )


def test_detalle_crea_checklist_vacio(admin_client, proceso):
    resp = admin_client.get(reverse('onboarding_detalle', args=[proceso.pk]))
    assert resp.status_code == 200
    chk = ChecklistTI.objects.get(proceso=proceso)
    assert chk.avance == 0
    assert chk.completado is False


def test_guardar_checklist_actualiza_avance(admin_client, proceso):
    activo = ActivoAsignado.objects.create(
        personal=proceso.personal, tipo='LAPTOP',
        descripcion='Laptop Dell 5520', fecha_asignacion=date(2026, 7, 1),
    )
    resp = admin_client.post(
        reverse('checklist_ti_guardar', args=[proceso.pk]), {
            'correo_creado': '1',
            'correo_corporativo': 'pablo@empresa.pe',
            'usuario_ad_creado': '1',
            'usuario_ad': 'EMPRESA\\pnuevo',
            'equipo_entregado': '1',
            'equipo_asignado': str(activo.pk),
            'accesos_sistemas': 'ERP, correo, carpeta compartida',
        })
    assert resp.status_code == 302

    chk = ChecklistTI.objects.get(proceso=proceso)
    assert chk.completado is True
    assert chk.avance == 75          # falta fotocheck
    assert chk.equipo_asignado == activo
    assert chk.correo_corporativo == 'pablo@empresa.pe'


def test_no_vincula_activo_de_otro_trabajador(admin_client, proceso):
    otro = Personal.objects.create(
        nro_doc='72220002',
        apellidos_nombres='OTRO TI, LUZ',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2026, 7, 1),
        sueldo_base=Decimal('2500.00'),
    )
    activo_ajeno = ActivoAsignado.objects.create(
        personal=otro, tipo='CELULAR',
        descripcion='iPhone', fecha_asignacion=date(2026, 7, 1),
    )
    admin_client.post(
        reverse('checklist_ti_guardar', args=[proceso.pk]),
        {'equipo_asignado': str(activo_ajeno.pk)},
    )
    chk = ChecklistTI.objects.get(proceso=proceso)
    assert chk.equipo_asignado is None
