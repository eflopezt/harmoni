"""
UI configurable de Conceptos Remunerativos.

URLs:
- /nominas/conceptos/                 — Lista + tabla con todas las flags
- /nominas/conceptos/nuevo/           — Crear concepto custom
- /nominas/conceptos/&lt;pk&gt;/editar/    — Editar concepto
- /nominas/conceptos/&lt;pk&gt;/eliminar/  — Eliminar (solo si no es_sistema)
- /nominas/conceptos/templates/       — Catálogo de conceptos típicos pre-armados
- /nominas/conceptos/templates/&lt;k&gt;/aplicar/  — Activa template como concepto

Permite al admin:
- Ver TODOS los conceptos con sus flags (essalud, afp, onp, renta, cts, gratif, vac)
- Configurar codigo_plame y casilla_plame para mapeo SUNAT
- Activar/desactivar
- Crear conceptos desde cero
- Aplicar templates de gastronomía (vale canasta, propinas, recargo, etc.)
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .models import ConceptoRemunerativo


# ════════════════════════════════════════════════════════════════════════
# Templates de conceptos típicos (catálogo)
# ════════════════════════════════════════════════════════════════════════

TEMPLATES_CONCEPTOS = {
    'vale_canasta': {
        'codigo': 'vale_canasta', 'nombre': 'Vale de canasta',
        'descripcion': 'Vale de canasta navideña o mensual. NO remunerativo. No afecta ESSALUD ni AFP ni IR. (Art. 19 LRJ).',
        'categoria': 'ALIMENTACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('200.00'),
        'afecto_essalud': False, 'afecto_afp': False, 'afecto_onp': False,
        'afecto_renta': False, 'afecto_cts': False, 'afecto_gratif': False,
        'codigo_plame': '0922',  # Otros ingresos no remunerativos
    },
    'movilidad': {
        'codigo': 'movilidad', 'nombre': 'Movilidad',
        'descripcion': 'Asignación por movilidad. NO remunerativo (Art. 19 LRJ).',
        'categoria': 'MOVILIDAD', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('150.00'),
        'afecto_essalud': False, 'afecto_afp': False, 'afecto_renta': False,
        'codigo_plame': '0916',
    },
    'refrigerio': {
        'codigo': 'refrigerio', 'nombre': 'Refrigerio',
        'descripcion': 'Refrigerio servido en el centro de trabajo. NO remunerativo.',
        'categoria': 'ALIMENTACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('100.00'),
        'codigo_plame': '0917',
    },
    'propinas': {
        'codigo': 'propinas', 'nombre': 'Propinas',
        'descripcion': 'Propinas recibidas por el personal de servicio. NO remunerativo (DS 003-2018-TR).',
        'categoria': 'PROPINAS', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0920',
    },
    'recargo_consumo': {
        'codigo': 'recargo_consumo', 'nombre': 'Recargo por consumo (10%)',
        'descripcion': 'Recargo del 10% al consumo distribuido entre el personal de servicio. NO remunerativo.',
        'categoria': 'PROPINAS', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0921',
    },
    'bonif_riesgo': {
        'codigo': 'bonif_riesgo', 'nombre': 'Bonificación por riesgo',
        'descripcion': 'Bonificación por trabajo de riesgo (cocina, manejo de fuego). REMUNERATIVA — afecta todo.',
        'categoria': 'BONIFICACION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('5.00'),
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0202',
    },
    'comision_ventas': {
        'codigo': 'comision_ventas', 'nombre': 'Comisión por ventas',
        'descripcion': 'Comisión variable. REMUNERATIVA — afecta todo.',
        'categoria': 'COMISION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0107',
    },
    'asignacion_escolar': {
        'codigo': 'asignacion_escolar', 'nombre': 'Asignación escolar',
        'descripcion': 'Asignación anual por escolaridad (marzo). NO remunerativa.',
        'categoria': 'FAMILIAR', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('250.00'),
        'codigo_plame': '0918',
    },
    'bono_desempeno': {
        'codigo': 'bono_desempeno', 'nombre': 'Bono por desempeño',
        'descripcion': 'Bono anual o trimestral por cumplimiento de metas. REMUNERATIVO.',
        'categoria': 'BONIFICACION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0307',
    },
    'descuento_eps': {
        'codigo': 'descuento_eps', 'nombre': 'Descuento EPS (aporte trabajador)',
        'descripcion': 'Descuento por afiliación a EPS (Pacífico Salud, Rímac EPS, etc.). 2.25% RMV.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('45.00'),
        'codigo_plame': '0608',
    },
    'descuento_judicial': {
        'codigo': 'descuento_judicial', 'nombre': 'Descuento por mandato judicial',
        'descripcion': 'Descuento por alimentos u otra orden judicial. Máximo 60% del neto.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0612',
    },
    'descuento_prestamo': {
        'codigo': 'descuento_prestamo', 'nombre': 'Descuento por préstamo',
        'descripcion': 'Cuota de préstamo otorgado por la empresa.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
    },
}


# ════════════════════════════════════════════════════════════════════════
# Lista de conceptos
# ════════════════════════════════════════════════════════════════════════

@login_required
def conceptos_lista(request):
    """Lista todos los conceptos con sus flags y mapeo PLAME."""
    conceptos = ConceptoRemunerativo.objects.all().order_by('tipo', 'orden', 'nombre')

    # Filtros
    tipo_filter = request.GET.get('tipo', '')
    if tipo_filter:
        conceptos = conceptos.filter(tipo=tipo_filter)

    activo_filter = request.GET.get('activo', '')
    if activo_filter == '1':
        conceptos = conceptos.filter(activo=True)
    elif activo_filter == '0':
        conceptos = conceptos.filter(activo=False)

    # Stats
    total           = ConceptoRemunerativo.objects.count()
    activos         = ConceptoRemunerativo.objects.filter(activo=True).count()
    sin_plame       = ConceptoRemunerativo.objects.filter(codigo_plame='').count()
    custom          = ConceptoRemunerativo.objects.filter(es_sistema=False).count()

    return render(request, 'nominas/conceptos/lista.html', {
        'conceptos':    conceptos,
        'total':        total,
        'activos':      activos,
        'sin_plame':    sin_plame,
        'custom':       custom,
        'tipo_filter':  tipo_filter,
        'activo_filter': activo_filter,
        'tipos':        ConceptoRemunerativo.TIPO_CHOICES,
    })


# ════════════════════════════════════════════════════════════════════════
# Crear / Editar concepto
# ════════════════════════════════════════════════════════════════════════

def _save_concepto_from_post(post, concepto=None):
    """Helper para crear/editar desde POST. Devuelve (concepto, errors)."""
    errors = []
    is_new = concepto is None

    codigo = (post.get('codigo') or '').strip().lower().replace(' ', '_')
    nombre = (post.get('nombre') or '').strip()

    if is_new and ConceptoRemunerativo.objects.filter(codigo=codigo).exists():
        errors.append(f'Ya existe un concepto con código "{codigo}"')
    if not nombre:
        errors.append('Nombre es obligatorio')

    if errors:
        return None, errors

    if is_new:
        concepto = ConceptoRemunerativo(codigo=codigo)

    concepto.nombre      = nombre
    concepto.descripcion = post.get('descripcion', '')
    concepto.categoria   = post.get('categoria', 'OTRO')
    concepto.tipo        = post.get('tipo', 'INGRESO')
    concepto.subtipo     = post.get('subtipo', 'REMUNERATIVO')
    concepto.formula     = post.get('formula', 'FIJO')

    try:
        concepto.porcentaje = Decimal(post.get('porcentaje') or '0')
    except Exception:
        concepto.porcentaje = Decimal('0')
    try:
        concepto.monto_fijo = Decimal(post.get('monto_fijo') or '0')
    except Exception:
        concepto.monto_fijo = Decimal('0')

    # Afectaciones (checkboxes)
    concepto.afecto_essalud    = post.get('afecto_essalud') == 'on'
    concepto.afecto_afp        = post.get('afecto_afp') == 'on'
    concepto.afecto_onp        = post.get('afecto_onp') == 'on'
    concepto.afecto_renta      = post.get('afecto_renta') == 'on'
    concepto.afecto_cts        = post.get('afecto_cts') == 'on'
    concepto.afecto_gratif     = post.get('afecto_gratif') == 'on'
    concepto.afecto_vacaciones = post.get('afecto_vacaciones') == 'on'

    # PLAME
    concepto.codigo_plame      = post.get('codigo_plame', '').strip()
    concepto.casilla_plame     = post.get('casilla_plame', '').strip()
    concepto.codigo_tregistro  = post.get('codigo_tregistro', '').strip()

    concepto.activo = post.get('activo') == 'on'
    try:
        concepto.orden = int(post.get('orden') or 0)
    except Exception:
        concepto.orden = 0

    concepto.save()
    return concepto, []


@login_required
@require_http_methods(['GET', 'POST'])
def concepto_nuevo(request):
    if request.method == 'POST':
        concepto, errors = _save_concepto_from_post(request.POST)
        if not errors:
            messages.success(request, f'Concepto "{concepto.nombre}" creado.')
            return redirect('conceptos_lista')
        return render(request, 'nominas/conceptos/form.html', {
            'concepto': None, 'errors': errors,
            'form_data': request.POST,
            'categorias': ConceptoRemunerativo.CATEGORIA_CHOICES,
            'tipos':      ConceptoRemunerativo.TIPO_CHOICES,
            'subtipos':   ConceptoRemunerativo.SUBTIPO_CHOICES,
            'formulas':   ConceptoRemunerativo.FORMULA_CHOICES,
        })
    return render(request, 'nominas/conceptos/form.html', {
        'concepto':   None,
        'categorias': ConceptoRemunerativo.CATEGORIA_CHOICES,
        'tipos':      ConceptoRemunerativo.TIPO_CHOICES,
        'subtipos':   ConceptoRemunerativo.SUBTIPO_CHOICES,
        'formulas':   ConceptoRemunerativo.FORMULA_CHOICES,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def concepto_editar(request, pk):
    concepto = get_object_or_404(ConceptoRemunerativo, pk=pk)
    if request.method == 'POST':
        c, errors = _save_concepto_from_post(request.POST, concepto)
        if not errors:
            messages.success(request, f'Concepto "{c.nombre}" actualizado.')
            return redirect('conceptos_lista')
        return render(request, 'nominas/conceptos/form.html', {
            'concepto': concepto, 'errors': errors,
            'form_data': request.POST,
            'categorias': ConceptoRemunerativo.CATEGORIA_CHOICES,
            'tipos':      ConceptoRemunerativo.TIPO_CHOICES,
            'subtipos':   ConceptoRemunerativo.SUBTIPO_CHOICES,
            'formulas':   ConceptoRemunerativo.FORMULA_CHOICES,
        })
    return render(request, 'nominas/conceptos/form.html', {
        'concepto':   concepto,
        'categorias': ConceptoRemunerativo.CATEGORIA_CHOICES,
        'tipos':      ConceptoRemunerativo.TIPO_CHOICES,
        'subtipos':   ConceptoRemunerativo.SUBTIPO_CHOICES,
        'formulas':   ConceptoRemunerativo.FORMULA_CHOICES,
    })


# ════════════════════════════════════════════════════════════════════════
# Templates / catálogo
# ════════════════════════════════════════════════════════════════════════

@login_required
def conceptos_templates(request):
    """Catálogo con templates pre-armados. Indica cuáles ya están instalados."""
    items = []
    for key, t in TEMPLATES_CONCEPTOS.items():
        existing = ConceptoRemunerativo.objects.filter(codigo=t['codigo']).first()
        items.append({
            'key':      key,
            'template': t,
            'instalado': existing is not None,
            'existing':  existing,
        })
    return render(request, 'nominas/conceptos/templates.html', {
        'items': items,
    })


@login_required
@require_http_methods(['POST'])
def concepto_aplicar_template(request, key):
    """Crea un concepto desde un template."""
    t = TEMPLATES_CONCEPTOS.get(key)
    if not t:
        messages.error(request, 'Template no encontrado.')
        return redirect('conceptos_templates')

    if ConceptoRemunerativo.objects.filter(codigo=t['codigo']).exists():
        messages.warning(request, f'El concepto "{t["nombre"]}" ya existe.')
        return redirect('conceptos_lista')

    ConceptoRemunerativo.objects.create(**t)
    messages.success(request, f'Concepto "{t["nombre"]}" creado.')
    return redirect('conceptos_lista')
