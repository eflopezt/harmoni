"""
Middleware Plan Starter — restringe acceso a features enterprise.

═══════════════════════════════════════════════════════════════════════
Plan Starter (S/149/mes — 30 colaboradores) — alcance mínimo:
═══════════════════════════════════════════════════════════════════════

✅ INCLUIDO (lo mínimo necesario para operar planilla):
- Personal (CRUD básico, sin división RCO/Staff)
- Asistencia (registro + 1 reporte matricial básico)
- Planilla mensual (cálculos completos: AFP/ONP, IGV, gratif, CTS, etc.)
- Boleta PDF (generación local — no envío al trabajador)
- Papeletas (admin entra permisos, licencias, vacaciones manuales)
- Vacaciones (admin gestiona — sin solicitud del trabajador)
- Exportes contables y SUNAT (legal)
- Cuenta / configuración básica

❌ NO INCLUIDO (todo lo demás):
- Portal del colaborador (sin login de trabajadores)
- Envío/notificación de boletas a trabajadores
- Solicitudes de horas extras desde portal
- Reclutamiento (Pipeline, banco talento, IA matching, scoring)
- Capacitaciones / Evaluaciones 360 / Disciplinaria formal
- Organigrama visual / Calendario laboral / Contratos formales
- Roster matricial / Banco de horas / Workflows
- Bandas salariales / Préstamos / Comunicaciones masivas
- Pulse del Grupo / Briefing / Onboarding gastronomía
- BI Excel cross-modulo / Dashboard Ejecutivo / IA Predictor Rotación
- PDFs avanzados (solo boleta y constancia legal)

═══════════════════════════════════════════════════════════════════════
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


# Usuarios identificados como Plan Starter (fallback / legacy).
# La identificación PRIMARIA es vía Empresa.plan == 'STARTER' (Personal → Empresa).
# Este whitelist queda como fallback para demo users que no tengan Personal asociado.
STARTER_USERNAMES = ['demo2']


# Prefijos URL bloqueados para Plan Starter
# Match con re.match al inicio de request.path
STARTER_BLOCKED_PATTERNS = [
    # ─── Reclutamiento (entero) ───
    r'^/reclutamiento/',
    r'^/api/v1/reclutamiento/',

    # ─── BI / Dashboard Ejecutivo (sistema) ───
    r'^/sistema/dashboard/ejecutivo/',
    r'^/sistema/reporte-bi-mensual/',

    # ─── Evaluaciones (entero) — HR avanzado, no es Starter ───
    r'^/evaluaciones/',

    # ─── Capacitaciones (entero) ───
    r'^/capacitaciones/',

    # ─── Encuestas (entero) — sin portal, sin encuestas ───
    r'^/encuestas/',

    # ─── Analytics (entero) — KPIs avanzados son Profesional+ ───
    r'^/analytics/',

    # ─── Integraciones externas (Synkro, SAP, etc.) — enterprise ───
    r'^/integraciones/',

    # ─── Viáticos — módulo adicional, no core de planilla ───
    r'^/viaticos/',

    # ─── Comunicaciones (entero) — sin portal no hay comunicación interna ───
    r'^/comunicaciones/',

    # ─── Onboarding gastronomía ───
    r'^/onboarding/gastro/',

    # ─── Multi-empresa / Pulse / Briefing / Roster gastro ───
    r'^/empresas/pulse/',
    r'^/asistencia/briefing/',
    r'^/roster/gastro/',
    r'^/personal/roster/gastro/',
    # ─── Workflows / Salarios / Préstamos / Disciplinaria ───
    r'^/workflows/',
    r'^/salarios/',
    r'^/prestamos/',
    r'^/disciplinaria/',

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

    # ─── Portal del colaborador (entero) — Starter no incluye portal ───
    r'^/portal/',
    r'^/mi-portal/',
    r'^/documentos/boletas/mis/',
    r'^/api/v1/portal/',

    # ─── Solicitudes desde el portal (HE, vacaciones, papeletas worker) ───
    r'^/asistencia/solicitudes-he/',

    # ─── Notificaciones a trabajadores (sin portal, no se notifica) ───
    r'^/nominas/boletas/\d+/notificar/',
    r'^/nominas/notificar/',
    r'^/documentos/vencimientos/notificar/',
    r'^/disciplinaria/\d+/notificar/',

    # ─── PDFs de reportes avanzados (Starter no genera PDFs salvo boletas/constancias) ───
    r'^/reportes/planilla/pdf/',
    r'^/reportes/personal/pdf/',
    r'^/reportes/asistencia/pdf/',
    r'^/reportes/vacaciones/pdf/',
    # ─── Reportes avanzados de asistencia (solo matricial básico para Starter) ───
    r'^/asistencia/reportes/areas/',          # Reporte por áreas + envío email
    r'^/asistencia/reportes/pivote/',         # Pivote cross-empresa
    r'^/asistencia/reportes/kpis-cross/',     # KPIs cross-empresa
    r'^/asistencia/reportes/\d+/pdf/',        # PDF individual
    r'^/asistencia/reportes/\d+/enviar/',     # Envío por email
    r'^/asistencia/reportes/masivo/',         # PDF masivo
    r'^/asistencia/reportes/enviar-masivo/',  # Envío masivo
]

# Compilar patterns una vez
STARTER_BLOCKED_RE = [re.compile(p) for p in STARTER_BLOCKED_PATTERNS]


def is_starter_user(user):
    """
    Devuelve True si el user pertenece a una empresa con Plan Starter.

    Resolución (en orden de prioridad):
    1. Empresa.plan == 'STARTER' via Personal.empresa  (caso producción)
    2. Username en STARTER_USERNAMES                    (caso demo / fallback)
    """
    if not user.is_authenticated:
        return False

    # 1. Resolver via Personal → Empresa.plan
    try:
        personal = getattr(user, 'personal', None)
        if personal and getattr(personal, 'empresa', None):
            if personal.empresa.plan == 'STARTER':
                return True
    except Exception:
        # Si el modelo Personal no existe aún, o la relación falla → fallback
        pass

    # 2. Fallback por username (demos)
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
