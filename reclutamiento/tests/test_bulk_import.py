"""
Tests para bulk import de candidatos + descarga plantilla.
"""
import io
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from personal.models import Area
from reclutamiento.models import Vacante, Postulacion, EtapaPipeline


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin_bi", password="x", email="a@a.com")


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
        titulo="Mesero", descripcion="t", area=area, estado="PUBLICADA",
    )


@pytest.fixture
def etapa(db):
    return EtapaPipeline.objects.create(codigo='recibido', nombre='Recibido', orden=1)


class TestBulkImportForm:
    def test_render_form(self, client_admin):
        resp = client_admin.get(reverse("candidatos_bulk_import"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Bulk Import" in body
        assert "plantilla" in body.lower()

    def test_descarga_plantilla(self, client_admin):
        resp = client_admin.get(reverse("candidatos_bulk_plantilla"))
        assert resp.status_code == 200
        assert "spreadsheet" in resp["Content-Type"]
        # Verificar bytes Excel
        assert resp.content[:2] == b"PK"
        # Verificar el contenido (nombres de columnas)
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        headers = [c.value for c in ws[1]]
        assert any('nombre' in (h or '').lower() for h in headers)
        assert any('email' in (h or '').lower() for h in headers)


class TestBulkImportCSV:
    def test_subir_csv_valido(self, client_admin, vacante, etapa):
        csv_content = (
            "nombre_completo,email,telefono,anios_experiencia,fuente,skills\n"
            "TEST UNO,test1@ejemplo.com,987111111,3,LINKEDIN,cocina_caliente\n"
            "TEST DOS,test2@ejemplo.com,987222222,5,PORTAL,sommelier\n"
        )
        archivo = SimpleUploadedFile(
            'cands.csv',
            csv_content.encode('utf-8'),
            content_type='text/csv',
        )
        resp = client_admin.post(reverse("candidatos_bulk_import"), {
            'archivo': archivo,
        })
        assert resp.status_code == 200
        body = resp.content.decode()
        # Preview muestra ambos candidatos
        assert "TEST UNO" in body
        assert "TEST DOS" in body

    def test_subir_csv_invalido(self, client_admin):
        archivo = SimpleUploadedFile(
            'sin_headers.txt',
            b'no es un csv valido',
            content_type='text/plain',
        )
        resp = client_admin.post(reverse("candidatos_bulk_import"), {
            'archivo': archivo,
        })
        # Formato no soportado → redirect con error
        assert resp.status_code == 302

    def test_confirma_import_crea_postulaciones(self, client_admin, vacante, etapa):
        # Step 1: subir CSV
        csv_content = (
            "nombre_completo,email,telefono\n"
            "MARIA TEST,maria_bulk@ejemplo.com,987333333\n"
            "PEDRO TEST,pedro_bulk@ejemplo.com,987444444\n"
        )
        archivo = SimpleUploadedFile('c.csv', csv_content.encode('utf-8'),
                                      content_type='text/csv')
        client_admin.post(reverse("candidatos_bulk_import"), {'archivo': archivo})

        # Step 2: confirmar
        resp = client_admin.post(reverse("candidatos_bulk_import"), {
            'confirmar': '1',
            'vacante_id': vacante.pk,
            'omitir_duplicados': '0',
        })
        assert resp.status_code == 302
        # Postulaciones creadas
        assert Postulacion.objects.filter(email='maria_bulk@ejemplo.com').exists()
        assert Postulacion.objects.filter(email='pedro_bulk@ejemplo.com').exists()

    def test_omitir_duplicados(self, client_admin, vacante, etapa):
        # Crear postulación existente
        Postulacion.objects.create(
            vacante=vacante, etapa=etapa,
            nombre_completo='ANTIGUO',
            email='dup@ejemplo.com',
        )

        # Subir CSV con duplicado
        csv_content = (
            "nombre_completo,email\n"
            "NUEVO,dup@ejemplo.com\n"
            "OTRO,otro@ejemplo.com\n"
        )
        archivo = SimpleUploadedFile('d.csv', csv_content.encode('utf-8'),
                                      content_type='text/csv')
        client_admin.post(reverse("candidatos_bulk_import"), {'archivo': archivo})

        # Confirmar con omitir_duplicados=1
        resp = client_admin.post(reverse("candidatos_bulk_import"), {
            'confirmar': '1',
            'vacante_id': vacante.pk,
            'omitir_duplicados': '1',
        })
        assert resp.status_code == 302
        # 'dup@ejemplo.com' debe seguir teniendo solo 1 postulación
        assert Postulacion.objects.filter(email='dup@ejemplo.com').count() == 1
        # 'otro@ejemplo.com' sí debe crearse
        assert Postulacion.objects.filter(email='otro@ejemplo.com').exists()


class TestScoreDetalle:
    def test_render_score_detalle(self, client_admin, vacante, etapa):
        post = Postulacion.objects.create(
            vacante=vacante, etapa=etapa,
            nombre_completo='TEST SCORE',
            email='score@ejemplo.com',
            telefono='987555555',
            experiencia_anos=5,
            cv_skills=['cocina_caliente', 'haccp'],
            cv_score=75,
        )
        resp = client_admin.get(reverse("postulacion_score_detalle", args=[post.pk]))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Score de Matching" in body
        assert "TEST SCORE" in body
        # Componentes visibles
        assert "Años de experiencia" in body
        assert "Email detectado" in body
        assert "Skills" in body

    def test_404_si_no_existe(self, client_admin):
        resp = client_admin.get(reverse("postulacion_score_detalle", args=[99999]))
        assert resp.status_code == 404


class TestPermisos:
    def test_bulk_anonimo_redirige(self, client):
        resp = client.get(reverse("candidatos_bulk_import"))
        assert resp.status_code == 302

    def test_score_anonimo_redirige(self, client, vacante, etapa):
        post = Postulacion.objects.create(
            vacante=vacante, etapa=etapa,
            nombre_completo='X', email='x@x.com',
        )
        resp = client.get(reverse("postulacion_score_detalle", args=[post.pk]))
        assert resp.status_code == 302
