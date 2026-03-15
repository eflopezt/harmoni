#!/usr/bin/env bash
# =============================================================================
# FASE 2: Instalar servicios + tuning de rendimiento
# Ejecutar como: deploy (con sudo)
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"

info "=== FASE 2: Instalación de servicios + optimización ==="

# ─── 1. PostgreSQL 16 + pgvector ─────────────────────────────────────────────
info "Instalando PostgreSQL 16..."
sudo sh -c 'echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list'
wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | sudo apt-key add -
sudo apt-get update
sudo apt-get install -y postgresql-16 postgresql-contrib-16 libpq-dev

info "Instalando pgvector..."
sudo apt-get install -y postgresql-16-pgvector

# Aplicar tuning de PostgreSQL
info "Aplicando tuning de PostgreSQL..."
sudo cp "${DEPLOY_DIR}/postgres/postgresql.conf" /etc/postgresql/16/main/conf.d/harmoni.conf

# Configurar bases de datos
info "Configurando bases de datos..."
sudo -u postgres psql << 'SQLEOF'
-- === Harmoni ERP ===
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'harmoni') THEN
        CREATE ROLE harmoni WITH LOGIN PASSWORD 'H4rm0n1_Pr0d_2026!';
    END IF;
END $$;
CREATE DATABASE harmoni_db OWNER harmoni;
GRANT ALL PRIVILEGES ON DATABASE harmoni_db TO harmoni;
\c harmoni_db
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- === NexoTalent ===
DO $$ BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nexotalent') THEN
        CREATE ROLE nexotalent WITH LOGIN PASSWORD 'N3x0T4l3nt_Pr0d_2026!';
    END IF;
END $$;
CREATE DATABASE nexotalent_db OWNER nexotalent;
GRANT ALL PRIVILEGES ON DATABASE nexotalent_db TO nexotalent;
\c nexotalent_db
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verificar
\l
SQLEOF

# Permitir conexiones con password
sudo sed -i 's/local\s*all\s*all\s*peer/local   all             all                                     md5/' /etc/postgresql/16/main/pg_hba.conf
sudo systemctl restart postgresql
info "PostgreSQL 16 + pgvector instalado ✓ (DBs: harmoni_db, nexotalent_db)"

# ─── 2. Redis ────────────────────────────────────────────────────────────────
info "Instalando Redis..."
sudo apt-get install -y redis-server

# Aplicar config optimizada
info "Aplicando config optimizada de Redis..."
sudo cp /etc/redis/redis.conf /etc/redis/redis.conf.bak
sudo cp "${DEPLOY_DIR}/redis/redis.conf" /etc/redis/redis.conf

sudo systemctl enable redis-server
sudo systemctl restart redis-server
redis-cli -a "H4rm0n1_R3d1s_2026!" ping
info "Redis instalado y optimizado ✓ (maxmemory: 200mb, policy: allkeys-lru)"

# ─── 3. Docker + Docker Compose ──────────────────────────────────────────────
info "Instalando Docker..."
sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker deploy
info "Docker instalado ✓"

# ─── 4. Nginx ────────────────────────────────────────────────────────────────
info "Instalando Nginx..."
sudo apt-get install -y nginx

# Aplicar nginx.conf optimizado
info "Aplicando nginx.conf optimizado..."
sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
sudo cp "${DEPLOY_DIR}/nginx/nginx.conf" /etc/nginx/nginx.conf

sudo systemctl enable nginx
sudo systemctl start nginx
info "Nginx instalado y optimizado ✓ (epoll, gzip, file cache, rate limiting)"

# ─── 5. Certbot ──────────────────────────────────────────────────────────────
info "Instalando Certbot..."
sudo apt-get install -y certbot python3-certbot-nginx
info "Certbot instalado ✓"

# ─── 6. Node.js 22 LTS (para OpenClaw) ───────────────────────────────────────
info "Instalando Node.js 22 LTS..."
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
info "Node.js instalado ✓ ($(node --version))"

# ─── 7. Kernel tuning ────────────────────────────────────────────────────────
info "Aplicando tuning del kernel..."
sudo cp "${DEPLOY_DIR}/sysctl/99-vps-webserver.conf" /etc/sysctl.d/
sudo sysctl -p /etc/sysctl.d/99-vps-webserver.conf

# File descriptor limits
sudo tee /etc/security/limits.d/99-nofile.conf > /dev/null << 'EOF'
*    soft    nofile    65535
*    hard    nofile    65535
root soft    nofile    65535
root hard    nofile    65535
EOF
info "Kernel tuning aplicado ✓ (BBR, TCP optimizado, file descriptors)"

# ─── 8. Estructura de directorios ────────────────────────────────────────────
info "Creando estructura de directorios..."
sudo mkdir -p /opt/harmoni/{app,backups,logs,media,staticfiles}
sudo mkdir -p /opt/nexotalent/{app,backups,logs,media,staticfiles}
sudo mkdir -p /opt/openclaw
sudo mkdir -p /var/www/certbot
sudo chown -R deploy:deploy /opt/harmoni /opt/nexotalent /opt/openclaw

# ─── 9. Swap (si no existe) ──────────────────────────────────────────────────
if ! swapon --show | grep -q '/swapfile'; then
    # Detectar RAM y ajustar swap
    TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
    if [ "$TOTAL_RAM_MB" -le 4096 ]; then
        SWAP_SIZE="2G"
    else
        SWAP_SIZE="4G"
    fi
    info "Creando swap de ${SWAP_SIZE} (RAM detectada: ${TOTAL_RAM_MB}MB)..."
    sudo fallocate -l ${SWAP_SIZE} /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

# ─── Resumen ─────────────────────────────────────────────────────────────────
TOTAL_RAM_MB=$(free -m | awk '/^Mem:/{print $2}')
info "=== FASE 2 COMPLETADA ==="
echo ""
echo "┌─────────────────────────────────────────────────────┐"
echo "│  Servicios instalados + optimizados                 │"
echo "├─────────────────────────────────────────────────────┤"
echo "│  ✓ PostgreSQL 16 + pgvector                        │"
echo "│    ├── harmoni_db   (user: harmoni)                │"
echo "│    └── nexotalent_db (user: nexotalent)            │"
echo "│  ✓ Redis 7 (200mb maxmemory, LRU eviction)        │"
echo "│  ✓ Docker $(docker --version | grep -oP '\d+\.\d+\.\d+')                                    │"
echo "│  ✓ Nginx (epoll, gzip, rate limiting)              │"
echo "│  ✓ Certbot (Let's Encrypt)                         │"
echo "│  ✓ Node.js $(node --version)                               │"
echo "│  ✓ Kernel tuning (BBR, TCP, file descriptors)      │"
echo "│  RAM total: ${TOTAL_RAM_MB}MB                             │"
echo "└─────────────────────────────────────────────────────┘"
echo ""
if [ "$TOTAL_RAM_MB" -le 4096 ]; then
    warn "VPS de 4GB detectado — usando configuración conservadora"
    warn "Considera upgrade a 8GB si vas a correr ambos proyectos + OpenClaw"
fi
echo ""
warn "IMPORTANTE: Cierra sesión y reconecta para que el grupo 'docker' tome efecto:"
warn "  exit && ssh -p 2222 deploy@212.56.34.166"
echo ""
info "Siguiente paso: bash 03-setup-harmoni.sh"
