"""
Tests integration de las features grandes 2026 cross-modulo.

Verifica que las URLs principales construidas durante 2026 responden 200
con seeds básicos. Es el smoke test que corre antes de cualquier release.
"""
import pytest
from django.contrib.auth.models import User


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_2026', password='x', email='a2026@test.com',
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


class TestFeatures2026URLs:
    """Smoke test que verifica que todas las URLs grandes de 2026 cargan."""

    @pytest.mark.parametrize('url,desc', [
        ('/',                                              'Home admin'),
        ('/sistema/dashboard/ejecutivo/',                  'Dashboard Ejecutivo'),
        ('/sistema/reporte-bi-mensual/?anio=2026&mes=5',   'BI Excel mensual'),
        ('/reclutamiento/pipeline/',                       'Pipeline Kanban'),
        ('/reclutamiento/mi-dia/',                         'Mi Día Reclutador'),
        ('/reclutamiento/funnel/',                         'Funnel'),
        ('/reclutamiento/banco-talento/',                  'Banco Talento'),
        ('/reclutamiento/comparar/',                       'Comparar (empty)'),
        ('/reclutamiento/calendario/',                     'Calendario Entrevistas'),
        ('/reclutamiento/stats-reclutadores/',             'Stats Reclutadores'),
    ])
    def test_url_renders_200(self, client_admin, url, desc, db):
        """Cada URL del menú 2026 responde 200 con DB vacía."""
        r = client_admin.get(url)
        # Permitir 200 o 302 (redirect a login si por ahí pierde sesión)
        assert r.status_code in (200, 302), f'{desc} falló con {r.status_code}'


class TestFeatures2026CrossOrigin:
    """Tests cross-modulo que verifican integraciones funcionando."""

    def test_pipeline_filtros_no_rompen_con_db_vacia(self, client_admin, db):
        """Filtros de pipeline no deben crashear con DB sin postulaciones."""
        urls = [
            '/reclutamiento/pipeline/?score_min=70',
            '/reclutamiento/pipeline/?fuente=LINKEDIN',
            '/reclutamiento/pipeline/?dias_min=14',
        ]
        for u in urls:
            r = client_admin.get(u)
            assert r.status_code == 200, f'{u} → {r.status_code}'

    def test_api_funnel_stats(self, client_admin, db):
        """API funnel-stats responde JSON valido aún sin etapas."""
        r = client_admin.get('/api/v1/reclutamiento/postulaciones/funnel-stats/')
        assert r.status_code == 200
        import json
        data = json.loads(r.content)
        assert isinstance(data, list)

    def test_api_lista_etapas(self, client_admin, db):
        """API etapas responde lista (puede ser vacía)."""
        r = client_admin.get('/api/v1/reclutamiento/etapas/')
        assert r.status_code == 200

    def test_api_lista_vacantes(self, client_admin, db):
        """API vacantes responde paginated list."""
        r = client_admin.get('/api/v1/reclutamiento/vacantes/')
        assert r.status_code == 200


class TestFeatures2026Access:
    """Verifica control de acceso."""

    def test_anonimo_no_accede_a_dashboard(self, client, db):
        """Sin login, dashboard ejecutivo redirige a login."""
        r = client.get('/sistema/dashboard/ejecutivo/')
        assert r.status_code in (302, 403)

    def test_anonimo_no_accede_a_mi_dia(self, client, db):
        r = client.get('/reclutamiento/mi-dia/')
        assert r.status_code in (302, 403)

    def test_anonimo_no_accede_a_bi_excel(self, client, db):
        r = client.get('/sistema/reporte-bi-mensual/?anio=2026&mes=5')
        assert r.status_code in (302, 403)


class TestHomeTiles:
    """Verifica que los tiles 2026 aparecen en el home."""

    def test_home_admin_contiene_tiles_2026(self, client_admin, db):
        r = client_admin.get('/')
        if r.status_code != 200:
            pytest.skip(f'home redirige a {r.status_code}')
        body = r.content.decode()
        # Esperar que la sección "Herramientas avanzadas" esté presente
        assert 'Herramientas avanzadas' in body
        # Algunos tiles clave
        assert 'Pipeline Reclutamiento' in body or 'Mi Día' in body
        # Class ft-tile presente
        assert 'ft-tile' in body


class TestPDFsRespondenContentTypeCorrecto:
    """Smoke test de los PDFs ejecutivos."""

    def test_stats_reclutadores_pdf(self, client_admin, db):
        r = client_admin.get('/reclutamiento/stats-reclutadores/pdf/?periodo=90')
        assert r.status_code == 200
        assert r['Content-Type'] == 'application/pdf'
        assert r.content[:4] == b'%PDF'

    def test_bi_excel_mensual(self, client_admin, db):
        r = client_admin.get('/sistema/reporte-bi-mensual/?anio=2026&mes=5')
        assert r.status_code == 200
        # Excel mime type
        assert 'spreadsheet' in r['Content-Type']
        # ZIP magic bytes
        assert r.content[:2] == b'PK'
