"""
Cierre mensual de planilla con un carril guiado de inicio a fin.

Vista que muestra el flujo completo del cierre mensual con steps
secuenciales, indicando qué ya está hecho y qué falta:

 1. Importar asistencia del mes
 2. Verificar conceptos sin inconsistencias
 3. Crear/abrir período del mes
 4. Generar planilla
 5. Aprobar planilla
 6. Emitir boletas + notificar trabajadores
 7. Recolectar acuses
 8. Exportar PLAME a SUNAT
 9. Exportar AFPNet (AFP Habitat/Integra/Prima/Profuturo)
10. Generar archivo de pago a banco
11. Exportar asiento contable
12. Cerrar período

Cada step tiene un `key` estable (str) — el frontend puede ocultarlos
vía localStorage (`workflow_mes_hidden_steps`) para personalizar el
checklist por usuario sin migrar BD.

URL: /nominas/workflow-mes/
"""
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

solo_admin = user_passes_test(lambda u: u.is_superuser)

MESES = [
    (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
    (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
    (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
]


def _periodos_regulares(request):
    """Base de periodos regulares, acotada al RUC activo si existe."""
    from .models import PeriodoNomina

    qs = PeriodoNomina.objects.filter(tipo='REGULAR')
    empresa = getattr(request, 'empresa_actual', None)
    if empresa is not None:
        qs = qs.filter(Q(empresa=empresa) | Q(empresa__isnull=True))
    return qs


def _parse_periodo_request(request, hoy):
    """Lee ?mes=&anio=; si no viene, usa el mes actual."""
    try:
        mes = int(request.GET.get('mes', hoy.month))
        anio = int(request.GET.get('anio', hoy.year))
    except (TypeError, ValueError):
        mes, anio = hoy.month, hoy.year
    if mes < 1 or mes > 12:
        mes = hoy.month
    if anio < 2000 or anio > hoy.year + 2:
        anio = hoy.year
    return mes, anio


def _periodo_query(mes, anio):
    return f'mes={mes}&anio={anio}'


def _periodo_create_url(mes, anio):
    query = urlencode({
        'tipo': 'REGULAR',
        'mes': mes,
        'anio': anio,
        'origen': 'workflow',
    })
    return f'{reverse("nominas_periodo_crear")}?{query}'


def _status_from_step(step):
    if step.get('done'):
        return 'done'
    if step.get('bloqueado'):
        return 'locked'
    if step.get('actual'):
        return 'current'
    if step.get('post_close_attention'):
        return 'warning'
    return 'pending'


def _construir_steps(periodo, anio, mes, request):
    """Construye la lista de steps con estado calculado."""
    from .models import RegistroNomina

    steps = []
    query = _periodo_query(mes, anio)

    # Step 1: Asistencia del mes
    asis_done = False
    asis_link = f'{reverse("pre_planilla")}?{query}'
    asis_msg = f'Valida tareo, permisos, HE y ausencias de {mes:02d}/{anio}'
    try:
        # El sistema registra asistencia en RegistroTareo (no existe
        # RegistroAsistencia → el import fallaba siempre y el paso 1 quedaba
        # eternamente "no hecho" aunque hubiera tareo cargado).
        from asistencia.models import RegistroTareo
        tareo_qs = RegistroTareo.objects.filter(fecha__year=anio, fecha__month=mes)
        empresa = getattr(request, 'empresa_actual', None)
        if empresa is not None:
            tareo_qs = tareo_qs.filter(personal__empresa=empresa)
        count = tareo_qs.count()
        if count > 0:
            asis_done = True
            asis_msg = f'{count} registros del período alimentan la planilla'
    except Exception:
        pass
    steps.append({
        'n': 1, 'key': 'asistencia', 'icon': 'fas fa-clock', 'titulo': 'Asistencia del mes',
        'descripcion': asis_msg, 'done': asis_done, 'link': asis_link,
        'phase': 'preparar', 'origen': 'Asistencia y turnos',
        'resultado': 'Tareo entra al cálculo sin volver a cargarlo',
        'cta': 'Preparar datos',
    })

    # Step 2: Conceptos sin inconsistencias
    inconsistencias = 0
    try:
        from .models import ConceptoRemunerativo
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
    steps.append({
        'n': 2, 'key': 'conceptos', 'icon': 'fas fa-cogs', 'titulo': 'Conceptos sin inconsistencias',
        'descripcion': 'Todos los conceptos activos bien configurados'
                       if inconsistencias == 0
                       else f'{inconsistencias} concepto(s) con flags inconsistentes',
        'done': inconsistencias == 0, 'link': reverse('conceptos_lista'),
        'phase': 'preparar', 'origen': 'Conceptos y afectaciones',
        'resultado': 'Haberes, descuentos y PLAME salen con reglas únicas',
        'cta': 'Revisar conceptos' if inconsistencias else 'Ver conceptos',
    })

    # Step 3: Crear/abrir período
    if periodo:
        steps.append({
            'n': 3, 'key': 'periodo', 'icon': 'fas fa-calendar-plus', 'titulo': 'Período abierto',
            'descripcion': f'Período {periodo.mes:02d}/{periodo.anio} ({periodo.get_estado_display()})',
            'done': True, 'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'preparar', 'origen': 'Calendario de planilla',
            'resultado': 'El cierre usa un solo período como fuente de verdad',
            'cta': 'Abrir período',
        })
    else:
        steps.append({
            'n': 3, 'key': 'periodo', 'icon': 'fas fa-calendar-plus', 'titulo': 'Crear período del mes',
            'descripcion': f'Crea el período REGULAR de {mes:02d}/{anio}',
            'done': False, 'link': _periodo_create_url(mes, anio),
            'phase': 'preparar', 'origen': 'Calendario de planilla',
            'resultado': 'Abre el contenedor del cálculo mensual',
            'cta': 'Crear período',
        })

    # Step 4-10 dependen del periodo
    if periodo:
        n_registros = RegistroNomina.objects.filter(periodo=periodo).count()
        # Step 4: Generar
        generado = periodo.estado in ('CALCULADO', 'APROBADO', 'CERRADO') and n_registros > 0
        steps.append({
            'n': 4, 'key': 'generar', 'icon': 'fas fa-calculator', 'titulo': 'Generar planilla',
            'descripcion': f'{n_registros} boletas calculadas'
                           if generado
                           else 'Período cerrado sin registros calculados'
                           if periodo.estado == 'CERRADO'
                           else 'Pendiente — ejecuta cálculo',
            'done': generado,
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'calcular', 'origen': 'Datos preparados',
            'resultado': 'Boletas y totales quedan calculados una sola vez',
            'cta': 'Calcular' if periodo.estado == 'BORRADOR' else 'Abrir cálculo',
        })
        # Step 5: Aprobar
        steps.append({
            'n': 5, 'key': 'aprobar', 'icon': 'fas fa-check-circle', 'titulo': 'Aprobar planilla',
            'descripcion': 'Período aprobado — listo para emitir'
                           if periodo.estado in ('APROBADO', 'CERRADO') and n_registros > 0
                           else 'Pendiente — revisar y aprobar',
            'done': periodo.estado in ('APROBADO', 'CERRADO') and n_registros > 0,
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'validar', 'origen': 'Cálculo del período',
            'resultado': 'Variaciones y excepciones quedan trazables',
            'cta': 'Revisar y aprobar',
        })
        # Step 6: Emitir boletas
        steps.append({
            'n': 6, 'key': 'boletas', 'icon': 'fas fa-paper-plane', 'titulo': 'Emitir boletas',
            'descripcion': 'Notifica a trabajadores que tienen boleta lista',
            'done': periodo.estado in ('APROBADO', 'CERRADO') and n_registros > 0,
            'link': reverse('nominas_emision_boletas'),
            'phase': 'entregar', 'origen': 'Planilla aprobada',
            'resultado': 'Boletas disponibles para colaborador y RRHH',
            'cta': 'Emitir boletas',
        })
        # Step 7: Recolectar acuses
        acuses_count = 0
        firmados = 0
        try:
            from .models import AcuseReciboBoleta
            firmados_pks = set(AcuseReciboBoleta.objects.values_list('registro_nomina_id', flat=True))
            registros = RegistroNomina.objects.filter(periodo=periodo).values_list('pk', flat=True)
            acuses_count = len(registros)
            firmados = sum(1 for r in registros if r in firmados_pks)
        except Exception:
            pass
        pct_firmado = int(firmados / acuses_count * 100) if acuses_count else 0
        steps.append({
            'n': 7, 'key': 'acuses', 'icon': 'fas fa-signature', 'titulo': 'Acuses de recibo',
            'descripcion': 'Sin boletas emitidas para recoger acuses'
                           if acuses_count == 0
                           else f'{firmados}/{acuses_count} firmados ({pct_firmado}%)',
            'done': (acuses_count == 0 and periodo.estado == 'CERRADO') or (
                acuses_count > 0 and pct_firmado >= 80),
            'link': reverse('nominas_emision_boletas'),
            'phase': 'entregar', 'origen': 'Portal del colaborador',
            'resultado': 'Evidencia de recepción lista para fiscalización',
            'cta': 'Ver acuses',
        })
        # Step 8: Exportar PLAME
        steps.append({
            'n': 8, 'key': 'plame', 'icon': 'fas fa-file-export', 'titulo': 'Exportar PLAME',
            'descripcion': 'Genera archivo plano para SUNAT (T-Registro/PDT 601)',
            'done': periodo.estado == 'CERRADO' and n_registros > 0,  # no tenemos flag específico
            'link': reverse('nominas_periodo_plame', args=[periodo.pk])
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'exportar', 'origen': 'Planilla aprobada',
            'resultado': 'Archivo SUNAT listo sin armar Excel manual',
            'cta': 'Descargar PLAME',
        })
        # Step 9: Exportar AFPNet (Habitat / Integra / Prima / Profuturo)
        steps.append({
            'n': 9, 'key': 'afpnet', 'icon': 'fas fa-piggy-bank', 'titulo': 'Exportar AFPNet',
            'descripcion': 'Archivo plano para AFP Habitat, Integra, Prima y Profuturo (formato SBS)'
                           if periodo.estado in ('APROBADO', 'CERRADO')
                           else 'Disponible cuando la planilla esté aprobada',
            'done': periodo.estado == 'CERRADO' and n_registros > 0,
            'link': reverse('integ_afp_net_panel')
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'exportar', 'origen': 'Descuentos pensionarios',
            'resultado': 'AFPNet sale desde el cálculo aprobado',
            'cta': 'Abrir AFPNet',
        })
        # Step 10: Pago a banco (archivo de transferencias por el NETO)
        steps.append({
            'n': 10, 'key': 'banco', 'icon': 'fas fa-university', 'titulo': 'Pago a banco',
            'descripcion': 'Genera el archivo de transferencias (neto) para el banco'
                           if periodo.estado in ('APROBADO', 'CERRADO')
                           else 'Disponible cuando la planilla esté aprobada',
            'done': periodo.estado == 'CERRADO' and n_registros > 0,
            'link': reverse('nominas_periodo_archivo_banco', args=[periodo.pk])
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'exportar', 'origen': 'Neto aprobado',
            'resultado': 'Transferencias bancarias listas por período',
            'cta': 'Archivo banco',
        })
        # Step 11: Asiento contable
        steps.append({
            'n': 11, 'key': 'contable', 'icon': 'fas fa-file-invoice', 'titulo': 'Asiento contable',
            'descripcion': 'Exportado a CONCAR/Siscont/SAP'
                           if getattr(periodo, 'contabilizado', False)
                           else 'Pendiente — exporta para tu contador',
            'done': getattr(periodo, 'contabilizado', False),
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'exportar', 'origen': 'Totales aprobados',
            'resultado': 'Contabilidad recibe el asiento sin recaptura',
            'cta': 'Ver contabilidad',
        })
        # Step 12: Cerrar
        steps.append({
            'n': 12, 'key': 'cerrar', 'icon': 'fas fa-lock', 'titulo': 'Cerrar período',
            'descripcion': 'Período inmutable — congelado para auditoría'
                           if periodo.estado == 'CERRADO'
                           else 'Pendiente — cerrar cuando todo esté OK',
            'done': periodo.estado == 'CERRADO',
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'phase': 'exportar', 'origen': 'Evidencia completa',
            'resultado': 'Período congelado para auditoría y reportes',
            'cta': 'Cerrar período',
        })

        # ── Dependencias: marcar como BLOQUEADO lo que aún no se puede hacer ──
        # (un paso bloqueado espera a que se complete uno anterior). Así el
        # usuario ve UN solo paso para ejecutar y no 7 pasos "en curso" a la vez.
        generado = periodo.estado in ('CALCULADO', 'APROBADO', 'CERRADO') and n_registros > 0
        aprobado = periodo.estado in ('APROBADO', 'CERRADO')
        _bloqueo = {
            'aprobar':  not generado,   # primero hay que generar la planilla
            'boletas':  not aprobado,   # emitir requiere planilla aprobada
            'acuses':   not aprobado,
            'plame':    not aprobado,
            'afpnet':   not aprobado,
            'banco':    not aprobado,
            'contable': not aprobado,
            'cerrar':   not aprobado,   # cerrar requiere todo aprobado
        }
        for s in steps:
            if not s.get('done') and _bloqueo.get(s['key']):
                s['bloqueado'] = True
    else:
        # Sin período, los demás steps están bloqueados
        for n, key, phase, icon, titulo, descr, cta in [
            (4,  'generar',  'calcular', 'fas fa-calculator',     'Generar planilla',  'Primero crea el período', 'Calcular'),
            (5,  'aprobar',  'validar',  'fas fa-check-circle',   'Aprobar planilla',  'Primero calcula el período', 'Revisar'),
            (6,  'boletas',  'entregar', 'fas fa-paper-plane',    'Emitir boletas',    'Disponible luego de aprobar', 'Emitir'),
            (7,  'acuses',   'entregar', 'fas fa-signature',      'Acuses de recibo',  'Disponible luego de emitir', 'Ver acuses'),
            (8,  'plame',    'exportar', 'fas fa-file-export',    'Exportar PLAME',    'Disponible luego de aprobar', 'PLAME'),
            (9,  'afpnet',   'exportar', 'fas fa-piggy-bank',     'Exportar AFPNet',   'Disponible luego de aprobar', 'AFPNet'),
            (10, 'banco',    'exportar', 'fas fa-university',     'Pago a banco',      'Disponible luego de aprobar', 'Banco'),
            (11, 'contable', 'exportar', 'fas fa-file-invoice',   'Asiento contable',  'Disponible luego de aprobar', 'Contabilidad'),
            (12, 'cerrar',   'exportar', 'fas fa-lock',           'Cerrar período',    'Disponible al completar exportaciones', 'Cerrar'),
        ]:
            steps.append({
                'n': n, 'key': key, 'icon': icon, 'titulo': titulo,
                'descripcion': descr, 'done': False, 'link': None, 'bloqueado': True,
                'phase': phase, 'origen': 'Pendiente',
                'resultado': 'Se habilita al completar lo anterior',
                'cta': cta,
            })

    for step in steps:
        step['status'] = _status_from_step(step)

    return steps


def _construir_grupos(steps):
    phases = [
        {
            'key': 'preparar', 'n': '01', 'titulo': 'Preparar datos',
            'descripcion': 'Asistencia, conceptos y período quedan listos antes del cálculo.',
            'icon': 'fas fa-tasks',
        },
        {
            'key': 'calcular', 'n': '02', 'titulo': 'Calcular',
            'descripcion': 'El motor toma los datos preparados y genera boletas.',
            'icon': 'fas fa-calculator',
        },
        {
            'key': 'validar', 'n': '03', 'titulo': 'Validar',
            'descripcion': 'Se revisan variaciones antes de aprobar.',
            'icon': 'fas fa-shield-alt',
        },
        {
            'key': 'entregar', 'n': '04', 'titulo': 'Entregar',
            'descripcion': 'Boletas y acuses quedan disponibles en el portal.',
            'icon': 'fas fa-paper-plane',
        },
        {
            'key': 'exportar', 'n': '05', 'titulo': 'Exportar y cerrar',
            'descripcion': 'SUNAT, AFPNet, banco y contabilidad salen del mismo cierre.',
            'icon': 'fas fa-file-export',
        },
    ]

    for phase in phases:
        phase_steps = [s for s in steps if s.get('phase') == phase['key']]
        done = sum(1 for s in phase_steps if s.get('done'))
        total = len(phase_steps)
        pending = [s for s in phase_steps if not s.get('done')]
        phase['steps'] = phase_steps
        phase['done'] = done
        phase['total'] = total
        phase['progress'] = round(done / total * 100) if total else 0
        if total and done == total:
            phase['status'] = 'done'
        elif any(s.get('actual') for s in phase_steps):
            phase['status'] = 'current'
        elif any(s.get('post_close_attention') for s in phase_steps):
            phase['status'] = 'warning'
        elif pending and all(s.get('bloqueado') for s in pending):
            phase['status'] = 'locked'
        else:
            phase['status'] = 'pending'
    return phases


def _resumen_cierre(periodo, next_step, pendientes_post_cierre, mes, anio):
    if not periodo:
        return {
            'tono': 'warning',
            'titulo': f'Sin período regular {mes:02d}/{anio}',
            'detalle': (
                'Crea el período para que asistencia, conceptos y cálculo '
                'trabajen sobre el mismo cierre.'
            ),
            'label': 'Crear período',
            'url': _periodo_create_url(mes, anio),
            'icon': 'fas fa-calendar-plus',
        }
    if periodo.estado == 'CERRADO':
        if pendientes_post_cierre:
            return {
                'tono': 'warning',
                'titulo': 'Cierre congelado con señales por revisar',
                'detalle': (
                    f'{len(pendientes_post_cierre)} señal(es) no coinciden '
                    'con el cierre. Revisa el período antes de copiar '
                    'procesos manuales.'
                ),
                'label': 'Auditar cierre',
                'url': reverse('nominas_periodo_detalle', args=[periodo.pk]),
                'icon': 'fas fa-search',
            }
        return {
            'tono': 'done',
            'titulo': 'Cierre completo',
            'detalle': 'Período cerrado, datos congelados y salidas listas para consulta.',
            'label': 'Ver período',
            'url': reverse('nominas_periodo_detalle', args=[periodo.pk]),
            'icon': 'fas fa-lock',
        }
    if next_step:
        return {
            'tono': 'current',
            'titulo': next_step['titulo'],
            'detalle': next_step['descripcion'],
            'label': next_step.get('cta') or 'Continuar',
            'url': next_step.get('link'),
            'icon': next_step.get('icon') or 'fas fa-arrow-right',
        }
    return {
        'tono': 'done',
        'titulo': 'Listo para cerrar',
        'detalle': 'No quedan pasos abiertos en el cierre operativo.',
        'label': 'Ver período',
        'url': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        'icon': 'fas fa-check-circle',
    }


@login_required
@solo_admin
def workflow_mes(request):
    """Pantalla guiada del cierre del mes."""
    hoy = timezone.localdate()
    mes, anio = _parse_periodo_request(request, hoy)
    periodos = _periodos_regulares(request)
    periodo = periodos.filter(anio=anio, mes=mes).order_by('-pk').first()

    # Sin parametros, si el mes actual no existe, mostrar el cierre mas reciente.
    has_period_query = 'mes' in request.GET or 'anio' in request.GET
    if not periodo and not has_period_query:
        periodo = periodos.order_by('-anio', '-mes', '-pk').first()
        if periodo:
            mes, anio = periodo.mes, periodo.anio

    steps = _construir_steps(periodo, anio, mes, request)
    # El "siguiente" paso = primero no hecho y no bloqueado.
    pendientes_post_cierre = []
    if periodo and periodo.estado == 'CERRADO':
        pendientes_post_cierre = [
            s for s in steps
            if not s.get('done') and not s.get('bloqueado')
        ]
        for s in pendientes_post_cierre:
            s['post_close_attention'] = True
    else:
        for s in steps:
            if not s.get('done') and not s.get('bloqueado'):
                s['actual'] = True
                break
    for step in steps:
        step['status'] = _status_from_step(step)

    next_step = next((s for s in steps if s.get('actual')), None)
    phase_groups = _construir_grupos(steps)
    n_done = sum(1 for s in steps if s.get('done'))
    # round (no int) para coincidir con el Math.round del JS (evita 16% vs 17%)
    progreso_pct = round(n_done / len(steps) * 100) if steps else 0
    resumen_cierre = _resumen_cierre(
        periodo, next_step, pendientes_post_cierre, mes, anio)
    query = _periodo_query(mes, anio)

    return render(request, 'nominas/workflow_mes.html', {
        'hoy':           hoy,
        'periodo':       periodo,
        'steps':         steps,
        'phase_groups':  phase_groups,
        'next_step':     next_step,
        'resumen_cierre': resumen_cierre,
        'pendientes_post_cierre': pendientes_post_cierre,
        'n_done':        n_done,
        'n_total':       len(steps),
        'progreso_pct':  progreso_pct,
        'mes':           mes,
        'anio':          anio,
        'mes_nombre':    dict(MESES).get(mes, ''),
        'meses':         MESES,
        'anios':         range(hoy.year - 2, hoy.year + 2),
        'periodo_query': query,
    })
