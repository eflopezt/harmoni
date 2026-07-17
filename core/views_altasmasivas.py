"""
Generador de Carga Masiva T-Registro — SUNAT.

URL: /altasmasivas/  (pública, sin login, sin DB)

Herramienta tipo formulario para preparar los archivos de importación del
T-Registro (RP_<RUC>.ide/.tra/.per/.est/.edu/.cta) que luego se validan
con el PVS T-Registro de SUNAT y se suben por SOL (Mi RUC y Otros
Registros → T-Registro → Carga masiva).

Soporta 3 operaciones: ALTA de trabajador, BAJA y MODIFICACIÓN de datos.
Todo el procesamiento es client-side (JS): la página no persiste nada en
el servidor. Los catálogos grandes (Tabla 30 ocupaciones, Tabla 28 ubigeo,
Tablas 4/26) se cargan de static/altasmasivas/catalogos.json.

Fuentes normativas:
- R.M. 121-2011-TR y modificatorias (Anexos 2 y 3).
- Manual de Usuario PVS T-Registro (act. 26.11.2021) — estructuras E04,
  E05, E11, E17, E29 y E30, nomenclatura RP_RUC.* y formato palotes.
- Tablas paramétricas SUNAT actualizadas al 08.07.2026.
"""
from django.views.decorators.http import require_GET


@require_GET
def altas_masivas(request):
    """Vista pública — herramienta interactiva de carga masiva T-Registro."""
    from django.shortcuts import render
    return render(request, 'altasmasivas/herramienta.html')
