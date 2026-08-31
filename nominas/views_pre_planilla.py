"""
Checklist de ALISTAMIENTO de planilla (pre-planilla).

Puente crítico entre asistencia y nómina: antes de generar la planilla del mes,
muestra en un semáforo qué falta resolver (papeletas por aprobar, HHEE y
justificaciones pendientes, empleados sin contrato vigente, contratos por vencer)
y qué se aplicará (préstamos y descuentos activos).

Complementa a `workflow_mes` (que cubre el PROCESO de emisión), no lo reemplaza.
Todas las consultas son defensivas: si un modelo/campo no existe, el check se
marca "no disponible" en vez de romper la página.
"""
import calendar as _cal
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse

from personal.permissions import filtrar_personal_por_request

MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]


def _safe(fn):
    """Ejecuta una consulta; devuelve None si algo falla (modelo/campo ausente)."""
    try:
        return fn()
    except Exception:
        return None


def _url(name):
    try:
        return reverse(name)
    except NoReverseMatch:
        return None


def _url_kwargs(name, **kwargs):
    try:
        return reverse(name, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _periodos_regulares(request):
    from nominas.models import PeriodoNomina

    qs = PeriodoNomina.objects.filter(tipo='REGULAR')
    empresa = getattr(request, 'empresa_actual', None)
    if empresa is not None:
        qs = qs.filter(Q(empresa=empresa) | Q(empresa__isnull=True))
    return qs


def _chk(
    clave,
    label,
    icono,
    valor,
    ok_si,
    tipo,
    detalle,
    url_name,
    *,
    items=None,
    url=None,
    action_label='Resolver',
):
    """Arma un check. `ok_si` decide verde; si valor es None => 'no disponible'."""
    if valor is None:
        estado = 'na'
    elif ok_si(valor):
        estado = 'ok'
    else:
        estado = tipo  # 'warn' o 'error'
    return {
        'clave': clave, 'label': label, 'icono': icono,
        'valor': valor, 'estado': estado, 'detalle': detalle,
        'url': url if url is not None else _url(url_name),
        'action_label': action_label,
        'items': items or [],
    }


def _personal_del_periodo(personal_qs, ini, fin):
    """Trabajadores que pertenecen al cierre del mes elegido."""
    return personal_qs.filter(
        Q(fecha_alta__isnull=True) | Q(fecha_alta__lte=fin),
    ).filter(
        Q(fecha_cese__isnull=True) | Q(fecha_cese__gte=ini),
    ).filter(
        Q(estado='Activo') | Q(fecha_cese__gte=ini),
    )


def _ids_con_cobertura_contractual(personal_qs, ids, ini, fin):
    """Contrato documental que cubre al trabajador en el mes de planilla."""
    from personal.models import Contrato

    con_contrato = set(
        Contrato.objects.filter(
            personal_id__in=ids,
            fecha_inicio__lte=fin,
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=ini)
        ).values_list('personal_id', flat=True)
    )
    con_ficha = set(
        personal_qs.filter(
            fecha_inicio_contrato__isnull=False,
            fecha_inicio_contrato__lte=fin,
        ).filter(
            Q(fecha_fin_contrato__isnull=True) | Q(fecha_fin_contrato__gte=ini)
        ).values_list('id', flat=True)
    )
    return con_contrato | con_ficha


def _ultimo_contrato_por_personal(ids):
    from personal.models import Contrato

    contratos = (
        Contrato.objects.filter(personal_id__in=ids)
        .order_by('personal_id', '-fecha_inicio', '-pk')
    )
    mapa = {}
    for contrato in contratos:
        mapa.setdefault(contrato.personal_id, contrato)
    return mapa


def _area_persona(persona):
    subarea = getattr(persona, 'subarea', None)
    area = getattr(subarea, 'area', None) if subarea else None
    if area:
        return area.nombre
    if subarea:
        return subarea.nombre
    return 'Sin área'


def _contrato_item_base(persona, motivo, action_label, action_url, *, fecha_inicio=None, fecha_fin=None):
    return {
        'nombre': persona.apellidos_nombres,
        'dni': persona.nro_doc or 'Sin DNI',
        'area': _area_persona(persona),
        'cargo': persona.cargo or 'Sin cargo',
        'motivo': motivo,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'action_label': action_label,
        'action_url': action_url,
        'secondary_label': 'Ver historial',
        'secondary_url': _url_kwargs('contrato_detalle', pk=persona.pk),
    }


def _motivo_sin_cobertura(persona, contrato, ini, fin):
    fecha_inicio = persona.fecha_inicio_contrato or (contrato.fecha_inicio if contrato else None)
    fecha_fin = persona.fecha_fin_contrato or (contrato.fecha_fin if contrato else None)

    if not fecha_inicio and not fecha_fin and not persona.tipo_contrato and contrato is None:
        return 'No tiene contrato registrado en ficha ni historial.'
    if fecha_inicio and fecha_inicio > fin:
        return 'El contrato registrado inicia después del mes de planilla.'
    if fecha_fin and fecha_fin < ini:
        return 'El contrato registrado terminó antes del mes de planilla.'
    if not fecha_inicio:
        return 'Falta fecha de inicio contractual para validar el mes.'
    return 'No hay contrato documental que cubra todo o parte del período.'


def _trabajadores_sin_cobertura_contractual(personal_qs, ids, ini, fin):
    cubiertos = _ids_con_cobertura_contractual(personal_qs, ids, ini, fin)
    faltantes = [personal_id for personal_id in ids if personal_id not in cubiertos]
    if not faltantes:
        return []

    contratos = _ultimo_contrato_por_personal(faltantes)
    personas = (
        personal_qs.filter(pk__in=faltantes)
        .select_related('subarea__area')
        .order_by('apellidos_nombres')
    )

    items = []
    for persona in personas:
        contrato = contratos.get(persona.pk)
        fecha_inicio = persona.fecha_inicio_contrato or (contrato.fecha_inicio if contrato else None)
        fecha_fin = persona.fecha_fin_contrato or (contrato.fecha_fin if contrato else None)
        items.append(_contrato_item_base(
            persona,
            _motivo_sin_cobertura(persona, contrato, ini, fin),
            'Crear contrato',
            _url_kwargs('contrato_crear', personal_pk=persona.pk),
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
        ))
    return items


def _trabajadores_con_contrato_sin_continuidad(personal_qs, ids, ini, fin):
    """Trabajadores cuyo contrato termina en el período y no tiene renovación."""
    from personal.models import Contrato

    pendientes = {}

    def _tiene_continuidad(personal_id, fecha_fin):
        inicio_siguiente = fecha_fin + timedelta(days=1)
        tiene_contrato = Contrato.objects.filter(
            personal_id=personal_id,
            fecha_inicio__lte=inicio_siguiente,
        ).filter(
            Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=inicio_siguiente)
        ).exists()
        if tiene_contrato:
            return True
        return personal_qs.filter(
            pk=personal_id,
            fecha_inicio_contrato__isnull=False,
            fecha_inicio_contrato__lte=inicio_siguiente,
        ).filter(
            Q(fecha_fin_contrato__isnull=True)
            | Q(fecha_fin_contrato__gte=inicio_siguiente)
        ).exists()

    contratos_terminan = Contrato.objects.filter(
        personal_id__in=ids,
        fecha_fin__gte=ini,
        fecha_fin__lte=fin,
    ).values_list('personal_id', 'fecha_fin')
    for personal_id, fecha_fin in contratos_terminan:
        if fecha_fin and not _tiene_continuidad(personal_id, fecha_fin):
            pendientes[personal_id] = max(fecha_fin, pendientes.get(personal_id, fecha_fin))

    fichas_terminan = personal_qs.filter(
        fecha_fin_contrato__gte=ini,
        fecha_fin_contrato__lte=fin,
    ).values_list('id', 'fecha_fin_contrato')
    for personal_id, fecha_fin in fichas_terminan:
        if fecha_fin and not _tiene_continuidad(personal_id, fecha_fin):
            pendientes[personal_id] = max(fecha_fin, pendientes.get(personal_id, fecha_fin))

    if not pendientes:
        return []

    personas = (
        personal_qs.filter(pk__in=pendientes)
        .select_related('subarea__area')
        .order_by('apellidos_nombres')
    )
    items = []
    for persona in personas:
        fecha_fin = pendientes[persona.pk]
        inicio_siguiente = fecha_fin + timedelta(days=1)
        items.append(_contrato_item_base(
            persona,
            f'Termina el {fecha_fin:%d/%m/%Y}; falta contrato desde el {inicio_siguiente:%d/%m/%Y}.',
            'Renovar con continuidad',
            _url_kwargs('contrato_renovar_personal', personal_pk=persona.pk),
            fecha_inicio=inicio_siguiente,
            fecha_fin=fecha_fin,
        ))
    return items


def _contratos_que_terminan_sin_continuidad(personal_qs, ids, ini, fin):
    return len(_trabajadores_con_contrato_sin_continuidad(personal_qs, ids, ini, fin))


@login_required
def pre_planilla(request):
    hoy = date.today()
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month
    if mes < 1 or mes > 12:
        mes = hoy.month
    if anio < 2000 or anio > hoy.year + 2:
        anio = hoy.year
    ini = date(anio, mes, 1)
    fin = date(anio, mes, _cal.monthrange(anio, mes)[1])

    personal_qs = _personal_del_periodo(
        filtrar_personal_por_request(request),
        ini,
        fin,
    )
    ids = list(personal_qs.values_list('id', flat=True))
    n_activos = len(ids)

    from asistencia.models import (
        JustificacionNoMarcaje,
        RegistroPapeleta,
        RegistroTareo,
        SolicitudHE,
    )
    checks = []

    # 1. Asistencia del mes cargada
    n_tareo = _safe(lambda: RegistroTareo.objects.filter(
        personal_id__in=ids, fecha__gte=ini, fecha__lte=fin).count())
    checks.append(_chk(
        'asistencia', 'Asistencia del mes cargada', 'fa-fingerprint',
        n_tareo, lambda v: v > 0, 'error',
        f'{n_tareo or 0} registros de tareo', 'asistencia_vista'))

    # 2. Papeletas por aprobar
    n_pap = _safe(lambda: RegistroPapeleta.objects.filter(
        personal_id__in=ids, estado='PENDIENTE',
        fecha_inicio__gte=ini, fecha_inicio__lte=fin).count())
    checks.append(_chk(
        'papeletas', 'Papeletas por aprobar', 'fa-file-signature',
        n_pap, lambda v: v == 0, 'warn',
        f'{n_pap or 0} pendientes', 'asistencia_papeletas'))

    # 3. Horas extra por aprobar
    n_he = _safe(lambda: SolicitudHE.objects.filter(
        personal_id__in=ids, estado='PENDIENTE',
        fecha__gte=ini, fecha__lte=fin).count())
    checks.append(_chk(
        'he', 'Horas extra por aprobar', 'fa-clock',
        n_he, lambda v: v == 0, 'warn',
        f'{n_he or 0} solicitudes', 'asistencia_solicitudes_he'))

    # 4. Justificaciones por revisar
    n_just = _safe(lambda: JustificacionNoMarcaje.objects.filter(
        personal_id__in=ids, estado='PENDIENTE',
        fecha__gte=ini, fecha__lte=fin).count())
    checks.append(_chk(
        'justif', 'Justificaciones por revisar', 'fa-pen-alt',
        n_just, lambda v: v == 0, 'warn',
        f'{n_just or 0} pendientes', 'asistencia_justificaciones'))

    # 5. Empleados del período sin cobertura contractual
    items_sin_contrato = _safe(lambda: _trabajadores_sin_cobertura_contractual(
        personal_qs, ids, ini, fin))
    n_sin = len(items_sin_contrato) if items_sin_contrato is not None else None
    checks.append(_chk(
        'contratos', 'Trabajadores sin contrato del período', 'fa-file-contract',
        n_sin, lambda v: v == 0, 'error',
        f'{n_sin or 0} de {n_activos} trabajadores', 'contratos_panel',
        items=items_sin_contrato,
        url='#pp-detail-contratos' if items_sin_contrato else None,
        action_label='Ver casos'))

    # 6. Contratos que terminan y todavía no tienen continuidad
    items_sin_continuidad = _safe(lambda: _trabajadores_con_contrato_sin_continuidad(
        personal_qs, ids, ini, fin))
    n_venc = len(items_sin_continuidad) if items_sin_continuidad is not None else None
    checks.append(_chk(
        'vencen', 'Contratos que terminan sin continuidad', 'fa-calendar-times',
        n_venc, lambda v: v == 0, 'warn',
        f'{n_venc or 0} por enlazar', 'contratos_panel',
        items=items_sin_continuidad,
        url='#pp-detail-vencen' if items_sin_continuidad else None,
        action_label='Ver casos'))

    # 7. Préstamos activos a descontar (informativo)
    n_prest = _safe(lambda: __import__(
        'prestamos.models', fromlist=['Prestamo']
    ).Prestamo.objects.filter(personal_id__in=ids, estado='EN_CURSO').count())
    checks.append({
        'clave': 'prestamos', 'label': 'Préstamos activos a descontar',
        'icono': 'fa-hand-holding-usd', 'valor': n_prest,
        'estado': 'info' if n_prest is not None else 'na',
        'detalle': f'{n_prest or 0} en curso', 'url': _url('prestamos_lista'),
    })

    # 8. Descuentos activos a aplicar (informativo)
    n_desc = _safe(lambda: __import__(
        'descuentos.models', fromlist=['DescuentoPlanilla']
    ).DescuentoPlanilla.objects.filter(
        personal_id__in=ids, estado__in=['APROBADO', 'EN_CURSO']).count())
    checks.append({
        'clave': 'descuentos', 'label': 'Descuentos activos a aplicar',
        'icono': 'fa-minus-circle', 'valor': n_desc,
        'estado': 'info' if n_desc is not None else 'na',
        'detalle': f'{n_desc or 0} activos', 'url': _url('descuentos_lista'),
    })

    # 9. Periodo de planilla del mes
    def _periodo():
        return _periodos_regulares(request).filter(anio=anio, mes=mes).order_by('-pk').first()
    per = _safe(_periodo)
    if per is None:
        per_estado, per_det = 'warn', 'Sin período creado aún'
    else:
        listo = per.estado in ('CALCULADO', 'APROBADO', 'CERRADO')
        per_estado = 'ok' if listo else 'warn'
        per_det = f'Período {per.get_estado_display()}'
    checks.append({
        'clave': 'periodo', 'label': 'Período de planilla', 'icono': 'fa-calendar-check',
        'valor': None, 'estado': per_estado, 'detalle': per_det,
        'url': _url('nominas_panel'),
    })

    # ── Resumen / semáforo global ──
    n_error = sum(1 for c in checks if c['estado'] == 'error')
    n_warn = sum(1 for c in checks if c['estado'] == 'warn')
    modo_cerrado = bool(per and per.estado == 'CERRADO')
    if modo_cerrado:
        estado_global, resumen = (
            'cerrado',
            'Período cerrado: datos congelados para auditoría',
        )
    elif n_error:
        estado_global, resumen = 'critico', 'Faltan puntos críticos por resolver'
    elif n_warn:
        estado_global, resumen = 'mejorable', 'Casi listo: revisa los pendientes'
    else:
        estado_global, resumen = 'listo', 'Alistamiento completo: puedes generar la planilla'

    context = {
        'checks': checks,
        'resolution_groups': [
            check for check in checks
            if check.get('items') and check['estado'] in ('error', 'warn')
        ],
        'estado_global': estado_global,
        'resumen': resumen,
        'n_error': n_error,
        'n_warn': n_warn,
        'mes': mes, 'anio': anio,
        'mes_nombre': dict(MESES).get(mes, ''),
        'meses': MESES,
        'anios': range(hoy.year - 2, hoy.year + 2),
        'n_activos': n_activos,
        'modo_cerrado': modo_cerrado,
    }
    return render(request, 'nominas/pre_planilla.html', context)
