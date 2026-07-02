"""
Feriados efectivos: FeriadoCalendario ± traslados de CompensacionFeriado.

Un traslado (D.S. que mueve el descanso de un feriado a otro día) se
parametriza en CompensacionFeriado: `fecha_feriado` se trabaja normal y
`fecha_compensada` toma el tratamiento de feriado. Este helper es la
única fuente que deben consultar los procesadores de tareo (P9: sin
comandos hardcodeados por año).
"""


def feriados_efectivos(fecha_ini=None, fecha_fin=None) -> set:
    """Set de fechas con tratamiento de feriado, con traslados aplicados.

    Sin argumentos devuelve todos los feriados activos; con rango, solo
    los que caen dentro (los traslados se evalúan también contra el rango).
    """
    from asistencia.models import CompensacionFeriado, FeriadoCalendario

    qs = FeriadoCalendario.objects.filter(activo=True)
    if fecha_ini:
        qs = qs.filter(fecha__gte=fecha_ini)
    if fecha_fin:
        qs = qs.filter(fecha__lte=fecha_fin)
    feriados = set(qs.values_list('fecha', flat=True))

    for comp in CompensacionFeriado.objects.filter(activo=True):
        feriados.discard(comp.fecha_feriado)
        f = comp.fecha_compensada
        if (fecha_ini is None or f >= fecha_ini) and \
                (fecha_fin is None or f <= fecha_fin):
            feriados.add(f)
    return feriados
