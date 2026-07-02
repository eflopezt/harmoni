"""
Paso GENERAR_CARGA_S10 del wizard de cierre: ya no es informativo,
genera el archivo de verdad y expone la URL de descarga (P11).
"""
from datetime import date
from decimal import Decimal

import pytest

from cierre.engine import _paso_generar_carga_s10
from cierre.models import PeriodoCierre


@pytest.fixture
def periodo(db):
    return PeriodoCierre.objects.create(anio=2026, mes=5)


@pytest.fixture
def personal_rco(db):
    from personal.models import Personal
    return Personal.objects.create(
        nro_doc='77777777',
        apellidos_nombres='OBRERO S10, JOSE',
        cargo='Operario',
        tipo_trab='Obrero',
        estado='Activo',
        grupo_tareo='RCO',
        condicion='FORANEO',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('1800.00'),
    )


def test_paso_s10_sin_datos_advierte(periodo):
    """Sin tareo RCO en el período, el paso genera 0 filas y ADVIERTE
    (antes devolvía OK siempre sin generar nada)."""
    res = _paso_generar_carga_s10(periodo)
    assert res['estado'] == 'ADVERTENCIA'
    assert res['datos']['filas'] == 0
    assert 'descarga_url' in res['datos']


def test_paso_s10_genera_archivo_con_datos(periodo, personal_rco):
    from asistencia.models import TareoImportacion, RegistroTareo

    imp = TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 4, 21),
        periodo_fin=date(2026, 5, 20),
        archivo_nombre='s10_test.xlsx',
        estado='COMPLETADO',
    )
    RegistroTareo.objects.create(
        importacion=imp,
        personal=personal_rco,
        dni=personal_rco.nro_doc,
        nombre_archivo=personal_rco.apellidos_nombres,
        grupo='RCO',
        condicion='FORANEO',
        fecha=date(2026, 5, 5),
        dia_semana=1,
        codigo_dia='A',
        horas_efectivas=Decimal('11'),
        horas_normales=Decimal('11'),
        he_25=Decimal('2'),
        he_35=Decimal('1'),
        he_100=Decimal('0'),
    )

    res = _paso_generar_carga_s10(periodo)

    assert res['estado'] == 'OK'
    assert res['datos']['filas'] == 1
    assert res['datos']['descarga_url'].endswith('?anio=2026&mes=5')
    assert res['datos']['he_total'] == pytest.approx(3.0)
