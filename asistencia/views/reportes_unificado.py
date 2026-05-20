"""
Panel unificado de reportes de asistencia.

Reemplaza al menú disperso de reportes con un único panel de 3 tabs:

    SEMANA       — semana lunes-domingo (datepicker o dropdown de 8 últimas)
    MES          — mes calendario completo
    MES DE CORTE — ciclo 22→21 (período de planilla)

Cada tab comparte los mismos filtros (área, grupo, trabajador) y las
mismas acciones (ver HTML, descargar PDF/ZIP, descargar Excel, enviar
por email).

Las URLs legacy (``asistencia_reportes``, ``asistencia_reportes_areas``,
``asistencia_exportar_panel`` y demás) siguen vivas para mantener
compatibilidad con código existente.
"""
from __future__ import annotations

from datetime import date

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from asistencia.services.periodo_helper import (
    Periodo,
    TIPO_MES,
    TIPO_MES_CORTE,
    TIPO_SEMANA,
    get_periodo,
)
from asistencia.views._common import solo_admin
from personal.models import Area


def _empresa_dict() -> dict:
    """Devuelve dict mínimo con datos de empresa para el template.

    Lee ``ConfiguracionSistema`` de forma defensiva: si no hay registro o
    falla, retorna un dict vacío (el template hará fallback a "Reporte de
    Asistencia"). NO hardcodear ningún cliente específico.
    """
    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.get()
        return {
            'razon_social': (cfg.empresa_nombre or '').strip(),
            'ruc': (cfg.ruc or '').strip(),
            'email': (cfg.empresa_email or '').strip(),
        }
    except Exception:
        return {}


def _ultimas_semanas(n: int = 8) -> list[Periodo]:
    """Lista de las últimas `n` semanas (lunes-domingo) descendiente."""
    hoy = date.today()
    return [
        get_periodo(TIPO_SEMANA, hoy.year, hoy.month, semana_offset=-i)
        for i in range(n)
    ]


def _meses_recientes() -> list[tuple[int, int, str]]:
    """Lista de los últimos 18 meses, retorna (anio, mes, label)."""
    from asistencia.services.periodo_helper import _MESES_ES
    hoy = date.today()
    out = []
    anio, mes = hoy.year, hoy.month
    for _ in range(18):
        out.append((anio, mes, f'{_MESES_ES[mes]} {anio}'))
        mes -= 1
        if mes == 0:
            mes = 12
            anio -= 1
    return out


@login_required
@solo_admin
def panel(request):
    """Render del panel unificado con los 3 tabs."""
    hoy = date.today()

    # Tipo seleccionado: SEMANA | MES | MES_CORTE
    tipo_sel = (request.GET.get('tipo') or TIPO_MES_CORTE).upper()
    if tipo_sel not in (TIPO_SEMANA, TIPO_MES, TIPO_MES_CORTE):
        tipo_sel = TIPO_MES_CORTE

    # Período calculado para el preview (defaults razonables)
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
        semana_offset = int(request.GET.get('semana_offset', 0))
    except (ValueError, TypeError):
        anio, mes, semana_offset = hoy.year, hoy.month, 0

    try:
        periodo_actual = get_periodo(tipo_sel, anio, mes, semana_offset)
    except ValueError:
        periodo_actual = get_periodo(TIPO_MES_CORTE, hoy.year, hoy.month)

    # Filtros compartidos
    grupo_sel = request.GET.get('grupo', 'TODOS')
    area_sel = request.GET.get('area', '')

    empresa = _empresa_dict()

    # Flag: mostrar reportes legacy de obras (banco horas STAFF, etc.)
    # `es_consorcio_obras` no existe en el modelo — fallback a superuser.
    mostrar_legacy = bool(getattr(request.user, 'is_superuser', False))
    # Si en el futuro se agrega `request.empresa.es_consorcio_obras`,
    # actualizar esta línea:
    if hasattr(request, 'empresa') and getattr(request.empresa, 'es_consorcio_obras', False):
        mostrar_legacy = True

    context = {
        'titulo': 'Reportes de Asistencia',
        'empresa': empresa,
        'tipo_sel': tipo_sel,
        'periodo_actual': periodo_actual,
        'anio': anio,
        'mes': mes,
        'semana_offset': semana_offset,
        'grupo_sel': grupo_sel,
        'area_sel': area_sel,
        'areas': Area.objects.filter(activa=True).order_by('nombre'),
        'semanas_recientes': _ultimas_semanas(8),
        'meses_recientes': _meses_recientes(),
        'anios': list(range(hoy.year - 2, hoy.year + 1)),
        'mostrar_legacy': mostrar_legacy,
        # Constantes para template
        'TIPO_SEMANA': TIPO_SEMANA,
        'TIPO_MES': TIPO_MES,
        'TIPO_MES_CORTE': TIPO_MES_CORTE,
    }
    return render(request, 'asistencia/reportes_panel_unificado.html', context)
