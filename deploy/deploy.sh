#!/bin/bash
# =============================================================================
# Harmoni ERP — Deploy git-based (robusto)
# Uso: bash deploy/deploy.sh
#
# Despliega lo que YA está en origin/main. No sube working tree por scp:
#   1) valida que main local esté limpio y pusheado,
#   2) en el VPS hace git fetch + reset --hard origin/main,
#   3) build + migrate + collectstatic + up bajo nohup (sobrevive cortes ssh),
#   4) poll del log remoto hasta DEPLOY_OK o error,
#   5) verifica containers healthy + HTTP 200.
#
# Requisito: haber hecho `git push origin main` antes (el script aborta si no).
# Fallback (sin GitHub / código sin pushear): deploy/deploy_tarball.sh
# =============================================================================
set -euo pipefail

VPS="root@212.56.34.166"
APP_DIR="/opt/harmoni/app"
BRANCH="main"
COMPOSE="deploy/docker-compose.prod.yml"
LOG="/tmp/harmoni-redeploy.log"

# ssh: usa la clave por defecto del agente/config; añade -i solo si existe.
SSH_OPTS="-o ConnectTimeout=15"
if [ -f "$HOME/.ssh/id_ed25519" ]; then
  SSH_OPTS="$SSH_OPTS -i $HOME/.ssh/id_ed25519"
fi
ssh_vps() { ssh $SSH_OPTS "$VPS" "$@"; }

echo "=== Harmoni Deploy (git-based) ==="

# ── 1. Validaciones locales ─────────────────────────────────────────────────
echo "[1/5] Validando estado local..."
current_branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$current_branch" != "$BRANCH" ]; then
  echo "  ✗ Estás en '$current_branch', no en '$BRANCH'. Cambia de rama o mergea antes." >&2
  exit 1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "  ✗ Hay cambios sin commitear en tracked files. Commitea o descarta antes de desplegar." >&2
  git status --short --untracked-files=no >&2
  exit 1
fi
git fetch origin "$BRANCH" --quiet
if [ -n "$(git log origin/$BRANCH..$BRANCH --oneline)" ]; then
  echo "  ✗ Tienes commits locales sin pushear. Corre 'git push origin $BRANCH' primero." >&2
  git log origin/$BRANCH..$BRANCH --oneline >&2
  exit 1
fi
echo "  ✓ main limpio y sincronizado con origin ($(git rev-parse --short $BRANCH))"

# ── 2. Reset del VPS a origin/main ──────────────────────────────────────────
echo "[2/5] Actualizando código en el VPS..."
ssh_vps "cd $APP_DIR && git fetch origin --quiet && git reset --hard origin/$BRANCH && chown -R deploy:deploy $APP_DIR && git log --oneline -1"

# ── 3. Build + migrate + collectstatic + up (nohup, sobrevive cortes) ───────
echo "[3/5] Lanzando build en el VPS (nohup)..."
ssh_vps "rm -f $LOG && nohup bash -c '
  set -e
  cd $APP_DIR
  export COMPOSE_PROJECT_NAME=harmoni
  docker compose -f $COMPOSE build web
  docker compose -f $COMPOSE run --rm web python manage.py migrate --noinput
  docker compose -f $COMPOSE run --rm -v /opt/harmoni/staticfiles:/app/staticfiles web python manage.py collectstatic --noinput
  chmod -R 777 /opt/harmoni/staticfiles || true
  docker compose -f $COMPOSE up -d --force-recreate
  echo DEPLOY_OK
' > $LOG 2>&1 & echo '  ✓ build lanzado'"

# ── 4. Poll del log remoto ──────────────────────────────────────────────────
echo "[4/5] Esperando fin del build..."
for i in $(seq 1 60); do
  hits=$(ssh_vps "grep -cE 'DEPLOY_OK|Traceback|ERROR:|failed|denied|no space' $LOG 2>/dev/null" || echo 0)
  if [ "$hits" != "0" ] && [ -n "$hits" ]; then break; fi
  sleep 20
done
echo "  --- últimas líneas del log remoto ---"
ssh_vps "tail -6 $LOG"

if ! ssh_vps "grep -q DEPLOY_OK $LOG"; then
  echo "  ✗ El build NO terminó con DEPLOY_OK. Revisa $LOG en el VPS." >&2
  exit 1
fi

# ── 5. Verificar ────────────────────────────────────────────────────────────
echo "[5/5] Verificando producción..."
ssh_vps "docker ps --format '{{.Names}} {{.Status}}' | grep -E '^harmoni-(web|celery|beat)'"
code=$(ssh_vps "curl -s -o /dev/null -w '%{http_code}' https://harmoni.pe/")
echo "  harmoni.pe -> HTTP $code"
if [ "$code" != "200" ]; then
  echo "  ✗ El sitio no responde 200. Revisa logs del contenedor web." >&2
  exit 1
fi

echo ""
echo "=== Deploy completado: https://harmoni.pe ==="
