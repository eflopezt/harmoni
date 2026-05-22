"""
Tests para el módulo Evaluaciones 360°.
Cubre: creación, respuestas, agregación, gaps, vistas y PDF.
"""
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from personal.models import Area, SubArea, Personal
from evaluaciones.models import (
    COMPETENCIAS_GASTRO_360,
    Competencia,
    Evaluacion360,
    ParticipanteEvaluacion360,
    RespuestaCompetencia360,
)


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def area():
    return Area.objects.create(nombre='COCINA')


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre='SALON', area=area)


@pytest.fixture
def evaluado(subarea):
    return Personal.objects.create(
        nro_doc='10000001',
        apellidos_nombres='GARCIA LOPEZ JOSE',
        cargo='Supervisor de Servicio',
        tipo_trab='Empleado',
        subarea=subarea,
        estado='Activo',
    )


@pytest.fixture
def manager(subarea):
    return Personal.objects.create(
        nro_doc='10000002',
        apellidos_nombres='PEREZ DIAZ MARIA',
        cargo='Gerente Operaciones',
        tipo_trab='Empleado',
        subarea=subarea,
        estado='Activo',
    )


@pytest.fixture
def peer(subarea):
    return Personal.objects.create(
        nro_doc='10000003',
        apellidos_nombres='RUIZ TORRES PEDRO',
        cargo='Supervisor de Servicio',
        tipo_trab='Empleado',
        subarea=subarea,
        estado='Activo',
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username='admin360', password='test1234', email='a@a.com')


@pytest.fixture
def evaluacion(evaluado):
    return Evaluacion360.objects.create(
        personal_evaluado=evaluado,
        periodo='2026-Q2',
        estado='EN_CURSO',
    )


# ── Modelos: creación + cálculos ──────────────────────────────

@pytest.mark.django_db
def test_crear_evaluacion_360_basica(evaluado):
    eval360 = Evaluacion360.objects.create(
        personal_evaluado=evaluado,
        periodo='2026-Q1',
    )
    assert eval360.pk is not None
    assert eval360.estado == 'BORRADOR'
    assert eval360.total_participantes == 0
    assert eval360.porcentaje_avance == 0


@pytest.mark.django_db
def test_participante_calcula_puntaje_global(evaluacion, manager):
    participante = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
    )
    # 3 competencias con puntajes 4, 3, 5 → promedio 4.00
    for cod, label, p in [
        ('liderazgo', 'Liderazgo', Decimal('4.0')),
        ('equipo',    'Trabajo en Equipo', Decimal('3.0')),
        ('servicio',  'Calidad de Servicio', Decimal('5.0')),
    ]:
        RespuestaCompetencia360.objects.create(
            participante=participante,
            competencia_codigo=cod,
            competencia_label=label,
            puntaje=p,
        )
    promedio = participante.calcular_puntaje_global()
    assert promedio == Decimal('4.00')
    participante.refresh_from_db()
    assert participante.puntaje_global == Decimal('4.00')


@pytest.mark.django_db
def test_matriz_comparativa_promedia_por_tipo(evaluacion, evaluado, manager, peer):
    # Auto
    a = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='AUTOEVALUACION', personal_evaluador=evaluado,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=a, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('5.0'),
    )
    # Manager
    m = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=m, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('3.0'),
    )
    # Peer
    p = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='PEER', personal_evaluador=peer,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=p, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('4.0'),
    )

    matriz = evaluacion.matriz_comparativa()
    assert 'liderazgo' in matriz
    promedios = matriz['liderazgo']['promedios']
    assert promedios['AUTOEVALUACION'] == Decimal('5.00')
    assert promedios['MANAGER'] == Decimal('3.00')
    assert promedios['PEER'] == Decimal('4.00')


@pytest.mark.django_db
def test_detectar_gap_auto_vs_manager(evaluacion, evaluado, manager):
    a = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='AUTOEVALUACION', personal_evaluador=evaluado,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=a, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('5.0'),
    )
    m = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=m, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('2.5'),
    )
    gaps = evaluacion.gaps_auto_manager()
    assert len(gaps) == 1
    g = gaps[0]
    assert g['codigo'] == 'liderazgo'
    assert g['gap'] == Decimal('2.50')
    assert g['severidad'] == 'critical'


# ── Vistas ────────────────────────────────────────────────────

@pytest.mark.django_db
def test_panel_360_responde_200(admin_user, evaluacion):
    client = Client()
    client.force_login(admin_user)
    resp = client.get(reverse('evaluacion_360_panel'))
    assert resp.status_code == 200
    assert b'Evaluaciones 360' in resp.content


@pytest.mark.django_db
def test_detalle_360_responde_200(admin_user, evaluacion, evaluado, manager):
    # Cargar algo de data
    p = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
        completada=True,
    )
    RespuestaCompetencia360.objects.create(
        participante=p, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('4.0'),
    )

    client = Client()
    client.force_login(admin_user)
    resp = client.get(reverse('evaluacion_360_detalle', args=[evaluacion.pk]))
    assert resp.status_code == 200
    assert b'Liderazgo' in resp.content


@pytest.mark.django_db
def test_pdf_360_genera_bytes(admin_user, evaluacion, manager):
    p = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
        completada=True, puntaje_global=Decimal('4.00'),
    )
    RespuestaCompetencia360.objects.create(
        participante=p, competencia_codigo='liderazgo',
        competencia_label='Liderazgo', puntaje=Decimal('4.0'),
    )
    client = Client()
    client.force_login(admin_user)
    resp = client.get(reverse('evaluacion_360_pdf', args=[evaluacion.pk]))
    assert resp.status_code == 200
    assert resp['Content-Type'] == 'application/pdf'
    # Es un PDF válido (header)
    assert resp.content[:4] == b'%PDF'


@pytest.mark.django_db
def test_responder_360_guarda_respuestas(admin_user, evaluacion, manager):
    participante = ParticipanteEvaluacion360.objects.create(
        evaluacion=evaluacion, tipo='MANAGER', personal_evaluador=manager,
    )
    client = Client()
    client.force_login(admin_user)
    url = reverse('evaluacion_360_responder', args=[evaluacion.pk, participante.pk])

    post_data = {
        'fortalezas': 'Liderazgo claro',
        'areas_mejora': 'Comunicación',
        'comentario_general': 'Buen trabajo',
    }
    # Usa una de las competencias gastro siempre disponibles
    for cod, _ in COMPETENCIAS_GASTRO_360[:3]:
        post_data[f'puntaje_{cod}'] = '4'
        post_data[f'comentario_{cod}'] = ''

    resp = client.post(url, post_data)
    assert resp.status_code in (302, 200)

    participante.refresh_from_db()
    assert participante.completada is True
    assert participante.respuestas.count() >= 3
    assert participante.puntaje_global is not None
