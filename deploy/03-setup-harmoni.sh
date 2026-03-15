#!/usr/bin/env bash
# =============================================================================
# FASE 3: Setup de Harmoni ERP (Deploy con Docker + Nginx + SSL)
# Ejecutar como: deploy
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

APP_DIR="/opt/harmoni/app"
DOMAIN_1="harmoni.pe"
DOMAIN_2="nexotalent.pe"

info "=== FASE 3: Deploy de Harmoni ERP ==="

# ─── 1. Clonar o actualizar repositorio ─────────────────────────────────────
if [ -d "${APP_DIR}/.git" ]; then
    info "Repositorio existente, actualizando..."
    cd "$APP_DIR"
    git pull origin main
else
    info "Clonando repositorio..."
    # Cambiar esta URL por tu repo real
    warn "EDITA este script con la URL de tu repositorio Git"
    warn "Ejemplo: git clone https://github.com/tu-usuario/harmoni.git ${APP_DIR}"
    echo ""
    read -p "URL del repositorio Git (o 'skip' para copiar manualmente): " REPO_URL
    if [ "$REPO_URL" != "skip" ]; then
        git clone "$REPO_URL" "$APP_DIR"
    else
        warn "Copia manual: scp -P 2222 -r ./Harmoni/* deploy@212.56.34.166:/opt/harmoni/app/"
        info "Después de copiar, vuelve a ejecutar este script."
        exit 0
    fi
fi

cd "$APP_DIR"

# ─── 2. Copiar archivos de deploy ───────────────────────────────────────────
info "Copiando archivos de producción..."
if [ -f deploy/docker-compose.prod.yml ]; then
    cp deploy/docker-compose.prod.yml docker-compose.prod.yml
fi

# Verificar que existe .env.production
if [ ! -f .env.production ]; then
    if [ -f deploy/.env.production ]; then
        cp deploy/.env.production .env.production
        warn "Archivo .env.production copiado — EDITA las credenciales antes de continuar"
        warn "  nano /opt/harmoni/app/.env.production"
        read -p "Presiona Enter cuando hayas editado el .env.production..."
    else
        error "No se encontró .env.production. Crea uno basado en deploy/.env.production"
    fi
fi

# ─── 3. Generar SECRET_KEY si falta ─────────────────────────────────────────
if grep -q "CAMBIAR-genera" .env.production; then
    info "Generando DJANGO_SECRET_KEY..."
    NEW_KEY=$(python3 -c "import secrets; print(secrets.token_urlsafe(50))")
    sed -i "s|DJANGO_SECRET_KEY=CAMBIAR.*|DJANGO_SECRET_KEY=${NEW_KEY}|" .env.production
    info "SECRET_KEY generado ✓"
fi

# ─── 4. Configurar Nginx ────────────────────────────────────────────────────
info "Configurando Nginx..."
sudo mkdir -p /var/www/certbot

# Copiar configs de nginx
sudo cp deploy/nginx/harmoni.pe.conf /etc/nginx/sites-available/harmoni.pe
sudo cp deploy/nginx/nexotalent.pe.conf /etc/nginx/sites-available/nexotalent.pe

# Habilitar sites
sudo ln -sf /etc/nginx/sites-available/harmoni.pe /etc/nginx/sites-enabled/
sudo ln -sf /etc/nginx/sites-available/nexotalent.pe /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Temporalmente usar HTTP-only para obtener certificados
# Comentar bloque SSL hasta tener certificados
for CONF in /etc/nginx/sites-available/harmoni.pe /etc/nginx/sites-available/nexotalent.pe; do
    # Comentar el bloque del server 443 temporalmente
    sudo sed -i '/listen 443/,/^}/s/^/#/' "$CONF"
    # Descomentar redirect para que pase tráfico directo
    sudo sed -i 's|return 301 https://\$host\$request_uri;|proxy_pass http://127.0.0.1:8000;|' "$CONF"
done

sudo nginx -t && sudo systemctl reload nginx
info "Nginx configurado ✓"

# ─── 5. Build y arrancar Docker ──────────────────────────────────────────────
info "Construyendo contenedores Docker..."
docker compose -f docker-compose.prod.yml build

info "Ejecutando migraciones..."
docker compose -f docker-compose.prod.yml run --rm web python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml run --rm web python manage.py createcachetable

info "Recopilando archivos estáticos..."
docker compose -f docker-compose.prod.yml run --rm web python manage.py collectstatic --noinput

info "Cargando fixtures..."
docker compose -f docker-compose.prod.yml run --rm web python manage.py loaddata personal/fixtures/empleados_280.json || warn "Fixture de empleados no encontrado"
docker compose -f docker-compose.prod.yml run --rm web python manage.py setup_harmoni || warn "setup_harmoni no disponible"
docker compose -f docker-compose.prod.yml run --rm web python manage.py create_demo_users || warn "create_demo_users no disponible"

info "Arrancando servicios..."
docker compose -f docker-compose.prod.yml up -d
sleep 5
docker compose -f docker-compose.prod.yml ps

# ─── 6. Obtener certificados SSL ─────────────────────────────────────────────
info "Obteniendo certificados SSL con Let's Encrypt..."
echo ""
warn "REQUISITO: Los dominios deben apuntar a la IP 212.56.34.166"
warn "Configura los DNS A records antes de continuar:"
warn "  ${DOMAIN_1}     → 212.56.34.166"
warn "  www.${DOMAIN_1} → 212.56.34.166"
warn "  ${DOMAIN_2}     → 212.56.34.166"
warn "  www.${DOMAIN_2} → 212.56.34.166"
echo ""
read -p "¿Los DNS ya están configurados? (y/n): " DNS_READY

if [ "$DNS_READY" = "y" ]; then
    read -p "Email para Let's Encrypt (para notificaciones de renovación): " LE_EMAIL

    # Obtener certificado para harmoni.pe
    sudo certbot --nginx -d ${DOMAIN_1} -d www.${DOMAIN_1} \
        --email "$LE_EMAIL" --agree-tos --non-interactive --redirect || \
        warn "Certbot falló para ${DOMAIN_1} — verifica los DNS"

    # Obtener certificado para nexotalent.pe
    sudo certbot --nginx -d ${DOMAIN_2} -d www.${DOMAIN_2} \
        --email "$LE_EMAIL" --agree-tos --non-interactive --redirect || \
        warn "Certbot falló para ${DOMAIN_2} — verifica los DNS"

    # Verificar renovación automática
    sudo certbot renew --dry-run
    info "Certificados SSL instalados ✓"
else
    warn "SSL pospuesto — ejecuta manualmente cuando los DNS estén listos:"
    warn "  sudo certbot --nginx -d ${DOMAIN_1} -d www.${DOMAIN_1}"
    warn "  sudo certbot --nginx -d ${DOMAIN_2} -d www.${DOMAIN_2}"
fi

# ─── 7. Restaurar nginx con SSL ─────────────────────────────────────────────
# Restaurar los configs originales (Certbot ya los habrá modificado si corrió)
sudo cp deploy/nginx/harmoni.pe.conf /etc/nginx/sites-available/harmoni.pe
sudo cp deploy/nginx/nexotalent.pe.conf /etc/nginx/sites-available/nexotalent.pe
sudo nginx -t && sudo systemctl reload nginx

# ─── 8. Cron para backups ────────────────────────────────────────────────────
info "Configurando backup diario de PostgreSQL..."
cat > /opt/harmoni/backups/backup-db.sh << 'BKEOF'
#!/bin/bash
BACKUP_DIR="/opt/harmoni/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PGPASSWORD="H4rm0n1_Pr0d_2026!" pg_dump -U harmoni -h localhost harmoni_db | gzip > "${BACKUP_DIR}/harmoni_db_${TIMESTAMP}.sql.gz"
# Mantener solo los últimos 7 días
find "${BACKUP_DIR}" -name "harmoni_db_*.sql.gz" -mtime +7 -delete
BKEOF
chmod +x /opt/harmoni/backups/backup-db.sh
(crontab -l 2>/dev/null; echo "0 3 * * * /opt/harmoni/backups/backup-db.sh") | sort -u | crontab -
info "Backup diario configurado (3:00 AM) ✓"

info "=== FASE 3 COMPLETADA ==="
echo ""
echo "Harmoni ERP está corriendo en:"
echo "  http://212.56.34.166"
echo "  https://${DOMAIN_1} (cuando SSL esté listo)"
echo "  https://${DOMAIN_2} (cuando SSL esté listo)"
echo ""
echo "Comandos útiles:"
echo "  docker compose -f docker-compose.prod.yml logs -f    # Ver logs"
echo "  docker compose -f docker-compose.prod.yml restart     # Reiniciar"
echo "  docker compose -f docker-compose.prod.yml down        # Parar"
echo ""
info "Siguiente paso: bash 04-install-openclaw.sh"
