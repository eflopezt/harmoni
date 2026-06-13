from django.apps import AppConfig


class ComunicacionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comunicaciones'
    verbose_name = 'Comunicaciones Inteligentes'

    def ready(self):
        # Aprobaciones por Telegram (botones inline al crear solicitudes)
        from . import signals_aprobaciones  # noqa: F401
