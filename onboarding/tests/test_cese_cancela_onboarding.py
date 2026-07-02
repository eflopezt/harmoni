"""
Cesar a un trabajador debe cancelar su onboarding EN_CURSO
(personal/signals.py::_cancelar_onboarding_en_curso).
"""
from datetime import date
from decimal import Decimal

import pytest

from onboarding.models import PlantillaOnboarding, ProcesoOnboarding
from personal.models import Personal


@pytest.fixture
def personal_activo(db):
    return Personal.objects.create(
        nro_doc='74444444',
        apellidos_nombres='NUEVO TEST, CARLOS',
        cargo='Asistente',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2026, 6, 1),
        sueldo_base=Decimal('2500.00'),
    )


@pytest.fixture
def plantilla(db):
    return PlantillaOnboarding.objects.create(
        nombre='Onboarding Estándar',
        aplica_grupo='TODOS',
    )


def _cesar(personal):
    personal.refresh_from_db()
    personal.estado = 'Cesado'
    personal.fecha_cese = date(2026, 7, 1)
    personal.motivo_cese = personal.motivo_cese or ''
    personal.save()


def test_cese_cancela_onboarding_en_curso(personal_activo, plantilla):
    proceso = ProcesoOnboarding.objects.create(
        personal=personal_activo,
        plantilla=plantilla,
        fecha_ingreso=date(2026, 6, 1),
        estado='EN_CURSO',
    )

    _cesar(personal_activo)

    proceso.refresh_from_db()
    assert proceso.estado == 'CANCELADO'


def test_cese_no_toca_onboarding_completado(personal_activo, plantilla):
    proceso = ProcesoOnboarding.objects.create(
        personal=personal_activo,
        plantilla=plantilla,
        fecha_ingreso=date(2026, 6, 1),
        estado='COMPLETADO',
    )

    _cesar(personal_activo)

    proceso.refresh_from_db()
    assert proceso.estado == 'COMPLETADO'


def test_cese_crea_proceso_offboarding(personal_activo):
    """El signal crea el ProcesoOffboarding desde la plantilla activa,
    para cualquier camino de cese (wizard o programático)."""
    from onboarding.models import (
        PasoPlantillaOff, PlantillaOffboarding, ProcesoOffboarding,
    )
    plantilla_off = PlantillaOffboarding.objects.create(
        nombre='Offboarding Estándar', activa=True)
    PasoPlantillaOff.objects.create(
        plantilla=plantilla_off, titulo='Entrega de activos', orden=1)

    personal_activo.estado = 'Cesado'
    personal_activo.fecha_cese = date(2026, 7, 1)
    personal_activo.motivo_cese = 'RENUNCIA'
    personal_activo.save()

    proceso = ProcesoOffboarding.objects.get(personal=personal_activo)
    assert proceso.estado == 'EN_CURSO'
    assert proceso.pasos.count() == 1

    # Idempotente: re-guardar no duplica
    personal_activo.save()
    assert ProcesoOffboarding.objects.filter(
        personal=personal_activo).count() == 1


def test_cese_no_toca_onboarding_de_otro_trabajador(personal_activo, plantilla):
    otro = Personal.objects.create(
        nro_doc='75555555',
        apellidos_nombres='OTRO TEST, MARIA',
        cargo='Asistente',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2026, 6, 1),
        sueldo_base=Decimal('2500.00'),
    )
    proceso_otro = ProcesoOnboarding.objects.create(
        personal=otro,
        plantilla=plantilla,
        fecha_ingreso=date(2026, 6, 1),
        estado='EN_CURSO',
    )

    _cesar(personal_activo)

    proceso_otro.refresh_from_db()
    assert proceso_otro.estado == 'EN_CURSO'
