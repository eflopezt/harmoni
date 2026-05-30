"""
Liquidación al Cese — Nóminas Harmoni.

Calcula y genera la liquidación final del trabajador:
  1. Remuneración trunca (días del mes de cese)
  2. Vacaciones truncas (pendientes + proporcionales al año)
  3. Gratificación trunca (Ley 27735)
  4. CTS trunca (DL 650)

Flujo:
  /nominas/liquidaciones/           → panel + lista cesados
  /nominas/liquidaciones/<pk>/      → detalle / preview
  /nominas/liquidaciones/<pk>/generar/ → POST: crea PeriodoNomina(tipo='LIQUIDACION')
  /nominas/liquidaciones/<pk>/pdf/  → PDF boleta de liquidación
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from personal.models import Personal
from .models import PeriodoNomina, RegistroNomina

# ── constantes (fallbacks — se sobreescriben con snapshot del período) ───────
RMV        = Decimal('1130.00')
ASIG_FAM   = (RMV * Decimal('0.10')).quantize(Decimal('0.01'), ROUND_HALF_UP)
ESSALUD    = Decimal('0.09')
AFP_APORTE = Decimal('0.10')
ONP_TASA   = Decimal('0.13')


def _rd(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal('0.01'), ROUND_HALF_UP)


def _rmv_actual() -> Decimal:
    """Lee RMV live de ConfiguracionSistema con fallback a RMV constante."""
    try:
        from asistencia.models import ConfiguracionSistema
        return Decimal(ConfiguracionSistema.get().rmv_valor)
    except Exception:
        return RMV


# ── helpers de cálculo ────────────────────────────────────────────────────────

def _meses_semestre_gratif(fecha_cese: date) -> int:
    """
    Meses COMPLETOS en el semestre de gratificación vigente a la fecha de cese.
    Ley 27735: solo se computan meses íntegros trabajados.
    Semestre 1: enero–junio (pago julio).
    Semestre 2: julio–diciembre (pago diciembre).
    Mínimo 0, máximo 6.
    """
    import calendar
    m = fecha_cese.month
    inicio_sem = 1 if m <= 6 else 7
    # Meses completos previos al mes de cese
    meses_completos = max(0, m - inicio_sem)
    # El mes de cese cuenta solo si trabajó hasta el último día
    ultimo_dia_mes = calendar.monthrange(fecha_cese.year, fecha_cese.month)[1]
    if fecha_cese.day >= ultimo_dia_mes:
        meses_completos += 1
    return min(meses_completos, 6)


def _meses_semestre_cts(fecha_cese: date) -> int:
    """
    Meses cumplidos en el semestre de CTS vigente a la fecha de cese.
    Período 1: noviembre–abril  (depósito mayo).
    Período 2: mayo–octubre     (depósito noviembre).
    Retorna solo meses COMPLETOS (días truncos proporcionales se ignoran por simplicidad).
    """
    m = fecha_cese.month
    if m <= 4:   # nov ant → abril: contamos desde noviembre del año anterior
        return m + 2        # nov=1, dic=2, ene=3, feb=4, mar=5, abr=6
    elif m <= 10:  # may–oct
        return m - 4        # may=1, jun=2, jul=3, ago=4, sep=5, oct=6
    else:          # nov–dic: primer mes del nuevo período
        return m - 10       # nov=1, dic=2


def _calcular_liquidacion(personal: Personal, rmv: Decimal = None) -> dict:
    """
    Retorna dict con todos los conceptos de la liquidación.
    Usa fecha_cese del empleado; si no tiene, usa hoy.

    Args:
        personal: empleado cesado
        rmv:      RMV a usar (si None, lee de ConfiguracionSistema). Permite
                  pasar un snapshot congelado si la liquidación ya tiene período.
    """
    fecha_cese = personal.fecha_cese or timezone.localdate()
    sueldo     = _rd(personal.sueldo_base or 0)
    tiene_af   = getattr(personal, 'asignacion_familiar', False)

    if rmv is None:
        rmv = _rmv_actual()
    asig_fam_calc = _rd(rmv * Decimal('0.10'))
    asig_fam      = asig_fam_calc if tiene_af else Decimal('0')

    # ── 1. Remuneración trunca ────────────────────────────────────────────────
    # días trabajados en el mes de cese: del 1 al día del cese
    dias_mes   = fecha_cese.day
    rem_trunca = _rd(sueldo / 30 * dias_mes)

    # ── 2. Gratificación trunca (Ley 27735) ───────────────────────────────────
    # Usar helper centralizado para evitar duplicación.
    from .engine import calcular_prov_gratif
    meses_gratif  = _meses_semestre_gratif(fecha_cese)
    rem_base_grat = sueldo + asig_fam
    gratif_trunca = _rd(rem_base_grat / 6 * meses_gratif)

    # Bonificación extraordinaria 9% sobre gratificación (Ley 29351) — empleador
    bonus_ext     = _rd(gratif_trunca * Decimal('0.09'))

    # ── 3. CTS trunca (DL 650) ───────────────────────────────────────────────
    # Trabajamos con Decimal exacto y redondeamos SOLO al final para evitar
    # pérdida por redondeo en cascada (prov_gratif * 12 * meses).
    meses_cts          = _meses_semestre_cts(fecha_cese)
    prov_gratif_exacto = (sueldo + asig_fam) / Decimal('6')   # NO redondear aún
    base_cts_exacta    = sueldo + asig_fam + prov_gratif_exacto
    cts_trunca         = _rd(base_cts_exacta / Decimal('12') * Decimal(meses_cts))
    # Versiones redondeadas para informar al usuario
    prov_grat          = calcular_prov_gratif(sueldo, asig_fam)
    base_cts           = _rd(base_cts_exacta)

    # ── 4. Vacaciones truncas (DL 713) ───────────────────────────────────────
    dias_pendientes = Decimal('0')
    dias_truncos    = Decimal('0')
    try:
        from vacaciones.models import SaldoVacacional
        sv = SaldoVacacional.objects.filter(personal=personal).order_by('-periodo_inicio').first()
        if sv:
            dias_pendientes = Decimal(str(sv.dias_pendientes or 0))
            dias_truncos    = Decimal(str(sv.dias_truncos or 0))
    except Exception:
        pass

    vac_pendientes = _rd(sueldo / 30 * dias_pendientes)
    vac_truncas    = _rd(sueldo / 30 * dias_truncos)

    # ── 5. Descuentos sobre liquidación ──────────────────────────────────────
    # AFP/ONP aplican SOLO sobre la remuneración afecta (rem_trunca). La
    # gratificación trunca, la CTS y las vacaciones son INAFECTAS a aportes
    # pensionarios (Ley 29351 / Ley 30334).
    base_desctos = rem_trunca
    regimen      = getattr(personal, 'regimen_pension', 'AFP')

    descto_pension = Decimal('0')
    if regimen == 'ONP':
        descto_pension = _rd(base_desctos * ONP_TASA)
    elif regimen == 'AFP':
        from .engine import AFP_TASAS
        afp_nombre = getattr(personal, 'afp', 'Prima') or 'Prima'
        tasas = AFP_TASAS.get(afp_nombre, AFP_TASAS['Prima'])
        afp_aporte   = _rd(base_desctos * AFP_APORTE)
        afp_comision = _rd(base_desctos * tasas['comision_flujo'] / Decimal('100'))
        afp_seguro   = _rd(base_desctos * tasas['seguro'] / Decimal('100'))
        descto_pension = afp_aporte + afp_comision + afp_seguro

    # EsSalud (empleador) sobre rem_trunca + gratif_trunca
    essalud_empleador = _rd((rem_trunca + gratif_trunca) * ESSALUD)

    # ── 6. Totales ────────────────────────────────────────────────────────────
    total_haberes = rem_trunca + gratif_trunca + cts_trunca + vac_pendientes + vac_truncas + bonus_ext
    total_desctos = descto_pension
    neto_pagar    = total_haberes - total_desctos

    return {
        'fecha_cese':        fecha_cese,
        'sueldo_base':       sueldo,
        'asig_fam':          asig_fam,
        # Haberes
        'rem_trunca':        rem_trunca,
        'dias_mes':          dias_mes,
        'gratif_trunca':     gratif_trunca,
        'meses_gratif':      meses_gratif,
        'bonus_ext':         bonus_ext,
        'cts_trunca':        cts_trunca,
        'meses_cts':         meses_cts,
        'base_cts':          base_cts,
        'vac_pendientes':    vac_pendientes,
        'dias_pendientes':   int(dias_pendientes),
        'vac_truncas':       vac_truncas,
        'dias_truncos':      float(dias_truncos),
        # Descuentos
        'regimen_pension':   regimen,
        'descto_pension':    descto_pension,
        # Totales
        'essalud_empleador': essalud_empleador,
        'total_haberes':     total_haberes,
        'total_desctos':     total_desctos,
        'neto_pagar':        neto_pagar,
    }


# ── views ─────────────────────────────────────────────────────────────────────

@login_required
def liquidaciones_panel(request):
    """Panel: cesados pendientes de liquidar + liquidaciones recientes."""
    # Empleados cesados
    cesados = Personal.objects.filter(
        estado='Cesado',
        fecha_cese__isnull=False,
    ).order_by('-fecha_cese').select_related('subarea__area')

    # IDs ya liquidados (tienen RegistroNomina en un periodo LIQUIDACION)
    liq_personal_ids = set(
        RegistroNomina.objects.filter(
            periodo__tipo='LIQUIDACION'
        ).values_list('personal_id', flat=True)
    )

    pendientes   = [c for c in cesados if c.pk not in liq_personal_ids]
    ya_liquidados = [c for c in cesados if c.pk in liq_personal_ids]

    # Períodos de liquidación recientes
    periodos_liq = PeriodoNomina.objects.filter(
        tipo='LIQUIDACION'
    ).order_by('-fecha_pago')[:20]

    return render(request, 'nominas/liquidaciones_panel.html', {
        'titulo':         'Liquidaciones al Cese',
        'pendientes':     pendientes,
        'ya_liquidados':  ya_liquidados,
        'periodos_liq':   periodos_liq,
    })


@login_required
def liquidacion_detalle(request, pk):
    """Vista detalle + preview de liquidación para un empleado cesado."""
    personal = get_object_or_404(Personal, pk=pk, estado='Cesado')
    liq      = _calcular_liquidacion(personal)

    # ¿Ya existe liquidación generada?
    registro_existente = RegistroNomina.objects.filter(
        personal=personal,
        periodo__tipo='LIQUIDACION',
    ).select_related('periodo').first()

    return render(request, 'nominas/liquidacion_detalle.html', {
        'titulo':    f'Liquidación — {personal.apellidos_nombres}',
        'personal':  personal,
        'liq':       liq,
        'registro':  registro_existente,
    })


@login_required
@require_POST
def liquidacion_generar(request, pk):
    """
    Crea PeriodoNomina(tipo='LIQUIDACION') + RegistroNomina con los montos calculados.
    Idempotente: si ya existe, muestra mensaje y redirige.
    """
    personal = get_object_or_404(Personal, pk=pk, estado='Cesado')

    # Verificar si ya existe
    if RegistroNomina.objects.filter(personal=personal, periodo__tipo='LIQUIDACION').exists():
        messages.warning(request, f'Ya existe una liquidación registrada para {personal.apellidos_nombres}.')
        return redirect('nominas_liquidacion_detalle', pk=pk)

    liq       = _calcular_liquidacion(personal)
    fecha_cese = liq['fecha_cese']

    with transaction.atomic():
        # Un período LIQUIDACION por mes — get_or_create (pueden haber varios cesados en el mismo mes)
        periodo, created = PeriodoNomina.objects.get_or_create(
            tipo=  'LIQUIDACION',
            anio=  fecha_cese.year,
            mes=   fecha_cese.month,
            defaults={
                'descripcion': f'Liquidaciones {fecha_cese:%m/%Y}',
                'fecha_inicio': date(fecha_cese.year, fecha_cese.month, 1),
                'fecha_fin':    fecha_cese,
                'fecha_pago':   fecha_cese,
                'estado':       'CALCULADO',
            },
        )

        # Crear registro de nómina para este empleado
        RegistroNomina.objects.create(
            periodo          = periodo,
            personal         = personal,
            sueldo_base      = liq['sueldo_base'],
            dias_trabajados  = liq['dias_mes'],
            regimen_pension  = liq['regimen_pension'],
            otros_ingresos   = (
                liq['gratif_trunca'] + liq['cts_trunca'] +
                liq['vac_pendientes'] + liq['vac_truncas'] +
                liq['bonus_ext']
            ),
            otros_descuentos = liq['descto_pension'],
            total_ingresos   = liq['total_haberes'],
            total_descuentos = liq['total_desctos'],
            neto_a_pagar     = liq['neto_pagar'],
            aporte_essalud   = liq['essalud_empleador'],
            costo_total_empresa = liq['total_haberes'] + liq['essalud_empleador'],
        )

        # Recalcular totales del período sumando todos los registros
        from django.db.models import Sum
        agg = RegistroNomina.objects.filter(periodo=periodo).aggregate(
            t_bruto  = Sum('total_ingresos'),
            t_desc   = Sum('total_descuentos'),
            t_neto   = Sum('neto_a_pagar'),
            t_costo  = Sum('costo_total_empresa'),
            t_count  = models.Count('pk'),
        )
        periodo.total_trabajadores  = agg['t_count'] or 0
        periodo.total_bruto         = agg['t_bruto']  or Decimal('0')
        periodo.total_descuentos    = agg['t_desc']   or Decimal('0')
        periodo.total_neto          = agg['t_neto']   or Decimal('0')
        periodo.total_costo_empresa = agg['t_costo']  or Decimal('0')
        periodo.save(update_fields=[
            'total_trabajadores', 'total_bruto', 'total_descuentos',
            'total_neto', 'total_costo_empresa',
        ])

    messages.success(
        request,
        f'Liquidación de {personal.apellidos_nombres} generada correctamente. '
        f'Neto a pagar: S/ {liq["neto_pagar"]:,.2f}'
    )
    return redirect('nominas_liquidacion_detalle', pk=pk)


@login_required
def liquidacion_pdf(request, pk):
    """
    Genera PDF de la boleta de liquidación al cese.
    Usa WeasyPrint si disponible; fallback: HTML con cabecera de descarga.
    """
    personal = get_object_or_404(Personal, pk=pk, estado='Cesado')
    liq      = _calcular_liquidacion(personal)

    # Empresa
    empresa = 'la empresa'
    ruc     = ''
    try:
        from asistencia.models import ConfiguracionSistema
        cfg     = ConfiguracionSistema.get()
        empresa = cfg.empresa_nombre or empresa
        ruc     = cfg.empresa_ruc or ''
    except Exception:
        pass

    ctx = {
        'personal': personal,
        'liq':      liq,
        'empresa':  empresa,
        'ruc':      ruc,
        'hoy':      timezone.localdate(),
    }

    try:
        from weasyprint import HTML as WP_HTML
        from django.template.loader import render_to_string
        html_str = render_to_string('nominas/liquidacion_pdf.html', ctx, request=request)
        pdf_file = WP_HTML(string=html_str, base_url=request.build_absolute_uri('/')).write_pdf()
        filename = f"liquidacion_{personal.pk}_{liq['fecha_cese']:%Y%m%d}.pdf"
        resp = HttpResponse(pdf_file, content_type='application/pdf')
        resp['Content-Disposition'] = f'inline; filename="{filename}"'
        return resp
    except ImportError:
        # Fallback: renderizar HTML para imprimir
        return render(request, 'nominas/liquidacion_pdf.html', ctx)


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 1 — LiquidacionLaboral (modelo header)
# ══════════════════════════════════════════════════════════════════════════════
# Estas vistas operan sobre el nuevo modelo LiquidacionLaboral (no sobre
# RegistroNomina como las vistas legacy de arriba). Implementan la API y
# las pantallas de detalle/aprobación que pide el Sprint 1.
# ══════════════════════════════════════════════════════════════════════════════

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse


@staff_member_required
def api_liquidacion(request, personal_id):
    """
    GET /nominas/api/liquidacion/<personal_id>/

    Retorna la liquidación calculada del trabajador en JSON. Si el
    trabajador no está cesado, retorna {error: 'no_cesado'} con 400.
    Solo accesible para staff (admin).
    """
    from .models import LiquidacionLaboral

    personal = get_object_or_404(Personal, pk=personal_id)
    if personal.estado != 'Cesado':
        return JsonResponse({'error': 'no_cesado'}, status=400)

    # Buscar liquidación existente; si no existe, intentar crearla/calcularla.
    liq = LiquidacionLaboral.objects.filter(personal=personal).first()
    if liq is None:
        liq, _ = LiquidacionLaboral.objects.get_or_create(
            personal=personal,
            defaults={
                'fecha_cese':  personal.fecha_cese or timezone.localdate(),
                'motivo_cese': 'RENUNCIA',
            },
        )
        liq.calcular()

    return JsonResponse({
        'id':                 liq.pk,
        'personal_id':        personal.pk,
        'personal_nombre':    personal.apellidos_nombres,
        'fecha_cese':         liq.fecha_cese.isoformat(),
        'motivo_cese':        liq.motivo_cese,
        'estado':             liq.estado,
        # Haberes
        'vacaciones_truncas': str(liq.vacaciones_truncas),
        'gratif_trunca':      str(liq.gratif_trunca),
        'cts_trunca':         str(liq.cts_trunca),
        'sueldo_mes_curso':   str(liq.sueldo_mes_curso),
        'he_no_compensadas':  str(liq.he_no_compensadas),
        'indemnizacion':      str(liq.indemnizacion),
        'otros_pagos':        str(liq.otros_pagos),
        # Descuentos
        'descuento_pension':    str(liq.descuento_pension),
        'prestamos_pendientes': str(liq.prestamos_pendientes),
        'adelantos_pendientes': str(liq.adelantos_pendientes),
        'embargo':              str(liq.embargo),
        'otros_descuentos':     str(liq.otros_descuentos),
        # Totales
        'total_bruto': str(liq.total_bruto),
        'total_neto':  str(liq.total_neto),
    })


@login_required
def liquidacion_laboral_detalle(request, liquidacion_id):
    """
    GET /nominas/liquidacion/<liquidacion_id>/

    Muestra la liquidación con tabla de conceptos, tabla de descuentos,
    total, botón "Aprobar" (cambia estado a APROBADA) y botón "Imprimir PDF".
    """
    from .models import LiquidacionLaboral

    liq = get_object_or_404(
        LiquidacionLaboral.objects.select_related('personal', 'aprobada_por'),
        pk=liquidacion_id,
    )

    conceptos = [
        ('Sueldo del mes en curso',     liq.sueldo_mes_curso),
        ('Gratificación trunca',        liq.gratif_trunca),
        ('CTS trunca',                  liq.cts_trunca),
        ('Vacaciones truncas',          liq.vacaciones_truncas),
        ('Horas extra no compensadas',  liq.he_no_compensadas),
        ('Indemnización (despido arb.)', liq.indemnizacion),
        ('Otros pagos',                 liq.otros_pagos),
    ]
    descuentos = [
        ('Aporte pensionario (AFP/ONP)', liq.descuento_pension),
        ('Préstamos pendientes',  liq.prestamos_pendientes),
        ('Adelantos pendientes',  liq.adelantos_pendientes),
        ('Embargo judicial',      liq.embargo),
        ('Otros descuentos',      liq.otros_descuentos),
    ]
    total_descuentos = sum(v for _, v in descuentos)

    # Sprint 3 — Determinar si la etapa 1 del workflow offboarding
    # (Encuesta de salida) está activa para esta liquidación. En ese caso
    # mostramos el botón "Enviar encuesta exit" en el template.
    encuesta_exit_etapa_activa = False
    encuesta_exit_url = ''
    try:
        if liq.instancia_flujo and liq.instancia_flujo.estado == 'EN_PROCESO':
            etapa = liq.instancia_flujo.etapa_actual
            if etapa and etapa.orden == 1 and 'salida' in etapa.nombre.lower():
                encuesta_exit_etapa_activa = True
                # Resolver Encuesta SALIDA — sin crashear si no fue sembrada.
                try:
                    from encuestas.models import Encuesta
                    enc = (
                        Encuesta.objects.filter(tipo='SALIDA', estado='ACTIVA')
                        .order_by('-fecha_inicio').first()
                    )
                    if enc:
                        encuesta_exit_url = f'/encuestas/responder/{enc.pk}/'
                except Exception:
                    pass
    except Exception:
        pass

    return render(request, 'nominas/liquidacion_laboral_detalle.html', {
        'titulo':           f'Liquidación — {liq.personal.apellidos_nombres}',
        'liq':              liq,
        'personal':         liq.personal,
        'conceptos':        conceptos,
        'descuentos':       descuentos,
        'total_descuentos': total_descuentos,
        # Sprint 3 — botones nuevos
        'encuesta_exit_etapa_activa': encuesta_exit_etapa_activa,
        'encuesta_exit_url':          encuesta_exit_url,
    })


@login_required
@require_POST
def liquidacion_laboral_aprobar(request, liquidacion_id):
    """POST /nominas/liquidacion/<id>/aprobar/ → estado APROBADA + aprobada_por."""
    from .models import LiquidacionLaboral

    liq = get_object_or_404(LiquidacionLaboral, pk=liquidacion_id)
    if liq.estado in ('APROBADA', 'FIRMADA', 'PAGADA', 'CERRADA'):
        messages.info(request, 'La liquidación ya fue aprobada.')
    else:
        liq.estado       = 'APROBADA'
        liq.aprobada_por = request.user
        liq.save(update_fields=['estado', 'aprobada_por', 'actualizado_en'])
        messages.success(
            request,
            f'Liquidación de {liq.personal.apellidos_nombres} aprobada por {request.user}.',
        )
    return redirect('nominas_liquidacion_laboral_detalle', liquidacion_id=liq.pk)


@login_required
def liquidacion_laboral_pdf(request, liquidacion_id):
    """Reutiliza el generador PDF de boleta de liquidación legacy."""
    from .models import LiquidacionLaboral

    liq = get_object_or_404(LiquidacionLaboral.objects.select_related('personal'),
                            pk=liquidacion_id)
    # Delegamos a la vista legacy con el personal.
    return liquidacion_pdf(request, pk=liq.personal_id)


# ══════════════════════════════════════════════════════════════════════════════
# Sprint 3 — Documentos al cese (Carta de no adeudo + Certificado de trabajo)
# ══════════════════════════════════════════════════════════════════════════════

@staff_member_required
def carta_no_adeudo_pdf(request, liquidacion_id):
    """
    GET /nominas/liquidacion/<liquidacion_id>/carta-no-adeudo/

    Descarga el PDF "Carta de no adeudo y liberación mutua" para la
    liquidación. Solo accesible a staff (RRHH).
    """
    from .models import LiquidacionLaboral
    from .cartas import generar_carta_no_adeudo

    liq = get_object_or_404(
        LiquidacionLaboral.objects.select_related('personal'),
        pk=liquidacion_id,
    )
    pdf_bytes = generar_carta_no_adeudo(liq)
    filename = (
        f"carta_no_adeudo_{liq.personal.nro_doc}_"
        f"{liq.fecha_cese:%Y%m%d}.pdf"
    )
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{filename}"'
    return resp


@staff_member_required
def certificado_trabajo_pdf(request, personal_id):
    """
    GET /personal/<personal_id>/certificado-trabajo/

    Descarga el PDF "Certificado de Trabajo" del trabajador cesado.
    Devuelve 400 si el trabajador no está cesado.
    """
    from .cartas import generar_certificado_trabajo

    personal = get_object_or_404(Personal, pk=personal_id)
    try:
        pdf_bytes = generar_certificado_trabajo(personal)
    except ValueError as exc:
        return HttpResponse(
            f'Error: {exc}',
            status=400,
            content_type='text/plain; charset=utf-8',
        )
    filename = (
        f"certificado_trabajo_{personal.nro_doc}_"
        f"{personal.fecha_cese:%Y%m%d}.pdf"
    )
    resp = HttpResponse(pdf_bytes, content_type='application/pdf')
    resp['Content-Disposition'] = f'inline; filename="{filename}"'
    return resp
