"""
Workflow del Mes — checklist guiado para cerrar el mes en planilla.

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
10. Exportar asiento contable
11. Cerrar período

Cada step tiene un `key` estable (str) — el frontend puede ocultarlos
vía localStorage (`workflow_mes_hidden_steps`) para personalizar el
checklist por usuario sin migrar BD.

URL: /nominas/workflow-mes/
"""
from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone


solo_admin = user_passes_test(lambda u: u.is_superuser)


def _construir_steps(periodo, hoy):
    """Construye la lista de steps con estado calculado."""
    from .models import RegistroNomina

    steps = []

    # Step 1: Asistencia del mes
    asis_done = False
    asis_link = '/asistencia/'
    asis_msg = 'Importa o consolida la asistencia de los trabajadores'
    try:
        from asistencia.models import RegistroAsistencia
        count = RegistroAsistencia.objects.filter(
            fecha__year=hoy.year,
            fecha__month=hoy.month,
        ).count()
        if count > 0:
            asis_done = True
            asis_msg = f'{count} registros del mes cargados'
    except Exception:
        pass
    steps.append({
        'n': 1, 'key': 'asistencia', 'icon': 'fas fa-clock', 'titulo': 'Asistencia del mes',
        'descripcion': asis_msg, 'done': asis_done, 'link': asis_link,
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
    })

    # Step 3: Crear/abrir período
    if periodo:
        steps.append({
            'n': 3, 'key': 'periodo', 'icon': 'fas fa-calendar-plus', 'titulo': 'Período abierto',
            'descripcion': f'Período {periodo.mes:02d}/{periodo.anio} ({periodo.get_estado_display()})',
            'done': True, 'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
    else:
        steps.append({
            'n': 3, 'key': 'periodo', 'icon': 'fas fa-calendar-plus', 'titulo': 'Crear período del mes',
            'descripcion': f'Crea el período REGULAR de {hoy.month:02d}/{hoy.year}',
            'done': False, 'link': reverse('nominas_periodo_crear'),
        })

    # Step 4-10 dependen del periodo
    if periodo:
        n_registros = RegistroNomina.objects.filter(periodo=periodo).count()
        # Step 4: Generar
        steps.append({
            'n': 4, 'key': 'generar', 'icon': 'fas fa-calculator', 'titulo': 'Generar planilla',
            'descripcion': f'{n_registros} boletas calculadas'
                           if periodo.estado in ('CALCULADO', 'APROBADO', 'CERRADO')
                           else 'Pendiente — ejecuta cálculo',
            'done': periodo.estado in ('CALCULADO', 'APROBADO', 'CERRADO'),
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 5: Aprobar
        steps.append({
            'n': 5, 'key': 'aprobar', 'icon': 'fas fa-check-circle', 'titulo': 'Aprobar planilla',
            'descripcion': 'Período aprobado — listo para emitir'
                           if periodo.estado in ('APROBADO', 'CERRADO')
                           else 'Pendiente — revisar y aprobar',
            'done': periodo.estado in ('APROBADO', 'CERRADO'),
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 6: Emitir boletas
        steps.append({
            'n': 6, 'key': 'boletas', 'icon': 'fas fa-paper-plane', 'titulo': 'Emitir boletas',
            'descripcion': 'Notifica a trabajadores que tienen boleta lista',
            'done': periodo.estado in ('APROBADO', 'CERRADO'),
            'link': reverse('nominas_emision_boletas'),
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
            'descripcion': f'{firmados}/{acuses_count} firmados ({pct_firmado}%)',
            'done': acuses_count > 0 and pct_firmado >= 80,
            'link': reverse('nominas_emision_boletas'),
        })
        # Step 8: Exportar PLAME
        steps.append({
            'n': 8, 'key': 'plame', 'icon': 'fas fa-file-export', 'titulo': 'Exportar PLAME',
            'descripcion': 'Genera archivo plano para SUNAT (T-Registro/PDT 601)',
            'done': periodo.estado == 'CERRADO',  # no tenemos flag específico
            'link': reverse('nominas_periodo_plame', args=[periodo.pk])
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 9: Exportar AFPNet (Habitat / Integra / Prima / Profuturo)
        steps.append({
            'n': 9, 'key': 'afpnet', 'icon': 'fas fa-piggy-bank', 'titulo': 'Exportar AFPNet',
            'descripcion': 'Archivo plano para AFP Habitat, Integra, Prima y Profuturo (formato SBS)'
                           if periodo.estado in ('APROBADO', 'CERRADO')
                           else 'Disponible cuando la planilla esté aprobada',
            'done': periodo.estado == 'CERRADO',
            'link': reverse('integ_afp_net_panel')
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 10: Pago a banco (archivo de transferencias por el NETO)
        steps.append({
            'n': 10, 'key': 'banco', 'icon': 'fas fa-university', 'titulo': 'Pago a banco',
            'descripcion': 'Genera el archivo de transferencias (neto) para el banco'
                           if periodo.estado in ('APROBADO', 'CERRADO')
                           else 'Disponible cuando la planilla esté aprobada',
            'done': periodo.estado == 'CERRADO',
            'link': reverse('nominas_periodo_archivo_banco', args=[periodo.pk])
                    if periodo.estado in ('APROBADO', 'CERRADO')
                    else reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 11: Asiento contable
        steps.append({
            'n': 11, 'key': 'contable', 'icon': 'fas fa-file-invoice', 'titulo': 'Asiento contable',
            'descripcion': 'Exportado a CONCAR/Siscont/SAP'
                           if getattr(periodo, 'contabilizado', False)
                           else 'Pendiente — exporta para tu contador',
            'done': getattr(periodo, 'contabilizado', False),
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
        # Step 12: Cerrar
        steps.append({
            'n': 12, 'key': 'cerrar', 'icon': 'fas fa-lock', 'titulo': 'Cerrar período',
            'descripcion': 'Período inmutable — congelado para auditoría'
                           if periodo.estado == 'CERRADO'
                           else 'Pendiente — cerrar cuando todo esté OK',
            'done': periodo.estado == 'CERRADO',
            'link': reverse('nominas_periodo_detalle', args=[periodo.pk]),
        })
    else:
        # Sin período, los demás steps están bloqueados
        for n, key, icon, titulo, descr in [
            (4,  'generar',  'fas fa-calculator',     'Generar planilla',  'Espera al paso 3'),
            (5,  'aprobar',  'fas fa-check-circle',   'Aprobar planilla',  'Espera al paso 3'),
            (6,  'boletas',  'fas fa-paper-plane',    'Emitir boletas',    'Espera al paso 3'),
            (7,  'acuses',   'fas fa-signature',      'Acuses de recibo',  'Espera al paso 3'),
            (8,  'plame',    'fas fa-file-export',    'Exportar PLAME',    'Espera al paso 3'),
            (9,  'afpnet',   'fas fa-piggy-bank',     'Exportar AFPNet',   'Espera al paso 3'),
            (10, 'banco',    'fas fa-university',     'Pago a banco',      'Espera al paso 3'),
            (11, 'contable', 'fas fa-file-invoice',   'Asiento contable',  'Espera al paso 3'),
            (12, 'cerrar',   'fas fa-lock',           'Cerrar período',    'Espera al paso 3'),
        ]:
            steps.append({
                'n': n, 'key': key, 'icon': icon, 'titulo': titulo,
                'descripcion': descr, 'done': False, 'link': None, 'bloqueado': True,
            })

    return steps


@login_required
@solo_admin
def workflow_mes(request):
    """Pantalla guiada del cierre del mes."""
    from .models import PeriodoNomina

    hoy = timezone.localdate()
    periodo = PeriodoNomina.objects.filter(
        tipo='REGULAR', anio=hoy.year, mes=hoy.month,
    ).first()
    # Si no hay del mes actual, mostrar el más reciente
    if not periodo:
        periodo = PeriodoNomina.objects.filter(tipo='REGULAR').order_by('-anio', '-mes').first()

    steps = _construir_steps(periodo, hoy)
    n_done = sum(1 for s in steps if s.get('done'))
    # round (no int) para coincidir con el Math.round del JS (evita 16% vs 17%)
    progreso_pct = round(n_done / len(steps) * 100) if steps else 0

    return render(request, 'nominas/workflow_mes.html', {
        'hoy':           hoy,
        'periodo':       periodo,
        'steps':         steps,
        'n_done':        n_done,
        'n_total':       len(steps),
        'progreso_pct':  progreso_pct,
    })
