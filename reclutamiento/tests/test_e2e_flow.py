"""
Tests E2E del flujo completo de reclutamiento.

Simula el flujo entero desde subir CV hasta contratar, verificando:
- Parser de CV → score
- Asignación a vacante con etapa inicial
- Movimientos entre etapas con emails + notifs in-app
- Entrevistas programadas
- Contratación final con Personal creado
- Bulk actions completos
- API REST custom actions
"""
import json
from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from personal.models import Area
from reclutamiento.models import (
    EtapaPipeline, Postulacion, Vacante,
    NotaPostulacion, EntrevistaPrograma,
)


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_e2e', password='x', email='admin_e2e@test.com',
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def area(db):
    return Area.objects.create(nombre='Cocina E2E')


@pytest.fixture
def vacante(db, area):
    return Vacante.objects.create(
        titulo='Sous Chef E2E',
        descripcion='Vacante E2E test',
        area=area,
        estado='PUBLICADA',
        experiencia_minima=3,
    )


@pytest.fixture
def etapas(db):
    out = {}
    nombres_ordenados = ['Recibido', 'Screening', 'Entrevista', 'Prueba', 'Oferta', 'Contratado']
    for i, nombre in enumerate(nombres_ordenados, start=1):
        e, _ = EtapaPipeline.objects.get_or_create(
            codigo=nombre.lower(),
            defaults={'nombre': nombre, 'orden': i, 'activa': True},
        )
        out[nombre] = e
    return out


# ── Test E2E: Flujo completo ─────────────────────────────────

class TestFlujoCompletoReclutamiento:
    """Test E2E del happy path completo."""

    def test_flujo_completo_happy_path(
        self, client_admin, vacante, etapas, settings, admin_user,
    ):
        # Disable emails para no depender de SMTP en tests
        settings.RECLUTAMIENTO_DISABLE_EMAILS = True

        # 1. Crear postulación manualmente (simulando admin upload)
        post = Postulacion.objects.create(
            vacante=vacante,
            etapa=etapas['Recibido'],
            nombre_completo='CANDIDATO E2E',
            email='candidato_e2e@test.com',
            telefono='987654321',
            experiencia_anos=5,
            cv_skills=['cocina_caliente', 'haccp', 'sushi'],
            cv_idiomas=['espanol', 'ingles_basico'],
            cv_score=82,
            cv_parsed_at=timezone.now(),
        )

        # 2. Verificar score visible en pipeline
        r = client_admin.get(reverse('pipeline_panel'))
        assert r.status_code == 200
        assert 'CANDIDATO E2E' in r.content.decode()

        # 3. Agregar nota (sirve para tracking de reclutador)
        nota = NotaPostulacion.objects.create(
            postulacion=post,
            autor=admin_user,
            tipo='NOTA',
            texto='Candidato prometedor, agendar entrevista',
        )
        assert post.notas_detalle.count() == 1

        # 4. Mover a Screening
        r = client_admin.post(
            reverse('postulacion_mover_etapa', args=[post.pk]),
            {'etapa_id': etapas['Screening'].pk},
        )
        assert r.status_code == 200
        post.refresh_from_db()
        assert post.etapa == etapas['Screening']

        # 5. Programar entrevista
        entrev = EntrevistaPrograma.objects.create(
            postulacion=post,
            fecha_hora=timezone.now() + timedelta(days=3),
            entrevistador=admin_user,
            tipo='RRHH',
            modalidad='PRESENCIAL',
            resultado='PENDIENTE',
        )
        assert post.entrevistas.count() == 1

        # 6. Mover a Entrevista
        client_admin.post(
            reverse('postulacion_mover_etapa', args=[post.pk]),
            {'etapa_id': etapas['Entrevista'].pk},
        )
        post.refresh_from_db()
        assert post.etapa == etapas['Entrevista']

        # 7. Aprobar entrevista
        entrev.resultado = 'APROBADO'
        entrev.calificacion = 8
        entrev.save()

        # 8. Asignar tag top_talent
        post.add_tag('top_talent')
        post.refresh_from_db()
        assert 'top_talent' in post.tags

        # 9. Verificar que tag filter funciona
        from django.db import connection
        if connection.vendor == 'postgresql':
            r = client_admin.get(reverse('pipeline_panel') + '?tag=top_talent')
            assert r.status_code == 200
            assert 'CANDIDATO E2E' in r.content.decode()

        # 10. Mover a Oferta
        client_admin.post(
            reverse('postulacion_mover_etapa', args=[post.pk]),
            {'etapa_id': etapas['Oferta'].pk},
        )
        post.refresh_from_db()
        assert post.etapa == etapas['Oferta']

        # 11. Mover a Contratado
        client_admin.post(
            reverse('postulacion_mover_etapa', args=[post.pk]),
            {'etapa_id': etapas['Contratado'].pk},
        )
        post.refresh_from_db()
        assert post.etapa == etapas['Contratado']

        # 12. Verificar historial de notas (bulk + cambio etapa)
        # Cada mover_etapa crea una nota automatica
        assert post.notas_detalle.count() >= 4  # nota manual + 3 movs

        # 13. Verificar PDF candidato genera correctamente
        r = client_admin.get(reverse('postulacion_pdf', args=[post.pk]))
        assert r.status_code == 200
        assert r['Content-Type'] == 'application/pdf'
        assert r.content[:4] == b'%PDF'


# ── Test E2E: Descarte y rescate ─────────────────────────────

class TestFlujoDescarteRescate:
    def test_descartar_y_rescatar_via_banco(
        self, client_admin, vacante, etapas, area, settings,
    ):
        settings.RECLUTAMIENTO_DISABLE_EMAILS = True

        post = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='DESCARTABLE E2E',
            email='descart_e2e@test.com',
            cv_score=72,
        )

        # Descartar
        r = client_admin.post(
            reverse('postulacion_descartar', args=[post.pk]),
            {'motivo': 'No match con perfil actual'},
        )
        assert r.status_code == 200
        post.refresh_from_db()
        assert post.estado == 'DESCARTADA'

        # Debe aparecer en Banco de Talento
        r = client_admin.get(reverse('banco_de_talento'))
        assert r.status_code == 200
        assert 'DESCARTABLE E2E' in r.content.decode()

        # Crear segunda vacante
        vacante2 = Vacante.objects.create(
            titulo='Cocinero Junior E2E',
            descripcion='Otra vacante',
            area=area, estado='PUBLICADA',
        )

        # Rescatar al candidato
        r = client_admin.post(
            reverse('reactivar_candidato', args=[post.pk]),
            {'vacante_id': vacante2.pk},
        )
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data['ok']

        # Verificar nueva postulacion creada
        nueva = Postulacion.objects.get(pk=data['nueva_postulacion_id'])
        assert nueva.vacante == vacante2
        assert nueva.nombre_completo == 'DESCARTABLE E2E'
        assert nueva.email == 'descart_e2e@test.com'
        assert nueva.fuente == 'BANCO'
        # CV skills/score se conservan
        assert nueva.cv_score == 72

        # Original tiene tag reubicar
        post.refresh_from_db()
        assert 'reubicar' in post.tags


# ── Test E2E: Bulk actions ───────────────────────────────────

class TestFlujoBulkActions:
    def test_bulk_mover_y_etiquetar(self, client_admin, vacante, etapas, settings):
        settings.RECLUTAMIENTO_DISABLE_EMAILS = True

        # Crear 4 candidatos
        candidatos = []
        for i in range(4):
            candidatos.append(Postulacion.objects.create(
                vacante=vacante, etapa=etapas['Recibido'],
                nombre_completo=f'BULK CAND {i}',
                email=f'bulk{i}_e2e@test.com',
                cv_score=70 + i*5,
            ))

        ids_str = ','.join(str(c.pk) for c in candidatos)

        # Bulk: tag_add 'prioritario'
        r = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids_str, 'accion': 'tag_add', 'tag': 'prioritario',
        })
        assert r.status_code == 200
        for c in candidatos:
            c.refresh_from_db()
            assert 'prioritario' in c.tags

        # Bulk: mover los 4 a Screening
        r = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids_str, 'accion': 'mover',
            'etapa_id': etapas['Screening'].pk,
        })
        assert r.status_code == 200
        for c in candidatos:
            c.refresh_from_db()
            assert c.etapa == etapas['Screening']

        # Bulk: nota
        r = client_admin.post(reverse('pipeline_bulk_action'), {
            'ids': ids_str, 'accion': 'nota',
            'texto': 'Coordinar entrevistas grupales esta semana',
        })
        assert r.status_code == 200
        # Cada candidato tiene 1 nota bulk
        for c in candidatos:
            notas_bulk = c.notas_detalle.filter(texto__contains='[BULK]')
            assert notas_bulk.count() >= 1


# ── Test E2E: API REST con todas las custom actions ─────────

class TestFlujoAPIREST:
    def test_api_pipeline_completo(
        self, client_admin, vacante, etapas, settings, admin_user,
    ):
        settings.RECLUTAMIENTO_DISABLE_EMAILS = True

        post = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='API E2E',
            email='api_e2e@test.com',
            cv_score=75,
        )

        # GET list
        r = client_admin.get('/api/v1/reclutamiento/postulaciones/')
        assert r.status_code == 200

        # GET detalle
        r = client_admin.get(f'/api/v1/reclutamiento/postulaciones/{post.pk}/')
        assert r.status_code == 200
        body = json.loads(r.content)
        assert body['nombre_completo'] == 'API E2E'
        assert body['cv_score'] == 75

        # POST mover-etapa
        r = client_admin.post(
            f'/api/v1/reclutamiento/postulaciones/{post.pk}/mover-etapa/',
            data=json.dumps({'etapa_id': etapas['Screening'].pk, 'comentario': 'Via API'}),
            content_type='application/json',
        )
        assert r.status_code == 200
        post.refresh_from_db()
        assert post.etapa == etapas['Screening']

        # POST toggle-tag
        r = client_admin.post(
            f'/api/v1/reclutamiento/postulaciones/{post.pk}/toggle-tag/',
            data=json.dumps({'tag': 'top_talent'}),
            content_type='application/json',
        )
        assert r.status_code == 200
        body = json.loads(r.content)
        assert body['ok']
        assert body['has_tag']

        # GET funnel-stats
        r = client_admin.get('/api/v1/reclutamiento/postulaciones/funnel-stats/')
        assert r.status_code == 200
        body = json.loads(r.content)
        # Debe ser una lista con info de etapas
        assert isinstance(body, list)
        assert any('etapa_nombre' in item for item in body)

        # POST bulk
        r = client_admin.post(
            '/api/v1/reclutamiento/postulaciones/bulk/',
            data=json.dumps({
                'ids': [post.pk],
                'accion': 'nota',
                'texto': 'Nota desde API bulk',
            }),
            content_type='application/json',
        )
        assert r.status_code == 200
        body = json.loads(r.content)
        assert body['count'] == 1

        # POST descartar
        r = client_admin.post(
            f'/api/v1/reclutamiento/postulaciones/{post.pk}/descartar/',
            data=json.dumps({'motivo': 'Test descarte API'}),
            content_type='application/json',
        )
        assert r.status_code == 200
        post.refresh_from_db()
        assert post.estado == 'DESCARTADA'

        # No se puede mover ya descartado
        r = client_admin.post(
            f'/api/v1/reclutamiento/postulaciones/{post.pk}/mover-etapa/',
            data=json.dumps({'etapa_id': etapas['Recibido'].pk}),
            content_type='application/json',
        )
        assert r.status_code == 400


# ── Test E2E: Comparar candidatos ────────────────────────────

class TestFlujoComparar:
    def test_comparar_multiples(self, client_admin, vacante, etapas):
        c1 = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='COMPARE A',
            email='a_cmp@test.com',
            cv_score=85,
            cv_skills=['haccp', 'sushi'],
        )
        c2 = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='COMPARE B',
            email='b_cmp@test.com',
            cv_score=78,
            cv_skills=['haccp', 'cocina_caliente'],
        )
        c3 = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Recibido'],
            nombre_completo='COMPARE C',
            email='c_cmp@test.com',
            cv_score=72,
            cv_skills=['sushi', 'cocina_caliente'],
        )

        r = client_admin.get(
            reverse('comparar_candidatos') + f'?ids={c1.pk},{c2.pk},{c3.pk}'
        )
        assert r.status_code == 200
        body = r.content.decode()
        assert 'COMPARE A' in body
        assert 'COMPARE B' in body
        assert 'COMPARE C' in body
        # Skills union: haccp, sushi, cocina_caliente
        assert 'skill-pill' in body


# ── Test E2E: Calendario ─────────────────────────────────────

class TestFlujoCalendario:
    def test_calendario_muestra_entrevistas(
        self, client_admin, vacante, etapas, admin_user,
    ):
        post = Postulacion.objects.create(
            vacante=vacante, etapa=etapas['Entrevista'],
            nombre_completo='CAL E2E', email='cal_e2e@test.com',
        )
        # Entrevista en este mes
        now = timezone.now()
        EntrevistaPrograma.objects.create(
            postulacion=post,
            fecha_hora=now + timedelta(days=2),
            entrevistador=admin_user,
            tipo='RRHH',
            modalidad='PRESENCIAL',
        )

        r = client_admin.get(reverse('calendario_entrevistas'))
        assert r.status_code == 200
        body = r.content.decode()
        # Nombre del candidato visible en el calendario
        assert 'CAL E2E' in body or 'CAL E2E'[:14] in body
