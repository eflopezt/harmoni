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
        if empresa_from_subdomain:
            request.empresa_actual = empresa_from_subdomain
        elif request.user.is_authenticated:
            # 2a. Modo consolidado explícito?
            if request.session.get('modo_consolidado') is True:
                request.modo_consolidado = True
                request.empresa_actual = None  # explícito: sin filtro de empresa
            else:
                # 2b. Session-based lookup
                empresa_id = request.session.get('empresa_actual_id')
                if empresa_id:
                    try:
                        from empresas.models import Empresa
                        request.empresa_actual = Empresa.objects.get(pk=empresa_id, activa=True)
                    except Exception:
                        pass

                # 3. Fallback to principal empresa
                if not request.empresa_actual:
                    try:
                        from empresas.models import Empresa
                        principal = Empresa.objects.filter(
                            activa=True, es_principal=True
                        ).first()
                        # Si la principal no tiene personal (instancia recién
                        # sembrada / demo), arrancar en modo CONSOLIDADO en vez
                        # de mostrar "Empleados" y demás vistas vacías.
                        if principal and principal.personal.exists():
                            request.empresa_actual = principal
                            request.session['empresa_actual_id']     = principal.pk
                            request.session['empresa_actual_nombre'] = principal.nombre_display
                        else:
                            request.modo_consolidado = True
                            request.empresa_actual = None
                    except Exception:
                        pass

        # Setear empresa en thread-local para el email backend
        if request.empresa_actual:
            from empresas.email_backend import set_current_empresa
            set_current_empresa(request.empresa_actual)

        response = self.get_response(request)

        # Limpiar thread-local después del request
        from empresas.email_backend import set_current_empresa
        set_current_empresa(None)

        return response
