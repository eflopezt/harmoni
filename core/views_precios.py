"""
Página de precios pública — para enviar a prospectos.

URL: /precios/  (público, sin login)
"""
from django.shortcuts import render

from core.planes import PLANES as _PLANES, plan_max_trabajadores


# Bullets curados por plan (marketing). Precios/topes salen de core/planes.py.
_FEATURES = {
    'ASISTENCIA': {
        'tagline': 'Control de asistencia para tu equipo',
        'color': '#0891b2', 'destacado': False,
        'features': [
            'Tareo diario (importación Excel/biométrico)',
            'Papeletas y permisos',
            'Horas extra y banco de horas',
            'Reportes de asistencia',
            'Vacaciones (gestión admin)',
            'Personal y áreas',
            'Soporte por email',
        ],
        'features_no': [
            'Planilla y boletas', 'Exportaciones SUNAT',
            'Gestión de talento', 'Reclutamiento y portal',
        ],
    },
    'PLANILLA': {
        'tagline': 'El ciclo de pago completo, sin Excel',
        'color': '#0f766e', 'destacado': True,
        'features': [
            '— Todo lo de Asistencia +',
            'Planilla mensual con cálculo automático',
            'Boletas (DS 009-2011-TR) y liquidaciones',
            'Conceptos, contratos y préstamos',
            'Workflow del mes guiado',
            'Exportaciones SUNAT: PLAME, AFPNet, T-Registro',
            'Archivo de pago a banco (neto)',
            'Reportes avanzados y PDFs',
            'Soporte por chat',
        ],
        'features_no': [
            'Evaluaciones, capacitaciones, clima',
            'Reclutamiento y banco de talento',
            'Portal del empleado',
        ],
    },
    'TALENTO': {
        'tagline': 'Gestión de RRHH de punta a punta',
        'color': '#7c3aed', 'destacado': False,
        'features': [
            '— Todo lo de Planilla +',
            'Evaluaciones de desempeño',
            'Capacitaciones',
            'Encuestas y clima laboral',
            'Organigrama y onboarding/offboarding',
            'Gestión disciplinaria',
            'Viáticos y calendario laboral',
            'Analytics y Dashboard Ejecutivo',
            'Workflows de aprobación',
        ],
        'features_no': [
            'Reclutamiento y banco de talento',
            'Portal del empleado',
            'IA',
        ],
    },
    'SUITE': {
        'tagline': 'RRHH completo con reclutamiento, portal e IA',
        'color': '#0d2b27', 'destacado': False,
        'features': [
            '— Todo lo de Talento +',
            'Reclutamiento: pipeline, vacantes, banco de talento',
            'CV parser y comparador de candidatos',
            'Portal del empleado (boletas, solicitudes, self-service)',
            'IA de RRHH',
            'Módulos de gastronomía (Pulse, Briefing, Roster)',
            'Multi-empresa (multi-RUC)',
            'Soporte prioritario',
        ],
        'features_no': [],
    },
}


def _construir_planes():
    out = []
    for code, meta in sorted(_PLANES.items(), key=lambda kv: kv[1]['nivel']):
        f = _FEATURES.get(code, {})
        tope = plan_max_trabajadores(code)
        out.append({
            'codigo':        code,
            'nombre':        meta['nombre'],
            'precio':        meta['precio'],
            'precio_label':  None if meta['precio'] else 'Personalizado',
            'colaboradores': f'hasta {tope}' if tope else '300+',
            'tagline':       f.get('tagline', meta.get('tagline', '')),
            'color':         f.get('color', '#0f766e'),
            'destacado':     f.get('destacado', False),
            'features':      f.get('features', []),
            'features_no':   f.get('features_no', []),
        })
    return out


PLANES = _construir_planes()


FAQS = [
    {
        'q': '¿Puedo cambiar de plan cuando quiera?',
        'a': 'Sí. Puedes subir o bajar de plan en cualquier momento desde tu panel admin. El cobro se prorratea automáticamente.',
    },
    {
        'q': '¿Hay un período de prueba?',
        'a': 'Sí. 30 días gratuitos sin tarjeta de crédito. Si no te convence, no pagas nada.',
    },
    {
        'q': '¿Qué pasa si supero el número de trabajadores del plan?',
        'a': 'El sistema te avisa al 80% del cap y al 100% bloquea altas nuevas. Te recomendamos upgrade — proceso automático sin pérdida de datos.',
    },
    {
        'q': '¿Los precios incluyen IGV?',
        'a': 'No. Los precios mostrados son sin IGV. Al 18% de IGV peruano corresponde sumarlo.',
    },
    {
        'q': '¿Aceptan pago anual?',
        'a': 'Sí. Pago anual adelantado tiene 10% de descuento. Ej: Talento = S/ 399/mes × 12 × 0.9 = S/ 4,309/año.',
    },
    {
        'q': '¿Qué incluye el onboarding del plan Suite?',
        'a': '2 semanas con un especialista que: (1) Carga workers desde tu sistema actual, (2) Configura conceptos custom (propinas, recargo), (3) Capacita a tu equipo de RRHH, (4) Migra histórico de planillas.',
    },
]


def precios(request):
    return render(request, 'precios/index.html', {
        'planes': PLANES,
        'faqs':   FAQS,
    })
