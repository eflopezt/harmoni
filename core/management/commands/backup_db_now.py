"""
Ejecuta el script deploy/backup-db.sh directamente.

Útil para:
  - Probar el backup manualmente (sin esperar al schedule de Celery beat).
  - Forzar un dump ad-hoc antes de un deploy riesgoso.
  - --dry-run para verificar configuración sin escribir nada.

Uso:
    python manage.py backup_db_now
    python manage.py backup_db_now --dry-run
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Ejecuta deploy/backup-db.sh para hacer un backup manual de PostgreSQL.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra los parámetros del backup sin ejecutarlo realmente.',
        )

    def handle(self, *args, **opts):
        dry_run = opts.get('dry_run', False)

        script = Path(settings.BASE_DIR) / 'deploy' / 'backup-db.sh'
        if not script.exists():
            raise CommandError(f'Script de backup no encontrado: {script}')

        env = os.environ.copy()
        if dry_run:
            env['BACKUP_DRY_RUN'] = '1'
            self.stdout.write(self.style.WARNING('Modo dry-run — no se ejecutará pg_dump.'))

        # Detectar si bash está disponible (Windows dev vs Linux prod)
        cmd: list[str]
        if os.name == 'nt':
            # En Windows usamos bash de Git for Windows o WSL si está
            bash = self._find_bash()
            if not bash:
                if dry_run:
                    # En dry-run podemos mostrar los params sin ejecutar realmente
                    self._print_dry_run_fallback(env, script)
                    return
                raise CommandError(
                    'bash no encontrado en PATH. Este comando requiere bash (Git Bash, WSL o Linux).'
                )
            cmd = [bash, str(script)]
        else:
            cmd = ['bash', str(script)]

        self.stdout.write(f'Ejecutando: {" ".join(cmd)}')
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=60 * 30)
        except subprocess.TimeoutExpired:
            raise CommandError('Timeout: el backup tardó más de 30 minutos.')

        # Reenviar output al usuario
        if result.stdout:
            self.stdout.write(result.stdout)
        if result.stderr:
            self.stderr.write(result.stderr)

        if result.returncode != 0:
            raise CommandError(f'backup-db.sh terminó con rc={result.returncode}')

        self.stdout.write(self.style.SUCCESS('Backup completado.'))

    @staticmethod
    def _find_bash() -> str | None:
        """Busca bash en ubicaciones comunes en Windows."""
        for candidate in (
            'bash',
            r'C:\Program Files\Git\bin\bash.exe',
            r'C:\Program Files\Git\usr\bin\bash.exe',
            r'C:\Windows\System32\bash.exe',  # WSL
        ):
            try:
                subprocess.run([candidate, '--version'], capture_output=True, timeout=5, check=True)
                return candidate
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                continue
        return None

    def _print_dry_run_fallback(self, env, script):
        """Cuando estamos en Windows sin bash y en dry-run, mostramos los params igual."""
        self.stdout.write('[DRY-RUN] Backup parameters (bash no disponible — fallback):')
        for var in (
            'DB_NAME', 'DB_USER', 'DB_HOST', 'DB_PORT',
            'BACKUP_DIR', 'BACKUP_RETENTION_DAYS',
            'BACKUP_S3_BUCKET', 'BACKUP_B2_BUCKET', 'BACKUP_B2_KEY_ID',
        ):
            self.stdout.write(f'  {var}={env.get(var, "(unset)")}')
        self.stdout.write(f'  script={script}')
        self.stdout.write(self.style.SUCCESS('Dry-run OK (sin ejecutar bash).'))
