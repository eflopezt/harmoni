"""
Context processors de Harmoni.
"""


def plan_starter_context(request):
    """
    Inyecta flag `es_plan_starter` para mostrar/ocultar features
    enterprise en templates.

    Uso en templates:
        {% if not es_plan_starter %}
            <a href="...">Feature avanzada</a>
        {% endif %}

    Flags inyectados:
        es_plan_starter:  bool — True si user del plan Starter
        plan_actual:      str  — 'Starter' o 'Profesional+'
        oculta_rco:       bool — True si debe ocultar la división RCO/STAFF
                                 (Starter solo maneja STAFF)
        oculta_pdf:       bool — True si debe ocultar botones de PDF de reportes
        oculta_capacitaciones: bool — True si oculta módulo capacitaciones
        oculta_organigrama:    bool — True si oculta módulo organigrama
        oculta_calendario:     bool — True si oculta calendario laboral
        oculta_contratos:      bool — True si oculta gestión formal de contratos
        oculta_disciplinaria:  bool — True si oculta medidas disciplinarias
    """
    try:
        from core.middleware_plan_starter import is_starter_user
        es_starter = is_starter_user(getattr(request, 'user', None))
    except Exception:
        es_starter = False
    return {
        'es_plan_starter':       es_starter,
        'plan_actual':           'Starter' if es_starter else 'Profesional+',
        # Flags de ocultación masiva — todos derivan del mismo bit
        'oculta_rco':            es_starter,
        'oculta_pdf':            es_starter,
        'oculta_capacitaciones': es_starter,
        'oculta_organigrama':    es_starter,
        'oculta_calendario':     es_starter,
        'oculta_contratos':      es_starter,
        'oculta_disciplinaria':  es_starter,
        'oculta_banco_horas':    es_starter,
        'oculta_workflows':      es_starter,
        'oculta_salarios':       es_starter,
        'oculta_prestamos':      es_starter,
        'oculta_reclutamiento':  es_starter,
    }
