"""
Vistas del módulo Tareo — Configuración y Parámetros.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from asistencia.views._common import solo_admin


# ---------------------------------------------------------------------------
# PARÁMETROS / CONFIGURACIÓN
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def parametros_view(request):
    """Vista de parámetros y configuración del módulo Tareo."""
    from asistencia.models import (
        FeriadoCalendario, HomologacionCodigo,
        RegimenTurno, TipoHorario,
    )

    hoy = date.today()
    context = {
        'titulo': 'Parámetros del Módulo Tareo',
        'regimenes': RegimenTurno.objects.all().order_by('nombre'),
        'horarios': TipoHorario.objects.all().order_by('nombre'),
        'feriados': FeriadoCalendario.objects.all().order_by('fecha'),
        'homologaciones': HomologacionCodigo.objects.all().order_by('prioridad', 'codigo_origen'),
        'anio_actual': hoy.year,
        'anios_feriados': range(hoy.year - 1, hoy.year + 3),
    }
    return render(request, 'asistencia/parametros.html', context)


# ---------------------------------------------------------------------------
# CONFIGURACIÓN DEL SISTEMA
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def configuracion_view(request):
    """Vista de configuración del sistema (ConfiguracionSistema)."""
    from asistencia.models import ConfiguracionSistema

    config = ConfiguracionSistema.get()

    if request.method == 'POST':
        # Campos básicos
        config.empresa_nombre = request.POST.get('empresa_nombre', config.empresa_nombre)
        config.ruc = request.POST.get('ruc', config.ruc)
        config.dia_corte_planilla = int(request.POST.get('dia_corte_planilla', config.dia_corte_planilla))
        config.regularizacion_activa = request.POST.get('regularizacion_activa') == '1'

        # Identidad visual / membrete
        config.empresa_direccion = request.POST.get('empresa_direccion', config.empresa_direccion).strip()
        config.empresa_telefono = request.POST.get('empresa_telefono', config.empresa_telefono).strip()
        config.empresa_email = request.POST.get('empresa_email', config.empresa_email).strip()
        config.empresa_web = request.POST.get('empresa_web', config.empresa_web).strip()
        config.membrete_color = request.POST.get('membrete_color', config.membrete_color).strip() or '#0f766e'
        config.membrete_mostrar = request.POST.get('membrete_mostrar') == '1'
        config.firma_nombre = request.POST.get('firma_nombre', config.firma_nombre).strip()
        config.firma_cargo = request.POST.get('firma_cargo', config.firma_cargo).strip()

        # Uploads de imágenes
        if 'logo' in request.FILES:
            if config.logo:
                config.logo.delete(save=False)    # elimina el archivo anterior
            config.logo = request.FILES['logo']
        if 'logo_eliminar' in request.POST and config.logo:
            config.logo.delete(save=False)
            config.logo = None

        if 'firma_imagen' in request.FILES:
            if config.firma_imagen:
                config.firma_imagen.delete(save=False)
            config.firma_imagen = request.FILES['firma_imagen']
        if 'firma_imagen_eliminar' in request.POST and config.firma_imagen:
            config.firma_imagen.delete(save=False)
            config.firma_imagen = None

        # Modo del sistema
        config.modo_sistema = request.POST.get('modo_sistema', config.modo_sistema)
        config.programa_nomina = request.POST.get('programa_nomina', config.programa_nomina)
        config.programa_nomina_nombre = request.POST.get('programa_nomina_nombre', '').strip()

        # Módulos activos
        config.mod_prestamos = request.POST.get('mod_prestamos') == '1'
        config.mod_viaticos = request.POST.get('mod_viaticos') == '1'
        config.mod_documentos = request.POST.get('mod_documentos') == '1'
        config.mod_evaluaciones = request.POST.get('mod_evaluaciones') == '1'
        config.mod_capacitaciones = request.POST.get('mod_capacitaciones') == '1'
        config.mod_reclutamiento = request.POST.get('mod_reclutamiento') == '1'
        config.mod_encuestas = request.POST.get('mod_encuestas') == '1'

        # Exportación
        config.export_incluir_sueldo = request.POST.get('export_incluir_sueldo') == '1'
        config.export_incluir_faltas = request.POST.get('export_incluir_faltas') == '1'
        config.export_incluir_banco_horas = request.POST.get('export_incluir_banco_horas') == '1'
        config.export_separar_staff_rco = request.POST.get('export_separar_staff_rco') == '1'
        config.export_formato = request.POST.get('export_formato', config.export_formato)

        # Jornadas
        from decimal import Decimal as D, InvalidOperation
        try:
            val = request.POST.get('jornada_local_horas', '').strip()
            if val:
                config.jornada_local_horas = D(val)
        except (InvalidOperation, ValueError):
            pass
        try:
            val = request.POST.get('jornada_foraneo_horas', '').strip()
            if val:
                config.jornada_foraneo_horas = D(val)
        except (InvalidOperation, ValueError):
            pass

        # Synkro
        config.synkro_hoja_reloj = request.POST.get('synkro_hoja_reloj', config.synkro_hoja_reloj)
        config.synkro_hoja_papeletas = request.POST.get('synkro_hoja_papeletas', config.synkro_hoja_papeletas)
        config.reloj_col_dni = int(request.POST.get('reloj_col_dni', config.reloj_col_dni))
        config.reloj_col_nombre = int(request.POST.get('reloj_col_nombre', config.reloj_col_nombre))
        config.reloj_col_condicion = int(request.POST.get('reloj_col_condicion', config.reloj_col_condicion))
        config.reloj_col_tipo_trab = int(request.POST.get('reloj_col_tipo_trab', config.reloj_col_tipo_trab))
        config.reloj_col_area = int(request.POST.get('reloj_col_area', config.reloj_col_area))
        config.reloj_col_inicio_dias = int(request.POST.get('reloj_col_inicio_dias', config.reloj_col_inicio_dias))

        # Email
        config.email_habilitado = request.POST.get('email_habilitado') == '1'
        config.email_desde = request.POST.get('email_desde', config.email_desde)
        config.email_asunto_semanal = request.POST.get('email_asunto_semanal', config.email_asunto_semanal)
        config.email_dia_envio = int(request.POST.get('email_dia_envio', config.email_dia_envio))

        # IA — Multi-Provider (Fase 4.4)
        config.ia_provider    = request.POST.get('ia_provider', config.ia_provider)
        config.ia_api_key     = request.POST.get('ia_api_key', getattr(config, 'ia_api_key', '')).strip()
        config.ia_endpoint    = request.POST.get('ia_endpoint', config.ia_endpoint).strip()
        config.ia_modelo      = request.POST.get('ia_modelo', config.ia_modelo).strip()
        config.ia_ocr_provider    = request.POST.get('ia_ocr_provider', getattr(config, 'ia_ocr_provider', 'NINGUNO'))
        config.ia_gemini_api_key  = request.POST.get('ia_gemini_api_key', getattr(config, 'ia_gemini_api_key', '')).strip()
        config.ia_mapeo_activo    = request.POST.get('ia_mapeo_activo') == '1'

        # S10
        config.s10_nombre_concepto_he25 = request.POST.get('s10_nombre_concepto_he25', config.s10_nombre_concepto_he25)
        config.s10_nombre_concepto_he35 = request.POST.get('s10_nombre_concepto_he35', config.s10_nombre_concepto_he35)
        config.s10_nombre_concepto_he100 = request.POST.get('s10_nombre_concepto_he100', config.s10_nombre_concepto_he100)

        # Control HE
        config.he_requiere_solicitud = request.POST.get('he_requiere_solicitud') == '1'
        config.he_tipo_default = request.POST.get('he_tipo_default', config.he_tipo_default)

        config.actualizado_por = request.user
        config.save()

        from core.audit import log_update
        log_update(request, config, {'configuracion': {'old': '—', 'new': 'Actualizada'}},
                   'Configuración del sistema actualizada')

        messages.success(request, 'Configuración guardada correctamente.')
        return redirect('asistencia_configuracion')

    # Calcular preview del ciclo actual
    hoy = date.today()
    inicio_he, fin_he = config.get_ciclo_he(hoy.year, hoy.month)
    inicio_asist, fin_asist = config.get_ciclo_asistencia(hoy.year, hoy.month)

    context = {
        'titulo': 'Configuración del Sistema',
        'config': config,
        'preview_ciclo_he': f'{inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
        'preview_asistencia': f'{inicio_asist.strftime("%d/%m/%Y")} → {fin_asist.strftime("%d/%m/%Y")}',
        'dias_semana': [
            (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'),
            (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
        ],
    }
    return render(request, 'asistencia/configuracion.html', context)


# ---------------------------------------------------------------------------
# IA — Test de conexión Ollama (AJAX)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
@require_POST
def ia_test_connection(request):
    """
    Verifica conectividad con el provider IA seleccionado.
    Recibe provider, api_key, endpoint, modelo vía POST.
    Devuelve JSON con {ok, info, error, modelos (Ollama)}.
    """
    from asistencia.services.ai_service import (
        GeminiService, OpenAICompatibleService, OllamaService
    )

    provider = request.POST.get('provider', 'OLLAMA').strip()
    api_key  = request.POST.get('api_key',  '').strip()
    endpoint = request.POST.get('endpoint', '').strip()
    modelo   = request.POST.get('modelo',   '').strip()

    try:
        if provider == 'GEMINI':
            if not api_key:
                return JsonResponse({'ok': False, 'error': 'API Key requerida para Gemini.', 'info': ''})
            svc = GeminiService(api_key=api_key, modelo=modelo or 'gemini-2.5-flash-preview-04-17')

        elif provider == 'DEEPSEEK':
            if not api_key:
                return JsonResponse({'ok': False, 'error': 'API Key requerida para DeepSeek.', 'info': ''})
            svc = OpenAICompatibleService(
                api_key=api_key,
                modelo=modelo or 'deepseek-chat',
                base_url=endpoint or 'https://api.deepseek.com/v1',
                provider_label='DEEPSEEK',
            )

        elif provider == 'OPENAI':
            if not api_key:
                return JsonResponse({'ok': False, 'error': 'API Key requerida para OpenAI.', 'info': ''})
            svc = OpenAICompatibleService(
                api_key=api_key,
                modelo=modelo or 'gpt-4o-mini',
                base_url='https://api.openai.com/v1',
                provider_label='OPENAI',
            )

        elif provider == 'OLLAMA':
            svc = OllamaService(
                endpoint=endpoint or 'http://localhost:11434',
                modelo=modelo or 'llama3.2',
            )

        else:
            return JsonResponse({'ok': False, 'error': f'Provider "{provider}" no reconocido.', 'info': ''})

        result = svc.test_connection()
        return JsonResponse(result)

    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e), 'info': ''})


# ---------------------------------------------------------------------------
# FERIADOS CRUD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
@require_POST
def feriado_crear(request):
    from asistencia.models import FeriadoCalendario
    try:
        f = FeriadoCalendario.objects.create(
            fecha=request.POST['fecha'],
            nombre=request.POST['nombre'].strip(),
            tipo=request.POST.get('tipo', 'NO_RECUPERABLE'),
            activo=True,
        )
        return JsonResponse({
            'ok': True,
            'pk': f.pk,
            'fecha': f.fecha.strftime('%d/%m/%Y'),
            'dia_semana': f.fecha.strftime('%A'),
            'nombre': f.nombre,
            'tipo': f.tipo,
            'tipo_display': f.get_tipo_display(),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def feriado_editar(request, pk):
    from asistencia.models import FeriadoCalendario
    f = get_object_or_404(FeriadoCalendario, pk=pk)
    try:
        f.fecha  = request.POST['fecha']
        f.nombre = request.POST['nombre'].strip()
        f.tipo   = request.POST.get('tipo', f.tipo)
        f.save()
        return JsonResponse({
            'ok': True,
            'pk': f.pk,
            'fecha': f.fecha.strftime('%d/%m/%Y'),
            'dia_semana': f.fecha.strftime('%A'),
            'nombre': f.nombre,
            'tipo': f.tipo,
            'tipo_display': f.get_tipo_display(),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def feriado_eliminar(request, pk):
    from asistencia.models import FeriadoCalendario
    f = get_object_or_404(FeriadoCalendario, pk=pk)
    f.delete()
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# HOMOLOGACIONES CRUD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
@require_POST
def homologacion_crear(request):
    from asistencia.models import HomologacionCodigo
    try:
        h = HomologacionCodigo.objects.create(
            codigo_origen=request.POST['codigo_origen'].strip().upper(),
            codigo_tareo=request.POST['codigo_tareo'].strip().upper(),
            codigo_roster=request.POST.get('codigo_roster', '').strip().upper(),
            descripcion=request.POST['descripcion'].strip(),
            tipo_evento=request.POST.get('tipo_evento', 'OTRO'),
            signo=request.POST.get('signo', '+'),
            cuenta_asistencia=request.POST.get('cuenta_asistencia') == '1',
            genera_he=request.POST.get('genera_he') == '1',
            es_numerico=request.POST.get('es_numerico') == '1',
            prioridad=int(request.POST.get('prioridad', 10)),
            activo=request.POST.get('activo', '1') == '1',
        )
        return JsonResponse(_homologacion_dict(h))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def homologacion_editar(request, pk):
    from asistencia.models import HomologacionCodigo
    h = get_object_or_404(HomologacionCodigo, pk=pk)
    try:
        h.codigo_origen = request.POST['codigo_origen'].strip().upper()
        h.codigo_tareo = request.POST['codigo_tareo'].strip().upper()
        h.codigo_roster = request.POST.get('codigo_roster', '').strip().upper()
        h.descripcion = request.POST['descripcion'].strip()
        h.tipo_evento = request.POST.get('tipo_evento', h.tipo_evento)
        h.signo = request.POST.get('signo', h.signo)
        h.cuenta_asistencia = request.POST.get('cuenta_asistencia') == '1'
        h.genera_he = request.POST.get('genera_he') == '1'
        h.es_numerico = request.POST.get('es_numerico') == '1'
        h.prioridad = int(request.POST.get('prioridad', h.prioridad))
        h.activo = request.POST.get('activo', '1') == '1'
        h.save()
        return JsonResponse(_homologacion_dict(h))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def homologacion_eliminar(request, pk):
    from asistencia.models import HomologacionCodigo
    h = get_object_or_404(HomologacionCodigo, pk=pk)
    h.delete()
    return JsonResponse({'ok': True})


def _homologacion_dict(h):
    return {
        'ok': True,
        'pk': h.pk,
        'codigo_origen': h.codigo_origen,
        'codigo_tareo': h.codigo_tareo,
        'codigo_roster': h.codigo_roster,
        'descripcion': h.descripcion,
        'tipo_evento': h.tipo_evento,
        'tipo_evento_display': h.get_tipo_evento_display(),
        'signo': h.signo,
        'signo_display': dict(h.SIGNO).get(h.signo, h.signo),
        'cuenta_asistencia': h.cuenta_asistencia,
        'genera_he': h.genera_he,
        'es_numerico': h.es_numerico,
        'prioridad': h.prioridad,
        'activo': h.activo,
    }


# ---------------------------------------------------------------------------
# REGÍMENES DE TURNO CRUD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
@require_POST
def regimen_crear(request):
    from asistencia.models import RegimenTurno
    from decimal import Decimal
    try:
        r = RegimenTurno.objects.create(
            nombre=request.POST['nombre'].strip(),
            codigo=request.POST['codigo'].strip().upper(),
            jornada_tipo=request.POST.get('jornada_tipo', 'SEMANAL'),
            dias_trabajo_ciclo=int(request.POST['dias_trabajo']),
            dias_descanso_ciclo=int(request.POST['dias_descanso']),
            minutos_almuerzo=int(request.POST.get('minutos_almuerzo', 60)),
            es_nocturno=request.POST.get('es_nocturno') == '1',
            recargo_nocturno_pct=Decimal(request.POST.get('recargo_nocturno', '35.00')),
            descripcion=request.POST.get('descripcion', '').strip(),
            activo=request.POST.get('activo', '1') == '1',
        )
        return JsonResponse(_regimen_dict(r))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def regimen_editar(request, pk):
    from asistencia.models import RegimenTurno
    from decimal import Decimal
    r = get_object_or_404(RegimenTurno, pk=pk)
    try:
        r.nombre = request.POST['nombre'].strip()
        r.codigo = request.POST['codigo'].strip().upper()
        r.jornada_tipo = request.POST.get('jornada_tipo', r.jornada_tipo)
        r.dias_trabajo_ciclo = int(request.POST['dias_trabajo'])
        r.dias_descanso_ciclo = int(request.POST['dias_descanso'])
        r.minutos_almuerzo = int(request.POST.get('minutos_almuerzo', r.minutos_almuerzo))
        r.es_nocturno = request.POST.get('es_nocturno') == '1'
        r.recargo_nocturno_pct = Decimal(request.POST.get('recargo_nocturno', str(r.recargo_nocturno_pct)))
        r.descripcion = request.POST.get('descripcion', '').strip()
        r.activo = request.POST.get('activo', '1') == '1'
        r.save()
        return JsonResponse(_regimen_dict(r))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def regimen_eliminar(request, pk):
    from asistencia.models import RegimenTurno
    r = get_object_or_404(RegimenTurno, pk=pk)
    # Verificar que no tenga horarios asociados
    if r.horarios.exists():
        return JsonResponse({
            'ok': False,
            'error': f'No se puede eliminar: tiene {r.horarios.count()} horario(s) asociado(s). Elimínelos primero.',
        }, status=400)
    r.delete()
    return JsonResponse({'ok': True})


def _regimen_dict(r):
    return {
        'ok': True,
        'pk': r.pk,
        'nombre': r.nombre,
        'codigo': r.codigo,
        'jornada_tipo': r.jornada_tipo,
        'jornada_tipo_display': r.get_jornada_tipo_display(),
        'dias_trabajo': r.dias_trabajo_ciclo,
        'dias_descanso': r.dias_descanso_ciclo,
        'ciclo': f'{r.dias_trabajo_ciclo}×{r.dias_descanso_ciclo}',
        'minutos_almuerzo': r.minutos_almuerzo,
        'es_nocturno': r.es_nocturno,
        'recargo_nocturno': str(r.recargo_nocturno_pct),
        'horas_max_ciclo': str(r.horas_max_ciclo),
        'descripcion': r.descripcion,
        'activo': r.activo,
    }


# ---------------------------------------------------------------------------
# HORARIOS CRUD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
@require_POST
def horario_crear(request):
    from asistencia.models import TipoHorario, RegimenTurno
    try:
        regimen = get_object_or_404(RegimenTurno, pk=request.POST['regimen'])
        h = TipoHorario.objects.create(
            regimen=regimen,
            nombre=request.POST['nombre'].strip(),
            tipo_dia=request.POST['tipo_dia'],
            hora_entrada=request.POST['hora_entrada'],
            hora_salida=request.POST['hora_salida'],
            salida_dia_siguiente=request.POST.get('salida_dia_siguiente') == '1',
            activo=request.POST.get('activo', '1') == '1',
        )
        h.refresh_from_db()
        return JsonResponse(_horario_dict(h))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def horario_editar(request, pk):
    from asistencia.models import TipoHorario, RegimenTurno
    h = get_object_or_404(TipoHorario, pk=pk)
    try:
        h.regimen = get_object_or_404(RegimenTurno, pk=request.POST['regimen'])
        h.nombre = request.POST['nombre'].strip()
        h.tipo_dia = request.POST['tipo_dia']
        h.hora_entrada = request.POST['hora_entrada']
        h.hora_salida = request.POST['hora_salida']
        h.salida_dia_siguiente = request.POST.get('salida_dia_siguiente') == '1'
        h.activo = request.POST.get('activo', '1') == '1'
        h.save()
        h.refresh_from_db()
        return JsonResponse(_horario_dict(h))
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def horario_eliminar(request, pk):
    from asistencia.models import TipoHorario
    h = get_object_or_404(TipoHorario, pk=pk)
    h.delete()
    return JsonResponse({'ok': True})


def _horario_dict(h):
    return {
        'ok': True,
        'pk': h.pk,
        'regimen_pk': h.regimen_id,
        'regimen_nombre': h.regimen.nombre,
        'regimen_codigo': h.regimen.codigo,
        'nombre': h.nombre,
        'tipo_dia': h.tipo_dia,
        'tipo_dia_display': h.get_tipo_dia_display(),
        'hora_entrada': h.hora_entrada.strftime('%H:%M'),
        'hora_salida': h.hora_salida.strftime('%H:%M'),
        'salida_dia_siguiente': h.salida_dia_siguiente,
        'horas_brutas': f'{h.horas_brutas:.2f}',
        'horas_efectivas': f'{h.horas_efectivas:.2f}',
        'activo': h.activo,
    }


@login_required
@solo_admin
@require_POST
def feriados_cargar_peru(request):
    """Carga los feriados nacionales del Perú para el año indicado."""
    from asistencia.models import FeriadoCalendario
    import datetime

    anio = int(request.POST.get('anio', date.today().year))

    # Feriados fijos Perú (D.Leg. 713 + Ley 29088 + otros)
    FERIADOS_FIJOS = [
        (1,  1,  'Año Nuevo'),
        (5,  1,  'Día del Trabajo'),
        (6,  7,  'San Pedro y San Pablo'),
        (7,  28, 'Fiestas Patrias — Independencia'),
        (7,  29, 'Fiestas Patrias — Gran Unidad Nacional'),
        (8,  6,  'Batalla de Junín'),
        (8,  30, 'Santa Rosa de Lima'),
        (10, 8,  'Combate de Angamos'),
        (11, 1,  'Todos los Santos'),
        (12, 8,  'Inmaculada Concepción'),
        (12, 9,  'Batalla de Ayacucho'),
        (12, 25, 'Navidad'),
    ]

    creados = 0
    existentes = 0
    for mes, dia, nombre in FERIADOS_FIJOS:
        fecha = datetime.date(anio, mes, dia)
        _, created = FeriadoCalendario.objects.get_or_create(
            fecha=fecha,
            defaults={'nombre': nombre, 'tipo': 'NO_RECUPERABLE'},
        )
        if created:
            creados += 1
        else:
            existentes += 1

    return JsonResponse({
        'ok': True,
        'creados': creados,
        'existentes': existentes,
        'mensaje': f'{creados} feriados creados, {existentes} ya existían para {anio}',
    })
