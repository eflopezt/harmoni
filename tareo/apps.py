from django.apps import AppConfig


class TareoConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tareo"
    verbose_name = "Tareo"

    def ready(self):
        pass  # Aquí se importarán señales cuando se agreguen
