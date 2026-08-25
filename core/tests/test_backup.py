"""
Tests para el subsystema de backup PostgreSQL.

No ejecutamos pg_dump real (requeriría server PG en CI). En su lugar:
  - Verificamos que el script existe y tiene la shape esperada.
  - Que el management command está registrado y --dry-run anda.
  - Que la Celery task es invocable y reportea errores correctamente.
  - Que la lógica de rotación calcula bien la edad de los archivos.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError


BACKUP_SCRIPT = Path(settings.BASE_DIR) / 'deploy' / 'backup-db.sh'


# ═══════════════════════════════════════════════════════════════════
# 1. Script de bash existe y tiene contenido razonable
# ═══════════════════════════════════════════════════════════════════

class TestBackupScript:
    def test_script_existe(self):
        """deploy/backup-db.sh debe existir y no estar vacío."""
        assert BACKUP_SCRIPT.exists(), f'{BACKUP_SCRIPT} no existe'
        assert BACKUP_SCRIPT.stat().st_size > 200, 'script muy chico — sospechoso'

    def test_script_tiene_shebang(self):
        """Primera línea = shebang de bash."""
        first = BACKUP_SCRIPT.read_text(encoding='utf-8').splitlines()[0]
        assert first.startswith('#!') and 'bash' in first, f'shebang inválido: {first!r}'

    def test_script_usa_pg_dump_custom(self):
        """El script debe usar pg_dump con format=custom y compress=9 (decisión arquitectónica)."""
        contenido = BACKUP_SCRIPT.read_text(encoding='utf-8')
        assert 'pg_dump' in contenido
        assert '--format=custom' in contenido
        assert '--compress=9' in contenido
        assert '--no-owner' in contenido

    def test_script_soporta_env_vars_documentadas(self):
        """Las env vars que documentamos en el doctring deben aparecer en el script."""
        contenido = BACKUP_SCRIPT.read_text(encoding='utf-8')
        for var in ('DB_NAME', 'DB_USER', 'BACKUP_DIR', 'BACKUP_RETENTION_DAYS',
                    'BACKUP_S3_BUCKET', 'BACKUP_B2_BUCKET'):
            assert var in contenido, f'{var} no referenciada en backup-db.sh'

    def test_script_rotacion_30_dias_por_default(self):
        """BACKUP_RETENTION_DAYS default = 30."""
        contenido = BACKUP_SCRIPT.read_text(encoding='utf-8')
        assert 'BACKUP_RETENTION_DAYS:-30' in contenido, \
            'el default de retención cambió — actualizar docs'


# ═══════════════════════════════════════════════════════════════════
# 2. Management command backup_db_now
# ═══════════════════════════════════════════════════════════════════

class TestBackupManagementCommand:
    def test_command_dry_run_no_falla(self, capsys):
        """`manage.py backup_db_now --dry-run` debe terminar sin error en cualquier OS."""
        # En Windows sin bash, el fallback dentro del command imprime los params.
        # En Linux/Mac, ejecuta el script con BACKUP_DRY_RUN=1.
        try:
            call_command('backup_db_now', '--dry-run')
        except CommandError as e:
            pytest.fail(f'backup_db_now --dry-run falló inesperadamente: {e}')

    def test_command_falla_si_script_ausente(self, tmp_path, monkeypatch):
        """Si BASE_DIR no contiene deploy/backup-db.sh, el command debe levantar CommandError."""
        monkeypatch.setattr(settings, 'BASE_DIR', tmp_path)
        with pytest.raises(CommandError, match='no encontrado'):
            call_command('backup_db_now', '--dry-run')


# ═══════════════════════════════════════════════════════════════════
# 3. Celery task: importable e invocable
# ═══════════════════════════════════════════════════════════════════

class TestCeleryTask:
    def test_task_es_importable(self):
        from core.tasks_backup import backup_db_diario  # noqa: F401
        assert callable(backup_db_diario)

    def test_task_registrada_en_celery(self):
        """El worker debe descubrir la task sin importarla manualmente."""
        from config.celery import app

        app.autodiscover_tasks(force=True)
        assert 'core.tasks_backup.backup_db_diario' in app.tasks

    def test_task_falla_limpio_si_script_ausente(self, tmp_path, monkeypatch):
        """Si deploy/backup-db.sh no existe, debe levantar FileNotFoundError (no crashear silenciosamente)."""
        monkeypatch.setattr(settings, 'BASE_DIR', tmp_path)
        from core.tasks_backup import backup_db_diario
        # Invocar la función subyacente (no .delay()) para test síncrono
        with pytest.raises(FileNotFoundError):
            backup_db_diario.apply().get(propagate=True)

    def test_task_invoca_subprocess_run(self, monkeypatch):
        """Mock subprocess.run, verificar que la task lo invoca con el script correcto."""
        from core import tasks_backup

        called = {}

        def fake_run(cmd, **kwargs):
            called['cmd'] = cmd
            called['kwargs'] = kwargs
            # Simular éxito
            mock_result = mock.MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = 'backup OK (fake)\n'
            mock_result.stderr = ''
            return mock_result

        monkeypatch.setattr(tasks_backup.subprocess, 'run', fake_run)

        # Asegurar que el script "existe" desde el punto de vista del task
        # (de hecho existe — está en deploy/backup-db.sh)
        result = tasks_backup.backup_db_diario.apply().get(propagate=True)
        assert result['ok'] is True
        assert 'backup-db.sh' in str(called['cmd'])


# ═══════════════════════════════════════════════════════════════════
# 4. Beat schedule entry registrada
# ═══════════════════════════════════════════════════════════════════

class TestBeatSchedule:
    def test_backup_diario_en_beat_schedule(self):
        """CELERY_BEAT_SCHEDULE debe tener 'backup-db-diario' apuntando a la task correcta."""
        sched = settings.CELERY_BEAT_SCHEDULE
        assert 'backup-db-diario' in sched, 'falta entry backup-db-diario en CELERY_BEAT_SCHEDULE'
        entry = sched['backup-db-diario']
        assert entry['task'] == 'core.tasks_backup.backup_db_diario'
        # Verificar que tiene un schedule (no asumimos hora exacta para evitar tests frágiles)
        assert 'schedule' in entry


# ═══════════════════════════════════════════════════════════════════
# 5. Lógica de rotación (cálculo de fechas)
# ═══════════════════════════════════════════════════════════════════

class TestRotationDateMath:
    """El find -mtime +N borra archivos modificados hace MÁS de N días.

    Estos tests validan el cálculo conceptual que documenta el comportamiento
    esperado (no ejecutamos find real, pero verificamos las fechas que el
    script considera "antiguas").
    """

    def test_archivo_de_31_dias_es_borrable_con_retencion_30(self):
        retention_days = 30
        ahora = datetime(2026, 5, 24, 3, 30, 0)
        antigüedad_archivo = ahora - timedelta(days=31)
        edad_en_dias = (ahora - antigüedad_archivo).days
        assert edad_en_dias > retention_days

    def test_archivo_de_29_dias_NO_es_borrable_con_retencion_30(self):
        retention_days = 30
        ahora = datetime(2026, 5, 24, 3, 30, 0)
        antigüedad_archivo = ahora - timedelta(days=29)
        edad_en_dias = (ahora - antigüedad_archivo).days
        assert edad_en_dias < retention_days

    def test_timestamp_filename_pattern_es_parseable(self):
        """El patrón harmoni-db-YYYYMMDD-HHMMSS.dump debe ser parseable a datetime."""
        sample = 'harmoni-db-20260524-033000.dump'
        # Extraer timestamp
        prefix = 'harmoni-db-'
        suffix = '.dump'
        ts_str = sample[len(prefix):-len(suffix)]
        parsed = datetime.strptime(ts_str, '%Y%m%d-%H%M%S')
        assert parsed.year == 2026
        assert parsed.month == 5
        assert parsed.day == 24
