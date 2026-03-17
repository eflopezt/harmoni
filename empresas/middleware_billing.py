"""
Billing Middleware — Controla acceso según estado de suscripción.

Lógica:
- ACTIVA / TRIAL (con días restantes): acceso completo
- TRIAL vencido: redirect a página de pago
- SUSPENDIDA: warning banner, acceso read-only (GET permitido, POST bloqueado)
- CANCELADA / sin suscripción: redirect a página de pago
- Superusers: siempre pasan sin restricción
"""
import re
from django.shortcuts import redirect
from django.contrib import messages
from django.http import JsonResponse


# URLs que siempre deben ser accesibles (login, logout, billing, admin, etc.)
EXEMPT_URL_PATTERNS = [
    r'^/admin/',
    r'^/accounts/',
    r'^/login',
    r'^/logout',
    r'^/health/',
    r'^/robots\.txt',
    r'^/offline/',
    r'^/empresas/billing/',
    r'^/static/',
    r'^/media/',
    r'^/api/v1/auth/',
    r'^/$',           # landing
]

EXEMPT_COMPILED = [re.compile(p) for p in EXEMPT_URL_PATTERNS]


class BillingMiddleware:
    """
    Verifica que la empresa activa tenga una suscripción válida.

    Inyecta `request.suscripcion` y `request.billing_status` para uso en templates.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Defaults
        request.suscripcion = None
        request.billing_status = None
        request.billing_warning = None

        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superusers
        if request.user.is_superuser:
            # Still load suscripcion for display purposes
            self._load_suscripcion(request)
            return self.get_response(request)

        # Skip exempt URLs
        path = request.path
        if any(pat.match(path) for pat in EXEMPT_COMPILED):
            return self.get_response(request)

        # Load suscripcion
        self._load_suscripcion(request)
        suscripcion = request.suscripcion

        # No empresa = skip billing check (shouldn't happen in normal flow)
        empresa = getattr(request, 'empresa_actual', None)
        if not empresa:
            return self.get_response(request)

        # No suscripcion = redirect to billing
        if not suscripcion:
            request.billing_status = 'NO_SUBSCRIPTION'
            if not self._is_billing_url(path):
                messages.warning(
                    request,
                    'Su empresa no tiene una suscripción activa. '
                    'Por favor contacte al administrador.',
                )
                return redirect('billing_dashboard')
            return self.get_response(request)

        # Check status
        if suscripcion.estado == 'ACTIVA':
            request.billing_status = 'ACTIVE'
            return self.get_response(request)

        if suscripcion.estado == 'TRIAL':
            if suscripcion.trial_vencido:
                request.billing_status = 'TRIAL_EXPIRED'
                if not self._is_billing_url(path):
                    messages.warning(
                        request,
                        'Su periodo de prueba ha expirado. '
                        'Elija un plan para continuar usando Harmoni.',
                    )
                    return redirect('billing_dashboard')
            else:
                request.billing_status = 'TRIAL'
                request.billing_warning = (
                    f'Periodo de prueba: {suscripcion.dias_trial_restantes} '
                    f'días restantes.'
                )
            return self.get_response(request)

        if suscripcion.estado == 'SUSPENDIDA':
            request.billing_status = 'SUSPENDED'
            request.billing_warning = (
                'Su suscripción está suspendida. '
                'Realice su pago para restaurar el acceso completo.'
            )
            # Allow GET (read-only), block POST/PUT/DELETE
            if request.method != 'GET':
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'error': 'Suscripción suspendida. Solo lectura.'},
                        status=403,
                    )
                messages.error(
                    request,
                    'Su suscripción está suspendida. '
                    'No puede realizar cambios hasta regularizar el pago.',
                )
                return redirect('billing_dashboard')
            return self.get_response(request)

        if suscripcion.estado == 'CANCELADA':
            request.billing_status = 'CANCELLED'
            if not self._is_billing_url(path):
                messages.error(
                    request,
                    'Su suscripción ha sido cancelada. '
                    'Contacte al administrador para reactivarla.',
                )
                return redirect('billing_dashboard')
            return self.get_response(request)

        return self.get_response(request)

    def _load_suscripcion(self, request):
        """Load suscripcion for the current empresa."""
        empresa = getattr(request, 'empresa_actual', None)
        if not empresa:
            return
        try:
            from empresas.models_billing import Suscripcion
            request.suscripcion = Suscripcion.objects.select_related('plan').get(
                empresa=empresa,
            )
            request.billing_status = request.suscripcion.estado
        except Exception:
            request.suscripcion = None

    def _is_billing_url(self, path):
        """Check if the URL is a billing-related URL."""
        return path.startswith('/empresas/billing/')
