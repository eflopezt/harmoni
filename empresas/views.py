"""Empresas — Vistas: CRUD de empresas y selección de empresa activa."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .models import Empresa

solo_admin = user_passes_test(lambda u: u.is_superuser)


@login_required
@solo_admin
def empresas_panel(request):
    """Lista de empresas."""
    empresas = Empresa.objects.all()
    return render(request, 'empresas/panel.html', {
        'titulo': 'Empresas',
        'empresas': empresas,
    })


@login_required
@solo_admin
def empresa_crear(request):
    """Crear nueva empresa."""
    if request.method == 'POST':
        ruc          = request.POST.get('ruc', '').strip()
        razon_social = request.POST.get('razon_social', '').strip()
        nombre_comercial = request.POST.get('nombre_comercial', '').strip()
        es_principal = request.POST.get('es_principal') == '1'

        if not ruc or not razon_social:
            messages.error(request, 'RUC y Razón Social son requeridos.')
            return redirect('empresa_crear')

        if Empresa.objects.filter(ruc=ruc).exists():
            messages.error(request, f'Ya existe una empresa con RUC {ruc}.')
            return redirect('empresa_crear')

        emp = Empresa.objects.create(
            ruc=ruc,
            razon_social=razon_social,
            nombre_comercial=nombre_comercial,
            es_principal=es_principal,
            creado_por=request.user,
        )
        messages.success(request, f'Empresa "{emp}" creada exitosamente.')
        return redirect('empresas_panel')

    return render(request, 'empresas/form.html', {
        'titulo': 'Nueva Empresa',
        'action': 'crear',
        'regimen_choices': Empresa.REGIMEN_CHOICES,
    })


@login_required
@solo_admin
def empresa_editar(request, pk):
    """Editar empresa existente."""
    empresa = get_object_or_404(Empresa, pk=pk)

    if request.method == 'POST':
        empresa.razon_social     = request.POST.get('razon_social', empresa.razon_social).strip()
        empresa.nombre_comercial = request.POST.get('nombre_comercial', '').strip()
        empresa.ruc              = request.POST.get('ruc', empresa.ruc).strip()
        empresa.direccion        = request.POST.get('direccion', '').strip()
        empresa.telefono         = request.POST.get('telefono', '').strip()
        empresa.email_rrhh       = request.POST.get('email_rrhh', '').strip()
        empresa.regimen_laboral  = request.POST.get('regimen_laboral', 'GENERAL')
        empresa.es_principal     = request.POST.get('es_principal') == '1'
        empresa.activa           = request.POST.get('activa') == '1'
        empresa.save()
        messages.success(request, f'Empresa "{empresa}" actualizada.')
        return redirect('empresas_panel')

    return render(request, 'empresas/form.html', {
        'titulo': f'Editar — {empresa.nombre_display}',
        'empresa': empresa,
        'action': 'editar',
        'regimen_choices': Empresa.REGIMEN_CHOICES,
    })


@login_required
@require_POST
def seleccionar_empresa(request):
    """
    Cambia la empresa activa en la sesión.
    Cualquier usuario autenticado puede cambiar su empresa activa.
    """
    empresa_id = request.POST.get('empresa_id')
    next_url   = request.POST.get('next', '/')
    # Prevent open redirect — only allow internal URLs
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = '/'

    if empresa_id:
        try:
            emp = Empresa.objects.get(pk=empresa_id, activa=True)
            request.session['empresa_actual_id']     = emp.pk
            request.session['empresa_actual_nombre'] = emp.nombre_display
            messages.success(request, f'Empresa activa: {emp.nombre_display}')
        except Empresa.DoesNotExist:
            messages.error(request, 'Empresa no encontrada.')
    else:
        # Limpiar selección (vuelve a la empresa principal)
        request.session.pop('empresa_actual_id', None)
        request.session.pop('empresa_actual_nombre', None)
        messages.info(request, 'Empresa activa restablecida.')

    return redirect(next_url)


@login_required
@solo_admin
def configuracion_empresa(request, pk):
    """Configurar identidad visual de la empresa: logo, membrete, firma."""
    empresa = get_object_or_404(Empresa, pk=pk)

    if request.method == 'POST':
        # Campos de texto
        empresa.representante_legal = request.POST.get('representante_legal', '').strip()
        empresa.cargo_representante = request.POST.get('cargo_representante', '').strip()

        # Corte de planilla
        try:
            dia_ini = int(request.POST.get('dia_inicio_corte', 22))
            if 1 <= dia_ini <= 28:
                empresa.dia_inicio_corte = dia_ini
        except (ValueError, TypeError):
            pass
        try:
            dia_fin = int(request.POST.get('dia_fin_corte', 21))
            if 1 <= dia_fin <= 28:
                empresa.dia_fin_corte = dia_fin
        except (ValueError, TypeError):
            pass

        # Archivos de imagen
        if 'logo' in request.FILES:
            empresa.logo = request.FILES['logo']
        if 'membrete_header' in request.FILES:
            empresa.membrete_header = request.FILES['membrete_header']
        if 'firma_representante' in request.FILES:
            empresa.firma_representante = request.FILES['firma_representante']

        # Permitir borrar imágenes
        if request.POST.get('borrar_logo') == '1':
            empresa.logo = ''
        if request.POST.get('borrar_membrete') == '1':
            empresa.membrete_header = ''
        if request.POST.get('borrar_firma') == '1':
            empresa.firma_representante = ''

        empresa.save()
        messages.success(request, 'Configuración de empresa actualizada correctamente.')
        return redirect('configuracion_empresa', pk=empresa.pk)

    return render(request, 'empresas/configuracion.html', {
        'titulo': f'Configuración — {empresa.nombre_display}',
        'empresa': empresa,
    })


# ──────────────────────────────────────────────────────────────────
#  Pulse del Grupo — Dashboard multi-local para grupo corporativo
# ──────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def pulse_del_grupo(request):
    """Dashboard ejecutivo: vista unificada de todas las empresas/locales.

    Para grupos corporativos con múltiples RUCs (gastronomía, retail, etc).
    Muestra cada empresa como tarjeta con KPIs operacionales + estado:
    - Headcount activo
    - Asistencia hoy (presentes / faltas / sin marcar)
    - Planilla del último período (neto + costo empresa)
    - Alertas (contratos por vencer, HE excedida, etc.)
    - Código de color: verde/amarillo/rojo según salud operativa

    El "cockpit de Isabel" — la pantalla que el dueño abre con su café.
    """
    from datetime import date, timedelta
    from django.db.models import Count, Q, Sum
    from personal.models import Personal
    from nominas.models import PeriodoNomina
    from empresas.models import Empresa

    hoy = date.today()
    en_30_dias = hoy + timedelta(days=30)

    empresas_qs = Empresa.objects.filter(activa=True).order_by('razon_social')

    locales = []
    for emp in empresas_qs:
        # Headcount activo
        personal_qs = Personal.objects.filter(empresa=emp, estado='Activo')
        headcount = personal_qs.count()

        # Asistencia hoy (solo si el modulo está activo)
        asistencia_hoy = None
        try:
            from asistencia.models import RegistroTareo
            tareo_qs = RegistroTareo.objects.filter(
                personal__empresa=emp, fecha=hoy,
            )
            agg = tareo_qs.aggregate(
                total=Count('id'),
                presentes=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS'])),
                faltas=Count('id', filter=Q(codigo_dia__in=['FA', 'LSG'])),
                permisos=Count('id', filter=Q(codigo_dia__in=[
                    'V', 'DL', 'DLA', 'DM', 'LCG', 'LF', 'LP', 'LM',
                ])),
            )
            sin_marcar = headcount - (agg['total'] or 0)
            asistencia_hoy = {**agg, 'sin_marcar': max(0, sin_marcar)}
        except Exception:
            pass

        # Último período de planilla (consolidado entre todas las empresas)
        # Usamos el último período REGULAR cerrado/aprobado, agregando por empresa
        ultimo_periodo = PeriodoNomina.objects.filter(
            tipo='REGULAR',
            estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
        ).order_by('-anio', '-mes').first()

        planilla_emp = None
        if ultimo_periodo:
            from nominas.models import RegistroNomina
            reg_qs = RegistroNomina.objects.filter(
                periodo=ultimo_periodo, personal__empresa=emp,
            )
            agg_pl = reg_qs.aggregate(
                trabajadores=Count('id'),
                neto=Sum('neto_a_pagar'),
                costo=Sum('costo_total_empresa'),
            )
            if agg_pl['trabajadores']:
                planilla_emp = {
                    'periodo': f'{ultimo_periodo.mes_nombre} {ultimo_periodo.anio}',
                    'trabajadores': agg_pl['trabajadores'],
                    'neto':         agg_pl['neto']  or 0,
                    'costo':        agg_pl['costo'] or 0,
                }

        # Alertas
        alertas = []
        # Contratos por vencer (30 días)
        contratos_vencen = personal_qs.filter(
            fecha_fin_contrato__isnull=False,
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=en_30_dias,
        ).count()
        if contratos_vencen:
            alertas.append({
                'tipo':    'warning',
                'icono':   'fa-file-contract',
                'texto':   f'{contratos_vencen} contrato(s) por vencer en 30 días',
                'count':   contratos_vencen,
            })

        # Sin saldos de apertura cargados → bandera amarilla
        try:
            from nominas.models import SaldoAperturaTrabajador
            personal_con_saldo = SaldoAperturaTrabajador.objects.filter(
                personal__empresa=emp,
            ).count()
            sin_saldo = headcount - personal_con_saldo
            if headcount and sin_saldo > headcount * 0.5:
                alertas.append({
                    'tipo':  'info',
                    'icono': 'fa-rocket',
                    'texto': f'Saldos de apertura pendientes ({sin_saldo} trab.)',
                    'count': sin_saldo,
                })
        except Exception:
            pass

        # Determinar color de salud
        if asistencia_hoy and asistencia_hoy.get('faltas', 0) > headcount * 0.15:
            color = 'rojo'
        elif alertas or (asistencia_hoy and asistencia_hoy.get('sin_marcar', 0) > headcount * 0.3):
            color = 'amarillo'
        else:
            color = 'verde'

        locales.append({
            'empresa':        emp,
            'headcount':      headcount,
            'asistencia_hoy': asistencia_hoy,
            'planilla':       planilla_emp,
            'alertas':        alertas,
            'color':          color,
            'contratos_vencen': contratos_vencen,
        })

    # Stats agregadas globales
    total_locales = len(locales)
    total_headcount = sum(l['headcount'] for l in locales)
    total_planilla_neto = sum((l['planilla']['neto'] if l['planilla'] else 0) for l in locales)
    total_planilla_costo = sum((l['planilla']['costo'] if l['planilla'] else 0) for l in locales)
    total_alertas = sum(len(l['alertas']) for l in locales)
    locales_verde = sum(1 for l in locales if l['color'] == 'verde')
    locales_amarillo = sum(1 for l in locales if l['color'] == 'amarillo')
    locales_rojo = sum(1 for l in locales if l['color'] == 'rojo')

    return render(request, 'empresas/pulse_grupo.html', {
        'locales':              locales,
        'total_locales':        total_locales,
        'total_headcount':      total_headcount,
        'total_planilla_neto':  total_planilla_neto,
        'total_planilla_costo': total_planilla_costo,
        'total_alertas':        total_alertas,
        'locales_verde':        locales_verde,
        'locales_amarillo':     locales_amarillo,
        'locales_rojo':         locales_rojo,
        'hoy':                  hoy,
    })


@login_required
@solo_admin
def pulse_local_detalle(request, pk):
    """Drill-down de un local específico desde el Pulse del Grupo.

    Muestra detalle completo del local: trabajadores, briefings hoy,
    asistencia hoy, alertas, último período planilla.
    """
    from datetime import date, timedelta
    from django.db.models import Count, Q, Sum
    from personal.models import Personal
    from nominas.models import PeriodoNomina, RegistroNomina
    from empresas.models import Empresa

    emp = get_object_or_404(Empresa, pk=pk)
    hoy = date.today()
    en_30_dias = hoy + timedelta(days=30)

    # Trabajadores activos del local
    personal_qs = Personal.objects.filter(empresa=emp, estado='Activo').order_by('apellidos_nombres')
    headcount = personal_qs.count()

    # Distribución por grupo
    grupos = list(
        personal_qs.values('grupo_tareo')
        .annotate(n=Count('id'))
        .order_by('-n')
    )

    # Asistencia hoy
    asistencia_hoy = None
    try:
        from asistencia.models import RegistroTareo
        tareo_qs = RegistroTareo.objects.filter(personal__empresa=emp, fecha=hoy)
        agg = tareo_qs.aggregate(
            total=Count('id'),
            presentes=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS'])),
            faltas=Count('id', filter=Q(codigo_dia__in=['FA', 'LSG'])),
            permisos=Count('id', filter=Q(codigo_dia__in=['V', 'DL', 'DLA', 'DM', 'LCG', 'LF', 'LP', 'LM'])),
        )
        asistencia_hoy = {**agg, 'sin_marcar': max(0, headcount - (agg['total'] or 0))}
    except Exception:
        pass

    # Briefings de hoy/mañana
    briefings = []
    try:
        from asistencia.models import BriefingServicio
        briefings = list(
            BriefingServicio.objects
            .filter(empresa=emp, fecha__gte=hoy, fecha__lte=hoy + timedelta(days=2))
            .order_by('fecha', 'servicio')
        )
    except Exception:
        pass

    # Último período planilla
    ultimo_periodo = PeriodoNomina.objects.filter(
        tipo='REGULAR',
        estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
    ).order_by('-anio', '-mes').first()

    planilla_emp = None
    if ultimo_periodo:
        reg_qs = RegistroNomina.objects.filter(periodo=ultimo_periodo, personal__empresa=emp)
        agg_pl = reg_qs.aggregate(
            trabajadores=Count('id'),
            bruto=Sum('total_ingresos'),
            descuentos=Sum('total_descuentos'),
            neto=Sum('neto_a_pagar'),
            costo=Sum('costo_total_empresa'),
        )
        if agg_pl['trabajadores']:
            planilla_emp = {
                'periodo':      f'{ultimo_periodo.mes_nombre} {ultimo_periodo.anio}',
                'periodo_pk':   ultimo_periodo.pk,
                'trabajadores': agg_pl['trabajadores'],
                'bruto':        agg_pl['bruto']      or 0,
                'descuentos':   agg_pl['descuentos'] or 0,
                'neto':         agg_pl['neto']       or 0,
                'costo':        agg_pl['costo']      or 0,
            }

    # Contratos por vencer
    contratos_vencen = personal_qs.filter(
        fecha_fin_contrato__isnull=False,
        fecha_fin_contrato__gte=hoy,
        fecha_fin_contrato__lte=en_30_dias,
    ).order_by('fecha_fin_contrato')[:10]

    # Saldos apertura del local
    saldos_apertura_count = 0
    try:
        from nominas.models import SaldoAperturaTrabajador
        saldos_apertura_count = SaldoAperturaTrabajador.objects.filter(
            personal__empresa=emp,
        ).count()
    except Exception:
        pass

    return render(request, 'empresas/pulse_local_detalle.html', {
        'empresa':              emp,
        'headcount':            headcount,
        'grupos':               grupos,
        'asistencia_hoy':       asistencia_hoy,
        'briefings':            briefings,
        'planilla_emp':         planilla_emp,
        'ultimo_periodo':       ultimo_periodo,
        'contratos_vencen':     contratos_vencen,
        'saldos_apertura_count': saldos_apertura_count,
        'workers_sample':       personal_qs[:20],
        'hoy':                  hoy,
    })
