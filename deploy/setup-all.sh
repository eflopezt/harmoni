#!/usr/bin/env bash
# =============================================================================
# MASTER SCRIPT — Setup completo del VPS Contabo para Harmoni ERP
# =============================================================================
#
# INSTRUCCIONES DE USO:
#
# 1. Desde tu máquina local (Windows/Git Bash), copia todo al servidor:
#
#    scp -r deploy/ root@212.56.34.166:/root/deploy/
#
# 2. Conéctate al servidor:
#
#    ssh root@212.56.34.166
#
# 3. Ejecuta las fases EN ORDEN:
#
#    cd /root/deploy
#    bash 01-harden-server.sh      # Como root — crea usuario 'deploy'
#
#    ⚠️  ANTES de continuar:
#    - Agrega tu SSH key al servidor (desde otra terminal local):
#      ssh-copy-id -p 22 deploy@212.56.34.166
#    - Prueba: ssh -p 2222 deploy@212.56.34.166
#    - Reinicia SSH: sudo systemctl restart sshd
#
#    # Ya como usuario 'deploy':
#    ssh -p 2222 deploy@212.56.34.166
#    cd /root/deploy  # o copia los scripts a /home/deploy/
#    sudo cp -r /root/deploy /home/deploy/deploy && cd /home/deploy/deploy
#
#    bash 02-install-services.sh    # Instala PostgreSQL, Redis, Docker, etc.
#    exit                           # Salir y reconectar para grupo docker
#    ssh -p 2222 deploy@212.56.34.166
#    bash 03-setup-harmoni.sh       # Deploy de la app
#    bash 04-install-openclaw.sh    # Instalar OpenClaw
#
# =============================================================================

echo "Este script es solo documentación. Ejecuta cada fase por separado."
echo "Lee las instrucciones arriba o el README."
