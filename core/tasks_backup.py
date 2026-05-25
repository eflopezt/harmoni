"""
Tareas Celery para backup automatizado de PostgreSQL.

Tareas disponibles:
  - backup_db_diario  → ejecuta deploy/backup-db.sh, captura output a Sentry si falla.

Activación: agendado en CELERY_BEAT_SCHEDULE (config/settings/base.py)
  → 'backup-db-diario': 03:30 UTC diario.
"""
from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from celery import shared_task
from django.conf import settings

logger = logging.getLogger('core.backup')


def _backup_script_path() -> Path:
    """Resuelve la ruta absoluta a deploy/backup-db.sh respecto a BASE_DIR."""
    return Path(settings.BASE_DIR) / 'deploy' / 'backup-db.sh'


@shared_task(bind=True, max_retries=1, default_retry_delay=300, name='core.tasks_backup.backup_db_diario')
def backup_db_diario(self):
    """Ejecuta el script de backup de PostgreSQL.

    - Llama a deploy/backup-db.sh via subprocess.
    - Si el script retorna != 0, captura stdout/stderr a Sentry (con tag y
      contexto) y reintenta una vez.
    - En éxito, loggea a 'core.backup' y retorna el path del dump (si está
      en el stdout).
    """
    script = _backup_script_path()

    if not script.exists():
        msg = f'Script de backup no encontrado: {script}'
        logger.error(msg)
        _report_sentry('backup_db_diario: script ausente', extra={'path': str(script)})
        raise FileNotFoundError(msg)

    if not os.access(script, os.X_OK):
        # En despliegues nuevos puede no estar ejecutable. Ejecutamos via bash
        # como fallback, pero loggeamos un warning para que se arregle.
        logger.warning('Script %s sin bit ejecutable — invocando vía bash', script)
        cmd = ['bash', str(script)]
    else:
        cmd = [str(script)]

    logger.info('[backup_db_diario] ejecutando %s', cmd)

    try:
        # timeout 30min — pg_dump de bases <10GB termina muy por debajo de eso.
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60 * 30,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        logger.error('[backup_db_diario] timeout tras 30min')
        _report_sentry(
            'backup_db_diario: timeout',
            extra={'stdout': (e.stdout or '')[-2000:], 'stderr': (e.stderr or '')[-2000:]},
        )
        raise self.retry(exc=e)
    except Exception as e:
        logger.exception('[backup_db_diario] excepción inesperada')
        _report_sentry('backup_db_diario: excepción', extra={'error': str(e)})
        raise self.retry(exc=e)

    if result.returncode != 0:
        logger.error(
            '[backup_db_diario] script falló rc=%s stdout=%s stderr=%s',
            result.returncode,
            result.stdout[-1000:],
            result.stderr[-1000:],
        )
        _report_sentry(
            'backup_db_diario: script con rc != 0',
            extra={
                'returncode': result.returncode,
                'stdout': result.stdout[-2000:],
                'stderr': result.stderr[-2000:],
            },
        )
        raise self.retry(exc=RuntimeError(f'backup-db.sh rc={result.returncode}'))

    # Éxito
    logger.info('[backup_db_diario] OK — output:\n%s', result.stdout.strip()[-2000:])
    return {
        'ok': True,
        'returncode': 0,
        'stdout_tail': result.stdout.strip().splitlines()[-3:] if result.stdout else [],
    }


def _report_sentry(message: str, extra: dict | None = None, level: str = 'error') -> None:
    """Reporta a Sentry si está disponible. No falla si sentry_sdk no está."""
    try:
        import sentry_sdk
    except ImportError:
        return

    try:
        with sentry_sdk.new_scope() as scope:
            scope.set_tag('subsystem', 'backup')
            if extra:
                scope.set_context('backup', extra)
            sentry_sdk.capture_message(message, level=level)
    except Exception:  # noqa: BLE001
        logger.exception('[backup_db_diario] no se pudo reportar a Sentry')
