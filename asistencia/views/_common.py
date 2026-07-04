"""
Utilidades compartidas entre las vistas del módulo Tareo.
"""
from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Exists, Max, OuterRef, Subquery

# RBAC (WS1): staff con mod_asistencia (staff sin perfil conserva acceso, compat).
from core.permisos import requiere_modulo_o_staff
solo_admin = requiere_modulo_o_staff('asistencia')
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

    Implementación: Subquery con MAX(importacion_id) por (personal_id, fecha).
    El índice parcial tareo_staff_dedup_idx (personal_id, fecha, importacion_id DESC)
    WHERE grupo='STAFF' convierte el inner scan en un Index-Only Scan sin sort.
    """
    from asistencia.models import RegistroTareo

    # MAX importacion_id para cada (personal_id, fecha) STAFF —
    # el índice tareo_staff_dedup_idx hace esto un Index-Only Scan instantáneo.
    max_imp_subq = (
        RegistroTareo.objects
        .filter(
            personal_id=OuterRef('personal_id'),
            fecha=OuterRef('fecha'),
            grupo='STAFF',
        )
        .values('personal_id', 'fecha')
        .annotate(max_imp=Max('importacion_id'))
        .values('max_imp')
    )

    return RegistroTareo.objects.filter(
        grupo='STAFF',
        fecha__gte=mes_ini,
        fecha__lte=mes_fin,
        personal__isnull=False,
        importacion_id=Subquery(max_imp_subq),
    )


# ── Códigos de ausencia pagada (no descuentan, cuentan como 8h jornada legal) ──
# Fuente canónica — importar desde aquí en banco.py y reporte_individual.py
CODIGOS_AUSENCIA_PAGADA = {
    'DL', 'DLA', 'VAC', 'LCG', 'DM', 'LF', 'LP', 'CHE',
    'CT', 'CDT', 'CPF', 'FER', 'TR',
}

# ── Mapeo tipo_permiso → código tareo para papeletas ─────────
TIPO_PERMISO_A_CODIGO = {
    'VACACIONES': 'VAC',
    'LICENCIA_SIN_GOCE': 'LSG',
    'LICENCIA_CON_GOCE': 'LCG',
    'DESCANSO_MEDICO': 'DM',
    'COMPENSACION_HE': 'CHE',
    'LICENCIA_FALLECIMIENTO': 'LF',
    'LICENCIA_PATERNIDAD': 'LP',
    'COMISION_TRABAJO': 'CT',
    'COMP_DIA_TRABAJO': 'CDT',
    'COMPENSACION_FERIADO': 'CPF',
    'SUSPENSION': 'SAI',
    'SUSPENSION_ACTO_INSEGURO': 'SAI',
    'BAJADAS': 'DL',
    'BAJADAS_ACUMULADAS': 'DLA',
}


def _qs_sin_papeleta(qs, incluir_pendientes=True):
    """Excluye RegistroTareo cuyas fechas están cubiertas por una papeleta
    vigente del mismo personal.

    Por defecto considera APROBADA, EJECUTADA y PENDIENTE — mismo criterio
    que la matriz asistencial (`_papeletas_bulk`), para que el usuario vea
    los mismos días excluidos en pantalla y en reportes. Las pendientes se
    asume "buena fe": si después se rechaza la papeleta, los días vuelven
    a contar como falta automáticamente.

    Pasar `incluir_pendientes=False` para criterio estricto (solo papeletas
    aprobadas), útil en cierre de planilla S10 si se requiere.

    Implementación: correlated EXISTS subquery — Postgres lo resuelve
    eficientemente con el índice (personal_id, fecha_inicio, fecha_fin).
    """
    from asistencia.models import RegistroPapeleta
    estados = (['APROBADA', 'EJECUTADA', 'PENDIENTE']
               if incluir_pendientes else ['APROBADA', 'EJECUTADA'])
    cubre = RegistroPapeleta.objects.filter(
        personal_id=OuterRef('personal_id'),
        estado__in=estados,
        fecha_inicio__lte=OuterRef('fecha'),
        fecha_fin__gte=OuterRef('fecha'),
    )
    return qs.annotate(_tiene_pap=Exists(cubre)).filter(_tiene_pap=False)


def _papeletas_por_fecha(personal_id, inicio, fin):
    """
    Construye un dict {date: codigo_tareo} a partir de RegistroPapeleta.

    Solo considera papeletas APROBADAS o EJECUTADAS.
    Si hay múltiples papeletas para la misma fecha, la primera gana.
    """
    from asistencia.models import RegistroPapeleta
    papeletas = RegistroPapeleta.objects.filter(
        personal_id=personal_id,
        fecha_inicio__lte=fin,
        fecha_fin__gte=inicio,
        estado__in=['APROBADA', 'EJECUTADA', 'PENDIENTE'],
    ).order_by('pk')

    fecha_map = {}
    for pap in papeletas:
        codigo = TIPO_PERMISO_A_CODIGO.get(pap.tipo_permiso, pap.tipo_permiso)
        d = max(pap.fecha_inicio, inicio)
        tope = min(pap.fecha_fin, fin)
        while d <= tope:
            if d not in fecha_map:
                fecha_map[d] = codigo
            d += timedelta(days=1)
    return fecha_map


def _papeletas_bulk(personal_ids, inicio, fin):
    """
    Versión bulk: {personal_id: {date: {codigo, pk, tipo_display, detalle, estado, fecha_inicio, fecha_fin}}}
    Para uso en la vista matricial (calendario grid).
    """
    from asistencia.models import RegistroPapeleta
    papeletas = RegistroPapeleta.objects.filter(
        personal_id__in=personal_ids,
        fecha_inicio__lte=fin,
        fecha_fin__gte=inicio,
        estado__in=['APROBADA', 'EJECUTADA', 'PENDIENTE'],
    ).order_by('pk')

    result = {}
    for pap in papeletas:
        pid = pap.personal_id
        codigo = TIPO_PERMISO_A_CODIGO.get(pap.tipo_permiso, pap.tipo_permiso)
        info = {
            'codigo': codigo,
            'pk': pap.pk,
            'tipo_display': pap.get_tipo_permiso_display(),
            'detalle': pap.detalle or '',
            'estado': pap.get_estado_display(),
            'fecha_inicio': pap.fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_fin': pap.fecha_fin.strftime('%d/%m/%Y'),
            'dias_habiles': pap.dias_habiles,
        }
        if pid not in result:
            result[pid] = {}
        d = max(pap.fecha_inicio, inicio)
        tope = min(pap.fecha_fin, fin)
        while d <= tope:
            if d not in result[pid]:
                result[pid][d] = info
            d += timedelta(days=1)
    return result
