"""
Validador de onboarding — conteo "sin PLAME".

Regla: solo cuentan como "sin PLAME" los conceptos que SÍ son líneas del PLAME
0601 del trabajador (ingresos y descuentos). Los aportes del empleador
(EsSalud/SCTR, tipo=APORTE_EMPLEADOR) y las provisiones internas (prov-gratif/
prov-cts, subtipo=PROVISION) NO se declaran como concepto del trabajador, así que
no deben disparar el warn aunque les falte código PLAME.
"""
import pytest

from nominas.models import ConceptoRemunerativo
from nominas.views_onboarding_validator import _check_conceptos

pytestmark = pytest.mark.django_db


def _concepto(codigo, tipo='INGRESO', subtipo='REMUNERATIVO', plame=''):
    return ConceptoRemunerativo.objects.create(
        codigo=codigo, nombre=codigo, tipo=tipo, subtipo=subtipo,
        codigo_plame=plame, activo=True,
    )


def _warn_sin_plame(checks):
    return next((c for c in checks if 'sin PLAME' in c['titulo']), None)


def test_aportes_empleador_y_provisiones_no_cuentan_como_sin_plame():
    # Aporte del empleador y provisión SIN código PLAME → NO deben flaguearse.
    _concepto('essalud', tipo='APORTE_EMPLEADOR')
    _concepto('sctr-salud', tipo='APORTE_EMPLEADOR')
    _concepto('prov-cts', tipo='INGRESO', subtipo='PROVISION')
    _concepto('prov-gratificacion', tipo='INGRESO', subtipo='PROVISION')
    # Un ingreso del trabajador CON código → tampoco flaguea.
    _concepto('sueldo-basico', tipo='INGRESO', plame='0121')

    checks = _check_conceptos()
    assert _warn_sin_plame(checks) is None, \
        'Aportes del empleador/provisiones no deben contar como "sin PLAME"'


def test_ingreso_o_descuento_del_trabajador_sin_plame_si_flaguea():
    # Un descuento del trabajador sin código PLAME SÍ es un problema real.
    _concepto('otros-descuentos', tipo='DESCUENTO', plame='')
    _concepto('sueldo-basico', tipo='INGRESO', plame='0121')

    checks = _check_conceptos()
    warn = _warn_sin_plame(checks)
    assert warn is not None and warn['severidad'] == 'warn', \
        'Un descuento del trabajador sin PLAME debe seguir flagueándose'
