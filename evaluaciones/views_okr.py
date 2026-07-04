"""
Vistas del módulo OKR (Objetivos y Resultados Clave).
Parte del módulo Evaluaciones.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from personal.models import Personal
from .models import (
    CicloEvaluacion,
    ObjetivoClave, ResultadoClave, CheckInOKR,
)

# RBAC (WS1): superuser o staff con mod_evaluaciones en su PerfilAcceso.
from core.permisos import requiere_modulo
solo_admin = requiere_modulo('evaluaciones')
# ── Panel principal ──────────────────────────────────────────────

@login_required
@solo_admin
def okr_panel(request):
    """Panel de OKRs: todos los objetivos con filtros."""
    from personal.models import Area

    qs = ObjetivoClave.objects.select_related(
        'personal', 'area', 'objetivo_padre',
    ).prefetch_related('resultados_clave').order_by('-anio', 'trimestre', 'nivel', 'titulo')

    # Filtros
    nivel       = request.GET.get('nivel', '')
    status      = request.GET.get('status', 'ACTIVO')
    try:
        anio    = int(request.GET.get('anio', date.today().year))
    except (ValueError, TypeError):
        anio    = date.today().year
    area_id     = request.GET.get('area', '')
    personal_id = request.GET.get('personal', '')

    if nivel:
        qs = qs.filter(nivel=nivel)
    if status and status != 'TODOS':
        qs = qs.filter(status=status)
    qs = qs.filter(anio=anio)
    if area_id:
        qs = qs.filter(area_id=area_id)
    if personal_id:
        qs = qs.filter(personal_id=personal_id)

    # Stats del año
    todos = ObjetivoClave.objects.filter(anio=anio)
    stats = {
        'empresa':     todos.filter(nivel='EMPRESA').count(),
        'area':        todos.filter(nivel='AREA').count(),
        'individual':  todos.filter(nivel='INDIVIDUAL').count(),
        'completados': todos.filter(status='COMPLETADO').count(),
        'en_riesgo':   todos.filter(status='EN_RIESGO').count(),
        'activos':     todos.filter(status='ACTIVO').count(),
        'total':       todos.count(),
    }

    context = {
        'titulo': 'OKRs — Objetivos y Resultados Clave',
        'objetivos': qs[:200],
        'stats': stats,
        'filtro_nivel':    nivel,
        'filtro_status':   status,
        'filtro_anio':     anio,
        'filtro_area':     area_id,
        'filtro_personal': personal_id,
        'nivel_choices':   ObjetivoClave.NIVEL_CHOICES,
        'status_choices':  ObjetivoClave.STATUS_CHOICES,
        'areas':           Area.objects.filter(activa=True).order_by('nombre'),
        'personal_list':   Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
        'anios':           list(range(date.today().year - 2, date.today().year + 3)),
    }
    return render(request, 'evaluaciones/okr_panel.html', context)


# ── CRUD Objetivos ───────────────────────────────────────────────

@login_required
@solo_admin
def okr_crear(request):
    """Crear un nuevo objetivo OKR."""
    from personal.models import Area

    if request.method == 'POST':
        try:
            personal_id = request.POST.get('personal_id') or None
            area_id     = request.POST.get('area_id') or None
            padre_id    = request.POST.get('objetivo_padre_id') or None
            ciclo_id    = request.POST.get('ciclo_id') or None
            trimestre   = request.POST.get('trimestre') or None

            obj = ObjetivoClave.objects.create(
                titulo=request.POST['titulo'],
                descripcion=request.POST.get('descripcion', ''),
                nivel=request.POST.get('nivel', 'INDIVIDUAL'),
                personal_id=personal_id,
                area_id=area_id,
                objetivo_padre_id=padre_id,
                ciclo_evaluacion_id=ciclo_id,
                periodo=request.POST.get('periodo', 'TRIMESTRAL'),
                anio=int(request.POST.get('anio', date.today().year)),
                trimestre=int(trimestre) if trimestre else None,
                peso=request.POST.get('peso', '100.00') or '100.00',
                status='BORRADOR',
                creado_por=request.user,
            )
            messages.success(request, f'Objetivo "{obj.titulo}" creado. Agrega los Key Results.')
            return redirect('okr_detalle', pk=obj.pk)
        except Exception as e:
            messages.error(request, f'Error al crear objetivo: {e}')

    padres = ObjetivoClave.objects.filter(
        status__in=['BORRADOR', 'ACTIVO'],
        anio=date.today().year,
    ).exclude(nivel='INDIVIDUAL').order_by('nivel', 'titulo')

    context = {
        'titulo': 'Nuevo Objetivo (OKR)',
        'obj': None,
        'personal_list': Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
        'areas':    Area.objects.filter(activa=True).order_by('nombre'),
        'padres':   padres,
        'ciclos':   CicloEvaluacion.objects.filter(
            estado__in=['BORRADOR', 'ABIERTO', 'EN_EVALUACION']
        ).order_by('-fecha_inicio'),
        'nivel_choices':   ObjetivoClave.NIVEL_CHOICES,
        'periodo_choices': ObjetivoClave.PERIODO_CHOICES,
        'anio_actual': date.today().year,
        'anios': list(range(date.today().year - 1, date.today().year + 3)),
    }
    return render(request, 'evaluaciones/okr_form.html', context)


@login_required
@solo_admin
def okr_editar(request, pk):
    """Editar un objetivo OKR."""
    from personal.models import Area

    obj = get_object_or_404(ObjetivoClave, pk=pk)

    if request.method == 'POST':
        try:
            obj.titulo      = request.POST['titulo']
            obj.descripcion = request.POST.get('descripcion', '')
            obj.nivel       = request.POST.get('nivel', obj.nivel)
            obj.personal_id = request.POST.get('personal_id') or None
            obj.area_id     = request.POST.get('area_id') or None
            padre_id        = request.POST.get('objetivo_padre_id') or None
            obj.objetivo_padre_id = int(padre_id) if padre_id else None
            obj.periodo     = request.POST.get('periodo', obj.periodo)
            obj.anio        = int(request.POST.get('anio', obj.anio))
            trimestre       = request.POST.get('trimestre') or None
            obj.trimestre   = int(trimestre) if trimestre else None
            obj.peso        = request.POST.get('peso', obj.peso) or obj.peso
            obj.ciclo_evaluacion_id = request.POST.get('ciclo_id') or None
            obj.save()
            messages.success(request, 'Objetivo actualizado.')
            return redirect('okr_detalle', pk=obj.pk)
        except Exception as e:
            messages.error(request, f'Error: {e}')

    padres = ObjetivoClave.objects.filter(
        status__in=['BORRADOR', 'ACTIVO'],
        anio=obj.anio,
    ).exclude(pk=obj.pk).exclude(nivel='INDIVIDUAL').order_by('nivel', 'titulo')

    context = {
        'titulo': f'Editar: {obj.titulo}',
        'obj': obj,
        'personal_list': Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
        'areas':    Area.objects.filter(activa=True).order_by('nombre'),
        'padres':   padres,
        'ciclos':   CicloEvaluacion.objects.filter(
            estado__in=['BORRADOR', 'ABIERTO', 'EN_EVALUACION']
        ).order_by('-fecha_inicio'),
        'nivel_choices':   ObjetivoClave.NIVEL_CHOICES,
        'periodo_choices': ObjetivoClave.PERIODO_CHOICES,
        'anios': list(range(date.today().year - 1, date.today().year + 3)),
    }
    return render(request, 'evaluaciones/okr_form.html', context)


@login_required
@solo_admin
def okr_detalle(request, pk):
    """Detalle de un objetivo: KRs, check-ins, objetivos hijo, cascada."""
    obj = get_object_or_404(
        ObjetivoClave.objects.select_related('personal', 'area', 'objetivo_padre'),
        pk=pk,
    )
    krs    = obj.resultados_clave.select_related('responsable').prefetch_related('checkins').order_by('orden')
    hijos  = obj.objetivos_hijo.select_related('personal', 'area').prefetch_related('resultados_clave')

    context = {
        'titulo':       obj.titulo,
        'obj':          obj,
        'krs':          krs,
        'hijos':        hijos,
        'avance':       obj.avance_promedio,
        'personal_list': Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
        'status_choices': ObjetivoClave.STATUS_CHOICES,
        'unidad_choices': ResultadoClave.UNIDAD_CHOICES,
    }
    return render(request, 'evaluaciones/okr_detalle.html', context)


@login_required
@solo_admin
@require_POST
def okr_cambiar_status(request, pk):
    """Cambia el status de un objetivo (AJAX)."""
    obj = get_object_or_404(ObjetivoClave, pk=pk)
    nuevo_status = request.POST.get('status', '')
    validos = [s[0] for s in ObjetivoClave.STATUS_CHOICES]
    if nuevo_status not in validos:
        return JsonResponse({'ok': False, 'error': 'Status inválido.'}, status=400)
    obj.status = nuevo_status
    obj.save(update_fields=['status', 'actualizado_en'])
    return JsonResponse({
        'ok': True, 'status': nuevo_status,
        'label': obj.get_status_display(),
        'avance': obj.avance_promedio,
    })


@login_required
@solo_admin
@require_POST
def okr_eliminar(request, pk):
    """Elimina un objetivo (solo si BORRADOR)."""
    obj = get_object_or_404(ObjetivoClave, pk=pk)
    if obj.status != 'BORRADOR':
        return JsonResponse({'ok': False, 'error': 'Solo se pueden eliminar objetivos en estado Borrador.'}, status=400)
    titulo = obj.titulo
    obj.delete()
    return JsonResponse({'ok': True, 'titulo': titulo})


# ── Key Results CRUD (AJAX) ──────────────────────────────────────

@login_required
@solo_admin
@require_POST
def kr_crear(request, objetivo_pk):
    """Agrega un Key Result a un objetivo."""
    obj = get_object_or_404(ObjetivoClave, pk=objetivo_pk)
    try:
        responsable_id = request.POST.get('responsable_id') or None
        kr = ResultadoClave.objects.create(
            objetivo=obj,
            descripcion=request.POST['descripcion'],
            unidad=request.POST.get('unidad', 'PORCENTAJE'),
            unidad_personalizada=request.POST.get('unidad_personalizada', ''),
            valor_inicial=request.POST.get('valor_inicial') or '0',
            valor_meta=request.POST['valor_meta'],
            valor_actual=request.POST.get('valor_actual') or request.POST.get('valor_inicial') or '0',
            fecha_limite=date.fromisoformat(request.POST['fecha_limite']) if request.POST.get('fecha_limite') else None,
            responsable_id=responsable_id,
            orden=obj.resultados_clave.count(),
        )
        return JsonResponse({
            'ok': True, 'pk': kr.pk,
            'descripcion': kr.descripcion,
            'avance': kr.porcentaje_avance,
            'unidad_label': kr.unidad_label,
            'color': kr.color_avance,
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def kr_actualizar(request, pk):
    """Edita un Key Result."""
    kr = get_object_or_404(ResultadoClave, pk=pk)
    try:
        kr.descripcion = request.POST.get('descripcion', kr.descripcion)
        kr.unidad      = request.POST.get('unidad', kr.unidad)
        kr.unidad_personalizada = request.POST.get('unidad_personalizada', kr.unidad_personalizada)
        kr.valor_meta  = request.POST.get('valor_meta', kr.valor_meta)
        kr.valor_actual= request.POST.get('valor_actual', kr.valor_actual)
        kr.valor_inicial= request.POST.get('valor_inicial', kr.valor_inicial)
        kr.fecha_limite = date.fromisoformat(request.POST['fecha_limite']) if request.POST.get('fecha_limite') else None
        kr.responsable_id = request.POST.get('responsable_id') or None
        if kr.unidad == 'SI_NO':
            kr.completado_binario = request.POST.get('completado_binario') == '1'
        kr.save()
        return JsonResponse({'ok': True, 'avance': kr.porcentaje_avance, 'color': kr.color_avance})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def kr_eliminar(request, pk):
    """Elimina un Key Result."""
    kr = get_object_or_404(ResultadoClave, pk=pk)
    kr.delete()
    return JsonResponse({'ok': True})


# ── Check-ins ────────────────────────────────────────────────────

@login_required
@require_POST
def checkin_registrar(request, kr_pk):
    """Registra un check-in de progreso. Admin o responsable del KR."""
    kr = get_object_or_404(ResultadoClave, pk=kr_pk)

    # Autorización
    if not request.user.is_superuser:
        from portal.views import _get_empleado
        empleado = _get_empleado(request.user)
        if not (empleado and kr.responsable == empleado):
            return JsonResponse({'ok': False, 'error': 'Sin permiso para este KR.'}, status=403)

    try:
        valor_nuevo = request.POST['valor_nuevo']
        checkin = CheckInOKR.objects.create(
            resultado_clave=kr,
            fecha=date.fromisoformat(request.POST['fecha']) if request.POST.get('fecha') else date.today(),
            valor_nuevo=valor_nuevo,
            comentario=request.POST.get('comentario', ''),
            registrado_por=request.user,
        )
        # Actualizar valor actual del KR
        kr.valor_actual = valor_nuevo
        if kr.unidad == 'SI_NO':
            kr.completado_binario = float(valor_nuevo) >= float(kr.valor_meta)
        kr.save(update_fields=['valor_actual', 'completado_binario'])

        return JsonResponse({
            'ok': True, 'pk': checkin.pk,
            'avance': kr.porcentaje_avance,
            'color': kr.color_avance,
            'valor': str(kr.valor_actual),
            'fecha': checkin.fecha.strftime('%d/%m/%Y'),
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


# ── Portal trabajador ─────────────────────────────────────────────

@login_required
def mis_okrs(request):
    """Portal: Mis OKRs — objetivos individuales y KRs asignados."""
    from portal.views import _get_empleado
    empleado  = _get_empleado(request.user)

    mis_objetivos = []
    krs_asignados = []

    try:
        anio = int(request.GET.get('anio', date.today().year))
    except (ValueError, TypeError):
        anio = date.today().year

    if empleado:
        mis_objetivos = ObjetivoClave.objects.filter(
            personal=empleado, anio=anio,
        ).prefetch_related('resultados_clave').order_by('trimestre', 'titulo')

        krs_asignados = ResultadoClave.objects.filter(
            responsable=empleado,
            objetivo__anio=anio,
        ).exclude(
            objetivo__personal=empleado,
        ).select_related('objetivo')

    context = {
        'titulo': 'Mis OKRs',
        'empleado':      empleado,
        'mis_objetivos': mis_objetivos,
        'krs_asignados': krs_asignados,
        'anio_filtro':   anio,
        'anios':         list(range(date.today().year - 1, date.today().year + 2)),
    }
    return render(request, 'evaluaciones/mis_okrs.html', context)
