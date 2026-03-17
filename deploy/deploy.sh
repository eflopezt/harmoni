#!/bin/bash
# =============================================================================
# Harmoni ERP — Quick Deploy Script
# Uso: bash deploy/deploy.sh
# Sube cambios locales al VPS y reinicia los containers
# =============================================================================
set -e

SSH_KEY="$HOME/.ssh/id_ed25519"
VPS="root@212.56.34.166"
APP_DIR="/opt/harmoni/app"

echo "=== Harmoni Deploy ==="

# 1. Crear tarball (excluyendo archivos innecesarios)
echo "[1/4] Empaquetando..."
tar czf /tmp/harmoni-deploy.tar.gz \
  --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
  --exclude='db.sqlite3' --exclude='staticfiles' --exclude='logs' \
  --exclude='.env' --exclude='node_modules' --exclude='.venv' --exclude='.claude' \
  --exclude='media' --exclude='htmlcov' --exclude='.coverage' \
  .

# 2. Subir al VPS
echo "[2/4] Subiendo al VPS..."
scp -O -i "$SSH_KEY" /tmp/harmoni-deploy.tar.gz "$VPS:/tmp/harmoni-deploy.tar.gz"
rm /tmp/harmoni-deploy.tar.gz

# 3. Extraer, build y reiniciar
echo "[3/4] Desplegando en el VPS..."
ssh -i "$SSH_KEY" "$VPS" "bash -s" << 'REMOTE'
set -e
cd /opt/harmoni/app

# Preservar .env.production y docker-compose.prod.yml
cp .env.production /tmp/harmoni-env-backup 2>/dev/null || true
cp docker-compose.prod.yml /tmp/harmoni-compose-backup 2>/dev/null || true

# Extraer nuevo código
tar xzf /tmp/harmoni-deploy.tar.gz
rm /tmp/harmoni-deploy.tar.gz

# Restaurar configs de producción
cp /tmp/harmoni-env-backup .env.production 2>/dev/null || true
cp /tmp/harmoni-compose-backup docker-compose.prod.yml 2>/dev/null || true

# Permisos
chown -R deploy:deploy /opt/harmoni/app

# Build y reiniciar
COMPOSE_PROJECT_NAME=harmoni docker compose -f docker-compose.prod.yml build web 2>&1 | tail -3
COMPOSE_PROJECT_NAME=harmoni docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput 2>&1 | tail -5
COMPOSE_PROJECT_NAME=harmoni docker compose -f docker-compose.prod.yml run --rm \
  -v /opt/harmoni/staticfiles:/app/staticfiles web python manage.py collectstatic --noinput 2>&1 | tail -1
chmod -R 777 /opt/harmoni/staticfiles
COMPOSE_PROJECT_NAME=harmoni docker compose -f docker-compose.prod.yml up -d --force-recreate 2>&1 | grep -E 'Started|Healthy'
REMOTE

# 4. Verificar
echo "[4/4] Verificando..."
ssh -i "$SSH_KEY" "$VPS" "docker ps --format 'table {{.Names}}\t{{.Status}}' | grep harmoni"
echo ""
echo "=== Deploy completado: https://harmoni.pe ==="
