"""
Permisos granulares por módulo — INFRA.3.

Uso en vistas:
    from core.permissions import requiere_permiso

    @requiere_permiso('nominas', 'ver')
    def mi_vista(request):
        ...

Acciones válidas: 'ver', 'crear', 'editar', 'aprobar', 'exportar'
Superusuarios siempre tienen acceso.
Staff con is_staff=True también (fallback generoso).
"""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import PermisoModulo


_ACCION_CAMPO = {
    'ver':      'puede_ver',
    'crear':    'puede_crear',
    'editar':   'puede_editar',
    'aprobar':  'puede_aprobar',
    'exportar': 'puede_exportar',
}


def tiene_permiso(user, modulo: str, accion: str = 'ver') -> bool:
    """
    Retorna True si el usuario puede ejecutar `accion` en `modulo`.
    Superusuarios → siempre True.
    Staff sin permiso explícito → False (safe default).
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True

    campo = _ACCION_CAMPO.get(accion, 'puede_ver')
    try:
        pm = PermisoModulo.objects.get(usuario=user, modulo=modulo)
        return getattr(pm, campo, False)
    except PermisoModulo.DoesNotExist:
        return False


def requiere_permiso(modulo: str, accion: str = 'ver'):
    """
    Decorador para vistas basadas en función.
    Redirige a login si no está autenticado.
    Retorna 403 si no tiene permiso.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def _wrapped(request, *args, **kwargs):
            if not tiene_permiso(request.user, modulo, accion):
                return HttpResponseForbidden(
                    f'<h2>Acceso denegado</h2>'
                    f'<p>No tienes permiso para acceder al módulo <strong>{modulo}</strong>.</p>'
                    f'<a href="/">← Volver al inicio</a>'
                )
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


def get_permisos_usuario(user) -> dict:
    """
    Retorna un dict {modulo: {ver, crear, editar, aprobar, exportar}}
    para el usuario dado. Si es superusuario, todo True.
    """
    if user.is_superuser:
        from .models import MODULOS_SISTEMA
        return {
            mod: {a: True for a in ['ver', 'crear', 'editar', 'aprobar', 'exportar']}
            for mod, _ in MODULOS_SISTEMA
        }

    permisos = PermisoModulo.objects.filter(usuario=user)
    result = {}
    for pm in permisos:
        result[pm.modulo] = {
            'ver':      pm.puede_ver,
            'crear':    pm.puede_crear,
            'editar':   pm.puede_editar,
            'aprobar':  pm.puede_aprobar,
            'exportar': pm.puede_exportar,
        }
    return result


# ═════════════════════════════════════════════════════════════════════════
# admin_required — atajo para bloquear trabajadores en URLs admin
# ═════════════════════════════════════════════════════════════════════════

def es_admin(user) -> bool:
    """
    Determina si un usuario tiene rol administrativo:
    - is_superuser (root)
    - is_staff (RRHH típicamente)
    - perfil_acceso.es_responsable o puede_aprobar (jefes de área)

    Los trabajadores puros (con personal_data pero sin estos flags) → False.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    perfil = getattr(user, 'perfil_acceso', None)
    if perfil:
        if getattr(perfil, 'es_responsable', False):
            return True
        if getattr(perfil, 'puede_aprobar', False):
            return True
    return False


def admin_required(view_func):
    """
    Decorador rápido: solo admin/staff/jefe puede acceder.
    Si es trabajador puro → redirect a /mi-portal/
    Si no autenticado → redirect a login (vía @login_required).

    Uso:
        from core.permissions import admin_required

        @admin_required
        def mi_vista_admin(request):
            ...
    """
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not es_admin(request.user):
            # Trabajador → su portal (no 403 que es confuso)
            from django.contrib import messages as _m
            _m.warning(
                request,
                'Esa página es solo para administradores. '
                'Si necesitas ayuda contacta a RRHH.',
            )
            return redirect('/mi-portal/')
        return view_func(request, *args, **kwargs)
    return _wrapped
