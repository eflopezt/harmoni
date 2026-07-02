"""
Tests del post-proceso automático de importaciones
(asistencia/services/postproceso.py): faltas automáticas + cruce Tareo-Roster
corriendo solos tras cada importación.
"""
from datetime import date
from decimal import Decimal

import pytest

from asistencia.services.postproceso import postprocesar_importacion


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def importacion(db):
    """Importación de tareo de una semana corta (lun 4 → mié 6 mayo 2026)."""
    from asistencia.models import TareoImportacion
    return TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 5, 4),
        periodo_fin=date(2026, 5, 6),
        archivo_nombre='test.xlsx',
        estado='COMPLETADO',
    )


@pytest.fixture
def personal_staff(db):
    from personal.models import Personal
    return Personal.objects.create(
        nro_doc='71111111',
        apellidos_nombres='STAFF TEST, JUAN',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('3000.00'),
    )


def _tareo(importacion, personal, fecha, codigo='A'):
    from asistencia.models import RegistroTareo
    return RegistroTareo.objects.create(
        importacion=importacion,
        personal=personal,
        dni=personal.nro_doc,
        nombre_archivo=personal.apellidos_nombres,
        grupo=personal.grupo_tareo,
        condicion=personal.condicion,
        fecha=fecha,
        dia_semana=fecha.weekday(),
        codigo_dia=codigo,
        horas_efectivas=Decimal('8'),
        horas_normales=Decimal('8'),
        he_25=Decimal('0'),
        he_35=Decimal('0'),
        he_100=Decimal('0'),
    )


# ═════════════════════════════════════════════════════════════════════════════
# Resolución de período y guards
# ═════════════════════════════════════════════════════════════════════════════


def test_skip_sin_periodo(db):
    """Sin importación ni fechas → skip limpio, sin excepción."""
    res = postprocesar_importacion()
    assert res == {'skipped': 'periodo no determinable'}


def test_skip_importacion_de_faltas_auto(db):
    """La importación de trazabilidad de generar_faltas_auto no se re-procesa."""
    from asistencia.models import TareoImportacion
    imp = TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 5, 4),
        periodo_fin=date(2026, 5, 6),
        archivo_nombre='generar_faltas_auto',
        estado='COMPLETADO',
    )
    res = postprocesar_importacion(imp)
    assert 'skipped' in res


def test_periodo_desde_importacion(importacion, personal_staff):
    res = postprocesar_importacion(importacion)
    assert res['periodo'] == ('2026-05-04', '2026-05-06')


def test_fechas_explicitas_tienen_precedencia(importacion, personal_staff):
    res = postprocesar_importacion(
        importacion, fecha_ini=date(2026, 5, 4), fecha_fin=date(2026, 5, 5))
    assert res['periodo'] == ('2026-05-04', '2026-05-05')


# ═════════════════════════════════════════════════════════════════════════════
# Faltas automáticas + cruce
# ═════════════════════════════════════════════════════════════════════════════


def test_genera_faltas_para_dias_sin_marca(importacion, personal_staff):
    """El staff marcó solo el lunes → mar y mié se persisten como FA."""
    from asistencia.models import RegistroTareo
    _tareo(importacion, personal_staff, date(2026, 5, 4))

    res = postprocesar_importacion(importacion)

    assert res['faltas_creadas'] == 2
    codigos = set(
        RegistroTareo.objects
        .filter(personal=personal_staff,
                fecha__in=[date(2026, 5, 5), date(2026, 5, 6)])
        .values_list('codigo_dia', flat=True)
    )
    assert codigos == {'FA'}


def test_puebla_cruce_tareo_roster(importacion, personal_staff):
    """Con roster T y marca real, el cruce queda COINCIDE; la falta contra
    roster T queda AUSENTE_PROYECTADO."""
    from asistencia.models import CruceTareoRoster
    from personal.models import Roster

    for d in (4, 5, 6):
        Roster.objects.create(
            personal=personal_staff, fecha=date(2026, 5, d), codigo='T')
    _tareo(importacion, personal_staff, date(2026, 5, 4))

    res = postprocesar_importacion(importacion)

    assert res['cruce'].get('COINCIDE', 0) >= 1
    assert res['cruce'].get('AUSENTE_PROYECTADO', 0) == 2
    cruce_lunes = CruceTareoRoster.objects.get(
        registro_tareo__personal=personal_staff,
        registro_tareo__fecha=date(2026, 5, 4),
    )
    assert cruce_lunes.variacion == 'COINCIDE'
    assert cruce_lunes.roster_codigo == 'T'


def test_no_toca_registros_existentes(importacion, personal_staff):
    """Idempotencia heredada: un segundo post-proceso no crea nada nuevo."""
    _tareo(importacion, personal_staff, date(2026, 5, 4))
    primero = postprocesar_importacion(importacion)
    segundo = postprocesar_importacion(importacion)
    assert primero['faltas_creadas'] == 2
    assert segundo['faltas_creadas'] == 0


def test_papeleta_aprobada_gana_sobre_falta(importacion, personal_staff):
    """Día cubierto por papeleta aprobada NO se convierte en FA."""
    from asistencia.models import RegistroPapeleta, RegistroTareo
    RegistroPapeleta.objects.create(
        personal=personal_staff,
        dni=personal_staff.nro_doc,
        nombre_archivo=personal_staff.apellidos_nombres,
        tipo_permiso='VACACIONES',
        fecha_inicio=date(2026, 5, 5),
        fecha_fin=date(2026, 5, 6),
        estado='APROBADA',
    )
    _tareo(importacion, personal_staff, date(2026, 5, 4))

    postprocesar_importacion(importacion)

    fa = RegistroTareo.objects.filter(
        personal=personal_staff, codigo_dia='FA',
        fecha__in=[date(2026, 5, 5), date(2026, 5, 6)],
    )
    assert not fa.exists()


def test_best_effort_no_levanta_excepcion(importacion, personal_staff, monkeypatch):
    """Si el cruce revienta, el post-proceso lo reporta pero no explota."""
    import asistencia.services.postproceso as pp

    def _boom(*a, **kw):
        raise RuntimeError('boom')

    monkeypatch.setattr(
        'asistencia.services.cruce_roster.poblar_cruce', _boom)
    res = postprocesar_importacion(importacion)
    assert 'cruce_error' in res
    assert res['faltas_creadas'] is not None
