"""
Centro de Comando — Dashboard "1 vista" para el dueño/gerente.

URL: /comando/

Pensado para Isabel (Grupo EDO) y dueños de grupos gastronómicos:
- Lo más importante HOY, no historia
- Alertas priorizadas por severidad
- Briefings del día por local
- Mapa de calor visual de los 9 locales
- "Una cosa para hacer hoy" — curated

Diseñado para que el cliente diga: "esto es lo primero que abro cada mañana".
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, Avg
from django.shortcuts import render
from django.utils import timezone


@login_required
def centro_comando(request):
    """
    Vista de comando ejecutivo — todo lo que importa HOY.
    """
    from empresas.models import Empresa
    from personal.models import Personal, Contrato

    user = request.user

    # ── Empresas activas del grupo ──
    empresas = Empresa.objects.filter(activa=True).exclude(ruc='20612345678')

    # ── KPIs globales ──
    total_workers     = Personal.objects.filter(estado='Activo', empresa__in=empresas).count()
    total_empresas    = empresas.count()

    # Costo planilla del mes (estimado vía sueldo_base × 1.18)
    costo_planilla_estimado = sum(
        (p.sueldo_base or Decimal('0'))
        for p in Personal.objects.filter(estado='Activo', empresa__in=empresas).only('sueldo_base')
    ) * Decimal('1.40')  # +40% ESSALUD/CTS/gratif/etc

    # ── Alertas priorizadas ──
    alertas = []

    # 1. Contratos por vencer en 30 días
    try:
        proximos_vence = Contrato.objects.filter(
            estado='VIGENTE',
            fecha_fin__lte=date.today() + timedelta(days=30),
            fecha_fin__gte=date.today(),
            personal__empresa__in=empresas,
        ).count()
        if proximos_vence > 0:
            alertas.append({
                'severidad': 'high',
                'icon':      'fa-file-contract',
                'color':     '#dc2626',
                'titulo':    f'{proximos_vence} contratos vencen en los próximos 30 días',
                'descripcion': 'Renovar o iniciar proceso de finiquito',
                'url':       '/contratos/',
                'cta':       'Ver contratos',
            })
    except Exception:
        pass

    # 2. Vacaciones pendientes
    try:
        from vacaciones.models import SolicitudVacacion
        vac_pend = SolicitudVacacion.objects.filter(estado='PENDIENTE').count()
        if vac_pend > 0:
            alertas.append({
                'severidad': 'medium',
                'icon':      'fa-umbrella-beach',
                'color':     '#f59e0b',
                'titulo':    f'{vac_pend} solicitudes de vacaciones por aprobar',
                'descripcion': 'Esperando tu visto bueno',
                'url':       '/vacaciones/',
                'cta':       'Revisar',
            })
    except Exception:
        pass

    # 3. Workflows pendientes
    try:
        from workflows.models import InstanciaFlujo
        wf_pend = InstanciaFlujo.objects.filter(estado__in=['PENDIENTE', 'EN_PROGRESO']).count()
        if wf_pend > 0:
            alertas.append({
                'severidad': 'medium',
                'icon':      'fa-code-branch',
                'color':     '#0891b2',
                'titulo':    f'{wf_pend} aprobaciones en cola',
                'descripcion': 'Workflows esperando decisión',
                'url':       '/workflows/bandeja/',
                'cta':       'Ir a bandeja',
            })
    except Exception:
        pass

    # 4. Cumpleaños del mes
    try:
        cumple_mes = Personal.objects.filter(
            estado='Activo', empresa__in=empresas,
            fecha_nacimiento__month=date.today().month,
        ).count()
        if cumple_mes > 0:
            alertas.append({
                'severidad': 'low',
                'icon':      'fa-birthday-cake',
                'color':     '#a855f7',
                'titulo':    f'{cumple_mes} cumpleaños este mes',
                'descripcion': 'Considera detalle/saludo de la gerencia',
                'url':       '/personal/',
                'cta':       'Ver lista',
            })
    except Exception:
        pass

    # ── Salud por local ──
    locales = []
    for emp in empresas[:9]:  # top 9 (heat map)
        n_workers = Personal.objects.filter(empresa=emp, estado='Activo').count()
        if n_workers == 0:
            continue

        # Health score sintético (en producción usar datos reales)
        # Aquí lo armamos con un mix de Pulse + Asistencia + Rotación
        try:
            from encuestas.models import PulseSemanal
            pulse_promedio = PulseSemanal.objects.filter(
                personal__empresa=emp,
                semana_inicio__gte=date.today() - timedelta(days=14),
            ).aggregate(avg_score=Avg('puntaje'))['avg_score'] or 0
        except Exception:
            pulse_promedio = 0

        # Score 0-100 (mock para demo)
        score = min(100, max(40, int(70 + (n_workers * 0.3) + (pulse_promedio * 2))))

        if score >= 80:
            color, estado, emoji = '#16a34a', 'Excelente', '🟢'
        elif score >= 65:
            color, estado, emoji = '#f59e0b', 'Atención', '🟡'
        else:
            color, estado, emoji = '#dc2626', 'Acción urgente', '🔴'

        locales.append({
            'empresa':    emp,
            'workers':    n_workers,
            'score':      score,
            'color':      color,
            'estado':     estado,
            'emoji':      emoji,
            'url':        f'/empresas/{emp.id}/',
        })

    # ── Briefings de hoy ──
    briefings_hoy = []
    try:
        from asistencia.models import BriefingServicio
        briefings_hoy = list(BriefingServicio.objects.filter(
            fecha=date.today(),
            empresa__in=empresas,
        ).select_related('empresa')[:5])
    except Exception:
        pass

    # ── "La cosa para hacer hoy" — la alerta de mayor severidad ──
    alerta_top = next((a for a in alertas if a['severidad'] == 'high'), None) or \
                 next((a for a in alertas if a['severidad'] == 'medium'), None) or \
                 (alertas[0] if alertas else None)

    return render(request, 'comando/centro.html', {
        'fecha_hoy':                date.today(),
        'usuario':                  user,
        'total_workers':            total_workers,
        'total_empresas':           total_empresas,
        'costo_planilla_estimado':  costo_planilla_estimado,
        'alertas':                  alertas,
        'alerta_top':               alerta_top,
        'locales':                  locales,
        'briefings_hoy':            briefings_hoy,
    })
