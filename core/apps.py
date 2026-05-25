from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "Core del Sistema"

    def ready(self):
        import core.signals  # noqa: F401 — registra señales de KnowledgeArticle
        import core.signals_plan_starter  # noqa: F401 — alertas upsell Starter

        # Audit log v2 — registra signals automáticos en modelos críticos
        # (Personal, SolicitudVacacion, Prestamo, RegistroPapeleta, PeriodoNomina).
        try:
            from core.audit_signals import auto_register_default_models
            auto_register_default_models()
        except Exception:  # noqa: BLE001
            # No queremos que un fallo en audit rompa el boot de Django.
            import logging
            logging.getLogger('harmoni.audit').exception(
                'auto_register_default_models falló al inicializar'
            )
