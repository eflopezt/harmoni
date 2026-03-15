#!/usr/bin/env bash
# =============================================================================
# FASE 4: Instalar OpenClaw — Asistente AI personal
# Ejecutar como: deploy
# =============================================================================
set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }

OPENCLAW_DIR="/opt/openclaw"

info "=== FASE 4: Instalación de OpenClaw ==="

# ─── 1. Instalar OpenClaw ────────────────────────────────────────────────────
info "Instalando OpenClaw via npm..."
cd "$OPENCLAW_DIR"

# Instalar globalmente
sudo npm install -g clawdbot@latest

info "OpenClaw instalado ✓ (versión: $(npx clawdbot --version 2>/dev/null || echo 'verificar'))"

# ─── 2. Ejecutar onboarding wizard ──────────────────────────────────────────
echo ""
info "Iniciando wizard de configuración de OpenClaw..."
warn "El wizard te guiará paso a paso para configurar:"
warn "  - API key (Claude, GPT, Gemini, etc.)"
warn "  - Canales (WhatsApp, Telegram, Discord, etc.)"
warn "  - Skills y permisos"
echo ""

# Crear directorio de datos
mkdir -p "$OPENCLAW_DIR/data"

# Ejecutar onboarding
openclaw onboard

# ─── 3. Configurar como servicio systemd ─────────────────────────────────────
info "Creando servicio systemd para OpenClaw..."
sudo tee /etc/systemd/system/openclaw.service > /dev/null << EOF
[Unit]
Description=OpenClaw AI Assistant
After=network.target

[Service]
Type=simple
User=deploy
WorkingDirectory=${OPENCLAW_DIR}
ExecStart=$(which openclaw) start
Restart=always
RestartSec=10
Environment=NODE_ENV=production

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable openclaw
sudo systemctl start openclaw

info "=== FASE 4 COMPLETADA ==="
echo ""
echo "OpenClaw está corriendo como servicio systemd"
echo ""
echo "Comandos útiles:"
echo "  sudo systemctl status openclaw     # Estado"
echo "  sudo systemctl restart openclaw    # Reiniciar"
echo "  sudo journalctl -u openclaw -f     # Ver logs"
echo "  openclaw onboard                   # Reconfigurar"
echo ""
info "¡Setup del servidor completo!"
