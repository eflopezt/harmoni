"""Conftest local para tests de core.

Fix para tests que usan Client(HTTP_HOST='demo.harmoni.pe', ...):
el SubdomainMiddleware levanta 404 si no encuentra Empresa con
subdominio="demo" → asegura su existencia en la BD del test.
"""
import pytest


@pytest.fixture(autouse=True)
def _empresa_demo_para_subdomain_middleware(db):
    """Asegura que existe la Empresa 'demo' para tests con HTTP_HOST=demo.harmoni.pe.

    Auto-aplicado a TODOS los tests que pidan `db`. Idempotente — usa get_or_create.
    """
    from empresas.models import Empresa
    Empresa.objects.get_or_create(
        subdominio='demo',
        defaults={
            'razon_social': 'Harmoni Demo SAC',
            'ruc': '20999999999',
            'plan': 'PROFESIONAL',
            'activa': True,
        },
    )
