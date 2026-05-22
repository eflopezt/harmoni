"""
Vistas del módulo Evaluaciones 360° (dedicado).
Maneja el ciclo completo:
  - Panel admin con filtros
  - Wizard de creación con invitación de participantes
  - Detalle con tabla comparativa + radar
  - Responder cuestionario
  - Exportación PDF
"""
import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

try:
    from personal.models import Personal
except ImportError:  # pragma: no cover
    Personal = None

from .models import (
    COMPETENCIAS_GASTRO_360,
    Competencia,
    Evaluacion360,
    ParticipanteEvaluacion360,
    RespuestaCompetencia360,
)

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

TIPO_LABEL = {
    'AUTOEVALUACION': 'Auto',
    'MANAGER': 'Manager',
    'PEER': 'Peers',
    'SUBORDINADO': 'Subordinados',
    'CLIENTE_INTERNO': 'Cliente Interno',
}

TIPO_COLOR = {
    'AUTOEVALUACION': '#6366f1',
    'MANAGER':        '#0f766e',
    'PEER':           '#f59e0b',
    'SUBORDINADO':    '#3b82f6',
    'CLIENTE_INTERNO': '#a855f7',
}


def _competencias_activas():
    """
    Devuelve lista [(codigo, label, competencia_obj_or_None)] con las
    competencias a usar para el cuestionario 360. Si hay competencias
    en BD se priorizan; si no, se cae a la lista gastronómica.
    """
    qs = Competencia.objects.filter(activa=True).order_by('orden', 'nombre')
    if qs.exists():
        # Filtra a las gastro relevantes si existen, sino toma primeras 6.
        codigos_gastro = {c[0] for c in COMPETENCIAS_GASTRO_360}
        prioridad = list(qs.filter(codigo__in=codigos_gastro))
        if len(prioridad) >= 4:
            seleccion = prioridad[:8]
        else:
            seleccion = list(qs[:8])
        return [(c.codigo, c.nombre, c) for c in seleccion]
    return [(cod, label, None) for cod, label in COMPETENCIAS_GASTRO_360]


# ──────────────────────────────────────────────────────────────
# Panel admin
# ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
def panel_360(request):
    """Lista de evaluaciones 360 con filtros por estado y periodo."""
    qs = Evaluacion360.objects.select_related('personal_evaluado').all()

    estado = (request.GET.get('estado') or '').strip()
    periodo = (request.GET.get('periodo') or '').strip()
    q = (request.GET.get('q') or '').strip()

    if estado:
        qs = qs.filter(estado=estado)
    if periodo:
        qs = qs.filter(periodo__icontains=periodo)
    if q:
        qs = qs.filter(personal_evaluado__apellidos_nombres__icontains=q)

    # KPIs
    total = Evaluacion360.objects.count()
    en_curso = Evaluacion360.objects.filter(estado='EN_CURSO').count()
    cerradas = Evaluacion360.objects.filter(estado='CERRADA').count()
    borradores = Evaluacion360.objects.filter(estado='BORRADOR').count()

    periodos = Evaluacion360.objects.values_list('periodo', flat=True).distinct()

    context = {
        'titulo': 'Evaluaciones 360°',
        'evaluaciones': qs[:100],
        'total': qs.count(),
        'kpis': {
            'total': total,
            'en_curso': en_curso,
            'cerradas': cerradas,
            'borradores': borradores,
        },
        'filtro_estado': estado,
        'filtro_periodo': periodo,
        'filtro_q': q,
        'periodos_disponibles': sorted({p for p in periodos if p}),
        'estado_choices': Evaluacion360.ESTADO_CHOICES,
    }
    return render(request, 'evaluaciones/panel_360.html', context)


# ──────────────────────────────────────────────────────────────
# Crear (wizard)
# ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
def crear_360(request):
    """Wizard: selecciona evaluado + invita participantes y crea evaluación."""
    if request.method == 'POST':
        try:
            evaluado_id = request.POST.get('personal_evaluado')
            periodo = (request.POST.get('periodo') or '').strip() or f'{date.today().year}-Q{((date.today().month-1)//3)+1}'
            if not evaluado_id:
                raise ValueError('Debe seleccionar al evaluado.')
            evaluado = Personal.objects.get(pk=evaluado_id) if Personal else None
            if evaluado is None:
                raise ValueError('Modelo Personal no disponible.')

            fecha_inicio = request.POST.get('fecha_inicio') or date.today().isoformat()
            fecha_cierre = request.POST.get('fecha_cierre') or ''

            evaluacion = Evaluacion360.objects.create(
                personal_evaluado=evaluado,
                periodo=periodo,
                estado='EN_CURSO',
                fecha_inicio=fecha_inicio or None,
                fecha_cierre=fecha_cierre or None,
                creado_por=request.user if request.user.is_authenticated else None,
            )

            # Participantes invitados: campos tipo arrays paralelos
            tipos = request.POST.getlist('participante_tipo')
            personas = request.POST.getlist('participante_persona')
            creados = 0
            # Asegura siempre la autoevaluación
            ParticipanteEvaluacion360.objects.create(
                evaluacion=evaluacion,
                tipo='AUTOEVALUACION',
                personal_evaluador=evaluado,
            )
            creados += 1
            for tipo, persona_id in zip(tipos, personas):
                if not tipo or tipo == 'AUTOEVALUACION':
                    continue
                persona = None
                if persona_id and Personal:
                    try:
                        persona = Personal.objects.get(pk=persona_id)
                    except Personal.DoesNotExist:
                        persona = None
                ParticipanteEvaluacion360.objects.create(
                    evaluacion=evaluacion,
                    tipo=tipo,
                    personal_evaluador=persona,
                )
                creados += 1

            messages.success(
                request,
                f'Evaluación 360° creada para {evaluado.apellidos_nombres} con {creados} participantes.',
            )
            return redirect('evaluacion_360_detalle', pk=evaluacion.pk)
        except Exception as exc:
            messages.error(request, f'Error al crear evaluación: {exc}')

    # GET: render wizard
    personal_qs = []
    if Personal is not None:
        personal_qs = Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')[:500]

    context = {
        'titulo': 'Nueva Evaluación 360°',
        'personal_disponible': personal_qs,
        'tipos_participante': ParticipanteEvaluacion360.TIPO_CHOICES,
        'periodo_default': f'{date.today().year}-Q{((date.today().month-1)//3)+1}',
    }
    return render(request, 'evaluaciones/crear_360.html', context)


# ──────────────────────────────────────────────────────────────
# Detalle (tabla comparativa + radar)
# ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
def detalle_360(request, pk):
    evaluacion = get_object_or_404(
        Evaluacion360.objects.select_related('personal_evaluado'), pk=pk,
    )
    participantes = list(evaluacion.participantes.select_related('personal_evaluador').all())
    matriz = evaluacion.matriz_comparativa()
    gaps = evaluacion.gaps_auto_manager()

    tipos_orden = ['AUTOEVALUACION', 'MANAGER', 'PEER', 'SUBORDINADO', 'CLIENTE_INTERNO']

    # Filas para template: lista de dicts con label + valores por tipo
    filas = []
    for cod, info in matriz.items():
        valores = []
        for tipo in tipos_orden:
            valor = info['promedios'].get(tipo)
            valores.append({
                'tipo': tipo,
                'valor': valor,
            })
        filas.append({
            'codigo': cod,
            'label': info['label'],
            'valores': valores,
        })

    # Datos para Chart.js radar
    radar_labels = [info['label'] for info in matriz.values()]
    radar_datasets = []
    for tipo in tipos_orden:
        data = []
        for info in matriz.values():
            v = info['promedios'].get(tipo)
            data.append(float(v) if v is not None else None)
        # Solo incluir el dataset si tiene al menos una respuesta no-nula
        if any(d is not None for d in data):
            radar_datasets.append({
                'label': TIPO_LABEL.get(tipo, tipo),
                'data': data,
                'borderColor': TIPO_COLOR.get(tipo, '#64748b'),
                'backgroundColor': TIPO_COLOR.get(tipo, '#64748b') + '33',
                'fill': True,
                'tension': 0.2,
            })

    # Anonimiza peers/subordinados
    peers_count = 0
    subord_count = 0
    participantes_publicos = []
    for p in participantes:
        if p.tipo == 'PEER':
            peers_count += 1
            display = f'Peer {peers_count}'
        elif p.tipo == 'SUBORDINADO':
            subord_count += 1
            display = f'Subordinado {subord_count}'
        elif p.tipo == 'AUTOEVALUACION':
            display = 'Autoevaluación'
        elif p.tipo == 'MANAGER':
            display = p.personal_evaluador.apellidos_nombres if p.personal_evaluador else 'Manager'
        else:
            display = TIPO_LABEL.get(p.tipo, p.tipo)
        participantes_publicos.append({
            'pk': p.pk,
            'display': display,
            'tipo': p.tipo,
            'tipo_label': p.get_tipo_display(),
            'completada': p.completada,
            'puntaje': p.puntaje_global,
        })

    context = {
        'titulo': f'Evaluación 360° — {evaluacion.personal_evaluado.apellidos_nombres}',
        'evaluacion': evaluacion,
        'participantes': participantes_publicos,
        'filas': filas,
        'tipos_orden': tipos_orden,
        'tipo_label': TIPO_LABEL,
        'gaps': gaps,
        'puntaje_global': evaluacion.puntaje_global,
        'porcentaje_avance': evaluacion.porcentaje_avance,
        'radar_labels_json': json.dumps(radar_labels),
        'radar_datasets_json': json.dumps(radar_datasets),
    }
    return render(request, 'evaluaciones/detalle_360.html', context)


# ──────────────────────────────────────────────────────────────
# Responder (formulario evaluador)
# ──────────────────────────────────────────────────────────────

@login_required
def responder_360(request, pk, participante_pk):
    evaluacion = get_object_or_404(Evaluacion360, pk=pk)
    participante = get_object_or_404(
        ParticipanteEvaluacion360, pk=participante_pk, evaluacion=evaluacion,
    )

    competencias = _competencias_activas()

    if request.method == 'POST':
        try:
            for codigo, label, comp in competencias:
                raw = request.POST.get(f'puntaje_{codigo}')
                if not raw:
                    continue
                try:
                    puntaje = Decimal(raw)
                except (InvalidOperation, TypeError):
                    continue
                if puntaje < Decimal('0'):
                    puntaje = Decimal('0')
                if puntaje > Decimal('5'):
                    puntaje = Decimal('5')
                comentario = request.POST.get(f'comentario_{codigo}', '').strip()
                RespuestaCompetencia360.objects.update_or_create(
                    participante=participante,
                    competencia_codigo=codigo,
                    defaults={
                        'competencia': comp,
                        'competencia_label': label,
                        'puntaje': puntaje,
                        'comentario': comentario,
                    },
                )

            participante.comentario_general = request.POST.get('comentario_general', '').strip()
            participante.fortalezas = request.POST.get('fortalezas', '').strip()
            participante.areas_mejora = request.POST.get('areas_mejora', '').strip()
            participante.completada = True
            participante.fecha_completada = timezone.now()
            participante.save()
            participante.calcular_puntaje_global()

            messages.success(request, 'Respuestas guardadas. ¡Gracias!')
            return redirect('evaluacion_360_detalle', pk=evaluacion.pk)
        except Exception as exc:
            messages.error(request, f'Error guardando respuestas: {exc}')

    # GET: prellenar con respuestas previas si existen
    previas = {r.competencia_codigo: r for r in participante.respuestas.all()}
    items = []
    for codigo, label, comp in competencias:
        r = previas.get(codigo)
        items.append({
            'codigo': codigo,
            'label': label,
            'descripcion': (comp.descripcion if comp else ''),
            'puntaje': r.puntaje if r else '',
            'comentario': r.comentario if r else '',
        })

    context = {
        'titulo': f'Responder 360° — {evaluacion.personal_evaluado.apellidos_nombres}',
        'evaluacion': evaluacion,
        'participante': participante,
        'items': items,
    }
    return render(request, 'evaluaciones/responder_360.html', context)


# ──────────────────────────────────────────────────────────────
# Cerrar
# ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def cerrar_360(request, pk):
    evaluacion = get_object_or_404(Evaluacion360, pk=pk)
    evaluacion.estado = 'CERRADA'
    if not evaluacion.fecha_cierre:
        evaluacion.fecha_cierre = date.today()
    evaluacion.save(update_fields=['estado', 'fecha_cierre', 'actualizado_en'])
    messages.success(request, 'Evaluación cerrada.')
    return redirect('evaluacion_360_detalle', pk=evaluacion.pk)


# ──────────────────────────────────────────────────────────────
# PDF
# ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
def pdf_360(request, pk):
    evaluacion = get_object_or_404(
        Evaluacion360.objects.select_related('personal_evaluado'), pk=pk,
    )
    from .pdf_evaluacion_360 import build_reporte_360_pdf
    buffer = build_reporte_360_pdf(evaluacion)
    nombre = (evaluacion.personal_evaluado.apellidos_nombres or 'evaluado').split()[0]
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="360_{nombre}_{evaluacion.periodo}.pdf"'
    )
    return response
