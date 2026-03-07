"""
Vistas de inicio y logout.
"""
from django.shortcuts import render, redirect
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from datetime import date, timedelta
from django.db.models import Count, Q, Sum
import json

from ..models import Area, SubArea, Personal, Roster
from ..permissions import (
    filtrar_areas, filtrar_subareas, filtrar_personal,
    get_context_usuario
)


# ── Frase del día ──────────────────────────────────────────────────────────────

def _get_frase_dia(hoy: date) -> dict:
    """
    Retorna una frase contextual según el calendario laboral peruano.
    Prioriza eventos próximos; si no hay ninguno, usa sabiduría RRHH
    rotatoria por día del año.
    """
    # ── 1. Calcular Día de la Madre y Padre (domingos móviles) ────────────
    def _nth_sunday(year, month, n):
        """Retorna el n-ésimo domingo del mes/año (1-based)."""
        d = date(year, month, 1)
        d += timedelta(days=(6 - d.weekday()) % 7)  # primer domingo
        return d + timedelta(weeks=n - 1)

    dia_madre = _nth_sunday(hoy.year, 5, 2)   # 2.° domingo de mayo
    dia_padre = _nth_sunday(hoy.year, 6, 3)   # 3.° domingo de junio

    # ── 2. Catálogo de eventos ────────────────────────────────────────────
    # Cada entrada: (fecha, ventana_antes, ventana_despues, nombre, frases, icono, color)
    EVENTOS = [
        (date(hoy.year, 1, 1), 3, 2,
         "Año Nuevo",
         [f"Año nuevo, mismo gran equipo — con metas aún más altas. ¡Bienvenidos al {hoy.year}!",
          "El inicio del año es el mejor momento para renovar el compromiso con las personas."],
         "fa-star", "#0f766e"),

        (date(hoy.year, 3, 8), 10, 2,
         "Día Internacional de la Mujer",
         ["La equidad de género no se declara, se construye todos los días. Hoy lo celebramos.",
          "Nuestras colaboradoras mueven el mundo. Hoy es el momento perfecto para reconocerlo.",
          "Una organización que valora a sus mujeres, valora su futuro."],
         "fa-venus", "#db2777"),

        (date(hoy.year, 5, 1), 14, 3,
         "Día del Trabajador",
         ["El 1° de mayo nos recuerda que detrás de cada indicador hay una historia humana. ¡Celebremos al equipo!",
          "Se acerca el día más importante del calendario laboral — ¡estoy emocionado de planear la celebración!",
          "El trabajo no solo construye empresas, construye personas. ¡Feliz Día del Trabajador!",
          "El mejor homenaje al Día del Trabajo es escuchar a nuestro equipo. ¿Ya tienes algo planeado?"],
         "fa-hard-hat", "#d97706"),

        (dia_madre, 10, 1,
         "Día de la Madre",
         ["Muchas de nuestras colaboradoras son madres. Hoy es el día de reconocer esa fortaleza doble.",
          "El mejor beneficio que podemos dar es flexibilidad para quienes además son mamás. ¡Feliz día!"],
         "fa-heart", "#ec4899"),

        (dia_padre, 7, 1,
         "Día del Padre",
         ["A todos los papás del equipo: gracias por la entrega doble, en casa y en el trabajo.",
          "Ser padre y colaborador es un acto de balance diario. Hoy los reconocemos."],
         "fa-child", "#0891b2"),

        (date(hoy.year, 6, 29), 5, 1,
         "San Pedro y San Pablo",
         ["Feriado a la vista — el equipo se lo ha ganado. ¡Que recarguen energías!"],
         "fa-church", "#7c3aed"),

        (date(hoy.year, 7, 28), 12, 3,
         "Fiestas Patrias",
         ["¡Tan peruanos como nuestro equipo! Que disfruten el descanso y vuelvan con energía renovada.",
          "El orgullo de ser peruanos se siente también en cómo tratamos a nuestra gente. ¡Viva el Perú!",
          "Fiestas Patrias: el momento ideal para agradecer al equipo por todo el año."],
         "fa-flag", "#dc2626"),

        (date(hoy.year, 8, 30), 5, 1,
         "Santa Rosa de Lima",
         ["Un feriado más para el equipo. La calidad de vida también se mide en días de descanso bien ganados."],
         "fa-sun", "#d97706"),

        (date(hoy.year, 10, 8), 5, 1,
         "Combate de Angamos",
         ["Recordar nuestra historia nos recuerda quiénes somos como equipo y como país."],
         "fa-anchor", "#0f766e"),

        (date(hoy.year, 11, 1), 4, 1,
         "Día de Todos los Santos",
         ["Un momento para reflexionar y agradecer a quienes nos acompañaron en el camino."],
         "fa-candle-holder", "#6366f1"),

        (date(hoy.year, 12, 9), 5, 1,
         "Batalla de Ayacucho",
         ["La libertad también se construye en las organizaciones, con respeto y oportunidades reales."],
         "fa-shield-alt", "#dc2626"),

        (date(hoy.year, 12, 25), 15, 4,
         "Navidad",
         ["La mejor época del año para agradecer a cada persona del equipo por su entrega y dedicación.",
          "Navidad nos recuerda que las grandes organizaciones se construyen con pequeños gestos de humanidad.",
          "Fin de año: el momento más poderoso para reconocer logros y sembrar expectativas positivas."],
         "fa-snowflake", "#0891b2"),

        (date(hoy.year, 12, 31), 5, 1,
         "Fin de Año",
         ["Un año más de logros y aprendizajes juntos. ¡El balance es positivo!",
          "Cada cierre de año es también un comienzo. ¿Qué historia escribiremos juntos el próximo?"],
         "fa-glass-cheers", "#7c3aed"),
    ]

    # ── 3. Buscar evento próximo o en curso ───────────────────────────────
    # Artículo correcto por evento (default "el")
    _ART = {
        "Fiestas Patrias":          "las",
        "Navidad":                  "la",
        "Batalla de Ayacucho":      "la",
        "Día de la Madre":          "el",
        "San Pedro y San Pablo":    "",
        "Santa Rosa de Lima":       "",
    }
    for (fecha_e, antes, despues, nombre, frases, icono, color) in EVENTOS:
        delta = (fecha_e - hoy).days
        if -despues <= delta <= antes:
            art = _ART.get(nombre, "el")
            nombre_con_art = f"{art} {nombre}".strip()
            if delta > 1:
                comentario = f"Faltan {delta} días para {nombre_con_art}"
            elif delta == 1:
                comentario = f"¡Mañana es {nombre_con_art}!"
            elif delta == 0:
                comentario = f"¡Hoy es {nombre_con_art}!"
            else:
                comentario = f"¡{nombre}!"
            frase = frases[hoy.timetuple().tm_yday % len(frases)]
            return {'evento': nombre, 'comentario': comentario,
                    'frase': frase, 'icono': icono, 'color': color}

    # ── 4. Sin evento especial — sabiduría RRHH rotatoria ─────────────────
    FRASES_RRHH = [
        ("Las personas no son recursos — son el propósito.", "fa-heart", "#0f766e"),
        ("Un equipo comprometido supera cualquier estrategia perfecta.", "fa-handshake", "#0891b2"),
        ("El bienestar del colaborador no es un beneficio, es una inversión.", "fa-seedling", "#059669"),
        ("Contratar bien es el acto de gestión más importante que existe.", "fa-user-check", "#7c3aed"),
        ("La cultura no se declara, se vive en cada decisión pequeña.", "fa-building", "#0f766e"),
        ("Un 'gracias' a tiempo vale más que cualquier bono.", "fa-award", "#d97706"),
        ("El mejor indicador de clima laboral es cuando la gente llega sonriendo.", "fa-smile", "#10b981"),
        ("Desarrollar personas es la única ventaja que nadie puede copiar.", "fa-chart-line", "#0891b2"),
        ("El onboarding termina cuando la persona se siente verdaderamente en casa.", "fa-home", "#059669"),
        ("La rotación no es un problema de personas — es un espejo de la organización.", "fa-sync-alt", "#ef4444"),
        ("Medir el desempeño sin retroalimentar es como pesar al paciente sin medicarle.", "fa-balance-scale", "#7c3aed"),
        ("Una conversación honesta a tiempo previene una renuncia inesperada.", "fa-comments", "#0f766e"),
        ("El liderazgo no se ejerce desde el cargo, se ejerce desde la confianza.", "fa-user-shield", "#0891b2"),
        ("Diversidad sin inclusión es decoración. Inclusión sin equidad es teatro.", "fa-users", "#059669"),
        ("El error más caro en RRHH es esperar a que alguien bueno se vaya para valorarlo.", "fa-exclamation-circle", "#d97706"),
        ("Flexibilidad no es sinónimo de caos — es sinónimo de confianza.", "fa-random", "#0f766e"),
        ("El salario emocional es lo que hace que la gente se quede cuando otra empresa paga más.", "fa-brain", "#7c3aed"),
        ("Un proceso de selección justo es el primer mensaje cultural que envías.", "fa-clipboard-check", "#0891b2"),
        ("Las políticas rígidas alejan a los mejores y retienen a los más conformistas.", "fa-file-contract", "#ef4444"),
        ("El propósito no se cuelga en una pared — se siente en el trato diario.", "fa-compass", "#059669"),
    ]

    # Día de semana: comentario motivacional
    MOTS_SEMANA = {
        0: "Lunes — el mejor momento para arrancar con intención.",
        1: "Martes — el día más productivo de la semana según la ciencia.",
        2: "Miércoles — mitad del camino, todo el impulso por delante.",
        3: "Jueves — un día más para hacer algo que importe.",
        4: "Viernes — bien hecho esta semana, equipo.",
        5: "Sábado — algunos trabajan hoy también. ¡Gracias!",
        6: "Domingo — mañana volvemos a construir.",
    }

    frase, icono, color = FRASES_RRHH[hoy.timetuple().tm_yday % len(FRASES_RRHH)]
    return {
        'evento': None,
        'comentario': MOTS_SEMANA[hoy.weekday()],
        'frase': frase,
        'icono': icono,
        'color': color,
    }


@login_required
def home(request):
    """Vista principal del sistema — Dashboard contextual.

    Si el usuario NO es staff/superuser y NO tiene áreas a cargo,
    se lo redirige al Portal del Colaborador (su espacio personal).
    """
    # ── Redirección automática a portal para trabajadores sin rol RRHH ──
    if not request.user.is_staff and not request.user.is_superuser:
        if not filtrar_areas(request.user).exists():
            return redirect('portal_home')

    hoy = date.today()

    # Filtros según rol del usuario
    gerencias_filtradas = filtrar_areas(request.user)
    areas_filtradas = filtrar_subareas(request.user)
    personal_filtrado = filtrar_personal(request.user)
    personal_activo = personal_filtrado.filter(estado='Activo')
    total_activos = personal_activo.count()

    # ── KPIs base ──
    _dist = {d['grupo_tareo']: d['n']
             for d in personal_activo.values('grupo_tareo').annotate(n=Count('id'))}
    context = {
        'total_gerencias': gerencias_filtradas.filter(activa=True).count(),
        'total_areas': areas_filtradas.filter(activa=True).count(),
        'total_personal': total_activos,
        'staff_count': _dist.get('STAFF', 0),
        'rco_count':   _dist.get('RCO',   0),
        'total_roster_hoy': Roster.objects.filter(
            fecha=hoy, personal__in=personal_filtrado,
        ).count(),
    }

    # ── Asistencia HOY (solo admin/responsable) ──
    if request.user.is_superuser or gerencias_filtradas.exists():
        from asistencia.models import RegistroTareo
        tareo_hoy = RegistroTareo.objects.filter(
            fecha=hoy, personal__in=personal_activo,
        )
        asistencia_hoy = tareo_hoy.aggregate(
            total=Count('id'),
            # SS = Sin Salida → persona PRESENTE (llegó pero no marcó salida)
            trabajando=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS'])),
            faltas=Count('id', filter=Q(codigo_dia__in=['FA', 'LSG'])),
            permisos=Count('id', filter=Q(codigo_dia__in=[
                'V', 'DL', 'DLA', 'DM', 'LCG', 'LF', 'LP', 'LM',
                'CAP', 'CT', 'CHE', 'CDT', 'CPF', 'ATM',
            ])),
            ss=Count('id', filter=Q(codigo_dia='SS')),  # sub-conteo para nota
        )
        context['asistencia_hoy'] = asistencia_hoy
        context['sin_registro_hoy'] = total_activos - (asistencia_hoy['total'] or 0)

    # ── Papeletas y Solicitudes HE pendientes (este mes) ──
    if request.user.is_superuser or gerencias_filtradas.exists():
        from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje

        inicio_mes = hoy.replace(day=1)

        pap_stats = RegistroPapeleta.objects.filter(
            personal__in=personal_activo,
            creado_en__date__gte=inicio_mes,
        ).aggregate(
            total_mes=Count('id'),
            pendientes=Count('id', filter=Q(estado='PENDIENTE')),
        )

        sol_stats = SolicitudHE.objects.filter(
            personal__in=personal_activo,
            creado_en__date__gte=inicio_mes,
        ).aggregate(
            total_mes=Count('id'),
            pendientes=Count('id', filter=Q(estado='PENDIENTE')),
        )

        just_stats = JustificacionNoMarcaje.objects.filter(
            personal__in=personal_activo,
            creado_en__date__gte=inicio_mes,
        ).aggregate(
            total_mes=Count('id'),
            pendientes=Count('id', filter=Q(estado='PENDIENTE')),
        )

        context['pap_stats'] = pap_stats
        context['sol_stats'] = sol_stats
        context['just_stats'] = just_stats

        # ── Actividad reciente (últimos 7 días) ──
        hace_7d = hoy - timedelta(days=7)

        actividad = []

        # Papeletas recientes
        for p in RegistroPapeleta.objects.filter(
            creado_en__date__gte=hace_7d,
            personal__in=personal_activo,
        ).select_related('personal').order_by('-creado_en')[:5]:
            actividad.append({
                'icono': 'fa-file-alt',
                'color': '#0f766e',
                'texto': f'{p.personal.apellidos_nombres if p.personal else "?"} — {p.get_tipo_permiso_display()}',
                'estado': p.estado,
                'estado_display': p.get_estado_display(),
                'fecha': p.creado_en,
                'tipo': 'papeleta',
            })

        # Solicitudes HE recientes
        for s in SolicitudHE.objects.filter(
            creado_en__date__gte=hace_7d,
            personal__in=personal_activo,
        ).select_related('personal').order_by('-creado_en')[:5]:
            actividad.append({
                'icono': 'fa-clock',
                'color': '#7c3aed',
                'texto': f'{s.personal.apellidos_nombres} — HE {s.horas_estimadas}h ({s.get_tipo_display()})',
                'estado': s.estado,
                'estado_display': s.get_estado_display(),
                'fecha': s.creado_en,
                'tipo': 'solicitud_he',
            })

        # Justificaciones recientes
        for j in JustificacionNoMarcaje.objects.filter(
            creado_en__date__gte=hace_7d,
            personal__in=personal_activo,
        ).select_related('personal').order_by('-creado_en')[:5]:
            actividad.append({
                'icono': 'fa-clipboard-check',
                'color': '#ea580c',
                'texto': f'{j.personal.apellidos_nombres} — {j.get_tipo_display()}',
                'estado': j.estado,
                'estado_display': j.get_estado_display(),
                'fecha': j.creado_en,
                'tipo': 'justificacion',
            })

        # ── Préstamos en actividad reciente ──
        try:
            from prestamos.models import Prestamo
            for pr in Prestamo.objects.filter(
                creado_en__date__gte=hace_7d,
                personal__in=personal_activo,
            ).select_related('personal', 'tipo').order_by('-creado_en')[:5]:
                actividad.append({
                    'icono': 'fa-hand-holding-usd',
                    'color': '#7c3aed',
                    'texto': f'{pr.personal.apellidos_nombres} — {pr.tipo.nombre} S/ {pr.monto_efectivo:,.2f}',
                    'estado': pr.estado,
                    'estado_display': pr.get_estado_display(),
                    'fecha': pr.creado_en,
                    'tipo': 'prestamo',
                })
        except Exception:
            pass

        # Ordenar por fecha descendente y limitar
        actividad.sort(key=lambda x: x['fecha'], reverse=True)
        context['actividad_reciente'] = actividad[:8]

    # ── Préstamos stats (si módulo activo) ──
    if request.user.is_superuser:
        try:
            from prestamos.models import Prestamo
            from asistencia.models import ConfiguracionSistema
            config = ConfiguracionSistema.get()
            if config.mod_prestamos:
                prest_stats = Prestamo.objects.filter(
                    personal__in=personal_activo,
                ).aggregate(
                    total=Count('id'),
                    en_curso=Count('id', filter=Q(estado='EN_CURSO')),
                    pendientes=Count('id', filter=Q(estado='PENDIENTE')),
                    saldo_total=Sum('monto_aprobado', filter=Q(estado='EN_CURSO')),
                )
                context['prest_stats'] = prest_stats
        except Exception:
            pass

    # ── Documentos stats (si módulo activo) ──
    if request.user.is_superuser:
        try:
            from documentos.models import DocumentoTrabajador
            from asistencia.models import ConfiguracionSistema
            config = ConfiguracionSistema.get()
            if config.mod_documentos:
                doc_stats = DocumentoTrabajador.objects.filter(
                    personal__in=personal_activo,
                ).aggregate(
                    total=Count('id'),
                    vigentes=Count('id', filter=Q(estado='VIGENTE')),
                    por_vencer=Count('id', filter=Q(estado='POR_VENCER')),
                )
                context['doc_stats'] = doc_stats
        except Exception:
            pass

    # ── Nóminas: último período ──
    if request.user.is_superuser:
        try:
            from nominas.models import PeriodoNomina
            ultimo_periodo = PeriodoNomina.objects.filter(
                tipo='REGULAR', estado__in=['CALCULADO', 'APROBADO', 'CERRADO']
            ).order_by('-anio', '-mes').first()
            context['nominas_stats'] = {
                'periodo':      ultimo_periodo,
                'neto':         ultimo_periodo.total_neto if ultimo_periodo else None,
                'trabajadores': ultimo_periodo.total_trabajadores if ultimo_periodo else 0,
                'estado':       ultimo_periodo.get_estado_display() if ultimo_periodo else None,
            }
        except Exception:
            pass

    # ── Vacaciones y permisos pendientes ──
    if request.user.is_superuser:
        try:
            from vacaciones.models import SolicitudVacacion, SolicitudPermiso
            vac_pend = SolicitudVacacion.objects.filter(
                estado='PENDIENTE', personal__in=personal_activo).count()
            perm_pend = SolicitudPermiso.objects.filter(
                estado='PENDIENTE', personal__in=personal_activo).count()
            context['vacaciones_stats'] = {
                'vac_pendientes':  vac_pend,
                'perm_pendientes': perm_pend,
                'total':           vac_pend + perm_pend,
            }
        except Exception:
            pass

    # ── Contratos por vencer (próximos 30 días) ──
    if request.user.is_superuser:
        try:
            en_30_dias = hoy + timedelta(days=30)
            context['contratos_vencen'] = personal_activo.filter(
                fecha_fin_contrato__isnull=False,
                fecha_fin_contrato__gte=hoy,
                fecha_fin_contrato__lte=en_30_dias,
            ).count()
        except Exception:
            pass

    # ── Workflows pendientes para este usuario ──
    if request.user.is_authenticated:
        try:
            from workflows.services import get_pendientes_usuario
            pendientes_wf = get_pendientes_usuario(request.user)
            context['workflows_pendientes'] = pendientes_wf.count()
        except Exception:
            pass

    # ── Alertas RRHH activas (admin) ──
    if request.user.is_superuser:
        try:
            from analytics.models import AlertaRRHH
            alertas_activas = AlertaRRHH.objects.filter(activa=True)
            context['alertas_rrhh_total'] = alertas_activas.count()
            context['alertas_rrhh_critical'] = alertas_activas.filter(severidad='CRITICAL').count()
        except Exception:
            pass

    # ── Procesos disciplinarios activos (admin) ──
    if request.user.is_superuser:
        try:
            from disciplinaria.models import MedidaDisciplinaria
            disc_activos = MedidaDisciplinaria.objects.filter(
                estado__in=('BORRADOR', 'EN_DESCARGO', 'EN_RESOLUCION')
            ).count()
            context['disciplinaria_activos'] = disc_activos
        except Exception:
            pass

    # ── Evaluaciones pendientes de completar (admin) ──
    if request.user.is_superuser:
        try:
            from evaluaciones.models import Evaluacion
            eval_pendientes = Evaluacion.objects.filter(
                estado__in=('PENDIENTE', 'EN_PROGRESO')
            ).count()
            context['evaluaciones_pendientes'] = eval_pendientes
        except Exception:
            pass

    # ── Onboarding activos (admin) ──
    if request.user.is_superuser:
        try:
            from onboarding.models import ProcesoOnboarding
            context['onboarding_activos'] = ProcesoOnboarding.objects.filter(
                estado__in=('EN_PROCESO', 'PENDIENTE'), tipo='ONBOARDING'
            ).count()
            context['offboarding_activos'] = ProcesoOnboarding.objects.filter(
                estado__in=('EN_PROCESO', 'PENDIENTE'), tipo='OFFBOARDING'
            ).count()
        except Exception:
            pass

    # ── Encuestas activas (admin) ──
    if request.user.is_superuser:
        try:
            from encuestas.models import Encuesta
            context['encuestas_activas'] = Encuesta.objects.filter(estado='ACTIVA').count()
        except Exception:
            pass

    # ── Reclutamiento: vacantes + candidatos nuevos (admin) ──
    if request.user.is_superuser:
        try:
            from reclutamiento.models import Vacante, Postulacion
            context['reclutamiento_stats'] = {
                'vacantes_activas': Vacante.objects.filter(
                    estado__in=['PUBLICADA', 'ACTIVA']
                ).count(),
                'candidatos_mes': Postulacion.objects.filter(
                    creado_en__date__gte=hoy.replace(day=1)
                ).count(),
            }
        except Exception:
            pass

    # ── Attrition risk: empleados con score alto (admin) ──
    if request.user.is_superuser:
        try:
            en_30_dias = hoy + timedelta(days=30)
            riesgo_count = personal_activo.filter(
                Q(fecha_fin_contrato__isnull=False,
                  fecha_fin_contrato__lte=en_30_dias) |
                Q(sueldo_base__isnull=True) |
                Q(sueldo_base=0)
            ).count()
            context['attrition_riesgo'] = riesgo_count
        except Exception:
            pass

    # ── Viáticos CDT por conciliar (admin) ──
    if request.user.is_superuser:
        try:
            from viaticos.models import ViaticoCDT
            context['viaticos_por_conciliar'] = ViaticoCDT.objects.filter(
                estado__in=['ENTREGADO', 'EN_RENDICION']
            ).count()
        except Exception:
            pass

    # ── Bandas salariales: cobertura (admin) ──
    if request.user.is_superuser:
        try:
            from salarios.models import HistorialSalarial
            con_banda = personal_activo.filter(
                historial_salarial__banda_salarial__isnull=False
            ).distinct().count()
            context['bandas_cobertura'] = {
                'con_banda': con_banda,
                'sin_banda': total_activos - con_banda,
                'pct': round((con_banda / total_activos * 100) if total_activos else 0),
            }
        except Exception:
            pass

    # ── Capacitaciones del mes (admin) ──
    if request.user.is_superuser:
        try:
            from capacitaciones.models import Capacitacion
            inicio_mes = hoy.replace(day=1)
            context['capacitaciones_mes'] = Capacitacion.objects.filter(
                fecha__gte=inicio_mes, fecha__lte=hoy
            ).count()
        except Exception:
            pass

    # ── Headcount tendencia: altas/bajas este mes (admin) ──
    if request.user.is_superuser:
        try:
            inicio_mes = hoy.replace(day=1)
            altas_mes = Personal.objects.filter(
                fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy
            ).count()
            bajas_mes = Personal.objects.filter(
                fecha_baja__gte=inicio_mes, fecha_baja__lte=hoy
            ).count()
            context['headcount_tendencia'] = {
                'altas': altas_mes,
                'bajas': bajas_mes,
                'neto': altas_mes - bajas_mes,
            }
        except Exception:
            pass

    context.update(get_context_usuario(request.user))
    context['frase_dia'] = _get_frase_dia(hoy)
    return render(request, 'home.html', context)


def logout_view(request):
    """Vista personalizada de logout que acepta GET y POST."""
    auth_logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('login')


# ── Command Palette — búsqueda global ──────────────────────────────────────────

@login_required
@require_GET
def cmd_search(request):
    """
    AJAX endpoint para el Command Palette (Ctrl+K).
    Busca empleados por nombre o DNI + retorna acciones contextuales.
    """
    q = request.GET.get('q', '').strip()
    results = {'empleados': [], 'acciones': [], 'nav': []}

    if len(q) >= 2:
        # Búsqueda de empleados
        qs = filtrar_personal(request.user).filter(
            Q(apellidos_nombres__icontains=q) |
            Q(nro_doc__startswith=q) |
            Q(cargo__icontains=q)
        ).select_related('subarea__area')[:8]

        for p in qs:
            area_str = p.subarea.area.nombre if p.subarea else ''
            results['empleados'].append({
                'pk':     p.pk,
                'nombre': p.apellidos_nombres,
                'dni':    p.nro_doc,
                'cargo':  p.cargo or '',
                'area':   area_str,
                'estado': p.estado,
                'url':    f'/personal/{p.pk}/',
            })

        # Acciones rápidas contextuales
        if request.user.is_superuser:
            if any(k in q.lower() for k in ['nuevo', 'crear', 'agregar', 'alta']):
                results['acciones'].append({'label': 'Nuevo Empleado', 'url': '/personal/nuevo/', 'icon': 'fa-user-plus'})
            if any(k in q.lower() for k in ['import', 'cargar', 'subir', 'excel']):
                results['acciones'].append({'label': 'Importar Excel', 'url': '/personal/importar/', 'icon': 'fa-file-excel'})
            if any(k in q.lower() for k in ['alert', 'pend', 'aprob']):
                results['acciones'].append({'label': 'Aprobaciones pendientes', 'url': '/aprobaciones/', 'icon': 'fa-tasks'})
            if any(k in q.lower() for k in ['cese', 'baja', 'liquidac']):
                results['acciones'].append({'label': 'Panel de Cese', 'url': '/documentos/cese/', 'icon': 'fa-user-slash'})

    # Navegación estática siempre disponible (filtrar según query)
    nav_items = [
        {'label': 'Personal',     'url': '/personal/',           'icon': 'fa-users',          'keys': ['personal', 'empleado', 'trabajador', 'lista']},
        {'label': 'Asistencia',   'url': '/tareo/',              'icon': 'fa-fingerprint',    'keys': ['asistencia', 'tareo', 'marcacion', 'control']},
        {'label': 'Vacaciones',   'url': '/vacaciones/',         'icon': 'fa-umbrella-beach', 'keys': ['vacacion', 'permiso', 'licencia']},
        {'label': 'Analytics',    'url': '/analytics/',          'icon': 'fa-chart-bar',      'keys': ['analytics', 'dashboard', 'reporte', 'kpi']},
        {'label': 'Documentos',   'url': '/documentos/',         'icon': 'fa-folder-open',    'keys': ['documento', 'legajo', 'archivo']},
        {'label': 'Reclutamiento','url': '/reclutamiento/',      'icon': 'fa-briefcase',      'keys': ['reclut', 'vacante', 'candidato', 'seleccion']},
        {'label': 'Capacitaciones','url': '/capacitaciones/',    'icon': 'fa-graduation-cap', 'keys': ['capacit', 'curso', 'entrenamiento']},
        {'label': 'Evaluaciones', 'url': '/evaluaciones/',       'icon': 'fa-star',           'keys': ['evaluac', '360', 'desempeno', 'performan']},
        {'label': 'Préstamos',    'url': '/prestamos/',          'icon': 'fa-hand-holding-usd','keys': ['prestamo', 'adelanto', 'credito']},
        {'label': 'Encuestas',    'url': '/encuestas/',          'icon': 'fa-poll',           'keys': ['encuesta', 'clima', 'pulso', 'enps']},
        {'label': 'Configuración','url': '/configuracion/',      'icon': 'fa-cog',            'keys': ['config', 'parametro', 'feriado', 'ajuste']},
        {'label': 'Roster',       'url': '/personal/roster/',    'icon': 'fa-calendar-alt',   'keys': ['roster', 'turno', 'rotacion']},
        {'label': 'Salarios',     'url': '/salarios/',           'icon': 'fa-dollar-sign',    'keys': ['salario', 'sueldo', 'banda', 'remuneracion']},
        {'label': 'Disciplinaria','url': '/disciplinaria/',      'icon': 'fa-gavel',          'keys': ['disciplin', 'falta', 'sancion']},
        {'label': 'Onboarding',   'url': '/onboarding/',         'icon': 'fa-door-open',      'keys': ['onboard', 'ingreso', 'bienvenida', 'offboard']},
        {'label': 'Comunicaciones','url': '/comunicaciones/',    'icon': 'fa-bell',           'keys': ['comunicac', 'notificac', 'correo', 'enviar']},
        {'label': 'Viáticos',     'url': '/viaticos/',           'icon': 'fa-receipt',        'keys': ['viatico', 'cdt', 'viaje', 'gasto']},
        {'label': 'Calendario',   'url': '/calendario/',         'icon': 'fa-calendar-check', 'keys': ['calendario', 'feriado', 'evento']},
    ]

    q_lower = q.lower()
    if q_lower:
        for item in nav_items:
            if any(k in q_lower for k in item['keys']) or q_lower in item['label'].lower():
                results['nav'].append({'label': item['label'], 'url': item['url'], 'icon': item['icon']})
    else:
        # Sin query: mostrar todos los módulos de navegación
        results['nav'] = [{'label': i['label'], 'url': i['url'], 'icon': i['icon']} for i in nav_items]

    return JsonResponse(results)


# ── Smart Alertas del Día ────────────────────────────────────────────────────

@login_required
@require_GET
def alertas_dia(request):
    """
    AJAX: genera las alertas proactivas del día.
    El frontend las muestra en el home como cards dinámicas.
    """
    hoy = date.today()
    alertas = []

    personal_activo = filtrar_personal(request.user).filter(estado='Activo')

    # ── 1. Cumpleaños hoy ──────────────────────────────────────────────
    cump_hoy = personal_activo.filter(
        fecha_nacimiento__month=hoy.month,
        fecha_nacimiento__day=hoy.day,
    ).values('pk', 'apellidos_nombres', 'cargo', 'fecha_nacimiento')[:5]

    for p in cump_hoy:
        edad = hoy.year - p['fecha_nacimiento'].year
        alertas.append({
            'tipo':    'cumpleanios',
            'icono':   'fa-birthday-cake',
            'color':   '#ec4899',
            'titulo':  f'Cumpleaños — {p["apellidos_nombres"].split(",")[0]}',
            'detalle': f'Hoy cumple {edad} años · {p["cargo"] or ""}',
            'url':     f'/personal/{p["pk"]}/',
            'prioridad': 10,
        })

    # ── 2. Cumpleaños esta semana (próximos 7 días, excl. hoy) ─────────
    cump_semana = []
    for delta in range(1, 8):
        dia = hoy + timedelta(days=delta)
        ps = personal_activo.filter(
            fecha_nacimiento__month=dia.month,
            fecha_nacimiento__day=dia.day,
        ).values('pk', 'apellidos_nombres', 'cargo', 'fecha_nacimiento')
        for p in ps:
            cump_semana.append((dia, p))

    if cump_semana:
        nombres = ', '.join(p['apellidos_nombres'].split(',')[0] for _, p in cump_semana[:3])
        extra = f' y {len(cump_semana)-3} más' if len(cump_semana) > 3 else ''
        alertas.append({
            'tipo':    'cumpleanios_semana',
            'icono':   'fa-cake-candles',
            'color':   '#f472b6',
            'titulo':  f'{len(cump_semana)} cumpleaño{"s" if len(cump_semana)>1 else ""} esta semana',
            'detalle': nombres + extra,
            'url':     '/personal/?orden=cumple',
            'prioridad': 8,
        })

    # ── 3. Aniversarios de ingreso notables (hoy) ──────────────────────
    for anios in [20, 15, 10, 5, 1]:
        anio_ingreso = hoy.year - anios
        aniv = personal_activo.filter(
            fecha_alta__year=anio_ingreso,
            fecha_alta__month=hoy.month,
            fecha_alta__day=hoy.day,
        ).values('pk', 'apellidos_nombres', 'cargo')
        for p in aniv:
            emoji = '🏆' if anios >= 10 else '🎖️' if anios >= 5 else '🌟'
            alertas.append({
                'tipo':    'aniversario',
                'icono':   'fa-medal',
                'color':   '#f59e0b',
                'titulo':  f'{emoji} {anios} año{"s" if anios>1 else ""} en la empresa',
                'detalle': f'{p["apellidos_nombres"]}',
                'url':     f'/personal/{p["pk"]}/',
                'prioridad': 9,
            })

    # ── 4. Contratos vencen esta semana ────────────────────────────────
    try:
        prox_semana = hoy + timedelta(days=7)
        contratos_criticos = personal_activo.filter(
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=prox_semana,
            tipo_contrato='PLAZO_FIJO',
        ).count()
        if contratos_criticos:
            alertas.append({
                'tipo':    'contrato_vence',
                'icono':   'fa-file-contract',
                'color':   '#dc2626',
                'titulo':  f'{contratos_criticos} contrato{"s" if contratos_criticos>1 else ""} vence{"n" if contratos_criticos>1 else ""} esta semana',
                'detalle': 'Renovar antes del vencimiento para evitar discontinuidad',
                'url':     '/personal/contratos/',
                'prioridad': 15,
            })
    except Exception:
        pass

    # ── 5. Período de prueba termina esta semana ────────────────────────
    try:
        altas_prueba = personal_activo.filter(
            fecha_inicio_contrato__gte=hoy - timedelta(days=97),
            fecha_inicio_contrato__lte=hoy - timedelta(days=83),
        ).count()
        if altas_prueba:
            alertas.append({
                'tipo':    'periodo_prueba',
                'icono':   'fa-user-clock',
                'color':   '#7c3aed',
                'titulo':  f'{altas_prueba} período{"s" if altas_prueba>1 else ""} de prueba terminando',
                'detalle': 'Alrededor de 90 días desde el ingreso — evaluar continuidad',
                'url':     '/personal/contratos/',
                'prioridad': 12,
            })
    except Exception:
        pass

    # ── 6. Vacaciones acumuladas críticas (>30 días) ──────────────────
    try:
        from vacaciones.models import SaldoVacacional
        vac_criticos = SaldoVacacional.objects.filter(
            personal__in=personal_activo,
            dias_pendientes__gt=30,
        ).count()
        if vac_criticos:
            alertas.append({
                'tipo':    'vacaciones_acumuladas',
                'icono':   'fa-umbrella-beach',
                'color':   '#0891b2',
                'titulo':  f'{vac_criticos} empleado{"s" if vac_criticos>1 else ""} con +30 días acumulados',
                'detalle': 'Provisión de vacaciones en riesgo — planificar salidas',
                'url':     '/vacaciones/',
                'prioridad': 7,
            })
    except Exception:
        pass

    # ── 7. Sin AFP/pensión (STAFF con régimen AFP vacío) ──────────────
    try:
        sin_pension = personal_activo.filter(
            grupo_tareo='STAFF',
            regimen_pension='AFP',
            afp='',
        ).count()
        if sin_pension:
            alertas.append({
                'tipo':    'sin_afp',
                'icono':   'fa-shield-alt',
                'color':   '#64748b',
                'titulo':  f'{sin_pension} trabajador{"es" if sin_pension>1 else ""} sin AFP registrada',
                'detalle': 'Riesgo de aporte pensionario — completar datos',
                'url':     '/personal/?filtro=sin_afp',
                'prioridad': 6,
            })
    except Exception:
        pass

    # ── 8. Procesos disciplinarios sin resolución >15 días ────────────
    try:
        from disciplinaria.models import ProcesoDisciplinario
        limite = hoy - timedelta(days=15)
        disc_pendientes = ProcesoDisciplinario.objects.filter(
            personal__in=personal_activo,
            estado__in=['INICIADO', 'EN_DESCARGO'],
            fecha_inicio__lte=limite,
        ).count()
        if disc_pendientes:
            alertas.append({
                'tipo':    'disciplinaria',
                'icono':   'fa-gavel',
                'color':   '#b45309',
                'titulo':  f'{disc_pendientes} proceso{"s" if disc_pendientes>1 else ""} disciplinario{"s" if disc_pendientes>1 else ""} sin resolver',
                'detalle': 'Más de 15 días sin resolución — riesgo legal D.Leg. 728',
                'url':     '/disciplinaria/',
                'prioridad': 14,
            })
    except Exception:
        pass

    # Ordenar por prioridad descendente
    alertas.sort(key=lambda x: x['prioridad'], reverse=True)

    return JsonResponse({
        'alertas': alertas[:10],
        'total':   len(alertas),
        'fecha':   hoy.strftime('%d/%m/%Y'),
    })


# ─────────────────────────────────────────────────────────────────────────────
# ASISTENTE RRHH — Natural Language HR Q&A (sin Ollama)
# ─────────────────────────────────────────────────────────────────────────────

@login_required
@require_GET
def hr_ask(request):
    """
    Endpoint de Q&A de RRHH en lenguaje natural.
    Detecta intents via palabras clave y ejecuta queries reales contra la BD.
    Funciona 100% sin Ollama — detección determinista.

    GET /api/hr-ask/?q=cuantos+empleados+hay
    Retorna: {respuesta, tipo, datos, acciones, confianza}
    """
    q = request.GET.get('q', '').strip().lower()
    if not q:
        return JsonResponse({'error': 'Sin consulta.'}, status=400)

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    # ── Helpers de normalización ─────────────────────────────────────────────
    def kw(*keywords):
        return any(k in q for k in keywords)

    def _fmt_num(n):
        return f'{n:,}'.replace(',', ',')

    def _emp_list(qs, max_n=5):
        return [{'pk': e.pk, 'nombre': e.apellidos_nombres, 'cargo': e.cargo or ''} for e in qs[:max_n]]

    # ── Intent: Headcount total ───────────────────────────────────────────────
    if kw('cuántos', 'cuantos', 'total empleados', 'total de empleados', 'headcount',
          'cuántas personas', 'cuantas personas', 'total trabajadores'):
        activos = Personal.objects.filter(estado='Activo')
        total = activos.count()
        staff = activos.filter(grupo_tareo='STAFF').count()
        rco = activos.filter(grupo_tareo='RCO').count()
        cesados = Personal.objects.filter(estado='Cesado').count()
        return JsonResponse({
            'tipo': 'headcount',
            'respuesta': f'Actualmente hay **{total} colaboradores activos** — {staff} STAFF y {rco} RCO. Total histórico (incluye cesados): {total + cesados}.',
            'datos': {'total': total, 'staff': staff, 'rco': rco, 'cesados': cesados},
            'acciones': [{'label': 'Ver personal', 'url': '/personal/', 'icono': 'fa-users'}],
            'confianza': 'alta',
        })

    # ── Intent: Cumpleaños ───────────────────────────────────────────────────
    if kw('cumpleaños', 'cumpleanos', 'cumple', 'birthday'):
        hoy_md = (hoy.month, hoy.day)
        fin_semana = hoy + timedelta(days=7)
        cumple_hoy = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__month=hoy.month,
            fecha_nacimiento__day=hoy.day,
        )
        cumple_semana = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__isnull=False,
        ).extra(where=[
            "CAST(strftime('%m', fecha_nacimiento) AS INTEGER) = %s "
            "AND CAST(strftime('%d', fecha_nacimiento) AS INTEGER) BETWEEN %s AND %s"
        ], params=[hoy.month, hoy.day, min(hoy.day + 7, 31)]).exclude(
            fecha_nacimiento__month=hoy.month,
            fecha_nacimiento__day=hoy.day,
        )[:5]

        hoy_list = list(cumple_hoy)
        proximos = list(cumple_semana)

        if hoy_list:
            nombres = ', '.join(e.apellidos_nombres.split(',')[0] for e in hoy_list[:3])
            resp = f'🎂 ¡Hoy cumple{"n" if len(hoy_list)>1 else ""} años **{nombres}**'
            if len(hoy_list) > 3:
                resp += f' y {len(hoy_list)-3} más'
            resp += '.'
        else:
            resp = 'Nadie cumple años hoy.'

        if proximos:
            nombres_prox = ', '.join(e.apellidos_nombres.split(',')[0] for e in proximos[:3])
            resp += f' Esta semana: **{nombres_prox}**.'

        return JsonResponse({
            'tipo': 'cumpleanios',
            'respuesta': resp,
            'datos': {
                'hoy': _emp_list(cumple_hoy),
                'semana': _emp_list(cumple_semana),
            },
            'acciones': [{'label': 'Ver personal', 'url': '/personal/', 'icono': 'fa-birthday-cake'}],
            'confianza': 'alta',
        })

    # ── Intent: Contratos por vencer ─────────────────────────────────────────
    if kw('contrato', 'contratos', 'vence', 'vencen', 'por vencer', 'vencimiento'):
        en_30 = hoy + timedelta(days=30)
        en_60 = hoy + timedelta(days=60)
        c30 = Personal.objects.filter(estado='Activo', tipo_contrato='PLAZO_FIJO',
                                       fecha_fin_contrato__gte=hoy, fecha_fin_contrato__lte=en_30)
        c60 = Personal.objects.filter(estado='Activo', tipo_contrato='PLAZO_FIJO',
                                       fecha_fin_contrato__gt=en_30, fecha_fin_contrato__lte=en_60)
        resp = f'En los próximos 30 días vencen **{c30.count()} contratos**'
        if c60.count():
            resp += f', y {c60.count()} más en 31–60 días'
        resp += '.'
        if c30.count() == 0:
            resp = 'No hay contratos por vencer en los próximos 30 días. ✅'
        return JsonResponse({
            'tipo': 'contratos',
            'respuesta': resp,
            'datos': {
                'proximos_30d': c30.count(),
                'proximos_60d': c60.count(),
                'lista_urgente': _emp_list(c30.order_by('fecha_fin_contrato')),
            },
            'acciones': [
                {'label': 'Ver contratos', 'url': '/personal/contratos/', 'icono': 'fa-file-contract'},
            ],
            'confianza': 'alta',
        })

    # ── Intent: Ausentismo / faltas ──────────────────────────────────────────
    if kw('ausentismo', 'faltas', 'ausencias', 'inasistencias', 'faltaron', 'faltó'):
        try:
            from asistencia.models import RegistroTareo
            total_reg = RegistroTareo.objects.filter(fecha__gte=inicio_mes, fecha__lte=hoy).count()
            faltas = RegistroTareo.objects.filter(
                fecha__gte=inicio_mes, fecha__lte=hoy, codigo_dia__in=['F', 'FALTA']
            ).count()
            pct = round(faltas / total_reg * 100, 1) if total_reg else 0
            resp = f'Este mes el ausentismo es de **{pct}%** ({faltas} faltas de {total_reg} registros).'
            if pct > 8:
                resp += ' ⚠️ Nivel crítico — investigar causas.'
            elif pct > 4:
                resp += ' Nivel moderado.'
            else:
                resp += ' Nivel dentro de lo normal. ✅'
        except Exception:
            resp = 'No hay datos de asistencia disponibles para este mes.'
            faltas, total_reg, pct = 0, 0, 0
        return JsonResponse({
            'tipo': 'ausentismo',
            'respuesta': resp,
            'datos': {'faltas': faltas, 'total': total_reg, 'pct': pct},
            'acciones': [{'label': 'Ver asistencia', 'url': '/asistencia/', 'icono': 'fa-fingerprint'}],
            'confianza': 'alta',
        })

    # ── Intent: Altas del mes ────────────────────────────────────────────────
    if kw('nuevos', 'nuevas', 'ingresaron', 'altas', 'ingresos del mes', 'incorporaciones'):
        nuevos = Personal.objects.filter(fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy)
        n = nuevos.count()
        resp = f'Este mes ingresaron **{n} colaborador{"es" if n != 1 else ""}**'
        if n > 0:
            lista = list(nuevos.order_by('-fecha_alta')[:3])
            nombres = ', '.join(e.apellidos_nombres.split(',')[0] for e in lista)
            resp += f': {nombres}'
            if n > 3:
                resp += f' y {n-3} más'
        resp += '.'
        return JsonResponse({
            'tipo': 'altas',
            'respuesta': resp,
            'datos': {'n': n, 'lista': _emp_list(nuevos.order_by('-fecha_alta'))},
            'acciones': [{'label': 'Ver personal', 'url': '/personal/', 'icono': 'fa-user-plus'}],
            'confianza': 'alta',
        })

    # ── Intent: Bajas / cesados del mes ─────────────────────────────────────
    if kw('bajas', 'cesados', 'ceses', 'salidas', 'renuncias', 'renunciaron'):
        bajas = Personal.objects.filter(
            fecha_cese__gte=inicio_mes, fecha_cese__lte=hoy, estado='Cesado'
        )
        n = bajas.count()
        resp = f'Este mes se registraron **{n} baja{"s" if n != 1 else ""}**.'
        if n == 0:
            resp = 'No se han registrado bajas este mes. ✅'
        return JsonResponse({
            'tipo': 'bajas',
            'respuesta': resp,
            'datos': {'n': n},
            'acciones': [
                {'label': 'Ver cesados', 'url': '/personal/?estado=Cesado', 'icono': 'fa-user-minus'},
                {'label': 'Panel cese', 'url': '/documentos/cese/', 'icono': 'fa-file-pdf'},
            ],
            'confianza': 'alta',
        })

    # ── Intent: Distribución por área ───────────────────────────────────────
    if kw('área', 'area', 'áreas', 'areas', 'gerencia', 'gerencias', 'departamento'):
        from personal.models import Area as AreaModel
        activos = Personal.objects.filter(estado='Activo')
        areas_data = (
            activos.values('subarea__area__nombre')
            .annotate(n=Count('id'))
            .order_by('-n')
        )
        items = [{'area': r['subarea__area__nombre'] or 'Sin área', 'n': r['n']} for r in areas_data]
        total = sum(i['n'] for i in items)
        if items:
            top = items[0]
            resp = f'El equipo está distribuido en **{len(items)} áreas**. La más grande es **{top["area"]}** con {top["n"]} personas.'
        else:
            resp = 'No hay datos de distribución por área.'
        return JsonResponse({
            'tipo': 'areas',
            'respuesta': resp,
            'datos': {'areas': items, 'total': total},
            'acciones': [{'label': 'Ver áreas', 'url': '/personal/areas/', 'icono': 'fa-building'}],
            'confianza': 'alta',
        })

    # ── Intent: Riesgo de rotación ───────────────────────────────────────────
    if kw('riesgo', 'fuga', 'rotación', 'rotacion', 'attrition', 'van a irse', 'podrían irse'):
        try:
            en_60d = hoy + timedelta(days=60)
            activos = Personal.objects.filter(estado='Activo')
            total = activos.count()
            # Aproximación rápida: contratos por vencer + ausentismo alto
            riesgo_contratos = activos.filter(
                tipo_contrato='PLAZO_FIJO',
                fecha_fin_contrato__gte=hoy,
                fecha_fin_contrato__lte=en_60d,
            ).count()
            resp = (
                f'Existen señales de riesgo en al menos **{riesgo_contratos} empleados** '
                f'con contratos venciendo en 60 días. Para un análisis completo con '
                f'scoring multifactorial, visita el módulo de Riesgo de Fuga.'
            )
        except Exception:
            resp = 'No se pudo calcular el riesgo de rotación.'
            riesgo_contratos = 0
        return JsonResponse({
            'tipo': 'riesgo',
            'respuesta': resp,
            'datos': {'riesgo_contratos': riesgo_contratos},
            'acciones': [
                {'label': 'Riesgo de Fuga', 'url': '/analytics/attrition/', 'icono': 'fa-user-slash'},
                {'label': 'Predictive Insights', 'url': '/analytics/predictive/', 'icono': 'fa-brain'},
            ],
            'confianza': 'media',
        })

    # ── Intent: Vacaciones ───────────────────────────────────────────────────
    if kw('vacaciones', 'descanso', 'días pendientes', 'dias pendientes', 'saldo vacacional'):
        try:
            from vacaciones.models import SaldoVacacional, SolicitudVacaciones
            pendientes = SolicitudVacaciones.objects.filter(estado='PENDIENTE').count()
            criticos = SaldoVacacional.objects.filter(dias_pendientes__gt=30).count()
            resp = f'Hay **{pendientes} solicitud{"es" if pendientes!=1 else ""} de vacaciones pendientes** de aprobación.'
            if criticos:
                resp += f' Además, **{criticos} empleado{"s" if criticos!=1 else ""}** tiene{"n" if criticos!=1 else ""} más de 30 días acumulados sin tomar.'
        except Exception:
            resp = 'No hay datos de vacaciones disponibles.'
            pendientes, criticos = 0, 0
        return JsonResponse({
            'tipo': 'vacaciones',
            'respuesta': resp,
            'datos': {'pendientes': pendientes, 'criticos': criticos},
            'acciones': [{'label': 'Ver vacaciones', 'url': '/vacaciones/', 'icono': 'fa-umbrella-beach'}],
            'confianza': 'alta',
        })

    # ── Intent: Evaluaciones ─────────────────────────────────────────────────
    if kw('evaluaci', 'desempeño', 'desempeno', 'performance', '360', '9-box', 'calificaciones'):
        try:
            from evaluaciones.models import ProcesoEvaluacion
            activos_eval = ProcesoEvaluacion.objects.filter(estado__in=['EN_PROCESO', 'INICIADO']).count()
            resp = f'Hay **{activos_eval} proceso{"s" if activos_eval!=1 else ""} de evaluación en curso**.'
            if activos_eval == 0:
                resp = 'No hay procesos de evaluación activos en este momento.'
        except Exception:
            resp = 'No hay datos de evaluaciones disponibles.'
            activos_eval = 0
        return JsonResponse({
            'tipo': 'evaluaciones',
            'respuesta': resp,
            'datos': {'activos': activos_eval},
            'acciones': [{'label': 'Ver evaluaciones', 'url': '/evaluaciones/', 'icono': 'fa-star-half-alt'}],
            'confianza': 'alta',
        })

    # ── Intent: Planilla / nómina ────────────────────────────────────────────
    if kw('planilla', 'nómina', 'nomina', 'sueldo', 'sueldos', 'costo laboral', 'masa salarial'):
        try:
            from personal.models import Personal as P
            activos = P.objects.filter(estado='Activo', sueldo_base__isnull=False)
            total_planilla = sum(float(e.sueldo_base) for e in activos)
            promedio = total_planilla / activos.count() if activos.count() else 0
            resp = (
                f'La masa salarial mensual es de **S/ {total_planilla:,.2f}** '
                f'(promedio: S/ {promedio:,.2f} por colaborador).'
            )
        except Exception:
            resp = 'No hay datos salariales disponibles.'
            total_planilla, promedio = 0, 0
        return JsonResponse({
            'tipo': 'planilla',
            'respuesta': resp,
            'datos': {'total': total_planilla, 'promedio': promedio},
            'acciones': [
                {'label': 'Análisis salarial', 'url': '/analytics/salarios/', 'icono': 'fa-coins'},
                {'label': 'Nóminas', 'url': '/nominas/', 'icono': 'fa-file-invoice-dollar'},
            ],
            'confianza': 'alta',
        })

    # ── Intent: Ayuda / comandos disponibles ─────────────────────────────────
    if kw('ayuda', 'help', 'qué puedes', 'que puedes', 'cómo funciona', 'comandos'):
        return JsonResponse({
            'tipo': 'ayuda',
            'respuesta': (
                'Puedo responder preguntas sobre tu equipo. Prueba con:\n'
                '• **"¿Cuántos empleados hay?"** → headcount\n'
                '• **"¿Quién cumple años esta semana?"** → cumpleaños\n'
                '• **"¿Cuántos contratos vencen?"** → contratos\n'
                '• **"¿Cuál es el ausentismo?"** → asistencia\n'
                '• **"¿Cuántos ingresaron este mes?"** → altas\n'
                '• **"¿Cómo está el riesgo de rotación?"** → análisis predictivo\n'
                '• **"¿Cuánto es la masa salarial?"** → planilla\n'
                '• **"¿Cuántas vacaciones hay pendientes?"** → vacaciones'
            ),
            'datos': {},
            'acciones': [],
            'confianza': 'alta',
        })

    # ── Fallback: Sin coincidencia ───────────────────────────────────────────
    return JsonResponse({
        'tipo': 'sin_match',
        'respuesta': (
            'No entendí la consulta. Prueba con: '
            '"¿cuántos empleados hay?", "cumpleaños", "contratos por vencer", '
            '"ausentismo", "altas del mes", "riesgo de rotación"...'
        ),
        'datos': {},
        'acciones': [{'label': 'Ver ayuda', 'url': '#ayuda', 'icono': 'fa-question-circle'}],
        'confianza': 'baja',
    })
