"""
Portal de autoservicio del colaborador.
Cada usuario ve y gestiona solo su propia información.
"""
import calendar
from datetime import date

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from asistencia.models import BancoHoras, JustificacionNoMarcaje, RegistroPapeleta, RegistroTareo, SolicitudHE
from personal.models import Roster, Personal, Area, SubArea


def _get_empleado(user):
    """Retorna el Personal vinculado al usuario, o None."""
    emp = getattr(user, 'personal_data', None)
    if emp is not None:
        # Ensure subarea/area are pre-loaded to avoid N+1 in templates
        from django.db.models import prefetch_related_objects
        try:
            prefetch_related_objects([emp], 'subarea__area')
        except Exception:
            pass
    return emp


def _safe_int(value, default):
    """Convierte value a int de forma segura, retornando default si falla."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


@login_required
def portal_home(request):
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        from django.db.models import Sum

        hoy = date.today()
        inicio_mes = hoy.replace(day=1)

        registros_mes = RegistroTareo.objects.filter(
            personal=empleado,
            fecha__gte=inicio_mes,
            fecha__lte=hoy,
        ).select_related('personal').order_by('-fecha')

        banco = BancoHoras.objects.filter(
            personal=empleado,
        ).select_related('personal').order_by('-periodo_anio', '-periodo_mes').first()

        roster_hoy = Roster.objects.filter(
            personal=empleado,
            fecha=hoy,
        ).select_related('personal').first()

        # ── Solicitudes pendientes del trabajador ──
        pap_pendientes = RegistroPapeleta.objects.filter(
            personal=empleado, estado='PENDIENTE',
        ).count()
        sol_pendientes = SolicitudHE.objects.filter(
            personal=empleado, estado='PENDIENTE',
        ).count()
        just_pendientes = JustificacionNoMarcaje.objects.filter(
            personal=empleado, estado='PENDIENTE',
        ).count()

        # ── Papeletas próximas (aprobadas, futuras) ──
        papeletas_prox = RegistroPapeleta.objects.filter(
            personal=empleado,
            estado='APROBADA',
            fecha_inicio__gte=hoy,
        ).order_by('fecha_inicio')[:3]

        # ── HE acumuladas este mes ──
        he_mes = registros_mes.aggregate(
            he25=Sum('he_25'), he35=Sum('he_35'), he100=Sum('he_100'),
        )
        he_total_mes = (he_mes['he25'] or 0) + (he_mes['he35'] or 0) + (he_mes['he100'] or 0)

        # ── Saldo vacacional disponible ──────────────────────────
        dias_vac_disponibles = None
        vac_proxima = None
        try:
            from vacaciones.models import SaldoVacacional, SolicitudVacacion
            from django.db.models import Sum as _Sum
            saldo_vac = SaldoVacacional.objects.filter(
                personal=empleado,
                estado__in=['PENDIENTE', 'PARCIAL'],
            ).aggregate(total=_Sum('dias_pendientes'))
            dias_vac_disponibles = float(saldo_vac['total'] or 0)

            vac_proxima = SolicitudVacacion.objects.filter(
                personal=empleado,
                estado='APROBADA',
                fecha_inicio__gte=hoy,
            ).order_by('fecha_inicio').first()
        except Exception:
            pass

        # ── Capacitaciones próximas ────────────────────────────
        caps_proximas = []
        try:
            from capacitaciones.models import AsistenciaCapacitacion
            caps_proximas = list(
                AsistenciaCapacitacion.objects.select_related('capacitacion')
                .filter(
                    personal=empleado,
                    capacitacion__estado='PROGRAMADA',
                    capacitacion__fecha_inicio__gte=hoy,
                )
                .order_by('capacitacion__fecha_inicio')[:3]
            )
        except Exception:
            pass

        # ── Último recibo calculado ────────────────────────────
        ultimo_recibo = None
        try:
            from nominas.models import RegistroNomina
            ultimo_recibo = (
                RegistroNomina.objects
                .filter(personal=empleado)
                .select_related('periodo')
                .order_by('-periodo__anio', '-periodo__mes')
                .first()
            )
        except Exception:
            pass

        # ── Préstamo activo (en curso con cuotas pendientes) ──
        prestamo_activo = None
        try:
            from prestamos.models import Prestamo
            prestamo_activo = (
                Prestamo.objects
                .filter(personal=empleado, estado='EN_CURSO')
                .order_by('-fecha_aprobacion')
                .first()
            )
        except Exception:
            pass

        # ── Notificaciones recientes no leídas ────────────────
        notif_recientes = []
        try:
            from comunicaciones.models import Notificacion
            notif_recientes = list(
                Notificacion.objects.filter(
                    destinatario=request.user,
                    leida=False,
                ).order_by('-creado_en')[:4]
            )
        except Exception:
            pass

        # ── Antigüedad ────────────────────────────────────────
        antiguedad = None
        if empleado.fecha_alta:
            delta = hoy - empleado.fecha_alta
            antiguedad = {
                'anios': delta.days // 365,
                'meses': (delta.days % 365) // 30,
            }

        # ── Propio aniversario este mes ───────────────────────
        es_mi_aniversario = False
        mi_aniversario_anios = None
        if empleado.fecha_alta and empleado.fecha_alta.month == hoy.month and empleado.fecha_alta.year != hoy.year:
            es_mi_aniversario = True
            mi_aniversario_anios = hoy.year - empleado.fecha_alta.year

        # ── Propio cumpleaños este mes ────────────────────────
        es_mi_cumple = False
        mi_cumple_edad = None
        if empleado.fecha_nacimiento and empleado.fecha_nacimiento.month == hoy.month:
            es_mi_cumple = True
            mi_cumple_edad = hoy.year - empleado.fecha_nacimiento.year

        # ── Cumpleaños compañeros del área (mismo mes) ────────
        companeros_cumple = []
        try:
            area_filtro = {}
            if empleado.subarea:
                area_filtro['subarea__area'] = empleado.subarea.area
            elif empleado.subarea:
                area_filtro['subarea'] = empleado.subarea
            if area_filtro:
                companeros_qs = Personal.objects.filter(
                    **area_filtro,
                    estado='Activo',
                    fecha_nacimiento__isnull=False,
                    fecha_nacimiento__month=hoy.month,
                ).exclude(pk=empleado.pk).order_by('fecha_nacimiento__day')[:6]
                for c in companeros_qs:
                    companeros_cumple.append({
                        'nombre': c.apellidos_nombres,
                        'dia': c.fecha_nacimiento.day,
                        'edad': hoy.year - c.fecha_nacimiento.year,
                        'es_hoy': (c.fecha_nacimiento.day == hoy.day),
                        'cargo': c.cargo or '',
                    })
        except Exception:
            pass

        # ── Pulse Semanal: ¿pendiente esta semana? ────────────
        pulse_pendiente = False
        try:
            from encuestas.views import pulse_pendiente_para
            pulse_pendiente = pulse_pendiente_para(empleado)
        except Exception:
            pass

        # ── Briefing del Día (si hay publicado para el local del trabajador) ──
        briefing_hoy = None
        ya_lei_briefing = False
        try:
            from asistencia.models import BriefingServicio, BriefingLectura
            if empleado.empresa_id:
                briefing_hoy = (
                    BriefingServicio.objects
                    .filter(empresa=empleado.empresa, fecha=hoy, estado='PUBLICADO')
                    .order_by('servicio')
                    .first()
                )
                if briefing_hoy:
                    ya_lei_briefing = BriefingLectura.objects.filter(
                        briefing=briefing_hoy, personal=empleado,
                    ).exists()
        except Exception:
            pass

        context.update({
            'briefing_hoy':    briefing_hoy,
            'ya_lei_briefing': ya_lei_briefing,
            'dias_trabajados_mes': registros_mes.filter(horas_efectivas__gt=0).count(),
            'banco_actual': banco,
            'roster_hoy': roster_hoy,
            'registros_recientes': registros_mes[:5],
            'pap_pendientes': pap_pendientes,
            'sol_pendientes': sol_pendientes,
            'just_pendientes': just_pendientes,
            'total_pendientes': pap_pendientes + sol_pendientes + just_pendientes,
            'papeletas_prox': papeletas_prox,
            'he_total_mes': he_total_mes,
            'dias_vac_disponibles': dias_vac_disponibles,
            'vac_proxima': vac_proxima,
            'caps_proximas': caps_proximas,
            'notif_recientes': notif_recientes,
            'ultimo_recibo': ultimo_recibo,
            'prestamo_activo': prestamo_activo,
            'antiguedad': antiguedad,
            'es_mi_aniversario': es_mi_aniversario,
            'mi_aniversario_anios': mi_aniversario_anios,
            'es_mi_cumple': es_mi_cumple,
            'mi_cumple_edad': mi_cumple_edad,
            'companeros_cumple': companeros_cumple,
            'pulse_pendiente': pulse_pendiente,
        })

    # Portal de beneficios externo (si la empresa lo tiene configurado)
    portal_beneficios = None
    try:
        emp = getattr(personal, 'empresa', None) if personal else None
        if emp and emp.portal_beneficios_url:
            portal_beneficios = {
                'nombre': emp.portal_beneficios_nombre or 'Mis Beneficios',
                'url':    emp.portal_beneficios_url,
                'logo':   emp.portal_beneficios_logo_url or '',
            }
    except Exception:
        pass
    context['portal_beneficios'] = portal_beneficios

    return render(request, 'portal/portal_home.html', context)


@login_required
def mi_perfil(request):
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    # ── POST: actualizar datos de contacto editables ───────────
    if request.method == 'POST' and empleado:
        from django.contrib import messages as _msg
        celular = request.POST.get('celular', '').strip()
        correo_personal = request.POST.get('correo_personal', '').strip()
        update_fields = []
        if celular != empleado.celular:
            empleado.celular = celular[:20]
            update_fields.append('celular')
        if correo_personal != (empleado.correo_personal or ''):
            empleado.correo_personal = correo_personal[:254]
            update_fields.append('correo_personal')
        if update_fields:
            empleado.save(update_fields=update_fields)
            _msg.success(request, 'Datos de contacto actualizados correctamente.')
        from django.shortcuts import redirect
        return redirect('mi_perfil')

    if empleado:
        hoy = date.today()

        # ── Antigüedad ────────────────────────────────────────
        antiguedad = None
        if empleado.fecha_alta:
            delta = hoy - empleado.fecha_alta
            anios = delta.days // 365
            meses = (delta.days % 365) // 30
            dias = (delta.days % 365) % 30
            antiguedad = {'anios': anios, 'meses': meses, 'dias': dias}
        context['antiguedad'] = antiguedad

        # ── Últimas 3 evaluaciones recibidas ─────────────────
        ultimas_evaluaciones = []
        try:
            from evaluaciones.models import Evaluacion
            ultimas_evaluaciones = list(
                Evaluacion.objects.filter(evaluado=empleado)
                .select_related('ciclo')
                .order_by('-ciclo__fecha_inicio', '-creado_en')[:3]
            )
        except Exception:
            pass
        context['ultimas_evaluaciones'] = ultimas_evaluaciones

        # ── Últimas 5 capacitaciones completadas ─────────────
        capacitaciones_completadas = []
        try:
            from capacitaciones.models import AsistenciaCapacitacion
            capacitaciones_completadas = list(
                AsistenciaCapacitacion.objects.filter(
                    personal=empleado,
                    estado__in=['ASISTIO', 'PARCIAL'],
                )
                .select_related('capacitacion', 'capacitacion__categoria')
                .order_by('-capacitacion__fecha_inicio')[:5]
            )
        except Exception:
            pass
        context['capacitaciones_completadas'] = capacitaciones_completadas

        # ── Historial de cambios salariales/cargo (últimos 5) ─
        historial_cargos = []
        try:
            from salarios.models import HistorialSalarial
            historial_cargos = list(
                HistorialSalarial.objects.filter(personal=empleado)
                .order_by('-fecha_efectiva')[:5]
            )
        except Exception:
            pass
        context['historial_cargos'] = historial_cargos

    return render(request, 'portal/mi_perfil.html', context)


@login_required
def mi_asistencia(request):
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        hoy = date.today()
        anio = _safe_int(request.GET.get('anio', hoy.year), hoy.year)
        mes = _safe_int(request.GET.get('mes', hoy.month), hoy.month)

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, calendar.monthrange(anio, mes)[1])

        registros = list(RegistroTareo.objects.filter(
            personal=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).order_by('fecha'))

        # ── Normalizar DL → DS para regímenes NO acumulativos (gastronomía 6×1, oficina 5×2)
        # En gastronomía el día libre semanal rota — NO es Día Libre del Roster Acumulativo.
        try:
            from asistencia.views.reporte_individual import _es_regimen_acumulativo
            if not _es_regimen_acumulativo(empleado):
                for r in registros:
                    if r.codigo_dia in ('DL', 'DLA'):
                        r.codigo_dia = 'DS'
        except Exception:
            pass

        # ── Estadísticas del mes ──────────────────────────────
        dias_trab = sum(1 for r in registros if r.codigo_dia in (
            'T', 'NOR', 'TR', 'A', 'SS', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'
        ))
        dias_falta = sum(1 for r in registros if r.codigo_dia in ('FA', 'F'))
        dias_lsg = sum(1 for r in registros if r.codigo_dia == 'LSG')
        dias_vac = sum(1 for r in registros if r.codigo_dia in ('VAC', 'V'))
        dias_dm = sum(1 for r in registros if r.codigo_dia == 'DM')
        dias_ss = sum(1 for r in registros if r.codigo_dia == 'SS')
        he_25 = sum(r.he_25 or 0 for r in registros)
        he_35 = sum(r.he_35 or 0 for r in registros)
        he_100 = sum(r.he_100 or 0 for r in registros)
        total_he = he_25 + he_35 + he_100
        total_horas_marc = sum(r.horas_marcadas or 0 for r in registros)

        # Días laborables del mes (lun-sab)
        dias_lab_mes = sum(
            1 for d in range(1, fecha_fin.day + 1)
            if date(anio, mes, d).weekday() < 6
        )
        pct_asistencia = round(dias_trab / dias_lab_mes * 100, 1) if dias_lab_mes else 0

        # Promedio de horas por día trabajado
        prom_horas = round(float(total_horas_marc) / dias_trab, 1) if dias_trab else 0

        # Años disponibles para el selector
        primer_registro = RegistroTareo.objects.filter(
            personal=empleado
        ).order_by('fecha').only('fecha').first()
        anio_inicio = primer_registro.fecha.year if primer_registro else hoy.year

        context.update({
            'registros': registros,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'total_he': total_he,
            'he_25': he_25,
            'he_35': he_35,
            'he_100': he_100,
            'dias_trab': dias_trab,
            'dias_falta': dias_falta,
            'dias_lsg': dias_lsg,
            'dias_vac': dias_vac,
            'dias_dm': dias_dm,
            'dias_ss': dias_ss,
            'total_horas_marc': total_horas_marc,
            'prom_horas': prom_horas,
            'dias_lab_mes': dias_lab_mes,
            'pct_asistencia': pct_asistencia,
            'anio_sel': anio,
            'mes_sel': mes,
            'anios': range(anio_inicio, hoy.year + 1),
            'meses': [
                (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
                (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
                (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
            ],
        })

    return render(request, 'portal/mi_asistencia.html', context)


@login_required
def mi_banco_horas(request):
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        # Materialise to list so we only hit the DB once (avoids double-eval
        # when the template iterates and sum() also iterates the queryset).
        registros = list(BancoHoras.objects.filter(
            personal=empleado,
        ).order_by('-periodo_anio', '-periodo_mes'))

        saldo_total = sum(r.saldo_horas or 0 for r in registros)

        context.update({
            'registros': registros,
            'saldo_total': saldo_total,
        })

    return render(request, 'portal/mi_banco_horas.html', context)


@login_required
def mi_roster(request):
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    if empleado:
        hoy = date.today()
        anio = _safe_int(request.GET.get('anio', hoy.year), hoy.year)
        mes = _safe_int(request.GET.get('mes', hoy.month), hoy.month)

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, calendar.monthrange(anio, mes)[1])

        registros = Roster.objects.filter(
            personal=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).order_by('fecha')

        primer_roster = Roster.objects.filter(
            personal=empleado,
        ).order_by('fecha').first()
        anio_inicio = primer_roster.fecha.year if primer_roster else hoy.year

        # --- Calendario mensual visual (semanas x 7 dias) ---
        reg_por_fecha = {r.fecha: r for r in registros}
        # Colores estables por codigo: sirve para cualquier empresa/rubro.
        _PALETA = ['#14b8a6', '#0ea5e9', '#f59e0b', '#a855f7', '#ef4444',
                   '#22c55e', '#ec4899', '#84cc16', '#f97316', '#6366f1']
        _DESCANSO = {'D', 'DL', 'DLA', 'DOL', 'DESC', 'LIBRE', 'OFF', 'L'}
        codigos_distintos = sorted({r.codigo for r in registros if r.codigo})
        color_por_codigo, _pi = {}, 0
        for c in codigos_distintos:
            if c.upper() in _DESCANSO:
                color_por_codigo[c] = '#94a3b8'   # gris = descanso
            else:
                color_por_codigo[c] = _PALETA[_pi % len(_PALETA)]
                _pi += 1

        cal = calendar.Calendar(firstweekday=0)   # 0 = lunes
        semanas = []
        for semana in cal.monthdatescalendar(anio, mes):
            fila = []
            for d in semana:
                r = reg_por_fecha.get(d)
                cod = r.codigo if r else ''
                fila.append({
                    'dia': d.day,
                    'fecha': d,
                    'en_mes': d.month == mes,
                    'es_hoy': d == hoy,
                    'codigo': cod,
                    'color': color_por_codigo.get(cod, ''),
                    'estado': r.estado if r else '',
                    'obs': (r.observaciones if r else '') or '',
                })
            semanas.append(fila)

        leyenda = [{'codigo': c, 'color': color_por_codigo[c]} for c in codigos_distintos]

        context.update({
            'registros': registros,
            'semanas': semanas,
            'leyenda': leyenda,
            'anio_sel': anio,
            'mes_sel': mes,
            'mes_nombre': f"{dict(MESES)[mes]} {anio}",
            'hoy': hoy,
            'anios': range(anio_inicio, hoy.year + 1),
            'meses': MESES,
        })

    return render(request, 'portal/mi_roster.html', context)


@login_required
def organigrama(request):
    """Organigrama jerárquico: Área → SubÁrea → Personas.

    Perf audit fix 2026-05-20: antes el template hacia subarea.personal_asignado.count
    (rompia el prefetch -> 1 COUNT extra por subárea, ~240 queries con 24 RUCs)
    y el prefetch incluía Personal cesado (data inutil).
    Fix: Prefetch tipado con queryset que (1) filtra solo Activos y (2) anota
    activos_count para usar en el template.
    """
    from django.db.models import Count, Prefetch, Q

    subareas_qs = SubArea.objects.annotate(
        activos_count=Count(
            'personal_asignado',
            filter=Q(personal_asignado__estado='Activo'),
        )
    ).prefetch_related(
        Prefetch(
            'personal_asignado',
            queryset=Personal.objects.filter(estado='Activo').only(
                'id', 'apellidos_nombres', 'cargo'
            ),
        )
    )

    areas = (
        Area.objects.filter(activa=True)
        .prefetch_related(
            'responsables',
            Prefetch('subareas', queryset=subareas_qs),
        )
        .order_by('nombre')
    )

    # Personas sin subárea asignada (directas al área o sin área)
    sin_area = Personal.objects.filter(
        estado='Activo', subarea__isnull=True,
    ).only('id', 'apellidos_nombres', 'cargo').order_by('apellidos_nombres')

    total_colaboradores = Personal.objects.filter(estado='Activo').count()

    return render(request, 'portal/organigrama.html', {
        'areas': areas,
        'sin_area': sin_area,
        'total_colaboradores': total_colaboradores,
    })


@login_required
def directorio(request):
    """Directorio de colaboradores con búsqueda."""
    buscar = request.GET.get('q', '').strip()
    area_id = request.GET.get('area', '')

    qs = Personal.objects.filter(estado='Activo').select_related(
        'subarea', 'subarea__area',
    ).order_by('apellidos_nombres')

    if buscar:
        from django.db.models import Q
        qs = qs.filter(
            Q(apellidos_nombres__icontains=buscar) |
            Q(cargo__icontains=buscar) |
            Q(correo_corporativo__icontains=buscar) |
            Q(nro_doc__icontains=buscar)
        )

    if area_id:
        qs = qs.filter(subarea__area_id=area_id)

    areas = Area.objects.filter(activa=True).order_by('nombre')

    # Materialise to list: avoids a separate COUNT query and double evaluation.
    personas = list(qs)

    return render(request, 'portal/directorio.html', {
        'personas': personas,
        'buscar': buscar,
        'area_id': area_id,
        'areas': areas,
        'total': len(personas),
    })


# ──────────────────────────────────────────────────────────────
# Justificaciones de No-Marcaje (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_justificaciones(request):
    """El trabajador ve y crea sus justificaciones de no-marcaje."""
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        hoy = date.today()
        anio = _safe_int(request.GET.get('anio', hoy.year), hoy.year)
        mes = _safe_int(request.GET.get('mes', hoy.month), hoy.month)

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, calendar.monthrange(anio, mes)[1])

        justificaciones = list(JustificacionNoMarcaje.objects.filter(
            personal=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).order_by('-fecha'))

        # Días del mes con registro para mostrar al trabajador
        registros_mes = RegistroTareo.objects.filter(
            personal=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).values('fecha', 'codigo_dia', 'horas_efectivas')

        registros_dict = {r['fecha']: r for r in registros_mes}

        # Justificaciones ya enviadas (por fecha)
        just_dict = {j.fecha: j for j in justificaciones}

        primer_registro = RegistroTareo.objects.filter(
            personal=empleado
        ).order_by('fecha').first()
        anio_inicio = primer_registro.fecha.year if primer_registro else hoy.year

        context.update({
            'justificaciones': justificaciones,
            'registros_dict': registros_dict,
            'just_dict': just_dict,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'anio_sel': anio,
            'mes_sel': mes,
            'anios': range(anio_inicio, hoy.year + 1),
            'meses': [
                (1,'Enero'),(2,'Febrero'),(3,'Marzo'),(4,'Abril'),
                (5,'Mayo'),(6,'Junio'),(7,'Julio'),(8,'Agosto'),
                (9,'Septiembre'),(10,'Octubre'),(11,'Noviembre'),(12,'Diciembre'),
            ],
            'tipos': JustificacionNoMarcaje.TIPO_CHOICES,
        })

    return render(request, 'portal/mis_justificaciones.html', context)


@login_required
@require_POST
def justificacion_crear(request):
    """El trabajador envía una nueva justificación."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)

    fecha_str = request.POST.get('fecha', '')
    tipo = request.POST.get('tipo', '')
    motivo = request.POST.get('motivo', '').strip()

    if not fecha_str or not tipo or not motivo:
        return JsonResponse({'ok': False, 'error': 'Fecha, tipo y motivo son obligatorios.'}, status=400)

    try:
        fecha_parsed = date.fromisoformat(fecha_str)
        j, created = JustificacionNoMarcaje.objects.get_or_create(
            personal=empleado,
            fecha=fecha_parsed,
            defaults={'tipo': tipo, 'motivo': motivo, 'estado': 'PENDIENTE'},
        )
        if not created:
            # Ya existe — actualizar solo si sigue PENDIENTE
            if j.estado != 'PENDIENTE':
                return JsonResponse(
                    {'ok': False, 'error': f'Esta justificación ya fue {j.get_estado_display().lower()}.'},
                    status=400
                )
            j.tipo = tipo
            j.motivo = motivo
            j.save()
        return JsonResponse({
            'ok': True,
            'pk': j.pk,
            'fecha_display': j.fecha.strftime('%d/%m/%Y'),
            'tipo_display': j.get_tipo_display(),
            'estado': j.estado,
            'estado_display': j.get_estado_display(),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def justificacion_anular(request, pk):
    """El trabajador anula (elimina) una justificación pendiente propia."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)
    try:
        j = JustificacionNoMarcaje.objects.get(pk=pk, personal=empleado)
    except JustificacionNoMarcaje.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrado.'}, status=404)
    if j.estado != 'PENDIENTE':
        return JsonResponse({'ok': False, 'error': 'Solo se pueden anular justificaciones pendientes.'}, status=400)
    j.delete()
    return JsonResponse({'ok': True})


# ──────────────────────────────────────────────────────────────
# Solicitudes de Horas Extra (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_solicitudes_he(request):
    """El trabajador ve y crea sus solicitudes de horas extra."""
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        hoy = date.today()
        anio = _safe_int(request.GET.get('anio', hoy.year), hoy.year)
        mes = _safe_int(request.GET.get('mes', hoy.month), hoy.month)

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, calendar.monthrange(anio, mes)[1])

        solicitudes = list(SolicitudHE.objects.filter(
            personal=empleado,
            fecha__gte=fecha_inicio,
            fecha__lte=fecha_fin,
        ).order_by('-fecha'))

        primer_registro = SolicitudHE.objects.filter(
            personal=empleado,
        ).order_by('fecha').only('fecha').first()
        anio_inicio = primer_registro.fecha.year if primer_registro else hoy.year

        # Verificar si el control HE está activo
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.objects.first()
        he_activo = config.he_requiere_solicitud if config else False

        context.update({
            'solicitudes': solicitudes,
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'anio_sel': anio,
            'mes_sel': mes,
            'anios': range(anio_inicio, hoy.year + 1),
            'meses': [
                (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
                (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
                (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
            ],
            'tipos': SolicitudHE.TIPO_CHOICES,
            'he_activo': he_activo,
        })

    return render(request, 'portal/mis_solicitudes_he.html', context)


@login_required
@require_POST
def solicitud_he_crear(request):
    """El trabajador crea una solicitud de HE."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)

    fecha_str = request.POST.get('fecha', '')
    horas = request.POST.get('horas_estimadas', '')
    tipo = request.POST.get('tipo', '')
    motivo = request.POST.get('motivo', '').strip()

    if not fecha_str or not horas or not tipo or not motivo:
        return JsonResponse({'ok': False, 'error': 'Todos los campos son obligatorios.'}, status=400)

    try:
        s, created = SolicitudHE.objects.get_or_create(
            personal=empleado,
            fecha=fecha_str,
            defaults={
                'horas_estimadas': horas,
                'tipo': tipo,
                'motivo': motivo,
                'estado': 'PENDIENTE',
            },
        )
        if not created:
            if s.estado != 'PENDIENTE':
                return JsonResponse(
                    {'ok': False, 'error': f'Ya existe una solicitud para esa fecha ({s.get_estado_display().lower()}).'},
                    status=400,
                )
            s.horas_estimadas = horas
            s.tipo = tipo
            s.motivo = motivo
            s.save()
        return JsonResponse({
            'ok': True,
            'pk': s.pk,
            'fecha_display': s.fecha.strftime('%d/%m/%Y'),
            'horas': str(s.horas_estimadas),
            'tipo': s.tipo,
            'tipo_display': s.get_tipo_display(),
            'estado': s.estado,
            'estado_display': s.get_estado_display(),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def solicitud_he_anular(request, pk):
    """El trabajador anula una solicitud pendiente propia."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)
    try:
        s = SolicitudHE.objects.get(pk=pk, personal=empleado)
    except SolicitudHE.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrado.'}, status=404)
    if s.estado != 'PENDIENTE':
        return JsonResponse({'ok': False, 'error': 'Solo se pueden anular solicitudes pendientes.'}, status=400)
    s.estado = 'ANULADA'
    s.save()
    return JsonResponse({'ok': True})


# ──────────────────────────────────────────────────────────────
# Mis Papeletas (portal del trabajador)
# ──────────────────────────────────────────────────────────────

# Tipos que un trabajador puede solicitar desde el portal
# (excluimos los que solo genera el sistema/admin)
TIPOS_PORTAL = [
    ('VACACIONES', 'Vacaciones (VAC)'),
    ('COMPENSACION_HE', 'Compensación por Horario Extendido (CHE)'),
    ('BAJADAS', 'Bajadas / Día Libre (DL)'),
    ('BAJADAS_ACUMULADAS', 'Bajadas Acumuladas (DLA)'),
    ('DESCANSO_MEDICO', 'Descanso Médico (DM)'),
    ('LICENCIA_CON_GOCE', 'Licencia con Goce (LCG)'),
    ('LICENCIA_SIN_GOCE', 'Licencia sin Goce (LSG)'),
    ('LICENCIA_FALLECIMIENTO', 'Licencia por Fallecimiento (LF)'),
    ('LICENCIA_PATERNIDAD', 'Licencia por Paternidad (LP)'),
    ('LICENCIA_MATERNIDAD', 'Licencia por Maternidad (LM)'),
    ('COMISION_TRABAJO', 'Comisión de Trabajo (CT)'),
    ('CAPACITACION', 'Capacitación (CAP)'),
    ('TRABAJO_REMOTO', 'Trabajo Remoto (TR)'),
    ('OTRO', 'Otro'),
]
TIPOS_PORTAL_KEYS = {t[0] for t in TIPOS_PORTAL}


@login_required
def mis_papeletas(request):
    """El trabajador ve todas sus papeletas (importadas + propias)."""
    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        hoy = date.today()
        anio = _safe_int(request.GET.get('anio', hoy.year), hoy.year)
        estado_filter = request.GET.get('estado', '')
        tipo_filter = request.GET.get('tipo', '')

        qs = RegistroPapeleta.objects.filter(
            personal=empleado,
            fecha_inicio__year=anio,
        )
        if estado_filter:
            qs = qs.filter(estado=estado_filter)
        if tipo_filter:
            qs = qs.filter(tipo_permiso=tipo_filter)

        papeletas = list(qs.order_by('-fecha_inicio'))

        pendientes = RegistroPapeleta.objects.filter(
            personal=empleado, estado='PENDIENTE',
        ).count()

        primera = RegistroPapeleta.objects.filter(
            personal=empleado,
        ).order_by('fecha_inicio').first()
        anio_inicio = primera.fecha_inicio.year if primera else hoy.year

        context.update({
            'papeletas': papeletas,
            'pendientes': pendientes,
            'anio_sel': anio,
            'anios': range(anio_inicio, hoy.year + 1),
            'estado_sel': estado_filter,
            'tipo_sel': tipo_filter,
            'estados': RegistroPapeleta.ESTADO_CHOICES,
            'tipos_todos': RegistroPapeleta.TIPO_PERMISO_CHOICES,
            'tipos_portal': TIPOS_PORTAL,
        })

    return render(request, 'portal/mis_papeletas.html', context)


@login_required
@require_POST
def papeleta_crear_portal(request):
    """El trabajador solicita una nueva papeleta."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)

    tipo = request.POST.get('tipo_permiso', '')
    fecha_inicio = request.POST.get('fecha_inicio', '')
    fecha_fin = request.POST.get('fecha_fin', '')
    detalle = request.POST.get('detalle', '').strip()

    if not tipo or not fecha_inicio or not fecha_fin:
        return JsonResponse({'ok': False, 'error': 'Tipo, fecha inicio y fecha fin son obligatorios.'}, status=400)

    if tipo not in TIPOS_PORTAL_KEYS:
        return JsonResponse({'ok': False, 'error': 'Tipo de papeleta no permitido desde el portal.'}, status=400)

    try:
        f_ini = date.fromisoformat(fecha_inicio)
        f_fin = date.fromisoformat(fecha_fin)
    except ValueError:
        return JsonResponse({'ok': False, 'error': 'Formato de fecha inválido.'}, status=400)

    if f_fin < f_ini:
        return JsonResponse({'ok': False, 'error': 'Fecha fin no puede ser anterior a fecha inicio.'}, status=400)

    # Calcular días hábiles (lun-vie entre inicio y fin)
    dias = 0
    d = f_ini
    from datetime import timedelta
    while d <= f_fin:
        if d.weekday() < 5:  # lun=0 ... vie=4
            dias += 1
        d += timedelta(days=1)

    try:
        p = RegistroPapeleta.objects.create(
            personal=empleado,
            dni=empleado.nro_doc,
            nombre_archivo=empleado.apellidos_nombres,
            tipo_permiso=tipo,
            fecha_inicio=f_ini,
            fecha_fin=f_fin,
            dias_habiles=dias,
            detalle=detalle,
            origen='PORTAL',
            estado='PENDIENTE',
            creado_por=request.user,
            area_trabajo=str(empleado.subarea.area) if empleado.subarea else '',
            cargo=empleado.cargo or '',
        )
        return JsonResponse({
            'ok': True,
            'pk': p.pk,
            'tipo': p.tipo_permiso,
            'tipo_display': p.get_tipo_permiso_display(),
            'fecha_inicio': p.fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_fin': p.fecha_fin.strftime('%d/%m/%Y'),
            'dias_habiles': p.dias_habiles,
            'estado': p.estado,
            'estado_display': p.get_estado_display(),
            'detalle': p.detalle[:80],
            'origen': p.origen,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def papeleta_anular_portal(request, pk):
    """El trabajador anula una papeleta pendiente que él creó."""
    empleado = _get_empleado(request.user)
    if not empleado:
        return JsonResponse({'ok': False, 'error': 'Sin perfil vinculado.'}, status=403)
    try:
        p = RegistroPapeleta.objects.get(pk=pk, personal=empleado, origen='PORTAL')
    except RegistroPapeleta.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'No encontrado o no es una papeleta propia.'}, status=404)
    if p.estado != 'PENDIENTE':
        return JsonResponse({'ok': False, 'error': 'Solo se pueden anular papeletas pendientes.'}, status=400)
    p.estado = 'ANULADA'
    p.save()
    return JsonResponse({'ok': True})


# ──────────────────────────────────────────────────────────────
# Mi Timeline (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mi_timeline(request):
    """Timeline cronológica del propio empleado (vista portal)."""
    from personal.views.timeline import _build_timeline

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        eventos = _build_timeline(empleado, limit=100)

        meses = {}
        for ev in eventos:
            key = ev['fecha'].strftime('%Y-%m')
            label = ev['fecha'].strftime('%B %Y').capitalize()
            if key not in meses:
                meses[key] = {'label': label, 'eventos': []}
            meses[key]['eventos'].append(ev)

        hoy = date.today()
        antiguedad = ''
        if empleado.fecha_alta:
            delta = hoy - empleado.fecha_alta
            anios = delta.days // 365
            meses_rest = (delta.days % 365) // 30
            if anios > 0:
                antiguedad = f'{anios} año{"s" if anios > 1 else ""}'
                if meses_rest > 0:
                    antiguedad += f', {meses_rest} mes{"es" if meses_rest > 1 else ""}'
            else:
                antiguedad = f'{meses_rest} mes{"es" if meses_rest > 1 else ""}'

        context.update({
            'meses': meses,
            'total_eventos': len(eventos),
            'antiguedad': antiguedad,
        })

    return render(request, 'portal/mi_timeline.html', context)


# ──────────────────────────────────────────────────────────────
# Mis Documentos (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_documentos(request):
    """El trabajador ve su legajo digital (solo lectura)."""
    from documentos.models import DocumentoTrabajador, TipoDocumento

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        docs = DocumentoTrabajador.objects.filter(
            personal=empleado,
        ).exclude(estado='ANULADO').select_related(
            'tipo', 'tipo__categoria',
        ).order_by('tipo__categoria__orden', 'tipo__orden', '-version')

        # Agrupar por categoría
        categorias_dict = {}
        for doc in docs:
            cat_nombre = doc.tipo.categoria.nombre if doc.tipo.categoria else 'General'
            cat_icono = doc.tipo.categoria.icono if doc.tipo.categoria else 'fa-folder'
            if cat_nombre not in categorias_dict:
                categorias_dict[cat_nombre] = {'icono': cat_icono, 'docs': []}
            categorias_dict[cat_nombre]['docs'].append(doc)

        # Documentos faltantes obligatorios
        tipos_oblig = TipoDocumento.objects.filter(obligatorio=True, activo=True)
        if empleado.grupo_tareo == 'STAFF':
            tipos_oblig = tipos_oblig.filter(aplica_staff=True)
        else:
            tipos_oblig = tipos_oblig.filter(aplica_rco=True)

        tipos_existentes = set(docs.values_list('tipo_id', flat=True))
        faltantes = [t for t in tipos_oblig if t.pk not in tipos_existentes]

        context.update({
            'categorias_dict': categorias_dict,
            'faltantes': faltantes,
            'total_docs': docs.count(),
        })

    return render(request, 'portal/mis_documentos.html', context)


# ──────────────────────────────────────────────────────────────
# Mi Nómina (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mi_nomina(request):
    """El trabajador ve su historial de recibos de sueldo."""
    from decimal import Decimal
    from nominas.models import RegistroNomina, LineaNomina

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    # SmartBoletas compliance: registrar la VISTA del listado de boletas.
    # Esto cuenta como acuse de visualización aunque no descargue el PDF.
    if empleado:
        try:
            from documentos.models import LogActividadTrabajador
            LogActividadTrabajador.registrar(
                personal=empleado,
                tipo='VIEW_BOLETA',
                request=request,
                metadata={'vista': 'listado_mi_nomina'},
            )
        except Exception:
            pass  # no rompemos el render por un log

        registros = list(
            RegistroNomina.objects.filter(personal=empleado)
            .select_related('periodo')
            .order_by('-periodo__anio', '-periodo__mes')
        )

        # ── Vincular BoletaPago (lectura/confirmación) por período ─────
        # BoletaPago.periodo es DateField (primer día del mes).
        # Mapa: (anio, mes, tipo_boleta) → BoletaPago
        boletas_map = {}
        try:
            from documentos.models import BoletaPago
            # Map PeriodoNomina.tipo → BoletaPago.tipo
            _tipo_map = {
                'REGULAR':       'MENSUAL',
                'GRATIFICACION': 'GRATIFICACION',
                'CTS':           'CTS',
                'LIQUIDACION':   'LIQUIDACION',
                'UTILIDADES':    'UTILIDADES',
            }
            for b in BoletaPago.objects.filter(personal=empleado).exclude(estado='ANULADA'):
                boletas_map[(b.periodo.year, b.periodo.month, b.tipo)] = b
            # Adjuntar la boleta a cada registro para uso simple en el template
            for r in registros:
                key = (r.periodo.anio, r.periodo.mes, _tipo_map.get(r.periodo.tipo, 'MENSUAL'))
                r.boleta_pago = boletas_map.get(key)
        except Exception:
            for r in registros:
                r.boleta_pago = None

        # Líneas del período más reciente para mostrar el detalle completo
        lineas_reciente = []
        registro_reciente = registros[0] if registros else None
        if registro_reciente:
            lineas_reciente = list(
                LineaNomina.objects.filter(registro=registro_reciente)
                .select_related('concepto')
                .order_by('concepto__tipo', 'concepto__orden')
            )

        # ── Agrupar líneas por categoría para tabs del modal ───────────
        # INGRESO / DESCUENTO los conocemos por concepto.tipo.
        # APORTE_EMPLEADOR también es concepto.tipo.
        # PROVISION es concepto.subtipo (gratificación/cts provisión).
        lineas_ingresos = []
        lineas_descuentos = []
        lineas_aportes = []      # APORTE_EMPLEADOR no PROVISION (ESSALUD, SCTR)
        lineas_provisiones = []  # subtipo PROVISION (CTS, Gratif provisionados)
        for l in lineas_reciente:
            c = l.concepto
            subtipo = getattr(c, 'subtipo', '') or ''
            if subtipo == 'PROVISION':
                lineas_provisiones.append(l)
            elif c.tipo == 'INGRESO':
                lineas_ingresos.append(l)
            elif c.tipo == 'DESCUENTO':
                lineas_descuentos.append(l)
            elif c.tipo == 'APORTE_EMPLEADOR':
                lineas_aportes.append(l)

        # Comparativa contra el período inmediato anterior (mismo tipo)
        registro_anterior = None
        variacion_neto = None
        variacion_pct = None
        if registro_reciente and len(registros) > 1:
            for r in registros[1:]:
                if r.periodo.tipo == registro_reciente.periodo.tipo:
                    registro_anterior = r
                    break
            if registro_anterior and registro_anterior.neto_a_pagar:
                variacion_neto = registro_reciente.neto_a_pagar - registro_anterior.neto_a_pagar
                if registro_anterior.neto_a_pagar:
                    variacion_pct = (variacion_neto / registro_anterior.neto_a_pagar) * Decimal('100')

        # ── YTD acumulado (netos del año del último período) ──────────
        ytd_acumulado = Decimal('0')
        if registro_reciente:
            anio_ytd = registro_reciente.periodo.anio
            for r in registros:
                if r.periodo.anio == anio_ytd:
                    ytd_acumulado += (r.neto_a_pagar or Decimal('0'))

        # ¿IA disponible para explicar boleta?
        # Consulta el mismo servicio que ejecuta la explicación (ConfiguracionSistema),
        # así si el admin activa IA por panel, el botón aparece sin redeploy.
        ia_explicador_activo = False
        try:
            from asistencia.services.ai_service import get_service
            ia_explicador_activo = get_service() is not None
        except Exception:
            pass

        context.update({
            'registros': registros,
            'registro_reciente': registro_reciente,
            'registro_anterior': registro_anterior,
            'variacion_neto': variacion_neto,
            'variacion_pct': variacion_pct,
            'ytd_acumulado': ytd_acumulado,
            'lineas_ingresos': lineas_ingresos,
            'lineas_descuentos': lineas_descuentos,
            'lineas_aportes': lineas_aportes,
            'lineas_provisiones': lineas_provisiones,
            'ia_explicador_activo': ia_explicador_activo,
        })

    return render(request, 'portal/mi_nomina.html', context)


# ──────────────────────────────────────────────────────────────
# Mis Evaluaciones (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_evaluaciones(request):
    """El trabajador ve sus evaluaciones de desempeño y PDI."""
    from evaluaciones.models import Evaluacion, PlanDesarrollo, ResultadoConsolidado

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        evaluaciones = list(
            Evaluacion.objects.filter(evaluado=empleado)
            .select_related('ciclo', 'evaluador')
            .order_by('-ciclo__fecha_inicio')
        )

        planes = list(
            PlanDesarrollo.objects.filter(personal=empleado)
            .select_related('ciclo')
            .prefetch_related('acciones')
            .order_by('-fecha_inicio')
        )

        resultados = list(
            ResultadoConsolidado.objects.filter(personal=empleado)
            .select_related('ciclo')
            .order_by('-ciclo__fecha_inicio')
        )

        context.update({
            'evaluaciones': evaluaciones,
            'planes': planes,
            'resultados': resultados,
        })

    return render(request, 'portal/mis_evaluaciones.html', context)


# ──────────────────────────────────────────────────────────────
# Mi Adelanto de Sueldo — EWA sobre devengado (portal)
# ──────────────────────────────────────────────────────────────

@login_required
def mi_adelanto(request):
    """El trabajador solicita un adelanto contra sus días ya trabajados.

    El tope es el 50% del devengado del ciclo de planilla en curso; la
    solicitud entra al flujo normal de préstamos (RRHH aprueba/desembolsa)
    y la cuota única se descuenta sola en la planilla del período.
    """
    from django.contrib import messages
    from django.shortcuts import redirect

    from prestamos import ewa
    from prestamos.models import Prestamo

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if not empleado:
        return render(request, 'portal/mi_adelanto.html', context)

    if request.method == 'POST':
        try:
            prestamo = ewa.solicitar_adelanto(
                empleado,
                monto=request.POST.get('monto', ''),
                usuario=request.user,
                motivo=(request.POST.get('motivo') or '').strip()[:500],
            )
            messages.success(
                request,
                f'Solicitud registrada por S/ {prestamo.monto_solicitado}. '
                f'RRHH la revisará; el descuento se aplicará en tu planilla del período.'
            )
            return redirect('portal_mi_adelanto')
        except ewa.EWAError as e:
            messages.error(request, str(e))

    info = ewa.calcular_disponible(empleado)
    solicitudes = list(
        Prestamo.objects.filter(personal=empleado, tipo__codigo=ewa.TIPO_CODIGO)
        .order_by('-fecha_solicitud', '-creado_en')[:10]
    )
    context.update({
        'info': info,
        'pct_tope': int(ewa.PCT_TOPE_DEVENGADO * 100),
        'monto_minimo': ewa.MONTO_MINIMO,
        'solicitudes': solicitudes,
    })
    return render(request, 'portal/mi_adelanto.html', context)


# ──────────────────────────────────────────────────────────────
# Mis Capacitaciones (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_capacitaciones(request):
    """El trabajador ve sus capacitaciones asistidas y certificaciones."""
    from capacitaciones.models import AsistenciaCapacitacion, CertificacionTrabajador

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        asistencias = list(
            AsistenciaCapacitacion.objects.filter(personal=empleado)
            .select_related('capacitacion', 'capacitacion__categoria')
            .order_by('-capacitacion__fecha_inicio')
        )

        certificaciones = list(
            CertificacionTrabajador.objects.filter(personal=empleado)
            .select_related('requerimiento', 'capacitacion')
            .order_by('-fecha_obtencion')
        )

        # KPI totals
        total_horas = sum(
            (a.capacitacion.horas or 0)
            for a in asistencias
            if a.estado in ('ASISTIO', 'PARCIAL')
        )
        total_aprobados = sum(1 for a in asistencias if a.aprobado)
        total_certificados = len(certificaciones)

        context.update({
            'asistencias': asistencias,
            'certificaciones': certificaciones,
            'total_horas': total_horas,
            'total_aprobados': total_aprobados,
            'total_certificados': total_certificados,
        })

    return render(request, 'portal/mis_capacitaciones.html', context)


# ──────────────────────────────────────────────────────────────
# Mis Vacaciones (portal del trabajador)
# ──────────────────────────────────────────────────────────────

@login_required
def mis_vacaciones(request):
    """El trabajador ve su saldo vacacional e historial de solicitudes."""
    from vacaciones.models import SaldoVacacional, SolicitudVacacion

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        saldos = list(
            SaldoVacacional.objects.filter(personal=empleado)
            .order_by('-periodo_fin')
        )

        solicitudes = list(
            SolicitudVacacion.objects.filter(personal=empleado)
            .select_related('saldo')
            .order_by('-fecha_inicio')[:20]
        )

        total_pendientes_dias = sum(s.dias_pendientes for s in saldos)

        context.update({
            'saldos': saldos,
            'solicitudes': solicitudes,
            'total_pendientes_dias': total_pendientes_dias,
        })

    return render(request, 'portal/mis_vacaciones.html', context)


@login_required
def mis_archivos_hr(request):
    """El trabajador ve y descarga los archivos que RRHH le envió."""
    from documentos.models import ArchivoHR

    empleado = _get_empleado(request.user)
    context = {'empleado': empleado}

    if empleado:
        archivos = ArchivoHR.objects.filter(
            personal=empleado,
            visible=True,
        ).order_by('-creado_en')

        context['archivos'] = archivos
        context['total'] = archivos.count()
        context['pendientes'] = archivos.filter(descargado=False).count()

    return render(request, 'portal/mis_archivos_hr.html', context)
