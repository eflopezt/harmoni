"""
"Mi Día Nóminas" — Dashboard del admin/gerente RR.HH.

Vista personalizada que responde a:
"¿Qué tengo que hacer hoy en planilla?"

Expone también API JSON: GET /api/v1/nominas/mi-dia/
para apps mobile e integraciones.

Bloques:
1. Hoy / Esta semana — fechas críticas del calendario laboral peruano
2. Período actual — estado del mes y siguientes pasos
3. Acuses pendientes — boletas sin firmar por trabajador (DS 009-2011-TR)
4. Inconsistencias detectadas — conceptos mal configurados
5. Cambios recientes — últimos 7 días del audit log
6. Próximos hitos — gratif, CTS, vacaciones del mes

URL: /nominas/mi-dia/
"""
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .models import ConceptoAuditLog, ConceptoRemunerativo, PeriodoNomina, RegistroNomina

solo_admin = user_passes_test(lambda u: u.is_superuser)


# ─── Calendario laboral peruano ──────────────────────────────────
# Eventos recurrentes del año fiscal
_CALENDARIO_FIJO = [
    # (mes, día, etiqueta, descripción, severidad)
    (1,  31, 'Cierre IR 5ta Categoría',      'Última semana para presentar PLAME diciembre.', 'urgente'),
    (3,  31, 'Pago Utilidades (D.Leg. 892)', 'Empresas con +20 trabajadores y renta de 3ra.', 'urgente'),
    (5,  15, 'Cierre CTS Mayo',              'Depósito antes del 15 de mayo (D.Leg. 650).',  'critico'),
    (7,  15, 'Pago Gratificación Julio',     'Hasta 15 jul. Bonif. extraord. 9% (Ley 29351). EPS: 6.75%.', 'critico'),
    (9,  30, 'Cierre liquidación 3T',        'Recordar provisiones contables.', 'recordatorio'),
    (11, 15, 'Cierre CTS Noviembre',         'Depósito antes del 15 de noviembre.', 'critico'),
    (12, 15, 'Pago Gratificación Diciembre', 'Hasta 15 dic. Bonif. extraord. 9% (Ley 29351). EPS: 6.75%.', 'critico'),
]


def _calendario_proximos(hoy, ventana_dias=60):
    """Devuelve eventos del calendario en los próximos N días."""
    eventos = []
    for mes, dia, label, desc, sev in _CALENDARIO_FIJO:
        # Probar este año, año próximo si ya pasó
        for anio_offset in (0, 1):
            try:
                fecha = date(hoy.year + anio_offset, mes, dia)
            except ValueError:
                continue
            dias = (fecha - hoy).days
            if 0 <= dias <= ventana_dias:
                eventos.append({
                    'fecha':       fecha,
                    'dias':        dias,
                    'label':       label,
                    'descripcion': desc,
                    'severidad':   sev,
                    'es_hoy':      dias == 0,
                    'es_pronto':   dias <= 7,
                })
                break
    eventos.sort(key=lambda e: e['fecha'])
    return eventos


def _periodo_actual(hoy):
    """Período del mes en curso o más reciente."""
    p = PeriodoNomina.objects.filter(
        tipo='REGULAR',
        anio=hoy.year,
        mes=hoy.month,
    ).first()
    if p:
        return p, 'actual'
    # Último cerrado
    p = PeriodoNomina.objects.filter(tipo='REGULAR').order_by('-anio', '-mes').first()
    return p, 'historico'


def build_mi_dia_report(usuario):
    """Recolecta todo el contexto de 'Mi Día Nóminas'.

    Separado para que tanto la vista HTML como la API JSON
    compartan la lógica.
    """
    hoy = timezone.localdate()
    nombre_user = (usuario.get_full_name() if usuario.is_authenticated else None) \
                  or (usuario.username if usuario.is_authenticated else 'invitado')

    # Saludo según hora
    hora = timezone.localtime().hour
    if hora < 12:
        saludo = '¡Buenos días'
    elif hora < 19:
        saludo = '¡Buenas tardes'
    else:
        saludo = '¡Buenas noches'

    # 1. Calendario laboral
    eventos = _calendario_proximos(hoy, ventana_dias=60)
    eventos_hoy = [e for e in eventos if e['es_hoy']]
    eventos_semana = [e for e in eventos if 0 < e['dias'] <= 7]
    eventos_mes = [e for e in eventos if 7 < e['dias'] <= 30]

    # 2. Período actual
    periodo, periodo_estado = _periodo_actual(hoy)

    # 3. Acuses pendientes (boletas emitidas sin firmar)
    acuses_pendientes = 0
    try:
        from .models import RegistroNomina
        # Boletas de períodos APROBADOS o CERRADOS sin acuse de recibo
        # AcuseReciboBoleta tiene FK a RegistroNomina
        try:
            from documentos.models import AcuseReciboBoleta  # opcional
            firmados = AcuseReciboBoleta.objects.values_list('registro_nomina_id', flat=True)
            acuses_pendientes = RegistroNomina.objects.filter(
                periodo__estado__in=['APROBADO', 'CERRADO'],
            ).exclude(pk__in=firmados).count()
        except Exception:
            acuses_pendientes = 0
    except Exception:
        pass

    # 4. Inconsistencias de conceptos
    inconsistencias = 0
    try:
        from .views_conceptos import detectar_inconsistencias
        for c in ConceptoRemunerativo.objects.filter(activo=True).only(
            'id', 'codigo', 'subtipo', 'tipo', 'afecto_essalud', 'afecto_afp',
            'afecto_onp', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
            'afecto_renta', 'codigo_plame', 'formula', 'monto_fijo', 'es_sistema',
        ):
            if detectar_inconsistencias(c):
                inconsistencias += 1
    except Exception:
        pass

    # 5. Audit log — últimos 7 días
    desde = timezone.now() - timedelta(days=7)
    cambios_recientes = list(
        ConceptoAuditLog.objects
        .filter(fecha__gte=desde)
        .select_related('usuario')
        .order_by('-fecha')[:10]
    )
    cambios_count = ConceptoAuditLog.objects.filter(fecha__gte=desde).count()

    # 6. KPIs rápidos del último período
    kpi = {}
    if periodo:
        agg = RegistroNomina.objects.filter(periodo=periodo).aggregate(
            total_trab=Count('id'),
            total_neto=Sum('neto_a_pagar'),
            total_bruto=Sum('total_ingresos'),
            total_desc=Sum('total_descuentos'),
        )
        kpi = {
            'trabajadores': agg['total_trab'] or 0,
            'neto':         float(agg['total_neto'] or 0),
            'bruto':        float(agg['total_bruto'] or 0),
            'descuentos':   float(agg['total_desc'] or 0),
        }

    # 7. Tareas sugeridas (smart actions según estado actual)
    tareas = []
    if periodo:
        if periodo.estado == 'BORRADOR':
            tareas.append({
                'icon': 'fas fa-calculator', 'color': '#0f766e',
                'titulo': f'Generar planilla {periodo}',
                'descripcion': 'El período está en borrador. Genera el cálculo.',
                'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            })
        elif periodo.estado == 'CALCULADO':
            tareas.append({
                'icon': 'fas fa-check-circle', 'color': '#15803d',
                'titulo': f'Aprobar planilla {periodo}',
                'descripcion': 'Período calculado. Revisa y aprueba para liberar boletas.',
                'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            })
        elif periodo.estado == 'APROBADO' and not periodo.contabilizado:
            tareas.append({
                'icon': 'fas fa-file-csv', 'color': '#1d4ed8',
                'titulo': 'Exportar asiento contable',
                'descripcion': 'Planilla aprobada — exporta para tu contador.',
                'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            })

    if acuses_pendientes >= 5:
        tareas.append({
            'icon': 'fas fa-envelope-open-text', 'color': '#d97706',
            'titulo': f'{acuses_pendientes} acuses de boleta pendientes',
            'descripcion': 'Notifica a los trabajadores para que firmen.',
            'link': reverse('nominas_emision_boletas'),
        })

    if inconsistencias > 0:
        tareas.append({
            'icon': 'fas fa-exclamation-triangle', 'color': '#dc2626',
            'titulo': f'{inconsistencias} conceptos con inconsistencias',
            'descripcion': 'Revisa flags de afectación incongruentes.',
            'link': reverse('conceptos_lista'),
        })

    if periodo and periodo.estado in ['APROBADO', 'CERRADO']:
        if not RegistroNomina.objects.filter(periodo=periodo).exists():
            pass
        else:
            # PLAME
            tareas.append({
                'icon': 'fas fa-file-export', 'color': '#0369a1',
                'titulo': 'Exportar PLAME',
                'descripcion': 'Archivo plano para subir a SUNAT (T-Registro y PDT 601).',
                'link': reverse('nominas_periodo_plame', args=[periodo.pk]),
            })

    # Si no hay tareas, mostrar mensaje positivo
    if not tareas:
        tareas.append({
            'icon': 'fas fa-coffee', 'color': '#0f766e',
            'titulo': '¡Todo al día!',
            'descripcion': 'No tienes pendientes urgentes. Buen momento para revisar el plan del mes próximo.',
            'link': reverse('nominas_panel'),
        })

    return {
        'hoy':                hoy,
        'nombre_user':        nombre_user,
        'saludo':             saludo,
        'eventos_hoy':        eventos_hoy,
        'eventos_semana':     eventos_semana,
        'eventos_mes':        eventos_mes,
        'periodo':            periodo,
        'periodo_estado':     periodo_estado,
        'acuses_pendientes':  acuses_pendientes,
        'inconsistencias':    inconsistencias,
        'cambios_recientes':  cambios_recientes,
        'cambios_count':      cambios_count,
        'kpi':                kpi,
        'tareas':             tareas,
    }


# ─── Vista HTML ──────────────────────────────────────────────────────
@login_required
@solo_admin
def mi_dia_nominas(request):
    """Dashboard HTML 'Mi Día Nóminas' (Design V2 Cockpit)."""
    ctx = build_mi_dia_report(request.user)
    return render(request, 'nominas/mi_dia_nominas.html', ctx)


# ─── API JSON ────────────────────────────────────────────────────────
@login_required
def mi_dia_api(request):
    """GET /api/v1/nominas/mi-dia/  →  JSON mobile-friendly."""
    from django.http import JsonResponse

    ctx = build_mi_dia_report(request.user)

    # Serializar: períodos, fechas, logs → dicts
    periodo = ctx['periodo']
    periodo_dict = None
    if periodo:
        periodo_dict = {
            'id':           periodo.pk,
            'tipo':         periodo.tipo,
            'anio':         periodo.anio,
            'mes':          periodo.mes,
            'estado':       periodo.estado,
            'descripcion':  str(periodo),
        }

    cambios = [{
        'fecha':           log.fecha.isoformat(),
        'accion':          log.accion,
        'accion_label':    log.get_accion_display(),
        'concepto_codigo': log.concepto_codigo,
        'concepto_nombre': log.concepto_nombre,
        'usuario':         log.usuario_username or 'sistema',
        'num_cambios':     log.num_cambios,
    } for log in ctx['cambios_recientes']]

    eventos_to_dict = lambda lst: [{
        'fecha':       e['fecha'].isoformat(),
        'dias':        e['dias'],
        'label':       e['label'],
        'descripcion': e['descripcion'],
        'severidad':   e['severidad'],
        'es_hoy':      e['es_hoy'],
        'es_pronto':   e['es_pronto'],
    } for e in lst]

    return JsonResponse({
        'hoy':             ctx['hoy'].isoformat(),
        'saludo':          ctx['saludo'],
        'usuario':         ctx['nombre_user'],
        'periodo':         periodo_dict,
        'periodo_estado': ctx['periodo_estado'],
        'kpi':             ctx['kpi'],
        'eventos_hoy':     eventos_to_dict(ctx['eventos_hoy']),
        'eventos_semana':  eventos_to_dict(ctx['eventos_semana']),
        'eventos_mes':     eventos_to_dict(ctx['eventos_mes']),
        'acuses_pendientes': ctx['acuses_pendientes'],
        'inconsistencias': ctx['inconsistencias'],
        'cambios_count':   ctx['cambios_count'],
        'cambios_recientes': cambios,
        'tareas':          ctx['tareas'],
    })
