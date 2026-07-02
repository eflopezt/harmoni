"""
Motor de cierre mensual.

Cada función recibe (periodo: PeriodoCierre) y devuelve un dict:
  {
    'estado': 'OK' | 'ERROR' | 'ADVERTENCIA',
    'mensaje': str,        # resumen corto
    'detalles': list[str], # líneas informativas
    'datos': dict,         # data adicional para el template
  }
"""
from django.utils import timezone
from decimal import Decimal


PASOS_ORDENADOS = [
    ('VERIFICAR_IMPORTACIONES', 1),
    ('VALIDAR_DNI',             2),
    ('VERIFICAR_SS',            3),
    ('ASEGURAR_BANCO',          4),
    ('GENERAR_CARGA_S10',       5),
    ('REPORTE_CIERRE',          6),
    ('BLOQUEAR_PERIODO',        7),
]


def inicializar_pasos(periodo):
    """Crea los PasoCierre si aún no existen para este período."""
    from cierre.models import PasoCierre
    for codigo, orden in PASOS_ORDENADOS:
        PasoCierre.objects.get_or_create(
            periodo=periodo, codigo=codigo,
            defaults={'orden': orden},
        )


def ejecutar_paso(periodo, codigo):
    """Ejecuta un paso y guarda el resultado en BD."""
    from cierre.models import PasoCierre

    paso = PasoCierre.objects.get(periodo=periodo, codigo=codigo)
    paso.estado = 'EJECUTANDO'
    paso.save(update_fields=['estado'])

    try:
        fn = _EJECUTORES.get(codigo)
        if fn is None:
            resultado = {'estado': 'ERROR', 'mensaje': f'Sin ejecutor para {codigo}', 'detalles': [], 'datos': {}}
        else:
            resultado = fn(periodo)
    except Exception as exc:
        resultado = {
            'estado': 'ERROR',
            'mensaje': f'Error inesperado: {exc}',
            'detalles': [str(exc)],
            'datos': {},
        }

    paso.estado = resultado['estado']
    paso.resultado = resultado
    paso.ejecutado_en = timezone.now()
    paso.save()
    return resultado


# ── Ejecutores individuales ─────────────────────────────────

def _paso_verificar_importaciones(periodo):
    from asistencia.models import TareoImportacion, ConfiguracionSistema
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_he(periodo.anio, periodo.mes)

    # Importaciones cuyo período solape con el ciclo de asistencia
    importaciones = TareoImportacion.objects.filter(
        periodo_inicio__lte=fin,
        periodo_fin__gte=inicio,
        estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'],
    ).order_by('tipo')

    count = importaciones.count()
    tipos = list(importaciones.values_list('tipo', flat=True).distinct())
    detalles = [
        f'Tipo {t}: {importaciones.filter(tipo=t).count()} importación(es)'
        for t in tipos
    ]

    if count == 0:
        return {
            'estado': 'ERROR',
            'mensaje': 'No hay importaciones completadas para este período',
            'detalles': [
                'Realiza al menos una importación (RELOJ) antes de cerrar',
                f'Período buscado: {inicio.strftime("%d/%m/%Y")} → {fin.strftime("%d/%m/%Y")}',
            ],
            'datos': {'total': 0},
        }

    return {
        'estado': 'OK',
        'mensaje': f'{count} importación(es) completada(s) — tipos: {", ".join(tipos)}',
        'detalles': detalles,
        'datos': {'total': count, 'tipos': tipos},
    }


def _paso_validar_dni(periodo):
    from asistencia.models import RegistroTareo, ConfiguracionSistema
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_he(periodo.anio, periodo.mes)

    sin_match = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin,
        personal__isnull=True,
    ).values('nro_doc_raw').distinct() if hasattr(
        RegistroTareo, 'nro_doc_raw') else []

    # Alternativa: registros sin personal vinculado
    total_regs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin).count()
    sin_personal = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin, personal__isnull=True,
    ).count()

    if sin_personal > 0:
        return {
            'estado': 'ADVERTENCIA',
            'mensaje': f'{sin_personal} registro(s) sin empleado vinculado',
            'detalles': [
                f'Total registros: {total_regs}',
                f'Sin match personal: {sin_personal}',
                'Revisar en Vista Staff/RCO y vincular manualmente si es necesario',
            ],
            'datos': {'total': total_regs, 'sin_match': sin_personal},
        }

    return {
        'estado': 'OK',
        'mensaje': f'Todos los {total_regs} registros tienen personal vinculado',
        'detalles': [f'Total registros verificados: {total_regs}'],
        'datos': {'total': total_regs, 'sin_match': 0},
    }


def _paso_verificar_ss(periodo):
    from asistencia.models import RegistroTareo, ConfiguracionSistema
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_he(periodo.anio, periodo.mes)

    ss_regs = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin,
        codigo_dia='SS',
    )
    count_ss = ss_regs.count()

    if count_ss > 0:
        nombres = list(
            ss_regs.values_list('personal__apellidos_nombres', flat=True)
            .distinct()[:10]
        )
        detalles = [f'• {n}' for n in nombres if n]
        if count_ss > 10:
            detalles.append(f'... y {count_ss - 10} más')

        return {
            'estado': 'ADVERTENCIA',
            'mensaje': f'{count_ss} registro(s) con código SS (Sin Salida)',
            'detalles': ['Personas con SS pendiente:'] + detalles,
            'datos': {'count_ss': count_ss},
        }

    return {
        'estado': 'OK',
        'mensaje': 'Sin registros SS pendientes',
        'detalles': ['Todos los registros tienen salida registrada'],
        'datos': {'count_ss': 0},
    }


def _paso_asegurar_banco(periodo):
    from asistencia.models import BancoHoras, ConfiguracionSistema
    from personal.models import Personal

    activos_staff = Personal.objects.filter(
        grupo_tareo='STAFF', estado='Activo',
    ).count()

    banco_count = BancoHoras.objects.filter(
        periodo_anio=periodo.anio, periodo_mes=periodo.mes,
    ).count()

    faltantes = activos_staff - banco_count

    if faltantes > 0:
        return {
            'estado': 'ADVERTENCIA',
            'mensaje': f'{faltantes} empleado(s) STAFF sin registro de banco en este período',
            'detalles': [
                f'STAFF activos: {activos_staff}',
                f'Con BancoHoras: {banco_count}',
                f'Sin BancoHoras: {faltantes}',
                'Los registros faltantes tienen saldo 0 implícito',
            ],
            'datos': {'activos': activos_staff, 'con_banco': banco_count, 'faltantes': faltantes},
        }

    return {
        'estado': 'OK',
        'mensaje': f'BancoHoras verificado — {banco_count} registros para {activos_staff} activos STAFF',
        'detalles': [
            f'STAFF activos: {activos_staff}',
            f'Registros BancoHoras: {banco_count}',
        ],
        'datos': {'activos': activos_staff, 'con_banco': banco_count, 'faltantes': 0},
    }


def _paso_generar_carga_s10(periodo):
    """Genera de verdad el archivo CargaS10 (antes solo reportaba stats) para
    validar que la exportación funciona con los datos del período, y expone
    la URL de descarga."""
    from asistencia.models import RegistroTareo, ConfiguracionSistema
    from asistencia.services.exporters import CargaS10Exporter
    from django.db.models import Sum, Count
    from django.urls import reverse

    config = ConfiguracionSistema.get()
    inicio_he, fin_he = config.get_ciclo_he(periodo.anio, periodo.mes)

    rco_stats = RegistroTareo.objects.filter(
        fecha__gte=inicio_he, fecha__lte=fin_he,
        personal__grupo_tareo='RCO',
    ).aggregate(
        personas=Count('personal', distinct=True),
        he25=Sum('he_25'),
        he35=Sum('he_35'),
        he100=Sum('he_100'),
    )

    he_total = (
        (rco_stats['he25'] or Decimal('0')) +
        (rco_stats['he35'] or Decimal('0')) +
        (rco_stats['he100'] or Decimal('0'))
    )

    descarga_url = (
        reverse('asistencia_exportar_s10')
        + f'?anio={periodo.anio}&mes={periodo.mes}'
    )

    try:
        exporter = CargaS10Exporter(periodo.anio, periodo.mes, config)
        buffer = exporter.generar()
        tam_kb = len(buffer.getvalue()) / 1024
        filas = getattr(exporter, 'total_filas', 0)
    except Exception as exc:
        return {
            'estado': 'ERROR',
            'mensaje': f'La CargaS10 no se pudo generar: {exc}',
            'detalles': [
                f'Período HE: {inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
                'Corrige el error antes de cerrar el período.',
            ],
            'datos': {},
        }

    estado = 'OK' if filas else 'ADVERTENCIA'
    mensaje = (
        f'Carga S10 generada — {filas} trabajadores, {he_total:.1f}h HE'
        if filas else
        'CargaS10 generada sin filas: no hay tareo RCO en el período.'
    )
    return {
        'estado': estado,
        'mensaje': mensaje,
        'detalles': [
            f'Período HE: {inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
            f'Filas en el archivo: {filas} ({tam_kb:.1f} KB)',
            f'Trabajadores RCO con tareo: {rco_stats["personas"] or 0}',
            f'HE 25%: {rco_stats["he25"] or 0:.2f}h',
            f'HE 35%: {rco_stats["he35"] or 0:.2f}h',
            f'HE 100%: {rco_stats["he100"] or 0:.2f}h',
        ],
        'datos': {
            'personas': rco_stats['personas'] or 0,
            'he_total': float(he_total),
            'filas': filas,
            'descarga_url': descarga_url,
        },
    }


def _paso_reporte_cierre(periodo):
    from asistencia.models import RegistroTareo, BancoHoras, ConfiguracionSistema
    from django.db.models import Sum, Count, Q
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_he(periodo.anio, periodo.mes)

    resumen = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin,
    ).aggregate(
        total=Count('id'),
        trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR'])),
        faltas=Count('id', filter=Q(codigo_dia='FA')),
        he25=Sum('he_25'),
        he35=Sum('he_35'),
        he100=Sum('he_100'),
    )

    banco_total = BancoHoras.objects.filter(
        periodo_anio=periodo.anio, periodo_mes=periodo.mes,
    ).aggregate(saldo=Sum('saldo_horas'))

    return {
        'estado': 'OK',
        'mensaje': f'Reporte generado — {resumen["total"]} registros, {resumen["trabajados"]} días trabajados',
        'detalles': [
            f'Total registros: {resumen["total"]}',
            f'Días trabajados: {resumen["trabajados"]}',
            f'Faltas (FA): {resumen["faltas"]}',
            f'HE Total: {((resumen["he25"] or 0) + (resumen["he35"] or 0) + (resumen["he100"] or 0)):.1f}h',
            f'Saldo banco STAFF: {banco_total["saldo"] or 0:.1f}h',
        ],
        'datos': {
            'total': resumen['total'],
            'trabajados': resumen['trabajados'],
            'faltas': resumen['faltas'],
        },
    }


def _paso_bloquear_periodo(periodo):
    periodo.estado = 'CERRADO'
    periodo.cerrado_en = timezone.now()
    periodo.save(update_fields=['estado', 'cerrado_en'])

    return {
        'estado': 'OK',
        'mensaje': f'Período {periodo.mes_nombre} {periodo.anio} cerrado y bloqueado',
        'detalles': [
            f'Fecha de cierre: {periodo.cerrado_en.strftime("%d/%m/%Y %H:%M")}',
            'Los registros de asistencia quedan protegidos contra modificaciones',
            'Para reabrir, usa la acción "Reabrir período" en la lista de períodos',
        ],
        'datos': {'cerrado_en': periodo.cerrado_en.isoformat()},
    }


_EJECUTORES = {
    'VERIFICAR_IMPORTACIONES': _paso_verificar_importaciones,
    'VALIDAR_DNI':             _paso_validar_dni,
    'VERIFICAR_SS':            _paso_verificar_ss,
    'ASEGURAR_BANCO':          _paso_asegurar_banco,
    'GENERAR_CARGA_S10':       _paso_generar_carga_s10,
    'REPORTE_CIERRE':          _paso_reporte_cierre,
    'BLOQUEAR_PERIODO':        _paso_bloquear_periodo,
}
