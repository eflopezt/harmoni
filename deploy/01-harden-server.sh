#!/usr/bin/env bash
# =============================================================================
# FASE 1: Asegurar el servidor (Ubuntu 24.04 - Contabo VPS)
# Ejecutar como root: bash 01-harden-server.sh
# =============================================================================
set -euo pipefail

# --- Colores ---
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# --- Validar que somos root ---
[[ $EUID -ne 0 ]] && error "Este script debe ejecutarse como root"

# --- Variables configurables ---
NEW_USER="deploy"
SSH_PORT=2222

info "=== FASE 1: Hardening del servidor ==="

# 1. Actualizar sistema
info "Actualizando sistema..."
apt-get update && apt-get upgrade -y
apt-get install -y curl wget git vim htop unzip software-properties-common \
    fail2ban ufw apt-transport-https ca-certificates gnupg lsb-release

# 2. Crear usuario no-root
info "Creando usuario '${NEW_USER}'..."
if id "$NEW_USER" &>/dev/null; then
    warn "Usuario '${NEW_USER}' ya existe, saltando..."
else
    adduser --disabled-password --gecos "" "$NEW_USER"
    usermod -aG sudo "$NEW_USER"
    echo "${NEW_USER} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${NEW_USER}
    chmod 440 /etc/sudoers.d/${NEW_USER}
    info "Usuario '${NEW_USER}' creado con sudo sin password"
fi

# 3. Copiar SSH keys del root al nuevo usuario
info "Configurando SSH keys para '${NEW_USER}'..."
mkdir -p /home/${NEW_USER}/.ssh
if [ -f /root/.ssh/authorized_keys ]; then
    cp /root/.ssh/authorized_keys /home/${NEW_USER}/.ssh/
fi
chown -R ${NEW_USER}:${NEW_USER} /home/${NEW_USER}/.ssh
chmod 700 /home/${NEW_USER}/.ssh
chmod 600 /home/${NEW_USER}/.ssh/authorized_keys 2>/dev/null || true

# 4. Configurar SSH seguro
info "Endureciendo configuración SSH..."
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.bak

cat > /etc/ssh/sshd_config.d/hardened.conf << 'SSHEOF'
Port 2222
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
AuthorizedKeysFile .ssh/authorized_keys
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
AllowUsers deploy
SSHEOF

# 5. Configurar firewall UFW
info "Configurando firewall UFW..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ${SSH_PORT}/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
echo "y" | ufw enable
ufw status verbose

# 6. Configurar Fail2Ban
info "Configurando Fail2Ban..."
cat > /etc/fail2ban/jail.local << EOF
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 3
backend  = systemd

[sshd]
enabled = true
port    = ${SSH_PORT}
filter  = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime  = 86400
EOF

systemctl enable fail2ban
systemctl restart fail2ban

# 7. Configurar timezone
info "Configurando timezone a America/Lima..."
timedatectl set-timezone America/Lima

# 8. Configurar swap (2GB) si no existe
if ! swapon --show | grep -q '/swapfile'; then
    info "Creando swap de 2GB..."
    fallocate -l 2G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    # Optimizar swappiness
    echo 'vm.swappiness=10' >> /etc/sysctl.conf
    sysctl -p
else
    warn "Swap ya existe, saltando..."
fi

# 9. Límites de seguridad del kernel
info "Aplicando sysctl de seguridad..."
cat >> /etc/sysctl.conf << 'EOF'

# Hardening
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
net.ipv4.tcp_syncookies = 1
EOF
sysctl -p

# 10. Automatic security updates
info "Habilitando actualizaciones automáticas de seguridad..."
apt-get install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades

info "=== FASE 1 COMPLETADA ==="
echo ""
warn "╔══════════════════════════════════════════════════════════════════╗"
warn "║  IMPORTANTE: Antes de cerrar esta sesión SSH:                   ║"
warn "║                                                                 ║"
warn "║  1. Agrega tu SSH key pública al servidor:                      ║"
warn "║     ssh-copy-id -p 22 deploy@212.56.34.166                      ║"
warn "║     (desde tu máquina local, ANTES de reiniciar SSH)            ║"
warn "║                                                                 ║"
warn "║  2. Prueba la conexión en OTRA terminal:                        ║"
warn "║     ssh -p 2222 deploy@212.56.34.166                            ║"
warn "║                                                                 ║"
warn "║  3. Si funciona, reinicia SSH:                                  ║"
warn "║     sudo systemctl restart sshd                                 ║"
warn "║                                                                 ║"
warn "║  ⚠ Si NO agregas tu SSH key, perderás acceso al servidor ⚠     ║"
warn "╚══════════════════════════════════════════════════════════════════╝"
echo ""
info "Siguiente paso: bash 02-install-services.sh"
