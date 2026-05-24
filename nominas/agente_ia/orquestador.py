"""
Orquestador del Agente IA — conecta LLM con tools.

Dos modos:

* **LLM real** (`procesar_mensaje_llm` en `llm_orchestrator.py`): cuando
  `ConfiguracionSistema.ia_provider != 'NINGUNO'` y `ia_disponible()` es True.
  El LLM razona, llama tools, cita normativa y propone acciones concretas.

* **Heurística** (este archivo, función `_procesar_heuristico`): fallback
  cuando no hay LLM configurado o disponible. Router por regex de intents.
  Conserva backward-compat de la primera versión del agente.

La función pública `procesar_mensaje` decide el modo automáticamente y, si
el LLM falla en runtime, hace fallback al heurístico para no romper la
experiencia del usuario.

Flujo común (en ambos modos):
1. Mensaje del usuario → `MensajeAgenteIA(rol='user')` + `AuditAgenteIA`
2. Tools ejecutadas → `MensajeAgenteIA(rol='tool')`
3. Respuesta final → `MensajeAgenteIA(rol='assistant')`
"""
import logging
import re
from decimal import Decimal

from .tools import ejecutar_tool

logger = logging.getLogger('harmoni.ai.nominas')


# ──────────────────────────────────────────────────────────────────────
# Heurística simple para enrutar mensajes a tools
# ──────────────────────────────────────────────────────────────────────

# Orden importante: el primero en la lista gana ante empate de matches.
# Casos masivos se evalúan antes del reintegro individual.
INTENTS = [
    {
        'name': 'reintegro_masivo',
        'patterns': [
            r'(olvid[eé]|no pagu[eé]|no pague|falt[oó] pagar|aument[eo]|subir|incrementar)',
            r'(todos|a todos los|al personal|al staff|a todos)',
            r'(sueldo|salario|remuneraci[oó]n)',
        ],
        'tool': 'reintegro_masivo_hint',
    },
    {
        'name': 'consulta_normativa',
        'patterns': [
            r'(cu[aá]ndo|cu[aá]l|qu[eé] es|como funciona|cuando|cual|que es)',
            r'(gratif|cts|afp|onp|essalud|eps|ir 5ta|vacaciones|liquidaci[oó]n|embargo|subsidio|maternidad|incapacidad|asignaci[oó]n familiar|sueldo m[ií]nimo|rmv|uit|reintegro|aumento|retroactivo)',
        ],
        'tool': 'consultar_normativa',
    },
    {
        'name': 'buscar_trabajador',
        'patterns': [
            r'(busca|encuentra|buscar|trabajador|empleado)\s*([a-záéíóúñ\s]+|\d{8})',
        ],
        'tool': 'buscar_trabajador',
    },
    {
        'name': 'reintegro_sueldo',
        'patterns': [
            r'(me equivoqu[eé]|equivocado|paragaron|pagu[eé] de m[aá]s|de menos|recibi[oó]|olvid[eé]|olvide|no pagu[eé]|no pague|falt[oó] pagar|aument[eo]|subir|incrementar)',
            r'(sueldo|remuneraci[oó]n|salario|paga|aumento|incremento)',
            r'(\d{2,5})',
        ],
        'tool': 'calcular_reintegro_sueldo',
    },
]


def _detectar_intent(mensaje: str) -> str:
    """Detecta la intención principal del mensaje."""
    mensaje_l = mensaje.lower()
    matches_por_intent = {}
    for intent in INTENTS:
        count = sum(1 for p in intent['patterns'] if re.search(p, mensaje_l))
        if count > 0:
            matches_por_intent[intent['name']] = (count, intent['tool'])
    if not matches_por_intent:
        return 'general'
    # El de más matches gana
    return max(matches_por_intent.items(), key=lambda x: x[1][0])[0]


def _formatear_normativa_response(resultados: list) -> str:
    """Formatea resultados de RAG en respuesta legible."""
    if not resultados:
        return ('No encontré normativa específica para tu pregunta. ¿Puedes '
                'reformularla o ser más específico? Por ejemplo: "¿Cuándo se '
                'paga la gratificación?" o "¿Cuál es la tasa de ESSALUD?".')

    bloques = []
    for r in resultados:
        bloques.append(
            f"### 📚 {r['titulo']}\n"
            f"_Base legal: {r['base_legal']}_\n\n"
            f"{r['descripcion']}"
        )
    return '\n\n---\n\n'.join(bloques)


def _formatear_reintegro_response(resultado: dict) -> str:
    """Formatea resultado de cálculo de reintegro."""
    if 'error' in resultado:
        return f"⚠ Error: {resultado['error']}"

    if resultado.get('mensaje'):
        return resultado['mensaje']

    fmt = lambda v: f"S/ {v:,.2f}" if isinstance(v, (int, float, Decimal)) else str(v)

    respuesta = f"""\
**Cálculo de reintegro para {resultado['trabajador']}**

Período de origen del error: **{resultado.get('periodo_origen', '?')}**

- Lo que se pagó: **{fmt(resultado.get('sueldo_pagado', 0))}**
- Lo que debió pagarse: **{fmt(resultado.get('sueldo_correcto', 0))}**
- Diferencia a reintegrar (bruto): **{fmt(resultado.get('monto_reintegro', 0))}**

### Impacto fiscal

- Régimen: {resultado.get('regimen', '?')} {'(EPS)' if resultado.get('tiene_eps') else ''}
- Aportes que descuentan al trabajador: {sum(float(v) for v in resultado.get('descuentos', {}).values()):,.2f}
- **Neto a depositar al trabajador: {fmt(resultado.get('monto_neto', 0))}**
- Costo total para la empresa (incluyendo ESSALUD): {fmt(resultado.get('costo_empresa', 0))}

¿Confirmas que cree esta propuesta de reintegro?
"""
    return respuesta


def procesar_mensaje(conversacion, texto_usuario: str, usuario=None, ip=None) -> dict:
    """Procesa un mensaje del usuario.

    Decide entre modo LLM y heurístico:
    1. Si `asistencia.services.ai_service.ia_disponible()` y la importación del
       orquestador LLM funciona → modo LLM.
    2. Si el LLM falla en runtime (excepción) → fallback heurístico + log.
    3. Si no hay LLM configurado → heurístico directo.

    Returns: dict con `respuesta`, `msg_user_id`, `msg_assistant_id`,
    `tools_llamadas`, `intent_detectado`, `modo` ('llm' | 'heuristico').
    """
    # ── Modo LLM ──
    try:
        from asistencia.services.ai_service import ia_disponible
        if ia_disponible():
            from .llm_orchestrator import procesar_mensaje_llm
            return procesar_mensaje_llm(
                conversacion=conversacion,
                texto_usuario=texto_usuario,
                usuario=usuario, ip=ip,
            )
    except Exception:
        logger.exception(
            'LLM orchestrator falló — usando fallback heurístico'
        )

    # ── Modo heurístico (fallback / sin IA configurada) ──
    return _procesar_heuristico(conversacion, texto_usuario, usuario, ip)


def _procesar_heuristico(conversacion, texto_usuario: str, usuario=None, ip=None) -> dict:
    """Implementación legacy basada en regex de intents.

    Se usa como fallback cuando el LLM no está disponible. Garantiza que el
    chat NUNCA se queda sin responder por una falla de infraestructura IA.
    """
    from ..models import MensajeAgenteIA, AuditAgenteIA

    # ── 1. Guardar mensaje del usuario ──
    msg_user = MensajeAgenteIA.objects.create(
        conversacion=conversacion,
        rol='user',
        contenido=texto_usuario,
    )

    AuditAgenteIA.objects.create(
        conversacion=conversacion,
        usuario=usuario,
        accion='CONVERSACION',
        detalle={'mensaje': texto_usuario[:300]},
        ip=ip,
    )

    # ── 2. Detectar intent + ejecutar tool ──
    intent = _detectar_intent(texto_usuario)
    tools_llamadas = []
    respuesta_texto = ''

    if intent == 'consulta_normativa':
        # Extraer la pregunta limpia
        tool_args = {'query': texto_usuario}
        tool_result = ejecutar_tool(
            'consultar_normativa', tool_args,
            context={'usuario': usuario, 'conversacion': conversacion},
        )
        tools_llamadas.append({
            'name':   'consultar_normativa',
            'args':   tool_args,
            'result': tool_result,
        })

        # Guardar tool result como mensaje
        MensajeAgenteIA.objects.create(
            conversacion=conversacion,
            rol='tool',
            contenido='Búsqueda en normativa peruana',
            tool_name='consultar_normativa',
            tool_args=tool_args,
            tool_result=tool_result,
        )

        AuditAgenteIA.objects.create(
            conversacion=conversacion,
            usuario=usuario,
            accion='CONSULTA_NORMATIVA',
            detalle={'query': texto_usuario, 'resultados': len(tool_result.get('resultados', []))},
            ip=ip,
        )

        respuesta_texto = _formatear_normativa_response(tool_result.get('resultados', []))

    elif intent == 'reintegro_masivo':
        # Modo heurístico no puede ejecutar la tool masiva sin parámetros estructurados,
        # pero SÍ puede consultar el RAG y dar una respuesta útil que cite normativa
        # y dirija al usuario a configurar IA para automatizar.
        tool_args = {'query': texto_usuario}
        tool_result = ejecutar_tool('consultar_normativa', tool_args)
        tools_llamadas.append({
            'name': 'consultar_normativa', 'args': tool_args, 'result': tool_result,
        })
        MensajeAgenteIA.objects.create(
            conversacion=conversacion, rol='tool',
            contenido='Búsqueda en normativa peruana',
            tool_name='consultar_normativa',
            tool_args=tool_args, tool_result=tool_result,
        )

        normativa_md = _formatear_normativa_response(tool_result.get('resultados', []))
        respuesta_texto = (
            "**Detecté un caso de reintegro retroactivo masivo** (aumento que olvidaste aplicar "
            "a varios trabajadores, asignación no pagada, etc.).\n\n"
            "Aquí la normativa aplicable:\n\n"
            f"{normativa_md}\n\n"
            "---\n\n"
            "🤖 **Para que yo calcule el impacto automáticamente** (cuántos trabajadores afectados, "
            "bruto, neto, costo empresa) y proponga los registros de reintegro en lote, necesito "
            "que actives la IA en **Configuración → IA**: pega tu API key de Google Gemini "
            "(gratis en https://aistudio.google.com/apikey) o DeepSeek/OpenAI.\n\n"
            "Mientras tanto, podés correr manualmente la herramienta `reintegro_masivo` desde el "
            "shell de Django (también disponible para tu equipo técnico)."
        )

    else:
        # Respuesta general — fallback
        respuesta_texto = (
            "Soy Harmoni IA Nóminas. Puedo ayudarte con:\n\n"
            "**Consultas de normativa peruana:**\n"
            "- _\"¿Cuándo se paga la gratificación?\"_\n"
            "- _\"¿Cuál es el tope del embargo?\"_\n"
            "- _\"¿Cómo funciona la EPS?\"_\n\n"
            "**Cálculos de reintegros:**\n"
            "- _\"Le pagué S/2500 a Juan cuando era S/3000 en abril, calcula el reintegro\"_\n"
            "- _\"No le pagué la asignación familiar a María por 3 meses\"_\n"
            "- _\"Tiene 5 horas extra pendientes del mes pasado\"_\n"
            "- _\"Olvidé aumentar S/200 a todos el mes pasado\"_ (caso masivo)\n\n"
            "**Datos de planilla:**\n"
            "- _\"Muéstrame la boleta de Pedro de marzo 2026\"_\n"
            "- _\"Lista los reintegros pendientes\"_\n\n"
            "💡 Para razonamiento avanzado con citas normativas y propuestas automáticas, "
            "activa tu API key en **Configuración → IA**.\n\n"
            "¿En qué te ayudo?"
        )

    # ── 3. Guardar respuesta del asistente ──
    msg_assistant = MensajeAgenteIA.objects.create(
        conversacion=conversacion,
        rol='assistant',
        contenido=respuesta_texto,
        modelo='harmoni-rules-v1',  # placeholder hasta integrar LLM real
    )

    # Actualizar título de la conversación si está vacío
    if not conversacion.titulo and texto_usuario:
        conversacion.titulo = texto_usuario[:80]
        conversacion.save(update_fields=['titulo', 'actualizada_en'])

    return {
        'respuesta':         respuesta_texto,
        'msg_user_id':       msg_user.pk,
        'msg_assistant_id':  msg_assistant.pk,
        'tools_llamadas':    tools_llamadas,
        'intent_detectado':  intent,
        'modo':              'heuristico',
    }
