#!/bin/bash
# crear-cliente.sh — Provisiona una nueva instancia Harmoni para un cliente
#
# Uso:
#   ./crear-cliente.sh <subdominio> <razon_social> [puerto]
#
# Ejemplo:
#   ./crear-cliente.sh acme "ACME Industries SAC" 8005
#
# Crea:
#   - BD PostgreSQL: harmoni_<sub>_db con usuario harmoni_<sub>
#   - Redis DB: <puerto-base>+offset (broker), +1 (results)
#   - Contenedores Docker: harmoni-<sub>-web, -celery, -beat
#   - Empresa con subdominio=<sub> y razón social
#   - Superuser admin / Demo2026!
#   - Nginx vhost <sub>.harmoni.pe
#   - DNS A record vía Cloudflare API
#   - SSL Let's Encrypt
#
# Requisitos previos en VPS:
#   - /opt/harmoni/app/ con código de Harmoni
#   - /opt/harmoni/secrets/cloudflare-dns-token con token (chmod 600)
#   - Imagen Docker harmoni-web-img:latest construida
#   - PostgreSQL + Redis + Nginx + Certbot instalados

set -euo pipefail

SUB="${1:?Falta subdominio}"
RAZON="${2:?Falta razón social}"
PORT="${3:-0}"

# Validar subdominio
if ! [[ "$SUB" =~ ^[a-z][a-z0-9-]{1,30}$ ]]; then
    echo "ERROR: subdominio inválido '$SUB'. Solo minúsculas, números y guiones (2-31 chars)." >&2
    exit 1
fi

# Reservados
case "$SUB" in
    www|admin|api|static|media|mail|smtp|ftp|ssh|ns1|ns2|cdn|staging|dev|demo)
        echo "ERROR: '$SUB' es subdominio reservado." >&2
        exit 1
        ;;
esac

# Asignar puerto automáticamente si es 0
if [ "$PORT" = "0" ]; then
    PORT=8004
    while ss -tlnp | grep -q ":$PORT "; do
        PORT=$((PORT + 1))
    done
    echo "Puerto auto-asignado: $PORT"
fi

# Redis DB number (offset desde 5 para no chocar con prod=0/1, demo=3/4)
REDIS_DB_BROKER=$((10 + (PORT - 8004) * 2))
REDIS_DB_RESULTS=$((REDIS_DB_BROKER + 1))

DB_NAME="harmoni_${SUB}_db"
DB_USER="harmoni_${SUB}"
DB_PASS="$(openssl rand -base64 16 | tr -d '/+=' | head -c 20)"
SECRET_KEY="$(openssl rand -base64 64 | tr -d '\n')"
HOST="${SUB}.harmoni.pe"

echo "==========================================="
echo "Provisionando cliente: $SUB"
echo "  Razón social:  $RAZON"
echo "  Host:          $HOST"
echo "  Puerto:        $PORT"
echo "  Redis DB:      $REDIS_DB_BROKER (broker), $REDIS_DB_RESULTS (results)"
echo "  BD:            $DB_NAME"
echo "==========================================="

# === 1. PostgreSQL ===
echo "[1/8] Creando BD..."
sudo -u postgres psql <<SQL
CREATE USER $DB_USER WITH PASSWORD '$DB_PASS';
CREATE DATABASE $DB_NAME OWNER $DB_USER;
SQL

sudo -u postgres psql -d "$DB_NAME" -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT ALL ON SCHEMA public TO $DB_USER;"

# Clonar schema de producción (más rápido que correr migrate con conflicts)
sudo -u postgres pg_dump --schema-only --no-owner --no-acl -d harmoni_db -f /tmp/schema_${SUB}.sql
sudo -u postgres psql -d "$DB_NAME" -f /tmp/schema_${SUB}.sql > /dev/null 2>&1

# Reasignar ownership
sudo -u postgres psql -d "$DB_NAME" <<SQL
DO \$\$
DECLARE r RECORD;
BEGIN
  FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
    EXECUTE 'ALTER TABLE public.' || quote_ident(r.tablename) || ' OWNER TO $DB_USER';
  END LOOP;
  FOR r IN SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema='public' LOOP
    EXECUTE 'ALTER SEQUENCE public.' || quote_ident(r.sequence_name) || ' OWNER TO $DB_USER';
  END LOOP;
END\$\$;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
SQL
rm /tmp/schema_${SUB}.sql

# === 2. Volúmenes ===
echo "[2/8] Creando volúmenes..."
mkdir -p /opt/harmoni-${SUB}/{staticfiles,media,logs}
chown -R 1000:1000 /opt/harmoni-${SUB}
chmod -R 777 /opt/harmoni-${SUB}/logs

# Guardar credenciales (root only)
cat > /opt/harmoni-${SUB}/.env <<ENV
# Variables de la instancia $SUB (referencia, no la usa Docker)
DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME
REDIS_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER
DJANGO_SECRET_KEY=$SECRET_KEY
DJANGO_ALLOWED_HOSTS=$HOST,212.56.34.166
PUERTO=$PORT
ENV
chmod 600 /opt/harmoni-${SUB}/.env

# === 3. Contenedores ===
echo "[3/8] Lanzando contenedores..."

docker run -d --name harmoni-${SUB}-web --network host --restart unless-stopped \
  -v /opt/harmoni/app:/app:ro \
  -v /opt/harmoni-${SUB}/staticfiles:/app/staticfiles \
  -v /opt/harmoni-${SUB}/media:/app/media \
  -v /opt/harmoni-${SUB}/logs:/app/logs \
  -e DJANGO_SETTINGS_MODULE=config.settings.production \
  -e "DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME" \
  -e "REDIS_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_BROKER_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_RESULT_BACKEND=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_RESULTS" \
  -e "DJANGO_SECRET_KEY=$SECRET_KEY" \
  -e "DJANGO_ALLOWED_HOSTS=$HOST,localhost,212.56.34.166" \
  -e "DJANGO_DEBUG=False" \
  -e "SECURE_SSL_REDIRECT=False" \
  -e "CSRF_TRUSTED_ORIGINS=https://$HOST" \
  harmoni-web-img:latest \
  gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120

docker run -d --name harmoni-${SUB}-celery --network host --restart unless-stopped \
  -v /opt/harmoni/app:/app:ro \
  -v /opt/harmoni-${SUB}/logs:/app/logs \
  -e DJANGO_SETTINGS_MODULE=config.settings.production \
  -e "DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME" \
  -e "REDIS_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_BROKER_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_RESULT_BACKEND=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_RESULTS" \
  -e "DJANGO_SECRET_KEY=$SECRET_KEY" \
  -e "DJANGO_ALLOWED_HOSTS=$HOST,localhost" \
  -e "DJANGO_DEBUG=False" \
  harmoni-web-img:latest \
  celery -A config worker --loglevel=info --concurrency=1

docker run -d --name harmoni-${SUB}-beat --network host --restart unless-stopped \
  -v /opt/harmoni/app:/app:ro \
  -v /opt/harmoni-${SUB}/logs:/app/logs \
  -e DJANGO_SETTINGS_MODULE=config.settings.production \
  -e "DATABASE_URL=postgresql://$DB_USER:$DB_PASS@localhost:5432/$DB_NAME" \
  -e "REDIS_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_BROKER_URL=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_BROKER" \
  -e "CELERY_RESULT_BACKEND=redis://:H4rm0n1_R3d1s_2026!@localhost:6379/$REDIS_DB_RESULTS" \
  -e "DJANGO_SECRET_KEY=$SECRET_KEY" \
  -e "DJANGO_ALLOWED_HOSTS=$HOST,localhost" \
  -e "DJANGO_DEBUG=False" \
  harmoni-web-img:latest \
  celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

sleep 6

# === 4. Datos iniciales ===
echo "[4/8] Creando Empresa + superuser..."
docker exec harmoni-${SUB}-web python manage.py migrate --fake --no-input > /dev/null 2>&1

ADMIN_PASS="$(openssl rand -base64 12 | tr -d '/+=' | head -c 14)"
docker exec harmoni-${SUB}-web python manage.py shell <<EOF
from django.contrib.auth import get_user_model
from empresas.models import Empresa
U = get_user_model()
u, c = U.objects.get_or_create(username='admin', defaults={'email':'admin@${SUB}.com'})
u.set_password('$ADMIN_PASS'); u.is_superuser=True; u.is_staff=True; u.is_active=True; u.save()
e, _ = Empresa.objects.get_or_create(
    subdominio='$SUB',
    defaults={
        'razon_social': '$RAZON',
        'nombre_comercial': '$RAZON',
        'ruc': '20000000000',
        'direccion': '',
        'email_rrhh': 'rrhh@${SUB}.com',
        'activa': True,
    },
)
print(f'Empresa creada: {e}, admin/$ADMIN_PASS')
EOF

docker exec harmoni-${SUB}-web python manage.py collectstatic --no-input > /dev/null 2>&1 || true

# === 5. Nginx vhost ===
echo "[5/8] Configurando Nginx..."
cat > /etc/nginx/sites-available/${HOST} <<NGINX
server {
    listen 80;
    server_name ${HOST};

    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files \$uri =404;
    }
    location / {
        return 301 https://\$host\$request_uri;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/${HOST} /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# === 6. DNS Cloudflare ===
echo "[6/8] Creando DNS A record..."
TOKEN=$(cat /opt/harmoni/secrets/cloudflare-dns-token)
ZONE_ID=842a08c0dbd4325a92e566ae2679cb1f
curl -4 -sS -X POST "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"type\":\"A\",\"name\":\"$SUB\",\"content\":\"212.56.34.166\",\"ttl\":300,\"proxied\":false}" > /tmp/dns-${SUB}.json
grep -q '"success":true' /tmp/dns-${SUB}.json && echo "  ✓ DNS creado" || { echo "  ✗ DNS error:"; cat /tmp/dns-${SUB}.json; exit 1; }

# === 7. Esperar propagación + SSL ===
echo "[7/8] Esperando propagación DNS..."
for i in {1..12}; do
    if [ -n "$(dig +short ${HOST} @1.1.1.1)" ]; then
        echo "  ✓ DNS propagado"
        break
    fi
    sleep 5
done

echo "[7/8] Generando SSL Let's Encrypt..."
certbot certonly --webroot -w /var/www/html -d ${HOST} \
  --agree-tos --email eflopezt@gmail.com --non-interactive --no-eff-email

# === 8. Vhost final HTTPS ===
echo "[8/8] Activando HTTPS..."
cat > /etc/nginx/sites-available/${HOST} <<NGINX
server {
    listen 80;
    server_name ${HOST};
    location /.well-known/acme-challenge/ {
        root /var/www/html;
        try_files \$uri =404;
    }
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl http2;
    server_name ${HOST};
    ssl_certificate /etc/letsencrypt/live/${HOST}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/${HOST}/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    client_max_body_size 50M;
    proxy_read_timeout 120s;

    location /static/ { alias /opt/harmoni-${SUB}/staticfiles/; expires 7d; }
    location /media/  { alias /opt/harmoni-${SUB}/media/; }
    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
NGINX
nginx -t && systemctl reload nginx

# === Resumen ===
echo ""
echo "==========================================="
echo "✅ CLIENTE PROVISIONADO"
echo "==========================================="
echo "  URL:       https://${HOST}"
echo "  Usuario:   admin"
echo "  Password:  $ADMIN_PASS"
echo "  BD:        $DB_NAME (user: $DB_USER, pass guardada en /opt/harmoni-${SUB}/.env)"
echo "  Puerto:    $PORT"
echo ""
echo "  Para dar de baja: ./eliminar-cliente.sh $SUB"
echo "==========================================="
