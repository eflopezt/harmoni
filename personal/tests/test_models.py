"""
Tests para modelos del módulo personal.
"""
import pytest
from personal.models import Area, SubArea, Personal, Roster
from datetime import date


@pytest.mark.django_db
class TestArea:
    def test_crear_area(self):
        area = Area.objects.create(
            nombre='AREA DE PRUEBA',
            descripcion='Descripción de prueba'
        )
        assert area.nombre == 'AREA DE PRUEBA'
        assert area.activa is True
        assert str(area) == 'AREA DE PRUEBA'


@pytest.mark.django_db
class TestSubArea:
    def test_crear_subarea(self):
        area = Area.objects.create(nombre='AREA TEST')
        subarea = SubArea.objects.create(
            nombre='SUBAREA TEST',
            area=area
        )
        assert subarea.nombre == 'SUBAREA TEST'
        assert subarea.area == area
        assert str(subarea) == 'AREA TEST - SUBAREA TEST'


@pytest.mark.django_db
class TestPersonal:
    def test_crear_personal(self):
        area = Area.objects.create(nombre='AREA TEST')
        subarea = SubArea.objects.create(nombre='SUBAREA TEST', area=area)
        
        personal = Personal.objects.create(
            nro_doc='12345678',
            apellidos_nombres='TEST USUARIO',
            cargo='CARGO TEST',
            tipo_trab='Empleado',
            subarea=subarea,
            estado='Activo'
        )
        
        assert personal.nro_doc == '12345678'
        assert personal.esta_activo is True
        assert personal.nombre_completo == 'TEST USUARIO'


@pytest.mark.django_db
class TestRoster:
    def test_crear_roster(self):
        area = Area.objects.create(nombre='AREA TEST')
        subarea = SubArea.objects.create(nombre='SUBAREA TEST', area=area)
        personal = Personal.objects.create(
            nro_doc='12345678',
            apellidos_nombres='TEST USUARIO',
            cargo='CARGO TEST',
            tipo_trab='Empleado',
            subarea=subarea
        )
        
        roster = Roster.objects.create(
            personal=personal,
            fecha=date.today(),
            codigo='D'
        )
        
        assert roster.personal == personal
        assert roster.codigo == 'D'
        assert roster.estado == 'aprobado'  # Default
