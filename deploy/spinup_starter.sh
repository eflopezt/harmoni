#!/bin/bash
# =============================================================================
# spinup_starter.sh — provisiona un nuevo cliente Plan Starter
#
# Uso:
#   ./spinup_starter.sh <client_slug> <port>
#
# Ejemplo:
#   ./spinup_starter.sh pixelmotion 8100
#
# Qué hace:
#   1. Crea /opt/harmoni-starter/<slug>/ con estructura de volúmenes
#   2. Crea DB postgres harmoni_<slug> con user dedicado
#   3. Copia template .env.starter.example → .env.starter
#   4. Levanta contenedor con docker compose
#   5. Aplica migrations
#   6. Crea superuser inicial admin/temp_password
#
# Pre-requisitos:
#   - Docker + docker compose en host
#   - PostgreSQL nativo en host (puerto 5432)
#   - Nginx config separado para subdom <slug>.harmoni.pe (manual)
# =============================================================================

set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "Uso: $0 <client_slug> <port>"
  echo "Ejemplo: $0 pixelmotion 8100"
  exit 1
fi

SLUG=$1
PORT=$2
BASE_DIR=/opt/harmoni-starter/${SLUG}
DB_NAME=harmoni_${SLUG}
DB_USER=harmoni_${SLUG}
DB_PASS=$(openssl rand -hex 16)
DJANGO_SECRET=$(openssl rand -hex 32)

echo "─────────────────────────────────────────────────────"
echo "  Provisionando cliente Starter: ${SLUG}"
echo "  Puerto:   ${PORT}"
echo "  Base dir: ${BASE_DIR}"
echo "  DB:       ${DB_NAME}"
echo "─────────────────────────────────────────────────────"

# 1. Estructura de directorios
sudo mkdir -p "${BASE_DIR}"/{staticfiles,media,logs}
sudo chown -R "${USER}:${USER}" "${BASE_DIR}"

# 2. Base de datos
sudo -u postgres psql <<SQL
CREATE DATABASE ${DB_NAME};
CREATE USER ${DB_USER} WITH ENCRYPTED PASSWORD '${DB_PASS}';
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};
SQL

# 3. Archivos de configuración
cp .env.starter.example "${BASE_DIR}/.env.starter"
sed -i "s|CLIENT_SLUG=.*|CLIENT_SLUG=${SLUG}|" "${BASE_DIR}/.env.starter"
sed -i "s|STARTER_PORT=.*|STARTER_PORT=${PORT}|" "${BASE_DIR}/.env.starter"
sed -i "s|SECRET_KEY=.*|SECRET_KEY=${DJANGO_SECRET}|" "${BASE_DIR}/.env.starter"
sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@host.docker.internal:5432/${DB_NAME}|" "${BASE_DIR}/.env.starter"
sed -i "s|ALLOWED_HOSTS=.*|ALLOWED_HOSTS=${SLUG}.harmoni.pe,localhost|" "${BASE_DIR}/.env.starter"
cp docker-compose.starter.yml "${BASE_DIR}/"

# 4. Up
cd "${BASE_DIR}"
CLIENT_SLUG=${SLUG} STARTER_PORT=${PORT} docker compose -f docker-compose.starter.yml --env-file .env.starter up -d --build

# 5. Migrations
sleep 10
docker exec "harmoni-starter-${SLUG}" python manage.py migrate --noinput

# 6. Static files
docker exec "harmoni-starter-${SLUG}" python manage.py collectstatic --noinput

echo ""
echo "✓ Cliente ${SLUG} provisionado correctamente"
echo ""
echo "Próximos pasos:"
echo "  1. Crear superuser:"
echo "       docker exec -it harmoni-starter-${SLUG} python manage.py createsuperuser"
echo "  2. Configurar nginx para ${SLUG}.harmoni.pe → http://localhost:${PORT}"
echo "  3. Generar certificado SSL: certbot --nginx -d ${SLUG}.harmoni.pe"
echo ""
echo "Credenciales DB (guardar en password manager):"
echo "  DB:       ${DB_NAME}"
echo "  User:     ${DB_USER}"
echo "  Password: ${DB_PASS}"
echo ""
