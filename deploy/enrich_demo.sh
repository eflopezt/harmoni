#!/usr/bin/env bash
# enrich_demo.sh — Enriquece el demo (demo.harmoni.pe) para que luzca completo
# ante clientes potenciales. Idempotente. Ejecutar en el VPS.
#
# Uso (en el VPS, contenedor del demo):
#   docker exec -it harmoni-demo-web bash deploy/enrich_demo.sh
# o paso a paso con docker exec ... python manage.py <comando>
set -euo pipefail

MANAGE="python manage.py"

echo "==> 1. Legajo digital (documentos por trabajador)"
$MANAGE seed_legajo_demo || true

echo "==> 2. Enriquecimiento general (liquidaciones, contratos, vacaciones, préstamos, bandas)"
$MANAGE seed_demo_enriquecer || true

echo "==> 3. Certificaciones BPM/HACCP (panel gastro)"
$MANAGE shell -c "exec(open('scripts/seed_gastro_certs.py', encoding='utf-8').read())" || true

echo "==> 4. Períodos históricos (comparativo mensual / interanual / flujo de caja)"
$MANAGE seed_periodos_historicos || true

echo ""
echo "Listo. Verificar en:"
echo "  /documentos/            (legajo poblado)"
echo "  /capacitaciones/gastro/ (certs BPM/HACCP)"
echo "  /nominas/comparativo/   (5 meses de tendencia)"
echo "  /nominas/liquidaciones/ (liquidaciones)"
echo ""
echo "NOTA — IR 5ta histórico: si alguna boleta vieja muestra IR sub-retenido"
echo "(proyección ×12 en vez de ×14), regenerar SOLO ese período con cuidado:"
echo "  el engine actual ya calcula ×14 correctamente. Evitar generar_periodo si"
echo "  el período es multi-empresa y solo se quiere recalcular el subconjunto."
