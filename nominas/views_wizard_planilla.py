"""
Wizard "Configurar mi planilla en 5 minutos" — para cliente nuevo.

URL: /nominas/configurar/wizard/

3 pasos:
1. Selección de tipo de empresa (gastronomía, construcción, oficina, etc.)
2. Selección de conceptos comunes a usar (checkboxes con templates)
3. Confirmar y aplicar — crea todos los conceptos seleccionados

Pensado para que el cliente arranque ya configurado.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .models import ConceptoRemunerativo
from .views_conceptos import TEMPLATES_CONCEPTOS


PERFILES_EMPRESA = {
    'gastronomia': {
        'nombre':      'Gastronomía / Restaurante',
        'icon':        'fa-utensils',
        'color':       '#dc2626',
        'descripcion': 'Restaurantes, bares, catering. Incluye propinas, recargo consumo, alimentación.',
        'conceptos_recomendados': [
            'sueldo_basico', 'asignacion_familiar', 'horas_extras_25', 'horas_extras_35',
            'propinas', 'recargo_consumo', 'refrigerio',
            'descuento_onp', 'descuento_afp_aporte', 'descuento_afp_comision', 'descuento_afp_seguro',
            'descuento_ir_5ta', 'descuento_eps_aporte',
            'essalud_9pct', 'gratificacion_jul', 'gratificacion_dic', 'bonif_extraord_grat', 'cts_provision',
            'vacaciones_truncas', 'asignacion_vacacional',
        ],
    },
    'construccion': {
        'nombre':      'Construcción Civil (D.Leg. 727)',
        'icon':        'fa-hard-hat',
        'color':       '#f59e0b',
        'descripcion': 'Empresas constructoras. Régimen CAPECO-FTCCP, SCTR obligatorio, BUC.',
        'conceptos_recomendados': [
            'sueldo_basico', 'asignacion_familiar', 'horas_extras_25', 'horas_extras_35',
            'movilidad', 'bonif_riesgo',
            'descuento_onp', 'descuento_afp_aporte', 'descuento_afp_comision', 'descuento_afp_seguro',
            'descuento_ir_5ta',
            'essalud_9pct', 'sctr_salud', 'sctr_pension',
            'gratificacion_jul', 'gratificacion_dic', 'bonif_extraord_grat', 'cts_provision',
            'vacaciones_truncas', 'asignacion_vacacional',
        ],
    },
    'oficina': {
        'nombre':      'Oficina / Servicios profesionales',
        'icon':        'fa-briefcase',
        'color':       '#0891b2',
        'descripcion': 'Empresas de servicios, oficinas administrativas, consultoras.',
        'conceptos_recomendados': [
            'sueldo_basico', 'asignacion_familiar', 'horas_extras_25', 'horas_extras_35',
            'comision_ventas', 'bono_desempeno', 'movilidad', 'vale_canasta',
            'descuento_onp', 'descuento_afp_aporte', 'descuento_afp_comision', 'descuento_afp_seguro',
            'descuento_ir_5ta', 'descuento_eps_aporte',
            'essalud_9pct', 'gratificacion_jul', 'gratificacion_dic', 'bonif_extraord_grat', 'cts_provision',
            'vacaciones_truncas', 'asignacion_vacacional',
        ],
    },
    'comercio': {
        'nombre':      'Comercio / Retail',
        'icon':        'fa-store',
        'color':       '#16a34a',
        'descripcion': 'Tiendas, bodegas, comercio al por menor. Comisiones por ventas.',
        'conceptos_recomendados': [
            'sueldo_basico', 'asignacion_familiar', 'horas_extras_25',
            'comision_ventas', 'bono_desempeno',
            'descuento_onp', 'descuento_afp_aporte', 'descuento_afp_comision', 'descuento_afp_seguro',
            'descuento_ir_5ta',
            'essalud_9pct', 'gratificacion_jul', 'gratificacion_dic', 'bonif_extraord_grat', 'cts_provision',
            'vacaciones_truncas', 'asignacion_vacacional',
        ],
    },
    'salud': {
        'nombre':      'Salud / Clínicas',
        'icon':        'fa-hospital',
        'color':       '#7c3aed',
        'descripcion': 'Clínicas, consultorios, farmacias. Turnos nocturnos, bonificación por riesgo.',
        'conceptos_recomendados': [
            'sueldo_basico', 'asignacion_familiar', 'horas_extras_25', 'horas_extras_35',
            'bonif_riesgo', 'movilidad',
            'descuento_onp', 'descuento_afp_aporte', 'descuento_afp_comision', 'descuento_afp_seguro',
            'descuento_ir_5ta', 'descuento_eps_aporte',
            'essalud_9pct', 'sctr_salud', 'gratificacion_jul', 'gratificacion_dic', 'bonif_extraord_grat',
            'cts_provision', 'vacaciones_truncas', 'asignacion_vacacional',
        ],
    },
    'personalizado': {
        'nombre':      'Personalizado (elegir todo)',
        'icon':        'fa-cog',
        'color':       '#64748b',
        'descripcion': 'Yo eligiré qué conceptos usar, sin sugerencia automática.',
        'conceptos_recomendados': [],
    },
}


@login_required
def wizard_step1(request):
    """Paso 1: elegir perfil de empresa."""
    return render(request, 'nominas/conceptos/wizard_step1.html', {
        'perfiles': PERFILES_EMPRESA,
    })


@login_required
@require_http_methods(['GET', 'POST'])
def wizard_step2(request):
    """Paso 2: elegir conceptos a aplicar."""
    perfil_key = request.GET.get('perfil', 'personalizado')
    perfil = PERFILES_EMPRESA.get(perfil_key, PERFILES_EMPRESA['personalizado'])
    recomendados = set(perfil['conceptos_recomendados'])

    if request.method == 'POST':
        # Aplicar seleccionados
        seleccionados = request.POST.getlist('conceptos')
        created = 0
        existed = 0
        for key in seleccionados:
            t = TEMPLATES_CONCEPTOS.get(key)
            if not t:
                continue
            if ConceptoRemunerativo.objects.filter(codigo=t['codigo']).exists():
                existed += 1
                continue
            ConceptoRemunerativo.objects.create(**t)
            created += 1

        messages.success(
            request,
            f'✓ {created} conceptos creados. {existed} ya existían. '
            f'Total ahora: {ConceptoRemunerativo.objects.count()}. Tu planilla está lista para usarse.'
        )
        return redirect('conceptos_lista')

    # Agrupar templates por categoría para mostrar
    grupos = {}
    for key, t in TEMPLATES_CONCEPTOS.items():
        cat = t.get('categoria', 'OTRO')
        existing = ConceptoRemunerativo.objects.filter(codigo=t['codigo']).exists()
        if cat not in grupos:
            grupos[cat] = []
        grupos[cat].append({
            'key':       key,
            'template':  t,
            'recomendado': key in recomendados,
            'existing':  existing,
        })

    return render(request, 'nominas/conceptos/wizard_step2.html', {
        'perfil':       perfil,
        'perfil_key':   perfil_key,
        'grupos':       grupos,
    })
