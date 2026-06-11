#!/usr/bin/env python
"""
Setup IA demo — Configura Anthropic Claude como proveedor de IA
en el demo de Harmoni (demo.harmoni.pe).

Uso (DENTRO del container demo):
    python manage.py shell < scripts/setup_demo_ia.py

O directamente:
    DJANGO_SETTINGS_MODULE=config.settings python scripts/setup_demo_ia.py

Configura:
  - ia_provider = 'ANTHROPIC'
  - ia_modelo   = 'claude-sonnet-4-20250514' (modelo demo, balance precio/calidad)
  - ia_api_key  = <key>

NOTA: La key se lee de env var ANTHROPIC_API_KEY si no se pasa como argumento.
"""
import os
import sys

# Bootstrap Django si se ejecuta standalone
if 'DJANGO_SETTINGS_MODULE' not in os.environ:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

try:
    import django
    django.setup()
except Exception:
    pass

from asistencia.models import ConfiguracionSistema

# Obtener key de argumento o env var
API_KEY = (
    (sys.argv[1] if len(sys.argv) > 1 else '')
    or os.environ.get('ANTHROPIC_API_KEY', '')
)

if not API_KEY:
    print("[!] Falta API key. Pasala como argumento o ANTHROPIC_API_KEY env.")
    sys.exit(1)

# Sanity check formato
if not API_KEY.startswith('sk-ant-api'):
    print(f"[!] La key no parece de Anthropic (esperado prefijo sk-ant-api...). Procediendo de todos modos.")

cfg = ConfiguracionSistema.get()

# Guardar valores previos para reporte
prev = {
    'provider': cfg.ia_provider,
    'modelo':   cfg.ia_modelo,
    'key':      cfg.ia_api_key[:16] + '...' if cfg.ia_api_key else '(vacía)',
}

# Aplicar configuración Anthropic
cfg.ia_provider = 'ANTHROPIC'
cfg.ia_api_key  = API_KEY
cfg.ia_modelo   = 'claude-sonnet-4-20250514'   # demo balance
cfg.ia_endpoint = ''  # no aplica para Anthropic
cfg.ia_mapeo_activo = True  # habilita mapeo IA columnas

# OCR: usar Gemini si ya hay key, sino dejar en None (Anthropic no hace OCR nativo)
# (no tocamos ia_ocr_provider para no romper config previa de OCR si existía)

cfg.save()

print("=" * 60)
print("  IA CONFIGURADA — Anthropic Claude Sonnet 4 (demo)")
print("=" * 60)
print(f"  Provider: {prev['provider']} → {cfg.ia_provider}")
print(f"  Modelo:   {prev['modelo']} → {cfg.ia_modelo}")
print(f"  API Key:  {prev['key']} → {API_KEY[:16]}...{API_KEY[-6:]}")
print(f"  Endpoint: (vacío — Anthropic SDK usa URL oficial)")
print(f"  Mapeo IA: {cfg.ia_mapeo_activo}")
print("=" * 60)
print()
print("  Próximos pasos:")
print("  1. Restart container:  docker restart harmoni-demo-web")
print("  2. Verificar:          curl https://demo.harmoni.pe/nominas/agente/")
print("  3. RECORDATORIO:       eliminar key después de la demo")
print("=" * 60)
