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

from .models import ConceptoAuditLog, ConceptoRemunerativo
from .signals_audit import clear_audit_context, set_audit_context


def _set_audit_from_request(request, accion_override=None):
    """Inyecta usuario + IP + UA + URL para que los signals tengan contexto."""
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
         or request.META.get('REMOTE_ADDR') or None
    set_audit_context(
        usuario=request.user if request.user.is_authenticated else None,
        ip=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        contexto=request.path[:200],
        accion_override=accion_override,
    )


# ════════════════════════════════════════════════════════════════════════
# Templates de conceptos típicos (catálogo)
# ════════════════════════════════════════════════════════════════════════

TEMPLATES_CONCEPTOS = {
    # ─── INGRESOS REMUNERATIVOS ─────────────────────────────────────────
    'sueldo_basico': {
        'codigo': 'sueldo_basico', 'nombre': 'Remuneración o jornal básico',
        'descripcion': 'Sueldo base mensual del trabajador. REMUNERATIVO — afecta todo.',
        'categoria': 'SUELDO', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'FIJO',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'afecto_vacaciones': True,
        'codigo_plame': '0121',  # OFICIAL SUNAT
    },
    'asignacion_familiar': {
        'codigo': 'asignacion_familiar', 'nombre': 'Asignación familiar',
        'descripcion': '10% RMV mensual (Ley 25129). REMUNERATIVO si trabajador tiene hijos menores.',
        'categoria': 'FAMILIAR', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('113.00'),  # 10% RMV 2026 (S/1130)
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'afecto_vacaciones': True,
        'codigo_plame': '0201',
    },
    'comision_ventas': {
        'codigo': 'comision_ventas', 'nombre': 'Comisiones o destajo',
        'descripcion': 'Comisión variable por ventas/destajo. REMUNERATIVA — afecta todo.',
        'categoria': 'COMISION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'afecto_vacaciones': True,
        'codigo_plame': '0103',
    },
    'horas_extras_25': {
        'codigo': 'horas_extras_25', 'nombre': 'Horas extras 25%',
        'descripcion': 'Sobretiempo primera y segunda hora (Ley 27671 art. 10). REMUNERATIVO.',
        'categoria': 'OTROS_ING', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'HE_25',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0105',
    },
    'horas_extras_35': {
        'codigo': 'horas_extras_35', 'nombre': 'Horas extras 35%',
        'descripcion': 'Sobretiempo tercera hora en adelante. REMUNERATIVO.',
        'categoria': 'OTROS_ING', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'HE_35',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0106',
    },
    'asignacion_vacacional': {
        'codigo': 'asignacion_vacacional', 'nombre': 'Asignación vacacional',
        'descripcion': 'Pago por descanso vacacional (30 días al año). REMUNERATIVO.',
        'categoria': 'OTROS_ING', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': False, 'afecto_gratif': True,
        'codigo_plame': '0210',
    },
    'vacaciones_truncas': {
        'codigo': 'vacaciones_truncas', 'nombre': 'Vacaciones truncas',
        'descripcion': 'Vacaciones proporcionales al cese (1/12 por mes trabajado).',
        'categoria': 'OTROS_ING', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': False, 'afecto_gratif': False,
        'codigo_plame': '0114',
    },
    'bonif_riesgo': {
        'codigo': 'bonif_riesgo', 'nombre': 'Bonificación por riesgo',
        'descripcion': 'Bonificación por trabajo de riesgo (cocina, manejo de fuego). REMUNERATIVA.',
        'categoria': 'BONIFICACION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('5.00'),
        'afecto_essalud': True, 'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': True, 'afecto_gratif': True,
        'codigo_plame': '0202',
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

    # ─── INGRESOS NO REMUNERATIVOS (DS 003-2018-TR / Art. 19 LRJ) ──────
    'vale_canasta': {
        'codigo': 'vale_canasta', 'nombre': 'Canasta de Navidad o similares',
        'descripcion': 'Vale de canasta navideña. NO remunerativo (Art. 19 LRJ).',
        'categoria': 'ALIMENTACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('200.00'),
        'codigo_plame': '0903',  # OFICIAL
    },
    'movilidad': {
        'codigo': 'movilidad', 'nombre': 'Movilidad de libre disposición',
        'descripcion': 'Asignación por movilidad. NO remunerativo (Art. 19 LRJ).',
        'categoria': 'MOVILIDAD', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('150.00'),
        'codigo_plame': '0908',
    },
    'refrigerio': {
        'codigo': 'refrigerio', 'nombre': 'Refrigerio (no es alimentación principal)',
        'descripcion': 'Refrigerio servido en el centro de trabajo. NO remunerativo.',
        'categoria': 'ALIMENTACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('100.00'),
        'codigo_plame': '0914',
    },
    'prestacion_alimentaria': {
        'codigo': 'prestacion_alimentaria', 'nombre': 'Prestaciones alimentarias — suministros directos',
        'descripcion': 'Almuerzo provisto por la empresa (vales/tickets restaurante). NO remunerativo.',
        'categoria': 'ALIMENTACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('300.00'),
        'codigo_plame': '0112',
    },
    'propinas': {
        'codigo': 'propinas', 'nombre': 'Propinas',
        'descripcion': 'Propinas recibidas por personal de servicio. NO remunerativo (DS 003-2018-TR).',
        'categoria': 'PROPINAS', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0925',  # Otros ingresos no remunerativos
    },
    'recargo_consumo': {
        'codigo': 'recargo_consumo', 'nombre': 'Recargo por consumo 10%',
        'descripcion': '10% al consumo distribuido al personal de servicio (DS 012-2003-TR). NO remunerativo.',
        'categoria': 'PROPINAS', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0925',
    },
    'asignacion_escolar': {
        'codigo': 'asignacion_escolar', 'nombre': 'Asignación escolar',
        'descripcion': 'Asignación anual por escolaridad (marzo). NO remunerativa.',
        'categoria': 'FAMILIAR', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'FIJO', 'monto_fijo': Decimal('250.00'),
        'codigo_plame': '0925',
    },

    # ─── DESCUENTOS AL TRABAJADOR ────────────────────────────────────────
    'descuento_onp': {
        'codigo': 'descuento_onp', 'nombre': 'ONP — Sistema Nacional Pensiones',
        'descripcion': '13% sobre remuneración computable. Descuento al trabajador.',
        'categoria': 'APORTE', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'ONP',
        'codigo_plame': '0607',
    },
    'descuento_afp_aporte': {
        'codigo': 'descuento_afp_aporte', 'nombre': 'AFP — Aporte obligatorio 10%',
        'descripcion': 'Aporte AFP 10% obligatorio (Sistema Privado de Pensiones).',
        'categoria': 'APORTE', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'AFP_APORTE',
        'codigo_plame': '0608',
    },
    'descuento_afp_comision': {
        'codigo': 'descuento_afp_comision', 'nombre': 'AFP — Comisión flujo',
        'descripcion': 'Comisión variable por AFP (Integra 1.55%, Prima 1.60%, Habitat 1.47%, Profuturo 1.69%).',
        'categoria': 'APORTE', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'AFP_COMISION',
        'codigo_plame': '0609',
    },
    'descuento_afp_seguro': {
        'codigo': 'descuento_afp_seguro', 'nombre': 'AFP — Prima de seguro',
        'descripcion': 'Prima de seguro AFP (~1.74% sobre tope), variable por AFP.',
        'categoria': 'APORTE', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'AFP_SEGURO',
        'codigo_plame': '0610',
    },
    'descuento_ir_5ta': {
        'codigo': 'descuento_ir_5ta', 'nombre': 'IR 5ta categoría — Retención',
        'descripcion': 'Retención de IR para trabajadores con ingresos > 7 UIT anuales. Calculado por proyección.',
        'categoria': 'IMPUESTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'IR_5TA',
        'codigo_plame': '0605',
    },
    'descuento_eps_aporte': {
        'codigo': 'descuento_eps_aporte', 'nombre': 'EPS — Aporte trabajador',
        'descripcion': (
            'Trabajador afiliado a EPS (Rímac, Pacífico, etc.) puede aportar adicional. '
            'NO confundir con crédito EPS al empleador.'
        ),
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0611',
    },
    'descuento_judicial': {
        'codigo': 'descuento_judicial', 'nombre': 'Mandato judicial (alimentos, etc.)',
        'descripcion': 'Descuento autorizado u ordenado por mandato judicial. Máximo 60% del neto.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0703',
    },
    'descuento_prestamo': {
        'codigo': 'descuento_prestamo', 'nombre': 'Descuento por préstamo',
        'descripcion': 'Cuota de préstamo otorgado por la empresa.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0704',
    },
    'descuento_adelanto': {
        'codigo': 'descuento_adelanto', 'nombre': 'Adelanto de sueldo',
        'descripcion': 'Adelanto entregado durante el mes que se descuenta al pagar.',
        'categoria': 'DESCUENTO', 'tipo': 'DESCUENTO', 'subtipo': 'REMUNERATIVO',
        'formula': 'MANUAL',
        'codigo_plame': '0705',
    },

    # ─── APORTES DEL EMPLEADOR ───────────────────────────────────────────
    'essalud_9pct': {
        'codigo': 'essalud_9pct', 'nombre': 'ESSALUD 9% (seguro regular)',
        'descripcion': (
            'Aporte del empleador 9% sobre remuneración. Si trabajador tiene EPS, '
            'el empleador recibe crédito de hasta 2.25% (queda 6.75% efectivo).'
        ),
        'categoria': 'APORTE', 'tipo': 'APORTE_EMPLEADOR', 'subtipo': 'REMUNERATIVO',
        'formula': 'ESSALUD',
        'codigo_plame': '0804',
    },
    'essalud_eps_credito': {
        'codigo': 'essalud_eps_credito', 'nombre': 'EPS — Crédito empleador (reduce ESSALUD)',
        'descripcion': (
            'Cuando trabajador está en EPS, el empleador descuenta 2.25% de RMV del aporte '
            'ESSALUD (Ley 26790 art. 15). Reduce el ESSALUD efectivo de 9% a 6.75%.'
        ),
        'categoria': 'APORTE', 'tipo': 'APORTE_EMPLEADOR', 'subtipo': 'REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('-2.25'),  # negativo = reduce ESSALUD
        'codigo_plame': '0807',
    },
    'sctr_salud': {
        'codigo': 'sctr_salud', 'nombre': 'SCTR Salud (riesgo)',
        'descripcion': 'Seguro Complementario Trabajo de Riesgo (salud). Solo si la actividad es de riesgo (DS 003-98-SA).',
        'categoria': 'APORTE', 'tipo': 'APORTE_EMPLEADOR', 'subtipo': 'REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('1.55'),
        'codigo_plame': '0812',
    },
    'sctr_pension': {
        'codigo': 'sctr_pension', 'nombre': 'SCTR Pensión (riesgo)',
        'descripcion': 'Seguro Complementario Trabajo de Riesgo (pensión).',
        'categoria': 'APORTE', 'tipo': 'APORTE_EMPLEADOR', 'subtipo': 'REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('1.30'),
        'codigo_plame': '0813',
    },

    # ─── GRATIFICACIONES Y PROVISIONES ───────────────────────────────────
    'gratificacion_jul': {
        'codigo': 'gratificacion_jul', 'nombre': 'Gratificación Fiestas Patrias',
        'descripcion': 'Gratificación de julio (Ley 27735). 1 sueldo si tiene 6 meses, truncos si menos.',
        'categoria': 'GRATIFICACION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'GRATIFICACION',
        'afecto_essalud': False,  # Gratif NO afecta ESSALUD (Ley 30334)
        'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': False, 'afecto_gratif': False,
        'codigo_plame': '0301',
    },
    'gratificacion_dic': {
        'codigo': 'gratificacion_dic', 'nombre': 'Gratificación Navidad',
        'descripcion': 'Gratificación de diciembre (Ley 27735). 1 sueldo si tiene 6 meses, truncos si menos.',
        'categoria': 'GRATIFICACION', 'tipo': 'INGRESO', 'subtipo': 'REMUNERATIVO',
        'formula': 'GRATIFICACION',
        'afecto_essalud': False,
        'afecto_afp': True, 'afecto_onp': True,
        'afecto_renta': True, 'afecto_cts': False, 'afecto_gratif': False,
        'codigo_plame': '0302',
    },
    'bonif_extraord_grat': {
        'codigo': 'bonif_extraord_grat', 'nombre': 'Bonificación extraordinaria gratificación',
        'descripcion': (
            'Bonificación extraordinaria del 9% (sin EPS) o 6.75% (con EPS) sobre el '
            'monto de la gratificación. Ley 30334 / 29351. El % depende del régimen de '
            'salud del trabajador. NO remunerativo, NO afecta CTS ni Gratif.'
        ),
        'categoria': 'BONIFICACION', 'tipo': 'INGRESO', 'subtipo': 'NO_REMUNERATIVO',
        'formula': 'PORCENTAJE', 'porcentaje': Decimal('9.00'),
        # NO afecta nada de nada — es bonificación extraordinaria
        'afecto_renta': True,  # Sí está afecto a IR 5ta
        'codigo_plame': '0312',
    },
    'cts_provision': {
        'codigo': 'cts_provision', 'nombre': 'CTS — Compensación Tiempo Servicios',
        'descripcion': 'Provisión semestral (mayo/noviembre). 1/12 sueldo × meses + 1/6 gratif. Va al banco.',
        'categoria': 'PROVISION', 'tipo': 'INGRESO', 'subtipo': 'PROVISION',
        'formula': 'CTS',
        'codigo_plame': '0904',
    },
}


# ════════════════════════════════════════════════════════════════════════
# Lista de conceptos
# ════════════════════════════════════════════════════════════════════════

def detectar_inconsistencias(concepto):
    """
    Detecta config inconsistente en un concepto. Devuelve lista de warnings.
    Reglas comunes según normativa peruana:
    - NO_REMUNERATIVO no debería afectar ESSALUD/AFP/ONP/CTS/GRA/VAC
    - REMUNERATIVO usualmente afecta ESSALUD + (AFP o ONP)
    - PROVISION (CTS/Gratif) no afecta sí mismo
    """
    warns = []
    no_rem = concepto.subtipo == 'NO_REMUNERATIVO'

    if no_rem:
        if concepto.afecto_essalud:
            warns.append('NO remunerativo afecta ESSALUD — inusual (Art. 19 LRJ)')
        if concepto.afecto_afp:
            warns.append('NO remunerativo afecta AFP — inusual')
        if concepto.afecto_onp:
            warns.append('NO remunerativo afecta ONP — inusual')
        if concepto.afecto_cts:
            warns.append('NO remunerativo afecta CTS — verificar')
        if concepto.afecto_gratif:
            warns.append('NO remunerativo afecta Gratif — verificar')

    if concepto.subtipo == 'REMUNERATIVO' and concepto.tipo == 'INGRESO':
        if not concepto.afecto_essalud and not concepto.es_sistema:
            warns.append('Remunerativo sin ESSALUD — revisar')
        if not concepto.afecto_afp and not concepto.afecto_onp and not concepto.es_sistema:
            warns.append('Remunerativo sin AFP ni ONP — revisar')

    if concepto.codigo_plame == '' and not concepto.es_sistema:
        warns.append('Sin código PLAME — no exportará a SUNAT')

    if concepto.formula == 'FIJO' and concepto.monto_fijo == Decimal('0'):
        warns.append('Fórmula FIJO con monto 0 — revisar')

    return warns


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

    categoria_filter = request.GET.get('categoria', '')
    if categoria_filter:
        conceptos = conceptos.filter(categoria=categoria_filter)

    q = request.GET.get('q', '').strip()
    if q:
        from django.db.models import Q
        conceptos = conceptos.filter(
            Q(nombre__icontains=q) |
            Q(codigo__icontains=q) |
            Q(codigo_plame__icontains=q) |
            Q(descripcion__icontains=q)
        )

    # Anotar inconsistencias (wrappear en dict para que el template las acceda)
    conceptos_list = []
    inconsistencias_count = 0
    for c in conceptos:
        warns = detectar_inconsistencias(c)
        c.warns = warns  # sin underscore prefix (Django template valida)
        c.warns_count = len(warns)
        conceptos_list.append(c)
        if warns:
            inconsistencias_count += 1

    # Stats
    total           = ConceptoRemunerativo.objects.count()
    activos         = ConceptoRemunerativo.objects.filter(activo=True).count()
    sin_plame       = ConceptoRemunerativo.objects.filter(codigo_plame='').count()
    custom          = ConceptoRemunerativo.objects.filter(es_sistema=False).count()

    return render(request, 'nominas/conceptos/lista.html', {
        'conceptos':            conceptos_list,
        'total':                total,
        'activos':              activos,
        'sin_plame':            sin_plame,
        'custom':               custom,
        'inconsistencias':      inconsistencias_count,
        'tipo_filter':          tipo_filter,
        'activo_filter':        activo_filter,
        'categoria_filter':     categoria_filter,
        'q':                    q,
        'tipos':                ConceptoRemunerativo.TIPO_CHOICES,
        'categorias':           ConceptoRemunerativo.CATEGORIA_CHOICES,
    })


# ════════════════════════════════════════════════════════════════════════
# Crear / Editar concepto
# ════════════════════════════════════════════════════════════════════════

def detectar_similares(codigo: str, nombre: str, top_n: int = 5):
    """
    Busca conceptos similares al que se va a crear.

    Heurística:
    1. Match exacto de codigo o nombre normalizado → ALTA confianza
    2. Tokens compartidos en codigo o nombre → MEDIA
    3. Solo el primer token coincide → BAJA

    Returns: lista de dicts {'concepto': obj, 'razon': str, 'confianza': str}
    """
    import re
    codigo_n = (codigo or '').strip().lower().replace(' ', '_')
    nombre_n = (nombre or '').strip().lower()

    if not codigo_n and not nombre_n:
        return []

    def tokens(s):
        return set(t for t in re.split(r'[\s_\-/.,]+', (s or '').lower()) if len(t) >= 3)

    tokens_input = tokens(codigo_n) | tokens(nombre_n)
    if not tokens_input:
        return []

    candidatos = []
    qs = ConceptoRemunerativo.objects.all().values('id', 'codigo', 'nombre', 'tipo', 'activo')
    for c in qs:
        # Match exacto codigo → ya existe
        if c['codigo'] == codigo_n:
            candidatos.append({
                'concepto':  c,
                'razon':     'Ya existe un concepto con este código exacto',
                'confianza': 'EXACTO',
                'score':     100,
            })
            continue

        # Match nombre exacto
        if nombre_n and c['nombre'].lower() == nombre_n:
            candidatos.append({
                'concepto':  c,
                'razon':     'Nombre idéntico al existente',
                'confianza': 'ALTA',
                'score':     90,
            })
            continue

        # Tokens compartidos
        tokens_c = tokens(c['codigo']) | tokens(c['nombre'])
        if not tokens_c:
            continue
        compartidos = tokens_input & tokens_c
        if not compartidos:
            continue
        score = int(100 * len(compartidos) / max(len(tokens_input | tokens_c), 1))
        if score >= 50:
            confianza = 'ALTA'
        elif score >= 30:
            confianza = 'MEDIA'
        elif score >= 15:
            confianza = 'BAJA'
        else:
            continue
        candidatos.append({
            'concepto':  c,
            'razon':     f'Comparte palabras: {", ".join(sorted(compartidos))}',
            'confianza': confianza,
            'score':     score,
        })

    candidatos.sort(key=lambda x: -x['score'])
    return candidatos[:top_n]


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
        # ── Detector de duplicados: si el usuario no confirmó ignorar, advertir ──
        if request.POST.get('ignorar_similares') != '1':
            codigo = (request.POST.get('codigo') or '').strip().lower().replace(' ', '_')
            nombre = (request.POST.get('nombre') or '').strip()
            similares = detectar_similares(codigo, nombre)
            # Solo bloqueamos si hay confianza ALTA/EXACTA — los demás son sugerencias
            blocking = [s for s in similares if s['confianza'] in ('EXACTO', 'ALTA')]
            if blocking:
                return render(request, 'nominas/conceptos/form.html', {
                    'concepto':       None,
                    'form_data':      request.POST,
                    'similares':      similares,
                    'similares_blocking': blocking,
                    'categorias':     ConceptoRemunerativo.CATEGORIA_CHOICES,
                    'tipos':          ConceptoRemunerativo.TIPO_CHOICES,
                    'subtipos':       ConceptoRemunerativo.SUBTIPO_CHOICES,
                    'formulas':       ConceptoRemunerativo.FORMULA_CHOICES,
                })

        _set_audit_from_request(request)
        try:
            concepto, errors = _save_concepto_from_post(request.POST)
        finally:
            clear_audit_context()
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
        _set_audit_from_request(request)
        try:
            c, errors = _save_concepto_from_post(request.POST, concepto)
        finally:
            clear_audit_context()
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

    _set_audit_from_request(request, accion_override='TEMPLATE')
    try:
        ConceptoRemunerativo.objects.create(**t)
    finally:
        clear_audit_context()
    messages.success(request, f'Concepto "{t["nombre"]}" creado.')
    return redirect('conceptos_lista')


# ════════════════════════════════════════════════════════════════════════
# Export / Import CSV
# ════════════════════════════════════════════════════════════════════════

@login_required
def conceptos_export_csv(request):
    """Descarga todos los conceptos como CSV. Migración entre clientes."""
    import csv
    from django.http import HttpResponse

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = 'attachment; filename="conceptos_harmoni.csv"'
    writer = csv.writer(resp)

    writer.writerow([
        'codigo', 'nombre', 'descripcion', 'categoria', 'tipo', 'subtipo',
        'formula', 'monto_fijo', 'porcentaje',
        'afecto_essalud', 'afecto_afp', 'afecto_onp',
        'afecto_renta', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
        'codigo_plame', 'casilla_plame', 'codigo_tregistro',
        'activo', 'orden',
    ])
    for c in ConceptoRemunerativo.objects.all().order_by('tipo', 'orden', 'codigo'):
        writer.writerow([
            c.codigo, c.nombre, c.descripcion, c.categoria, c.tipo, c.subtipo,
            c.formula, c.monto_fijo, c.porcentaje,
            'SI' if c.afecto_essalud else 'NO',
            'SI' if c.afecto_afp else 'NO',
            'SI' if c.afecto_onp else 'NO',
            'SI' if c.afecto_renta else 'NO',
            'SI' if c.afecto_cts else 'NO',
            'SI' if c.afecto_gratif else 'NO',
            'SI' if c.afecto_vacaciones else 'NO',
            c.codigo_plame, c.casilla_plame, c.codigo_tregistro,
            'SI' if c.activo else 'NO', c.orden,
        ])
    return resp


# ════════════════════════════════════════════════════════════════════════
# Auto-fix inconsistencias
# ════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(['POST'])
def concepto_autofix(request, pk):
    """
    Corrige automáticamente afectaciones obvias según subtipo.
    - NO_REMUNERATIVO → desmarca todas las flags de carga
    - REMUNERATIVO + INGRESO → marca ESSALUD + AFP/ONP + IR (sensato)
    """
    c = get_object_or_404(ConceptoRemunerativo, pk=pk)
    cambios = []

    if c.subtipo == 'NO_REMUNERATIVO':
        for f in ('afecto_essalud', 'afecto_afp', 'afecto_onp',
                  'afecto_cts', 'afecto_gratif', 'afecto_vacaciones'):
            if getattr(c, f):
                setattr(c, f, False)
                cambios.append(f)
        # IR depende, lo dejamos como está

    elif c.subtipo == 'REMUNERATIVO' and c.tipo == 'INGRESO':
        # Si no tiene NADA marcado, le ponemos lo mínimo común
        if not any([c.afecto_essalud, c.afecto_afp, c.afecto_onp, c.afecto_cts, c.afecto_gratif]):
            c.afecto_essalud = True
            c.afecto_afp = True
            c.afecto_onp = True
            c.afecto_renta = True
            c.afecto_cts = True
            c.afecto_gratif = True
            c.afecto_vacaciones = True
            cambios = ['todos los flags REM aplicados']

    if cambios:
        _set_audit_from_request(request, accion_override='AUTOFIX')
        try:
            c.save()
        finally:
            clear_audit_context()
        messages.success(request, f'{c.nombre}: {len(cambios)} ajustes aplicados.')
    else:
        messages.info(request, f'{c.nombre}: ya está configurado correctamente.')
    return redirect('conceptos_lista')


# ════════════════════════════════════════════════════════════════════════
# Bulk actions
# ════════════════════════════════════════════════════════════════════════

@login_required
@require_http_methods(['POST'])
def conceptos_bulk_action(request):
    """
    Acciones masivas sobre múltiples conceptos:
    - activar / desactivar
    - aplicar PLAME masivo (todos REM sin PLAME)
    - auto-fix masivo
    """
    ids = request.POST.getlist('concepto_ids')
    accion = request.POST.get('accion', '')

    if not ids:
        messages.warning(request, 'Selecciona al menos un concepto.')
        return redirect('conceptos_lista')

    conceptos = ConceptoRemunerativo.objects.filter(pk__in=ids)
    n = conceptos.count()

    if accion == 'activar':
        _set_audit_from_request(request, accion_override='ACTIVAR')
        try:
            # Iteramos para que signals registren cada cambio (no update masivo)
            for c in conceptos:
                if not c.activo:
                    c.activo = True
                    c.save()
        finally:
            clear_audit_context()
        messages.success(request, f'{n} conceptos activados.')
    elif accion == 'desactivar':
        _set_audit_from_request(request, accion_override='DESACTIVAR')
        try:
            for c in conceptos:
                if c.activo:
                    c.activo = False
                    c.save()
        finally:
            clear_audit_context()
        messages.success(request, f'{n} conceptos desactivados.')
    elif accion == 'autofix':
        fixed = 0
        _set_audit_from_request(request, accion_override='AUTOFIX')
        try:
            for c in conceptos:
                warns_antes = len(detectar_inconsistencias(c))
                if warns_antes > 0:
                    # Aplica auto-fix
                    if c.subtipo == 'NO_REMUNERATIVO':
                        for f in ('afecto_essalud', 'afecto_afp', 'afecto_onp',
                                  'afecto_cts', 'afecto_gratif', 'afecto_vacaciones'):
                            setattr(c, f, False)
                    elif c.subtipo == 'REMUNERATIVO' and c.tipo == 'INGRESO':
                        if not any([c.afecto_essalud, c.afecto_afp, c.afecto_onp]):
                            c.afecto_essalud = True
                            c.afecto_afp = True
                            c.afecto_onp = True
                            c.afecto_renta = True
                            c.afecto_cts = True
                            c.afecto_gratif = True
                    c.save()
                    fixed += 1
        finally:
            clear_audit_context()
        messages.success(request, f'Auto-fix aplicado a {fixed}/{n} conceptos.')
    else:
        messages.error(request, f'Acción no reconocida: {accion}')

    return redirect('conceptos_lista')


# ════════════════════════════════════════════════════════════════════════
# Audit Log — bitácora de cambios
# ════════════════════════════════════════════════════════════════════════

@login_required
def conceptos_audit_log(request):
    """
    Bitácora completa de cambios sobre conceptos remunerativos.

    Filtros: ?codigo=X&accion=UPDATE&usuario=admin&dias=7
    """
    from datetime import timedelta
    from django.utils import timezone

    logs = ConceptoAuditLog.objects.select_related('concepto', 'usuario').order_by('-fecha')

    # Filtros
    codigo = request.GET.get('codigo', '').strip()
    if codigo:
        logs = logs.filter(concepto_codigo__icontains=codigo)

    accion = request.GET.get('accion', '').strip()
    if accion:
        logs = logs.filter(accion=accion)

    usuario_q = request.GET.get('usuario', '').strip()
    if usuario_q:
        logs = logs.filter(usuario_username__icontains=usuario_q)

    dias = request.GET.get('dias', '').strip()
    desde = None
    if dias and dias.isdigit() and int(dias) > 0:
        desde = timezone.now() - timedelta(days=int(dias))
        logs = logs.filter(fecha__gte=desde)

    # Limit defensivo (UX + perf)
    total_filtrados = logs.count()
    logs = logs[:500]

    # Materializar y enriquecer
    rows = []
    for log in logs:
        rows.append({
            'log': log,
            'resumen': log.resumen_cambios[:8],  # top 8 cambios visibles, truncado
            'tiene_mas': log.num_cambios > 8,
            'num_cambios': log.num_cambios,
        })

    # Stats compactas
    from django.db.models import Count
    stats_accion = dict(
        ConceptoAuditLog.objects
        .values_list('accion')
        .annotate(n=Count('id'))
        .values_list('accion', 'n')
    )

    return render(request, 'nominas/conceptos/audit_log.html', {
        'rows': rows,
        'total_filtrados': total_filtrados,
        'showing': len(rows),
        'codigo': codigo,
        'accion': accion,
        'usuario_q': usuario_q,
        'dias': dias,
        'acciones': ConceptoAuditLog.ACCION_CHOICES,
        'stats_accion': stats_accion,
        'total_logs': ConceptoAuditLog.objects.count(),
    })


@login_required
def concepto_historial(request, pk):
    """Historial detallado de UN concepto específico."""
    concepto = get_object_or_404(ConceptoRemunerativo, pk=pk)
    logs = ConceptoAuditLog.objects.filter(
        concepto_codigo=concepto.codigo,
    ).select_related('usuario').order_by('-fecha')

    rows = [{
        'log': log,
        'resumen': log.resumen_cambios,
        'num_cambios': log.num_cambios,
    } for log in logs[:200]]

    return render(request, 'nominas/conceptos/historial.html', {
        'concepto': concepto,
        'rows': rows,
        'total': logs.count(),
    })


@login_required
def conceptos_comparador(request):
    """Compara dos conceptos lado a lado con diff visual.

    URL: /nominas/conceptos/configurar/comparar/?a=<pk>&b=<pk>
    """
    a_pk = request.GET.get('a')
    b_pk = request.GET.get('b')
    a = ConceptoRemunerativo.objects.filter(pk=a_pk).first() if a_pk else None
    b = ConceptoRemunerativo.objects.filter(pk=b_pk).first() if b_pk else None

    # Campos a comparar (orden de presentación)
    CAMPOS_COMPARAR = [
        ('codigo',            'Código'),
        ('nombre',            'Nombre'),
        ('descripcion',       'Descripción'),
        ('categoria',         'Categoría'),
        ('tipo',              'Tipo'),
        ('subtipo',           'Subtipo'),
        ('formula',           'Fórmula'),
        ('porcentaje',        'Porcentaje'),
        ('monto_fijo',        'Monto fijo'),
        ('afecto_essalud',    'Afecto ESSALUD'),
        ('afecto_afp',        'Afecto AFP'),
        ('afecto_onp',        'Afecto ONP'),
        ('afecto_renta',      'Afecto IR 5ta'),
        ('afecto_cts',        'Afecto CTS'),
        ('afecto_gratif',     'Afecto Gratif'),
        ('afecto_vacaciones', 'Afecto Vacaciones'),
        ('codigo_plame',      'Código PLAME'),
        ('casilla_plame',     'Casilla PLAME'),
        ('codigo_tregistro',  'T-Registro'),
        ('activo',            'Activo'),
        ('orden',             'Orden'),
        ('es_sistema',        'Es del sistema'),
    ]

    rows = []
    diff_count = 0
    if a and b:
        for campo, label in CAMPOS_COMPARAR:
            va = getattr(a, campo)
            vb = getattr(b, campo)
            es_diferente = va != vb
            if es_diferente:
                diff_count += 1
            rows.append({
                'campo':       campo,
                'label':       label,
                'a':           va,
                'b':           vb,
                'diferente':   es_diferente,
            })

    # Para selector: lista todos los conceptos
    todos = ConceptoRemunerativo.objects.all().order_by('codigo').values('id', 'codigo', 'nombre')

    return render(request, 'nominas/conceptos/comparador.html', {
        'a':           a,
        'b':           b,
        'rows':        rows,
        'diff_count':  diff_count,
        'total_campos': len(CAMPOS_COMPARAR),
        'todos':       list(todos),
    })


@login_required
def conceptos_audit_log_csv(request):
    """
    Export del audit log a CSV — para auditorías externas o backups.
    Respeta los mismos filtros del view HTML.
    """
    import csv
    from datetime import timedelta
    from django.http import HttpResponse
    from django.utils import timezone as dj_tz

    logs = ConceptoAuditLog.objects.select_related('usuario').order_by('-fecha')

    codigo = request.GET.get('codigo', '').strip()
    if codigo:
        logs = logs.filter(concepto_codigo__icontains=codigo)
    accion = request.GET.get('accion', '').strip()
    if accion:
        logs = logs.filter(accion=accion)
    usuario_q = request.GET.get('usuario', '').strip()
    if usuario_q:
        logs = logs.filter(usuario_username__icontains=usuario_q)
    dias = request.GET.get('dias', '').strip()
    if dias and dias.isdigit() and int(dias) > 0:
        desde = dj_tz.now() - timedelta(days=int(dias))
        logs = logs.filter(fecha__gte=desde)

    resp = HttpResponse(content_type='text/csv; charset=utf-8')
    resp['Content-Disposition'] = (
        f'attachment; filename="audit_conceptos_{dj_tz.now():%Y%m%d_%H%M%S}.csv"'
    )
    writer = csv.writer(resp)
    writer.writerow([
        'fecha', 'accion', 'concepto_codigo', 'concepto_nombre',
        'usuario', 'ip', 'contexto', 'num_cambios', 'cambios_detalle',
    ])

    for log in logs[:5000]:  # cap defensivo: 5k filas máx
        cambios_str = '; '.join(log.resumen_cambios) if log.resumen_cambios else ''
        writer.writerow([
            log.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            log.get_accion_display(),
            log.concepto_codigo,
            log.concepto_nombre,
            log.usuario_username or 'sistema',
            log.ip or '',
            log.contexto or '',
            log.num_cambios,
            cambios_str,
        ])

    return resp
