"""
Portal API endpoints for mobile access.
Provides lightweight JSON responses for employee self-service.
All endpoints require authentication and return data for the current user only.
"""
import calendar
from datetime import date

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


def _decimal_to_float(val):
    """Safely convert Decimal/None to float for JSON serialization."""
    if val is None:
        return 0.0
    return float(val)


def _get_empleado(user):
    """Return the Personal linked to this user, or None."""
    return getattr(user, 'personal_data', None)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_portal_me(request):
    """
    GET /api/v1/portal/me/
    Returns current employee's personal and work info.
    """
    empleado = _get_empleado(request.user)
    if not empleado:
        return Response(
            {'error': 'Tu usuario no está vinculado a un empleado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    hoy = date.today()
    antiguedad = None
    if empleado.fecha_alta:
        delta = hoy - empleado.fecha_alta
        antiguedad = {
            'anios': delta.days // 365,
            'meses': (delta.days % 365) // 30,
            'dias_total': delta.days,
        }

    # Pending requests count
    from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje
    pendientes = {
        'papeletas': RegistroPapeleta.objects.filter(
            personal=empleado, estado='PENDIENTE').count(),
        'solicitudes_he': SolicitudHE.objects.filter(
            personal=empleado, estado='PENDIENTE').count(),
        'justificaciones': JustificacionNoMarcaje.objects.filter(
            personal=empleado, estado='PENDIENTE').count(),
    }
    pendientes['total'] = sum(pendientes.values())

    # Notifications count
    notif_count = 0
    try:
        from comunicaciones.models import Notificacion
        notif_count = Notificacion.objects.filter(
            destinatario=request.user, leida=False).count()
    except Exception:
        pass

    data = {
        'id': empleado.pk,
        'nombre': empleado.apellidos_nombres,
        'nro_doc': empleado.nro_doc,
        'cargo': empleado.cargo or '',
        'estado': empleado.estado,
        'grupo_tareo': empleado.grupo_tareo,
        'area': '',
        'subarea': '',
        'fecha_alta': empleado.fecha_alta.isoformat() if empleado.fecha_alta else None,
        'fecha_fin_contrato': (
            empleado.fecha_fin_contrato.isoformat()
            if empleado.fecha_fin_contrato else None
        ),
        'correo_corporativo': empleado.correo_corporativo or '',
        'correo_personal': empleado.correo_personal or '',
        'celular': empleado.celular or '',
        'regimen_pension': empleado.regimen_pension or '',
        'afp': empleado.afp or '',
        'jornada_horas': _decimal_to_float(empleado.jornada_horas),
        'antiguedad': antiguedad,
        'pendientes': pendientes,
        'notificaciones_sin_leer': notif_count,
    }

    if empleado.subarea:
        data['subarea'] = empleado.subarea.nombre
        if empleado.subarea.area:
            data['area'] = empleado.subarea.area.nombre

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_portal_boletas(request):
    """
    GET /api/v1/portal/boletas/
    Returns recent payslips for the current employee.
    Query params: ?limit=10 (default 10, max 50)
    """
    from nominas.models import RegistroNomina, LineaNomina

    empleado = _get_empleado(request.user)
    if not empleado:
        return Response(
            {'error': 'Tu usuario no está vinculado a un empleado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    limit = min(int(request.GET.get('limit', 10)), 50)

    registros = (
        RegistroNomina.objects.filter(personal=empleado)
        .select_related('periodo')
        .order_by('-periodo__anio', '-periodo__mes')[:limit]
    )

    boletas = []
    for reg in registros:
        boleta = {
            'id': reg.pk,
            'periodo': str(reg.periodo),
            'anio': reg.periodo.anio,
            'mes': reg.periodo.mes,
            'tipo': reg.periodo.tipo,
            'dias_trabajados': reg.dias_trabajados,
            'sueldo_base': _decimal_to_float(reg.sueldo_base),
            'total_ingresos': _decimal_to_float(reg.total_ingresos),
            'total_descuentos': _decimal_to_float(reg.total_descuentos),
            'neto_a_pagar': _decimal_to_float(reg.neto_a_pagar),
            'estado': reg.estado,
            'regimen_pension': reg.regimen_pension or '',
            'afp': reg.afp or '',
        }
        if reg.periodo.fecha_pago:
            boleta['fecha_pago'] = reg.periodo.fecha_pago.isoformat()

        boletas.append(boleta)

    # Detail lines for the most recent payslip
    detalle_reciente = None
    if registros:
        lineas = (
            LineaNomina.objects.filter(registro=registros[0])
            .select_related('concepto')
            .order_by('concepto__tipo', 'concepto__orden')
        )
        detalle_reciente = {
            'periodo': str(registros[0].periodo),
            'ingresos': [
                {'concepto': l.concepto.nombre, 'monto': _decimal_to_float(l.monto)}
                for l in lineas if l.concepto.tipo == 'INGRESO'
            ],
            'descuentos': [
                {'concepto': l.concepto.nombre, 'monto': _decimal_to_float(l.monto)}
                for l in lineas if l.concepto.tipo == 'DESCUENTO'
            ],
        }

    return Response({
        'total': len(boletas),
        'boletas': boletas,
        'detalle_reciente': detalle_reciente,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_portal_asistencia(request):
    """
    GET /api/v1/portal/asistencia/
    Returns current month attendance summary and daily records.
    Query params: ?anio=2026&mes=3
    """
    from asistencia.models import RegistroTareo, BancoHoras

    empleado = _get_empleado(request.user)
    if not empleado:
        return Response(
            {'error': 'Tu usuario no está vinculado a un empleado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    hoy = date.today()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))

    try:
        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, calendar.monthrange(anio, mes)[1])
    except (ValueError, OverflowError):
        return Response(
            {'error': 'Año/mes inválido.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    registros = RegistroTareo.objects.filter(
        personal=empleado,
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    ).order_by('fecha')

    dias_trabajados = 0
    total_horas = 0.0
    total_he = 0.0
    records = []

    for r in registros:
        he = _decimal_to_float(r.he_25) + _decimal_to_float(r.he_35) + _decimal_to_float(r.he_100)
        horas_ef = _decimal_to_float(r.horas_efectivas)

        if horas_ef > 0:
            dias_trabajados += 1
        total_horas += horas_ef
        total_he += he

        records.append({
            'fecha': r.fecha.isoformat(),
            'dia_semana': r.fecha.strftime('%a'),
            'codigo_dia': r.codigo_dia or '',
            'horas_efectivas': round(horas_ef, 2),
            'he_25': _decimal_to_float(r.he_25),
            'he_35': _decimal_to_float(r.he_35),
            'he_100': _decimal_to_float(r.he_100),
            'he_total': round(he, 2),
        })

    # Banco de horas
    banco = BancoHoras.objects.filter(
        personal=empleado,
    ).order_by('-periodo_anio', '-periodo_mes').first()

    return Response({
        'periodo': {
            'anio': anio,
            'mes': mes,
            'fecha_inicio': fecha_inicio.isoformat(),
            'fecha_fin': fecha_fin.isoformat(),
        },
        'resumen': {
            'dias_trabajados': dias_trabajados,
            'total_horas': round(total_horas, 2),
            'total_he': round(total_he, 2),
            'total_registros': len(records),
        },
        'banco_horas': {
            'saldo': _decimal_to_float(banco.saldo_horas) if banco else 0.0,
            'periodo': f'{banco.periodo_anio}-{banco.periodo_mes:02d}' if banco else None,
        },
        'registros': records,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_portal_vacaciones(request):
    """
    GET /api/v1/portal/vacaciones/
    Returns vacation balance and recent requests for the current employee.
    """
    from vacaciones.models import SaldoVacacional, SolicitudVacacion

    empleado = _get_empleado(request.user)
    if not empleado:
        return Response(
            {'error': 'Tu usuario no está vinculado a un empleado.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    saldos = SaldoVacacional.objects.filter(
        personal=empleado
    ).order_by('-periodo_fin')

    total_pendientes = sum(_decimal_to_float(s.dias_pendientes) for s in saldos)
    total_gozados = sum(_decimal_to_float(s.dias_gozados) for s in saldos)
    total_derecho = sum(_decimal_to_float(s.dias_derecho) for s in saldos)

    saldos_data = []
    for s in saldos:
        saldos_data.append({
            'id': s.pk,
            'periodo_inicio': s.periodo_inicio.isoformat(),
            'periodo_fin': s.periodo_fin.isoformat(),
            'dias_derecho': _decimal_to_float(s.dias_derecho),
            'dias_gozados': _decimal_to_float(s.dias_gozados),
            'dias_pendientes': _decimal_to_float(s.dias_pendientes),
            'dias_vendidos': _decimal_to_float(s.dias_vendidos) if hasattr(s, 'dias_vendidos') else 0,
            'estado': s.estado,
        })

    solicitudes = (
        SolicitudVacacion.objects.filter(personal=empleado)
        .select_related('saldo')
        .order_by('-fecha_inicio')[:20]
    )

    solicitudes_data = []
    for sol in solicitudes:
        solicitudes_data.append({
            'id': sol.pk,
            'fecha_inicio': sol.fecha_inicio.isoformat(),
            'fecha_fin': sol.fecha_fin.isoformat(),
            'dias_calendario': sol.dias_calendario,
            'estado': sol.estado,
            'motivo': sol.motivo or '',
            'motivo_rechazo': sol.motivo_rechazo or '' if hasattr(sol, 'motivo_rechazo') else '',
            'fecha_aprobacion': (
                sol.fecha_aprobacion.isoformat()
                if hasattr(sol, 'fecha_aprobacion') and sol.fecha_aprobacion
                else None
            ),
        })

    return Response({
        'resumen': {
            'total_dias_pendientes': round(total_pendientes, 1),
            'total_dias_gozados': round(total_gozados, 1),
            'total_dias_derecho': round(total_derecho, 1),
        },
        'saldos': saldos_data,
        'solicitudes': solicitudes_data,
    })
