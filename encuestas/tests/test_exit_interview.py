"""
Tests Sprint 3 — Encuesta Exit Interview.

Cubre:
  1. seed_exit_interview crea la encuesta (idempotente).
  2. La encuesta tiene exactamente 10 preguntas con categorías esperadas.
  3. La encuesta sembrada es compatible con el flujo offboarding
     (existe consulta por tipo='SALIDA' estado='ACTIVA').
"""
from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from encuestas.models import Encuesta, PreguntaEncuesta


ENCUESTA_TITULO = 'Exit Interview — Entrevista de Salida'


# ─── 1. seed crea encuesta idempotente ────────────────────────────────────────

class TestSeedExitInterview:
    def test_seed_crea_encuesta(self, db):
        """Primera ejecución crea la encuesta SALIDA + 10 preguntas."""
        assert not Encuesta.objects.filter(titulo=ENCUESTA_TITULO).exists()

        out = StringIO()
        call_command('seed_exit_interview', stdout=out)

        enc = Encuesta.objects.get(titulo=ENCUESTA_TITULO)
        assert enc.tipo == 'SALIDA'
        assert enc.estado == 'ACTIVA'
        assert enc.anonima is False
        assert enc.preguntas.count() == 10

    def test_seed_es_idempotente(self, db):
        """Dos ejecuciones consecutivas → 1 sola encuesta + 10 preguntas."""
        out = StringIO()
        call_command('seed_exit_interview', stdout=out)
        call_command('seed_exit_interview', stdout=out)
        call_command('seed_exit_interview', stdout=out)

        qs = Encuesta.objects.filter(titulo=ENCUESTA_TITULO, tipo='SALIDA')
        assert qs.count() == 1
        assert qs.first().preguntas.count() == 10

    def test_seed_dry_run_no_persiste(self, db):
        """--dry-run no crea nada."""
        call_command('seed_exit_interview', '--dry-run', stdout=StringIO())
        assert not Encuesta.objects.filter(titulo=ENCUESTA_TITULO).exists()
        assert PreguntaEncuesta.objects.filter(
            encuesta__titulo=ENCUESTA_TITULO,
        ).count() == 0


# ─── 2. estructura de preguntas ───────────────────────────────────────────────

class TestEstructuraPreguntas:
    def test_tiene_10_preguntas_con_categorias(self, db):
        """Las 10 preguntas cubren las categorías clave del spec."""
        call_command('seed_exit_interview', stdout=StringIO())

        enc = Encuesta.objects.get(titulo=ENCUESTA_TITULO)
        preguntas = list(enc.preguntas.order_by('orden'))

        assert len(preguntas) == 10

        categorias = {p.categoria for p in preguntas}
        # Cubre dimensiones clave del exit interview
        for cat in (
            'Motivo', 'Satisfacción', 'eNPS', 'Liderazgo',
            'Compensación', 'Reconocimiento', 'Mejora',
        ):
            assert cat in categorias, f'Falta categoría {cat}'

    def test_tiene_tipos_variados(self, db):
        """Debe haber preguntas TEXTO, ESCALA_10, ESCALA_5 y OPCION."""
        call_command('seed_exit_interview', stdout=StringIO())
        enc = Encuesta.objects.get(titulo=ENCUESTA_TITULO)
        tipos = {p.tipo for p in enc.preguntas.all()}
        assert 'TEXTO' in tipos
        assert 'ESCALA_10' in tipos
        assert 'ESCALA_5' in tipos
        assert 'OPCION' in tipos

    def test_preguntas_opcion_tienen_opciones(self, db):
        """Toda pregunta OPCION debe traer la lista de opciones poblada."""
        call_command('seed_exit_interview', stdout=StringIO())
        enc = Encuesta.objects.get(titulo=ENCUESTA_TITULO)
        for p in enc.preguntas.filter(tipo='OPCION'):
            assert isinstance(p.opciones, list)
            assert len(p.opciones) >= 2, f'Pregunta {p.pk} sin opciones'


# ─── 3. compatibilidad con flujo offboarding ──────────────────────────────────

class TestCompatibilidadWorkflow:
    def test_consulta_por_tipo_salida_activa_devuelve_encuesta(self, db):
        """
        El template de detalle de liquidación filtra
        `Encuesta.objects.filter(tipo='SALIDA', estado='ACTIVA')`
        para mostrar el botón "Enviar encuesta exit". Verificamos
        que la encuesta seedeada responde a esa consulta.
        """
        call_command('seed_exit_interview', stdout=StringIO())
        qs = Encuesta.objects.filter(tipo='SALIDA', estado='ACTIVA')
        assert qs.exists()
        enc = qs.first()
        assert enc.titulo == ENCUESTA_TITULO

    def test_url_responder_resoluble(self, db, client):
        """
        La URL /encuestas/responder/<id>/ (que usa el botón "Enviar
        encuesta exit") está registrada en encuestas.urls. Solo
        verificamos que `reverse` la resuelve, no la respuesta HTTP
        (la vista requiere login).
        """
        from django.urls import reverse

        call_command('seed_exit_interview', stdout=StringIO())
        enc = Encuesta.objects.get(titulo=ENCUESTA_TITULO)
        url = reverse('responder_encuesta', args=[enc.pk])
        assert url == f'/encuestas/responder/{enc.pk}/'
