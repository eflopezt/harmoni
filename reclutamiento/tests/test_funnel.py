"""
Tests para view funnel_reclutamiento + seed_postulaciones_demo.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from personal.models import Area
from reclutamiento.models import Vacante, Postulacion, EtapaPipeline


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(username="admin_fn", password="x", email="a@a.com")


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
        descripcion="Test vacante para funnel",
        area=area,
        estado="PUBLICADA",
    )


@pytest.fixture
def etapas(db):
    out = {}
    for i, nombre in enumerate(['Recibido', 'Screening', 'Entrevista', 'Contratado'], start=1):
        e = EtapaPipeline.objects.create(
            codigo=nombre.lower(),
            nombre=nombre, orden=i,
        )
        out[nombre] = e
    return out


def crear_postulacion(vacante, etapa, *, fuente='PORTAL', estado='ACTIVA', score=70):
    return Postulacion.objects.create(
        vacante=vacante, etapa=etapa,
        nombre_completo=f"TEST {timezone.now().microsecond}",
        email=f"test{timezone.now().microsecond}@ejemplo.com",
        fuente=fuente, estado=estado, cv_score=score,
    )


class TestFunnelReclutamiento:
    def test_render_sin_data(self, client_admin):
        resp = client_admin.get(reverse("funnel_reclutamiento"))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Funnel de Reclutamiento" in body

    def test_kpis_globales(self, client_admin, vacante, etapas):
        # Crear postulaciones en varias etapas
        for _ in range(5):
            crear_postulacion(vacante, etapas['Recibido'])
        for _ in range(3):
            crear_postulacion(vacante, etapas['Screening'])
        crear_postulacion(vacante, etapas['Contratado'], estado='CONTRATADA')

        resp = client_admin.get(reverse("funnel_reclutamiento"))
        body = resp.content.decode()
        # Total 9 postulaciones
        assert "9" in body  # número total
        # Hay 1 contratado
        assert "1" in body

    def test_filtro_periodo(self, client_admin, vacante, etapas):
        # Postulación reciente
        crear_postulacion(vacante, etapas['Recibido'])
        # Postulación muy antigua (fuera de los 30 días default)
        old = crear_postulacion(vacante, etapas['Recibido'])
        old_date = timezone.now() - timedelta(days=120)
        Postulacion.objects.filter(pk=old.pk).update(fecha_postulacion=old_date)

        resp = client_admin.get(reverse("funnel_reclutamiento") + "?periodo=30")
        assert resp.status_code == 200

    def test_source_effectiveness(self, client_admin, vacante, etapas):
        crear_postulacion(vacante, etapas['Recibido'], fuente='LINKEDIN')
        crear_postulacion(vacante, etapas['Recibido'], fuente='REFERIDO')
        crear_postulacion(vacante, etapas['Contratado'],
                          fuente='LINKEDIN', estado='CONTRATADA')

        resp = client_admin.get(reverse("funnel_reclutamiento"))
        body = resp.content.decode()
        assert "LINKEDIN" in body
        assert "REFERIDO" in body

    def test_score_buckets(self, client_admin, vacante, etapas):
        # Diferentes scores
        crear_postulacion(vacante, etapas['Recibido'], score=30)   # 0-40
        crear_postulacion(vacante, etapas['Recibido'], score=55)   # 41-60
        crear_postulacion(vacante, etapas['Recibido'], score=75)   # 61-80
        crear_postulacion(vacante, etapas['Recibido'], score=90)   # 81-100

        resp = client_admin.get(reverse("funnel_reclutamiento"))
        body = resp.content.decode()
        # Los 4 labels deben estar
        assert "0-40" in body
        assert "41-60" in body
        assert "61-80" in body
        assert "81-100" in body


class TestPermisos:
    def test_anonimo_redirige(self, client):
        resp = client.get(reverse("funnel_reclutamiento"))
        assert resp.status_code == 302

    def test_no_superuser_no_pasa(self, db, client):
        u = User.objects.create_user(username="reg", password="x", is_superuser=False)
        client.force_login(u)
        resp = client.get(reverse("funnel_reclutamiento"))
        assert resp.status_code in (302, 403)


class TestSeedPostulaciones:
    def test_seed_requiere_vacantes(self, db, capsys):
        # Sin vacantes → seed sale con error
        call_command('seed_postulaciones_demo')
        captured = capsys.readouterr()
        assert 'No hay vacantes' in captured.out

    def test_seed_crea_25_postulaciones(self, db, vacante):
        call_command('seed_postulaciones_demo')
        # Aproximadamente 25 creadas
        assert Postulacion.objects.count() >= 20
        assert Postulacion.objects.count() <= 30

    def test_seed_distribuye_etapas(self, db, vacante):
        call_command('seed_postulaciones_demo')
        # Crea las 6 etapas
        assert EtapaPipeline.objects.count() >= 6
        # Recibido debe tener la mayoría
        recibido = EtapaPipeline.objects.get(codigo='recibido')
        assert Postulacion.objects.filter(etapa=recibido).count() >= 5

    def test_seed_idempotente(self, db, vacante):
        call_command('seed_postulaciones_demo')
        n1 = Postulacion.objects.count()
        call_command('seed_postulaciones_demo')
        n2 = Postulacion.objects.count()
        # Skip por email duplicado, no debe crear más
        assert n2 == n1

    def test_seed_clear_funciona(self, db, vacante):
        call_command('seed_postulaciones_demo')
        n1 = Postulacion.objects.count()
        # Crear una manual fuera del seed
        Postulacion.objects.create(
            vacante=vacante,
            nombre_completo='MANUAL',
            email='manual@ejemplo.com',
            notas='registro manual NO seed',
        )
        call_command('seed_postulaciones_demo', '--clear')
        # El manual sobrevive (no tiene marker en notas)
        assert Postulacion.objects.filter(email='manual@ejemplo.com').exists()
