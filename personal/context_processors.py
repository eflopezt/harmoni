"""
Context processors globales para Harmoni.

PERFORMANCE:
  - Antes: 7 queries SQL en CADA request de superuser
  - Después: 0 queries cuando hay cache (TTL: config=5min, badge=60s, rol=5min)

Invalidación:
  - invalidar_config()    → llamado en ConfiguracionSistema.save()
  - invalidar_badge(pk)   → llamado en signals de aprobaciones
  - invalidar_rol(pk)     → llamado al reasignar responsable de área
  - invalidar_perfil(pk)  → llamado al cambiar perfil de un usuario

RBAC (PerfilAcceso):
  - Los superusuarios ignoran el perfil (acceso total siempre).
  - El perfil RESTRINGE (intersección) los módulos activados en ConfiguracionSistema.
  - Un perfil no puede habilitar lo que la empresa tiene desactivado.
  - Cached 5 min por usuario.
"""
from django.core.cache import cache

_TTL_CONFIG  = 300   # 5 min
_TTL_ROLE    = 300   # 5 min
_TTL_BADGE   = 60    # 60 s
_TTL_PERFIL  = 300   # 5 min


def harmoni_context(request):
    base = {'harmoni_version': '1.0.0'}

    if not hasattr(request, 'user') or not request.user.is_authenticated:
        base.update({
            'es_responsable': False,
            'areas_responsable': None,
            'cambios_pendientes': 0,
            'empresa_actual': None,
            'empresas_disponibles': [],
        })
        return base

    user = request.user
    base.update(_get_config_context(user))
    # Aplicar restricciones de PerfilAcceso ANTES de exponer al template.
    # Superusuarios no se tocan — _get_perfil_overrides() devuelve {} para ellos.
    perfil_overrides = _get_perfil_overrides(user)
    for key, allowed in perfil_overrides.items():
        if not allowed:
            base[key] = False  # perfil restringe; nunca habilita lo ya desactivado
    # Exponer capacidades globales del perfil (puede_aprobar / puede_exportar)
    perfil_obj = _get_perfil_obj(user)
    if user.is_superuser:
        base['puede_aprobar']  = True
        base['puede_exportar'] = True
    elif perfil_obj is not None:
        base['puede_aprobar']  = perfil_obj.puede_aprobar
        base['puede_exportar'] = perfil_obj.puede_exportar
    else:
        # Sin perfil → acceso según config, por defecto puede exportar, no aprobar
        base['puede_aprobar']  = False
        base['puede_exportar'] = True
    base.update(_get_role_context(user))
    area_ids = base.pop('_area_ids', [])
    base['cambios_pendientes'] = _get_badge_count(user, area_ids)
    # Exponer perfil del usuario al template (para mostrar nombre de rol, etc.)
    base['perfil_acceso_usuario'] = perfil_obj

    # Multi-empresa
    base['empresa_actual'] = getattr(request, 'empresa_actual', None)
    base['empresas_disponibles'] = _get_empresas_disponibles()

    # Workflows — badge de pendientes
    base['pendientes_workflow'] = _get_workflow_pendientes(user)

    # Badges granulares para el sidebar
    extra_badges = _get_extra_badges(user, area_ids)
    base.update(extra_badges)

    return base


def _get_empresas_disponibles() -> list:
    """Retorna lista de empresas activas para el selector del sidebar. Cached 5 min."""
    cache_key = 'harmoni_ctx_empresas_v1'
    data = cache.get(cache_key)
    if data is None:
        try:
            from empresas.models import Empresa
            data = list(
                Empresa.objects.filter(activa=True)
                .values('pk', 'razon_social', 'nombre_comercial', 'ruc')
                .order_by('razon_social')
            )
        except Exception:
            data = []
        cache.set(cache_key, data, _TTL_CONFIG)
    return data


def _get_config_context(user) -> dict:
    cache_key = 'harmoni_ctx_config_v5'  # bump version when adding new fields
    cfg_data = cache.get(cache_key)
    if cfg_data is None:
        try:
            from asistencia.models import ConfiguracionSistema
            config = ConfiguracionSistema.get()
            cfg_data = {
                '_config_obj': config,
                'modo_sistema': config.modo_sistema,
                'programa_nomina': config.programa_nomina,
                'mod_prestamos':      config.mod_prestamos,
                'mod_viaticos':       config.mod_viaticos,
                'mod_documentos':     config.mod_documentos,
                'mod_evaluaciones':   config.mod_evaluaciones,
                'mod_capacitaciones': config.mod_capacitaciones,
                'mod_reclutamiento':  config.mod_reclutamiento,
                'mod_encuestas':      config.mod_encuestas,
                'mod_salarios':       config.mod_salarios,
                # Roster: solo activo si la empresa lo necesita (foráneos/turnos)
                'mod_roster':         config.mod_roster,
                'roster_aplica_a':    config.roster_aplica_a,
            }
            cache.set(cache_key, cfg_data, _TTL_CONFIG)
        except Exception:
            cfg_data = {
                '_config_obj': None, 'modo_sistema': 'ASISTENCIA',
                'programa_nomina': 'NINGUNO',
                'mod_prestamos': True, 'mod_viaticos': False,
                'mod_documentos': True, 'mod_evaluaciones': False,
                'mod_capacitaciones': False, 'mod_reclutamiento': False,
                'mod_encuestas': False, 'mod_salarios': False,
                'mod_roster': False, 'roster_aplica_a': 'FORANEOS',
            }

    result = dict(cfg_data)
    result['harmoni_config'] = result.pop('_config_obj', None)
    if user.is_superuser:
        for mod in ('mod_prestamos', 'mod_viaticos', 'mod_documentos', 'mod_evaluaciones',
                    'mod_capacitaciones', 'mod_reclutamiento', 'mod_encuestas', 'mod_salarios',
                    'mod_roster'):
            result[mod] = True
    return result


def _get_role_context(user) -> dict:
    cache_key = f'harmoni_ctx_role_{user.pk}_v2'
    role_data = cache.get(cache_key)
    if role_data is None:
        from personal.permissions import es_responsable_area, get_areas_responsable
        es_resp = es_responsable_area(user)
        area_ids = list(get_areas_responsable(user).values_list('pk', flat=True)) if es_resp else []
        role_data = {'es_responsable': es_resp, 'area_ids': area_ids}
        cache.set(cache_key, role_data, _TTL_ROLE)

    area_ids = role_data.get('area_ids', [])
    areas_qs = None
    if area_ids:
        from personal.models import Area
        areas_qs = Area.objects.filter(pk__in=area_ids)

    return {
        'es_responsable': role_data['es_responsable'],
        'areas_responsable': areas_qs,
        '_area_ids': area_ids,
    }


def _get_badge_count(user, area_ids: list) -> int:
    cache_key = f'harmoni_badge_{user.pk}_v3'
    count = cache.get(cache_key)
    if count is None:
        count = _calcular_badge(user, area_ids)
        cache.set(cache_key, count, _TTL_BADGE)
    return count


def _calcular_badge(user, area_ids: list) -> int:
    if not user.is_superuser and not area_ids:
        return 0

    from django.db.models import Q
    from personal.models import Roster
    from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje

    total = 0
    if user.is_superuser:
        total += Roster.objects.filter(estado='pendiente').count()
        total += RegistroPapeleta.objects.filter(estado='PENDIENTE').count()
        total += SolicitudHE.objects.filter(estado='PENDIENTE').count()
        total += JustificacionNoMarcaje.objects.filter(estado='PENDIENTE').count()
        try:
            from vacaciones.models import SolicitudVacacion, SolicitudPermiso
            total += SolicitudVacacion.objects.filter(estado='PENDIENTE').count()
            total += SolicitudPermiso.objects.filter(estado='PENDIENTE').count()
        except Exception:
            pass
    else:
        af = Q(personal__subarea__area__in=area_ids)
        total += Roster.objects.filter(Q(estado='pendiente') & af).count()
        total += RegistroPapeleta.objects.filter(Q(estado='PENDIENTE') & af).count()
        total += SolicitudHE.objects.filter(Q(estado='PENDIENTE') & af).count()
        total += JustificacionNoMarcaje.objects.filter(Q(estado='PENDIENTE') & af).count()
        try:
            from vacaciones.models import SolicitudVacacion, SolicitudPermiso
            total += SolicitudVacacion.objects.filter(Q(estado='PENDIENTE') & af).count()
            total += SolicitudPermiso.objects.filter(Q(estado='PENDIENTE') & af).count()
        except Exception:
            pass
    return total


# ── Perfil de Acceso (RBAC) ────────────────────────────────────────────────

def _get_perfil_obj(user):
    """Retorna el PerfilAcceso asignado al usuario o None. Sin caché (solo para display)."""
    if user.is_superuser:
        return None
    try:
        from personal.models import Personal
        personal = Personal.objects.select_related('perfil_acceso').get(usuario=user)
        return personal.perfil_acceso
    except Exception:
        return None


def _get_perfil_overrides(user) -> dict:
    """
    Retorna dict {mod_*: bool} con las restricciones del PerfilAcceso del usuario.
    Superusuarios → {} (sin restricciones).
    Cached 5 min por usuario.
    """
    if user.is_superuser:
        return {}

    cache_key = f'harmoni_perfil_{user.pk}_v1'
    data = cache.get(cache_key)
    if data is None:
        data = _calcular_perfil_overrides(user)
        cache.set(cache_key, data, _TTL_PERFIL)
    return data


def _calcular_perfil_overrides(user) -> dict:
    """
    Calcula los módulos visibles del usuario combinando dos capas:

    1) PerfilAcceso (base): define qué módulos ve su rol por defecto.
       Si no tiene perfil asignado → sin restricciones (ve todo lo que la empresa activa).

    2) PermisoModulo (overrides individuales): registros por usuario que pueden
       CONCEDER acceso a un módulo que el perfil no incluye, o
       REVOCAR uno que el perfil sí incluye.
       → Si existe PermisoModulo(modulo='analytics', puede_ver=True): se AÑADE.
       → Si existe PermisoModulo(modulo='salarios',  puede_ver=False): se QUITA.
       Los overrides tienen prioridad sobre el perfil.

    Regla final: empresa_activa AND (perfil_permite OR override_concede)
                                    y si override_revoca → False aunque el perfil lo permita.
    """
    # ── Capa 1: Perfil base ────────────────────────────────────────────
    base: dict = {}
    try:
        from personal.models import Personal
        personal = Personal.objects.select_related('perfil_acceso').get(usuario=user)
        if personal.perfil_acceso:
            base = personal.perfil_acceso.as_modulos_dict()
        # Sin perfil → base vacío (sin restricciones de perfil)
    except Exception:
        pass  # Sin Personal → sin restricciones de perfil

    # ── Capa 2: Overrides individuales (PermisoModulo) ─────────────────
    try:
        from core.models import PermisoModulo
        overrides = PermisoModulo.objects.filter(usuario=user).values('modulo', 'puede_ver')
        for ov in overrides:
            key = f'mod_{ov["modulo"]}'
            # puede_ver=True  → concede acceso (incluso si el perfil lo niega)
            # puede_ver=False → revoca acceso (incluso si el perfil lo permite)
            base[key] = ov['puede_ver']
    except Exception:
        pass

    return base


# ── API pública de invalidación ────────────────────────────────────────────

def invalidar_badge(user_pk: int | None = None):
    """Invalida badge de un usuario o de todos los superusers."""
    if user_pk is not None:
        cache.delete(f'harmoni_badge_{user_pk}_v3')
    else:
        from django.contrib.auth.models import User
        pks = User.objects.filter(is_superuser=True, is_active=True).values_list('pk', flat=True)
        cache.delete_many([f'harmoni_badge_{pk}_v3' for pk in pks])


def invalidar_config():
    """Invalida cache de configuración. Llamar en ConfiguracionSistema.save()."""
    cache.delete('harmoni_ctx_config_v5')


def invalidar_rol(user_pk: int):
    """Invalida cache de rol. Llamar al reasignar responsable de área."""
    cache.delete(f'harmoni_ctx_role_{user_pk}_v2')


def invalidar_empresas():
    """Invalida cache de empresas disponibles. Llamar en Empresa.save()."""
    cache.delete('harmoni_ctx_empresas_v1')


def invalidar_perfil(user_pk: int | None = None):
    """
    Invalida cache del perfil RBAC.
    Llamar cuando:
      - Se cambia personal.perfil_acceso
      - Se modifica un PerfilAcceso (afecta a todos sus usuarios)
      - Se crea/edita/elimina un PermisoModulo de un usuario
    """
    if user_pk is not None:
        cache.delete(f'harmoni_perfil_{user_pk}_v1')
    else:
        # Invalida perfiles de todos los usuarios activos no-superuser
        from django.contrib.auth.models import User
        pks = User.objects.filter(is_active=True, is_superuser=False).values_list('pk', flat=True)
        cache.delete_many([f'harmoni_perfil_{pk}_v1' for pk in pks])


def invalidar_extra_badges(user_pk: int | None = None):
    """Invalida badges granulares del sidebar para un usuario o todos los admins."""
    if user_pk is not None:
        cache.delete(f'harmoni_extra_badges_{user_pk}_v2')
    else:
        from django.contrib.auth.models import User
        pks = User.objects.filter(is_superuser=True, is_active=True).values_list('pk', flat=True)
        cache.delete_many([f'harmoni_extra_badges_{pk}_v2' for pk in pks])


def _get_extra_badges(user, area_ids: list) -> dict:
    """Badges granulares por sección del sidebar. Cached por usuario, TTL 60s."""
    cache_key = f'harmoni_extra_badges_{user.pk}_v2'
    data = cache.get(cache_key)
    if data is None:
        data = _calcular_extra_badges(user, area_ids)
        cache.set(cache_key, data, _TTL_BADGE)
    return data


def _calcular_extra_badges(user, area_ids: list) -> dict:
    """Calcula badges granulares para el sidebar sin arriesgar el render."""
    from django.db.models import Q

    result = {
        'vacaciones_badge': 0,
        'permisos_badge': 0,
        'prestamos_badge': 0,
        'disciplinaria_badge': 0,
        'encuestas_badge': 0,
    }

    is_admin = user.is_superuser
    af = Q(personal__subarea__area__in=area_ids) if area_ids else Q()

    # Vacaciones + Permisos pendientes
    try:
        from vacaciones.models import SolicitudVacacion, SolicitudPermiso
        vac_qs = SolicitudVacacion.objects.filter(estado='PENDIENTE')
        per_qs = SolicitudPermiso.objects.filter(estado='PENDIENTE')
        if not is_admin and area_ids:
            vac_qs = vac_qs.filter(af)
            per_qs = per_qs.filter(af)
        result['vacaciones_badge'] = vac_qs.count() if (is_admin or area_ids) else 0
        result['permisos_badge'] = per_qs.count() if (is_admin or area_ids) else 0
    except Exception:
        pass

    # Préstamos pendientes de aprobación
    if is_admin:
        try:
            from prestamos.models import Prestamo
            result['prestamos_badge'] = Prestamo.objects.filter(
                estado__in=['PENDIENTE', 'BORRADOR']
            ).count()
        except Exception:
            pass

    # Disciplinaria activa (procesos en curso legal)
    if is_admin:
        try:
            from disciplinaria.models import MedidaDisciplinaria
            result['disciplinaria_badge'] = MedidaDisciplinaria.objects.filter(
                estado__in=['BORRADOR', 'EN_DESCARGO', 'EN_RESOLUCION']
            ).count()
        except Exception:
            pass

    # Encuestas pendientes de respuesta para el empleado actual
    try:
        from personal.models import Personal
        personal = Personal.objects.filter(usuario=user).first()
        if personal:
            from encuestas.models import Encuesta, RespuestaEncuesta
            activas = Encuesta.objects.filter(estado='ACTIVA')
            respondidas = set(RespuestaEncuesta.objects.filter(
                personal=personal
            ).values_list('encuesta_id', flat=True))
            result['encuestas_badge'] = activas.exclude(pk__in=respondidas).count()
    except Exception:
        pass

    return result


def _get_workflow_pendientes(user) -> int:
    """Retorna el número de instancias de workflow pendientes para el usuario. Cached 60s."""
    cache_key = f'harmoni_wf_badge_{user.pk}_v1'
    count = cache.get(cache_key)
    if count is None:
        try:
            from workflows.services import get_pendientes_usuario
            count = get_pendientes_usuario(user).count()
        except Exception:
            count = 0
        cache.set(cache_key, count, _TTL_BADGE)
    return count
