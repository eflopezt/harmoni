"""
Tools del Agente IA Nóminas — function calling.

Cada tool tiene:
1. Una definición JSON-schema (para enviar al LLM como tool definitions)
2. Una función Python que el orquestador invoca cuando el LLM la pide

Diseño defensivo:
- NUNCA modifica la DB directamente sin pasar por estado PROPUESTO
- Toda operación queda en AuditAgenteIA
- Errores devuelven dict con 'error' (no levantan excepciones — el LLM las maneja)
"""
from decimal import Decimal
from datetime import date


# ════════════════════════════════════════════════════════════════════════
# DEFINICIONES (JSON Schema) — esto se envía al LLM como tools disponibles
# ════════════════════════════════════════════════════════════════════════

TOOL_DEFINITIONS = [
    {
        'name': 'consultar_normativa',
        'description': (
            'Busca en la normativa laboral peruana. Útil cuando el usuario pregunta '
            'sobre leyes, decretos, tasas, plazos, derechos. Ejemplos: "¿Cuándo se '
            'paga la gratificación?", "¿Cuál es el tope de embargo?".'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'Pregunta en lenguaje natural sobre normativa laboral peruana.',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'buscar_trabajador',
        'description': (
            'Busca un trabajador por DNI, nombres o apellidos. Devuelve datos '
            'básicos (ID, nombre, sueldo, régimen). Úsalo SIEMPRE antes de '
            'cualquier operación sobre un trabajador específico.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {
                    'type': 'string',
                    'description': 'DNI (8 dígitos) o nombre/apellido a buscar.',
                },
            },
            'required': ['query'],
        },
    },
    {
        'name': 'obtener_boleta',
        'description': (
            'Lee la boleta histórica de un trabajador en un período específico. '
            'Devuelve sueldo base pagado, conceptos aplicados, montos brutos/netos.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer', 'description': 'ID del trabajador (obtenido de buscar_trabajador).'},
                'anio': {'type': 'integer', 'description': 'Año del período (ej: 2026).'},
                'mes': {'type': 'integer', 'description': 'Mes del período (1-12).'},
            },
            'required': ['personal_id', 'anio', 'mes'],
        },
    },
    {
        'name': 'calcular_reintegro_sueldo',
        'description': (
            'Calcula el reintegro por error en sueldo base. Devuelve la '
            'diferencia bruta + impacto fiscal (AFP/ONP/ESSALUD/IR) + neto.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer'},
                'sueldo_pagado': {'type': 'number', 'description': 'Lo que se pagó (S/).'},
                'sueldo_correcto': {'type': 'number', 'description': 'Lo que debió pagarse (S/).'},
                'periodo_origen_anio': {'type': 'integer'},
                'periodo_origen_mes': {'type': 'integer'},
            },
            'required': ['personal_id', 'sueldo_pagado', 'sueldo_correcto', 'periodo_origen_anio', 'periodo_origen_mes'],
        },
    },
    {
        'name': 'calcular_reintegro_he',
        'description': 'Calcula reintegro por horas extra no pagadas en período anterior.',
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer'},
                'horas': {'type': 'number'},
                'tipo_he': {'type': 'string', 'enum': ['HE_25', 'HE_35', 'HE_100']},
                'periodo_origen_anio': {'type': 'integer'},
                'periodo_origen_mes': {'type': 'integer'},
            },
            'required': ['personal_id', 'horas', 'tipo_he', 'periodo_origen_anio', 'periodo_origen_mes'],
        },
    },
    {
        'name': 'calcular_reintegro_asignacion_familiar',
        'description': 'Calcula reintegro por asignación familiar omitida X meses.',
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer'},
                'meses_pendientes': {'type': 'integer'},
                'periodo_origen_anio': {'type': 'integer'},
                'periodo_origen_mes_inicio': {'type': 'integer'},
            },
            'required': ['personal_id', 'meses_pendientes', 'periodo_origen_anio', 'periodo_origen_mes_inicio'],
        },
    },
    {
        'name': 'proponer_reintegro',
        'description': (
            'Crea una propuesta de reintegro en estado PROPUESTO. '
            'NO la aplica todavía — el admin debe aprobarla después. '
            'Devuelve el ID del reintegro propuesto.'
        ),
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer'},
                'motivo': {
                    'type': 'string',
                    'enum': [
                        'ERROR_SUELDO', 'AUMENTO_RETROACTIVO', 'HE_NO_PAGADAS',
                        'ASIG_FAMILIAR_OMITIDA', 'BONIF_OMITIDA', 'GRATIF_MAL_CALCULADA',
                        'SENTENCIA_JUDICIAL', 'OTRO',
                    ],
                },
                'descripcion': {'type': 'string'},
                'periodo_origen_anio': {'type': 'integer'},
                'periodo_origen_mes': {'type': 'integer'},
                'monto_que_se_pago': {'type': 'number'},
                'monto_correcto': {'type': 'number'},
            },
            'required': [
                'personal_id', 'motivo', 'descripcion',
                'periodo_origen_anio', 'periodo_origen_mes',
                'monto_que_se_pago', 'monto_correcto',
            ],
        },
    },
    {
        'name': 'listar_reintegros_pendientes',
        'description': 'Lista reintegros en estado PROPUESTO o APROBADO (no aplicados aún).',
        'parameters': {
            'type': 'object',
            'properties': {
                'personal_id': {'type': 'integer', 'description': 'Opcional — filtrar por trabajador.'},
            },
        },
    },
]


# ════════════════════════════════════════════════════════════════════════
# IMPLEMENTACIONES — ejecutadas cuando el LLM llama una tool
# ════════════════════════════════════════════════════════════════════════

def _redondear_dict(d):
    """Convierte Decimals a float (con 2 decimales) para JSON-safe."""
    out = {}
    for k, v in d.items():
        if isinstance(v, Decimal):
            out[k] = float(v.quantize(Decimal('0.01')))
        elif isinstance(v, dict):
            out[k] = _redondear_dict(v)
        elif isinstance(v, date):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


def tool_buscar_trabajador(query: str):
    """Busca trabajador por DNI o nombre."""
    from personal.models import Personal
    from django.db.models import Q

    q = (query or '').strip()
    if not q:
        return {'error': 'Query vacía. Provee DNI o nombre.'}

    qs = Personal.objects.filter(
        Q(nro_doc__icontains=q) | Q(apellidos_nombres__icontains=q),
    )[:5]

    if not qs.exists():
        return {'error': f'No se encontró trabajador con "{q}".'}

    return {
        'encontrados': [
            {
                'id':              p.id,
                'dni':             p.nro_doc,
                'nombre':          p.apellidos_nombres,
                'cargo':           getattr(p, 'cargo', ''),
                'sueldo_base':     float(p.sueldo_base or 0),
                'regimen_pension': getattr(p, 'regimen_pension', ''),
                'asignacion_familiar': bool(getattr(p, 'asignacion_familiar', False)),
                'tiene_eps':       bool(getattr(p, 'tiene_eps', False)),
                'fecha_alta':      p.fecha_alta.isoformat() if p.fecha_alta else None,
            }
            for p in qs
        ],
        'total': qs.count(),
    }


def tool_obtener_boleta(personal_id: int, anio: int, mes: int):
    """Devuelve la boleta histórica de un trabajador en un período."""
    from ..models import PeriodoNomina, RegistroNomina

    periodo = PeriodoNomina.objects.filter(
        tipo='REGULAR', anio=anio, mes=mes,
    ).first()
    if not periodo:
        return {'error': f'No hay período REGULAR para {mes:02d}/{anio}.'}

    registro = RegistroNomina.objects.filter(
        periodo=periodo, personal_id=personal_id,
    ).first()
    if not registro:
        return {'error': f'Trabajador {personal_id} no figura en planilla {mes:02d}/{anio}.'}

    return {
        'trabajador': str(registro.personal),
        'periodo':    f'{mes:02d}/{anio}',
        'estado_periodo': periodo.estado,
        'sueldo_base':     float(registro.sueldo_base or 0),
        'total_ingresos':  float(registro.total_ingresos or 0),
        'total_descuentos': float(registro.total_descuentos or 0),
        'neto_a_pagar':    float(registro.neto_a_pagar or 0),
        'aporte_essalud':  float(getattr(registro, 'aporte_essalud', 0) or 0),
    }


def tool_calcular_reintegro_sueldo(personal_id: int, sueldo_pagado: float,
                                    sueldo_correcto: float, periodo_origen_anio: int,
                                    periodo_origen_mes: int):
    """Calcula el reintegro completo por error de sueldo."""
    from personal.models import Personal
    from ..engine_reintegros import (
        calcular_diferencia_sueldo,
        calcular_impacto_total_reintegro,
    )

    p = Personal.objects.filter(pk=personal_id).first()
    if not p:
        return {'error': f'Trabajador {personal_id} no existe.'}

    diff = calcular_diferencia_sueldo(Decimal(str(sueldo_pagado)), Decimal(str(sueldo_correcto)))
    if not diff['es_relevante']:
        return {
            'mensaje': 'La diferencia es menor a S/0.01 — sin reintegro necesario.',
            'diferencia': float(diff['diferencia']),
        }

    impacto = calcular_impacto_total_reintegro(
        monto_reintegro=diff['diferencia'],
        personal=p,
    )

    return _redondear_dict({
        'trabajador':         str(p),
        'periodo_origen':     f'{periodo_origen_mes:02d}/{periodo_origen_anio}',
        'sueldo_pagado':      diff['sueldo_pagado'],
        'sueldo_correcto':    diff['sueldo_correcto'],
        'monto_reintegro':    impacto['monto_reintegro'],
        'monto_neto':         impacto['monto_neto_reintegro'],
        'costo_empresa':      impacto['costo_empresa_total'],
        'impacto_ir_5ta':     impacto['impacto_ir_5ta'],
        'descuentos':         impacto['impacto_aportes'],
        'regimen':            impacto['regimen'],
        'tiene_eps':          impacto['tiene_eps'],
        'tipo':               diff['tipo'],
    })


def tool_calcular_reintegro_he(personal_id: int, horas: float, tipo_he: str,
                                periodo_origen_anio: int, periodo_origen_mes: int):
    """Calcula reintegro por horas extra no pagadas."""
    from personal.models import Personal
    from ..engine_reintegros import (
        calcular_reintegro_he_no_pagadas,
        calcular_impacto_total_reintegro,
    )

    p = Personal.objects.filter(pk=personal_id).first()
    if not p:
        return {'error': f'Trabajador {personal_id} no existe.'}

    he = calcular_reintegro_he_no_pagadas(
        horas_extra_no_pagadas=Decimal(str(horas)),
        sueldo_mensual=p.sueldo_base or Decimal('0'),
        tipo_he=tipo_he,
    )
    impacto = calcular_impacto_total_reintegro(
        monto_reintegro=he['monto'], personal=p,
    )

    return _redondear_dict({
        'trabajador':       str(p),
        'periodo_origen':   f'{periodo_origen_mes:02d}/{periodo_origen_anio}',
        'horas':            he['horas'],
        'tipo_he':          tipo_he,
        'monto_bruto':      he['monto'],
        'monto_neto':       impacto['monto_neto_reintegro'],
        'costo_empresa':    impacto['costo_empresa_total'],
        'descripcion':      he['descripcion'],
    })


def tool_calcular_reintegro_asignacion_familiar(personal_id: int, meses_pendientes: int,
                                                  periodo_origen_anio: int,
                                                  periodo_origen_mes_inicio: int):
    """Calcula reintegro por asignación familiar omitida."""
    from personal.models import Personal
    from ..engine_reintegros import (
        calcular_reintegro_asignacion_familiar,
        calcular_impacto_total_reintegro,
    )
    from ..engine import ASIG_FAM

    p = Personal.objects.filter(pk=personal_id).first()
    if not p:
        return {'error': f'Trabajador {personal_id} no existe.'}

    asig = calcular_reintegro_asignacion_familiar(meses_pendientes, ASIG_FAM)
    impacto = calcular_impacto_total_reintegro(
        monto_reintegro=asig['monto_total'], personal=p,
    )

    return _redondear_dict({
        'trabajador':            str(p),
        'periodo_origen_inicio': f'{periodo_origen_mes_inicio:02d}/{periodo_origen_anio}',
        'meses_pendientes':      asig['meses_pendientes'],
        'asig_fam_mensual':      asig['monto_mensual'],
        'monto_bruto':           asig['monto_total'],
        'monto_neto':            impacto['monto_neto_reintegro'],
        'costo_empresa':         impacto['costo_empresa_total'],
        'descripcion':           asig['descripcion'],
    })


def tool_proponer_reintegro(personal_id: int, motivo: str, descripcion: str,
                              periodo_origen_anio: int, periodo_origen_mes: int,
                              monto_que_se_pago: float, monto_correcto: float,
                              _context=None):
    """
    Crea un ReintegroNomina en estado PROPUESTO.

    No aplica todavía — el admin debe aprobarlo en la UI.
    """
    from personal.models import Personal
    from ..models import ReintegroNomina
    from ..engine_reintegros import calcular_impacto_total_reintegro

    p = Personal.objects.filter(pk=personal_id).first()
    if not p:
        return {'error': f'Trabajador {personal_id} no existe.'}

    diferencia = Decimal(str(monto_correcto)) - Decimal(str(monto_que_se_pago))
    impacto = calcular_impacto_total_reintegro(
        monto_reintegro=diferencia, personal=p,
    )

    # Empresa del trabajador (multi-tenant)
    empresa = getattr(p, 'empresa', None)
    if not empresa:
        try:
            from empresas.models import Empresa
            empresa = Empresa.objects.first()
        except Exception:
            empresa = None

    # Contexto (conversación + usuario) — viene del orquestador
    ctx = _context or {}
    usuario = ctx.get('usuario')
    conversacion = ctx.get('conversacion')

    # Convertir impacto_aportes (Decimal → str para JSON)
    impacto_aportes_serializable = {
        k: str(v) for k, v in impacto['impacto_aportes'].items()
    }

    reintegro = ReintegroNomina.objects.create(
        personal=p,
        empresa=empresa,
        motivo=motivo,
        descripcion=descripcion,
        periodo_origen_anio=periodo_origen_anio,
        periodo_origen_mes=periodo_origen_mes,
        monto_que_se_pago=Decimal(str(monto_que_se_pago)),
        monto_correcto=Decimal(str(monto_correcto)),
        monto_reintegro=diferencia,
        impacto_ir_5ta=impacto['impacto_ir_5ta'],
        impacto_aportes=impacto_aportes_serializable,
        monto_neto_reintegro=impacto['monto_neto_reintegro'],
        estado='PROPUESTO',
        propuesto_por=usuario,
        propuesto_por_ia=True,
        conversacion_ia=conversacion,
    )

    return _redondear_dict({
        'reintegro_id':       reintegro.pk,
        'estado':             reintegro.estado,
        'trabajador':         str(p),
        'periodo_origen':     reintegro.periodo_origen_str,
        'monto_reintegro':    reintegro.monto_reintegro,
        'monto_neto':         reintegro.monto_neto_reintegro,
        'requiere_aprobacion': True,
        'url_aprobacion':     f'/nominas/reintegros/{reintegro.pk}/',
        'mensaje':            f'Propuesta creada (ID #{reintegro.pk}). Pendiente de aprobación.',
    })


def tool_listar_reintegros_pendientes(personal_id: int = None):
    """Lista reintegros PROPUESTOS o APROBADOS no aplicados."""
    from ..models import ReintegroNomina

    qs = ReintegroNomina.objects.filter(
        estado__in=['PROPUESTO', 'APROBADO'],
    ).select_related('personal')
    if personal_id:
        qs = qs.filter(personal_id=personal_id)

    return {
        'reintegros': [
            {
                'id':            r.pk,
                'trabajador':    str(r.personal),
                'motivo':        r.get_motivo_display(),
                'periodo_origen': r.periodo_origen_str,
                'monto':         float(r.monto_reintegro),
                'estado':        r.estado,
                'creado':        r.creado_en.isoformat(),
            }
            for r in qs[:30]
        ],
        'total': qs.count(),
    }


def tool_consultar_normativa(query: str):
    """RAG search sobre normativa peruana (versión simple, sin embeddings aún)."""
    from .rag import buscar_normativa
    resultados = buscar_normativa(query, top_k=3)
    return {
        'query':       query,
        'resultados':  resultados,
        'fuente':      'Knowledge base normativa peruana — Harmoni IA',
    }


# ════════════════════════════════════════════════════════════════════════
# DISPATCHER — el orquestador llama esta función con el name + args del LLM
# ════════════════════════════════════════════════════════════════════════

TOOL_IMPLEMENTATIONS = {
    'consultar_normativa':                   tool_consultar_normativa,
    'buscar_trabajador':                     tool_buscar_trabajador,
    'obtener_boleta':                        tool_obtener_boleta,
    'calcular_reintegro_sueldo':             tool_calcular_reintegro_sueldo,
    'calcular_reintegro_he':                 tool_calcular_reintegro_he,
    'calcular_reintegro_asignacion_familiar': tool_calcular_reintegro_asignacion_familiar,
    'proponer_reintegro':                    tool_proponer_reintegro,
    'listar_reintegros_pendientes':          tool_listar_reintegros_pendientes,
}


def ejecutar_tool(name: str, args: dict, context: dict = None):
    """
    Dispatcher central. Llamado por el orquestador del agente cuando el LLM
    pide ejecutar una tool.

    Returns:
        dict — siempre devuelve un dict serializable (nunca raises).
    """
    fn = TOOL_IMPLEMENTATIONS.get(name)
    if not fn:
        return {'error': f'Tool desconocida: {name}'}

    try:
        # proponer_reintegro necesita contexto (usuario, conversación)
        if name == 'proponer_reintegro':
            args = dict(args or {})
            args['_context'] = context or {}
        return fn(**(args or {}))
    except TypeError as e:
        return {'error': f'Argumentos inválidos: {e}'}
    except Exception as e:
        return {'error': f'Error al ejecutar {name}: {e}'}
