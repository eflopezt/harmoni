"""
Tests para extras del Pipeline Kanban:
- Filtros (vacante, score_min, fuente, tag)
- Bulk actions (mover, descartar, tag_add, tag_remove)
- Tag helpers en Postulacion
- Toggle tag endpoint
- PDF candidato endpoint
- Emails automaticos (con flag DISABLE)
"""
import pytest

from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area
from reclutamiento.models import EtapaPipeline, Postulacion, Vacante


# ── Fixtures ────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username="admin_pe", password="x", email="a@a.com",
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Salón")


@pytest.fixture
def vacante(db, area):
    return Vacante.objects.create(
        titulo="Mesero Senior",
        descripcion="Test vacante pipeline extras",
        area=area, estado="PUBLICADA",
    )


@pytest.fixture
def etapas(db):
    out = {}
    for i, nombre in enumerate(['Recibido', 'Screening', 'Entrevista', 'Contratado'], start=1):
        e = EtapaPipeline.objects.create(
            codigo=nombre.lower(), nombre=nombre, orden=i,
        )
        out[nombre] = e
    return out


@pytest.fixture
def candidatos(db, vacante, etapas):
    """4 candidatos con distintos scores y fuentes."""
    base = dict(vacante=vacante, etapa=etapas['Recibido'])
    return {
        'alto':   Postulacion.objects.create(
            **base, nombre_completo='ALTO SCORE', email='alto@x.com',
            fuente='LINKEDIN', cv_score=92,
        ),
        'medio':  Postulacion.objects.create(
            **base, nombre_completo='MEDIO SCORE', email='medio@x.com',
            fuente='PORTAL', cv_score=65,
        ),
        'bajo':   Postulacion.objects.create(
            **base, nombre_completo='BAJO SCORE', email='bajo@x.com',
            fuente='OTRO', cv_score=40,
        ),
        'sin':    Postulacion.objects.create(
            **base, nombre_completo='SIN SCORE', email='sin@x.com',
            fuente='REFERIDO', cv_score=0,
        ),
    }


# ── Tests de filtros ────────────────────────────────────────

class TestPipelineFiltros:
    def test_render_pipeline_basico(self, client_admin, candidatos):
        resp = client_admin.get(reverse('pipeline_panel'))
        assert resp.status_code == 200
        body = resp.content.decode()
        # Header
        assert 'Pipeline' in body
        # Todos los candidatos visibles
        for p in candidatos.values():
            assert p.nombre_completo in body

    def test_filtro_score_min(self, client_admin, candidatos):
        resp = client_admin.get(reverse('pipeline_panel') + '?score_min=70')
        assert resp.status_code == 200
        body = resp.content.decode()
        assert candidatos['alto'].nombre_completo in body
        # Los de score < 70 no deben aparecer
        assert candidatos['medio'].nombre_completo not in body
        assert candidatos['bajo'].nombre_completo not in body
        assert candidatos['sin'].nombre_completo not in body

    def test_filtro_fuente(self, client_admin, candidatos):
        resp = client_admin.get(reverse('pipeline_panel') + '?fuente=LINKEDIN')
        assert resp.status_code == 200
        body = resp.content.decode()
        assert candidatos['alto'].nombre_completo in body
        assert candidatos['medio'].nombre_completo not in body

    def test_filtro_tag(self, client_admin, candidatos):
        from django.db import connection
        if connection.vendor == 'sqlite':
            pytest.skip("JSONField __contains lookup no soportado en SQLite")
        candidatos['alto'].add_tag('top_talent')
        resp = client_admin.get(reverse('pipeline_panel') + '?tag=top_talent')
        assert resp.status_code == 200
        body = resp.content.decode()
        assert candidatos['alto'].nombre_completo in body
        assert candidatos['medio'].nombre_completo not in body

    def test_filtros_combinados(self, client_admin, candidatos):
        resp = client_admin.get(
            reverse('pipeline_panel') + '?score_min=60&fuente=LINKEDIN',
        )
        assert resp.status_code == 200
        body = resp.content.decode()
        # Solo ALTO cumple ambos
        assert candidatos['alto'].nombre_completo in body
        assert candidatos['medio'].nombre_completo not in body


# ── Tests de tags ──────────────────────────────────────────

class TestTagsModelo:
    def test_add_tag(self, db, candidatos):
        p = candidatos['alto']
        p.add_tag('top_talent')
        p.refresh_from_db()
        assert 'top_talent' in p.tags

    def test_add_tag_idempotente(self, db, candidatos):
        p = candidatos['alto']
        p.add_tag('top_talent')
        p.add_tag('top_talent')
        p.refresh_from_db()
        assert p.tags.count('top_talent') == 1

    def test_remove_tag(self, db, candidatos):
        p = candidatos['alto']
        p.add_tag('top_talent')
        p.remove_tag('top_talent')
        p.refresh_from_db()
        assert 'top_talent' not in p.tags

    def test_toggle_tag(self, db, candidatos):
        p = candidatos['alto']
        p.toggle_tag('prioritario')
        p.refresh_from_db()
        assert 'prioritario' in p.tags
        p.toggle_tag('prioritario')
        p.refresh_from_db()
        assert 'prioritario' not in p.tags

    def test_has_tag(self, db, candidatos):
        p = candidatos['alto']
        assert not p.has_tag('top_talent')
        p.add_tag('top_talent')
        assert p.has_tag('top_talent')

    def test_tags_display(self, db, candidatos):
        p = candidatos['alto']
        p.tags = ['top_talent', 'prioritario']
        p.save()
        display = p.tags_display
        codes = [c for c, _ in display]
        labels = [l for _, l in display]
        assert 'top_talent' in codes
        assert 'Top Talent' in labels


class TestToggleTagEndpoint:
    def test_toggle_tag_post(self, client_admin, candidatos):
        p = candidatos['alto']
        resp = client_admin.post(
            reverse('postulacion_toggle_tag', args=[p.pk]),
            {'tag': 'top_talent'},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok']
        assert data['has_tag']
        assert 'top_talent' in data['tags']

    def test_toggle_tag_invalido(self, client_admin, candidatos):
        p = candidatos['alto']
        resp = client_admin.post(
            reverse('postulacion_toggle_tag', args=[p.pk]),
            {'tag': 'tag_inexistente'},
        )
        assert resp.status_code == 400

    def test_toggle_tag_no_existe(self, client_admin):
        resp = client_admin.post(
            reverse('postulacion_toggle_tag', args=[99999]),
            {'tag': 'top_talent'},
        )
        assert resp.status_code == 404

    def test_toggle_tag_get_no_permitido(self, client_admin, candidatos):
        p = candidatos['alto']
        resp = client_admin.get(reverse('postulacion_toggle_tag', args=[p.pk]))
        assert resp.status_code == 405


# ── Tests de bulk actions ──────────────────────────────────

class TestBulkActions:
    def test_bulk_mover(self, client_admin, candidatos, etapas):
        ids = ','.join(str(p.pk) for p in candidatos.values())
        resp = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids,
            'accion': 'mover',
            'etapa_id': etapas['Entrevista'].pk,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok']
        assert data['count'] == 4
        # Verificar que todos cambiaron de etapa
        for p in candidatos.values():
            p.refresh_from_db()
            assert p.etapa.pk == etapas['Entrevista'].pk

    def test_bulk_descartar(self, client_admin, candidatos):
        ids = ','.join(str(p.pk) for p in [candidatos['bajo'], candidatos['sin']])
        resp = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids,
            'accion': 'descartar',
            'motivo': 'No cumple requisitos',
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok']
        assert data['count'] == 2
        candidatos['bajo'].refresh_from_db()
        assert candidatos['bajo'].estado == 'DESCARTADA'
        # Los no incluidos siguen activos
        candidatos['alto'].refresh_from_db()
        assert candidatos['alto'].estado == 'ACTIVA'

    def test_bulk_tag_add(self, client_admin, candidatos):
        ids = ','.join(str(p.pk) for p in [candidatos['alto'], candidatos['medio']])
        resp = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids,
            'accion': 'tag_add',
            'tag': 'seguimiento',
        })
        assert resp.status_code == 200
        assert resp.json()['count'] == 2
        candidatos['alto'].refresh_from_db()
        candidatos['medio'].refresh_from_db()
        assert 'seguimiento' in candidatos['alto'].tags
        assert 'seguimiento' in candidatos['medio'].tags

    def test_bulk_tag_remove(self, client_admin, candidatos):
        candidatos['alto'].add_tag('en_espera')
        candidatos['medio'].add_tag('en_espera')
        ids = ','.join(str(p.pk) for p in [candidatos['alto'], candidatos['medio']])
        client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids,
            'accion': 'tag_remove',
            'tag': 'en_espera',
        })
        candidatos['alto'].refresh_from_db()
        assert 'en_espera' not in candidatos['alto'].tags

    def test_bulk_sin_ids(self, client_admin):
        resp = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': '', 'accion': 'mover',
        })
        assert resp.status_code == 400

    def test_bulk_etapa_invalida(self, client_admin, candidatos):
        resp = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': str(candidatos['alto'].pk),
            'accion': 'mover',
            'etapa_id': '99999',
        })
        assert resp.status_code == 400


# ── Tests de PDF candidato ─────────────────────────────────

class TestPDFCandidato:
    def test_pdf_render_200(self, client_admin, candidatos):
        resp = client_admin.get(reverse('postulacion_pdf', args=[candidatos['alto'].pk]))
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content[:4] == b'%PDF'

    def test_pdf_404_si_no_existe(self, client_admin):
        resp = client_admin.get(reverse('postulacion_pdf', args=[99999]))
        assert resp.status_code == 404


# ── Tests de emails automaticos ────────────────────────────

class TestEmailsDisabled:
    """Con flag DISABLE_EMAILS=True el sistema no debe intentar enviar."""

    def test_email_disabled_returns_false(self, db, candidatos, settings):
        settings.RECLUTAMIENTO_DISABLE_EMAILS = True
        from reclutamiento.emails import enviar_email_candidato
        assert enviar_email_candidato(candidatos['alto'], 'postulado') is False


class TestEmailsService:
    """Verifica el render y mapeo. NO testea SMTP."""

    def test_render_postulado(self, db, candidatos):
        from reclutamiento.emails import _render
        asunto, cuerpo = _render('postulado', {
            'nombre': 'Edwin', 'vacante': 'Chef', 'empresa': 'EDO',
        })
        assert 'Edwin' in cuerpo
        assert 'Chef' in asunto

    def test_render_template_inexistente(self, db):
        from reclutamiento.emails import _render
        asunto, cuerpo = _render('inexistente', {})
        assert asunto is None

    def test_email_sin_email_skip(self, db, vacante, etapas):
        p = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='SIN EMAIL', email='',
        )
        from reclutamiento.emails import enviar_email_candidato
        assert enviar_email_candidato(p, 'postulado') is False

    def test_etapa_to_template_mapping(self, db):
        from reclutamiento.emails import ETAPA_TO_TEMPLATE, TEMPLATES
        # Cada valor del mapping debe ser una key valida en TEMPLATES
        for codigo, template_key in ETAPA_TO_TEMPLATE.items():
            assert template_key in TEMPLATES, (
                f"Mapping {codigo}->{template_key} pero {template_key} no esta en TEMPLATES"
            )

    def test_email_por_etapa_etapa_desconocida(self, db, candidatos, etapas):
        """Si la etapa no esta en el mapping, no envia."""
        # Crear una etapa con codigo no mapeado
        etapa_otra = EtapaPipeline.objects.create(
            codigo='evaluacion_psicometrica', nombre='Eval', orden=99,
        )
        from reclutamiento.emails import email_por_etapa
        # No debe romper
        result = email_por_etapa(candidatos['alto'], etapa_otra)
        # Si la etapa no esta mapeada, retorna False (no envia)
        assert result is False
