"""Smoke de crawl autenticado — ninguna URL GET sin parámetros debe dar 500.

Recorre todas las rutas GET-eables del proyecto como superusuario y verifica
que ninguna devuelva 5xx. Es el guardarraíl que automatiza el crawl manual de
la estabilización 2026-05-29 (que encontró el template faltante de KPIs y
varios 500). Corre con DB de test (semilla mínima): un 5xx aquí = la vista no
maneja el caso sin datos, que es justo lo que queremos atrapar.
"""
import pytest
from django.urls import get_resolver

from empresas.models import Empresa


def _collect(resolver, prefix=''):
    out = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            out += _collect(p, prefix + str(p.pattern))
        else:
            out.append(prefix + str(p.pattern))
    return out


def _gettable_urls():
    urls = []
    for pat in _collect(get_resolver()):
        if '<' in pat or '(?P' in pat or '(' in pat:
            continue
        url = '/' + pat.lstrip('^').rstrip('$')
        if not url.endswith('/') and '.' not in url.split('/')[-1]:
            url += '/'
        if any(x in url for x in ['admin/', 'api/', '__debug__', 'media/',
                                  'static/', 'logout', 'jsi18n', '.json',
                                  'wa/sidecar', 'sync-now', 'sync/now']):
            continue
        urls.append(url)
    return sorted(set(urls))


@pytest.fixture
def admin_client(client, db, django_user_model):
    Empresa.objects.get_or_create(
        ruc='20100100100',
        defaults={'razon_social': 'Smoke SAC', 'plan': 'SUITE', 'activa': True},
    )
    u = django_user_model.objects.create_superuser(
        username='smoke_admin', password='x', email='smoke@test.com',
    )
    client.force_login(u)
    return client


def test_no_url_returns_500(admin_client):
    """Ninguna URL GET sin parámetros devuelve 5xx como superusuario."""
    failures = []
    for url in _gettable_urls():
        try:
            r = admin_client.get(url, follow=False)
        except Exception as e:  # noqa: BLE001
            failures.append(f'{url} → EXC {type(e).__name__}: {str(e)[:120]}')
            continue
        if r.status_code >= 500:
            failures.append(f'{url} → {r.status_code}')
    assert not failures, (
        f'{len(failures)} URL(s) GET devuelven 5xx:\n' + '\n'.join(failures)
    )
