"""
Subdomain-based multi-tenant middleware for Harmoni ERP.

Routes requests based on the subdomain portion of the host header:
  miempresa.harmoni.pe  →  Empresa with subdominio='miempresa'
  localhost:8000        →  no subdomain (skip)

Must be placed AFTER SecurityMiddleware and SessionMiddleware but BEFORE
EmpresaMiddleware so that request.empresa_actual is already set by the time
EmpresaMiddleware runs.
"""
import logging

from django.conf import settings
from django.http import Http404

logger = logging.getLogger(__name__)

# Subdomains that should never be treated as tenant identifiers.
# 'demo'/'app' son de showcase/infra, no tenants: en demo.harmoni.pe queremos
# la vista consolidada (todas las empresas), no forzar una empresa por subdominio.
RESERVED_SUBDOMAINS = frozenset({
    'www', 'admin', 'api', 'static', 'media', 'mail', 'smtp',
    'ftp', 'ssh', 'ns1', 'ns2', 'cdn', 'staging', 'dev', 'demo', 'app', 'test',
})

# Root domains where subdomain routing is active.
# Configurable via settings.HARMONI_TENANT_DOMAINS; defaults below.
_DEFAULT_TENANT_DOMAINS = ['harmoni.pe', 'nexotalent.pe']

# Localhost patterns for development (subdomain via /etc/hosts or lvh.me)
_DEV_DOMAINS = ['lvh.me', 'localhost.localdomain', 'nip.io']


def _get_tenant_domains():
    """Return the list of root domains that support subdomain routing."""
    return getattr(settings, 'HARMONI_TENANT_DOMAINS', _DEFAULT_TENANT_DOMAINS)


def _extract_subdomain(host):
    """
    Extract subdomain from the host string.

    Returns (subdomain, root_domain) or (None, host) if no subdomain.

    Examples:
        'miempresa.harmoni.pe'     → ('miempresa', 'harmoni.pe')
        'harmoni.pe'               → (None, 'harmoni.pe')
        'miempresa.lvh.me:3000'    → ('miempresa', 'lvh.me')
        'localhost:8000'           → (None, 'localhost:8000')
    """
    # Strip port if present
    host_no_port = host.split(':')[0].lower().strip('.')

    # Check against configured tenant domains
    for domain in _get_tenant_domains() + _DEV_DOMAINS:
        if host_no_port == domain:
            return None, domain
        if host_no_port.endswith(f'.{domain}'):
            subdomain = host_no_port[: -(len(domain) + 1)]
            # Only single-level subdomains (no dots)
            if '.' not in subdomain:
                return subdomain, domain
            return None, host_no_port

    return None, host_no_port


class SubdomainMiddleware:
    """
    Resolves the current tenant from the request's subdomain.

    Sets request.empresa_subdomain (Empresa instance or None).
    If a subdomain is present but does not match any active Empresa,
    returns a 404 response.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa_subdomain = None
        request._subdomain_raw = None

        host = request.get_host()
        subdomain, root_domain = _extract_subdomain(host)

        if subdomain and subdomain not in RESERVED_SUBDOMAINS:
            request._subdomain_raw = subdomain

            from empresas.models import Empresa

            try:
                empresa = Empresa.objects.get(subdominio=subdomain, activa=True)
                request.empresa_subdomain = empresa
                # Also pre-set in session so EmpresaMiddleware picks it up
                if hasattr(request, 'session'):
                    request.session['empresa_actual_id'] = empresa.pk
                    request.session['empresa_actual_nombre'] = empresa.nombre_display
                logger.debug(
                    'Subdomain tenant resolved: %s → %s (pk=%s)',
                    subdomain, empresa, empresa.pk,
                )
            except Empresa.DoesNotExist:
                logger.warning(
                    'Subdomain "%s" does not match any active Empresa', subdomain
                )
                raise Http404(
                    f'No se encontró empresa con subdominio "{subdomain}". '
                    f'Verifique la URL o contacte al administrador.'
                )

        return self.get_response(request)
