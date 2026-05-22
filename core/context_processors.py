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
    """
    try:
        from core.middleware_plan_starter import is_starter_user
        es_starter = is_starter_user(getattr(request, 'user', None))
    except Exception:
        es_starter = False
    return {
        'es_plan_starter': es_starter,
        'plan_actual':     'Starter' if es_starter else 'Profesional+',
    }
