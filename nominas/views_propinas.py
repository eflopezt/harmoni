"""
Views — Pool de Propinas.

Rutas:
  /nominas/propinas/                     → lista de pools + botón nuevo
  /nominas/propinas/nuevo/               → cargar pool + preview
  /nominas/propinas/<pk>/distribuir/     → POST: ejecuta distribución
  /nominas/propinas/<pk>/                → detalle (resultado de distribución)
  /nominas/propinas/config/              → configurar reglas del pool

Diseño: §2 de docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from personal.models import Cargo, Personal

from .models_propinas import (
    ConfiguracionPropinas,
    DistribucionPropinas,
    HorasTrabajadasPropinas,
    PoolPropinas,
    PuntosPropinas,
)


# ── helpers ──────────────────────────────────────────────────────────────
def _empresa(request):
    """Resuelve la empresa activa del request (middleware)."""
    return getattr(request, 'empresa_actual', None)


def _parse_decimal(raw: str, default: Decimal = Decimal('0')) -> Decimal:
    if raw is None or raw == '':
        return default
    try:
        return Decimal(str(raw).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return default


def _parse_date(raw: str):
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


# ══════════════════════════════════════════════════════════════════════════
# Configuración
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_config(request):
    """Configurar pool por empresa (GET form + POST guardar)."""
    empresa = _empresa(request)
    if not empresa:
        messages.error(request, 'Selecciona una empresa activa antes de configurar propinas.')
        return redirect('nominas_panel')

    cfg, _ = ConfiguracionPropinas.objects.get_or_create(empresa=empresa)

    if request.method == 'POST':
        cfg.modo = request.POST.get('modo', cfg.modo)
        cfg.incluye_cocina = request.POST.get('incluye_cocina') == 'on'
        cfg.incluye_admin = request.POST.get('incluye_admin') == 'on'
        cfg.porcentaje_casa = _parse_decimal(
            request.POST.get('porcentaje_casa'), Decimal('0'),
        )
        cfg.porcentaje_tipout_boh = _parse_decimal(
            request.POST.get('porcentaje_tipout_boh'), Decimal('0'),
        )
        cfg.save()

        # Guardar puntos por cargo (input: puntos_<cargo_id>=valor)
        for key, val in request.POST.items():
            if not key.startswith('puntos_'):
                continue
            try:
                cargo_id = int(key.split('_', 1)[1])
            except (ValueError, IndexError):
                continue
            puntos = _parse_decimal(val, Decimal('0'))
            if puntos > 0:
                PuntosPropinas.objects.update_or_create(
                    configuracion=cfg, cargo_id=cargo_id,
                    defaults={'puntos': puntos},
                )
            else:
                PuntosPropinas.objects.filter(
                    configuracion=cfg, cargo_id=cargo_id,
                ).delete()

        messages.success(request, 'Configuración de propinas guardada.')
        return redirect('propinas_config')

    cargos = Cargo.objects.filter(activo=True).order_by('nivel', 'nombre')
    puntos_map = {
        p.cargo_id: p.puntos for p in cfg.puntos_por_cargo.all()
    }
    cargos_con_puntos = [
        {'cargo': c, 'puntos': puntos_map.get(c.pk, Decimal('0'))}
        for c in cargos
    ]

    return render(request, 'nominas/propinas_config.html', {
        'titulo': 'Configuración de Propinas',
        'cfg': cfg,
        'cargos_con_puntos': cargos_con_puntos,
    })


# ══════════════════════════════════════════════════════════════════════════
# Lista de pools
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_lista(request):
    """Lista de pools registrados + acciones."""
    empresa = _empresa(request)
    if not empresa:
        messages.error(request, 'Selecciona una empresa activa.')
        return redirect('nominas_panel')

    pools = (
        PoolPropinas.objects
        .filter(empresa=empresa)
        .order_by('-fecha_fin', '-pk')
    )
    cfg = ConfiguracionPropinas.objects.filter(empresa=empresa).first()

    return render(request, 'nominas/propinas_lista.html', {
        'titulo': 'Pools de Propinas',
        'pools': pools,
        'cfg': cfg,
    })


# ══════════════════════════════════════════════════════════════════════════
# Detalle de pool
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_detalle(request, pool_id: int):
    """Detalle de un pool específico (resultado de distribución)."""
    empresa = _empresa(request)
    pool = get_object_or_404(PoolPropinas, pk=pool_id, empresa=empresa)
    distribuciones = (
        pool.distribuciones
        .select_related('personal')
        .order_by('-monto')
    )
    return render(request, 'nominas/propinas_lista.html', {
        'titulo': f'Pool — {pool.fecha_inicio:%d/%m/%Y} a {pool.fecha_fin:%d/%m/%Y}',
        'pools': [pool],
        'detalle': pool,
        'distribuciones': distribuciones,
        'cfg': ConfiguracionPropinas.objects.filter(empresa=empresa).first(),
    })


# ══════════════════════════════════════════════════════════════════════════
# Nuevo pool + preview
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_nuevo(request):
    """
    Cargar nuevo pool de propinas.
      GET   → formulario vacío (con fechas default = semana actual)
      POST  → crea PoolPropinas + redirige a vista de pool para distribuir.
    """
    empresa = _empresa(request)
    if not empresa:
        messages.error(request, 'Selecciona una empresa activa.')
        return redirect('nominas_panel')

    cfg = ConfiguracionPropinas.objects.filter(empresa=empresa).first()
    if not cfg:
        messages.warning(
            request,
            'Configura primero las reglas del pool antes de cargar montos.',
        )
        return redirect('propinas_config')

    # Defaults
    hoy = date.today()
    inicio_default = hoy - timedelta(days=hoy.weekday())  # lunes
    fin_default = inicio_default + timedelta(days=6)      # domingo

    if request.method == 'POST':
        fecha_inicio = _parse_date(request.POST.get('fecha_inicio')) or inicio_default
        fecha_fin = _parse_date(request.POST.get('fecha_fin')) or fin_default
        # Nuevo: cash + card separados (best practice mundial).
        # Legacy: monto_bruto si el formulario aún lo manda.
        monto_cash = _parse_decimal(request.POST.get('monto_cash'), Decimal('0'))
        monto_card = _parse_decimal(request.POST.get('monto_card'), Decimal('0'))
        monto_bruto_legacy = _parse_decimal(
            request.POST.get('monto_bruto'), Decimal('0'),
        )
        notas = request.POST.get('notas', '').strip()

        total = monto_cash + monto_card
        if total <= 0:
            # Fallback al campo legacy
            if monto_bruto_legacy <= 0:
                messages.error(
                    request,
                    'El monto total (cash + card) debe ser mayor a 0.',
                )
                return redirect('propinas_nuevo')

        if fecha_fin < fecha_inicio:
            messages.error(request, 'La fecha fin no puede ser anterior a la fecha inicio.')
            return redirect('propinas_nuevo')

        pool_kwargs = dict(
            empresa=empresa,
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            notas=notas,
        )
        if total > 0:
            pool_kwargs['monto_cash'] = monto_cash
            pool_kwargs['monto_card'] = monto_card
        else:
            pool_kwargs['monto_bruto'] = monto_bruto_legacy

        pool = PoolPropinas.objects.create(**pool_kwargs)
        pool.refresh_from_db()
        messages.success(
            request,
            f'Pool de S/ {pool.monto_bruto} creado '
            f'(cash S/ {pool.monto_cash} + card S/ {pool.monto_card}). '
            f'Revisa el preview y distribuye.',
        )
        return redirect('propinas_detalle', pool_id=pool.pk)

    # Preview de participantes para ayudar al usuario
    n_activos = Personal.objects.filter(
        empresa=empresa, estado='Activo',
    ).count()

    return render(request, 'nominas/propinas_form.html', {
        'titulo': 'Nuevo Pool de Propinas',
        'cfg': cfg,
        'fecha_inicio_default': inicio_default.isoformat(),
        'fecha_fin_default': fin_default.isoformat(),
        'n_activos': n_activos,
    })


# ══════════════════════════════════════════════════════════════════════════
# Ejecutar distribución
# ══════════════════════════════════════════════════════════════════════════
@login_required
@require_POST
def propinas_distribuir(request, pool_id: int):
    """Ejecuta `pool.distribuir()`. Idempotente."""
    empresa = _empresa(request)
    pool = get_object_or_404(PoolPropinas, pk=pool_id, empresa=empresa)

    if pool.distribuido:
        messages.info(request, 'Este pool ya fue distribuido.')
        return redirect('propinas_detalle', pool_id=pool.pk)

    distribuciones = pool.distribuir()
    if distribuciones:
        n_anomalias = sum(1 for d in distribuciones if d.anomalia)
        msg = (
            f'Pool distribuido entre {len(distribuciones)} trabajadores. '
            f'Total: S/ {pool.monto_distribuible}.'
        )
        if n_anomalias:
            msg += (
                f' Atención: {n_anomalias} distribución(es) marcada(s) como '
                'anomalía (< 50% del promedio del cargo) — revisar antes de pagar.'
            )
            messages.warning(request, msg)
        else:
            messages.success(request, msg)
    else:
        messages.warning(
            request,
            'Pool marcado como distribuido pero no se generaron entradas '
            '(sin participantes elegibles o modo INDIVIDUAL).',
        )
    return redirect('propinas_detalle', pool_id=pool.pk)


# ══════════════════════════════════════════════════════════════════════════
# Acta de Distribución — PDF firmable
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_acta_pdf(request, pool_id: int):
    """Genera el Acta de Distribución de Propinas en PDF firmable.

    Best practice mundial (Toast Tips Manager, TipHaus, tronc UK): el manager
    imprime el acta del período y los trabajadores firman recibiendo su parte.
    Sirve como defensa ante SUNAFIL/disputas.
    """
    empresa = _empresa(request)
    pool = get_object_or_404(PoolPropinas, pk=pool_id, empresa=empresa)

    from .pdf_propinas import generar_acta_distribucion_pdf
    pdf_bytes = generar_acta_distribucion_pdf(pool)

    fname = (
        f'acta_propinas_{pool.fecha_inicio:%Y%m%d}_'
        f'{pool.fecha_fin:%Y%m%d}.pdf'
    )
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{fname}"'
    return resp


# ══════════════════════════════════════════════════════════════════════════
# Horas trabajadas (carga rápida para modos *_HORAS)
# ══════════════════════════════════════════════════════════════════════════
@login_required
def propinas_horas(request, pool_id: int):
    """Carga horas trabajadas por trabajador para un pool específico.

    Solo aplica en modos POOL_HORAS y POOL_PUNTOS_HORAS. Para otros modos
    redirige al detalle con mensaje.

      GET   → formulario con todos los participantes activos del pool.
      POST  → guarda HorasTrabajadasPropinas por persona.
    """
    empresa = _empresa(request)
    pool = get_object_or_404(PoolPropinas, pk=pool_id, empresa=empresa)
    cfg = ConfiguracionPropinas.objects.filter(empresa=empresa).first()

    if not cfg or not cfg.usa_horas:
        messages.info(
            request,
            'Las horas trabajadas solo aplican en modos POOL_HORAS o '
            'POOL_PUNTOS_HORAS. Cambia el modo desde la configuración.',
        )
        return redirect('propinas_detalle', pool_id=pool.pk)

    if pool.distribuido:
        messages.info(
            request,
            'Este pool ya fue distribuido — las horas registradas son solo '
            'de referencia.',
        )

    # Participantes activos en el rango del pool
    from django.db.models import Q
    activos = Personal.objects.filter(
        empresa=empresa,
        estado='Activo',
        fecha_alta__lte=pool.fecha_fin,
    ).filter(
        Q(fecha_cese__isnull=True) | Q(fecha_cese__gte=pool.fecha_inicio)
    ).order_by('cargo', 'apellidos_nombres')

    if request.method == 'POST':
        for persona in activos:
            raw = request.POST.get(f'horas_{persona.pk}')
            if raw is None:
                continue
            horas = _parse_decimal(raw, Decimal('0'))
            if horas > 0:
                HorasTrabajadasPropinas.objects.update_or_create(
                    pool=pool, personal=persona,
                    defaults={'horas': horas},
                )
            else:
                HorasTrabajadasPropinas.objects.filter(
                    pool=pool, personal=persona,
                ).delete()
        messages.success(request, 'Horas trabajadas guardadas.')
        return redirect('propinas_horas', pool_id=pool.pk)

    horas_map = {
        h.personal_id: h.horas
        for h in pool.horas.all()
    }
    rows = [
        {'persona': p, 'horas': horas_map.get(p.pk, Decimal('0'))}
        for p in activos
    ]

    return render(request, 'nominas/propinas_horas.html', {
        'titulo': f'Horas trabajadas — Pool {pool.fecha_inicio:%d/%m/%Y}–{pool.fecha_fin:%d/%m/%Y}',
        'pool': pool,
        'cfg': cfg,
        'rows': rows,
    })
