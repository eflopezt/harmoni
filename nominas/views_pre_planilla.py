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
from datetime import date
import calendar as _cal

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse, NoReverseMatch

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


def _chk(clave, label, icono, valor, ok_si, tipo, detalle, url_name):
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
        'url': _url(url_name),
    }


@login_required
def pre_planilla(request):
    hoy = date.today()
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month
    ini = date(anio, mes, 1)
    fin = date(anio, mes, _cal.monthrange(anio, mes)[1])

    personal_qs = filtrar_personal_por_request(request)
    ids = list(personal_qs.values_list('id', flat=True))
    activos_ids = list(
        personal_qs.filter(estado='Activo').values_list('id', flat=True)
    )
    n_activos = len(activos_ids)

    from asistencia.models import (
        RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje, RegistroTareo,
    )
    from personal.models import Contrato

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

    # 5. Empleados activos sin contrato vigente
    def _sin_contrato():
        con = set(Contrato.objects.filter(
            personal_id__in=activos_ids, estado='VIGENTE'
        ).values_list('personal_id', flat=True))
        return sum(1 for i in activos_ids if i not in con)
    n_sin = _safe(_sin_contrato)
    checks.append(_chk(
        'contratos', 'Activos sin contrato vigente', 'fa-file-contract',
        n_sin, lambda v: v == 0, 'error',
        f'{n_sin or 0} de {n_activos} activos', 'personal_list'))

    # 6. Contratos que vencen este mes
    n_venc = _safe(lambda: Contrato.objects.filter(
        personal_id__in=activos_ids, estado='VIGENTE',
        fecha_fin__gte=hoy, fecha_fin__lte=fin).count())
    checks.append(_chk(
        'vencen', 'Contratos que vencen este mes', 'fa-calendar-times',
        n_venc, lambda v: v == 0, 'warn',
        f'{n_venc or 0} por vencer', 'personal_list'))

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
        from nominas.models import PeriodoNomina
        return PeriodoNomina.objects.filter(
            anio=anio, mes=mes, tipo='REGULAR').first()
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
    if n_error:
        estado_global, resumen = 'critico', 'Faltan puntos críticos por resolver'
    elif n_warn:
        estado_global, resumen = 'mejorable', 'Casi listo: revisa los pendientes'
    else:
        estado_global, resumen = 'listo', 'Alistamiento completo: puedes generar la planilla'

    context = {
        'checks': checks,
        'estado_global': estado_global,
        'resumen': resumen,
        'n_error': n_error,
        'n_warn': n_warn,
        'mes': mes, 'anio': anio,
        'mes_nombre': dict(MESES).get(mes, ''),
        'meses': MESES,
        'anios': range(hoy.year - 2, hoy.year + 2),
        'n_activos': n_activos,
    }
    return render(request, 'nominas/pre_planilla.html', context)
