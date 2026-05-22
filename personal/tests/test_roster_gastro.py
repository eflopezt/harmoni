"""
Tests para Roster Quincenal Gastronomico.
"""
from datetime import date, time, timedelta

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.urls import reverse

from personal.models import (
    Area,
    AsignacionRosterQuincena,
    Personal,
    SubArea,
    TurnoGastronomia,
)
from personal.roster_validator import quincena_rango, validar_roster_quincena


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser('admin_rg', 'a@a.com', 'pass1234')


@pytest.fixture
def persona(db):
    area = Area.objects.create(nombre='Gastro Test')
    sub = SubArea.objects.create(nombre='Cocina', area=area)
    return Personal.objects.create(
        nro_doc='99999999',
        apellidos_nombres='COCINERO TEST',
        cargo='Cocinero',
        tipo_trab='Empleado',
        subarea=sub,
        estado='Activo',
    )


@pytest.fixture
def turno_alm(db):
    return TurnoGastronomia.objects.create(
        codigo='ALM', nombre='Almuerzo',
        hora_entrada=time(10, 0), hora_salida=time(18, 0),
        color='#0f766e',
    )


@pytest.mark.django_db
class TestModeloAsignacion:
    def test_crear_asignacion(self, persona, turno_alm):
        a = AsignacionRosterQuincena.objects.create(
            personal=persona, fecha=date(2026, 6, 1), turno=turno_alm,
        )
        assert a.id is not None
        assert not a.es_libre
        assert str(a).endswith('ALM')

    def test_asignacion_libre(self, persona):
        a = AsignacionRosterQuincena.objects.create(
            personal=persona, fecha=date(2026, 6, 1), turno=None,
        )
        assert a.es_libre

    def test_unique_personal_fecha(self, persona, turno_alm):
        AsignacionRosterQuincena.objects.create(
            personal=persona, fecha=date(2026, 6, 1), turno=turno_alm,
        )
        with pytest.raises(IntegrityError):
            AsignacionRosterQuincena.objects.create(
                personal=persona, fecha=date(2026, 6, 1), turno=None,
            )


@pytest.mark.django_db
class TestValidador:
    def test_validacion_sin_asignaciones(self, persona):
        # Sin asignaciones: cada dia se asume trabajado -> error (no hay descansos)
        res = validar_roster_quincena(
            persona, date(2026, 6, 1), date(2026, 6, 15),
        )
        assert res['valido'] is False
        assert len(res['errores']) > 0

    def test_validacion_con_descansos_cada_7d(self, persona, turno_alm):
        # 14 dias: 1 libre cada 7, 6 trabajados
        f0 = date(2026, 6, 1)
        for i in range(14):
            f = f0 + timedelta(days=i)
            turno = None if i % 7 == 0 else turno_alm
            AsignacionRosterQuincena.objects.create(
                personal=persona, fecha=f, turno=turno,
            )
        res = validar_roster_quincena(persona, f0, f0 + timedelta(days=13))
        assert res['valido'] is True, res['errores']

    def test_validacion_detecta_7_consecutivos(self, persona, turno_alm):
        # 8 dias seguidos trabajados -> error
        f0 = date(2026, 6, 1)
        for i in range(8):
            AsignacionRosterQuincena.objects.create(
                personal=persona, fecha=f0 + timedelta(days=i), turno=turno_alm,
            )
        res = validar_roster_quincena(persona, f0, f0 + timedelta(days=7))
        assert res['valido'] is False
        assert any('consecutivos' in e['mensaje'].lower()
                   or 'consecut' in e['mensaje'].lower()
                   or '7' in e['mensaje']
                   for e in res['errores'])

    def test_quincena_rango_primera(self):
        ini, fin, mes, sq, anio = quincena_rango(2026, 1)
        assert ini == date(2026, 1, 1)
        assert fin == date(2026, 1, 15)
        assert mes == 1
        assert sq == 1

    def test_quincena_rango_segunda(self):
        ini, fin, mes, sq, _ = quincena_rango(2026, 2)
        assert ini == date(2026, 1, 16)
        assert fin == date(2026, 1, 31)
        assert sq == 2


@pytest.mark.django_db
class TestVistas:
    def test_grid_200(self, client, admin_user, persona, turno_alm):
        client.force_login(admin_user)
        url = reverse('roster_gastro_grid') + '?anio=2026&quincena=11'  # junio q1
        resp = client.get(url)
        assert resp.status_code == 200
        assert b'Roster Quincenal Gastronomico' in resp.content

    def test_asignar_ajax(self, client, admin_user, persona, turno_alm):
        client.force_login(admin_user)
        url = reverse('roster_gastro_asignar')
        resp = client.post(
            url,
            data={
                'personal_id': persona.id,
                'fecha': '2026-06-01',
                'turno_id': turno_alm.id,
            },
            content_type='application/json',
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['success'] is True
        assert AsignacionRosterQuincena.objects.filter(
            personal=persona, fecha=date(2026, 6, 1)
        ).exists()

    def test_asignar_libre(self, client, admin_user, persona):
        client.force_login(admin_user)
        url = reverse('roster_gastro_asignar')
        resp = client.post(
            url,
            data={
                'personal_id': persona.id,
                'fecha': '2026-06-01',
                'turno_id': 'libre',
            },
            content_type='application/json',
        )
        assert resp.status_code == 200
        a = AsignacionRosterQuincena.objects.get(
            personal=persona, fecha=date(2026, 6, 1)
        )
        assert a.turno is None

    def test_bulk_assign(self, client, admin_user, persona, turno_alm):
        client.force_login(admin_user)
        url = reverse('roster_gastro_asignar_bulk')
        resp = client.post(
            url,
            data={
                'personal_ids': [persona.id],
                'fecha_inicio': '2026-06-01',
                'fecha_fin': '2026-06-05',
                'turno_id': turno_alm.id,
                'solo_vacios': True,
            },
            content_type='application/json',
        )
        assert resp.status_code == 200
        assert resp.json()['success'] is True
        assert AsignacionRosterQuincena.objects.filter(
            personal=persona, fecha__range=(date(2026, 6, 1), date(2026, 6, 5))
        ).count() == 5

    def test_pdf_200(self, client, admin_user, persona, turno_alm):
        client.force_login(admin_user)
        # Asegurar asignacion para que el PDF tenga contenido
        AsignacionRosterQuincena.objects.create(
            personal=persona, fecha=date(2026, 6, 1), turno=turno_alm,
        )
        url = reverse('roster_gastro_pdf') + '?anio=2026&quincena=11'
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content[:4] == b'%PDF'
