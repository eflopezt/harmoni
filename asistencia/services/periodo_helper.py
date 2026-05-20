"""
Helper unificado de período para reportes de asistencia.

Tres tipos oficiales:

    SEMANA      Semana ISO (lunes a domingo). Útil para reportes operativos.
    MES         Mes calendario completo (1 al último día del mes).
    MES_CORTE   Ciclo de planilla 22→21 (22 mes anterior al 21 del mes).

Todos los reportes del módulo Asistencia deben construir su rango de
fechas vía :func:`get_periodo` para evitar inconsistencias.

Ejemplos
--------
>>> get_periodo('MES_CORTE', 2026, 5)
Periodo(tipo='MES_CORTE',
        fecha_inicio=date(2026, 4, 22),
        fecha_fin=date(2026, 5, 21),
        label='Mes de corte 22-Abr al 21-May 2026')

>>> get_periodo('MES', 2026, 5)
Periodo(tipo='MES',
        fecha_inicio=date(2026, 5, 1),
        fecha_fin=date(2026, 5, 31),
        label='Mayo 2026')

>>> get_periodo('SEMANA', 2026, 5, 0)   # semana actual del mes
Periodo(tipo='SEMANA', fecha_inicio=..., fecha_fin=..., label='Semana ...')
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

# Tipos válidos
TIPO_SEMANA = 'SEMANA'
TIPO_MES = 'MES'
TIPO_MES_CORTE = 'MES_CORTE'
TIPOS_VALIDOS = (TIPO_SEMANA, TIPO_MES, TIPO_MES_CORTE)

_MESES_ES = [
    '', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]
_MESES_ES_CORTO = [
    '', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
]


@dataclass(frozen=True)
class Periodo:
    """Resultado canónico de :func:`get_periodo`.

    Attributes
    ----------
    tipo : str
        Uno de ``'SEMANA'``, ``'MES'``, ``'MES_CORTE'``.
    fecha_inicio : date
        Primer día del período (inclusive).
    fecha_fin : date
        Último día del período (inclusive).
    label : str
        Etiqueta legible para mostrar en UI / PDF.
    """
    tipo: str
    fecha_inicio: date
    fecha_fin: date
    label: str

    @property
    def dias(self) -> int:
        return (self.fecha_fin - self.fecha_inicio).days + 1

    def __iter__(self):
        """Permite ``ini, fin = periodo``."""
        yield self.fecha_inicio
        yield self.fecha_fin


def _semana_lunes(d: date) -> date:
    """Devuelve el lunes (weekday=0) de la semana que contiene `d`."""
    return d - timedelta(days=d.weekday())


def _ciclo_corte(anio: int, mes: int) -> tuple[date, date]:
    """Devuelve (inicio, fin) del ciclo 22→21 para (anio, mes).

    Lee el día de corte desde ``ConfiguracionSistema`` si está disponible;
    si no, usa 22→21 por defecto.

    Ejemplo: mes=5, anio=2026 → (22/04/2026, 21/05/2026).
    """
    try:
        from asistencia.models import ConfiguracionSistema  # local import: evita ciclo
        cfg = ConfiguracionSistema.get()
        return cfg.get_ciclo_he(anio, mes)
    except Exception:
        # Fallback defensivo: corte clásico 22→21.
        if mes == 1:
            inicio = date(anio - 1, 12, 22)
        else:
            inicio = date(anio, mes - 1, 22)
        fin = date(anio, mes, 21)
        return inicio, fin


def get_periodo(tipo: str,
                anio: int | None = None,
                mes: int | None = None,
                semana_offset: int = 0) -> Periodo:
    """Construye un :class:`Periodo` consistente para el tipo solicitado.

    Parameters
    ----------
    tipo : str
        ``'SEMANA'`` | ``'MES'`` | ``'MES_CORTE'``.
    anio : int, optional
        Año. Si se omite, usa el año de hoy.
    mes : int, optional
        Mes 1-12. Requerido para ``MES`` y ``MES_CORTE``. Para ``SEMANA``
        sirve para anclar la semana dentro de ese mes; si se omite, usa
        el mes actual.
    semana_offset : int, default 0
        Solo para ``SEMANA``. Desplazamiento en semanas relativo a la
        "semana actual" del mes (la que contiene hoy si aplica, o la
        primera semana del mes/año pedido en caso contrario). Negativo
        para semanas previas, positivo para posteriores.

        - ``semana_offset=0``  → semana que contiene hoy (o la primera
          del mes/año pedido si la fecha actual no cae en ese mes).
        - ``semana_offset=-1`` → semana anterior.

    Returns
    -------
    Periodo

    Raises
    ------
    ValueError
        Si `tipo` no está en :data:`TIPOS_VALIDOS` o falta `mes` cuando
        se requiere.
    """
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(
            f'Tipo de período inválido: {tipo!r}. '
            f'Esperado uno de {TIPOS_VALIDOS}.'
        )

    hoy = date.today()
    if anio is None:
        anio = hoy.year

    if tipo == TIPO_SEMANA:
        # Anclar al lunes correspondiente.
        if mes is None:
            mes = hoy.month
        # Si el mes/año coincide con hoy, anclamos en hoy; si no, en el
        # primer día del mes solicitado.
        if anio == hoy.year and mes == hoy.month:
            anclaje = hoy
        else:
            anclaje = date(anio, mes, 1)

        lunes = _semana_lunes(anclaje) + timedelta(weeks=semana_offset)
        domingo = lunes + timedelta(days=6)

        # Label: "Semana 18-24 May 2026" o "Semana 30 Abr - 6 May 2026"
        if lunes.month == domingo.month and lunes.year == domingo.year:
            label = (
                f'Semana {lunes.day}-{domingo.day} '
                f'{_MESES_ES_CORTO[lunes.month]} {lunes.year}'
            )
        else:
            label = (
                f'Semana {lunes.day} {_MESES_ES_CORTO[lunes.month]}'
                f' - {domingo.day} {_MESES_ES_CORTO[domingo.month]} {domingo.year}'
            )
        return Periodo(TIPO_SEMANA, lunes, domingo, label)

    if tipo == TIPO_MES:
        if mes is None:
            raise ValueError('Tipo MES requiere parámetro `mes`.')
        if not 1 <= mes <= 12:
            raise ValueError(f'Mes fuera de rango: {mes}')
        inicio = date(anio, mes, 1)
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        fin = date(anio, mes, ultimo_dia)
        label = f'{_MESES_ES[mes]} {anio}'
        return Periodo(TIPO_MES, inicio, fin, label)

    # MES_CORTE
    if mes is None:
        raise ValueError('Tipo MES_CORTE requiere parámetro `mes`.')
    if not 1 <= mes <= 12:
        raise ValueError(f'Mes fuera de rango: {mes}')
    inicio, fin = _ciclo_corte(anio, mes)
    label = (
        f'Mes de corte {inicio.day:02d}-{_MESES_ES_CORTO[inicio.month]} '
        f'al {fin.day:02d}-{_MESES_ES_CORTO[fin.month]} {fin.year}'
    )
    return Periodo(TIPO_MES_CORTE, inicio, fin, label)


def get_periodo_desde_request(request, default_tipo: str = TIPO_MES_CORTE) -> Periodo:
    """Construye un :class:`Periodo` leyendo parámetros de un request.

    Lee ``tipo_periodo``, ``anio``, ``mes`` y ``semana_offset`` del GET.
    Acepta variantes legacy (``tipo_periodo=corte``/``calendario``) para
    mantener compatibilidad con vistas previas.
    """
    raw_tipo = (request.GET.get('tipo_periodo', '') or '').strip().upper()
    legacy = {
        'CORTE': TIPO_MES_CORTE,
        'CALENDARIO': TIPO_MES,
        'MENSUAL': TIPO_MES,
        'SEMANAL': TIPO_SEMANA,
    }
    tipo = legacy.get(raw_tipo, raw_tipo or default_tipo)

    hoy = date.today()
    try:
        anio = int(request.GET.get('anio', hoy.year))
    except (ValueError, TypeError):
        anio = hoy.year
    try:
        mes = int(request.GET.get('mes', hoy.month))
    except (ValueError, TypeError):
        mes = hoy.month
    try:
        semana_offset = int(request.GET.get('semana_offset', 0))
    except (ValueError, TypeError):
        semana_offset = 0

    return get_periodo(tipo, anio, mes, semana_offset)
