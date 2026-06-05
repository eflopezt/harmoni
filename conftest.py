"""Conftest raíz para toda la suite pytest.

Helpers globales que aplican a TODOS los tests del proyecto.
"""
import pytest


@pytest.fixture(autouse=True)
def _empresa_demo_para_subdomain_middleware(db):
    """Asegura que existe la Empresa 'demo' para tests que usan
    Client(HTTP_HOST='demo.harmoni.pe', ...).

    El SubdomainMiddleware levanta Http404 si el subdomain del HOST no
    matchea ninguna Empresa activa. Como Django test client por default
    pone 'testserver' pero muchos tests override-an el HOST para simular
    el subdomain de prod, sin esta fixture todos esos tests reciben 404.

    Auto-aplicado a todo test que reciba `db`. Idempotente vía get_or_create.

    Si tu test necesita VER el comportamiento 404 del middleware, puedes
    desactivarlo explícitamente con: @pytest.mark.usefixtures('_no_empresa_demo')
    """
    from empresas.models import Empresa
    Empresa.objects.get_or_create(
        subdominio='demo',
        defaults={
            'razon_social': 'Harmoni Demo SAC',
            'ruc': '20999999999',
            'plan': 'SUITE',
            'activa': True,
        },
    )
