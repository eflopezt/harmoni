from django.apps import AppConfig


class DocumentosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documentos'
    verbose_name = 'Documentos y Boletas'

    def ready(self):
        # Conectar signals de actividad del trabajador (DS 009-2011-TR)
        from . import signals  # noqa: F401
