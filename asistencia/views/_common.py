"""
Utilidades compartidas entre las vistas del módulo Tareo.
"""
from django.contrib.auth.decorators import user_passes_test
from django.db.models import OuterRef, Subquery

solo_admin = user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='login')


def _get_importacion_activa(tipo='RELOJ', importacion_id=None):
    """Devuelve la importación activa (por ID o la última completada de ese tipo)."""
    from asistencia.models import TareoImportacion
    if importacion_id:
        try:
            return TareoImportacion.objects.get(pk=importacion_id)
        except TareoImportacion.DoesNotExist:
            pass
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')
        .first()
    )


def _lista_importaciones(tipo='RELOJ'):
    """Lista de importaciones completadas para selector."""
    from asistencia.models import TareoImportacion
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')[:30]
    )


def _qs_staff_dedup(mes_ini, mes_fin):
    """
    Queryset de RegistroTareo STAFF para el rango de fechas dado,
    deduplicado: un solo registro por (personal, fecha), eligiendo
    siempre el de mayor importacion_id (importación más reciente).

    Evita doble-conteo cuando el mismo período fue importado varias veces
    (ej. import #1 SYNKRO y #5 RELOJ cubren el mismo rango de fechas).
    """
    from asistencia.models import RegistroTareo

    # Subquery: para cada (personal_id, fecha) STAFF, devuelve el id
    # del registro con el mayor importacion_id (el más reciente).
    latest_id = (
        RegistroTareo.objects
        .filter(
            personal_id=OuterRef('personal_id'),
            fecha=OuterRef('fecha'),
            grupo='STAFF',
        )
        .order_by('-importacion_id')
        .values('id')[:1]
    )

    return RegistroTareo.objects.filter(
        grupo='STAFF',
        fecha__gte=mes_ini,
        fecha__lte=mes_fin,
        personal__isnull=False,
        id=Subquery(latest_id),
    )
