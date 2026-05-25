# Backup & Recovery — Harmoni ERP

> Procedimiento oficial para backup automatizado de PostgreSQL y restauración ante
> incidente. Cubre el item 🟡 #6 del Plan Estabilización Q2 2026.

## Componentes

| Componente | Archivo | Responsabilidad |
|------------|---------|-----------------|
| Script bash | `deploy/backup-db.sh` | `pg_dump` + rotación + upload offsite opcional |
| Celery task | `core/tasks_backup.py::backup_db_diario` | Ejecuta el script, captura fallos a Sentry |
| Beat schedule | `config/settings/base.py` `CELERY_BEAT_SCHEDULE['backup-db-diario']` | 03:30 diario |
| Comando manual | `python manage.py backup_db_now [--dry-run]` | Backup ad-hoc o smoke test |

## Configuración por entorno

El script lee todo de variables de entorno con defaults sanos para el VPS de prod.

| Variable | Default | Notas |
|----------|---------|-------|
| `DB_NAME` | `harmoni_db` | Nombre de la base PostgreSQL |
| `DB_USER` | `harmoni` | Usuario PG (debe poder hacer `pg_dump`) |
| `DB_HOST` | `127.0.0.1` | Local en el VPS |
| `DB_PORT` | `5432` | |
| `BACKUP_DIR` | `/opt/harmoni/backups` | Directorio destino (crear con permisos correctos) |
| `BACKUP_RETENTION_DAYS` | `30` | Dumps con > N días se borran |
| `BACKUP_S3_BUCKET` | (vacío) | Si se define + `aws` CLI presente → upload a S3 |
| `BACKUP_B2_BUCKET` | (vacío) | Si se define + `b2` CLI presente → upload a Backblaze B2 |
| `BACKUP_B2_KEY_ID` | (vacío) | Requerido junto con `BACKUP_B2_BUCKET` |

Para que `pg_dump` no pida password en modo no interactivo, usar `~/.pgpass` del
usuario que corre el worker/beat (chmod 600).

## Activar offsite

### Opción A: AWS S3 (~$0.50/mes para bases <5GB)

1. Instalar AWS CLI en el container del beat:
   ```bash
   apt-get install -y awscli  # o pip install awscli
   ```
2. Configurar credenciales (en el `.env` del container o `~/.aws/credentials`):
   ```bash
   export AWS_ACCESS_KEY_ID=AKIA...
   export AWS_SECRET_ACCESS_KEY=...
   export AWS_DEFAULT_REGION=us-east-1
   export BACKUP_S3_BUCKET=harmoni-backups-prod
   ```
3. Crear bucket con versionado + lifecycle (Glacier después de 90 días):
   ```bash
   aws s3api create-bucket --bucket harmoni-backups-prod --region us-east-1
   aws s3api put-bucket-versioning --bucket harmoni-backups-prod \
       --versioning-configuration Status=Enabled
   ```

### Opción B: Backblaze B2 (~$5/mes para 1TB, recomendado por costo)

1. Instalar B2 CLI:
   ```bash
   pip install b2
   ```
2. Autorizar:
   ```bash
   b2 authorize-account "$BACKUP_B2_KEY_ID" "$BACKUP_B2_APPLICATION_KEY"
   ```
3. Setear env vars:
   ```bash
   export BACKUP_B2_BUCKET=harmoni-backups
   export BACKUP_B2_KEY_ID=000...
   ```

> **Nota**: Las dos opciones son mutuamente excluyentes a nivel de costo, pero
> el script soporta ambas activas simultáneamente (subirá a las dos) si así se
> configura. Recomendado: una sola.

## Restauración desde un dump

### Restore completo (DR scenario)

```bash
# 1. Detener servicios que escriben en DB
docker compose stop web worker beat

# 2. Crear DB nueva limpia (o DROP+CREATE)
psql -h 127.0.0.1 -U harmoni -d postgres -c "DROP DATABASE harmoni_db;"
psql -h 127.0.0.1 -U harmoni -d postgres -c "CREATE DATABASE harmoni_db OWNER harmoni;"

# 3. Restore desde el dump más reciente
pg_restore -h 127.0.0.1 -U harmoni -d harmoni_db --no-owner --jobs=4 \
    /opt/harmoni/backups/harmoni-db-20260524-033000.dump

# 4. Re-iniciar servicios
docker compose start web worker beat

# 5. Verificar
python manage.py check
python manage.py shell -c "from empresas.models import Empresa; print(Empresa.objects.count())"
```

### Restore parcial (solo una tabla)

```bash
# Listar contenido del dump
pg_restore -l /opt/harmoni/backups/harmoni-db-20260524-033000.dump > toc.txt

# Editar toc.txt para dejar solo las líneas que queremos restaurar
# Luego:
pg_restore -h 127.0.0.1 -U harmoni -d harmoni_db --no-owner -L toc.txt \
    /opt/harmoni/backups/harmoni-db-20260524-033000.dump
```

## Verificar salud del backup

### Smoke check diario manual

```bash
# 1. Hay dump de hoy?
ls -la /opt/harmoni/backups/ | grep "$(date +%Y%m%d)"

# 2. Tamaño esperado?
du -h /opt/harmoni/backups/harmoni-db-*.dump | tail -5
# Esperado: 50-500 MB para bases < 10GB de datos

# 3. El dump más reciente NO está corrupto?
pg_restore -l /opt/harmoni/backups/harmoni-db-$(date +%Y%m%d)*.dump > /dev/null \
    && echo "dump OK" || echo "dump CORRUPTO"

# 4. Logs sin errores recientes?
tail -50 /opt/harmoni/backups/backup.log
```

### Restore de prueba mensual (obligatorio según métrica plan estabilización)

El día 1 de cada mes, restaurar el último dump a una DB temporal para validar
que el backup es **realmente restorable** (no basta con que `pg_dump` no falle).

```bash
# 1. Crear DB temporal
createdb -h 127.0.0.1 -U harmoni harmoni_db_restore_test

# 2. Restaurar último dump
LATEST=$(ls -t /opt/harmoni/backups/harmoni-db-*.dump | head -1)
pg_restore -h 127.0.0.1 -U harmoni -d harmoni_db_restore_test --no-owner --jobs=4 "$LATEST"

# 3. Smoke check: contar registros clave
psql -h 127.0.0.1 -U harmoni -d harmoni_db_restore_test -c "
    SELECT
        (SELECT COUNT(*) FROM empresas_empresa) AS empresas,
        (SELECT COUNT(*) FROM personal_trabajador) AS trabajadores,
        (SELECT COUNT(*) FROM nominas_planilla) AS planillas;
"

# 4. Limpiar
dropdb -h 127.0.0.1 -U harmoni harmoni_db_restore_test
```

## Tamaño esperado

| Métrica | Valor típico (mayo 2026) |
|---------|--------------------------|
| Tamaño DB descomprimido | ~500 MB (Consorcio Stiler con 12 meses históricos) |
| Tamaño dump comprimido (`--compress=9`) | ~80–120 MB |
| Tiempo de `pg_dump` | 20–60 s |
| Tiempo de upload offsite | 30 s (B2) — 90 s (S3) |
| Acumulado 30 días local | ~3–4 GB |

Si el dump pasa de 1 GB comprimido, considerar:
- Mover tablas históricas (>3 años) a otra base.
- Subir frecuencia de rotación local (mantener solo 7 días local + 90 en offsite).
- Particionado por fecha en tablas grandes (`nominas_registrotareo`, `audit_log`).

## Alertas

El Celery task `backup_db_diario` captura a Sentry:
- Script no encontrado → `error`, tag `subsystem=backup`.
- Timeout (> 30 min) → `error` + retry una vez.
- `rc != 0` → `error` + stdout/stderr (últimos 2 KB) + retry.

Crear regla en Sentry: alertar a `eflopezt@gmail.com` si más de 1 evento
`subsystem=backup` en 24h.

## Histórico

- **2026-05-24** — Creado en sprint estabilización Q2. Reemplaza el script
  `backup-db.sh` original (que solo hacía `pg_dump | gzip` sin rotación
  configurable, sin tarea Celery, sin offsite).
