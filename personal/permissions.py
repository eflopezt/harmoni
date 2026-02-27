"""
Utilidades para manejo de permisos y filtros por usuario.
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from .models import Area, SubArea, Personal


def es_responsable_area(user):
    """Verifica si el usuario es responsable de un área."""
    if user.is_superuser:
        return False
    if user.groups.filter(name='Responsable de Área').exists():
        return True
    return get_areas_responsable(user).exists()


def get_areas_responsable(user):
    """Obtiene las áreas de las que el usuario es responsable."""
    if user.is_superuser:
        return Area.objects.none()

    personal = getattr(user, 'personal_data', None)
    if not personal:
        personal = Personal.objects.filter(usuario=user).first()

    if not personal:
        return Area.objects.none()

    return Area.objects.filter(responsables=personal)


def get_area_responsable(user):
    """Obtiene una sola área responsable (compatibilidad para UI)."""
    return get_areas_responsable(user).first()


def filtrar_areas(user):
    """Filtra áreas según el usuario."""
    # Todos los usuarios pueden ver todas las áreas (son catálogos)
    # La restricción de edición se hace a nivel de vista
    return Area.objects.all()


def filtrar_subareas(user):
    """Filtra subáreas según el usuario."""
    if user.is_superuser:
        return SubArea.objects.all()
    
    areas = get_areas_responsable(user)
    if areas.exists():
        return SubArea.objects.filter(area__in=areas)
    
    return SubArea.objects.none()


def filtrar_personal(user):
    """Filtra personal según el usuario."""
    if user.is_superuser:
        return Personal.objects.all()
    
    # Si el usuario tiene un Personal vinculado, puede ver su propio registro
    if hasattr(user, 'personal_data') and user.personal_data:
        # Si también es responsable, ve su área completa
        areas = get_areas_responsable(user)
        if areas.exists():
            return Personal.objects.filter(subarea__area__in=areas)
        # Si solo es personal regular, solo ve su propio registro
        return Personal.objects.filter(id=user.personal_data.id)
    
    # Si es responsable sin Personal vinculado (caso legacy)
    areas = get_areas_responsable(user)
    if areas.exists():
        return Personal.objects.filter(subarea__area__in=areas)
    
    return Personal.objects.none()


def puede_editar_personal(user, personal):
    """Verifica si el usuario puede editar un personal específico."""
    if user.is_superuser:
        return True
    
    # Un usuario puede editar su propio registro de Personal
    if hasattr(user, 'personal_data') and user.personal_data and user.personal_data == personal:
        return True
    
    # Un responsable puede editar el personal de su área
    areas = get_areas_responsable(user)
    if personal.subarea and areas.filter(pk=personal.subarea.area_id).exists():
        return True
    
    return False


def puede_editar_roster(user, personal):
    """Verifica si el usuario puede editar roster de un personal específico."""
    if user.is_superuser:
        return True

    areas = get_areas_responsable(user)
    if personal.subarea and areas.filter(pk=personal.subarea.area_id).exists():
        return True

    return False


def solo_responsable(view_func):
    """
    Decorador que restringe el acceso solo a responsables de area.
    Los superusuarios también tienen acceso.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or es_responsable_area(request.user):
            return view_func(request, *args, **kwargs)
        messages.error(request, 'No tienes permisos para acceder a esta sección.')
        return redirect('home')
    return wrapper


def get_context_usuario(user):
    """
    Retorna contexto común para el usuario (gerencia, es_responsable, etc).
    """
    from .models import Roster
    
    es_responsable = es_responsable_area(user)
    areas = get_areas_responsable(user) if es_responsable else Area.objects.none()
    
    # Contar cambios pendientes de aprobación
    cambios_pendientes = 0
    if user.is_superuser:
        cambios_pendientes = Roster.objects.filter(estado='pendiente').count()
    elif areas.exists():
        cambios_pendientes = Roster.objects.filter(
            estado='pendiente',
            personal__subarea__area__in=areas
        ).count()
    
    return {
        'es_responsable': es_responsable,
        'area_responsable': areas.first(),
        'areas_responsable': areas,
        'es_superusuario': user.is_superuser,
        'cambios_pendientes': cambios_pendientes,
    }
