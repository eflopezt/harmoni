"""
Middleware Plan Starter — restringe acceso a features enterprise.

Para usuarios del Plan Starter (S/149/mes — 30 colaboradores), bloquea:
- Reclutamiento (Pipeline, banco talento, comparar, etc.)
- IA y AI features (predictor rotación, AI summary CV)
- Evaluaciones 360
- BI Excel + Dashboard Ejecutivo cross-modulo
- Capacitaciones gastro BPM/HACCP
- Pulse del Grupo / Briefing / Cuadrícula gastro
- Workflows engine
- Bandas salariales / Análisis equidad
- Préstamos workflow
- Comunicaciones masivas (campañas WhatsApp)
- Onboarding gastronomía

Usuarios identificados por:
1. Username en STARTER_USERNAMES (hardcoded en settings o aquí)
2. (Futuro) Atributo en perfil/empresa

Si el user intenta acceder a feature bloqueada → redirect a /upgrade/
con mensaje explicativo del plan necesario.
"""
import logging
import re

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.urls import reverse

logger = logging.getLogger('core.plan_starter')


# Usuarios identificados como Plan Starter
# (en producción esto vendría de Empresa.plan o User.profile.plan)
STARTER_USERNAMES = ['demo2']


# Prefijos URL bloqueados para Plan Starter
# Match con re.match al inicio de request.path
STARTER_BLOCKED_PATTERNS = [
    # Reclutamiento — entero NO incluido en Starter
    r'^/reclutamiento/',
    # Analytics IA
    r'^/analytics/predictor-rotacion/',
    # Evaluaciones 360 (la 360 sí, lo básico está OK)
    r'^/evaluaciones/360/',
    # Dashboard Ejecutivo cross-modulo
    r'^/sistema/dashboard/ejecutivo/',
    # BI Excel mensual
    r'^/sistema/reporte-bi-mensual/',
    # Capacitaciones gastro
    r'^/capacitaciones/gastro/',
    # Onboarding gastronomía
    r'^/onboarding/gastro/',
    # Pulse del Grupo (es para multi-local)
    r'^/empresas/pulse/',
    # Briefing del día (gastro)
    r'^/asistencia/briefing/',
    # Workflows engine
    r'^/workflows/',
    # Salarios (bandas + equidad)
    r'^/salarios/',
    # Comunicaciones masivas
    r'^/comunicaciones/campanas/',
    # WhatsApp
    r'^/comunicaciones/whatsapp/',
    # Préstamos (no en starter)
    r'^/prestamos/',
    # Roster Quincenal Gastro
    r'^/roster/gastro/',
    # Encuestas Pulse semanales (gastro)
    r'^/encuestas/pulse/',
    # API REST avanzada
    r'^/api/v1/reclutamiento/',
]

# Compilar patterns una vez
STARTER_BLOCKED_RE = [re.compile(p) for p in STARTER_BLOCKED_PATTERNS]


def is_starter_user(user):
    """Devuelve True si el user está en plan Starter."""
    if not user.is_authenticated:
        return False
    return user.username in STARTER_USERNAMES


def is_blocked_path(path):
    """Devuelve True si la URL está bloqueada para Starter."""
    for pat in STARTER_BLOCKED_RE:
        if pat.match(path):
            return True
    return False


class PlanStarterMiddleware:
    """Restringe acceso a features enterprise para users Starter."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Solo aplica a users autenticados de Plan Starter
        if not is_starter_user(request.user):
            return self.get_response(request)

        # Permitir siempre: admin, logout, static, api de auth, upgrade
        path = request.path
        ALWAYS_ALLOW = (
            '/admin/', '/logout/', '/static/', '/media/',
            '/upgrade/', '/login/', '/cuenta/',
        )
        if any(path.startswith(p) for p in ALWAYS_ALLOW):
            return self.get_response(request)

        # Verificar si está bloqueado
        if is_blocked_path(path):
            logger.info(
                f"Plan Starter bloqueado: {request.user.username} → {path}"
            )
            try:
                messages.warning(
                    request,
                    'Esta funcionalidad no está incluida en tu Plan Starter. '
                    'Habla con ventas para upgrade a un plan superior.'
                )
            except Exception:
                pass
            try:
                return HttpResponseRedirect(reverse('upgrade_plan'))
            except Exception:
                # Si la URL upgrade no existe, redirect a home
                return HttpResponseRedirect('/')

        return self.get_response(request)
