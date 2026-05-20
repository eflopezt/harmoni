"""
Vistas para Timeline del Empleado — historia laboral cronológica.

Agrega eventos de: Personal, Papeletas, Solicitudes HE, Justificaciones,
BancoHoras, Documentos, Roster.
"""
from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

from personal.models import Personal

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


def _build_timeline(empleado, limit=100):
    """Construye la lista de eventos cronológicos para un empleado."""
    from asistencia.models import (
        RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje,
        MovimientoBancoHoras,
    )
    from documentos.models import DocumentoTrabajador

    eventos = []

    # ── Ingreso / Cese ──
    if empleado.fecha_alta:
        eventos.append({
            'fecha': empleado.fecha_alta,
            'icono': 'fa-user-plus',
            'color': '#059669',
            'titulo': 'Ingreso a la empresa',
            'detalle': f'{empleado.cargo or "Sin cargo"} — {empleado.grupo_tareo}',
            'tipo': 'ingreso',
        })

    if empleado.fecha_cese:
        eventos.append({
            'fecha': empleado.fecha_cese,
            'icono': 'fa-user-minus',
            'color': '#dc2626',
            'titulo': 'Cese / Salida',
            'detalle': f'Estado: {empleado.estado}',
            'tipo': 'cese',
        })

    # ── Papeletas (aprobadas y ejecutadas) ──
    papeletas = RegistroPapeleta.objects.filter(
        personal=empleado,
        estado__in=['APROBADA', 'EJECUTADA'],
    ).order_by('-fecha_inicio')[:50]

    PAPELETA_ICONS = {
        'VACACIONES': ('fa-umbrella-beach', '#0ea5e9'),
        'DESCANSO_MEDICO': ('fa-hospital', '#ef4444'),
        'LICENCIA_CON_GOCE': ('fa-calendar-check', '#8b5cf6'),
        'LICENCIA_SIN_GOCE': ('fa-calendar-minus', '#6b7280'),
        'LICENCIA_FALLECIMIENTO': ('fa-heart-crack', '#374151'),
        'LICENCIA_PATERNIDAD': ('fa-baby', '#3b82f6'),
        'LICENCIA_MATERNIDAD': ('fa-baby-carriage', '#ec4899'),
        'BAJADAS': ('fa-plane-departure', '#f59e0b'),
        'BAJADAS_ACUMULADAS': ('fa-plane-departure', '#f59e0b'),
        'COMPENSACION_HE': ('fa-exchange-alt', '#10b981'),
        'COMPENSACION_FERIADO': ('fa-exchange-alt', '#10b981'),
        'COMP_DIA_TRABAJO': ('fa-exchange-alt', '#10b981'),
        'COMISION_TRABAJO': ('fa-briefcase', '#6366f1'),
        'CAPACITACION': ('fa-graduation-cap', '#0891b2'),
        'SUSPENSION': ('fa-ban', '#dc2626'),
        'TRABAJO_REMOTO': ('fa-laptop-house', '#8b5cf6'),
    }

    for p in papeletas:
        icono, color = PAPELETA_ICONS.get(p.tipo_permiso, ('fa-file-alt', '#6b7280'))
        dias = f' ({p.dias_habiles}d háb.)' if p.dias_habiles else ''
        eventos.append({
            'fecha': p.fecha_inicio,
            'icono': icono,
            'color': color,
            'titulo': p.get_tipo_permiso_display(),
            'detalle': f'{p.fecha_inicio.strftime("%d/%m")} → {p.fecha_fin.strftime("%d/%m/%Y")}{dias}',
            'tipo': 'papeleta',
            'subtipo': p.tipo_permiso,
        })

    # ── Solicitudes HE aprobadas ──
    solicitudes = SolicitudHE.objects.filter(
        personal=empleado,
        estado='APROBADA',
    ).order_by('-fecha')[:30]

    for s in solicitudes:
        eventos.append({
            'fecha': s.fecha,
            'icono': 'fa-clock',
            'color': '#f59e0b',
            'titulo': f'Horas Extra Aprobadas — {s.horas_estimadas}h',
            'detalle': f'{s.get_tipo_display()} · {s.motivo[:60]}' if s.motivo else s.get_tipo_display(),
            'tipo': 'solicitud_he',
        })

    # ── Justificaciones aprobadas ──
    justificaciones = JustificacionNoMarcaje.objects.filter(
        personal=empleado,
        estado='APROBADA',
    ).order_by('-fecha')[:30]

    for j in justificaciones:
        eventos.append({
            'fecha': j.fecha,
            'icono': 'fa-pen-square',
            'color': '#6366f1',
            'titulo': f'Justificación: {j.get_tipo_display()}',
            'detalle': j.motivo[:60] if j.motivo else '',
            'tipo': 'justificacion',
        })

    # ── Documentos subidos ──
    documentos = DocumentoTrabajador.objects.filter(
        personal=empleado,
    ).exclude(estado='ANULADO').select_related('tipo').order_by('-creado_en')[:20]

    for d in documentos:
        eventos.append({
            'fecha': d.creado_en.date(),
            'icono': 'fa-file-upload',
            'color': '#0f766e',
            'titulo': f'Documento: {d.tipo.nombre}',
            'detalle': f'v{d.version} · {d.nombre_archivo[:40]}',
            'tipo': 'documento',
        })

    # ── Movimientos Banco de Horas (solo significativos) ──
    movimientos = MovimientoBancoHoras.objects.filter(
        banco__personal=empleado,
    ).select_related('banco').order_by('-fecha')[:20]

    MOVIMIENTO_ICONS = {
        'ACUMULACION': ('fa-plus-circle', '#10b981'),
        'COMPENSACION': ('fa-minus-circle', '#f59e0b'),
        'VENCIMIENTO': ('fa-clock', '#dc2626'),
        'AJUSTE_MANUAL': ('fa-sliders-h', '#6366f1'),
        'LIQUIDACION': ('fa-file-invoice-dollar', '#374151'),
    }

    for m in movimientos:
        icono, color = MOVIMIENTO_ICONS.get(m.tipo, ('fa-exchange-alt', '#6b7280'))
        signo = '+' if m.horas > 0 else ''
        eventos.append({
            'fecha': m.fecha,
            'icono': icono,
            'color': color,
            'titulo': f'Banco Horas: {m.get_tipo_display()}',
            'detalle': f'{signo}{m.horas}h ({m.get_tasa_display()})',
            'tipo': 'banco_horas',
        })

    # ── Cambios Salariales ──
    try:
        from salarios.models import HistorialSalarial
        for h in HistorialSalarial.objects.filter(personal=empleado).order_by('fecha_efectiva'):
            if not h.fecha_efectiva:
                continue
            motivo_txt = h.get_motivo_display() if hasattr(h, 'get_motivo_display') else ''
            eventos.append({
                'fecha': h.fecha_efectiva,
                'icono': 'fa-money-bill-wave',
                'color': '#16a34a',
                'titulo': f'Ajuste salarial: S/ {h.remuneracion_nueva:,.2f}',
                'detalle': motivo_txt,
                'tipo': 'salario',
            })
    except Exception:
        pass

    # ── Vacaciones Aprobadas ──
    try:
        from vacaciones.models import SolicitudVacacion
        for s in SolicitudVacacion.objects.filter(
            personal=empleado, estado__in=['APROBADA', 'EN_GOCE', 'COMPLETADA']
        ).order_by('fecha_inicio'):
            if not s.fecha_inicio:
                continue
            dias = s.dias_habiles or s.dias_calendario or 0
            eventos.append({
                'fecha': s.fecha_inicio,
                'icono': 'fa-umbrella-beach',
                'color': '#f59e0b',
                'titulo': f'Vacaciones: {dias} días',
                'detalle': (
                    f'{s.fecha_inicio.strftime("%d/%m/%Y")} → {s.fecha_fin.strftime("%d/%m/%Y")}'
                    if s.fecha_fin else s.fecha_inicio.strftime('%d/%m/%Y')
                ),
                'tipo': 'vacacion',
            })
    except Exception:
        pass

    # ── Capacitaciones Completadas ──
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        cap_qs = AsistenciaCapacitacion.objects.filter(
            personal=empleado, estado__in=['ASISTIO', 'PARCIAL']
        ).select_related('capacitacion', 'capacitacion__categoria').order_by(
            'capacitacion__fecha_inicio'
        )
        for a in cap_qs:
            fecha_cap = a.capacitacion.fecha_inicio if a.capacitacion else None
            if not fecha_cap:
                continue
            cat_nombre = ''
            if hasattr(a.capacitacion, 'categoria') and a.capacitacion.categoria:
                cat_nombre = a.capacitacion.categoria.nombre
            eventos.append({
                'fecha': fecha_cap,
                'icono': 'fa-graduation-cap',
                'color': '#8b5cf6',
                'titulo': f'Capacitación: {a.capacitacion.titulo}',
                'detalle': cat_nombre,
                'tipo': 'capacitacion',
            })
    except Exception:
        pass

    # ── Evaluaciones Completadas ──
    try:
        from evaluaciones.models import Evaluacion
        eval_qs = Evaluacion.objects.filter(
            evaluado=empleado, estado__in=['COMPLETADA', 'CALIBRADA']
        ).select_related('ciclo').order_by('fecha_completada')
        for e in eval_qs:
            fecha_ev = e.fecha_completada.date() if e.fecha_completada else None
            if not fecha_ev:
                continue
            relacion_txt = e.get_relacion_display() if hasattr(e, 'get_relacion_display') else ''
            ciclo_nombre = e.ciclo.nombre if e.ciclo else ''
            detalle = ' · '.join(filter(None, [relacion_txt, ciclo_nombre]))
            eventos.append({
                'fecha': fecha_ev,
                'icono': 'fa-star',
                'color': '#0891b2',
                'titulo': 'Evaluación de desempeño',
                'detalle': detalle,
                'tipo': 'evaluacion',
            })
    except Exception:
        pass

    # ── Préstamos Aprobados ──
    try:
        from prestamos.models import Prestamo
        prest_qs = Prestamo.objects.filter(
            personal=empleado,
            estado__in=['APROBADO', 'EN_CURSO', 'PAGADO'],
        ).order_by('fecha_solicitud')
        for p in prest_qs:
            if not p.fecha_solicitud:
                continue
            eventos.append({
                'fecha': p.fecha_solicitud,
                'icono': 'fa-hand-holding-usd',
                'color': '#7c3aed',
                'titulo': f'Préstamo: S/ {p.monto_solicitado:,.2f}',
                'detalle': f'{p.num_cuotas} cuota{"s" if p.num_cuotas != 1 else ""}',
                'tipo': 'prestamo',
            })
    except Exception:
        pass

    # ── Ordenar cronológicamente (más reciente primero) ──
    eventos.sort(key=lambda e: e['fecha'], reverse=True)

    return eventos[:limit]


@login_required
@solo_admin
def timeline_empleado(request, pk):
    """Timeline cronológica completa de un empleado (vista admin)."""
    empleado = get_object_or_404(Personal, pk=pk)
    eventos = _build_timeline(empleado, limit=150)

    # Agrupar por año-mes para encabezados
    meses = {}
    for ev in eventos:
        key = ev['fecha'].strftime('%Y-%m')
        label = ev['fecha'].strftime('%B %Y').capitalize()
        if key not in meses:
            meses[key] = {'label': label, 'eventos': []}
        meses[key]['eventos'].append(ev)

    # Stats rápidas
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

    context = {
        'titulo': f'Timeline — {empleado.apellidos_nombres}',
        'empleado': empleado,
        'meses': meses,
        'total_eventos': len(eventos),
        'antiguedad': antiguedad,
    }
    return render(request, 'personal/timeline.html', context)
