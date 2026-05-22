"""
Página de precios pública — para enviar a prospectos.

URL: /precios/  (público, sin login)
"""
from django.shortcuts import render


PLANES = [
    {
        'codigo':       'STARTER',
        'nombre':       'Starter',
        'precio':       149,
        'colaboradores': 'hasta 30',
        'tagline':      'Para PYMEs que necesitan planilla simple',
        'color':        '#94a3b8',
        'destacado':    False,
        'features': [
            'Personal y asistencia',
            'Papeletas (admin entra permisos)',
            'Planilla mensual completa',
            'Boleta PDF (descarga local)',
            'Vacaciones (gestión admin)',
            'Exportes Concar, Siscont',
            'PLAME / AFPnet',
            'Soporte por email',
        ],
        'features_no': [
            'Portal del colaborador',
            'Envío automático de boletas',
            'Reclutamiento con IA',
            'Multi-empresa',
        ],
    },
    {
        'codigo':       'PROFESIONAL',
        'nombre':       'Profesional',
        'precio':       399,
        'colaboradores': 'hasta 100',
        'tagline':      'El plan más elegido',
        'color':        '#0f766e',
        'destacado':    True,
        'features': [
            '— Todo lo de Starter +',
            'Portal del trabajador (mobile)',
            'Envío automático de boletas',
            'Acuses electrónicos (DS 009-2011-TR)',
            'Reclutamiento con CV parser',
            'Pipeline Kanban',
            'Capacitaciones + Evaluaciones',
            'Préstamos / Adelantos',
            'Disciplinaria con templates',
            'Soporte por chat (4h SLA)',
        ],
        'features_no': [
            'Predictor IA de Rotación',
            'BI Excel multi-empresa',
            'Multi-empresa (multi-RUC)',
            'Workflows custom',
        ],
    },
    {
        'codigo':       'BUSINESS',
        'nombre':       'Business',
        'precio':       799,
        'colaboradores': 'hasta 300',
        'tagline':      'Para empresas medianas con BI e IA',
        'color':        '#0d2b27',
        'destacado':    False,
        'features': [
            '— Todo lo de Profesional +',
            'Predictor IA de Rotación',
            'AI Summary de CVs',
            'Evaluaciones 360°',
            'Dashboard Ejecutivo cross-modulo',
            'BI Excel multi-empresa (8 tabs)',
            'Workflows custom (vacaciones, HE, etc.)',
            'Bandas salariales + análisis equidad',
            'API REST integraciones',
            'Soporte prioritario (2h SLA)',
        ],
        'features_no': [
            'Multi-empresa avanzado (>3 RUCs)',
            'SSO / Active Directory',
            'Integración Synkro / SAP',
        ],
    },
    {
        'codigo':       'ENTERPRISE',
        'nombre':       'Enterprise',
        'precio':       None,
        'precio_label': 'Personalizado',
        'colaboradores': '300+',
        'tagline':      'Para grupos con múltiples razones sociales',
        'color':        '#a855f7',
        'destacado':    False,
        'features': [
            '— Todo lo de Business +',
            'Multi-empresa ilimitado (24+ RUCs)',
            'Pulse del Grupo (multi-local)',
            'Briefing del Día (gastronomía)',
            'Cuadrícula Semanal drag&drop',
            'BPM/HACCP tracking gastro',
            'SSO / Active Directory',
            'Integración Synkro / SAP / Spring',
            'Onboarding dedicado (2 semanas)',
            'Soporte 24×7 con SLA garantizado',
            'Features customizadas',
        ],
        'features_no': [],
    },
]


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
        'a': 'Sí. Pago anual adelantado tiene 10% de descuento. Ej: Profesional = S/ 399/mes × 12 × 0.9 = S/ 4,309/año.',
    },
    {
        'q': '¿Qué incluye el onboarding dedicado del Enterprise?',
        'a': '2 semanas con un especialista que: (1) Carga workers desde sistema actual, (2) Configura conceptos custom (propinas, recargo), (3) Capacita a tu equipo de RRHH, (4) Migra histórico de planillas.',
    },
]


def precios(request):
    return render(request, 'precios/index.html', {
        'planes': PLANES,
        'faqs':   FAQS,
    })
