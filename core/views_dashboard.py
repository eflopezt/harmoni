"""
Core — Dashboard Ejecutivo Unificado.

Vista cross-módulo para CEO/Director del Grupo. Combina KPIs de:
  - personal (headcount, áreas, evolución)
  - nominas (PeriodoNomina total_neto, historial)
  - reclutamiento (vacantes, postulaciones, funnel, conversion)
  - asistencia (BriefingServicio del día, RegistroPapeleta pendientes)
  - capacitaciones (CertificacionTrabajador POR_VENCER/VENCIDA, próx. eventos)
  - empresas (locales activos)

Diseño defensivo: cada bloque intenta su query y si falla (import error,
campo faltante, módulo desactivado) cae a 0/lista vacía para que el
dashboard nunca rompa.
"""
from __future__ import annotations

import logging
from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger('core.views_dashboard')


# ── Constantes de UI ──────────────────────────────────────────────────
MESES_ES_CORTOS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                   'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

# Color por defecto cuando la etapa de pipeline no tiene color asignado
COLOR_DEFAULT_ETAPA = '#94a3b8'


# ── Helpers ───────────────────────────────────────────────────────────

def _safe(func, default=None):
    """Ejecuta func() y devuelve default si lanza cualquier excepción."""
    try:
        return func()
    except Exception as exc:  # noqa: BLE001
        logger.warning('dashboard_ejecutivo: bloque falló: %s', exc)
        return default


def _ultimos_n_meses(n: int, hoy: date) -> list[tuple[int, int, str]]:
    """Lista de (anio, mes, label) para los últimos N meses ordenados crono."""
    anchors: list[tuple[int, int]] = []
    y, m = hoy.year, hoy.month
    for _ in range(n):
        anchors.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    anchors.reverse()
    return [(y, m, f'{MESES_ES_CORTOS[m - 1]} {str(y)[2:]}') for y, m in anchors]


# ── Vista principal ───────────────────────────────────────────────────

@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='login')
def dashboard_ejecutivo(request):
    """Dashboard ejecutivo unificado para CEO/Director."""
    hoy = timezone.localdate()
    inicio_mes = hoy.replace(day=1)
    seis_meses = _ultimos_n_meses(6, hoy)

    # Filtro opcional por empresa
    empresa_pk = request.GET.get('empresa') or ''
    try:
        empresa_filtro = int(empresa_pk) if empresa_pk else None
    except (TypeError, ValueError):
        empresa_filtro = None

    # ──────────────────────────────────────────────────────────────
    # 1. EMPRESAS (locales activos)
    # ──────────────────────────────────────────────────────────────
    def _empresas_lista():
        from empresas.models import Empresa
        return list(
            Empresa.objects.filter(activa=True)
            .order_by('razon_social')
            .values('id', 'razon_social', 'nombre_comercial')
        )

    empresas = _safe(_empresas_lista, default=[])
    empresas_activas = len(empresas)

    # ──────────────────────────────────────────────────────────────
    # 2. PERSONAL (activo, áreas, evolución)
    # ──────────────────────────────────────────────────────────────
    def _personal_base():
        from personal.models import Personal
        qs = Personal.objects.filter(estado='Activo')
        if empresa_filtro:
            qs = qs.filter(empresa_id=empresa_filtro)
        return qs

    personal_activo = _safe(lambda: _personal_base().count(), default=0)

    # Distribución por área (top 8)
    def _personal_por_area():
        qs = _personal_base()
        rows = (
            qs.values('subarea__area__nombre')
            .annotate(total=Count('id'))
            .order_by('-total')[:8]
        )
        return [
            {
                'area': r['subarea__area__nombre'] or 'Sin área',
                'total': r['total'],
            }
            for r in rows
        ]

    personal_por_area = _safe(_personal_por_area, default=[])

    # Evolución de headcount últimos 6 meses (acumulado de fecha_alta - cesados)
    def _headcount_evolucion():
        from personal.models import Personal
        labels, valores = [], []
        for anio, mes, label in seis_meses:
            # Último día del mes
            if mes == 12:
                fin = date(anio + 1, 1, 1) - timedelta(days=1)
            else:
                fin = date(anio, mes + 1, 1) - timedelta(days=1)
            qs = Personal.objects.filter(fecha_alta__lte=fin)
            qs = qs.filter(
                Q(fecha_cese__isnull=True) | Q(fecha_cese__gt=fin)
            )
            if empresa_filtro:
                qs = qs.filter(empresa_id=empresa_filtro)
            labels.append(label)
            valores.append(qs.count())
        return {'labels': labels, 'valores': valores}

    headcount_evolucion = _safe(
        _headcount_evolucion,
        default={'labels': [l for _, _, l in seis_meses], 'valores': [0] * 6},
    )

    # ──────────────────────────────────────────────────────────────
    # 3. NÓMINA (mes actual + histórico)
    # ──────────────────────────────────────────────────────────────
    def _nomina_mes():
        from nominas.models import PeriodoNomina
        qs = (
            PeriodoNomina.objects
            .filter(estado__in=['CALCULADO', 'APROBADO', 'CERRADO'])
            .order_by('-anio', '-mes', '-id')
        )
        if empresa_filtro:
            qs = qs.filter(empresa_id=empresa_filtro)
        periodo = qs.first()
        if not periodo:
            return {'monto': Decimal('0'), 'anio': hoy.year, 'mes': hoy.month,
                    'mes_label': MESES_ES_CORTOS[hoy.month - 1], 'estado': '—'}
        return {
            'monto': periodo.total_neto or Decimal('0'),
            'anio': periodo.anio,
            'mes': periodo.mes,
            'mes_label': MESES_ES_CORTOS[periodo.mes - 1],
            'estado': periodo.get_estado_display(),
        }

    nomina_mes = _safe(
        _nomina_mes,
        default={'monto': Decimal('0'), 'anio': hoy.year, 'mes': hoy.month,
                 'mes_label': MESES_ES_CORTOS[hoy.month - 1], 'estado': '—'},
    )

    def _nomina_historico():
        from nominas.models import PeriodoNomina
        labels, valores = [], []
        for anio, mes, label in seis_meses:
            qs = PeriodoNomina.objects.filter(
                anio=anio, mes=mes,
                estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
            )
            if empresa_filtro:
                qs = qs.filter(empresa_id=empresa_filtro)
            agg = qs.aggregate(total=Sum('total_neto'))
            valores.append(float(agg['total'] or 0))
            labels.append(label)
        return {'labels': labels, 'valores': valores}

    nomina_historico = _safe(
        _nomina_historico,
        default={'labels': [l for _, _, l in seis_meses], 'valores': [0] * 6},
    )

    # ──────────────────────────────────────────────────────────────
    # 4. RECLUTAMIENTO (vacantes, postulaciones, funnel, métricas)
    # ──────────────────────────────────────────────────────────────
    def _vacantes_abiertas():
        from reclutamiento.models import Vacante
        return Vacante.objects.filter(
            estado__in=['PUBLICADA', 'EN_PROCESO']
        ).count()

    vacantes_abiertas = _safe(_vacantes_abiertas, default=0)

    def _postulaciones_mes():
        from reclutamiento.models import Postulacion
        return Postulacion.objects.filter(
            fecha_postulacion__year=hoy.year,
            fecha_postulacion__month=hoy.month,
        ).count()

    postulaciones_mes = _safe(_postulaciones_mes, default=0)

    def _contrataciones_mes():
        from reclutamiento.models import Postulacion
        return Postulacion.objects.filter(
            estado='CONTRATADA',
            fecha_postulacion__year=hoy.year,
            fecha_postulacion__month=hoy.month,
        ).count()

    contrataciones_mes = _safe(_contrataciones_mes, default=0)

    # Conversion rate del mes
    conversion_rate = 0.0
    if postulaciones_mes > 0:
        conversion_rate = round(
            (contrataciones_mes / postulaciones_mes) * 100, 1
        )

    # Funnel: candidatos activos por etapa
    def _funnel_etapas():
        from reclutamiento.models import EtapaPipeline
        etapas = (
            EtapaPipeline.objects.filter(activa=True)
            .annotate(total=Count(
                'postulaciones',
                filter=Q(postulaciones__estado='ACTIVA'),
            ))
            .order_by('orden')[:6]
        )
        return [
            {
                'nombre': e.nombre,
                'color': e.color or COLOR_DEFAULT_ETAPA,
                'total': e.total or 0,
            }
            for e in etapas
        ]

    funnel_etapas = _safe(_funnel_etapas, default=[])

    # Tiempo promedio de contratación (días entre postulación y CONTRATADA)
    def _tiempo_avg_contratacion():
        from reclutamiento.models import Postulacion
        contratadas = Postulacion.objects.filter(
            estado='CONTRATADA',
            personal_creado__isnull=False,
        ).select_related('personal_creado').order_by('-fecha_postulacion')[:50]
        dias = []
        for p in contratadas:
            if p.personal_creado and p.personal_creado.fecha_alta:
                fecha_alta = p.personal_creado.fecha_alta
                fecha_post = p.fecha_postulacion.date()
                delta = (fecha_alta - fecha_post).days
                if 0 <= delta <= 365:
                    dias.append(delta)
        if not dias:
            return 0
        return round(sum(dias) / len(dias))

    tiempo_avg_contratacion = _safe(_tiempo_avg_contratacion, default=0)

    # Top 3 vacantes con más candidatos activos
    def _top_vacantes():
        from reclutamiento.models import Vacante
        return list(
            Vacante.objects.filter(estado__in=['PUBLICADA', 'EN_PROCESO'])
            .annotate(
                activos=Count(
                    'postulaciones',
                    filter=Q(postulaciones__estado='ACTIVA'),
                )
            )
            .order_by('-activos')[:3]
            .values('id', 'titulo', 'estado', 'activos')
        )

    top_vacantes = _safe(_top_vacantes, default=[])

    # Postulaciones por mes — chart bar
    def _postulaciones_historico():
        from reclutamiento.models import Postulacion
        labels, valores = [], []
        for anio, mes, label in seis_meses:
            cnt = Postulacion.objects.filter(
                fecha_postulacion__year=anio,
                fecha_postulacion__month=mes,
            ).count()
            labels.append(label)
            valores.append(cnt)
        return {'labels': labels, 'valores': valores}

    postulaciones_historico = _safe(
        _postulaciones_historico,
        default={'labels': [l for _, _, l in seis_meses], 'valores': [0] * 6},
    )

    # ──────────────────────────────────────────────────────────────
    # 5. ASISTENCIA / OPERACIÓN (briefings, papeletas)
    # ──────────────────────────────────────────────────────────────
    def _briefings_hoy():
        from asistencia.models import BriefingServicio
        publicados = BriefingServicio.objects.filter(
            fecha=hoy, estado='PUBLICADO'
        )
        if empresa_filtro:
            publicados = publicados.filter(empresa_id=empresa_filtro)
        # contar empresas distintas que publicaron
        publicados_count = publicados.values('empresa_id').distinct().count()
        return publicados_count

    briefings_hoy = _safe(_briefings_hoy, default=0)

    def _papeletas_pendientes():
        from asistencia.models import RegistroPapeleta
        return RegistroPapeleta.objects.filter(estado='PENDIENTE').count()

    papeletas_pendientes = _safe(_papeletas_pendientes, default=0)

    # ──────────────────────────────────────────────────────────────
    # 6. CAPACITACIONES & CERTIFICACIONES
    # ──────────────────────────────────────────────────────────────
    def _capacitaciones_proximas():
        from capacitaciones.models import Capacitacion
        en_30 = hoy + timedelta(days=30)
        return Capacitacion.objects.filter(
            fecha_inicio__gte=hoy, fecha_inicio__lte=en_30,
            estado__in=['PROGRAMADA', 'EN_CURSO'],
        ).count()

    capacitaciones_proximas = _safe(_capacitaciones_proximas, default=0)

    def _certificaciones_estado():
        from capacitaciones.models import CertificacionTrabajador
        por_vencer = CertificacionTrabajador.objects.filter(
            estado='POR_VENCER'
        ).count()
        vencidas = CertificacionTrabajador.objects.filter(
            estado='VENCIDA'
        ).count()
        return {'por_vencer': por_vencer, 'vencidas': vencidas}

    certs = _safe(
        _certificaciones_estado, default={'por_vencer': 0, 'vencidas': 0}
    )

    # ──────────────────────────────────────────────────────────────
    # 7. ALERTAS URGENTES
    # ──────────────────────────────────────────────────────────────
    alertas: list[dict] = []

    if certs['vencidas'] > 0:
        alertas.append({
            'tipo': 'danger',
            'icono': 'fa-triangle-exclamation',
            'titulo': f'{certs["vencidas"]} certificación(es) vencidas',
            'detalle': 'BPM/HACCP/SSOMA fuera de vigencia — riesgo legal y fiscal',
        })
    if certs['por_vencer'] > 0:
        alertas.append({
            'tipo': 'warning',
            'icono': 'fa-clock',
            'titulo': f'{certs["por_vencer"]} certificación(es) por vencer',
            'detalle': 'Vencen en los próximos 30 días',
        })

    # Vacantes sin actividad > 30 días
    def _vacantes_estancadas():
        from reclutamiento.models import Vacante
        lim = hoy - timedelta(days=30)
        return Vacante.objects.filter(
            estado__in=['PUBLICADA', 'EN_PROCESO'],
            actualizado_en__date__lt=lim,
        ).count()

    vacantes_estancadas = _safe(_vacantes_estancadas, default=0)
    if vacantes_estancadas > 0:
        alertas.append({
            'tipo': 'warning',
            'icono': 'fa-hourglass-half',
            'titulo': f'{vacantes_estancadas} vacante(s) sin actividad >30 días',
            'detalle': 'Revisar pipeline o reasignar responsable',
        })

    # Postulaciones estancadas > 14 días sin nota
    def _postulaciones_estancadas():
        from reclutamiento.models import Postulacion
        lim = timezone.now() - timedelta(days=14)
        # Las que no tienen notas recientes
        return Postulacion.objects.filter(
            estado='ACTIVA',
            fecha_postulacion__lt=lim,
        ).exclude(
            notas_detalle__fecha__gte=lim,
        ).count()

    postulaciones_estancadas = _safe(_postulaciones_estancadas, default=0)
    if postulaciones_estancadas > 0:
        alertas.append({
            'tipo': 'info',
            'icono': 'fa-user-clock',
            'titulo': f'{postulaciones_estancadas} postulación(es) estancadas',
            'detalle': 'Más de 14 días sin actualización en la misma etapa',
        })

    # Briefings sin publicar hoy
    if empresas_activas and briefings_hoy < empresas_activas:
        faltantes = empresas_activas - briefings_hoy
        alertas.append({
            'tipo': 'warning',
            'icono': 'fa-bullhorn',
            'titulo': f'{faltantes} local(es) sin briefing publicado hoy',
            'detalle': f'{briefings_hoy} de {empresas_activas} locales con briefing del día',
        })

    if papeletas_pendientes > 0:
        alertas.append({
            'tipo': 'info',
            'icono': 'fa-file-pen',
            'titulo': f'{papeletas_pendientes} papeleta(s) pendientes',
            'detalle': 'Esperando aprobación de RRHH o jefe de área',
        })

    # ──────────────────────────────────────────────────────────────
    # CONTEXT
    # ──────────────────────────────────────────────────────────────
    context = {
        'hoy': hoy,
        'empresa_filtro': empresa_filtro,
        'empresas': empresas,
        # Headline cards
        'kpi_personal_activo': personal_activo,
        'kpi_empresas_activas': empresas_activas,
        'kpi_nomina_mes': nomina_mes,
        'kpi_vacantes_abiertas': vacantes_abiertas,
        'kpi_postulaciones_mes': postulaciones_mes,
        'kpi_contrataciones_mes': contrataciones_mes,
        # Reclutamiento
        'conversion_rate': conversion_rate,
        'tiempo_avg_contratacion': tiempo_avg_contratacion,
        'funnel_etapas': funnel_etapas,
        'top_vacantes': top_vacantes,
        # Asistencia / Op
        'briefings_hoy': briefings_hoy,
        'papeletas_pendientes': papeletas_pendientes,
        'capacitaciones_proximas': capacitaciones_proximas,
        'certs_por_vencer': certs['por_vencer'],
        'certs_vencidas': certs['vencidas'],
        # Charts (serializados como JSON-safe lists)
        'chart_postulaciones': postulaciones_historico,
        'chart_personal_areas': personal_por_area,
        'chart_headcount': headcount_evolucion,
        'chart_nomina': nomina_historico,
        # Alertas
        'alertas': alertas,
    }
    return render(request, 'core/dashboard_ejecutivo.html', context)
