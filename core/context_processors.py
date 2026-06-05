"""
Context processors de Harmoni.
"""


def plan_starter_context(request):
    """
    Inyecta info del plan y flags de ocultación de módulos a TODOS los templates,
    derivados del nivel real del plan (Asistencia/Planilla/Talento/Suite) — ver
    core/planes.py. Mantiene los nombres `es_plan_starter` y `oculta_*` por
    back-compat con los templates existentes.

    Nuevos:
        plan_codigo / plan_nombre / plan_nivel
        modulos      dict {modulo_key: bool incluido}  → {% if modulos.reclutamiento %}
    """
    user = getattr(request, 'user', None)
    try:
        from core.planes import (PLANES, PLAN_DEFAULT, plan_nivel,
                                  modulos_por_nivel)
        from core.middleware_plan_starter import resolve_plan

        if user is not None and getattr(user, 'is_superuser', False):
            plan_code = PLAN_DEFAULT          # staff Harmoni ve todo
        elif user is not None and getattr(user, 'is_authenticated', False):
            plan_code = resolve_plan(user)
        else:
            plan_code = PLAN_DEFAULT

        nivel = plan_nivel(plan_code)
        modulos = modulos_por_nivel(plan_code)
        meta = PLANES.get(plan_code, PLANES[PLAN_DEFAULT])
    except Exception:
        # Fallback ultradefensivo: tratar como plan tope (no ocultar nada).
        plan_code, nivel, meta = 'SUITE', 4, {'nombre': 'Suite'}
        modulos = {}

    def oculto(mod_key):
        # Si el módulo no está en el mapa (no gateado) → nunca oculto.
        return not modulos.get(mod_key, True)

    es_starter = nivel <= 1

    # ── Estado de suscripción/prueba (para el banner) ──
    sub_estado = 'SIN_RESTRICCION'   # ACTIVA / TRIAL / VENCIDA / SIN_RESTRICCION
    sub_dias = None
    try:
        if user is not None and getattr(user, 'is_authenticated', False) \
                and not getattr(user, 'is_superuser', False):
            from core.middleware_plan_starter import empresa_de
            emp = empresa_de(user)
            if emp is not None:
                sub_estado = emp.estado_suscripcion
                sub_dias = emp.dias_acceso_restantes
    except Exception:
        pass

    return {
        # Suscripción / prueba
        'sub_estado':           sub_estado,
        'sub_dias_restantes':   sub_dias,
        'mostrar_banner_sub':   sub_estado in ('TRIAL', 'ACTIVA', 'VENCIDA'),
        # Back-compat (trial)
        'trial_dias_restantes': sub_dias,
        'trial_vencido':        sub_estado == 'VENCIDA',
        'en_prueba':            sub_estado == 'TRIAL',
        # Identidad del plan
        'plan_codigo':    plan_code,
        'plan_nombre':    meta.get('nombre', plan_code),
        'plan_nivel':     nivel,
        'modulos':        modulos,
        # Back-compat
        'es_plan_starter': es_starter,
        'plan_actual':     meta.get('nombre', 'Suite'),
        # Flags de ocultación (derivados del módulo real)
        'oculta_capacitaciones': oculto('capacitaciones'),
        'oculta_organigrama':    oculto('organigrama'),
        'oculta_calendario':     oculto('calendario'),
        'oculta_contratos':      oculto('contratos'),
        'oculta_disciplinaria':  oculto('disciplinaria'),
        'oculta_workflows':      oculto('workflows'),
        'oculta_salarios':       oculto('salarios'),
        'oculta_prestamos':      oculto('prestamos'),
        'oculta_reclutamiento':  oculto('reclutamiento'),
        'oculta_portal':         oculto('portal'),
        # Portal-dependientes (solicitudes/notificaciones al trabajador)
        'oculta_horas_extras':   oculto('portal'),
        'oculta_notificar':      oculto('portal'),
        'oculta_solicitudes':    oculto('portal'),
        # Banco de horas ahora es parte de Asistencia (nivel 1) → nunca oculto
        'oculta_banco_horas':    False,
        # RCO/STAFF: división de asistencia, disponible en todos los planes
        'oculta_rco':            False,
        # PDFs de reportes avanzados → desde Talento (analytics)
        'oculta_pdf':            oculto('analytics'),
    }
