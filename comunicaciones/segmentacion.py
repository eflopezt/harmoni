"""
Resolución de destinatarios de campañas de comunicación.

Reusa los filtros declarativos de CampanaComunicacion para construir un
QuerySet de Personal. Puede usarse también desde otros módulos que
necesiten segmentar empleados (encuestas, capacitaciones, etc.).
"""
import logging

logger = logging.getLogger('comunicaciones.segmentacion')


def resolver_destinatarios(campana):
    """
    Devuelve un QuerySet de Personal según los filtros de la campaña.

    Filtros aplicados en orden (AND):
        - filtro_solo_activos: estado='Activo'
        - filtro_area_ids: subarea__area_id IN
        - filtro_subarea_ids: subarea_id IN
        - filtro_cargo: cargo__icontains
        - filtro_grupo_tareo: grupo_tareo exacto
        - filtro_empresa_ids: empresa_id IN

    Args:
        campana: instancia de CampanaComunicacion (o cualquier objeto
                 con los atributos filtro_*).

    Returns:
        QuerySet[Personal] distinct, ordenado por apellidos_nombres.
    """
    from personal.models import Personal

    qs = Personal.objects.all()

    # Solo activos (default True)
    if getattr(campana, 'filtro_solo_activos', True):
        qs = qs.filter(estado='Activo')

    # Áreas
    area_ids = getattr(campana, 'filtro_area_ids', None) or []
    if area_ids:
        qs = qs.filter(subarea__area_id__in=area_ids)

    # SubÁreas
    subarea_ids = getattr(campana, 'filtro_subarea_ids', None) or []
    if subarea_ids:
        qs = qs.filter(subarea_id__in=subarea_ids)

    # Cargo (substring)
    cargo = (getattr(campana, 'filtro_cargo', '') or '').strip()
    if cargo:
        qs = qs.filter(cargo__icontains=cargo)

    # Grupo tareo
    grupo = (getattr(campana, 'filtro_grupo_tareo', '') or '').strip()
    if grupo:
        qs = qs.filter(grupo_tareo=grupo)

    # Empresa (puede no existir el campo en Personal en algunos forks)
    empresa_ids = getattr(campana, 'filtro_empresa_ids', None) or []
    if empresa_ids:
        try:
            qs = qs.filter(empresa_id__in=empresa_ids)
        except Exception as exc:
            # Si Personal no tiene FK a Empresa, ignoramos el filtro
            logger.warning(
                f"Filtro empresa ignorado (Personal sin empresa_id): {exc}"
            )

    return qs.distinct().order_by('apellidos_nombres')


def contar_destinatarios(campana):
    """Atajo: cuenta destinatarios sin materializar la lista."""
    return resolver_destinatarios(campana).count()


def vista_previa_destinatarios(campana, sample_size=5):
    """
    Devuelve dict con {'total': N, 'sample': [Personal, ...]}.

    Útil para pintar "Vista previa" en el formulario de creación.
    """
    qs = resolver_destinatarios(campana)
    return {
        'total': qs.count(),
        'sample': list(qs[:sample_size]),
    }
