"""Punto de autodeteccion de tareas Celery del modulo core."""

# Celery solo autodetecta modulos llamados ``tasks``. Las implementaciones se
# mantienen separadas por subsistema, pero deben importarse aqui para que el
# worker las registre al arrancar.
from .tasks_backup import backup_db_diario

__all__ = ['backup_db_diario']
