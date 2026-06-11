#!/bin/bash
# ════════════════════════════════════════════════════════════════
#  Cleanup IA demo — Elimina la API key de Anthropic POST-DEMO
#  Uso (en el VPS):
#      bash /opt/harmoni-demo/cleanup_demo_ia.sh
#  O directamente vía SSH:
#      ssh root@212.56.34.166 'bash -s' < scripts/cleanup_demo_ia.sh
# ════════════════════════════════════════════════════════════════

set -e
ENV='/opt/harmoni-demo/.env.demo'

echo "════════════════════════════════════════════════════════════"
echo "  CLEANUP IA DEMO — eliminando API key Anthropic"
echo "════════════════════════════════════════════════════════════"

# 1. Borrar la línea ANTHROPIC_API_KEY del .env.demo
if grep -q '^ANTHROPIC_API_KEY=' "$ENV"; then
    sed -i '/^# Anthropic Claude API (DEMO ONLY/d' "$ENV"
    sed -i '/^ANTHROPIC_API_KEY=/d' "$ENV"
    echo "  [OK] ANTHROPIC_API_KEY eliminada de $ENV"
else
    echo "  [skip] ANTHROPIC_API_KEY no estaba en $ENV"
fi

# 2. Limpiar ConfiguracionSistema en DB (volver a NINGUNO / Gemini default)
docker exec harmoni-demo-web python manage.py shell -c "
from asistencia.models import ConfiguracionSistema
cfg = ConfiguracionSistema.get()
prev = (cfg.ia_provider, cfg.ia_modelo, len(cfg.ia_api_key))
cfg.ia_provider = 'NINGUNO'
cfg.ia_api_key  = ''
cfg.ia_modelo   = 'gemini-2.5-flash'
cfg.ia_mapeo_activo = False
cfg.save()
print(f'  [OK] DB: provider {prev[0]} -> NINGUNO')
print(f'  [OK] DB: modelo {prev[1]} -> gemini-2.5-flash (default)')
print(f'  [OK] DB: api_key borrada ({prev[2]} chars eliminados)')
"

# 3. Recrear containers para que NO tengan más la env var
echo ""
echo "  Recreando containers sin la key..."
for c in harmoni-demo-web harmoni-demo-celery harmoni-demo-beat; do
    docker stop "$c" > /dev/null 2>&1 || true
    docker rm   "$c" > /dev/null 2>&1 || true
done
sleep 2

docker run -d --name harmoni-demo-web --network host --restart unless-stopped \
  --env-file "$ENV" \
  -v /opt/harmoni-demo/app:/app:ro \
  -v /opt/harmoni-demo/staticfiles:/app/staticfiles \
  -v /opt/harmoni-demo/media:/app/media \
  -v /opt/harmoni-demo/logs:/app/logs \
  harmoni-web-img:latest \
  gunicorn config.wsgi:application --bind 0.0.0.0:8004 --workers 2 --timeout 120 > /dev/null

docker run -d --name harmoni-demo-celery --network host --restart unless-stopped \
  --env-file "$ENV" \
  -v /opt/harmoni-demo/app:/app:ro \
  -v /opt/harmoni-demo/media:/app/media \
  -v /opt/harmoni-demo/logs:/app/logs \
  harmoni-web-img:latest \
  celery -A config worker --loglevel=info --concurrency=1 > /dev/null

docker run -d --name harmoni-demo-beat --network host --restart unless-stopped \
  --env-file "$ENV" \
  -v /opt/harmoni-demo/app:/app:ro \
  -v /opt/harmoni-demo/logs:/app/logs \
  harmoni-web-img:latest \
  celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler > /dev/null

sleep 4
echo ""
echo "  Verificación final:"
docker ps --filter name=harmoni-demo --format '    {{.Names}}: {{.Status}}'
echo ""
echo "════════════════════════════════════════════════════════════"
echo "  CLEANUP COMPLETO — API key eliminada del demo"
echo "  Recordatorio: REVOCA TAMBIÉN la key en console.anthropic.com"
echo "════════════════════════════════════════════════════════════"
