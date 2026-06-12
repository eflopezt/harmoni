#!/usr/bin/env bash
# =============================================================================
# PostgreSQL Backup — Harmoni ERP
#
# Backup automatizado de PostgreSQL con rotación, log rotation por tamaño
# y soporte opcional para AWS S3 y Backblaze B2.
#
# Uso manual:
#   /opt/harmoni/app/deploy/backup-db.sh
#
# Via Celery beat (recomendado en prod):
#   El task `core.tasks_backup.backup_db_diario` corre 03:30 cada día
#   (configurado en config/settings/base.py CELERY_BEAT_SCHEDULE).
#
# Variables de entorno:
#   DB_NAME              (default: harmoni_db)
#   DB_USER              (default: harmoni)
#   DB_HOST              (default: 127.0.0.1)
#   DB_PORT              (default: 5432)
#   BACKUP_DIR           (default: /opt/harmoni/backups)
#   BACKUP_RETENTION_DAYS (default: 30)
#   BACKUP_S3_BUCKET     (opcional → si está seteado y `aws` existe, sube a S3)
#   BACKUP_B2_BUCKET     (opcional → si está seteado y `b2` existe, sube a B2)
#   BACKUP_B2_KEY_ID     (requerido si BACKUP_B2_BUCKET seteado)
#   BACKUP_DRY_RUN       (opcional: si =1, solo muestra qué haría sin ejecutar)
#
# Exit codes:
#   0 = éxito
#   1 = error (pg_dump fail, disk full, etc)
# =============================================================================
set -euo pipefail

# ── Config ────────────────────────────────────────────────────────────────
DB_NAME="${DB_NAME:-harmoni_db}"
DB_USER="${DB_USER:-harmoni}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-5432}"
BACKUP_DIR="${BACKUP_DIR:-/opt/harmoni/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
DRY_RUN="${BACKUP_DRY_RUN:-0}"

# ── Credenciales ──────────────────────────────────────────────────────────
# pg_dump necesita PGPASSWORD (no hay .pgpass en el contenedor). Si no viene
# en el entorno, derivarla de DATABASE_URL (postgresql://user:pass@host/db),
# que es la fuente única de credenciales en prod.
if [ -z "${PGPASSWORD:-}" ] && [ -n "${DATABASE_URL:-}" ]; then
    _userpass="${DATABASE_URL#*://}"
    _userpass="${_userpass%%@*}"
    if [ "$_userpass" != "${_userpass#*:}" ]; then
        export PGPASSWORD="${_userpass#*:}"
    fi
fi

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DUMP_FILE="${BACKUP_DIR}/harmoni-db-${TIMESTAMP}.dump"
LOG_FILE="${BACKUP_DIR}/backup.log"
LOG_MAX_BYTES=$((10 * 1024 * 1024))  # 10 MB

# ── Helpers ────────────────────────────────────────────────────────────────
log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    # Append to log file solo si el directorio existe (en dry-run puede no existir)
    if [ -d "$BACKUP_DIR" ]; then
        echo "$msg" >> "$LOG_FILE"
    fi
}

rotate_log_if_needed() {
    if [ ! -f "$LOG_FILE" ]; then return 0; fi
    local size
    # `stat -c` (GNU) en Linux. macOS usa `stat -f%z`. Producción es Linux/VPS.
    size=$(stat -c%s "$LOG_FILE" 2>/dev/null || stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)
    if [ "$size" -gt "$LOG_MAX_BYTES" ]; then
        mv "$LOG_FILE" "${LOG_FILE}.1"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] log rotated (>${LOG_MAX_BYTES} bytes)" > "$LOG_FILE"
    fi
}

err_exit() {
    log "ERROR: $*"
    exit 1
}

# ── Dry-run mode ──────────────────────────────────────────────────────────
if [ "$DRY_RUN" = "1" ]; then
    echo "[DRY-RUN] Backup parameters:"
    echo "  DB_NAME=$DB_NAME"
    echo "  DB_USER=$DB_USER"
    echo "  DB_HOST=$DB_HOST"
    echo "  DB_PORT=$DB_PORT"
    echo "  BACKUP_DIR=$BACKUP_DIR"
    echo "  RETENTION_DAYS=$BACKUP_RETENTION_DAYS"
    echo "  Would create: $DUMP_FILE"
    echo "  S3 enabled:  $([ -n "${BACKUP_S3_BUCKET:-}" ] && command -v aws >/dev/null 2>&1 && echo yes || echo no)"
    echo "  B2 enabled:  $([ -n "${BACKUP_B2_BUCKET:-}" ] && command -v b2 >/dev/null 2>&1 && echo yes || echo no)"
    exit 0
fi

# ── Preflight ─────────────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR" || err_exit "no se pudo crear $BACKUP_DIR"
rotate_log_if_needed

command -v pg_dump >/dev/null 2>&1 || err_exit "pg_dump no está en PATH"

log "==== Inicio backup db=$DB_NAME host=$DB_HOST ===="

# ── pg_dump ───────────────────────────────────────────────────────────────
# --format=custom → permite pg_restore selectivo
# --compress=9    → máxima compresión
# --no-owner      → portable entre instalaciones
log "pg_dump → $DUMP_FILE"
if ! pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        --format=custom \
        --compress=9 \
        --no-owner \
        --file="$DUMP_FILE" \
        "$DB_NAME"; then
    err_exit "pg_dump falló"
fi

# Verificar tamaño > 0
if [ ! -s "$DUMP_FILE" ]; then
    err_exit "dump generado pero está vacío: $DUMP_FILE"
fi

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
log "dump OK ($DUMP_SIZE)"

# ── Upload S3 (opcional, solo si está configurado y aws CLI disponible) ──
if [ -n "${BACKUP_S3_BUCKET:-}" ]; then
    if command -v aws >/dev/null 2>&1; then
        log "Subiendo a S3: s3://${BACKUP_S3_BUCKET}/"
        if aws s3 cp "$DUMP_FILE" "s3://${BACKUP_S3_BUCKET}/$(basename "$DUMP_FILE")" >> "$LOG_FILE" 2>&1; then
            log "S3 upload OK"
        else
            log "WARN: S3 upload falló (backup local OK, revisar credenciales aws)"
        fi
    else
        log "WARN: BACKUP_S3_BUCKET seteado pero 'aws' no está en PATH — skip S3"
    fi
fi

# ── Upload Backblaze B2 (opcional) ────────────────────────────────────────
if [ -n "${BACKUP_B2_BUCKET:-}" ] && [ -n "${BACKUP_B2_KEY_ID:-}" ]; then
    if command -v b2 >/dev/null 2>&1; then
        log "Subiendo a B2: b2://${BACKUP_B2_BUCKET}/"
        if b2 upload-file "$BACKUP_B2_BUCKET" "$DUMP_FILE" "$(basename "$DUMP_FILE")" >> "$LOG_FILE" 2>&1; then
            log "B2 upload OK"
        else
            log "WARN: B2 upload falló (backup local OK)"
        fi
    else
        log "WARN: BACKUP_B2_BUCKET seteado pero 'b2' no está en PATH — skip B2"
    fi
fi

# ── Rotación: borrar dumps con > N días ───────────────────────────────────
log "Rotación: borrando dumps con más de ${BACKUP_RETENTION_DAYS} días"
DELETED=$(find "$BACKUP_DIR" -maxdepth 1 -name 'harmoni-db-*.dump' -mtime "+${BACKUP_RETENTION_DAYS}" -print -delete | wc -l)
log "Borrados: ${DELETED} archivo(s)"

# ── Resumen ───────────────────────────────────────────────────────────────
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)
log "Backup completo. Total ocupado en $BACKUP_DIR: $TOTAL_SIZE"
log "==== Fin backup OK ===="

exit 0
