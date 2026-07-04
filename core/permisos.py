"""
RBAC central de Harmoni (WS1).

Un solo lugar para resolver permisos por módulo, en reemplazo de las ~30
copias de `solo_admin = user_passes_test(lambda u: u.is_superuser...)`
regadas por cada app.

Modelo de permisos:
- **superuser**: puede todo.
- **staff con Personal + PerfilAcceso**: puede operar los módulos cuyo
  `mod_<x>` esté activo en su perfil (ej. un RECLUTADOR con
  `mod_reclutamiento=True` opera todo el pipeline).
- **vistas de DINERO** (motor de nóminas, aprobar préstamos, generar/cerrar
  períodos, liquidaciones): quedan superuser-only en esta fase — se
  protegen con `solo_superuser`, NO con `requiere_modulo`.
- **aprobaciones** dentro de un módulo: gate adicional `puede_aprobar`.

El enlace es User → Personal (`user.personal_data`) → PerfilAcceso
(`personal.perfil_acceso`).
"""
from django.contrib.auth.decorators import user_passes_test


def perfil_de(user):
    """Devuelve el PerfilAcceso del usuario (vía Personal), o None."""
    if not getattr(user, 'is_authenticated', False):
        return None
    personal = getattr(user, 'personal_data', None)
    return getattr(personal, 'perfil_acceso', None) if personal else None


def es_admin(user) -> bool:
    """Compat con el viejo `solo_admin` de la mayoría de apps: superuser."""
    return bool(getattr(user, 'is_superuser', False))


def es_admin_o_staff(user) -> bool:
    """Compat con el `solo_admin` de asistencia/calendario (superuser o staff)."""
    return bool(getattr(user, 'is_superuser', False)
                or getattr(user, 'is_staff', False))


def tiene_modulo(user, modulo: str) -> bool:
    """True si el usuario puede operar `modulo`.

    superuser siempre; staff con Personal + PerfilAcceso.mod_<modulo> activo.
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    # Requiere ser staff Y tener el módulo en su perfil.
    if not getattr(user, 'is_staff', False):
        return False
    perfil = perfil_de(user)
    if perfil is None:
        return False
    return bool(getattr(perfil, f'mod_{modulo}', False))


def puede_aprobar(user) -> bool:
    """True si el usuario puede aprobar solicitudes (superuser o
    PerfilAcceso.puede_aprobar)."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    perfil = perfil_de(user)
    return bool(perfil and getattr(perfil, 'puede_aprobar', False))


# ── Decoradores para vistas ─────────────────────────────────────────────────

def requiere_modulo(modulo: str):
    """Decorador: acceso al módulo `modulo` (superuser o staff con el
    mod_<modulo> en su PerfilAcceso).

    Usar SOLO para reemplazar un `solo_admin` que era `is_superuser`-only:
    así la migración solo AÑADE acceso (a los profile-holders), sin regresión.

    Uso: `@requiere_modulo('reclutamiento')`
    """
    return user_passes_test(lambda u: tiene_modulo(u, modulo), login_url='login')


def tiene_modulo_o_staff(user, modulo: str) -> bool:
    """Como `tiene_modulo`, pero un staff SIN perfil asignado conserva acceso
    (compat legacy). Para migrar vistas que antes eran `is_superuser or
    is_staff` sin regresar a los staff que aún no tienen PerfilAcceso.

    - superuser → sí
    - staff con perfil que tiene mod_<x> → sí
    - staff con perfil que NO tiene mod_<x> → no (RBAC ya activo para él)
    - staff sin perfil → sí (legacy, hasta que se le asigne uno)
    - no-staff → no
    """
    if not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    if not getattr(user, 'is_staff', False):
        return False
    perfil = perfil_de(user)
    if perfil is None:
        return True   # legacy: staff sin perfil mantiene acceso
    return bool(getattr(perfil, f'mod_{modulo}', False))


def requiere_modulo_o_staff(modulo: str):
    """Decorador para vistas que antes eran `is_superuser or is_staff`.
    Migra a RBAC sin regresar a staff sin perfil. Ver `tiene_modulo_o_staff`.
    """
    return user_passes_test(lambda u: tiene_modulo_o_staff(u, modulo),
                            login_url='login')


#: Vistas críticas / de dinero — superuser exclusivo (motor nóminas, cierre,
#: aprobar préstamos, liquidaciones). Alias explícito para dejar claro en el
#: código que la restricción es deliberada, no un módulo pendiente de abrir.
solo_superuser = user_passes_test(es_admin, login_url='login')
