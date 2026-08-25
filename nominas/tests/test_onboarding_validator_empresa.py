"""El validador de arranque calcula exclusivamente el RUC solicitado."""
from datetime import date
from decimal import Decimal

import pytest

from empresas.models import Empresa
from nominas.models import PeriodoNomina
from nominas.views_onboarding_validator import _check_personal, _check_planilla
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre):
    return Empresa.objects.create(ruc=ruc, razon_social=nombre, activa=True)


def _persona(empresa, documento, estado='Activo'):
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=documento,
        apellidos_nombres=f'PERSONA {documento}',
        cargo='Analista',
        tipo_trab='Empleado',
        estado=estado,
        fecha_alta=date(2025, 1, 1),
        sueldo_base=Decimal('2500.00'),
    )


def test_check_personal_no_mezcla_empresas_y_no_cuenta_cesados_como_activos():
    propia = _empresa('20123456761', 'Empresa propia')
    ajena = _empresa('20123456762', 'Empresa ajena')
    _persona(propia, '71000201')
    _persona(propia, '71000202', estado='Cesado')
    _persona(ajena, '71000203')

    checks = _check_personal(propia)

    resumen = next(item for item in checks if 'trabajadores activos' in item['titulo'])
    assert resumen['titulo'] == '1 trabajadores activos'
    assert 'Total: 2' in resumen['descripcion']


def test_check_planilla_no_usa_periodo_de_otro_ruc():
    propia = _empresa('20123456763', 'Empresa sin planilla')
    ajena = _empresa('20123456764', 'Empresa con planilla')
    PeriodoNomina.objects.create(
        empresa=ajena,
        tipo='REGULAR',
        anio=2026,
        mes=8,
        fecha_inicio=date(2026, 8, 1),
        fecha_fin=date(2026, 8, 31),
        estado='APROBADO',
    )

    checks = _check_planilla(propia)

    assert checks[0]['titulo'] == 'Sin períodos de planilla'
