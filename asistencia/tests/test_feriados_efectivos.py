"""
feriados_efectivos: FeriadoCalendario ± traslados de CompensacionFeriado (P9).
El TareoProcessor y generar_faltas_auto deben respetar los traslados sin
comandos hardcodeados por año.
"""
from datetime import date

import pytest

from asistencia.models import CompensacionFeriado, FeriadoCalendario
from asistencia.services.feriados import feriados_efectivos


@pytest.fixture
def feriado_jueves_santo(db):
    return FeriadoCalendario.objects.create(
        fecha=date(2026, 4, 2), nombre='Jueves Santo',
        tipo='NACIONAL', activo=True,
    )


def test_sin_compensaciones_devuelve_feriados(feriado_jueves_santo):
    assert feriados_efectivos() == {date(2026, 4, 2)}


def test_traslado_mueve_el_feriado(feriado_jueves_santo):
    CompensacionFeriado.objects.create(
        fecha_feriado=date(2026, 4, 2),
        fecha_compensada=date(2026, 4, 4),
        descripcion='Traslado D.S.',
        activo=True,
    )
    efectivos = feriados_efectivos()
    assert date(2026, 4, 2) not in efectivos   # se trabaja normal
    assert date(2026, 4, 4) in efectivos       # toma el tratamiento


def test_compensacion_inactiva_se_ignora(feriado_jueves_santo):
    CompensacionFeriado.objects.create(
        fecha_feriado=date(2026, 4, 2),
        fecha_compensada=date(2026, 4, 4),
        activo=False,
    )
    assert feriados_efectivos() == {date(2026, 4, 2)}


def test_rango_filtra_feriados_y_traslados(feriado_jueves_santo):
    FeriadoCalendario.objects.create(
        fecha=date(2026, 5, 1), nombre='Día del Trabajo',
        tipo='NACIONAL', activo=True,
    )
    CompensacionFeriado.objects.create(
        fecha_feriado=date(2026, 4, 2),
        fecha_compensada=date(2026, 4, 4),
        activo=True,
    )
    # Rango solo abril
    efectivos = feriados_efectivos(date(2026, 4, 1), date(2026, 4, 30))
    assert efectivos == {date(2026, 4, 4)}
    # Rango solo mayo: el traslado de abril no entra
    efectivos = feriados_efectivos(date(2026, 5, 1), date(2026, 5, 31))
    assert efectivos == {date(2026, 5, 1)}


def test_processor_usa_traslados(db, feriado_jueves_santo):
    """El TareoProcessor carga los feriados vía el helper."""
    from asistencia.models import TareoImportacion
    from asistencia.services.processor import TareoProcessor

    CompensacionFeriado.objects.create(
        fecha_feriado=date(2026, 4, 2),
        fecha_compensada=date(2026, 4, 4),
        activo=True,
    )
    imp = TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 4, 1),
        periodo_fin=date(2026, 4, 30),
        archivo_nombre='t.xlsx',
        estado='PENDIENTE',
    )
    proc = TareoProcessor(imp)
    assert date(2026, 4, 2) not in proc._feriados
    assert date(2026, 4, 4) in proc._feriados
