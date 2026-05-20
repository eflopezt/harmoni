"""
Tests para modelos del modulo reclutamiento y seleccion.
Valida vacantes, pipeline, postulaciones, notas y entrevistas.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from personal.models import Area
from reclutamiento.models import (
    Vacante, EtapaPipeline, Postulacion,
    NotaPostulacion, EntrevistaPrograma,
)


@pytest.fixture
def area():
    return Area.objects.create(nombre='INGENIERIA')


@pytest.fixture
def user():
    return User.objects.create_user(username='reclutador', password='test1234')


@pytest.fixture
def vacante(area, user):
    return Vacante.objects.create(
        titulo='Ingeniero Civil Senior',
        area=area,
        descripcion='Se requiere ingeniero con experiencia en obras civiles.',
        experiencia_minima=5,
        educacion_minima='UNIVERSITARIO',
        tipo_contrato='INDETERMINADO',
        salario_min=Decimal('5000.00'),
        salario_max=Decimal('8000.00'),
        moneda='PEN',
        prioridad='ALTA',
        fecha_publicacion=date.today(),
        fecha_limite=date.today() + timedelta(days=30),
        responsable=user,
    )


@pytest.fixture
def etapa_recepcion():
    return EtapaPipeline.objects.create(
        nombre='Recepción CV', codigo='recepcion-cv', orden=1,
    )


@pytest.fixture
def etapa_entrevista():
    return EtapaPipeline.objects.create(
        nombre='Entrevista', codigo='entrevista', orden=2,
    )


@pytest.fixture
def postulacion(vacante, etapa_recepcion):
    return Postulacion.objects.create(
        vacante=vacante,
        etapa=etapa_recepcion,
        nombre_completo='MARTINEZ PEREZ CARLOS',
        email='carlos@test.com',
        telefono='987654321',
        experiencia_anos=6,
        educacion='UNIVERSITARIO',
        salario_pretendido=Decimal('7000.00'),
        fuente='LINKEDIN',
    )


# ──────────────────────────────────────────────────────────────
# Vacante
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestVacante:

    def test_crear_vacante_defaults(self):
        v = Vacante.objects.create(titulo='Asistente')
        assert v.estado == 'BORRADOR'
        assert v.prioridad == 'MEDIA'
        assert v.moneda == 'PEN'
        assert v.educacion_minima == 'NO_REQUERIDO'

    def test_str(self, vacante):
        s = str(vacante)
        assert 'Ingeniero Civil Senior' in s
        assert 'Borrador' in s  # default estado

    def test_total_postulaciones_vacio(self, vacante):
        assert vacante.total_postulaciones == 0

    def test_total_postulaciones_con_candidatos(self, vacante, postulacion):
        assert vacante.total_postulaciones == 1

    def test_postulaciones_activas(self, vacante, etapa_recepcion):
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='Candidato A', estado='ACTIVA',
        )
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='Candidato B', estado='DESCARTADA',
        )
        assert vacante.postulaciones_activas == 1

    def test_esta_vencida_con_fecha_futura(self, vacante):
        assert vacante.esta_vencida is False

    def test_esta_vencida_con_fecha_pasada(self, vacante):
        vacante.fecha_limite = date.today() - timedelta(days=1)
        vacante.save()
        assert vacante.esta_vencida is True

    def test_esta_vencida_sin_fecha_limite(self):
        v = Vacante.objects.create(titulo='Sin fecha limite')
        assert v.esta_vencida is False

    def test_salario_min_no_negativo(self):
        v = Vacante(titulo='Test', salario_min=Decimal('-100.00'))
        with pytest.raises(ValidationError):
            v.full_clean()

    def test_postulaciones_por_etapa(self, vacante, etapa_recepcion, etapa_entrevista):
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='A', estado='ACTIVA',
        )
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='B', estado='ACTIVA',
        )
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_entrevista,
            nombre_completo='C', estado='ACTIVA',
        )
        por_etapa = vacante.postulaciones_por_etapa
        assert por_etapa[etapa_recepcion.id] == 2
        assert por_etapa[etapa_entrevista.id] == 1


# ──────────────────────────────────────────────────────────────
# EtapaPipeline
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEtapaPipeline:

    def test_crear_etapa(self, etapa_recepcion):
        assert etapa_recepcion.activa is True
        assert etapa_recepcion.eliminable is True
        assert str(etapa_recepcion) == 'Recepción CV'

    def test_codigo_unique(self, etapa_recepcion):
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            EtapaPipeline.objects.create(
                nombre='Otra', codigo='recepcion-cv', orden=5,
            )

    def test_ordering(self, etapa_recepcion, etapa_entrevista):
        etapas = list(EtapaPipeline.objects.all())
        assert etapas[0].orden < etapas[1].orden

    def test_total_postulaciones_activas(self, etapa_recepcion, vacante):
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='Activo', estado='ACTIVA',
        )
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa_recepcion,
            nombre_completo='Descartado', estado='DESCARTADA',
        )
        assert etapa_recepcion.total_postulaciones == 1


# ──────────────────────────────────────────────────────────────
# Postulacion
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPostulacion:

    def test_crear_postulacion(self, postulacion):
        assert postulacion.estado == 'ACTIVA'
        assert postulacion.fuente == 'LINKEDIN'
        assert postulacion.experiencia_anos == 6

    def test_str(self, postulacion):
        s = str(postulacion)
        assert 'MARTINEZ PEREZ CARLOS' in s
        assert 'Ingeniero Civil Senior' in s

    def test_dias_en_proceso(self, postulacion):
        # Recien creado, deberia ser 0 dias
        assert postulacion.dias_en_proceso == 0

    def test_mover_etapa(self, postulacion, etapa_entrevista):
        """Simula mover un candidato de una etapa a otra en el pipeline."""
        postulacion.etapa = etapa_entrevista
        postulacion.save()
        postulacion.refresh_from_db()
        assert postulacion.etapa == etapa_entrevista

    def test_descartar_postulacion(self, postulacion):
        postulacion.estado = 'DESCARTADA'
        postulacion.save()
        postulacion.refresh_from_db()
        assert postulacion.estado == 'DESCARTADA'


# ──────────────────────────────────────────────────────────────
# NotaPostulacion
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNotaPostulacion:

    def test_crear_nota(self, postulacion, user):
        nota = NotaPostulacion.objects.create(
            postulacion=postulacion,
            autor=user,
            texto='Buen perfil, cumple requisitos técnicos.',
            tipo='NOTA',
        )
        assert 'MARTINEZ PEREZ CARLOS' in str(nota)

    def test_tipos_nota(self, postulacion, user):
        for tipo in ['NOTA', 'ENTREVISTA', 'EVALUACION', 'REFERENCIA']:
            nota = NotaPostulacion.objects.create(
                postulacion=postulacion, autor=user,
                texto=f'Nota tipo {tipo}', tipo=tipo,
            )
            assert nota.tipo == tipo


# ──────────────────────────────────────────────────────────────
# EntrevistaPrograma
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestEntrevistaPrograma:

    def test_crear_entrevista(self, postulacion, user):
        entrevista = EntrevistaPrograma.objects.create(
            postulacion=postulacion,
            fecha_hora=timezone.now() + timedelta(days=3),
            duracion_minutos=45,
            entrevistador=user,
            tipo='TECNICA',
            modalidad='VIRTUAL',
            enlace_virtual='https://meet.google.com/abc-def-ghi',
        )
        assert entrevista.resultado == 'PENDIENTE'
        assert entrevista.duracion_minutos == 45
        assert 'MARTINEZ PEREZ CARLOS' in str(entrevista)

    def test_calificacion_rango_valido(self, postulacion, user):
        entrevista = EntrevistaPrograma(
            postulacion=postulacion,
            fecha_hora=timezone.now(),
            entrevistador=user,
            calificacion=11,  # fuera del rango 1-10
        )
        with pytest.raises(ValidationError):
            entrevista.full_clean()

    def test_calificacion_rango_valido_bajo(self, postulacion, user):
        entrevista = EntrevistaPrograma(
            postulacion=postulacion,
            fecha_hora=timezone.now(),
            entrevistador=user,
            calificacion=0,  # minimo es 1
        )
        with pytest.raises(ValidationError):
            entrevista.full_clean()

    def test_registrar_resultado_entrevista(self, postulacion, user):
        entrevista = EntrevistaPrograma.objects.create(
            postulacion=postulacion,
            fecha_hora=timezone.now(),
            entrevistador=user,
            tipo='RRHH',
        )
        entrevista.resultado = 'APROBADO'
        entrevista.calificacion = 8
        entrevista.notas_post = 'Excelente comunicación y experiencia relevante.'
        entrevista.save()
        entrevista.refresh_from_db()
        assert entrevista.resultado == 'APROBADO'
        assert entrevista.calificacion == 8
