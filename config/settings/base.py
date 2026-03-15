"""
Base settings for gestion_personal project.
This file contains settings common to all environments.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Importar configuración de logging
from config.logging_config import LOGGING

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-key-change-this-in-production-#$%^&*'
)

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'drf_spectacular',
    'django_filters',
    'corsheaders',
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Humanize (formato de números)
    'django.contrib.humanize',

    # Local apps
    'core.apps.CoreConfig',
    'personal.apps.PersonalConfig',
    'asistencia.apps.AsistenciaConfig',
    'portal.apps.PortalConfig',
    'cierre.apps.CierreConfig',
    'documentos.apps.DocumentosConfig',
    'prestamos.apps.PrestamosConfig',
    'viaticos.apps.ViaticosConfig',
    'vacaciones.apps.VacacionesConfig',
    'capacitaciones.apps.CapacitacionesConfig',
    'disciplinaria.apps.DisciplinariaConfig',
    'salarios.apps.SalariosConfig',
    'evaluaciones.apps.EvaluacionesConfig',
    'encuestas.apps.EncuestasConfig',
    'calendario.apps.CalendarioConfig',
    'onboarding.apps.OnboardingConfig',
    'reclutamiento.apps.ReclutamientoConfig',
    'comunicaciones.apps.ComunicacionesConfig',
    'analytics.apps.AnalyticsConfig',
    'integraciones.apps.IntegracionesConfig',
    'nominas.apps.NominasConfig',
    'empresas.apps.EmpresasConfig',
    'workflows.apps.WorkflowsConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'empresas.middleware.EmpresaMiddleware',
    'core.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'personal.context_processors.harmoni_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Password validation - Mínimo 6 caracteres (permite DNI como contraseña)
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 6},
    },
]


# Internationalization
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login URL
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'login'


# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 50,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    },
}

# DRF Spectacular (OpenAPI / Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Harmoni ERP API',
    'DESCRIPTION': 'API REST para Harmoni — Sistema de Gestión de RRHH',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Personal', 'description': 'Empleados, áreas, subareas, roster'},
        {'name': 'Asistencia', 'description': 'Tareos, banco de horas, configuración'},
        {'name': 'Vacaciones', 'description': 'Saldos, solicitudes, permisos'},
        {'name': 'Préstamos', 'description': 'Tipos, préstamos, cuotas'},
        {'name': 'Documentos', 'description': 'Legajo digital, boletas de pago'},
        {'name': 'Capacitaciones', 'description': 'LMS, requerimientos, certificaciones'},
        {'name': 'Evaluaciones', 'description': 'Ciclos 360°, competencias'},
        {'name': 'Encuestas', 'description': 'Clima laboral, eNPS'},
        {'name': 'Salarios', 'description': 'Bandas, historial, simulaciones'},
        {'name': 'Reclutamiento', 'description': 'Vacantes, pipeline, postulaciones'},
        {'name': 'Comunicaciones', 'description': 'Notificaciones, comunicados masivos'},
    ],
}

# SimpleJWT
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=8),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}


# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"


# Cache (Redis)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Session cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'


# Celery Configuration
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://127.0.0.1:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos

# Celery Beat — Tareas periódicas
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ── Asistencia ──────────────────────────────────────────────
    'resumen-semanal-asistencia': {
        'task': 'asistencia.tasks.enviar_resumen_semanal_asistencia',
        'schedule': crontab(hour=8, minute=0, day_of_week='1'),  # Lunes 08:00
    },

    # ── Workflows ───────────────────────────────────────────────
    'verificar-vencimientos-workflows': {
        'task': 'workflows.verificar_vencimientos',
        'schedule': crontab(minute=0),  # Cada hora en punto
    },
    'notificar-pendientes-workflows': {
        'task': 'workflows.notificar_pendientes',
        'schedule': crontab(hour=8, minute=0, day_of_week='1-5'),  # Lun-Vie 08:00
    },

    # ── Personal ────────────────────────────────────────────────
    'alertar-contratos-por-vencer': {
        'task': 'personal.tasks.alertar_contratos_por_vencer',
        'schedule': crontab(hour=7, minute=30),  # Diario 07:30
    },

    # ── Analytics ───────────────────────────────────────────────
    'snapshot-kpi-mensual': {
        'task': 'analytics.tasks.generar_snapshot_kpi',
        'schedule': crontab(hour=1, minute=0, day_of_month='1'),  # Día 1 de cada mes 01:00
    },
}
