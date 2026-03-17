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

import io
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from personal.models import Personal
from .models import PeriodoNomina, RegistroNomina, ConceptoRemunerativo

# ── constantes ────────────────────────────────────────────────────────────────
RMV        = Decimal('1130.00')
ASIG_FAM   = (RMV * Decimal('0.10')).quantize(Decimal('0.01'), ROUND_HALF_UP)
ESSALUD    = Decimal('0.09')
AFP_APORTE = Decimal('0.10')
ONP_TASA   = Decimal('0.13')


def _rd(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal('0.01'), ROUND_HALF_UP)


# ── helpers de cálculo ────────────────────────────────────────────────────────

def _meses_semestre_gratif(fecha_cese: date) -> int:
    """
    Meses cumplidos en el semestre de gratificación vigente a la fecha de cese.
    Semestre 1: enero–junio (pago julio).
    Semestre 2: julio–diciembre (pago diciembre).
    Mínimo 0, máximo 6.
    """
    m = fecha_cese.month
    inicio_sem = 1 if m <= 6 else 7
    return max(0, m - inicio_sem + 1)


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


def _calcular_liquidacion(personal: Personal) -> dict:
    """
    Retorna dict con todos los conceptos de la liquidación.
    Usa fecha_cese del empleado; si no tiene, usa hoy.
    """
    fecha_cese = personal.fecha_cese or timezone.localdate()
    sueldo     = _rd(personal.sueldo_base or 0)
    tiene_af   = getattr(personal, 'asignacion_familiar', False)
    asig_fam   = ASIG_FAM if tiene_af else Decimal('0')

    # ── 1. Remuneración trunca ────────────────────────────────────────────────
    # días trabajados en el mes de cese: del 1 al día del cese
    dias_mes   = fecha_cese.day
    rem_trunca = _rd(sueldo / 30 * dias_mes)

    # ── 2. Gratificación trunca (Ley 27735) ───────────────────────────────────
    meses_gratif  = _meses_semestre_gratif(fecha_cese)
    rem_base_grat = sueldo + asig_fam
    gratif_trunca = _rd(rem_base_grat / 6 * meses_gratif)

    # Bonificación extraordinaria 9% sobre gratificación (Ley 29351) — empleador
    bonus_ext     = _rd(gratif_trunca * Decimal('0.09'))

    # ── 3. CTS trunca (DL 650) ───────────────────────────────────────────────
    meses_cts  = _meses_semestre_cts(fecha_cese)
    prov_grat  = _rd(sueldo / 6)                    # 1/6 sueldo = provisión gratif
    base_cts   = sueldo + asig_fam + prov_grat
    cts_trunca = _rd(base_cts / 12 * meses_cts)

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
    # AFP/ONP aplican sobre rem_trunca y gratif_trunca; NO sobre CTS ni vacaciones (inafectos)
    base_desctos = rem_trunca + gratif_trunca
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
