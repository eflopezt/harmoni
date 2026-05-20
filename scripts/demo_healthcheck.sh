#!/bin/bash
# Demo healthcheck — corre desde local o desde el VPS
# Uso: bash scripts/demo_healthcheck.sh
# Output: status de las páginas críticas del demo + security headers

DEMO_URL="${DEMO_URL:-https://demo.harmoni.pe}"
COOKIES_ADMIN="/tmp/.demo_hc_admin.txt"
COOKIES_TRAB="/tmp/.demo_hc_trab.txt"

cleanup() { rm -f "$COOKIES_ADMIN" "$COOKIES_TRAB" 2>/dev/null; }
trap cleanup EXIT

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok=0; fail=0; warn=0
check() {
    local name="$1" code="$2" expected="$3"
    if [ "$code" = "$expected" ]; then
        echo -e "  ${GREEN}✓${NC} $name ($code)"
        ok=$((ok+1))
    else
        echo -e "  ${RED}✗${NC} $name ($code, esperado $expected)"
        fail=$((fail+1))
    fi
}

warn_check() {
    local name="$1" actual="$2"
    if [ -n "$actual" ]; then
        echo -e "  ${GREEN}✓${NC} $name: $actual"
        ok=$((ok+1))
    else
        echo -e "  ${YELLOW}⚠${NC} $name no presente"
        warn=$((warn+1))
    fi
}

echo "=== Harmoni Demo Healthcheck ==="
echo "URL: $DEMO_URL"
echo ""

# 1. Login admin
echo "1. Login admin (demo/demo)"
csrf=$(curl -s -c "$COOKIES_ADMIN" "$DEMO_URL/login/" | grep -oP 'csrfmiddlewaretoken["\s]*value=["\s]*\K[^"]+' | head -1)
admin_login=$(curl -s -b "$COOKIES_ADMIN" -c "$COOKIES_ADMIN" -H "Referer: $DEMO_URL/login/" \
    -d "csrfmiddlewaretoken=$csrf&username=demo&password=demo&next=/" \
    "$DEMO_URL/login/" -o /dev/null -w "%{http_code}")
check "Login admin" "$admin_login" "302"

# 2. Páginas admin críticas
echo ""
echo "2. Páginas admin críticas"
for p in / /personal/ /asistencia/ /asistencia/reportes/ /nominas/ /empresas/ /reclutamiento/ /vacaciones/ /capacitaciones/; do
    code=$(curl -s -b "$COOKIES_ADMIN" -o /dev/null -w "%{http_code}" -m 15 "$DEMO_URL$p")
    check "GET $p" "$code" "200"
done

# 3. Multi-empresa filter
echo ""
echo "3. Filtro multi-empresa (debería retornar 200, no 500)"
for emp in 1 2 3; do
    code=$(curl -s -b "$COOKIES_ADMIN" -o /dev/null -w "%{http_code}" -m 15 "$DEMO_URL/personal/?empresa=$emp")
    check "Personal empresa=$emp" "$code" "200"
done

# 4. Exports SUNAT
echo ""
echo "4. Exports SUNAT (PLAME/T-Registro)"
for sufijo in plame tregistro; do
    code=$(curl -s -b "$COOKIES_ADMIN" -o /dev/null -w "%{http_code}" -m 15 "$DEMO_URL/nominas/periodos/4/$sufijo/")
    check "Export $sufijo" "$code" "200"
done

# 5. Login trabajador (DNI gastronomía)
echo ""
echo "5. Login trabajador (73000005/demo123)"
csrf2=$(curl -s -c "$COOKIES_TRAB" "$DEMO_URL/login/" | grep -oP 'csrfmiddlewaretoken["\s]*value=["\s]*\K[^"]+' | head -1)
trab_login=$(curl -s -b "$COOKIES_TRAB" -c "$COOKIES_TRAB" -H "Referer: $DEMO_URL/login/" \
    -d "csrfmiddlewaretoken=$csrf2&username=73000005&password=demo123&next=/" \
    "$DEMO_URL/login/" -o /dev/null -w "%{http_code}")
check "Login trabajador" "$trab_login" "302"

# 6. Portal trabajador
echo ""
echo "6. Portal trabajador (páginas clave)"
for p in /mi-portal/ /mi-portal/mi-nomina/ /mi-portal/asistencia/ /documentos/boletas/mis/ /vacaciones/mis/; do
    code=$(curl -s -b "$COOKIES_TRAB" -o /dev/null -w "%{http_code}" -m 15 "$DEMO_URL$p")
    check "GET $p" "$code" "200"
done

# 7. Boleta PDF descarga + control de permisos (DS 009-2011-TR + multi-tenant)
echo ""
echo "7. Boleta PDF descarga"
# Encontrar el primer registro propio del trabajador via /mi-portal/mi-nomina/
own_id=$(curl -s -b "$COOKIES_TRAB" "$DEMO_URL/mi-portal/mi-nomina/" | grep -oP 'registros/\K\d+(?=/boleta\.pdf)' | head -1)
if [ -n "$own_id" ]; then
    boleta_size=$(curl -s -b "$COOKIES_TRAB" "$DEMO_URL/nominas/registros/$own_id/boleta.pdf" -o /tmp/.hc_boleta.pdf -w "%{size_download}" -m 20)
    if [ "$boleta_size" -gt "5000" ]; then
        echo -e "  ${GREEN}✓${NC} Boleta PDF propia (id=$own_id, $boleta_size bytes)"
        ok=$((ok+1))
    else
        echo -e "  ${RED}✗${NC} Boleta PDF muy chica o vacía (id=$own_id, $boleta_size bytes)"
        fail=$((fail+1))
    fi
    # Probar que la boleta de OTRO trabajador da 403 (multi-tenant security)
    other_id=$((own_id == 1 ? 2 : 1))
    other_code=$(curl -s -b "$COOKIES_TRAB" -o /dev/null -w "%{http_code}" "$DEMO_URL/nominas/registros/$other_id/boleta.pdf")
    check "Boleta ajena → 403 (security)" "$other_code" "403"
else
    echo -e "  ${YELLOW}⚠${NC} No se encontró registro propio del trabajador para testear"
    warn=$((warn+1))
fi
rm -f /tmp/.hc_boleta.pdf

# 8. Security headers
echo ""
echo "8. Security headers"
headers=$(curl -sI "$DEMO_URL/login/" 2>/dev/null)
warn_check "X-Frame-Options" "$(echo "$headers" | grep -i 'X-Frame-Options:' | awk '{print $2}' | tr -d '\r')"
warn_check "Strict-Transport-Security" "$(echo "$headers" | grep -i 'Strict-Transport-Security' | head -1 | awk -F': ' '{print $2}' | tr -d '\r' | cut -c1-60)"
warn_check "X-Content-Type-Options" "$(echo "$headers" | grep -i 'X-Content-Type-Options:' | awk '{print $2}' | tr -d '\r')"
warn_check "Content-Security-Policy" "$(echo "$headers" | grep -i 'Content-Security-Policy:' | head -1 | awk -F': ' '{print $2}' | tr -d '\r' | cut -c1-40)"

# 9. Rate limit verificar_boleta (no spamear, solo 1 call)
echo ""
echo "9. Endpoint público de verificación QR"
code=$(curl -s -o /dev/null -w "%{http_code}" "$DEMO_URL/nominas/verificar/0000000000000000000000000000000a/")
check "Verify token inválido → 404" "$code" "404"

# Resumen final
echo ""
echo "============================================================"
echo "  OK:    $ok"
echo "  FAIL:  $fail"
echo "  WARN:  $warn"
echo "============================================================"

if [ "$fail" -eq "0" ]; then
    echo -e "${GREEN}✓ DEMO HEALTHY${NC}"
    exit 0
else
    echo -e "${RED}✗ HAY FAILURES — revisar antes de la demo${NC}"
    exit 1
fi
