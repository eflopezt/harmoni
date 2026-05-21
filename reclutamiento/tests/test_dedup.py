"""
Tests para detector de duplicados de postulaciones.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from personal.models import Area, SubArea
from reclutamiento.models import Vacante, Postulacion, EtapaPipeline
from reclutamiento.dedup import (
    buscar_duplicados,
    _normalize_phone,
    _strip_acentos,
    _levenshtein,
)


@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Salón")


@pytest.fixture
def vacante(db, area):
    return Vacante.objects.create(
        titulo="Mesero Senior",
        descripcion="Test vacante",
        area=area,
        estado="PUBLICADA",
    )


@pytest.fixture
def etapa(db):
    return EtapaPipeline.objects.create(
        nombre="Recibido",
        orden=1,
    )


def crear_postulacion(vacante, etapa, *, email='', telefono='', nombre=''):
    return Postulacion.objects.create(
        vacante=vacante,
        etapa=etapa,
        nombre_completo=nombre,
        email=email,
        telefono=telefono,
    )


class TestHelpers:
    def test_normalize_phone_solo_digitos(self):
        assert _normalize_phone('+51 987-654-321') == '987654321'

    def test_normalize_phone_vacio(self):
        assert _normalize_phone('') == ''

    def test_normalize_phone_ultimos_9(self):
        assert _normalize_phone('00519999999999') == '999999999'

    def test_strip_acentos(self):
        assert _strip_acentos('Pérez') == 'Perez'
        assert _strip_acentos('González') == 'Gonzalez'

    def test_levenshtein(self):
        assert _levenshtein('hola', 'hola') == 0
        assert _levenshtein('Pérez', 'Perez') == 1  # solo 1 char distinto (é vs e)
        assert _levenshtein('Quispe', 'Quispi') == 1


class TestBuscarDuplicados:
    def test_email_exacto(self, vacante, etapa):
        p1 = crear_postulacion(vacante, etapa,
                                email='maria@empresa.com', nombre='MARIA Q')
        # Buscar por mismo email
        dups = buscar_duplicados(email='maria@empresa.com')
        assert len(dups) == 1
        assert dups[0][0].pk == p1.pk
        assert 'Email' in dups[0][1]
        assert dups[0][2] == 95

    def test_email_case_insensitive(self, vacante, etapa):
        crear_postulacion(vacante, etapa,
                          email='MARIA@empresa.COM', nombre='MARIA Q')
        dups = buscar_duplicados(email='maria@empresa.com')
        assert len(dups) == 1

    def test_telefono_coincide(self, vacante, etapa):
        p1 = crear_postulacion(vacante, etapa,
                                telefono='987654321', nombre='M Q')
        # Buscar con formato distinto pero mismos 9 dígitos
        dups = buscar_duplicados(telefono='+51 987-654-321')
        assert len(dups) == 1
        assert 'Teléfono' in dups[0][1]
        assert dups[0][2] == 90

    def test_nombre_fuzzy_match(self, vacante, etapa):
        crear_postulacion(vacante, etapa,
                          nombre='MARIA QUISPE LOPEZ')
        # Misma persona con tilde
        dups = buscar_duplicados(nombre_completo='MARÍA QUISPE LÓPEZ')
        # Debe encontrar similitud >= 85% (tildes ignoradas)
        assert len(dups) >= 1
        assert dups[0][2] >= 60

    def test_exclude_id(self, vacante, etapa):
        p1 = crear_postulacion(vacante, etapa,
                                email='test@test.com', nombre='TEST')
        # Excluyendo el mismo id, no debe encontrar nada
        dups = buscar_duplicados(email='test@test.com', exclude_id=p1.pk)
        assert len(dups) == 0

    def test_multiples_matches_orden_por_score(self, vacante, etapa):
        # Misma persona con email Y teléfono coincidiendo
        p1 = crear_postulacion(
            vacante, etapa,
            email='test@test.com',
            telefono='987654321',
            nombre='ABC',
        )
        # Búsqueda con ambos campos coincidiendo
        dups = buscar_duplicados(
            email='test@test.com',
            telefono='987654321',
        )
        # Mismo candidato encontrado solo una vez (seen set)
        assert len(dups) == 1
        # Y el motivo es el de mayor score (Email = 95)
        assert dups[0][2] == 95

    def test_sin_data_no_devuelve_nada(self, vacante, etapa):
        crear_postulacion(vacante, etapa, email='x@x.com', nombre='X')
        dups = buscar_duplicados()
        assert dups == []
