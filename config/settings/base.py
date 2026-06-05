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
    'django_celery_beat',
    'django_celery_results',
    
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
    'descuentos.apps.DescuentosConfig',
    'wa_marketing.apps.WaMarketingConfig',
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
    # CSP — solo activa si la libreria esta instalada (audit security fix)
    # Las constantes CSP_* en production.py controlan el comportamiento.
    *(['csp.middleware.CSPMiddleware'] if __import__('importlib').util.find_spec('csp') else []),
    'empresas.middleware_subdomain.SubdomainMiddleware',
    'empresas.middleware.EmpresaMiddleware',
    # (BillingMiddleware retirado — billing/suscripción ahora lo maneja el sistema
    #  vivo: core/planes.py + Empresa.suscripcion_hasta + PlanStarterMiddleware.)
    # Restringe trabajadores a URLs del portal (defensa profunda).
    'core.middleware_worker_access.WorkerAccessRestrictionMiddleware',
    # Gating por plan + trial/suscripción (core/planes.py).
    'core.middleware_plan_starter.PlanStarterMiddleware',
    'core.middleware.AuditMiddleware',
]

# Multi-tenant subdomain routing
# Root domains that support subdomain-based tenant resolution
HARMONI_TENANT_DOMAINS = ['harmoni.pe', 'nexotalent.pe']

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
                'core.context_processors.plan_starter_context',
                'nominas.context_processors.nominas_alerts',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 8},
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    # Security audit fix: previene que usuarios usen su DNI/email/nombre como password.
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
        'OPTIONS': {
            'user_attributes': ('username', 'email', 'first_name', 'last_name'),
            'max_similarity': 0.7,
        },
    },
]


# Internationalization
LANGUAGE_CODE = 'es-pe'
TIME_ZONE = 'America/Lima'
USE_I18N = True
USE_TZ = True

# Override del formato es_PE (Django default usa coma decimal — ambiguo S/X,XX).
# Custom formats en /formats/es_PE/formats.py forzan punto decimal + coma miles
# para DECIMALES (estándar peruano financiero: S/ 1,458.00).
# IMPORTANTE: USE_THOUSAND_SEPARATOR=False evita que años (2026) se formateen
# como "2,026". El separador de miles se aplica solo en filtros explícitos
# como |intcomma sobre DecimalFields.
FORMAT_MODULE_PATH = ['formats']
USE_THOUSAND_SEPARATOR = False
DECIMAL_SEPARATOR = '.'


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Django 5+: usa STORAGES dict en lugar de STATICFILES_STORAGE (deprecated).
# CompressedManifestStaticFilesStorage genera hash en el nombre del archivo
# (ej: harmoni.abc123.css) para invalidar caché del browser automáticamente
# cuando cambia el contenido. Sin esto, el browser cachea CSS viejos por días
# y el cliente debe hacer Ctrl+Shift+R para ver cambios.
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

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
        'anon': '50/hour',
        'user': '500/hour',
    },
}

# DRF Spectacular (OpenAPI / Swagger)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Harmoni ERP API',
    'DESCRIPTION': (
        'API REST para Harmoni — Sistema integral de Gestión de RRHH y Planillas '
        'para empresas peruanas.\n\n'
        '## Autenticación\n\n'
        'La API soporta dos métodos de autenticación:\n\n'
        '- **JWT Bearer Token**: Obtén un token en `/api/v1/token/` enviando '
        '`username` y `password`. Incluye el header `Authorization: Bearer <access_token>` '
        'en cada petición. Refresca el token en `/api/v1/token/refresh/`.\n'
        '- **Session Authentication**: Para uso desde el frontend web de Harmoni '
        '(requiere cookie de sesión activa).\n\n'
        '## Paginación\n\n'
        'Todos los endpoints de listado usan paginación por número de página '
        '(`page` query param, 50 items por defecto).\n\n'
        '## Rate Limiting\n\n'
        '- Usuarios anónimos: 50 requests/hora\n'
        '- Usuarios autenticados: 500 requests/hora'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    # Security audit (2026-05-20): /api/schema/, /api/docs/, /api/redoc/ ya no
    # son publicos. Solo staff puede ver el esquema (evita mapeo de la API
    # por terceros) ni se exponen modelos/endpoints en payload.
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAdminUser'],
    'CONTACT': {
        'name': 'Harmoni ERP',
        'url': 'https://harmoni.pe',
        'email': 'soporte@harmoni.pe',
    },
    'LICENSE': {
        'name': 'Propietario',
    },
    'TAGS': [
        {'name': 'Auth', 'description': 'Autenticación JWT — obtener y refrescar tokens'},
        {'name': 'Personal', 'description': 'Empleados, áreas, subareas, roster'},
        {'name': 'Asistencia', 'description': 'Tareos, banco de horas, configuración'},
        {'name': 'Nóminas', 'description': 'Periodos, registros, conceptos remunerativos'},
        {'name': 'Vacaciones', 'description': 'Saldos, solicitudes, permisos'},
        {'name': 'Préstamos', 'description': 'Tipos, préstamos, cuotas'},
        {'name': 'Documentos', 'description': 'Legajo digital, boletas de pago'},
        {'name': 'Capacitaciones', 'description': 'LMS, requerimientos, certificaciones'},
        {'name': 'Evaluaciones', 'description': 'Ciclos 360°, competencias'},
        {'name': 'Encuestas', 'description': 'Clima laboral, eNPS'},
        {'name': 'Salarios', 'description': 'Bandas, historial, simulaciones'},
        {'name': 'Reclutamiento', 'description': 'Vacantes, pipeline, postulaciones'},
        {'name': 'Comunicaciones', 'description': 'Notificaciones, comunicados masivos'},
        {'name': 'Analytics', 'description': 'KPIs, dashboards, alertas'},
        {'name': 'Empresas', 'description': 'Gestión multi-empresa'},
    ],
    'SECURITY': [
        {'BearerAuth': []},
    ],
    'APPEND_COMPONENTS': {
        'securitySchemes': {
            'BearerAuth': {
                'type': 'http',
                'scheme': 'bearer',
                'bearerFormat': 'JWT',
                'description': (
                    'Token JWT obtenido desde /api/v1/token/. '
                    'Formato: Bearer <access_token>'
                ),
            },
            'SessionAuth': {
                'type': 'apiKey',
                'in': 'cookie',
                'name': 'sessionid',
                'description': 'Cookie de sesión Django (para uso desde el frontend web)',
            },
        },
    },
    'SWAGGER_UI_SETTINGS': {
        'deepLinking': True,
        'persistAuthorization': True,
        'displayOperationId': False,
        'filter': True,
        'docExpansion': 'none',
    },
    'REDOC_UI_SETTINGS': {
        'hideDownloadButton': False,
        'expandResponses': '200,201',
    },
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
CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutos
CELERY_TASK_TIME_LIMIT = 600  # 10 minutos

# Celery Beat — Tareas periódicas
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    # ── Asistencia ──────────────────────────────────────────────
    'resumen-semanal-asistencia': {
        'task': 'asistencia.tasks.enviar_resumen_semanal_asistencia',
        'schedule': crontab(hour=8, minute=0, day_of_week='1'),  # Lunes 08:00
    },
    'health-check-papeletas-diario': {
        # Detecta y auto-corrige inconsistencias papeleta ↔ RegistroTareo
        # (ej: FA con papeleta APROBADA vigente). Salvaguarda contra bulk_create
        # u otras operaciones que no disparen signals.
        'task': 'asistencia.tasks.health_check_papeletas',
        'schedule': crontab(hour=5, minute=30),  # Diario 05:30
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

    # ── Integraciones — Synkro RRHH ────────────────────────────
    # Sync incremental con la BD remota de Synkro: papeletas, picados,
    # feriados. Solo corre si SYNKRO_HOST está configurado en .env.
    'sync-synkro-rrhh-15min': {
        'task': 'integraciones.tasks.sync_synkro_auto',
        'schedule': crontab(minute='*/15'),  # cada 15 minutos
    },

    # ── Sweep nocturno de asistencia ───────────────────────────
    # Limpia RegistroTareo donde codigo_dia=SS/SE con entrada+salida válidas
    # (debería ser 'A'), recalcula HE y propaga al BancoHoras.
    # Defensiva: el sync ya hace esto en vivo (línea 657 synkro_sync.py),
    # pero el sweep nocturno asegura que datos legacy o casos edge se
    # corrijan diariamente sin acción manual.
    'sweep-codigo-dia-banco-nocturno': {
        'task': 'asistencia.tasks.sweep_codigo_dia_y_banco_horas',
        'schedule': crontab(hour=2, minute=30),  # diario 02:30
    },

    # ── Infra — Backup PostgreSQL ──────────────────────────────
    # pg_dump diario de harmoni_db a /opt/harmoni/backups + rotación 30 días.
    # Si BACKUP_S3_BUCKET o BACKUP_B2_BUCKET están seteados en el entorno
    # del beat/worker, también sube offsite. Ver deploy/backup-db.sh.
    'backup-db-diario': {
        'task': 'core.tasks_backup.backup_db_diario',
        'schedule': crontab(hour=3, minute=30),  # Diario 03:30
    },
}
