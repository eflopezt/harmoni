"""
Production settings - extends base settings.
"""
import dj_database_url
from .base import *

# SECURITY — DEBUG must always be False in production
DEBUG = False

# Validate SECRET_KEY
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY or SECRET_KEY.startswith('django-insecure'):
    raise ValueError("DJANGO_SECRET_KEY must be set to a secure value in production")

ALLOWED_HOSTS = [host for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',') if host]

# Siempre permitir plataformas de deploy y wildcard subdomains for multi-tenant
for host in ['.onrender.com', '.harmoni.pe', '.nexotalent.pe']:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# Si se pasa CSRF_TRUSTED_ORIGINS explícitamente, se usa; si no, se deriva de ALLOWED_HOSTS
_csrf_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if _csrf_env:
    CSRF_TRUSTED_ORIGINS = [o for o in _csrf_env.split(',') if o]
else:
    CSRF_TRUSTED_ORIGINS = [
        f'https://{h}' for h in ALLOWED_HOSTS if h and not h.startswith('.')
    ]
    CSRF_TRUSTED_ORIGINS.append('https://*.onrender.com')
    CSRF_TRUSTED_ORIGINS.append('https://*.harmoni.pe')
    CSRF_TRUSTED_ORIGINS.append('https://*.nexotalent.pe')

# CORS settings - restrictive in production (optional)
cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if cors_origins:
    CORS_ALLOWED_ORIGINS = [origin for origin in cors_origins.split(',') if origin]

# Security settings
# Audit security 2026-05-20: SESSION_COOKIE_SECURE y CSRF_COOKIE_SECURE
# eran derivados de SECURE_SSL_REDIRECT. Cuando el deploy ponia
# SECURE_SSL_REDIRECT=False (nginx hacia el redirect), las cookies se
# emitian sin flag Secure y viajaban potencialmente por HTTP. Fix:
# default independiente a True (override solo en dev con SESSION_COOKIE_SECURE=False).
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True') == 'True'
CSRF_COOKIE_SECURE = os.environ.get('CSRF_COOKIE_SECURE', 'True') == 'True'
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
# CSRF_COOKIE_HTTPONLY debe ser False: la app usa el patrón AJAX que lee el
# token CSRF desde la cookie con JS (getCookie('csrftoken') → header
# X-CSRFToken). Con HTTPONLY=True el navegador oculta la cookie a JS, el header
# sale vacío y Django responde 403 "CSRF verification failed" en esos POST
# (roster matricial, detalle de personal, viáticos, checklist gastro, etc.).
# El token CSRF NO es un secreto que requiera HTTPOnly: su protección viene del
# patrón synchronizer, no de ocultarlo a JS (ver docs de Django).
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'same-origin'

# Session timeout — audit security recomendaba reducir el default 2 semanas
# para ERP con datos sensibles. 8h cubre una jornada completa + buffer.
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 horas
SESSION_SAVE_EVERY_REQUEST = True  # extiende la sesión en cada request activo

# Content Security Policy — django-csp 4.x API (dict)
# Audit security fix 2026-05-20: antes usaba constantes CSP_* (django-csp 3.x)
# que ya no aplican en la version 4 instalada. Migrado al formato dict.
CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src":     ["'self'"],
        # 'unsafe-eval' removido 2026-05-26 tras audit: no se usa eval(),
        # new Function() ni setTimeout("string") en ningún template ni JS
        # del proyecto, y las CDNs activas (Chart.js 4, Bootstrap 5, htmx) no
        # lo requieren. Si alguna lib futura lo necesita, browser logea
        # violación CSP en consola pero solo bloquea ese script específico.
        #
        # Pendiente Q3 2026: migrar 'unsafe-inline' a nonces vía
        # CSP_INCLUDE_NONCE_IN. Bloqueado por ~135 templates con <script>
        # inline. style-src debe mantener 'unsafe-inline' por 4k+ atributos
        # style="..." que no son cubribles por nonce.
        "script-src":      ["'self'", "'unsafe-inline'",
                             "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
        "style-src":       ["'self'", "'unsafe-inline'",
                             "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com",
                             "https://fonts.googleapis.com"],
        "font-src":        ["'self'", "https://fonts.gstatic.com",
                             "https://cdn.jsdelivr.net", "https://cdnjs.cloudflare.com"],
        "img-src":         ["'self'", "data:", "https:"],
        "connect-src":     ["'self'"],
        "frame-ancestors": ["'self'"],
    },
}

# Database - PostgreSQL for production
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    raise ValueError("DATABASE_URL environment variable is required in production")

# Synkro RRHH (Sistema de Control de Personal y Asistencias) — read-only
# Activar definiendo SYNKRO_HOST en .env. Usado para sync directo de
# marcaciones/papeletas. Driver mssql-django requiere ODBC Driver 18
# instalado en el contenedor.
SYNKRO_HOST = os.environ.get('SYNKRO_HOST')
if SYNKRO_HOST:
    DATABASES['synkro'] = {
        'ENGINE': 'mssql',
        'NAME': os.environ.get('SYNKRO_DB', 'DB_RRHH'),
        'HOST': SYNKRO_HOST,
        'PORT': os.environ.get('SYNKRO_PORT', '1433'),
        'USER': os.environ.get('SYNKRO_USER', 'rrhh'),
        'PASSWORD': os.environ.get('SYNKRO_PASSWORD', ''),
        'OPTIONS': {
            'driver': os.environ.get('SYNKRO_DRIVER', 'ODBC Driver 18 for SQL Server'),
            'extra_params': 'TrustServerCertificate=yes;Encrypt=no;',
        },
        'CONN_MAX_AGE': 60,
    }

# Cache: use Redis if available, otherwise database
REDIS_URL = os.environ.get('REDIS_URL')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
            'LOCATION': 'django_cache_table',
        }
    }
    SESSION_ENGINE = 'django.contrib.sessions.backends.db'

# Celery: use Redis broker if available, otherwise run tasks eagerly
CELERY_BROKER_URL_ENV = os.environ.get('CELERY_BROKER_URL')
if CELERY_BROKER_URL_ENV:
    CELERY_BROKER_URL = CELERY_BROKER_URL_ENV
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL_ENV)
    CELERY_TASK_ALWAYS_EAGER = False
    CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
    # Optimización de workers
    CELERY_WORKER_PREFETCH_MULTIPLIER = 1
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 100
    CELERY_WORKER_MAX_MEMORY_PER_CHILD = 150_000  # 150MB en KB
    CELERY_TASK_ACKS_LATE = True
    CELERY_TASK_SOFT_TIME_LIMIT = 300   # 5 min
    CELERY_TASK_TIME_LIMIT = 600        # 10 min hard kill
    CELERY_TASK_REJECT_ON_WORKER_LOST = True
    CELERY_TASK_COMPRESSION = 'gzip'
    CELERY_RESULT_EXPIRES = 3600
    CELERY_RESULT_COMPRESSION = 'gzip'
else:
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Email backend multi-tenant (usa SMTP de la empresa activa, fallback a settings globales)
EMAIL_BACKEND = 'empresas.email_backend.EmpresaEmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 'yes')
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() in ('true', '1', 'yes')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@harmoni.pe')

# Sentry error tracking
SENTRY_DSN = os.environ.get('SENTRY_DSN')
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            RedisIntegration(),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment='production',
        server_name='harmoni-vps',
    )

# Logging — hereda de base.py, solo ajusta nivel para producción
LOGGING['root']['level'] = 'WARNING'
LOGGING['handlers']['console']['level'] = 'WARNING'

# URL base para verificación de boletas (impreso en QR y al pie del PDF)
BOLETA_VERIFY_BASE_URL = os.environ.get("BOLETA_VERIFY_BASE_URL", "").strip()
if not BOLETA_VERIFY_BASE_URL and ALLOWED_HOSTS:
    BOLETA_VERIFY_BASE_URL = f"https://{ALLOWED_HOSTS[0]}"
