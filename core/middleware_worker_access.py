"""
Worker Access Restriction Middleware

Defensa profunda: si un usuario es trabajador puro (vinculado a Personal
pero SIN is_superuser, is_staff, ni perfil responsable), NO debe poder
acceder a URLs administrativas del ERP.

Cualquier URL que NO esté en `WORKER_ALLOWED_PATTERNS` redirige al
portal del trabajador.

Beneficio vs decorar uno por uno:
- Cobertura completa de cualquier URL admin nueva que se agregue
- Una sola lista a mantener
- No depende de que el dev recuerde poner el decorador

Si necesitas habilitar un endpoint nuevo para trabajadores, agrégalo
al patrón.
"""
import re

from django.contrib import messages
from django.shortcuts import redirect


# URLs que un trabajador puro PUEDE acceder.
WORKER_ALLOWED_PATTERNS = [
    # ── Sistema / housekeeping ──
    r'^/$',                             # home: redirige a portal si es worker
    r'^/admin/login/',                  # Django admin login (lo bloquea Django)
    r'^/admin/logout/',
    r'^/accounts/',                     # auth (login/logout)
    r'^/login',
    r'^/logout',
    r'^/health/',
    r'^/offline/',
    r'^/robots\.txt',
    r'^/favicon',
    r'^/static/',
    r'^/media/',
    r'^/api/v1/auth/',                  # auth API
    r'^/sw\.js$',                       # PWA service worker
    r'^/manifest\.webmanifest$',

    # ── Portal del trabajador (todo lo que es "mi*" o "mis*") ──
    r'^/portal/',                       # alias /portal/ → /mi-portal/
    r'^/mi-portal/',
    r'^/cuenta/',                       # cambiar contraseña, etc.

    # Documentos del trabajador
    r'^/documentos/boletas/mis/',
    r'^/documentos/boletas/\d+/',       # ver boleta individual
    r'^/documentos/laborales/mis/',
    r'^/documentos/laborales/ver/\d+/',
    r'^/documentos/constancias/mis/',
    r'^/documentos/constancias/\d+/',
    r'^/documentos/archivos-hr/\d+/descargar/',

    # Vacaciones / permisos
    r'^/vacaciones/mis',
    r'^/vacaciones/solicitar',
    r'^/vacaciones/anular/',
    r'^/vacaciones/permiso/solicitar',

    # Préstamos / Viáticos / Descuentos
    r'^/prestamos/mis',
    r'^/viaticos/mis',
    r'^/descuentos/mis',

    # Nómina del trabajador
    r'^/nominas/mis-recibos',
    r'^/nominas/registros/\d+/boleta\.pdf',
    r'^/nominas/registros/\d+/constancia\.pdf',
    r'^/nominas/registros/\d+/explicar/',
    r'^/nominas/registros/\d+/confirmar-recibo/',
    r'^/nominas/consentimiento-boleta/',
    r'^/nominas/verificar/',           # verificación QR pública (sin auth)

    # Desarrollo / capacitaciones / evaluaciones
    r'^/capacitaciones/mis',
    r'^/capacitaciones/inscribirse/',
    r'^/evaluaciones/mis',
    r'^/encuestas/mis',
    r'^/encuestas/responder/',
    r'^/encuestas/pulse/responder/',  # Pulse semanal del trabajador

    # Comunicaciones
    r'^/comunicaciones/mis-',
    r'^/comunicaciones/notificaciones/',  # mark read endpoints
    r'^/comunicaciones/comunicado/\d+/confirmar/',

    # Asistencia self-service
    r'^/asistencia/mi-',
    r'^/asistencia/papeleta/crear',
    r'^/asistencia/justificacion/crear',
    r'^/asistencia/solicitud-he/crear',
    r'^/asistencia/briefing/\d+/leido/',  # AJAX marcar briefing leído

    # Onboarding del trabajador
    r'^/onboarding/checklist/personal/',

    # Empresas — solo el detalle public (no billing/admin)
    # nada — facturación y empresas es solo admin
]

WORKER_ALLOWED_COMPILED = [re.compile(p) for p in WORKER_ALLOWED_PATTERNS]


class WorkerAccessRestrictionMiddleware:
    """
    Si el usuario es trabajador puro, restringe acceso a URLs admin.

    Trabajador puro = autenticado + tiene .personal_data + NO es:
    - is_superuser
    - is_staff
    - tiene perfil_acceso.es_responsable
    - tiene perfil_acceso.puede_aprobar
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Privilegiados pasan transparente
        if request.user.is_superuser or request.user.is_staff:
            return self.get_response(request)
        perfil = getattr(request.user, 'perfil_acceso', None)
        if perfil and (
            getattr(perfil, 'es_responsable', False)
            or getattr(perfil, 'puede_aprobar', False)
        ):
            return self.get_response(request)

        # Solo activar restricción si el usuario es un trabajador vinculado
        personal = getattr(request.user, 'personal_data', None)
        if not personal:
            # Sin perfil de empleado y sin privilegios admin — caso raro.
            # Mejor no romper el flow; deja pasar.
            return self.get_response(request)

        # Es trabajador puro: validar contra allowlist
        path = request.path
        if any(p.match(path) for p in WORKER_ALLOWED_COMPILED):
            return self.get_response(request)

        # URL no permitida — redirect a portal
        messages.warning(
            request,
            'Esa sección es solo para administradores. '
            'Si necesitas ayuda contacta a RRHH.',
        )
        return redirect('/mi-portal/')
