#!/bin/bash
# eliminar-cliente.sh — Da de baja una instancia Harmoni
#
# Uso: ./eliminar-cliente.sh <subdominio> [--keep-db]
#
# Por defecto borra todo. Con --keep-db conserva la BD para backup.

set -euo pipefail

SUB="${1:?Falta subdominio}"
KEEP_DB="${2:-}"
HOST="${SUB}.harmoni.pe"

echo "Eliminando cliente: $SUB ($HOST)"
read -p "¿Confirmás? (escribe 'si' para continuar): " CONFIRM
[ "$CONFIRM" = "si" ] || { echo "Cancelado"; exit 0; }

# Contenedores
docker stop harmoni-${SUB}-web harmoni-${SUB}-celery harmoni-${SUB}-beat 2>/dev/null || true
docker rm   harmoni-${SUB}-web harmoni-${SUB}-celery harmoni-${SUB}-beat 2>/dev/null || true

# Nginx
rm -f /etc/nginx/sites-enabled/${HOST}
rm -f /etc/nginx/sites-available/${HOST}
nginx -t && systemctl reload nginx

# DNS Cloudflare
TOKEN=$(cat /opt/harmoni/secrets/cloudflare-dns-token)
ZONE_ID=842a08c0dbd4325a92e566ae2679cb1f
RECORD_ID=$(curl -4 -sS "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records?type=A&name=${HOST}" \
    -H "Authorization: Bearer $TOKEN" | python3 -c "import sys,json;d=json.load(sys.stdin); print(d['result'][0]['id'] if d['result'] else '')")
if [ -n "$RECORD_ID" ]; then
    curl -4 -sS -X DELETE "https://api.cloudflare.com/client/v4/zones/$ZONE_ID/dns_records/$RECORD_ID" \
        -H "Authorization: Bearer $TOKEN" > /dev/null
    echo "DNS eliminado"
fi

# SSL cert
certbot delete --cert-name ${HOST} --non-interactive 2>/dev/null || true

# Volúmenes
rm -rf /opt/harmoni-${SUB}/

# BD
if [ "$KEEP_DB" != "--keep-db" ]; then
    sudo -u postgres psql <<SQL
DROP DATABASE IF EXISTS harmoni_${SUB}_db;
DROP USER IF EXISTS harmoni_${SUB};
SQL
    echo "BD eliminada"
else
    echo "BD conservada (--keep-db)"
fi

echo "✓ Cliente $SUB eliminado"
