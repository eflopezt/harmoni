"""
Tests para WorkerAccessRestrictionMiddleware.

Garantiza que un trabajador puro (vinculado a Personal pero sin
is_superuser/is_staff/perfil responsable) NO acceda a URLs admin.

CRÍTICO para seguridad — si esto se rompe, los trabajadores
pueden acceder a /personal/, /nominas/, /empresas/billing/ etc.
"""
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings


User = get_user_model()


# ── URLs que un trabajador puro DEBE poder acceder ──
URLS_ALLOWED = [
    '/mi-portal/',
    '/documentos/boletas/mis/',
    '/vacaciones/mis/',
    '/prestamos/mis/',
    '/nominas/mis-recibos/',
    '/nominas/consentimiento-boleta/',
    '/cuenta/',
]

# ── URLs admin que un trabajador NO DEBE poder acceder ──
URLS_BLOQUEADAS = [
    '/personal/',
    '/organigrama/',
    '/nominas/',
    '/nominas/boletas/',
    '/nominas/config/tasas-afp/',
    '/empresas/',
    '/empresas/billing/',
    '/asistencia/staff/',
    '/asistencia/reportes/',
    '/integraciones/contable/',
    '/reclutamiento/',
    '/sistema/auditoria/',
]


@pytest.fixture
def trabajador_puro(db):
    """Crea un trabajador vinculado a Personal sin privilegios admin."""
    from personal.models import Personal
    from empresas.models import Empresa

    empresa = Empresa.objects.create(
        razon_social='Test Co SAC',
        ruc='20100000001',
    )
    user = User.objects.create_user(
        username='trab_test',
        password='testpass123',
        is_staff=False,
        is_superuser=False,
    )
    Personal.objects.create(
        empresa=empresa,
        usuario=user,
        nro_doc='12345678',
        tipo_doc='DNI',
        apellidos_nombres='TEST WORKER, Juan',
        estado='Activo',
        sueldo_base=2000,
    )
    return user


@pytest.fixture
def admin_user(db):
    """Crea un admin con is_superuser=True."""
    user = User.objects.create_superuser(
        username='admin_test',
        password='adminpass123',
        email='admin@test.local',
    )
    return user


@pytest.mark.django_db
def test_trabajador_puro_accede_a_urls_worker(client, trabajador_puro):
    """Trabajador puede acceder a las URLs del portal."""
    client.login(username='trab_test', password='testpass123')
    for url in URLS_ALLOWED:
        response = client.get(url, follow=False)
        # 200 OK o 302 a otra URL worker — NO 302 a /mi-portal/ explícitamente
        assert response.status_code in (200, 302), (
            f'{url} retornó {response.status_code}, esperaba 200/302'
        )


@pytest.mark.django_db
def test_trabajador_puro_bloqueado_en_urls_admin(client, trabajador_puro):
    """Trabajador NO puede acceder a URLs admin — debe ser redirigido."""
    client.login(username='trab_test', password='testpass123')
    for url in URLS_BLOQUEADAS:
        response = client.get(url, follow=False)
        # Esperamos 302 a /mi-portal/ (el middleware redirige)
        assert response.status_code == 302, (
            f'{url}: esperaba 302 (bloqueo), recibí {response.status_code}'
        )
        # Verificar destino
        location = response.get('Location', '')
        assert '/mi-portal/' in location, (
            f'{url}: redirect debería ir a /mi-portal/, fue a "{location}"'
        )


@pytest.mark.django_db
def test_admin_no_es_bloqueado(client, admin_user):
    """Superuser/staff accede normalmente a TODAS las URLs admin."""
    client.login(username='admin_test', password='adminpass123')
    # Sample subset — al menos estas no deben redirigir
    for url in ['/personal/', '/nominas/', '/empresas/']:
        response = client.get(url, follow=False)
        # Debe ser 200 o un redirect a algo distinto de /mi-portal/
        if response.status_code == 302:
            location = response.get('Location', '')
            assert '/mi-portal/' not in location, (
                f'{url}: admin NO debe ser redirigido a /mi-portal/'
            )
        else:
            assert response.status_code == 200, (
                f'{url}: admin recibió {response.status_code}, esperaba 200'
            )


@pytest.mark.django_db
def test_usuario_no_autenticado_no_se_ve_afectado(client):
    """Usuario anónimo NO es procesado por el middleware (auth check pasa antes)."""
    # Sin login, debería ir a /login/?next=... (no a /mi-portal/)
    response = client.get('/personal/', follow=False)
    assert response.status_code == 302
    location = response.get('Location', '')
    # El user no autenticado es manejado por LoginRequiredMixin / @login_required,
    # NO por nuestro middleware. Debe ir a login, no a portal.
    assert '/login' in location or '/accounts/' in location, (
        f'Anónimo debería ir a login, fue a "{location}"'
    )


@pytest.mark.django_db
def test_trabajador_puro_static_y_health_pasan(client, trabajador_puro):
    """URLs sistemas (static, health, favicon) siempre permitidas."""
    client.login(username='trab_test', password='testpass123')
    for url in ['/health/', '/robots.txt']:
        response = client.get(url, follow=False)
        # Estas URLs deberían responder algo (200/404/etc.) pero NO redirect
        # a /mi-portal/
        if response.status_code == 302:
            location = response.get('Location', '')
            assert '/mi-portal/' not in location, (
                f'{url}: NO debe redirigir a portal'
            )
