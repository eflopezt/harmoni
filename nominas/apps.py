from django.apps import AppConfig


class NominasConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'nominas'
    verbose_name = 'Nóminas'

    def ready(self):
        # Registrar signal handlers para audit log de conceptos
        from . import signals_audit  # noqa: F401
