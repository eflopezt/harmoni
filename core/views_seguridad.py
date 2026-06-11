"""
Página pública de seguridad y compliance.

URL: /seguridad/
"""
from django.shortcuts import render


CATEGORIAS = [
    {
        'titulo':    'Encriptación de datos',
        'icon':      'fa-lock',
        'color':     '#0f766e',
        'items': [
            'Conexiones HTTPS/TLS 1.3 obligatorias (HSTS habilitado)',
            'Credenciales de integraciones (SMTP, API keys, tokens) cifradas at-rest con cifrado autenticado Fernet (AES-CBC + HMAC-SHA256)',
            'Hashes irreversibles de contraseñas (PBKDF2 + salt único)',
            'Contraseñas nunca se almacenan en texto plano',
        ],
    },
    {
        'titulo':    'Cumplimiento normativo peruano',
        'icon':      'fa-balance-scale',
        'color':     '#0891b2',
        'items': [
            'Ley N° 29733 — Protección de Datos Personales (Perú)',
            'D.S. N° 003-2013-JUS — Reglamento de la ley',
            'D.S. 009-2011-TR — Acuse de recibo de boletas electrónicas',
            'D.Leg. 854 — Jornada de trabajo (turno nocturno 35%)',
            'D.Leg. 728 + 727 — Regímenes laborales soportados',
            'DS 001-98-TR — Boletas de pago (datos obligatorios)',
        ],
    },
    {
        'titulo':    'Infraestructura y resiliencia',
        'icon':      'fa-server',
        'color':     '#a855f7',
        'items': [
            'Hosting en VPS dedicado (Contabo Cloud, datacenter EU)',
            'Backups automáticos diarios con retención 30 días',
            'PostgreSQL 16 con replicación point-in-time recovery',
            'Logs de auditoría inmutables (todo cambio queda registrado)',
            'Uptime histórico > 99.5% — ver /status/ en vivo',
            'CSP middleware activo — protección XSS',
        ],
    },
    {
        'titulo':    'Control de acceso',
        'icon':      'fa-user-shield',
        'color':     '#dc2626',
        'items': [
            'Perfiles de acceso granulares (4 niveles: admin, gerente, RRHH, trabajador)',
            'Worker access middleware — workers solo ven SU data',
            'Session timeout configurable (default 8 horas)',
            'Validador anti-passwords-comunes activado',
            'Rate limiting en login, auto-login y verificación QR (10/min/IP)',
            'JWT con refresh tokens para integraciones API',
        ],
    },
    {
        'titulo':    'Privacidad y manejo de datos',
        'icon':      'fa-eye-slash',
        'color':     '#16a34a',
        'items': [
            'DNI enmascarados en URLs públicas (verificación QR de boleta)',
            'IA con anonimización (no se envían DNIs ni montos a Gemini/DeepSeek)',
            'Default: APIs OpenAI deshabilitadas; preferimos Gemini (EU compliance)',
            'Logs no incluyen contraseñas, PII se sanitiza antes de loggear',
            'Borrado bajo demanda vía soporte (derechos ARCO — Ley 29733)',
        ],
    },
    {
        'titulo':    'IA responsable',
        'icon':      'fa-brain',
        'color':     '#7c3aed',
        'items': [
            '5 modelos IA con propósito específico (no LLM "todo poderoso")',
            'Predictor de rotación entrenado con data anonimizada',
            'CV parser local (no envía CVs completos a third-party)',
            'Cliente puede deshabilitar IA por completo desde admin',
            'Logs IA auditables — quién pidió qué y qué se devolvió',
        ],
    },
]


CERTIFICACIONES = [
    {'nombre': 'SUNAT', 'desc': 'Formatos PLAME, T-Registro, AFPnet 2026 actualizados', 'icon': 'fa-file-invoice', 'color': '#dc2626'},
    {'nombre': 'MTPE', 'desc': 'Cumplimiento DS 001-98-TR + DS 009-2011-TR', 'icon': 'fa-stamp', 'color': '#0891b2'},
    {'nombre': 'INDECOPI', 'desc': 'Ley 29733 datos personales — registros formales', 'icon': 'fa-shield-alt', 'color': '#16a34a'},
]


def seguridad(request):
    return render(request, 'seguridad/index.html', {
        'categorias':       CATEGORIAS,
        'certificaciones':  CERTIFICACIONES,
    })
