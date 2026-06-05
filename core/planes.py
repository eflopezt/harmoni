"""
Fuente ÚNICA de verdad de los planes comerciales de Harmoni y del gating por
módulos. Todo lo demás (modelo Empresa, middleware, context processor, api_plan,
UI de precios) debe leer de aquí.

4 planes ACUMULATIVOS por módulos (cada uno incluye lo del anterior):

  Nivel 1 · ASISTENCIA  — solo control de asistencia
  Nivel 2 · PLANILLA    — + nóminas/boletas/liquidación + SUNAT + contratos/préstamos
  Nivel 3 · TALENTO     — + gestión de RRHH (evaluaciones, capacitaciones, encuestas,
                            organigrama, onboarding, disciplinaria, analytics, viáticos)
  Nivel 4 · SUITE       — + reclutamiento (storage de CVs) + portal del empleado + IA

El middleware bloquea una URL si el módulo al que pertenece exige un nivel mayor
al del plan de la empresa. Las empresas sin plan tope ven un upsell a /upgrade/.
"""
import re

# ─────────────────────────────────────────────────────────────────────────────
# PLANES
# ─────────────────────────────────────────────────────────────────────────────
# code → metadata. `nivel` es el orden acumulativo (1..4). `precio` en S//mes
# (ajustable). `max_trab` = tope de colaboradores (None = sin tope).
PLANES = {
    'ASISTENCIA': {
        'nombre':   'Asistencia',
        'nivel':    1,
        'precio':   99,
        'max_trab': 50,
        'tagline':  'Control de asistencia, papeletas y horas extra.',
    },
    'PLANILLA': {
        'nombre':   'Planilla',
        'nivel':    2,
        'precio':   199,
        'max_trab': 100,
        'tagline':  'Todo el ciclo de pago: nóminas, boletas, liquidación y SUNAT.',
    },
    'TALENTO': {
        'nombre':   'Talento',
        'nivel':    3,
        'precio':   399,
        'max_trab': 300,
        'tagline':  'Gestión de RRHH: evaluaciones, capacitaciones, clima y más.',
    },
    'SUITE': {
        'nombre':   'Suite',
        'nivel':    4,
        'precio':   699,
        'max_trab': None,
        'tagline':  'RRHH completo: reclutamiento, portal del empleado e IA.',
    },
}

PLAN_DEFAULT = 'SUITE'          # default seguro para empresas sin plan explícito
PLAN_MIN     = 'ASISTENCIA'

# Choices para el modelo (display con precio).
def plan_choices():
    out = []
    for code, p in sorted(PLANES.items(), key=lambda kv: kv[1]['nivel']):
        precio = f"S/ {p['precio']}/mes" if p['precio'] else 'Personalizado'
        tope = f"hasta {p['max_trab']}" if p['max_trab'] else '300+'
        out.append((code, f"{p['nombre']} — {precio} ({tope} colaboradores)"))
    return out


# ─────────────────────────────────────────────────────────────────────────────
# MÓDULOS — cada módulo exige un nivel mínimo de plan y agrupa patrones de URL.
# El nivel del módulo = nivel del plan más bajo que lo incluye.
# (Lo no listado aquí está disponible desde el nivel 1: home, empleados, perfil,
#  asistencia/tareo, papeletas, vacaciones, documentos básicos, mi cuenta, etc.)
# ─────────────────────────────────────────────────────────────────────────────
MODULOS = {
    # ── Nivel 2 · PLANILLA ──────────────────────────────────────────────
    'nominas': {
        'nombre': 'Nóminas y boletas', 'nivel': 2,
        'patrones': [r'^/nominas/'],
    },
    'contratos': {
        'nombre': 'Contratos', 'nivel': 2,
        'patrones': [r'^/personal/contratos/'],
    },
    'prestamos': {
        'nombre': 'Préstamos', 'nivel': 2,
        'patrones': [r'^/prestamos/'],
    },
    'integraciones': {
        'nombre': 'Exportaciones SUNAT (PLAME/AFPNet/T-Registro/banco)', 'nivel': 2,
        'patrones': [r'^/integraciones/'],
    },

    # ── Nivel 3 · TALENTO ───────────────────────────────────────────────
    'salarios': {
        'nombre': 'Bandas salariales', 'nivel': 3,
        'patrones': [r'^/salarios/'],
    },
    'organigrama': {
        'nombre': 'Organigrama', 'nivel': 3,
        'patrones': [r'^/personal/organigrama/', r'^/personal/api/organigrama'],
    },
    'evaluaciones': {
        'nombre': 'Evaluaciones de desempeño', 'nivel': 3,
        'patrones': [r'^/evaluaciones/'],
    },
    'capacitaciones': {
        'nombre': 'Capacitaciones', 'nivel': 3,
        'patrones': [r'^/capacitaciones/'],
    },
    'encuestas': {
        'nombre': 'Encuestas y clima', 'nivel': 3,
        'patrones': [r'^/encuestas/'],
    },
    'disciplinaria': {
        'nombre': 'Gestión disciplinaria', 'nivel': 3,
        'patrones': [r'^/disciplinaria/'],
    },
    'onboarding': {
        'nombre': 'Onboarding / Offboarding', 'nivel': 3,
        'patrones': [r'^/onboarding/'],
    },
    'calendario': {
        'nombre': 'Calendario laboral', 'nivel': 3,
        'patrones': [r'^/calendario/'],
    },
    'viaticos': {
        'nombre': 'Viáticos', 'nivel': 3,
        'patrones': [r'^/viaticos/'],
    },
    'comunicaciones': {
        'nombre': 'Comunicaciones internas', 'nivel': 3,
        'patrones': [r'^/comunicaciones/'],
    },
    'analytics': {
        'nombre': 'Analytics y Dashboard Ejecutivo', 'nivel': 3,
        'patrones': [
            r'^/analytics/',
            r'^/sistema/dashboard/ejecutivo/',
            r'^/sistema/reporte-bi-mensual/',
        ],
    },
    'workflows': {
        'nombre': 'Workflows de aprobación', 'nivel': 3,
        'patrones': [r'^/workflows/'],
    },
    'gastronomia': {
        'nombre': 'Módulos de gastronomía (Pulse, Roster gastro, Briefing)', 'nivel': 3,
        'patrones': [
            r'^/empresas/pulse/', r'^/roster/gastro/',
            r'^/personal/roster/gastro/', r'^/asistencia/briefing/',
        ],
    },

    # ── Nivel 2 · PLANILLA — reportes avanzados / PDFs ──────────────────
    # (El panel básico de reportes y el listado quedan en nivel 1; lo avanzado
    #  —cruces, masivos, PDFs, envíos por email— exige Planilla.)
    'reportes_avanzados': {
        'nombre': 'Reportes avanzados y PDFs', 'nivel': 2,
        'patrones': [
            r'^/reportes/planilla/pdf/', r'^/reportes/personal/pdf/',
            r'^/reportes/asistencia/pdf/', r'^/reportes/vacaciones/pdf/',
            r'^/asistencia/reportes/areas/', r'^/asistencia/reportes/pivote/',
            r'^/asistencia/reportes/kpis-cross/', r'^/asistencia/reportes/masivo/',
            r'^/asistencia/reportes/enviar-masivo/',
            r'^/asistencia/reportes/\d+/pdf/', r'^/asistencia/reportes/\d+/enviar/',
            r'^/documentos/legajo/\d+/pdf/',
        ],
    },

    # ── Nivel 4 · SUITE ─────────────────────────────────────────────────
    'reclutamiento': {
        'nombre': 'Reclutamiento y banco de talento', 'nivel': 4,
        'patrones': [r'^/reclutamiento/', r'^/api/v1/reclutamiento/'],
    },
    'portal': {
        'nombre': 'Portal del empleado', 'nivel': 4,
        'patrones': [
            r'^/portal/', r'^/mi-portal/',
            r'^/documentos/boletas/mis/', r'^/api/v1/portal/',
            r'^/asistencia/solicitudes-he/',
            r'^/nominas/boletas/\d+/notificar/',
            r'^/nominas/notificar/',
            r'^/documentos/vencimientos/notificar/',
        ],
    },
}

# Compilar patrones una sola vez: lista de (regex, nivel_requerido, modulo_key)
_PATRONES = []
for _key, _m in MODULOS.items():
    for _p in _m['patrones']:
        _PATRONES.append((re.compile(_p), _m['nivel'], _key))


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def plan_nivel(plan_code):
    """Nivel (1..4) del plan. Códigos desconocidos → nivel del default."""
    p = PLANES.get(plan_code)
    if p:
        return p['nivel']
    return PLANES[PLAN_DEFAULT]['nivel']


def plan_incluye_modulo(plan_code, modulo_key):
    """True si el plan incluye el módulo dado."""
    m = MODULOS.get(modulo_key)
    if not m:
        return True  # módulo no gateado → disponible siempre
    return plan_nivel(plan_code) >= m['nivel']


def nivel_requerido_path(path):
    """Devuelve (nivel_requerido, modulo_key) para una URL, o (1, None) si la
    ruta no está gateada (disponible desde el nivel 1)."""
    for regex, nivel, key in _PATRONES:
        if regex.match(path):
            return nivel, key
    return 1, None


def plan_permite_path(plan_code, path):
    """True si el plan puede acceder a la URL."""
    nivel_req, _ = nivel_requerido_path(path)
    return plan_nivel(plan_code) >= nivel_req


def modulos_por_nivel(plan_code):
    """Dict {modulo_key: bool incluido} según el plan — para el context processor
    (ocultar UI de módulos no contratados)."""
    nivel = plan_nivel(plan_code)
    return {k: (nivel >= m['nivel']) for k, m in MODULOS.items()}


def plan_display(plan_code):
    p = PLANES.get(plan_code, PLANES[PLAN_DEFAULT])
    precio = f"S/ {p['precio']}/mes" if p['precio'] else 'Personalizado'
    return f"{p['nombre']} — {precio}"


def plan_max_trabajadores(plan_code):
    return PLANES.get(plan_code, PLANES[PLAN_DEFAULT])['max_trab']
