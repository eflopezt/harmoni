"""
Enforcement de MFA (TOTP) por sesión.

Política deliberadamente conservadora para no bloquear el acceso a prod:
- Si el usuario tiene un dispositivo TOTP CONFIRMADO y aún no verificó el
  código en esta sesión → se le redirige a /cuenta/2fa/verificar/.
- Si NO tiene dispositivo, no se le bloquea (el setup es opt-in y se
  promueve vía banner/Centro de Acción para staff). Así un problema con
  la app autenticadora nunca deja a la empresa sin nómina; el usuario
  puede desactivar MFA solo confirmando su contraseña.
"""
from django.shortcuts import redirect
from django.urls import reverse

# Prefijos siempre permitidos sin verificación (evitar loops y dejar salir)
_EXEMPT_PREFIXES = (
    '/cuenta/2fa/',
    '/accounts/logout/',
    '/logout',
    '/static/',
    '/media/',
    '/health/',
    '/api/',          # la API usa JWT, no sesión web
)


class MFAEnforceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated:
            path = request.path
            if not any(path.startswith(p) for p in _EXEMPT_PREFIXES):
                if self._requiere_verificacion(request, user):
                    return redirect(
                        f"{reverse('mfa_verificar')}?next={request.get_full_path()}"
                    )
        return self.get_response(request)

    @staticmethod
    def _requiere_verificacion(request, user):
        # is_verified() lo inyecta django_otp.middleware.OTPMiddleware
        verificado = getattr(user, 'is_verified', None)
        if verificado is None or verificado():
            return False
        try:
            from django_otp.plugins.otp_totp.models import TOTPDevice
            return TOTPDevice.objects.filter(user=user, confirmed=True).exists()
        except Exception:
            return False
