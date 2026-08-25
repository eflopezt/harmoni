"""
Middleware de multi-empresa para Harmoni.

Inyecta request.empresa_actual con la empresa activa.
Prioridad de resolución:
  1. Subdomain (set by SubdomainMiddleware → request.empresa_subdomain)
  2. Sesión (empresa_actual_id)
  3. Empresa principal (es_principal=True)
"""


class EmpresaMiddleware:
    """
    Inyecta `request.empresa_actual` (instancia de Empresa o None).
    Disponible en todas las vistas sin importar nada extra.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.empresa_actual = None
        # Modo "Vista consolidada" — el usuario eligió ver TODAS las empresas.
        # Querysets de Personal/Asistencia/Reclutamiento/etc. NO filtran por
        # empresa. Las planillas siguen siendo INDEPENDIENTES por empresa.
        request.modo_consolidado = False

        # 1. Subdomain takes priority (already resolved by SubdomainMiddleware)
        empresa_from_subdomain = getattr(request, 'empresa_subdomain', None)
        if empresa_from_subdomain and request.user.is_authenticated:
            from empresas.acceso import empresa_es_accesible
            if empresa_es_accesible(request.user, empresa_from_subdomain):
                request.empresa_actual = empresa_from_subdomain
        elif request.user.is_authenticated:
            # 2a. Modo consolidado explícito?
            if (request.session.get('modo_consolidado') is True
                    and request.user.is_superuser):
                request.modo_consolidado = True
                request.empresa_actual = None  # explícito: sin filtro de empresa
            else:
                request.session.pop('modo_consolidado', None)
                # 2b. Session-based lookup
                empresa_id = request.session.get('empresa_actual_id')
                if empresa_id:
                    try:
                        from empresas.acceso import empresas_accesibles
                        request.empresa_actual = empresas_accesibles(
                            request.user
                        ).get(pk=empresa_id)
                    except Exception:
                        request.session.pop('empresa_actual_id', None)
                        request.session.pop('empresa_actual_nombre', None)

                # 3. Fallback to principal empresa
                if not request.empresa_actual:
                    try:
                        from empresas.acceso import empresas_accesibles
                        permitidas = empresas_accesibles(request.user)
                        principal = permitidas.filter(es_principal=True).first()
                        elegida = principal or permitidas.order_by('razon_social').first()
                        if elegida:
                            request.empresa_actual = elegida
                            request.session['empresa_actual_id'] = elegida.pk
                            request.session['empresa_actual_nombre'] = elegida.nombre_display
                        elif request.user.is_superuser:
                            request.modo_consolidado = True
                            request.empresa_actual = None
                    except Exception:
                        pass

        # Setear empresa en thread-local para el email backend y el alcance
        # defensivo de modelos que contienen PII multiempresa.
        if request.empresa_actual:
            from empresas.email_backend import set_current_empresa
            set_current_empresa(request.empresa_actual)
        from empresas.request_scope import activate_request_scope, reset_request_scope
        scope_token = activate_request_scope(request)

        try:
            return self.get_response(request)
        finally:
            reset_request_scope(scope_token)
            from empresas.email_backend import set_current_empresa
            set_current_empresa(None)
