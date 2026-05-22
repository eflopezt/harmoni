"""
Middleware Plan Starter — restringe acceso a features enterprise.

Para usuarios del Plan Starter (S/149/mes — 30 colaboradores), bloquea:
- Reclutamiento (Pipeline, banco talento, comparar, etc.)
- IA y AI features (predictor rotación, AI summary CV)
- Evaluaciones 360
- BI Excel + Dashboard Ejecutivo cross-modulo
- Capacitaciones (entero — agencia pequeña no gestiona capacitación formal)
- Pulse del Grupo / Briefing / Cuadrícula gastro
- Workflows engine
- Bandas salariales / Análisis equidad
- Préstamos workflow
- Comunicaciones masivas (campañas WhatsApp)
- Onboarding gastronomía
- Organigrama (gestión visual avanzada)
- Calendario laboral (planning avanzado)
- Contratos (gestión formal de contratos / renovaciones / adendas)
- Roster matricial (vista avanzada — solo lista plana)
- Disciplinaria (medidas formales con carta PDF)
- Banco de horas
- Documentos legajo PDF
- PDFs de reportes (solo Excel/HTML para Starter)
- División RCO/Staff (Starter solo maneja STAFF)

Mantiene acceso a:
- Personal (CRUD básico)
- Asistencia (registro + 1 reporte matricial básico)
- Planillas (boletas PDF — requisito legal)
- Vacaciones (constancia PDF — requisito legal)
- Portal del colaborador
- Cuenta / configuración básica

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
    # ─── Reclutamiento (entero) ───
    r'^/reclutamiento/',
    r'^/api/v1/reclutamiento/',

    # ─── Analytics / IA / BI ───
    r'^/analytics/predictor-rotacion/',
    r'^/sistema/dashboard/ejecutivo/',
    r'^/sistema/reporte-bi-mensual/',

    # ─── Evaluaciones 360 ───
    r'^/evaluaciones/360/',

    # ─── Capacitaciones (entero) ───
    r'^/capacitaciones/',

    # ─── Onboarding gastronomía ───
    r'^/onboarding/gastro/',

    # ─── Multi-empresa / Pulse / Briefing / Roster gastro ───
    r'^/empresas/pulse/',
    r'^/asistencia/briefing/',
    r'^/roster/gastro/',
    r'^/personal/roster/gastro/',
    r'^/encuestas/pulse/',

    # ─── Workflows / Salarios / Préstamos / Disciplinaria ───
    r'^/workflows/',
    r'^/salarios/',
    r'^/prestamos/',
    r'^/disciplinaria/',

    # ─── Comunicaciones masivas ───
    r'^/comunicaciones/campanas/',
    r'^/comunicaciones/whatsapp/',

    # ─── Organigrama (gestión visual avanzada) ───
    r'^/personal/organigrama/',
    r'^/personal/api/organigrama',
    r'^/portal/organigrama/',

    # ─── Calendario laboral (entero) ───
    r'^/calendario/',

    # ─── Contratos (gestión formal — bloqueado para Starter) ───
    r'^/personal/contratos/',

    # ─── Roster matricial (vista avanzada — solo lista plana) ───
    r'^/personal/roster/matricial/',

    # ─── Banco de horas ───
    r'^/asistencia/banco-horas/',

    # ─── Documentos legajo PDF ───
    r'^/documentos/legajo/\d+/pdf/',

    # ─── PDFs de reportes avanzados (Starter no genera PDFs salvo boletas/constancias) ───
    r'^/reportes/planilla/pdf/',
    r'^/reportes/personal/pdf/',
    r'^/reportes/asistencia/pdf/',
    r'^/reportes/vacaciones/pdf/',
    r'^/asistencia/reportes/areas/pdf/',
    r'^/asistencia/reportes/pivote/pdf/',
    r'^/asistencia/reportes/\d+/pdf/',
    r'^/asistencia/reportes/masivo/',
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
