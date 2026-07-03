"""
P14: el calendario unificado es LA respuesta a disponibilidad.
Capa nueva 'ausencia' (papeletas aprobadas) + redirect del calendario
mensual de vacaciones al unificado.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from calendario.views import _build_events
from personal.models import Personal


@pytest.fixture
def personal(db):
    return Personal.objects.create(
        nro_doc='79999999',
        apellidos_nombres='CALENDARIO TEST, EVA',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('2500.00'),
    )


def _papeleta(personal, tipo='DESCANSO_MEDICO', ini=date(2026, 7, 6),
              fin=date(2026, 7, 8), detalle=''):
    from asistencia.models import RegistroPapeleta
    return RegistroPapeleta.objects.create(
        origen='SISTEMA',
        personal=personal,
        dni=personal.nro_doc,
        tipo_permiso=tipo,
        fecha_inicio=ini,
        fecha_fin=fin,
        estado='APROBADA',
        detalle=detalle,
    )


def test_capa_ausencia_muestra_papeletas(personal):
    _papeleta(personal)
    events = _build_events(date(2026, 7, 1), date(2026, 7, 31),
                           tipo_filter='ausencia')
    ausencias = [e for e in events if e['type'] == 'ausencia']
    assert len(ausencias) == 1
    assert 'Descanso Médico' in ausencias[0]['title']
    assert ausencias[0]['personal_name'] == personal.apellidos_nombres


def test_capa_ausencia_excluye_espejo_de_vacaciones(personal):
    """Las papeletas auto-creadas al aprobar una SolicitudVacacion no se
    duplican: esa ausencia ya la pinta la capa 'vacacion'."""
    _papeleta(personal, tipo='VACACIONES',
              detalle='Auto: SolicitudVacacion #7 aprobada')
    events = _build_events(date(2026, 7, 1), date(2026, 7, 31),
                           tipo_filter='ausencia')
    assert [e for e in events if e['type'] == 'ausencia'] == []


def test_capa_ausencia_incluida_por_defecto(personal):
    _papeleta(personal)
    events = _build_events(date(2026, 7, 1), date(2026, 7, 31))
    assert any(e['type'] == 'ausencia' for e in events)


def test_calendario_mensual_vacaciones_redirige_al_unificado(client, db):
    User.objects.create_superuser('admin.cal', 'c@test.pe', 'x')
    client.login(username='admin.cal', password='x')
    resp = client.get('/vacaciones/calendario/')
    assert resp.status_code == 302
    assert resp.url == '/calendario/'
