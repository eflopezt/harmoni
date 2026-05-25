"""
personal/views/cesar.py — Wizard de 3 pasos para cesar trabajador (Sprint 2 Liquidaciones).

Flujo:
  Paso 1: GET   /personal/<id>/cesar/             → form (fecha, motivo, observaciones)
  Paso 2: POST  /personal/<id>/cesar/preview/     → JSON con conceptos calculados (no persiste)
  Paso 3: POST  /personal/<id>/cesar/confirmar/   → persiste cese + signal crea LL + redirect

Reutiliza `LiquidacionLaboral.calcular(persist=False)` del Sprint 1 — NO duplica lógica.
La complementa con un mapeo entre los 13 motivos de `Personal.MOTIVO_CESE_CHOICES`
y los 8 motivos de `LiquidacionLaboral.MOTIVO_CESE_CHOICES`.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from personal.models import Personal


solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


# Motivos visibles en el wizard — los 8 oficiales de LiquidacionLaboral
# (más completos que los de Personal para fines de cálculo legal).
MOTIVOS_WIZARD = [
    ('RENUNCIA',       'Renuncia voluntaria'),
    ('DESPIDO',        'Despido (causa justa)'),
    ('DESPIDO_ARB',    'Despido arbitrario (indemnización)'),
    ('MUTUO',          'Mutuo disenso'),
    ('CADUCIDAD',      'Caducidad de contrato'),
    ('JUBILACION',     'Jubilación'),
    ('FALLECIMIENTO',  'Fallecimiento'),
    ('PERIODO_PRUEBA', 'No supera período de prueba'),
]


# Mapeo inverso: LiquidacionLaboral motive → Personal.motivo_cese
# Necesario porque al guardar Personal, el signal hace el mapeo opuesto.
_MAP_LIQ_A_PERSONAL = {
    'RENUNCIA':       'RENUNCIA',
    'DESPIDO':        'DESPIDO_CAUSA',
    'DESPIDO_ARB':    'DESPIDO_CAUSA',   # signal lo mapeará a DESPIDO; sobrescribimos LL después
    'MUTUO':          'MUTUO_ACUERDO',
    'CADUCIDAD':      'VENCIMIENTO',
    'JUBILACION':     'JUBILACION',
    'FALLECIMIENTO':  'FALLECIMIENTO',
    'PERIODO_PRUEBA': 'DESPIDO_CAUSA',
}


def _validar_form(request) -> tuple[date | None, str, str, str | None]:
    """Devuelve (fecha_cese, motivo, observaciones, error_msg)."""
    fecha_str = (request.POST.get('fecha_cese') or '').strip()
    motivo    = (request.POST.get('motivo_cese') or '').strip()
    obs       = (request.POST.get('observaciones') or '').strip()

    if not fecha_str:
        return None, motivo, obs, 'La fecha de cese es obligatoria.'
    try:
        fecha = date.fromisoformat(fecha_str)
    except ValueError:
        return None, motivo, obs, 'Fecha de cese inválida.'
    if fecha > date.today():
        return None, motivo, obs, 'La fecha de cese no puede ser futura.'
    if motivo not in dict(MOTIVOS_WIZARD):
        return None, motivo, obs, 'Motivo de cese inválido.'
    return fecha, motivo, obs, None


# ──────────────────────────────────────────────────────────────────────
# PASO 1 — Form inicial
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def cesar_wizard_paso1(request, personal_id):
    """GET — render del wizard con form vacío. Si el trabajador ya está cesado,
    redirige a su liquidación (o al detalle si no la tiene)."""
    personal = get_object_or_404(Personal, pk=personal_id)

    if personal.estado == 'Cesado':
        # Intentar redirigir a la LL si existe
        try:
            from nominas.models import LiquidacionLaboral
            liq = LiquidacionLaboral.objects.filter(personal=personal).first()
            if liq:
                messages.info(
                    request,
                    f'{personal.apellidos_nombres} ya figura como cesado.'
                )
                return redirect('nominas_liquidacion_laboral_detalle', liquidacion_id=liq.pk)
        except Exception:
            pass
        messages.warning(request, f'{personal.apellidos_nombres} ya está cesado.')
        return redirect('personal_detail', pk=personal_id)

    context = {
        'personal':       personal,
        'motivos_wizard': MOTIVOS_WIZARD,
        'today':          date.today(),
    }
    return render(request, 'personal/cesar_wizard.html', context)


# ──────────────────────────────────────────────────────────────────────
# PASO 2 — Preview (cálculo sin persistir)
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def cesar_wizard_preview(request, personal_id):
    """POST AJAX — calcula la liquidación temporalmente sin tocar BD.

    Reusa `LiquidacionLaboral(...).calcular(persist=False)` del Sprint 1.
    Devuelve JSON con todos los conceptos (haberes, descuentos, totales).
    """
    personal = get_object_or_404(Personal, pk=personal_id)

    if personal.estado == 'Cesado':
        return JsonResponse(
            {'error': f'{personal.apellidos_nombres} ya está cesado.'},
            status=400,
        )

    fecha_cese, motivo, obs, err = _validar_form(request)
    if err:
        return JsonResponse({'error': err}, status=400)

    # ── Instanciar LL en memoria (sin guardar) ──────────────────────────
    from nominas.models import LiquidacionLaboral
    ll_tmp = LiquidacionLaboral(
        personal=personal,
        fecha_cese=fecha_cese,
        motivo_cese=motivo,
        observaciones=obs,
    )

    try:
        ll_tmp.calcular(persist=False)
    except Exception as exc:
        return JsonResponse(
            {'error': f'Error al calcular liquidación: {exc}'},
            status=500,
        )

    def _d(v: Any) -> str:
        return f'{Decimal(str(v or 0)):.2f}'

    data = {
        'success':       True,
        'personal': {
            'pk':      personal.pk,
            'nombre':  personal.apellidos_nombres,
            'nro_doc': personal.nro_doc,
            'cargo':   personal.cargo or '',
            'sueldo':  _d(personal.sueldo_base),
        },
        'fecha_cese':    fecha_cese.isoformat(),
        'motivo':        motivo,
        'motivo_label':  dict(MOTIVOS_WIZARD).get(motivo, motivo),
        'haberes': {
            'vacaciones_truncas': _d(ll_tmp.vacaciones_truncas),
            'gratif_trunca':      _d(ll_tmp.gratif_trunca),
            'cts_trunca':         _d(ll_tmp.cts_trunca),
            'sueldo_mes_curso':   _d(ll_tmp.sueldo_mes_curso),
            'he_no_compensadas':  _d(ll_tmp.he_no_compensadas),
            'indemnizacion':      _d(ll_tmp.indemnizacion),
            'otros_pagos':        _d(ll_tmp.otros_pagos),
        },
        'descuentos': {
            'prestamos_pendientes': _d(ll_tmp.prestamos_pendientes),
            'adelantos_pendientes': _d(ll_tmp.adelantos_pendientes),
            'embargo':              _d(ll_tmp.embargo),
            'otros_descuentos':     _d(ll_tmp.otros_descuentos),
        },
        'totales': {
            'total_bruto': _d(ll_tmp.total_bruto),
            'total_neto':  _d(ll_tmp.total_neto),
        },
    }
    return JsonResponse(data)


# ──────────────────────────────────────────────────────────────────────
# PASO 3 — Confirmar (persiste cese)
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def cesar_wizard_confirmar(request, personal_id):
    """POST — persiste el cese en Personal. El signal post_save crea
    automáticamente la LiquidacionLaboral y la calcula.

    Luego sobreescribe el motivo de la LL al motivo del wizard (más preciso
    que el mapeo automático del signal).
    """
    personal = get_object_or_404(Personal, pk=personal_id)

    if personal.estado == 'Cesado':
        messages.warning(request, f'{personal.apellidos_nombres} ya está cesado.')
        return redirect('personal_detail', pk=personal_id)

    fecha_cese, motivo, obs, err = _validar_form(request)
    if err:
        messages.error(request, err)
        return redirect('personal_cesar_paso1', personal_id=personal_id)

    # ── 1. Persistir cese en Personal (dispara signal) ──────────────────
    personal.estado      = 'Cesado'
    personal.fecha_cese  = fecha_cese
    personal.motivo_cese = _MAP_LIQ_A_PERSONAL.get(motivo, 'RENUNCIA')
    if obs:
        existing = personal.observaciones or ''
        sep = '\n' if existing else ''
        personal.observaciones = f'{existing}{sep}[CESE {fecha_cese}] {obs}'
        personal.save(update_fields=['estado', 'fecha_cese', 'motivo_cese', 'observaciones'])
    else:
        personal.save(update_fields=['estado', 'fecha_cese', 'motivo_cese'])

    # ── 2. Recuperar la LL creada por el signal y ajustar motivo+obs ────
    from nominas.models import LiquidacionLaboral
    liq = LiquidacionLaboral.objects.filter(personal=personal).first()
    if liq is None:
        # Fallback: si el signal falló, crear y calcular manualmente.
        liq = LiquidacionLaboral.objects.create(
            personal=personal,
            fecha_cese=fecha_cese,
            motivo_cese=motivo,
            observaciones=obs,
        )
        liq.calcular()
    else:
        # El signal pone un motivo derivado; nosotros sabemos el exacto.
        dirty = False
        if liq.motivo_cese != motivo:
            liq.motivo_cese = motivo
            dirty = True
        if obs and obs not in (liq.observaciones or ''):
            liq.observaciones = (liq.observaciones + '\n' if liq.observaciones else '') + obs
            dirty = True
        if dirty:
            # Recalcular con el motivo correcto (importante p/ DESPIDO_ARB → indemnización)
            liq.calcular()

    messages.success(
        request,
        f'Cese de {personal.apellidos_nombres} registrado. '
        f'Liquidación neta calculada: S/ {liq.total_neto:.2f}.'
    )
    return redirect('nominas_liquidacion_laboral_detalle', liquidacion_id=liq.pk)
