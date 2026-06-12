"""
Validador de Onboarding — Checklist "¿está la empresa lista para procesar planilla?"

Expone también un endpoint API JSON: GET /api/v1/nominas/onboarding/
para integraciones, monitoreo y CI checks.

Comprueba en una sola página todos los pre-requisitos para que un cliente
empiece a usar Harmoni con confianza:

1. Datos de Empresa (RUC, razón social, representante legal, logo)
2. Conceptos remunerativos (mínimos activos, PLAME, inconsistencias)
3. Personal (trabajadores cargados, CUSPP, fecha alta, AFP/ONP)
4. Tasas AFP vigentes
5. Configuración de planilla (saldos apertura, primer período)

Cada check tiene:
- severidad: 'ok' | 'warn' | 'error' | 'info'
- titulo, descripcion
- link_fix (URL donde solucionar)
- categoria
- peso (0-100 — qué tan crítico)

URL: /nominas/onboarding/validador/
"""
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render
from django.urls import reverse

from .models import ConceptoRemunerativo, PeriodoNomina


solo_admin = user_passes_test(lambda u: u.is_superuser)


# ─── Categorías ───────────────────────────────────────────────────
CAT_EMPRESA      = ('empresa',      'Empresa',              'fas fa-building')
CAT_CONCEPTOS    = ('conceptos',    'Conceptos & PLAME',    'fas fa-cogs')
CAT_PERSONAL     = ('personal',     'Personal',             'fas fa-users')
CAT_PLANILLA     = ('planilla',     'Planilla',             'fas fa-file-invoice-dollar')
CAT_TASAS        = ('tasas',        'Tasas legales',        'fas fa-percent')


# ─── Helper para construir cada check ─────────────────────────────
def _check(categoria, titulo, descripcion, severidad, link=None, peso=10):
    return {
        'categoria':   categoria[0],
        'cat_label':   categoria[1],
        'cat_icon':    categoria[2],
        'titulo':      titulo,
        'descripcion': descripcion,
        'severidad':   severidad,
        'link':        link,
        'peso':        peso,
    }


# ─── Empresa ─────────────────────────────────────────────────────
def _check_empresa(empresa):
    checks = []
    if not empresa:
        checks.append(_check(
            CAT_EMPRESA,
            'Sin empresa configurada',
            'No hay empresa registrada. Crea una empresa para empezar.',
            'error', link=reverse('empresas_lista') if _url_exists('empresas_lista') else '/admin/empresas/empresa/',
            peso=100,
        ))
        return checks

    if empresa.ruc and len(empresa.ruc) == 11:
        checks.append(_check(CAT_EMPRESA, 'RUC válido', f'RUC {empresa.ruc} registrado.', 'ok', peso=20))
    else:
        checks.append(_check(
            CAT_EMPRESA, 'RUC inválido o vacío',
            'El RUC es obligatorio para boletas, PLAME y T-Registro.',
            'error', link=f'/empresas/{empresa.pk}/datos/', peso=80,
        ))

    if empresa.razon_social:
        checks.append(_check(CAT_EMPRESA, 'Razón social registrada', empresa.razon_social, 'ok', peso=15))
    else:
        checks.append(_check(
            CAT_EMPRESA, 'Razón social vacía',
            'Aparecerá en blanco en boletas y reportes.',
            'error', link=f'/empresas/{empresa.pk}/datos/', peso=70,
        ))

    if empresa.representante_legal:
        checks.append(_check(
            CAT_EMPRESA, 'Representante legal',
            f'{empresa.representante_legal} ({empresa.cargo_representante or "sin cargo"})',
            'ok', peso=10,
        ))
    else:
        checks.append(_check(
            CAT_EMPRESA, 'Representante legal sin configurar',
            'Necesario para boletas (firma) y contratos.',
            'warn', link=f'/empresas/{empresa.pk}/datos/', peso=40,
        ))

    if empresa.logo:
        checks.append(_check(CAT_EMPRESA, 'Logo cargado', 'Aparecerá en boletas y reportes PDF.', 'ok', peso=8))
    else:
        checks.append(_check(
            CAT_EMPRESA, 'Sin logo',
            'Las boletas y reportes se verán genéricas. Sube el logo en la ficha de empresa.',
            'warn', link=f'/empresas/{empresa.pk}/datos/', peso=25,
        ))

    if empresa.direccion:
        checks.append(_check(CAT_EMPRESA, 'Dirección registrada', empresa.direccion, 'ok', peso=5))
    else:
        checks.append(_check(
            CAT_EMPRESA, 'Sin dirección fiscal',
            'Requerida por SUNAT en boletas y T-Registro.',
            'warn', link=f'/empresas/{empresa.pk}/datos/', peso=30,
        ))

    return checks


# ─── Conceptos ────────────────────────────────────────────────────
def _check_conceptos():
    checks = []
    total       = ConceptoRemunerativo.objects.count()
    activos     = ConceptoRemunerativo.objects.filter(activo=True).count()
    # Solo cuentan como "sin PLAME" los conceptos que SÍ son líneas del PLAME 0601
    # del trabajador (ingresos y descuentos). Los aportes del empleador
    # (EsSalud/SCTR, tipo=APORTE_EMPLEADOR) y las provisiones internas
    # (prov-gratif/prov-cts, subtipo=PROVISION) NO se declaran como concepto del
    # trabajador → exigirles código PLAME era falsa alarma que bajaba el score.
    sin_plame   = (ConceptoRemunerativo.objects
                   .filter(codigo_plame='', activo=True)
                   .exclude(tipo='APORTE_EMPLEADOR')
                   .exclude(subtipo='PROVISION')
                   .count())

    if total == 0:
        checks.append(_check(
            CAT_CONCEPTOS, 'Sin conceptos remunerativos',
            'No hay catálogo de conceptos. Ejecuta `seed_conceptos_base` o usa el Wizard.',
            'error', link=reverse('wizard_step1'), peso=100,
        ))
        return checks

    if activos >= 10:
        checks.append(_check(
            CAT_CONCEPTOS, f'{activos} conceptos activos',
            'Catálogo robusto — suficiente para procesar planilla típica.',
            'ok', peso=20,
        ))
    elif activos >= 5:
        checks.append(_check(
            CAT_CONCEPTOS, f'Solo {activos} conceptos activos',
            'Recomendado tener al menos 10 (sueldo, asig. familiar, AFP/ONP, ESSALUD, IR, gratif, CTS, vacaciones...).',
            'warn', link=reverse('conceptos_templates'), peso=50,
        ))
    else:
        checks.append(_check(
            CAT_CONCEPTOS, f'Solo {activos} conceptos activos',
            'Catálogo muy reducido. Aplica los templates oficiales SUNAT.',
            'error', link=reverse('conceptos_templates'), peso=80,
        ))

    # Conceptos críticos (deben existir activos)
    # OJO: los códigos reales usan guion (sueldo-basico, ir-5ta), no guion bajo.
    # Antes se buscaba sueldo_basico/ir_5ta → falso "Falta" que bajaba el score
    # y disparaba severidad crítica aunque los conceptos SÍ existían.
    criticos = [
        ('sueldo-basico',   'Remuneración básica'),
        ('essalud',         'EsSalud 9%'),
        ('ir-5ta',          'IR 5ta Categoría'),
    ]
    for codigo, label in criticos:
        existe = ConceptoRemunerativo.objects.filter(codigo=codigo, activo=True).exists()
        if existe:
            checks.append(_check(CAT_CONCEPTOS, f'✓ {label}', f'Concepto "{codigo}" activo.', 'ok', peso=10))
        else:
            checks.append(_check(
                CAT_CONCEPTOS, f'Falta: {label}',
                f'No existe (o está inactivo) el concepto "{codigo}". Crítico para boletas.',
                'error', link=reverse('conceptos_templates'), peso=70,
            ))

    if sin_plame > 0:
        checks.append(_check(
            CAT_CONCEPTOS, f'{sin_plame} conceptos sin PLAME',
            'Estos conceptos no exportarán al archivo SUNAT. Asigna su código PLAME.',
            'warn', link=reverse('conceptos_lista') + '?activo=1&q=', peso=40,
        ))
    else:
        checks.append(_check(CAT_CONCEPTOS, 'Todos los conceptos tienen PLAME', 'Listo para exportar a SUNAT.', 'ok', peso=15))

    return checks


# ─── Personal ─────────────────────────────────────────────────────
def _check_personal():
    checks = []
    try:
        from personal.models import Personal
    except ImportError:
        return checks

    total   = Personal.objects.count()
    activos = Personal.objects.filter(activo=True).count() if hasattr(Personal, 'activo') else total

    if total == 0:
        checks.append(_check(
            CAT_PERSONAL, 'Sin trabajadores cargados',
            'Importa o crea trabajadores antes de generar planilla.',
            'error', link='/personal/', peso=100,
        ))
        return checks

    checks.append(_check(
        CAT_PERSONAL, f'{activos} trabajadores activos',
        f'Total: {total} (incluyendo cesados).', 'ok', peso=15,
    ))

    # CUSPP para los que están en AFP
    try:
        afp_sin_cuspp = Personal.objects.filter(
            sistema_pensionario__in=['AFP', 'AFP_INTEGRA', 'AFP_HABITAT', 'AFP_PROFUTURO', 'AFP_PRIMA'],
        ).exclude(cuspp__isnull=False).exclude(cuspp__gt='').count()
        if afp_sin_cuspp:
            checks.append(_check(
                CAT_PERSONAL, f'{afp_sin_cuspp} trabajadores AFP sin CUSPP',
                'Necesario para AFPnet. Completa CUSPP en la ficha de cada trabajador.',
                'warn', link='/personal/?q=', peso=35,
            ))
        else:
            checks.append(_check(CAT_PERSONAL, 'Todos los trabajadores AFP tienen CUSPP', 'Listo para AFPnet.', 'ok', peso=10))
    except Exception:
        pass

    # Sin fecha de alta
    try:
        sin_fecha = Personal.objects.filter(fecha_alta__isnull=True).count()
        if sin_fecha:
            checks.append(_check(
                CAT_PERSONAL, f'{sin_fecha} trabajadores sin fecha de alta',
                'Imprescindible para CTS, gratif y vacaciones (proporcional).',
                'warn', link='/personal/?q=', peso=40,
            ))
    except Exception:
        pass

    return checks


# ─── Planilla ─────────────────────────────────────────────────────
def _check_planilla():
    checks = []
    n_periodos = PeriodoNomina.objects.filter(tipo='REGULAR').count()
    n_aprob    = PeriodoNomina.objects.filter(tipo='REGULAR', estado__in=['APROBADO', 'CERRADO']).count()

    if n_periodos == 0:
        checks.append(_check(
            CAT_PLANILLA, 'Sin períodos de planilla',
            'Crea tu primer período (mes/año) y genera planilla.',
            'warn', link=reverse('nominas_periodo_crear') if _url_exists('nominas_periodo_crear') else '/nominas/', peso=50,
        ))
    elif n_aprob == 0:
        checks.append(_check(
            CAT_PLANILLA, f'{n_periodos} períodos, ninguno aprobado',
            'Aprueba tu primer período para liberar boletas.',
            'warn', link='/nominas/', peso=30,
        ))
    else:
        checks.append(_check(
            CAT_PLANILLA, f'{n_aprob} período(s) aprobado(s)',
            f'Total registros: {n_periodos}. Sistema en producción.', 'ok', peso=15,
        ))

    # Saldos de apertura
    try:
        from .models import SaldoAperturaTrabajador
        if SaldoAperturaTrabajador.objects.exists():
            checks.append(_check(
                CAT_PLANILLA, 'Saldos de apertura cargados',
                f'{SaldoAperturaTrabajador.objects.count()} saldos iniciales registrados.',
                'ok', peso=10,
            ))
        else:
            checks.append(_check(
                CAT_PLANILLA, 'Sin saldos de apertura',
                'Recomendado si migras de otro sistema (CTS, gratif acumulada, etc.).',
                'info', link='/nominas/apertura/', peso=15,
            ))
    except Exception:
        pass

    return checks


# ─── Tasas legales ───────────────────────────────────────────────
def _check_tasas():
    checks = []
    try:
        from personal.models import ConfiguracionAFP  # noqa: F401
        from personal.models import ConfiguracionAFP as _C
        n_afp = _C.objects.filter(activo=True).count() if hasattr(_C, 'activo') else _C.objects.count()
        if n_afp >= 4:
            checks.append(_check(CAT_TASAS, f'{n_afp} AFPs configuradas',
                                 'Tasas vigentes — Integra, Habitat, Profuturo, Prima.', 'ok', peso=10))
        else:
            checks.append(_check(CAT_TASAS, f'Solo {n_afp} AFPs', 'Verifica que las 4 AFPs estén configuradas y al día.',
                                 'warn', link='/nominas/config/tasas-afp/', peso=25))
    except Exception:
        # ConfiguracionAFP no existe — no es crítico
        pass

    return checks


# ─── URL exists helper ───────────────────────────────────────────
def _url_exists(name):
    try:
        reverse(name)
        return True
    except Exception:
        return False


# ─── Builder principal — usable por vista + API ──────────────────
def build_onboarding_report():
    """
    Construye reporte completo de onboarding.

    Retorna dict con:
    - empresa, checks, por_categoria, score, status, status_label,
    - n_ok, n_warn, n_error, n_info, total, pendientes
    """
    # Empresa activa
    empresa = None
    try:
        from empresas.models import Empresa
        empresa = Empresa.objects.order_by('pk').first()
    except Exception:
        pass

    # Recolectar todos los checks
    checks = []
    checks.extend(_check_empresa(empresa))
    checks.extend(_check_conceptos())
    checks.extend(_check_personal())
    checks.extend(_check_planilla())
    checks.extend(_check_tasas())

    # Score: cada error resta su peso completo, warn resta 50% del peso
    total_peso = sum(c['peso'] for c in checks) or 1
    penal = sum(
        c['peso'] if c['severidad'] == 'error' else
        (c['peso'] * 0.5) if c['severidad'] == 'warn' else 0
        for c in checks
    )
    score = max(0, round(100 - (penal / total_peso * 100)))

    # Agrupar por categoría
    por_categoria = {}
    for c in checks:
        cat = c['categoria']
        por_categoria.setdefault(cat, {
            'label': c['cat_label'],
            'icon':  c['cat_icon'],
            'items': [],
            'ok_count':    0,
            'warn_count':  0,
            'error_count': 0,
        })
        por_categoria[cat]['items'].append(c)
        if c['severidad'] == 'ok':
            por_categoria[cat]['ok_count'] += 1
        elif c['severidad'] == 'warn':
            por_categoria[cat]['warn_count'] += 1
        elif c['severidad'] == 'error':
            por_categoria[cat]['error_count'] += 1

    # Contadores globales
    n_ok    = sum(1 for c in checks if c['severidad'] == 'ok')
    n_warn  = sum(1 for c in checks if c['severidad'] == 'warn')
    n_error = sum(1 for c in checks if c['severidad'] == 'error')
    n_info  = sum(1 for c in checks if c['severidad'] == 'info')

    # Status global
    if n_error > 0:
        status = 'critico'
        status_label = 'Requiere atención inmediata'
        status_color = '#dc2626'
    elif n_warn > 0:
        status = 'mejorable'
        status_label = 'Configuración mejorable'
        status_color = '#d97706'
    else:
        status = 'listo'
        status_label = '¡Empresa lista para producción!'
        status_color = '#15803d'

    # Lista priorizada de "siguiente acción" (top 3 más críticos)
    pendientes = sorted(
        [c for c in checks if c['severidad'] in ('error', 'warn')],
        key=lambda c: (-1 if c['severidad'] == 'error' else 0, -c['peso']),
    )[:5]

    return {
        'empresa':        empresa,
        'checks':         checks,
        'por_categoria':  por_categoria,
        'n_ok':           n_ok,
        'n_warn':         n_warn,
        'n_error':        n_error,
        'n_info':         n_info,
        'total':          len(checks),
        'score':          score,
        'status':         status,
        'status_label':   status_label,
        'status_color':   status_color,
        'pendientes':     pendientes,
    }


# ─── Vista HTML ──────────────────────────────────────────────────
@login_required
@solo_admin
def onboarding_validador(request):
    """Checklist consolidado: muestra estado de configuración de la empresa."""
    report = build_onboarding_report()
    return render(request, 'nominas/onboarding_validador.html', report)


# ─── API JSON ────────────────────────────────────────────────────
@login_required
def onboarding_validador_api(request):
    """
    GET /api/v1/nominas/onboarding/  →  JSON con score + checks.

    Útil para CI checks, monitoreo externo, integraciones, dashboards.
    """
    from django.http import JsonResponse

    report = build_onboarding_report()
    # Serializar a JSON-friendly: empresa→dict, checks ya son dicts puros
    empresa = report['empresa']
    empresa_dict = None
    if empresa:
        empresa_dict = {
            'id':            empresa.pk,
            'ruc':           empresa.ruc,
            'razon_social':  empresa.razon_social,
            'plan':          getattr(empresa, 'plan', None),
            'representante': empresa.representante_legal or None,
        }

    return JsonResponse({
        'score':         report['score'],
        'status':        report['status'],
        'status_label':  report['status_label'],
        'empresa':       empresa_dict,
        'totals': {
            'ok':    report['n_ok'],
            'warn':  report['n_warn'],
            'error': report['n_error'],
            'info':  report['n_info'],
            'total': report['total'],
        },
        'checks':        report['checks'],
        'pendientes':    report['pendientes'],
        'generated_at':  timezone_now_iso(),
    })


def timezone_now_iso():
    from django.utils import timezone as dj_tz
    return dj_tz.now().isoformat()


# ─── PDF Onboarding (sales asset!) ───────────────────────────────
@login_required
@solo_admin
def onboarding_validador_pdf(request):
    """
    Genera PDF del reporte de onboarding — para enviar al cliente.
    Útil como sales asset: "Aquí está la evidencia de que tu sistema está al 95%".
    """
    from django.http import HttpResponse
    from django.template.loader import render_to_string
    from django.utils import timezone as dj_tz

    report = build_onboarding_report()
    report['fecha_emision'] = dj_tz.now()

    html = render_to_string('nominas/onboarding_validador_pdf.html', report)

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        resp = HttpResponse(pdf_bytes, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="onboarding_{dj_tz.now():%Y%m%d}.pdf"'
        )
        return resp
    except ImportError:
        # Fallback HTML si WeasyPrint no está disponible
        return HttpResponse(html, content_type='text/html; charset=utf-8')
