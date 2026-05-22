from django.apps import AppConfig


class DisciplinariaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'disciplinaria'
    verbose_name = 'Proceso Disciplinario'

    def ready(self):
        # Registrar signal handlers (notificación al trabajador, etc.)
        try:
            from . import signals  # noqa: F401
        except Exception:
            pass
