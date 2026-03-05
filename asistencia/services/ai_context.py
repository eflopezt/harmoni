"""
Constructor de contexto del sistema para el asistente IA.

Recopila datos reales de RRHH para inyectar como system prompt,
permitiendo que Ollama responda preguntas factuales sin alucinar.

Soporta lazy loading por módulo y fallback sin IA.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta

logger = logging.getLogger('harmoni.ai')

# Cache de datos del contexto (evita queries repetidos en conversaciones rápidas)
_context_cache: dict = {}     # {cache_key: (timestamp, data)}
_CONTEXT_CACHE_TTL = 15       # segundos — datos frescos pero no excesivos


# ═══════════════════════════════════════════════════════════════════════════
# Detección de módulos relevantes (lazy loading)
# ═══════════════════════════════════════════════════════════════════════════

MODULE_KEYWORDS: dict[str, list[str]] = {
    'personal':       ['empleado', 'personal', 'headcount', 'staff', 'rco', 'area', 'gerencia'],
    'asistencia':     ['asistencia', 'tareo', 'faltas', 'marcacion', 'horas extra', 'he ',
                       'tardanza', 'tardanzas', 'ausentismo', 'inasistencia', 'puntualidad'],
    'vacaciones':     ['vacacion', 'permiso', 'licencia', 'descanso', 'goce'],
    'capacitaciones': ['capacitacion', 'training', 'certificacion', 'curso', 'ssoma'],
    'evaluaciones':   ['evaluacion', 'desempeno', 'okr', 'competencia', 'pdi', '9-box', 'nine box'],
    'encuestas':      ['encuesta', 'clima', 'enps', 'pulso', 'satisfaccion'],
    'prestamos':      ['prestamo', 'adelanto', 'cuota', 'descuento'],
    'onboarding':     ['onboarding', 'offboarding', 'incorporacion', 'ingreso nuevo'],
    'disciplinaria':  ['disciplinaria', 'amonestacion', 'descargo', 'falta', 'suspension'],
    'comunicaciones': ['comunicado', 'notificacion', 'memo', 'aviso'],
    'reclutamiento':  ['vacante', 'reclutamiento', 'postulacion', 'candidato', 'entrevista'],
    'salarios':       ['salario', 'sueldo', 'remuneracion', 'banda salarial', 'incremento', 'compa-ratio'],
    'analytics':      ['kpi', 'rotacion', 'tendencia', 'dashboard', 'indicador', 'ausentismo',
                       'tasa', 'historico', 'snapshot', 'metricas'],
    'nominas':        ['nomina', 'nómina', 'planilla', 'boleta', 'neto', 'essalud', 'afp', 'gratificacion', 'cts', 'periodo nomina'],
}


def detect_module_context(message: str) -> list[str]:
    """
    Detecta qué módulos son relevantes para la pregunta del usuario.
    Retorna lista de identificadores de módulo para lazy loading.
    """
    msg = message.lower()
    detected = []
    for module, keywords in MODULE_KEYWORDS.items():
        if any(kw in msg for kw in keywords):
            detected.append(module)

    # Siempre incluir módulos base
    if not detected:
        detected = ['personal', 'asistencia']

    return detected


# ═══════════════════════════════════════════════════════════════════════════
# Helpers de recolección de datos por módulo
# ═══════════════════════════════════════════════════════════════════════════

def _collect_vacaciones(personal, data: dict) -> None:
    """Vacaciones: solicitudes, saldos, permisos."""
    try:
        from vacaciones.models import SolicitudVacacion, SaldoVacacional, SolicitudPermiso
        from django.db.models import Sum

        data['vacaciones_pendientes'] = SolicitudVacacion.objects.filter(
            estado='PENDIENTE', personal__in=personal).count()
        data['vacaciones_en_goce'] = SolicitudVacacion.objects.filter(
            estado='EN_GOCE', personal__in=personal).count()
        data['vacaciones_aprobadas'] = SolicitudVacacion.objects.filter(
            estado='APROBADA', personal__in=personal).count()

        saldo_agg = SaldoVacacional.objects.filter(
            personal__in=personal, estado__in=['PENDIENTE', 'PARCIAL'],
        ).aggregate(total=Sum('dias_pendientes'))
        data['vacaciones_dias_pendientes_total'] = float(saldo_agg['total'] or 0)

        data['permisos_pendientes'] = SolicitudPermiso.objects.filter(
            estado='PENDIENTE', personal__in=personal).count()
    except Exception as e:
        logger.debug(f'ai_context vacaciones: {e}')


def _collect_capacitaciones(personal, data: dict) -> None:
    """Capacitaciones: cursos, certificaciones."""
    try:
        from capacitaciones.models import Capacitacion, CertificacionTrabajador

        data['capacitaciones_en_curso'] = Capacitacion.objects.filter(
            estado='EN_CURSO').count()
        data['capacitaciones_programadas'] = Capacitacion.objects.filter(
            estado='PROGRAMADA').count()
        data['certificaciones_vencidas'] = CertificacionTrabajador.objects.filter(
            estado='VENCIDA', personal__in=personal).count()
        data['certificaciones_por_vencer'] = CertificacionTrabajador.objects.filter(
            estado='POR_VENCER', personal__in=personal).count()
    except Exception as e:
        logger.debug(f'ai_context capacitaciones: {e}')


def _collect_evaluaciones(personal, data: dict) -> None:
    """Evaluaciones: ciclos, pendientes, PDI, OKR."""
    try:
        from evaluaciones.models import CicloEvaluacion, Evaluacion, PlanDesarrollo, ObjetivoClave

        ciclos_activos = CicloEvaluacion.objects.filter(
            estado__in=['ABIERTO', 'EN_EVALUACION'])
        data['ciclos_evaluacion_activos'] = ciclos_activos.count()
        if ciclos_activos.exists():
            c = ciclos_activos.first()
            data['ciclo_eval_nombre'] = c.nombre
            data['ciclo_eval_avance'] = c.porcentaje_avance

        data['evaluaciones_pendientes'] = Evaluacion.objects.filter(
            estado='PENDIENTE', evaluado__in=personal).count()
        data['pdi_activos'] = PlanDesarrollo.objects.filter(
            estado='ACTIVO', personal__in=personal).count()
        data['okrs_activos'] = ObjetivoClave.objects.filter(
            status='ACTIVO').count()
        data['okrs_en_riesgo'] = ObjetivoClave.objects.filter(
            status='EN_RIESGO').count()
    except Exception as e:
        logger.debug(f'ai_context evaluaciones: {e}')


def _collect_encuestas(data: dict) -> None:
    """Encuestas: activas, eNPS."""
    try:
        from encuestas.models import Encuesta, ResultadoEncuesta

        data['encuestas_activas'] = Encuesta.objects.filter(
            estado='ACTIVA').count()
        enps = ResultadoEncuesta.objects.filter(
            enps_score__isnull=False,
        ).order_by('-calculado_en').first()
        if enps:
            data['enps_score'] = enps.enps_score
    except Exception as e:
        logger.debug(f'ai_context encuestas: {e}')


def _collect_prestamos(personal, data: dict) -> None:
    """Préstamos: en curso, saldo pendiente."""
    try:
        from prestamos.models import Prestamo, CuotaPrestamo
        from django.db.models import Sum

        en_curso = Prestamo.objects.filter(
            estado='EN_CURSO', personal__in=personal)
        data['prestamos_en_curso'] = en_curso.count()
        saldo = CuotaPrestamo.objects.filter(
            prestamo__in=en_curso, estado='PENDIENTE',
        ).aggregate(t=Sum('monto'))
        data['prestamos_saldo_pendiente'] = float(saldo['t'] or 0)
    except Exception as e:
        logger.debug(f'ai_context prestamos: {e}')


def _collect_onboarding(personal, data: dict) -> None:
    """Onboarding y offboarding: procesos en curso."""
    try:
        from onboarding.models import ProcesoOnboarding, ProcesoOffboarding

        onb = ProcesoOnboarding.objects.filter(
            estado='EN_CURSO', personal__in=personal)
        data['onboarding_en_curso'] = onb.count()
        if onb.exists():
            avances = [p.porcentaje_avance for p in onb[:20]]
            data['onboarding_avance_promedio'] = (
                round(sum(avances) / len(avances)) if avances else 0
            )
        data['offboarding_en_curso'] = ProcesoOffboarding.objects.filter(
            estado='EN_CURSO', personal__in=personal).count()
    except Exception as e:
        logger.debug(f'ai_context onboarding: {e}')


def _collect_disciplinaria(personal, data: dict) -> None:
    """Disciplinaria: medidas activas."""
    try:
        from disciplinaria.models import MedidaDisciplinaria

        data['disciplinaria_en_descargo'] = MedidaDisciplinaria.objects.filter(
            estado='EN_DESCARGO', personal__in=personal).count()
        data['disciplinaria_notificadas'] = MedidaDisciplinaria.objects.filter(
            estado='NOTIFICADA', personal__in=personal).count()
    except Exception as e:
        logger.debug(f'ai_context disciplinaria: {e}')


def _collect_comunicaciones(personal, data: dict) -> None:
    """Comunicaciones: pendientes de lectura."""
    try:
        from comunicaciones.models import Notificacion

        data['notificaciones_pendientes'] = Notificacion.objects.filter(
            estado='PENDIENTE', destinatario__in=personal).count()
    except Exception as e:
        logger.debug(f'ai_context comunicaciones: {e}')


def _collect_reclutamiento(data: dict) -> None:
    """Reclutamiento: vacantes y postulaciones."""
    try:
        from reclutamiento.models import Vacante, Postulacion

        vacantes_activas = Vacante.objects.filter(
            estado__in=['PUBLICADA', 'EN_PROCESO'])
        data['vacantes_activas'] = vacantes_activas.count()
        data['postulaciones_activas'] = Postulacion.objects.filter(
            estado='ACTIVA', vacante__in=vacantes_activas).count()
    except Exception as e:
        logger.debug(f'ai_context reclutamiento: {e}')


def _collect_nominas(data: dict) -> None:
    """Nóminas: período actual, totales, estado."""
    try:
        from nominas.models import PeriodoNomina, RegistroNomina
        from django.db.models import Sum, Count, Q

        # Período más reciente (el último creado)
        ultimo = PeriodoNomina.objects.order_by('-anio', '-mes').first()
        if not ultimo:
            return
        data['nomina_periodo']   = str(ultimo)
        data['nomina_estado']    = ultimo.estado
        data['nomina_tipo']      = ultimo.get_tipo_display()

        # Conteo y totales del período actual
        regs = RegistroNomina.objects.filter(periodo=ultimo)
        stats = regs.aggregate(
            total=Count('id'),
            aprobados=Count('id', filter=Q(estado='APROBADO')),
            calculados=Count('id', filter=Q(estado='CALCULADO')),
            neto_total=Sum('neto_a_pagar'),
            essalud_total=Sum('aporte_essalud'),
            costo_total=Sum('costo_total_empresa'),
        )
        data['nomina_registros_total']    = stats['total'] or 0
        data['nomina_registros_aprobados']= stats['aprobados'] or 0
        data['nomina_registros_calculados']= stats['calculados'] or 0
        data['nomina_neto_total']         = float(stats['neto_total'] or 0)
        data['nomina_essalud_total']      = float(stats['essalud_total'] or 0)
        data['nomina_costo_total']        = float(stats['costo_total'] or 0)

        # Período anterior para comparar
        anterior = PeriodoNomina.objects.filter(
            tipo='MENSUAL'
        ).exclude(pk=ultimo.pk).order_by('-anio', '-mes').first()
        if anterior:
            ant_neto = RegistroNomina.objects.filter(
                periodo=anterior
            ).aggregate(n=Sum('neto_a_pagar'))['n'] or 0
            data['nomina_neto_anterior'] = float(ant_neto)
            data['nomina_periodo_anterior'] = str(anterior)
    except Exception as e:
        logger.debug(f'_collect_nominas: {e}')


def _collect_salarios(personal, data: dict) -> None:
    """Salarios: incrementos recientes, bandas activas."""
    try:
        from salarios.models import HistorialSalarial, BandaSalarial

        hoy = date.today()
        data['incrementos_este_mes'] = HistorialSalarial.objects.filter(
            personal__in=personal,
            fecha_efectiva__year=hoy.year,
            fecha_efectiva__month=hoy.month,
        ).count()
        data['bandas_salariales_activas'] = BandaSalarial.objects.filter(
            activa=True).count()
    except Exception as e:
        logger.debug(f'ai_context salarios: {e}')


def _collect_asistencia_detail(personal, data: dict) -> None:
    """
    Asistencia detallada del mes en curso: tardanzas, HE, faltas por área.
    Complementa los datos diarios ya cargados en _build_system_prompt_data_uncached.
    """
    try:
        from asistencia.models import RegistroTareo, SolicitudHE
        from django.db.models import Sum, Count, Q

        hoy = date.today()
        inicio_mes = date(hoy.year, hoy.month, 1)

        # Registros del mes
        tareo_mes = RegistroTareo.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy, personal__in=personal,
        )

        # Totales del mes
        stats = tareo_mes.aggregate(
            total=Count('id'),
            faltas=Count('id', filter=Q(codigo_dia__in=['FA', 'F', 'FALTA'])),
            tardanzas=Count('id', filter=Q(codigo_dia__in=['TA', 'TD', 'TARDA', 'T_TARD'])),
            sin_salida=Count('id', filter=Q(codigo_dia='SS')),
        )
        data['asist_mes_faltas']    = stats['faltas'] or 0
        data['asist_mes_tardanzas'] = stats['tardanzas'] or 0
        data['asist_mes_ss']        = stats['sin_salida'] or 0

        # Top 5 áreas con más faltas este mes
        faltas_area = (
            tareo_mes.filter(codigo_dia__in=['FA', 'F', 'FALTA'])
            .values('personal__subarea__area__nombre')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )
        data['asist_faltas_por_area'] = [
            {'area': f['personal__subarea__area__nombre'] or 'Sin Área', 'faltas': f['total']}
            for f in faltas_area
        ]

        # HE del mes (horas totales y monto)
        he_mes = SolicitudHE.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy,
            personal__in=personal, estado='APROBADO',
        )
        he_stats = he_mes.aggregate(
            total_horas=Sum('horas_aprobadas'),
            count=Count('id'),
        )
        data['he_mes_horas']    = float(he_stats['total_horas'] or 0)
        data['he_mes_cantidad'] = he_stats['count'] or 0

    except Exception as e:
        logger.debug(f'_collect_asistencia_detail: {e}')


def _collect_analytics_kpis(data: dict) -> None:
    """KPI Snapshots: últimos 3 meses + alertas activas."""
    try:
        from analytics.models import KPISnapshot, AlertaRRHH

        # Últimos 3 snapshots (tendencia reciente)
        snaps = list(KPISnapshot.objects.order_by('-periodo')[:3])
        if snaps:
            data['kpi_snapshots'] = [
                {
                    'periodo': s.periodo.strftime('%b %Y'),
                    'headcount': s.total_empleados,
                    'rotacion': float(s.tasa_rotacion),
                    'asistencia': float(s.tasa_asistencia),
                    'he_horas': float(s.total_he_mes),
                    'altas': s.altas_mes,
                    'bajas': s.bajas_mes,
                }
                for s in snaps
            ]

        # Alertas activas
        alertas = AlertaRRHH.objects.filter(
            estado='ACTIVA',
        ).order_by('-severidad', '-creada_en')[:10]
        if alertas.exists():
            data['alertas_activas'] = [
                {'titulo': a.titulo, 'severidad': a.severidad, 'categoria': a.categoria}
                for a in alertas
            ]
            data['alertas_criticas'] = alertas.filter(severidad='CRITICA').count()
    except Exception as e:
        logger.debug(f'_collect_analytics_kpis: {e}')


# Mapa de módulos → helpers (personal requerido, función)
_MODULE_COLLECTORS: dict[str, tuple[bool, callable]] = {
    # (necesita_personal, funcion)
    'asistencia':     (True,  _collect_asistencia_detail),
    'analytics':      (False, _collect_analytics_kpis),
    'vacaciones':     (True,  _collect_vacaciones),
    'capacitaciones': (True,  _collect_capacitaciones),
    'evaluaciones':   (True,  _collect_evaluaciones),
    'encuestas':      (False, _collect_encuestas),
    'prestamos':      (True,  _collect_prestamos),
    'onboarding':     (True,  _collect_onboarding),
    'disciplinaria':  (True,  _collect_disciplinaria),
    'comunicaciones': (True,  _collect_comunicaciones),
    'reclutamiento':  (False, _collect_reclutamiento),
    'salarios':       (True,  _collect_salarios),
    'nominas':        (False, _collect_nominas),
}


# ═══════════════════════════════════════════════════════════════════════════
# Función principal: recopilar datos del sistema
# ═══════════════════════════════════════════════════════════════════════════

def build_system_prompt_data(user, modules: list[str] | None = None) -> dict:
    """
    Recopila estadísticas del sistema para inyectar en el system prompt.
    Retorna un dict con datos reales que el LLM puede referenciar.
    Usa cache de 15s para evitar queries repetidos en conversaciones rápidas.

    Args:
        user: Django User
        modules: Lista de módulos a consultar. None = todos.
    """
    global _context_cache

    # Cache key basado en user + módulos
    mod_key = ','.join(sorted(modules)) if modules else 'ALL'
    cache_key = f'{user.id}:{mod_key}'
    now = time.time()

    if cache_key in _context_cache:
        ts, cached_data = _context_cache[cache_key]
        if now - ts < _CONTEXT_CACHE_TTL:
            return cached_data

    data = _build_system_prompt_data_uncached(user, modules)
    _context_cache[cache_key] = (now, data)

    # Limpiar entradas viejas
    stale = [k for k, (ts, _) in _context_cache.items() if now - ts > _CONTEXT_CACHE_TTL * 4]
    for k in stale:
        del _context_cache[k]

    return data


def _build_system_prompt_data_uncached(user, modules: list[str] | None = None) -> dict:
    """Implementación real sin cache de build_system_prompt_data."""
    from personal.permissions import filtrar_areas, filtrar_subareas, filtrar_personal

    hoy = date.today()
    data: dict = {'fecha': hoy.isoformat()}
    personal = None

    # ── Personal (siempre) ──
    try:
        gerencias = filtrar_areas(user)
        areas = filtrar_subareas(user)
        personal = filtrar_personal(user).filter(estado='Activo')

        data['total_personal'] = personal.count()
        data['total_staff'] = personal.filter(grupo_tareo='STAFF').count()
        data['total_rco'] = personal.filter(grupo_tareo='RCO').count()
        data['total_areas'] = gerencias.filter(activa=True).count()
        data['total_subareas'] = areas.filter(activa=True).count()
    except Exception as e:
        logger.debug(f'ai_context personal: {e}')
        data.update(total_personal=0, total_staff=0, total_rco=0,
                    total_areas=0, total_subareas=0)

    # ── Asistencia hoy (siempre) ──
    try:
        from asistencia.models import RegistroTareo
        from django.db.models import Count, Q
        tareo_hoy = RegistroTareo.objects.filter(fecha=hoy, personal__in=personal)
        asist = tareo_hoy.aggregate(
            total=Count('id'),
            trabajando=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR'])),
            faltas=Count('id', filter=Q(codigo_dia='FA')),
            permisos=Count('id', filter=Q(codigo_dia__in=[
                'V', 'DL', 'DLA', 'DM', 'LCG', 'LSG', 'LF', 'LP', 'LM',
            ])),
        )
        data['asistencia_trabajando'] = asist['trabajando'] or 0
        data['asistencia_faltas'] = asist['faltas'] or 0
        data['asistencia_permisos'] = asist['permisos'] or 0
    except Exception as e:
        logger.debug(f'ai_context asistencia: {e}')

    # ── Aprobaciones pendientes (siempre) ──
    try:
        from asistencia.models import RegistroPapeleta, SolicitudHE
        pend_pap = RegistroPapeleta.objects.filter(
            estado='PENDIENTE', personal__in=personal).count()
        pend_he = SolicitudHE.objects.filter(
            estado='PENDIENTE', personal__in=personal).count()
        data['pendientes_papeletas'] = pend_pap
        data['pendientes_he'] = pend_he
        data['total_pendientes'] = pend_pap + pend_he
    except Exception as e:
        logger.debug(f'ai_context pendientes: {e}')

    # ── Contratos por vencer (siempre) ──
    try:
        en_30d = hoy + timedelta(days=30)
        data['contratos_por_vencer'] = personal.filter(
            fecha_fin_contrato__isnull=False,
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=en_30d,
        ).count()
    except Exception as e:
        logger.debug(f'ai_context contratos: {e}')

    # ── KPI snapshot (siempre si disponible) ──
    try:
        from analytics.models import KPISnapshot
        snap = KPISnapshot.objects.order_by('-periodo').first()  # el más reciente
        if snap:
            data['kpi_rotacion'] = float(snap.tasa_rotacion)
            data['kpi_asistencia'] = float(snap.tasa_asistencia)
            data['kpi_periodo'] = snap.periodo.strftime('%B %Y')
    except Exception:
        pass

    # ── Distribución por área (top 10, siempre) ──
    try:
        from django.db.models import Count as Count2
        top_areas = (
            personal.values('subarea__area__nombre')
            .annotate(total=Count2('id'))
            .order_by('-total')[:10]
        )
        data['top_areas'] = [
            {'area': a['subarea__area__nombre'] or 'Sin Área', 'total': a['total']}
            for a in top_areas
        ]
    except Exception:
        pass

    # ── Datos demográficos (siempre) ──
    try:
        data['personal_masculino'] = personal.filter(sexo='M').count()
        data['personal_femenino'] = personal.filter(sexo='F').count()
    except Exception:
        pass

    # ── Módulos adicionales (lazy loading) ──
    load_all = modules is None
    for mod_name, (needs_personal, collector) in _MODULE_COLLECTORS.items():
        if not load_all and mod_name not in modules:
            continue
        if needs_personal:
            collector(personal, data)
        else:
            collector(data)

    return data


# ═══════════════════════════════════════════════════════════════════════════
# System Prompt — secciones temáticas
# ═══════════════════════════════════════════════════════════════════════════

def build_system_prompt(user, modules: list[str] | None = None) -> str:
    """
    Construye el system prompt completo con datos reales para el asistente IA.
    Organizado en secciones temáticas; omite secciones sin datos.
    """
    data = build_system_prompt_data(user, modules=modules)

    # Nombre de empresa
    empresa = 'la empresa'
    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        if config.empresa_nombre:
            empresa = config.empresa_nombre
    except Exception:
        pass

    sections: list[str] = []

    # Header — instrucciones de comportamiento
    sections.append(
        f'Eres Harmoni AI, analista experto de RRHH de {empresa} (empresa constructora, Peru).\n'
        'REGLAS CRITICAS:\n'
        '1. Responde SIEMPRE en espanol.\n'
        '2. USA los numeros exactos del contexto — nunca seas vago con cifras.\n'
        '3. NUNCA digas "los datos muestran" ni "segun los datos" — ve directo al analisis.\n'
        '4. NUNCA inventes datos que no esten en el contexto.\n'
        '5. Si falta un dato especifico, dilo en 1 linea y continua con lo que si tienes.\n'
        '6. Para analisis: incluye SIEMPRE magnitud (cuanto), tendencia (hacia donde) y '
        'recomendacion accionable (que hacer).\n'
        '7. Formato: texto fluido, **negrita** para cifras clave. '
        'Listas con guion (-) solo si hay 3+ items.\n'
        '8. Legislacion peruana: cita el articulo o decreto exacto (DL 728, DL 713, etc).\n'
        '9. Tono ejecutivo: directo, sin relleno. Cada oracion debe agregar valor.'
    )

    # PLANTILLA
    plantilla = (
        f'PLANTILLA ({data["fecha"]}):\n'
        f'- Activos: {data.get("total_personal", 0)} '
        f'({data.get("total_staff", 0)} STAFF, {data.get("total_rco", 0)} RCO)\n'
        f'- Gerencias: {data.get("total_areas", 0)}, Areas: {data.get("total_subareas", 0)}\n'
        f'- Contratos por vencer (30d): {data.get("contratos_por_vencer", 0)}'
    )
    # Datos demográficos
    masc = data.get('personal_masculino', 0)
    fem = data.get('personal_femenino', 0)
    if masc or fem:
        plantilla += f'\n- Genero: {masc} masculino, {fem} femenino'
    if data.get('top_areas'):
        areas_line = ', '.join(
            f'{a["area"]}:{a["total"]}' for a in data['top_areas']
        )
        plantilla += f'\n- Top areas: {areas_line}'
    sections.append(plantilla)

    # ASISTENCIA HOY + MES
    asist_lines = [
        f'Hoy — Trabajando: {data.get("asistencia_trabajando", 0)}, '
        f'Faltas: {data.get("asistencia_faltas", 0)}, '
        f'Permisos: {data.get("asistencia_permisos", 0)}'
    ]
    if data.get('asist_mes_faltas') is not None:
        asist_lines.append(
            f'Este mes — Faltas: {data.get("asist_mes_faltas", 0)}, '
            f'Tardanzas: {data.get("asist_mes_tardanzas", 0)}, '
            f'Sin salida (SS): {data.get("asist_mes_ss", 0)}'
        )
    if data.get('he_mes_horas') is not None:
        asist_lines.append(
            f'HE aprobadas este mes: {data.get("he_mes_horas", 0):.1f} horas '
            f'({data.get("he_mes_cantidad", 0)} solicitudes)'
        )
    if data.get('asist_faltas_por_area'):
        top_faltas = ', '.join(
            f'{a["area"]}:{a["faltas"]}' for a in data['asist_faltas_por_area']
        )
        asist_lines.append(f'Top areas con faltas: {top_faltas}')
    sections.append('ASISTENCIA:\n- ' + '\n- '.join(asist_lines))

    # KPI HISTÓRICO (si hay snapshots)
    if data.get('kpi_snapshots'):
        snap_lines = []
        for s in data['kpi_snapshots']:
            snap_lines.append(
                f'{s["periodo"]}: {s["headcount"]} empl, '
                f'rot {s["rotacion"]:.1f}%, asist {s["asistencia"]:.1f}%, '
                f'HE {s["he_horas"]:.0f}h, +{s["altas"]}/-{s["bajas"]}'
            )
        sections.append('KPI HISTÓRICO (últimos 3 meses):\n- ' + '\n- '.join(snap_lines))

    # ALERTAS ACTIVAS
    if data.get('alertas_activas'):
        alerts_lines = [
            f'{a["severidad"]} — {a["titulo"]} [{a["categoria"]}]'
            for a in data['alertas_activas'][:5]
        ]
        crit = data.get('alertas_criticas', 0)
        header = f'ALERTAS RRHH ({len(data["alertas_activas"])} activas, {crit} críticas):'
        sections.append(header + '\n- ' + '\n- '.join(alerts_lines))

    # APROBACIONES PENDIENTES (agregado de todos los módulos)
    pendientes_lines = []
    for label, key in [
        ('Papeletas', 'pendientes_papeletas'),
        ('Solicitudes HE', 'pendientes_he'),
        ('Vacaciones', 'vacaciones_pendientes'),
        ('Permisos', 'permisos_pendientes'),
        ('Evaluaciones', 'evaluaciones_pendientes'),
    ]:
        val = data.get(key, 0)
        if val:
            pendientes_lines.append(f'{label}: {val}')
    if pendientes_lines:
        sections.append(
            'APROBACIONES PENDIENTES:\n- ' + '\n- '.join(pendientes_lines)
        )

    # VACACIONES (si hay datos expandidos)
    vac_lines = []
    if data.get('vacaciones_en_goce'):
        vac_lines.append(f'En goce: {data["vacaciones_en_goce"]}')
    if data.get('vacaciones_aprobadas'):
        vac_lines.append(f'Aprobadas: {data["vacaciones_aprobadas"]}')
    if data.get('vacaciones_dias_pendientes_total'):
        vac_lines.append(
            f'Dias pendientes acumulados: {data["vacaciones_dias_pendientes_total"]:.0f}'
        )
    if vac_lines:
        sections.append('VACACIONES:\n- ' + '\n- '.join(vac_lines))

    # DESARROLLO (evaluaciones, capacitaciones, OKR)
    dev_lines = []
    if data.get('ciclos_evaluacion_activos'):
        dev_lines.append(
            f'Ciclo eval: {data.get("ciclo_eval_nombre", "?")} '
            f'({data.get("ciclo_eval_avance", 0)}% avance)'
        )
    if data.get('capacitaciones_en_curso') or data.get('capacitaciones_programadas'):
        dev_lines.append(
            f'Capacitaciones: {data.get("capacitaciones_en_curso", 0)} en curso, '
            f'{data.get("capacitaciones_programadas", 0)} programadas'
        )
    if data.get('certificaciones_vencidas') or data.get('certificaciones_por_vencer'):
        dev_lines.append(
            f'Certificaciones: {data.get("certificaciones_vencidas", 0)} vencidas, '
            f'{data.get("certificaciones_por_vencer", 0)} por vencer'
        )
    if data.get('okrs_activos') or data.get('okrs_en_riesgo'):
        dev_lines.append(
            f'OKRs: {data.get("okrs_activos", 0)} activos, '
            f'{data.get("okrs_en_riesgo", 0)} en riesgo'
        )
    if data.get('pdi_activos'):
        dev_lines.append(f'PDI activos: {data["pdi_activos"]}')
    if dev_lines:
        sections.append('DESARROLLO:\n- ' + '\n- '.join(dev_lines))

    # BIENESTAR (encuestas, eNPS)
    well_lines = []
    if data.get('encuestas_activas'):
        well_lines.append(f'Encuestas activas: {data["encuestas_activas"]}')
    if data.get('enps_score') is not None:
        well_lines.append(f'Ultimo eNPS: {data["enps_score"]}')
    if well_lines:
        sections.append('BIENESTAR:\n- ' + '\n- '.join(well_lines))

    # FINANCIERO (préstamos, salarios)
    fin_lines = []
    if data.get('prestamos_en_curso'):
        fin_lines.append(
            f'Prestamos en curso: {data["prestamos_en_curso"]} '
            f'(saldo pend: S/ {data.get("prestamos_saldo_pendiente", 0):,.2f})'
        )
    if data.get('incrementos_este_mes'):
        fin_lines.append(f'Incrementos este mes: {data["incrementos_este_mes"]}')
    if data.get('bandas_salariales_activas'):
        fin_lines.append(f'Bandas salariales: {data["bandas_salariales_activas"]}')
    if fin_lines:
        sections.append('FINANCIERO:\n- ' + '\n- '.join(fin_lines))

    # NÓMINAS
    if data.get('nomina_periodo'):
        nom_lines = [
            f'Período: {data.get("nomina_periodo")} — {data.get("nomina_tipo")} / {data.get("nomina_estado")}',
            f'Registros: {data.get("nomina_registros_total", 0)} '
            f'({data.get("nomina_registros_aprobados", 0)} aprobados)',
            f'Neto a pagar: S/ {data.get("nomina_neto_total", 0):,.2f}',
            f'Costo empresa: S/ {data.get("nomina_costo_total", 0):,.2f}',
        ]
        if data.get('nomina_neto_anterior'):
            nom_lines.append(
                f'Período anterior: S/ {data.get("nomina_neto_anterior", 0):,.2f}'
            )
        sections.append('NÓMINAS:\n- ' + '\n- '.join(nom_lines))

    # RECLUTAMIENTO
    if data.get('vacantes_activas'):
        sections.append(
            'RECLUTAMIENTO:\n'
            f'- Vacantes activas: {data["vacantes_activas"]}\n'
            f'- Postulaciones activas: {data.get("postulaciones_activas", 0)}'
        )

    # OPERACIONAL (onboarding, offboarding, disciplinaria)
    ops_lines = []
    if data.get('onboarding_en_curso'):
        ops_lines.append(
            f'Onboarding: {data["onboarding_en_curso"]} en curso '
            f'({data.get("onboarding_avance_promedio", 0)}% prom.)'
        )
    if data.get('offboarding_en_curso'):
        ops_lines.append(f'Offboarding: {data["offboarding_en_curso"]} en curso')
    if data.get('disciplinaria_en_descargo') or data.get('disciplinaria_notificadas'):
        ops_lines.append(
            f'Disciplinarias: {data.get("disciplinaria_en_descargo", 0)} en descargo, '
            f'{data.get("disciplinaria_notificadas", 0)} notificadas'
        )
    if data.get('notificaciones_pendientes'):
        ops_lines.append(
            f'Notificaciones pend.: {data["notificaciones_pendientes"]}'
        )
    if ops_lines:
        sections.append('OPERACIONAL:\n- ' + '\n- '.join(ops_lines))

    # KPI
    if data.get('kpi_rotacion') is not None:
        sections.append(
            f'KPI ({data.get("kpi_periodo", "")}):\n'
            f'- Rotacion: {data.get("kpi_rotacion", 0):.1f}%\n'
            f'- Asistencia: {data.get("kpi_asistencia", 0):.1f}%'
        )

    # NAVEGACION HARMONI (donde encontrar cosas)
    sections.append(
        'NAVEGACION HARMONI:\n'
        '- Personal: /personal/ (empleados, areas, roster)\n'
        '- Asistencia: /asistencia/ (tareo, HE, papeletas)\n'
        '- Vacaciones: /vacaciones/ (saldos, solicitudes)\n'
        '- Capacitaciones: /capacitaciones/ (cursos, certificaciones)\n'
        '- Evaluaciones: /evaluaciones/ (ciclos, 360, OKR)\n'
        '- Prestamos: /prestamos/ (adelantos, cuotas)\n'
        '- Reclutamiento: /reclutamiento/ (vacantes, kanban)\n'
        '- Configuracion: /asistencia/configuracion/'
    )

    # LEGISLACION PERU (referencia rápida)
    sections.append(
        'LEYES PERU (referencia):\n'
        '- DL 728: estabilidad laboral, contratos\n'
        '- DS 003-97-TR: TUO ley productividad, despido\n'
        '- DL 713: descansos remunerados, vacaciones, feriados\n'
        '- Ley 30036: teletrabajo\n'
        '- DS 005-2012-TR: reglamento SST\n'
        '- HE: 25% primeras 2h, 35% siguientes, 100% feriados/domingos\n'
        '- Vacaciones: 30 dias por ano, venta max 15 dias\n'
        '- CTS: 1 sueldo/ano, depositos mayo y noviembre'
    )

    return '\n\n'.join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# Fallback sin IA — respuestas directas desde BD
# ═══════════════════════════════════════════════════════════════════════════

def _format_pendientes(data: dict) -> str:
    """Formatea todos los pendientes cruzando módulos."""
    items = [
        ('Papeletas', data.get('pendientes_papeletas', 0)),
        ('Solicitudes HE', data.get('pendientes_he', 0)),
        ('Vacaciones', data.get('vacaciones_pendientes', 0)),
        ('Permisos', data.get('permisos_pendientes', 0)),
        ('Evaluaciones', data.get('evaluaciones_pendientes', 0)),
    ]
    total = sum(v for _, v in items)
    if total == 0:
        return 'No hay aprobaciones pendientes en este momento.'
    lines = [f'**Aprobaciones y pendientes** (Total: {total}):\n']
    for label, count in items:
        if count:
            lines.append(f'- {label}: {count}')
    return '\n'.join(lines)


def _format_resumen_general(data: dict) -> str:
    """Genera un resumen ejecutivo con datos cruzados de todos los módulos."""
    lines = [f'**Resumen General** ({data["fecha"]}):\n']

    # Plantilla
    plantilla_extra = ''
    masc = data.get('personal_masculino', 0)
    fem = data.get('personal_femenino', 0)
    if masc or fem:
        plantilla_extra = f' — {masc}M/{fem}F'
    lines.append(
        f'👥 **Plantilla**: {data.get("total_personal", 0)} activos '
        f'({data.get("total_staff", 0)} STAFF, {data.get("total_rco", 0)} RCO){plantilla_extra}'
    )

    # Asistencia
    trab = data.get('asistencia_trabajando', 0)
    falt = data.get('asistencia_faltas', 0)
    perm = data.get('asistencia_permisos', 0)
    lines.append(f'📋 **Asistencia hoy**: {trab} trabajando, {falt} faltas, {perm} permisos')

    # Pendientes
    total_pend = data.get('total_pendientes', 0)
    if total_pend:
        lines.append(f'⚠️ **Pendientes**: {total_pend} aprobaciones')

    # Contratos
    vencer = data.get('contratos_por_vencer', 0)
    if vencer:
        lines.append(f'📄 **Contratos**: {vencer} vencen en 30 días')

    # Vacaciones
    vac_pend = data.get('vacaciones_pendientes', 0)
    vac_goce = data.get('vacaciones_en_goce', 0)
    if vac_pend or vac_goce:
        lines.append(
            f'🏖️ **Vacaciones**: {vac_goce} en goce, {vac_pend} solicitudes pendientes'
        )

    # Desarrollo
    dev_parts = []
    if data.get('capacitaciones_en_curso'):
        dev_parts.append(f'{data["capacitaciones_en_curso"]} capacitaciones en curso')
    if data.get('evaluaciones_pendientes'):
        dev_parts.append(f'{data["evaluaciones_pendientes"]} evaluaciones pendientes')
    if data.get('certificaciones_vencidas'):
        dev_parts.append(f'{data["certificaciones_vencidas"]} certs vencidas')
    if data.get('okrs_en_riesgo'):
        dev_parts.append(f'{data["okrs_en_riesgo"]} OKRs en riesgo')
    if dev_parts:
        lines.append(f'📚 **Desarrollo**: {", ".join(dev_parts)}')

    # Nóminas
    if data.get('nomina_periodo'):
        lines.append(
            f'💼 **Nómina**: {data.get("nomina_periodo")} — '
            f'Neto S/ {data.get("nomina_neto_total", 0):,.0f} '
            f'({data.get("nomina_registros_aprobados", 0)}/{data.get("nomina_registros_total", 0)} aprobados)'
        )

    # Financiero
    if data.get('prestamos_en_curso'):
        lines.append(
            f'💰 **Préstamos**: {data["prestamos_en_curso"]} en curso '
            f'(S/ {data.get("prestamos_saldo_pendiente", 0):,.0f} pendiente)'
        )

    # Reclutamiento
    vacantes = data.get('vacantes_activas', 0)
    if vacantes:
        lines.append(
            f'🔍 **Reclutamiento**: {vacantes} vacantes activas, '
            f'{data.get("postulaciones_activas", 0)} postulaciones'
        )

    # Onboarding
    if data.get('onboarding_en_curso'):
        lines.append(
            f'🆕 **Onboarding**: {data["onboarding_en_curso"]} en curso '
            f'({data.get("onboarding_avance_promedio", 0)}% promedio)'
        )

    # Disciplinaria
    disc_desc = data.get('disciplinaria_en_descargo', 0)
    disc_not = data.get('disciplinaria_notificadas', 0)
    if disc_desc or disc_not:
        lines.append(
            f'⚖️ **Disciplinaria**: {disc_not} notificadas, {disc_desc} en descargo'
        )

    # Bienestar
    if data.get('enps_score') is not None:
        lines.append(f'😊 **eNPS**: {data["enps_score"]}')

    # KPIs
    if data.get('kpi_rotacion') is not None:
        lines.append(
            f'📊 **KPIs**: Rotación {data["kpi_rotacion"]:.1f}%, '
            f'Asistencia {data.get("kpi_asistencia", 0):.1f}%'
        )

    return '\n'.join(lines)


# Patrones: (keywords, módulos_requeridos, formateador)
_FALLBACK_PATTERNS: list[tuple[list[str], list[str], callable]] = [
    (
        ['cuantos empleados', 'empleados activos', 'headcount', 'total personal'],
        ['personal'],
        lambda d: (
            f'Actualmente hay **{d.get("total_personal", 0)} empleados activos**: '
            f'{d.get("total_staff", 0)} STAFF y {d.get("total_rco", 0)} RCO.\n'
            f'Distribuidos en {d.get("total_areas", 0)} gerencias y '
            f'{d.get("total_subareas", 0)} áreas.'
            + (f'\n- Género: {d.get("personal_masculino", 0)} masculino, '
               f'{d.get("personal_femenino", 0)} femenino'
               if d.get('personal_masculino') or d.get('personal_femenino') else '')
            + (f'\n- Contratos por vencer (30d): {d["contratos_por_vencer"]}'
               if d.get('contratos_por_vencer') else '')
        ),
    ),
    (
        ['asistencia hoy', 'asistencia de hoy', 'quienes trabajaron', 'presentes hoy'],
        ['asistencia'],
        lambda d: (
            f'**Asistencia de hoy** ({d["fecha"]}):\n'
            f'- Trabajando: {d.get("asistencia_trabajando", 0)}\n'
            f'- Faltas: {d.get("asistencia_faltas", 0)}\n'
            f'- Con permiso: {d.get("asistencia_permisos", 0)}'
        ),
    ),
    (
        ['pendientes', 'aprobaciones', 'por aprobar'],
        ['vacaciones', 'evaluaciones'],
        _format_pendientes,
    ),
    (
        ['contratos', 'contrato', 'vencen', 'vencimiento'],
        ['personal'],
        lambda d: (
            f'Contratos por vencer en los proximos 30 dias: '
            f'**{d.get("contratos_por_vencer", 0)}**'
        ),
    ),
    (
        ['vacacion', 'vacaciones'],
        ['vacaciones'],
        lambda d: (
            f'**Vacaciones:**\n'
            f'- Solicitudes pendientes: {d.get("vacaciones_pendientes", 0)}\n'
            f'- En goce actualmente: {d.get("vacaciones_en_goce", 0)}\n'
            f'- Aprobadas: {d.get("vacaciones_aprobadas", 0)}\n'
            f'- Dias pendientes acumulados: {d.get("vacaciones_dias_pendientes_total", 0):.0f}'
        ),
    ),
    (
        ['capacitacion', 'capacitaciones', 'training', 'curso'],
        ['capacitaciones'],
        lambda d: (
            f'**Capacitaciones:**\n'
            f'- En curso: {d.get("capacitaciones_en_curso", 0)}\n'
            f'- Programadas: {d.get("capacitaciones_programadas", 0)}\n'
            f'- Certificaciones vencidas: {d.get("certificaciones_vencidas", 0)}\n'
            f'- Por vencer: {d.get("certificaciones_por_vencer", 0)}'
        ),
    ),
    (
        ['evaluacion', 'evaluaciones', 'desempeno', 'okr'],
        ['evaluaciones'],
        lambda d: (
            f'**Evaluaciones:**\n'
            f'- Ciclos activos: {d.get("ciclos_evaluacion_activos", 0)}'
            + (f' ({d.get("ciclo_eval_nombre", "")}, {d.get("ciclo_eval_avance", 0)}% avance)'
               if d.get('ciclo_eval_nombre') else '')
            + f'\n- Evaluaciones pendientes: {d.get("evaluaciones_pendientes", 0)}'
            + f'\n- PDI activos: {d.get("pdi_activos", 0)}'
            + f'\n- OKRs activos: {d.get("okrs_activos", 0)}, en riesgo: {d.get("okrs_en_riesgo", 0)}'
        ),
    ),
    (
        ['prestamo', 'prestamos', 'adelanto'],
        ['prestamos'],
        lambda d: (
            f'**Prestamos:**\n'
            f'- En curso: {d.get("prestamos_en_curso", 0)}\n'
            f'- Saldo pendiente total: S/ {d.get("prestamos_saldo_pendiente", 0):,.2f}'
        ),
    ),
    (
        ['vacante', 'vacantes', 'reclutamiento', 'postulacion'],
        ['reclutamiento'],
        lambda d: (
            f'**Reclutamiento:**\n'
            f'- Vacantes activas: {d.get("vacantes_activas", 0)}\n'
            f'- Postulaciones activas: {d.get("postulaciones_activas", 0)}'
        ),
    ),
    (
        ['onboarding', 'incorporacion', 'offboarding'],
        ['onboarding'],
        lambda d: (
            f'**Onboarding/Offboarding:**\n'
            f'- Onboarding en curso: {d.get("onboarding_en_curso", 0)}'
            + (f' ({d.get("onboarding_avance_promedio", 0)}% promedio)'
               if d.get('onboarding_en_curso') else '')
            + f'\n- Offboarding en curso: {d.get("offboarding_en_curso", 0)}'
        ),
    ),
    (
        ['disciplinaria', 'amonestacion', 'descargo', 'falta discipl'],
        ['disciplinaria'],
        lambda d: (
            f'**Disciplinaria:**\n'
            f'- Notificadas: {d.get("disciplinaria_notificadas", 0)}\n'
            f'- En descargo: {d.get("disciplinaria_en_descargo", 0)}'
        ),
    ),
    (
        ['salario', 'sueldo', 'incremento', 'banda salarial'],
        ['salarios'],
        lambda d: (
            f'**Salarios:**\n'
            f'- Incrementos este mes: {d.get("incrementos_este_mes", 0)}\n'
            f'- Bandas salariales activas: {d.get("bandas_salariales_activas", 0)}'
        ),
    ),
    # ── Saludos y preguntas genéricas ──
    (
        ['hola', 'hello', 'buenos dias', 'buenas tardes', 'buenas noches', 'hey'],
        ['personal'],
        lambda d: (
            f'¡Hola! Soy **Harmoni AI**, tu asistente de RRHH. '
            f'Hoy tenemos **{d.get("total_personal", 0)} empleados activos**. '
            + (f'Hay **{d.get("total_pendientes", 0)}** aprobaciones pendientes. '
               if d.get('total_pendientes', 0) else 'No hay aprobaciones pendientes. ')
            + '¿En qué puedo ayudarte?'
        ),
    ),
    (
        ['resumen', 'dashboard', 'estado general', 'como esta todo', 'como estamos',
         'situacion actual', 'overview', 'panorama'],
        ['vacaciones', 'capacitaciones', 'evaluaciones', 'reclutamiento'],
        _format_resumen_general,
    ),
    (
        ['kpi', 'indicador', 'metrica', 'rendimiento general'],
        ['personal'],
        lambda d: (
            '**KPIs principales:**\n'
            + (f'- Rotación: {d["kpi_rotacion"]:.1f}%\n' if d.get('kpi_rotacion') is not None else '')
            + (f'- Asistencia: {d["kpi_asistencia"]:.1f}%\n' if d.get('kpi_asistencia') is not None else '')
            + f'- Plantilla: {d.get("total_personal", 0)} activos\n'
            + f'- Pendientes: {d.get("total_pendientes", 0)}\n'
            + f'- Contratos por vencer: {d.get("contratos_por_vencer", 0)}'
        ),
    ),
    (
        ['area', 'areas', 'gerencia', 'gerencias', 'distribucion', 'departamento'],
        ['personal'],
        lambda d: (
            f'**Distribución por áreas:**\n'
            + '\n'.join(
                f'- {a["area"]}: {a["total"]} empleados'
                for a in d.get('top_areas', [])
            ) if d.get('top_areas') else 'Sin datos de áreas disponibles.'
        ),
    ),
    (
        ['notificacion', 'notificaciones', 'comunicado', 'comunicados', 'aviso'],
        ['comunicaciones'],
        lambda d: (
            f'**Comunicaciones:**\n'
            f'- Notificaciones pendientes: {d.get("notificaciones_pendientes", 0)}'
        ),
    ),
    (
        ['clima', 'enps', 'satisfaccion', 'bienestar'],
        ['encuestas'],
        lambda d: (
            f'**Clima y Bienestar:**\n'
            f'- Encuestas activas: {d.get("encuestas_activas", 0)}'
            + (f'\n- Último eNPS: {d["enps_score"]}' if d.get('enps_score') is not None else '')
        ),
    ),
    (
        ['nomina', 'nómina', 'planilla', 'boleta de pago', 'periodo nomina',
         'cuanto es el neto', 'costo planilla', 'masa salarial'],
        ['nominas'],
        lambda d: (
            (
                f'**Nóminas — {d.get("nomina_periodo", "Sin período")}** '
                f'({d.get("nomina_tipo", "")} / {d.get("nomina_estado", "")}):\n'
                f'- Registros: {d.get("nomina_registros_total", 0)} '
                f'({d.get("nomina_registros_aprobados", 0)} aprobados, '
                f'{d.get("nomina_registros_calculados", 0)} calculados)\n'
                f'- Neto a pagar: **S/ {d.get("nomina_neto_total", 0):,.2f}**\n'
                f'- EsSalud (empleador): S/ {d.get("nomina_essalud_total", 0):,.2f}\n'
                f'- Costo total empresa: S/ {d.get("nomina_costo_total", 0):,.2f}'
            ) + (
                f'\n- Período anterior ({d.get("nomina_periodo_anterior", "")}): '
                f'S/ {d.get("nomina_neto_anterior", 0):,.2f}'
                if d.get('nomina_neto_anterior') else ''
            )
        ) if d.get('nomina_periodo') else 'No hay períodos de nómina registrados aún.',
    ),
    (
        ['horas extra', 'sobretiempo', 'he '],
        ['asistencia'],
        lambda d: (
            f'**Horas Extra:**\n'
            f'- Solicitudes HE pendientes: {d.get("pendientes_he", 0)}\n'
            'Para ver detalle de HE, ve a **Asistencia > Vista Unificada**.'
        ),
    ),
    (
        ['que puedes hacer', 'ayuda', 'help', 'funciones', 'como funciona'],
        [],
        lambda d: (
            '**¿Qué puedo hacer?** 🤖\n\n'
            '- 👥 **Personal**: headcount, distribución, contratos\n'
            '- 📋 **Asistencia**: faltas, presencia, horas extra\n'
            '- ✅ **Pendientes**: papeletas, solicitudes, aprobaciones\n'
            '- 🏖️ **Vacaciones**: saldos, solicitudes, goce\n'
            '- 📚 **Capacitaciones**: cursos, certificaciones\n'
            '- 📊 **Evaluaciones**: ciclos, OKRs, PDI\n'
            '- 💰 **Préstamos**: en curso, saldos\n'
            '- 📈 **Gráficos**: pídeme gráficos con "muéstrame un gráfico de..."\n\n'
            'Prueba con: *"¿Cuántos empleados activos hay?"*'
        ),
    ),
]


def responder_sin_ia(message: str, user) -> str | None:
    """
    Responde consultas comunes directamente desde la BD, sin Ollama.
    Returns texto formateado, o None si no reconoce la pregunta.
    """
    msg = message.lower().strip()

    for keywords, extra_modules, formatter in _FALLBACK_PATTERNS:
        if any(kw in msg for kw in keywords):
            data = build_system_prompt_data(user, modules=extra_modules)
            return formatter(data)

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Detección de gráficos
# ═══════════════════════════════════════════════════════════════════════════

def detect_export_request(message: str) -> dict | None:
    """
    Detecta si el usuario quiere exportar un reporte Excel.
    Returns: {'type': str} o None.
    """
    msg = message.lower()
    export_kw = [
        'exportar reporte', 'descargar reporte', 'generar reporte',
        'reporte excel', 'reporte xlsx', 'exportar excel',
        'descargar excel', 'reporte ejecutivo',
    ]
    if any(kw in msg for kw in export_kw):
        return {'type': 'gerencia'}
    return None


def detect_dashboard_request(message: str) -> dict | None:
    """
    Detecta si el usuario quiere un dashboard ejecutivo multi-gráfico.
    Returns: {'type': 'dashboard_gerencia'} o None.
    """
    msg = message.lower()
    dashboard_kw = [
        'dashboard gerencia', 'dashboard ejecutivo', 'dashboard de gerencia',
        'vista gerencial', 'panel gerencia', 'resumen ejecutivo grafic',
        'dashboard general', 'todos los graficos',
    ]
    # Exact match for "dashboard" alone
    if any(kw in msg for kw in dashboard_kw):
        return {'type': 'dashboard_gerencia'}
    # Just "dashboard" if it's a direct request
    if msg.strip() in ('dashboard', 'dashboard de gerencia'):
        return {'type': 'dashboard_gerencia'}
    return None


def generate_dashboard_data(user) -> dict | None:
    """
    Genera un dashboard ejecutivo multi-gráfico: 4 charts combinados.
    Reutiliza generate_chart_data() para cada sub-gráfico.
    """
    charts = []
    for chart_type in ['areas', 'headcount', 'genero', 'tipo_personal']:
        data = generate_chart_data(chart_type, user)
        if data:
            charts.append(data)

    if not charts:
        return None

    return {
        'multi_dashboard': True,
        'charts': charts,
        'title': 'Dashboard Ejecutivo',
    }


def detect_chart_request(message: str) -> dict | None:
    """
    Detecta si el usuario pide un gráfico/chart y retorna la especificación.
    Returns: {'type': str} o None.
    """
    msg = message.lower()

    chart_kw = [
        'gráfico', 'grafico', 'gráfica', 'grafica', 'chart', 'graph',
        'muéstrame', 'muestrame', 'mostrar', 'visualiza', 'diagrama',
        'dibuja', 'genera un',
    ]
    is_chart = any(kw in msg for kw in chart_kw)
    if not is_chart:
        return None

    # Tipo de gráfico (orden de especificidad: más específico primero)
    if any(kw in msg for kw in [
        'antigüedad', 'antiguedad', 'tenure', 'tiempo en empresa',
        'permanencia', 'intervalo',
    ]):
        return {'type': 'antiguedad', 'raw_msg': msg}

    if any(kw in msg for kw in [
        'asistencia semanal', 'ultimos 7', 'ultima semana', 'semana',
    ]):
        return {'type': 'asistencia_semanal'}

    if any(kw in msg for kw in [
        'hora extra', 'horas extra', 'distribucion he', 'tipo he',
    ]):
        return {'type': 'he_distribucion'}

    if any(kw in msg for kw in ['vacacion', 'estado vacacion']):
        return {'type': 'vacaciones_estado'}

    if any(kw in msg for kw in [
        'capacitacion', 'training', 'estado capacitacion', 'cursos',
    ]):
        return {'type': 'capacitaciones_estado'}

    if any(kw in msg for kw in [
        'tipo contrato', 'tipo de contrato', 'contrato', 'modalidad contrat',
    ]):
        return {'type': 'tipo_contrato'}

    if any(kw in msg for kw in ['genero', 'género', 'sexo', 'hombre', 'mujer']):
        return {'type': 'genero'}

    if any(kw in msg for kw in ['edad', 'generacion', 'generación', 'demografía', 'rango etario']):
        return {'type': 'edad'}

    if any(kw in msg for kw in [
        'área', 'area', 'gerencia', 'departamento', 'división', 'division',
    ]):
        return {'type': 'areas'}

    if any(kw in msg for kw in ['staff', 'rco', 'tipo personal', 'grupo tareo']):
        return {'type': 'tipo_personal'}

    if any(kw in msg for kw in [
        'pension', 'pensión', 'afp', 'onp', 'regimen pension',
    ]):
        return {'type': 'regimen_pension'}

    if any(kw in msg for kw in ['rotación', 'rotacion', 'turnover']):
        return {'type': 'rotacion'}

    if any(kw in msg for kw in [
        'headcount', 'evolución', 'evolucion', 'tendencia', 'trend',
    ]):
        return {'type': 'headcount'}

    # Default
    return {'type': 'areas'}


# ═══════════════════════════════════════════════════════════════════════════
# Generación de datos de gráficos
# ═══════════════════════════════════════════════════════════════════════════

def generate_chart_data(chart_type: str, user, message: str = '') -> dict | None:
    """
    Genera datos de gráfico reales desde la BD.
    Retorna dict con spec para Chart.js en el frontend.
    """
    from personal.permissions import filtrar_personal
    from django.db.models import Count

    hoy = date.today()

    try:
        personal = filtrar_personal(user).filter(estado='Activo')
    except Exception:
        return None

    if chart_type == 'antiguedad':
        msg = message.lower()
        con_fecha = personal.filter(fecha_alta__isnull=False)
        sin_fecha = personal.filter(fecha_alta__isnull=True).count()

        if '6' in msg and '12' in msg:
            labels = ['0 – 6 meses', '7 – 12 meses', 'Más de 12 meses']
            v1 = con_fecha.filter(fecha_alta__gte=hoy - timedelta(days=182)).count()
            v2 = con_fecha.filter(
                fecha_alta__lt=hoy - timedelta(days=182),
                fecha_alta__gte=hoy - timedelta(days=365),
            ).count()
            v3 = con_fecha.filter(
                fecha_alta__lt=hoy - timedelta(days=365),
            ).count() + sin_fecha
            values = [v1, v2, v3]
            colors = ['#14b8a6', '#0891b2', '#7c3aed']
        else:
            labels = ['< 1 año', '1-3 años', '3-5 años', '5+ años']
            values = [
                con_fecha.filter(fecha_alta__gte=hoy - timedelta(days=365)).count(),
                con_fecha.filter(
                    fecha_alta__lt=hoy - timedelta(days=365),
                    fecha_alta__gte=hoy - timedelta(days=365 * 3),
                ).count(),
                con_fecha.filter(
                    fecha_alta__lt=hoy - timedelta(days=365 * 3),
                    fecha_alta__gte=hoy - timedelta(days=365 * 5),
                ).count(),
                con_fecha.filter(
                    fecha_alta__lt=hoy - timedelta(days=365 * 5),
                ).count() + sin_fecha,
            ]
            colors = ['#14b8a6', '#0f766e', '#0891b2', '#7c3aed']

        total = sum(values)
        return {
            'chart': 'doughnut',
            'title': 'Distribución por Antigüedad',
            'labels': labels,
            'values': values,
            'colors': colors,
            'summary': f'Total: {total} empleados activos',
        }

    elif chart_type == 'areas':
        areas_data = (
            personal
            .values('subarea__area__nombre')
            .annotate(total=Count('id'))
            .order_by('-total')[:10]
        )
        labels = [a['subarea__area__nombre'] or 'Sin Área' for a in areas_data]
        values = [a['total'] for a in areas_data]
        colors = [
            '#0f766e', '#0891b2', '#d97706', '#7c3aed', '#10b981',
            '#ef4444', '#6366f1', '#ea580c', '#0d9488', '#f43e5c',
        ]
        return {
            'chart': 'doughnut',
            'title': 'Distribución por Área',
            'labels': labels,
            'values': values,
            'colors': colors[:len(labels)],
            'summary': f'{len(labels)} áreas activas',
        }

    elif chart_type == 'tipo_personal':
        staff_n = personal.filter(grupo_tareo='STAFF').count()
        rco_n = personal.filter(grupo_tareo='RCO').count()
        return {
            'chart': 'doughnut',
            'title': 'Personal por Tipo',
            'labels': ['STAFF', 'RCO'],
            'values': [staff_n, rco_n],
            'colors': ['#0f766e', '#d97706'],
            'summary': f'Total: {staff_n + rco_n} empleados',
        }

    elif chart_type == 'rotacion':
        try:
            from analytics.models import KPISnapshot
            snaps = KPISnapshot.objects.order_by('-periodo')[:12][::-1]
            if not snaps:
                return None
            return {
                'chart': 'bar',
                'title': 'Rotación Mensual (%)',
                'labels': [s.periodo.strftime('%b %Y') for s in snaps],
                'values': [float(s.tasa_rotacion) for s in snaps],
                'colors': ['rgba(245,158,11,.7)'],
                'summary': f'Últimos {len(snaps)} meses',
            }
        except Exception:
            return None

    elif chart_type == 'headcount':
        try:
            from analytics.models import KPISnapshot
            snaps = KPISnapshot.objects.order_by('-periodo')[:12][::-1]
            if not snaps:
                return None
            return {
                'chart': 'line',
                'title': 'Evolución Headcount',
                'labels': [s.periodo.strftime('%b %Y') for s in snaps],
                'values': [s.total_empleados for s in snaps],
                'colors': ['#0f766e'],
                'summary': f'Últimos {len(snaps)} meses',
            }
        except Exception:
            return None

    elif chart_type == 'tipo_contrato':
        tipos = (
            personal.values('tipo_contrato')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        if not tipos:
            return None
        labels = [t['tipo_contrato'] or 'Sin tipo' for t in tipos]
        values = [t['total'] for t in tipos]
        colors = [
            '#0f766e', '#0891b2', '#d97706', '#7c3aed', '#10b981',
            '#ef4444', '#6366f1', '#ea580c', '#f43e5c', '#8b5cf6',
            '#059669', '#dc2626', '#2563eb',
        ]
        return {
            'chart': 'doughnut',
            'title': 'Personal por Tipo de Contrato',
            'labels': labels,
            'values': values,
            'colors': colors[:len(labels)],
            'summary': f'{len(labels)} tipos de contrato',
        }

    elif chart_type == 'genero':
        m = personal.filter(sexo='M').count()
        f = personal.filter(sexo='F').count()
        otro = personal.exclude(sexo__in=['M', 'F']).count()
        labels = ['Masculino', 'Femenino']
        values = [m, f]
        colors = ['#0891b2', '#d946ef']
        if otro:
            labels.append('Otro/No esp.')
            values.append(otro)
            colors.append('#94a3b8')
        return {
            'chart': 'doughnut',
            'title': 'Personal por Género',
            'labels': labels,
            'values': values,
            'colors': colors,
            'summary': f'Total: {sum(values)} empleados',
        }

    elif chart_type == 'edad':
        con_fn = personal.filter(fecha_nacimiento__isnull=False)
        if not con_fn.exists():
            return None

        rangos = {'18-25': 0, '26-35': 0, '36-45': 0, '46-55': 0, '56+': 0}
        for p in con_fn.only('fecha_nacimiento'):
            edad = (hoy - p.fecha_nacimiento).days // 365
            if edad <= 25:
                rangos['18-25'] += 1
            elif edad <= 35:
                rangos['26-35'] += 1
            elif edad <= 45:
                rangos['36-45'] += 1
            elif edad <= 55:
                rangos['46-55'] += 1
            else:
                rangos['56+'] += 1

        labels = list(rangos.keys())
        values = list(rangos.values())
        colors = ['#14b8a6', '#0f766e', '#0891b2', '#7c3aed', '#d97706']
        return {
            'chart': 'bar',
            'title': 'Distribución por Edad',
            'labels': labels,
            'values': values,
            'colors': colors,
            'summary': f'{con_fn.count()} empleados con fecha de nacimiento',
        }

    elif chart_type == 'regimen_pension':
        regimenes = (
            personal.values('regimen_pension')
            .annotate(total=Count('id'))
            .order_by('-total')
        )
        if not regimenes:
            return None
        labels = [r['regimen_pension'] or 'Sin régimen' for r in regimenes]
        values = [r['total'] for r in regimenes]
        color_map = {
            'AFP': '#0f766e', 'ONP': '#d97706',
            'SIN_PENSION': '#94a3b8',
        }
        colors = [color_map.get(l, '#6366f1') for l in labels]
        return {
            'chart': 'doughnut',
            'title': 'Régimen de Pensiones',
            'labels': labels,
            'values': values,
            'colors': colors,
            'summary': f'Total: {sum(values)} empleados',
        }

    # ── Charts de módulos ──

    elif chart_type == 'asistencia_semanal':
        try:
            from asistencia.models import RegistroTareo
            from django.db.models import Q

            dias = [hoy - timedelta(days=i) for i in range(6, -1, -1)]
            labels = []
            trabajando = []
            faltas = []

            for dia in dias:
                tareo_dia = RegistroTareo.objects.filter(
                    fecha=dia, personal__in=personal)
                agg = tareo_dia.aggregate(
                    t=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR'])),
                    f=Count('id', filter=Q(codigo_dia='FA')),
                )
                labels.append(dia.strftime('%a %d'))
                trabajando.append(agg['t'] or 0)
                faltas.append(agg['f'] or 0)

            return {
                'chart': 'bar',
                'title': 'Asistencia Últimos 7 Días',
                'labels': labels,
                'values': trabajando,
                'values2': faltas,
                'colors': ['rgba(15,118,110,.7)', 'rgba(239,68,68,.7)'],
                'summary': f'Promedio: {sum(trabajando) // max(len(trabajando), 1)} trabajando/día',
                'multi_series': True,
                'series_labels': ['Trabajando', 'Faltas'],
            }
        except Exception:
            return None

    elif chart_type == 'he_distribucion':
        try:
            from asistencia.models import RegistroTareo
            from django.db.models import Sum

            desde = hoy - timedelta(days=30)
            agg = RegistroTareo.objects.filter(
                fecha__gte=desde, personal__in=personal,
            ).aggregate(
                h25=Sum('he_25'), h35=Sum('he_35'), h100=Sum('he_100'),
            )
            values = [
                float(agg['h25'] or 0),
                float(agg['h35'] or 0),
                float(agg['h100'] or 0),
            ]
            if sum(values) == 0:
                return None

            return {
                'chart': 'doughnut',
                'title': 'Distribución Horas Extra (30 días)',
                'labels': ['HE 25%', 'HE 35%', 'HE 100%'],
                'values': values,
                'colors': ['#14b8a6', '#f59e0b', '#ef4444'],
                'summary': f'Total: {sum(values):.1f} horas extra',
            }
        except Exception:
            return None

    elif chart_type == 'vacaciones_estado':
        try:
            from vacaciones.models import SolicitudVacacion

            estados = (
                SolicitudVacacion.objects.filter(personal__in=personal)
                .values('estado')
                .annotate(total=Count('id'))
                .order_by('-total')
            )
            if not estados:
                return None

            labels = [e['estado'] for e in estados]
            values = [e['total'] for e in estados]
            color_map = {
                'PENDIENTE': '#f59e0b', 'APROBADA': '#10b981',
                'EN_GOCE': '#0891b2', 'COMPLETADA': '#6366f1',
                'RECHAZADA': '#ef4444', 'BORRADOR': '#94a3b8',
                'ANULADA': '#d1d5db',
            }
            colors = [color_map.get(l, '#999') for l in labels]

            return {
                'chart': 'doughnut',
                'title': 'Solicitudes de Vacaciones por Estado',
                'labels': labels,
                'values': values,
                'colors': colors,
                'summary': f'Total: {sum(values)} solicitudes',
            }
        except Exception:
            return None

    elif chart_type == 'capacitaciones_estado':
        try:
            from capacitaciones.models import Capacitacion

            estados = (
                Capacitacion.objects.values('estado')
                .annotate(total=Count('id'))
                .order_by('-total')
            )
            if not estados:
                return None

            labels = [e['estado'] for e in estados]
            values = [e['total'] for e in estados]
            color_map = {
                'PROGRAMADA': '#f59e0b', 'EN_CURSO': '#0891b2',
                'COMPLETADA': '#10b981', 'CANCELADA': '#ef4444',
            }
            colors = [color_map.get(l, '#999') for l in labels]

            return {
                'chart': 'doughnut',
                'title': 'Capacitaciones por Estado',
                'labels': labels,
                'values': values,
                'colors': colors,
                'summary': f'Total: {sum(values)} capacitaciones',
            }
        except Exception:
            return None

    return None


# ═══════════════════════════════════════════════════════════════════════════
# Insights (para dashboard home)
# ═══════════════════════════════════════════════════════════════════════════

def build_insights_prompt(user) -> tuple[str, str]:
    """
    Construye prompt para generar insights del dashboard.
    Returns: (system_prompt, user_prompt)
    """
    data = build_system_prompt_data(user)  # todos los módulos

    system = (
        'Eres un analista senior de RRHH de una empresa peruana. '
        'Genera exactamente 4 insights accionables en espanol. '
        'Se directo y concreto. Cada insight debe tener un hallazgo y una accion.\n'
        'FORMATO OBLIGATORIO: usa emojis + negrita para cada insight.\n'
        'Ejemplo: "⚠️ **Rotación al alza** — La tasa de 3.2% supera...'
        ' Accion: revisar encuestas de salida."'
    )

    total = data.get('total_personal', 0)
    trab = data.get('asistencia_trabajando', 0)
    tasa_pres = round(trab / total * 100, 1) if total else 0

    user_prompt = f"""Analiza estos datos de RRHH y genera 4 insights accionables:

PLANTILLA:
- {total} empleados activos ({data.get('total_staff', 0)} STAFF, {data.get('total_rco', 0)} RCO)
- Genero: {data.get('personal_masculino', 0)} masculino, {data.get('personal_femenino', 0)} femenino

ASISTENCIA HOY:
- {trab} trabajando, {data.get('asistencia_faltas', 0)} faltas, {data.get('asistencia_permisos', 0)} permisos
- Tasa presencia hoy: {tasa_pres}%

OPERACIONES:
- Aprobaciones pendientes: {data.get('total_pendientes', 0)}
- Contratos por vencer (30d): {data.get('contratos_por_vencer', 0)}"""

    if data.get('kpi_rotacion') is not None:
        user_prompt += f"""

KPIs HISTORICOS:
- Tasa rotacion: {data.get('kpi_rotacion', 0):.1f}%
- Tasa asistencia: {data.get('kpi_asistencia', 0):.1f}%"""

    if data.get('top_areas'):
        areas_str = ', '.join(
            f'{a["area"]}({a["total"]})' for a in data['top_areas'][:5]
        )
        user_prompt += f'\n- Top 5 areas: {areas_str}'

    # Datos enriquecidos de otros módulos — agrupados por tema
    modulos = []

    # Vacaciones
    vac_parts = []
    if data.get('vacaciones_pendientes'):
        vac_parts.append(f'Solicitudes pendientes: {data["vacaciones_pendientes"]}')
    if data.get('vacaciones_en_goce'):
        vac_parts.append(f'En goce: {data["vacaciones_en_goce"]}')
    if data.get('vacaciones_dias_pendientes_total'):
        vac_parts.append(
            f'Dias acumulados pendientes: {data["vacaciones_dias_pendientes_total"]:.0f}')
    if vac_parts:
        modulos.append('VACACIONES:\n' + '\n'.join(f'- {p}' for p in vac_parts))

    # Desarrollo
    dev_parts = []
    if data.get('capacitaciones_en_curso'):
        dev_parts.append(f'Capacitaciones en curso: {data["capacitaciones_en_curso"]}')
    if data.get('certificaciones_vencidas'):
        dev_parts.append(f'Certificaciones vencidas: {data["certificaciones_vencidas"]}')
    if data.get('ciclos_evaluacion_activos'):
        dev_parts.append(
            f'Ciclo evaluacion: {data.get("ciclo_eval_nombre", "?")}, '
            f'{data.get("ciclo_eval_avance", 0)}% avance'
        )
    if data.get('okrs_en_riesgo'):
        dev_parts.append(f'OKRs en riesgo: {data["okrs_en_riesgo"]}')
    if data.get('pdi_activos'):
        dev_parts.append(f'PDI activos: {data["pdi_activos"]}')
    if dev_parts:
        modulos.append('DESARROLLO:\n' + '\n'.join(f'- {p}' for p in dev_parts))

    # Financiero
    fin_parts = []
    if data.get('prestamos_en_curso'):
        fin_parts.append(
            f'Prestamos: {data["prestamos_en_curso"]} '
            f'(S/ {data.get("prestamos_saldo_pendiente", 0):,.0f} saldo)')
    if data.get('incrementos_este_mes'):
        fin_parts.append(f'Incrementos este mes: {data["incrementos_este_mes"]}')
    if fin_parts:
        modulos.append('FINANCIERO:\n' + '\n'.join(f'- {p}' for p in fin_parts))

    # Reclutamiento
    if data.get('vacantes_activas'):
        modulos.append(
            f'RECLUTAMIENTO:\n- Vacantes: {data["vacantes_activas"]}, '
            f'Postulaciones: {data.get("postulaciones_activas", 0)}'
        )

    # Bienestar
    well_parts = []
    if data.get('encuestas_activas'):
        well_parts.append(f'Encuestas activas: {data["encuestas_activas"]}')
    if data.get('enps_score') is not None:
        well_parts.append(f'eNPS: {data["enps_score"]}')
    if well_parts:
        modulos.append('BIENESTAR:\n' + '\n'.join(f'- {p}' for p in well_parts))

    # Onboarding / Disciplinaria
    ops_parts = []
    if data.get('onboarding_en_curso'):
        ops_parts.append(
            f'Onboarding: {data["onboarding_en_curso"]} en curso '
            f'({data.get("onboarding_avance_promedio", 0)}% avance)')
    if data.get('disciplinaria_en_descargo'):
        ops_parts.append(f'Disciplinarias en descargo: {data["disciplinaria_en_descargo"]}')
    if ops_parts:
        modulos.append('OPERACIONES RR.HH.:\n' + '\n'.join(f'- {p}' for p in ops_parts))

    if modulos:
        user_prompt += '\n\n' + '\n\n'.join(modulos)

    user_prompt += """

Genera exactamente 4 insights. Cada uno debe:
1. Empezar con un emoji relevante + titulo en negrita
2. Identificar un hallazgo concreto basado en los datos
3. Sugerir una accion especifica con responsable (RRHH, Jefe directo, etc.)
Maximo 2-3 lineas por insight. Prioriza lo urgente."""

    return system, user_prompt
