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

# Siempre permitir plataformas de deploy
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

# CORS settings - restrictive in production (optional)
cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', '')
if cors_origins:
    CORS_ALLOWED_ORIGINS = [origin for origin in cors_origins.split(',') if origin]

# Security settings
SECURE_SSL_REDIRECT = os.environ.get('SECURE_SSL_REDIRECT', 'True') == 'True'
SESSION_COOKIE_SECURE = SECURE_SSL_REDIRECT
CSRF_COOKIE_SECURE = SECURE_SSL_REDIRECT
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Database - PostgreSQL for production
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)
    }
else:
    raise ValueError("DATABASE_URL environment variable is required in production")

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
    CELERY_TASK_SOFT_TIME_LIMIT = 120
    CELERY_TASK_TIME_LIMIT = 180
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
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')

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
