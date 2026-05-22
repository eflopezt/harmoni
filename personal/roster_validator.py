"""
Validador de Roster Quincenal Gastronomico.

DS 003-97-TR Art. 25:
- Todo trabajador tiene derecho a 24 horas continuas de descanso semanal,
  preferentemente domingo.
- En la practica: minimo 1 dia libre cada 7 dias rodantes.
- Maximo 6 dias consecutivos de trabajo.
"""
from datetime import timedelta


def validar_roster_quincena(personal, fecha_inicio, fecha_fin):
    """
    Valida el roster de una persona en un rango de fechas (quincena tipica).

    Reglas:
      - Min 1 dia libre cada 7 dias rodantes
      - No mas de 6 dias consecutivos de trabajo

    Args:
        personal: instancia Personal
        fecha_inicio: date
        fecha_fin: date

    Returns:
        dict:
            {
                'valido': bool,
                'errores': [
                    {'fecha': date, 'mensaje': str, 'severidad': 'error'|'warning'},
                    ...
                ],
            }
    """
    from .models import AsignacionRosterQuincena

    if fecha_inicio > fecha_fin:
        return {'valido': True, 'errores': []}

    # Cargamos un buffer adicional de 6 dias hacia atras para evaluar continuidad
    # que viene desde antes del rango.
    fecha_buffer = fecha_inicio - timedelta(days=6)
    asignaciones = (
        AsignacionRosterQuincena.objects
        .filter(personal=personal, fecha__gte=fecha_buffer, fecha__lte=fecha_fin)
        .select_related('turno')
    )

    # Map fecha -> es_trabajo (bool). Si no existe asignacion, asumimos trabajo
    # (modelo actual: ausencia = trabajo por defecto). Si turno is None -> libre.
    por_fecha = {}
    for a in asignaciones:
        por_fecha[a.fecha] = (a.turno_id is not None)

    errores = []
    fecha = fecha_inicio
    while fecha <= fecha_fin:
        # Ventana rodante de 7 dias terminando en `fecha`
        ventana_inicio = fecha - timedelta(days=6)
        dias_trabajo_7 = 0
        dias_libres_7 = 0
        for offset in range(7):
            f = ventana_inicio + timedelta(days=offset)
            es_trabajo = por_fecha.get(f, True)  # default: trabaja
            if es_trabajo:
                dias_trabajo_7 += 1
            else:
                dias_libres_7 += 1

        if dias_libres_7 == 0:
            errores.append({
                'fecha': fecha,
                'mensaje': (
                    f'7 dias consecutivos de trabajo sin descanso '
                    f'(ventana {ventana_inicio.isoformat()} a {fecha.isoformat()}). '
                    f'DS 003-97-TR Art. 25 exige minimo 1 dia libre cada 7 dias.'
                ),
                'severidad': 'error',
            })

        fecha += timedelta(days=1)

    # Detectar tambien rachas > 6 dias consecutivos explicitamente
    racha = 0
    racha_inicio = None
    fecha = fecha_buffer
    while fecha <= fecha_fin:
        es_trabajo = por_fecha.get(fecha, True)
        if es_trabajo:
            if racha == 0:
                racha_inicio = fecha
            racha += 1
            if racha == 7 and fecha >= fecha_inicio:
                errores.append({
                    'fecha': fecha,
                    'mensaje': (
                        f'Racha de 7+ dias consecutivos de trabajo iniciada el '
                        f'{racha_inicio.isoformat()}. Maximo legal: 6 dias seguidos.'
                    ),
                    'severidad': 'error',
                })
        else:
            racha = 0
            racha_inicio = None
        fecha += timedelta(days=1)

    return {
        'valido': len(errores) == 0,
        'errores': errores,
    }


def quincena_rango(anio, quincena):
    """
    Devuelve (fecha_inicio, fecha_fin) de la quincena:
      - 1 -> dias 1..15
      - 2 -> dia 16..fin_de_mes (depende del mes/anio)
    Si se pasa quincena entera (ej. 3 para mes 2 q1), usa anio/quincena modular.

    Args:
        anio: int
        quincena: 1-24 (1 = enero-q1, 2 = enero-q2, 3 = febrero-q1, ...)

    Returns:
        (fecha_inicio, fecha_fin, mes, sub_quincena, anio_efectivo)
    """
    import calendar
    from datetime import date

    # Normalizar quincena 1..24 -> mes 1..12 y sub_quincena 1..2
    q = ((quincena - 1) % 24) + 1
    mes = ((q - 1) // 2) + 1
    sub_q = ((q - 1) % 2) + 1
    anio_efectivo = anio + ((quincena - 1) // 24)

    if sub_q == 1:
        ini = date(anio_efectivo, mes, 1)
        fin = date(anio_efectivo, mes, 15)
    else:
        ultimo_dia = calendar.monthrange(anio_efectivo, mes)[1]
        ini = date(anio_efectivo, mes, 16)
        fin = date(anio_efectivo, mes, ultimo_dia)

    return ini, fin, mes, sub_q, anio_efectivo
