"""
Sales Hub /h/ — un solo lugar con todo el material comercial.

URL: /h/  (público, sin login)

Hub central para que el vendedor (o el cliente) tenga TODOS los recursos
en un solo lugar. Pensado para mandar como link único.
"""
from django.shortcuts import render


RECURSOS = [
    {
        'categoria': '🎯 Demos en vivo',
        'items': [
            {
                'titulo': 'Demo Enterprise (Grupo Sabores)',
                'desc':   'Multi-empresa, gastronomía premium, 94 trabajadores',
                'url':    '/d/enterprise/',
                'icon':   'fa-rocket',
                'color':  '#0f766e',
                'badge':  'Recomendado',
            },
            {
                'titulo': 'Demo Starter (Pixel Motion)',
                'desc':   'Plan económico S/149, agencia 25 personas',
                'url':    '/d/starter/',
                'icon':   'fa-leaf',
                'color':  '#94a3b8',
            },
            {
                'titulo': 'Centro de Comando',
                'desc':   'La vista que el dueño abre cada mañana',
                'url':    '/comando/',
                'icon':   'fa-broadcast-tower',
                'color':  '#a855f7',
            },
            {
                'titulo': 'QR para mobile demo',
                'desc':   'Cliente escanea, entra al portal en su celular',
                'url':    '/qr-demo/',
                'icon':   'fa-qrcode',
                'color':  '#0891b2',
            },
        ],
    },
    {
        'categoria': '💰 Cifras y precios',
        'items': [
            {
                'titulo': 'Calculadora ROI',
                'desc':   'Cuánto te ahorra Harmoni vs tu proceso actual',
                'url':    '/roi/',
                'icon':   'fa-calculator',
                'color':  '#16a34a',
            },
            {
                'titulo': 'Precios y planes',
                'desc':   'Starter (S/149) · Profesional (S/399) · Business (S/799) · Enterprise',
                'url':    '/precios/',
                'icon':   'fa-tag',
                'color':  '#f59e0b',
            },
        ],
    },
    {
        'categoria': '📖 Información',
        'items': [
            {
                'titulo': 'Caso Sabores del Sur completo',
                'desc':   'Problema, solución, ROI 520% en grupos gastronómicos',
                'url':    '/casos/edo/',
                'icon':   'fa-utensils',
                'color':  '#dc2626',
            },
            {
                'titulo': 'Tour de 12 features',
                'desc':   'Grid con todas las features estrella + CTAs',
                'url':    '/tour/edo/',
                'icon':   'fa-route',
                'color':  '#7c3aed',
            },
            {
                'titulo': 'Clientes y testimonios',
                'desc':   '6 testimonios reales + métricas agregadas',
                'url':    '/clientes/',
                'icon':   'fa-comment-dots',
                'color':  '#16a34a',
            },
        ],
    },
    {
        'categoria': '❓ Soporte y compliance',
        'items': [
            {
                'titulo': 'FAQ gastronomía',
                'desc':   '15 preguntas frecuentes (propinas, turnos, multi-RUC)',
                'url':    '/faq/',
                'icon':   'fa-question-circle',
                'color':  '#0891b2',
            },
            {
                'titulo': 'Seguridad y compliance',
                'desc':   'Encriptación, RGPD, SUNAT, ISO 27001',
                'url':    '/seguridad/',
                'icon':   'fa-shield-alt',
                'color':  '#dc2626',
            },
            {
                'titulo': 'Status del sistema',
                'desc':   'Uptime en vivo, monitoreo health checks',
                'url':    '/status/',
                'icon':   'fa-heartbeat',
                'color':  '#16a34a',
            },
        ],
    },
    {
        'categoria': '🚀 Empezar',
        'items': [
            {
                'titulo': 'Wizard onboarding Starter',
                'desc':   '3 pasos guiados: empresa → admin → ¡listo!',
                'url':    '/onboarding/starter/',
                'icon':   'fa-rocket',
                'color':  '#16a34a',
                'badge':  '30 días gratis',
            },
            {
                'titulo': 'WhatsApp ventas',
                'desc':   'Conversemos 15 minutos sin compromiso',
                'url':    'https://wa.me/51906602313?text=Hola,%20vi%20el%20sales%20hub%20de%20Harmoni.%20Quiero%20conversar.',
                'icon':   'fa-whatsapp',
                'fa_brand': True,
                'color':  '#16a34a',
                'external': True,
            },
        ],
    },
]


def sales_hub(request):
    return render(request, 'h/index.html', {'recursos': RECURSOS})
