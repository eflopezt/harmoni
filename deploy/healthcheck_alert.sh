#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────
# Monitoreo EXTERNO de /health/ (prod + demo) con alerta por Telegram
# y/o WhatsApp (gateway OpenClaw). Corre en el HOST del VPS vía cron,
# fuera de Docker: si la app o el contenedor mueren, este script vive.
#
# Instalación (una vez, como root):
#   cp /opt/harmoni/app/deploy/healthcheck.env.example /opt/harmoni/healthcheck.env
#   nano /opt/harmoni/healthcheck.env   # poner credenciales
#   chmod 600 /opt/harmoni/healthcheck.env
#   crontab -e →  */5 * * * * /opt/harmoni/app/deploy/healthcheck_alert.sh >> /var/log/harmoni_healthcheck.log 2>&1
#
# Anti-spam: solo alerta en CAMBIO de estado (OK→DOWN y DOWN→OK), con un
# reintento a los 10s para no alertar por blips transitorios.
# Sin credenciales configuradas igual deja log (estado por chequeo).
# ─────────────────────────────────────────────────────────────────────
set -u

ENV_FILE="${HEALTHCHECK_ENV:-/opt/harmoni/healthcheck.env}"
STATE_DIR=/var/tmp/harmoni_health
mkdir -p "$STATE_DIR"
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && . "$ENV_FILE"

alert() {
    local msg="$1"
    # Telegram (https://core.telegram.org/bots/api#sendmessage)
    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
        curl -s -m 15 "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d chat_id="${TELEGRAM_CHAT_ID}" \
            --data-urlencode text="$msg" >/dev/null || true
    fi
    # WhatsApp vía gateway OpenClaw (mismo API que usa la app:
    # POST /api/sendMessage {phone, message})
    if [ -n "${OPENCLAW_URL:-}" ] && [ -n "${WHATSAPP_TO:-}" ]; then
        local json
        json=$(printf '{"phone":"%s","message":"%s"}' "$WHATSAPP_TO" \
               "$(printf '%s' "$msg" | sed 's/"/\\"/g')")
        curl -s -m 15 -X POST "${OPENCLAW_URL%/}/api/sendMessage" \
            -H 'Content-Type: application/json' \
            ${OPENCLAW_TOKEN:+-H "Authorization: Bearer $OPENCLAW_TOKEN"} \
            -d "$json" >/dev/null || true
    fi
}

check() {
    local name="$1" url="$2"
    local state_file="$STATE_DIR/$name.state"
    local prev="OK"
    [ -f "$state_file" ] && prev=$(cat "$state_file")

    local code
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || echo 000)
    if [ "$code" != "200" ]; then
        sleep 10  # reintento: evita falsos positivos por blips
        code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "$url" || echo 000)
    fi

    local now="OK"
    [ "$code" != "200" ] && now="DOWN"
    echo "$now" > "$state_file"

    if [ "$now" != "$prev" ]; then
        if [ "$now" = "DOWN" ]; then
            alert "🔴 Harmoni $name CAÍDO — $url respondió HTTP $code ($(date '+%F %T'))"
        else
            alert "✅ Harmoni $name recuperado — $url responde 200 ($(date '+%F %T'))"
        fi
    fi
    echo "$(date '+%F %T') $name HTTP=$code estado=$now"
}

check prod "https://harmoni.pe/health/"
check demo "https://demo.harmoni.pe/health/"
