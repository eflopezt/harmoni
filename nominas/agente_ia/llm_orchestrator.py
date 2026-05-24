"""
Orquestador con LLM real para el agente IA de Nóminas.

Se activa cuando `asistencia.services.ai_service.ia_disponible()` es True.
Si el LLM no está disponible o falla, el llamador (orquestador.procesar_mensaje)
hace fallback al flujo heurístico legacy.

Flujo:
1. Recibe mensaje del usuario + historial previo de la conversación.
2. Envía al LLM con system prompt + historial + tools disponibles.
3. Parsea respuesta JSON del LLM:
   - action="respond" → respuesta final
   - action="call_tool" → ejecuta tool, agrega resultado al historial, vuelve a llamar LLM
4. Loop con `MAX_ITERACIONES` para prevenir bucles infinitos.

El LLM razona SIEMPRE consultando normativa primero (regla en system prompt).
"""
from __future__ import annotations

import json
import logging
import re

from .prompt_llm import SYSTEM_PROMPT, construir_mensajes
from .tools import ejecutar_tool

logger = logging.getLogger('harmoni.ai.nominas')

MAX_ITERACIONES = 5  # tope de tool-calls por turno (protección contra loops)


# ──────────────────────────────────────────────────────────────────────
# Parsing defensivo del JSON que devuelve el LLM
# ──────────────────────────────────────────────────────────────────────

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parsear_respuesta_llm(raw: str) -> dict | None:
    """Intenta extraer un dict {action, ...} de la respuesta del LLM.

    Estrategia tolerante:
    1. JSON parse directo del string.
    2. Si falla, busca dentro de un bloque ```json ... ```.
    3. Si falla, busca el primer { ... } balanceado.
    """
    if not raw:
        return None
    raw = raw.strip()

    # 1) Parse directo
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and 'action' in parsed:
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass

    # 2) Bloque ```json``` o ```
    m = _JSON_FENCE_RE.search(raw)
    if m:
        try:
            parsed = json.loads(m.group(1))
            if isinstance(parsed, dict) and 'action' in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

    # 3) Primer { ... } (greedy hacia el último } cerrado a nivel raíz)
    start = raw.find('{')
    if start >= 0:
        depth = 0
        for i in range(start, len(raw)):
            ch = raw[i]
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(raw[start:i + 1])
                        if isinstance(parsed, dict) and 'action' in parsed:
                            return parsed
                    except json.JSONDecodeError:
                        break

    return None


# ──────────────────────────────────────────────────────────────────────
# Loop principal
# ──────────────────────────────────────────────────────────────────────


def procesar_mensaje_llm(
    conversacion,
    texto_usuario: str,
    usuario=None,
    ip=None,
    ia_service=None,
) -> dict:
    """Procesa un mensaje usando el LLM configurado.

    Args:
        conversacion: ConversacionAgenteIA
        texto_usuario: str con el mensaje del usuario
        usuario: User opcional
        ip: IP del cliente
        ia_service: opcional, IAService (si None, se obtiene de get_service()).
                    Útil para inyectar mock en tests.

    Returns:
        dict con la misma estructura que el orquestador heurístico:
        {'respuesta', 'msg_user_id', 'msg_assistant_id', 'tools_llamadas',
         'intent_detectado', 'modo': 'llm'}

    Raises:
        RuntimeError: si el servicio IA no está disponible. El caller debe
                      atrapar y hacer fallback al modo heurístico.
    """
    from ..models import MensajeAgenteIA, AuditAgenteIA

    if ia_service is None:
        from asistencia.services.ai_service import get_service
        ia_service = get_service()
    if ia_service is None:
        raise RuntimeError('IA service no disponible')

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
        detalle={'mensaje': texto_usuario[:300], 'modo': 'llm'},
        ip=ip,
    )

    # ── 2. Construir historial inicial ──
    historial_db = list(
        MensajeAgenteIA.objects
        .filter(conversacion=conversacion)
        .exclude(pk=msg_user.pk)
        .order_by('fecha')
    )
    messages = construir_mensajes(historial_db, texto_usuario)

    tools_llamadas: list[dict] = []
    respuesta_texto: str | None = None
    msg_assistant = None
    raw_llm = ''

    # ── 3. Loop con cap de iteraciones ──
    for iteracion in range(MAX_ITERACIONES):
        raw_llm = ia_service.chat(messages, system=SYSTEM_PROMPT) or ''
        parsed = _parsear_respuesta_llm(raw_llm)

        if parsed is None:
            # JSON malformado: damos UNA segunda oportunidad pidiendo formato
            logger.warning('LLM devolvió JSON malformado (iter %s). Reintento.', iteracion)
            messages.append({
                'role': 'user',
                'content': (
                    'Respuesta inválida: tu salida no era JSON parseable. '
                    'Devuelve EXCLUSIVAMENTE el JSON con campos `action` '
                    '(\"respond\" o \"call_tool\") y los demás campos según el contrato.'
                ),
            })
            continue

        action = parsed.get('action')

        if action == 'respond':
            respuesta_texto = (parsed.get('message') or '').strip()
            break

        if action == 'call_tool':
            tool_name = parsed.get('tool')
            tool_args = parsed.get('args') or {}
            tool_result = ejecutar_tool(
                tool_name, tool_args,
                context={'usuario': usuario, 'conversacion': conversacion},
            )
            tools_llamadas.append({
                'name': tool_name,
                'args': tool_args,
                'result': tool_result,
            })
            MensajeAgenteIA.objects.create(
                conversacion=conversacion,
                rol='tool',
                contenido=f'Ejecución de {tool_name}',
                tool_name=tool_name,
                tool_args=tool_args,
                tool_result=tool_result,
            )
            AuditAgenteIA.objects.create(
                conversacion=conversacion,
                usuario=usuario,
                accion='TOOL_CALL',
                detalle={'tool': tool_name, 'args_keys': list(tool_args.keys())},
                ip=ip,
            )
            # Realimentar al LLM con el resultado para que continúe el razonamiento
            messages.append({'role': 'assistant', 'content': raw_llm})
            messages.append({
                'role': 'user',
                'content': f'[Resultado de tool {tool_name}]\n{json.dumps(tool_result, ensure_ascii=False, default=str)[:6000]}',
            })
            continue

        # Acción desconocida
        logger.warning('LLM devolvió action desconocida: %r', action)
        messages.append({
            'role': 'user',
            'content': f'Acción "{action}" no reconocida. Usa "respond" o "call_tool".',
        })

    # ── 4. Si llegamos al límite sin respuesta final ──
    if respuesta_texto is None:
        respuesta_texto = (
            'Disculpa, no pude resolver tu consulta dentro del límite de pasos. '
            '¿Puedes reformularla más específica?'
        )

    # ── 5. Guardar respuesta del asistente ──
    msg_assistant = MensajeAgenteIA.objects.create(
        conversacion=conversacion,
        rol='assistant',
        contenido=respuesta_texto,
        modelo=getattr(ia_service, 'provider_name', 'llm'),
    )

    if not conversacion.titulo and texto_usuario:
        conversacion.titulo = texto_usuario[:80]
        conversacion.save(update_fields=['titulo', 'actualizada_en'])

    return {
        'respuesta': respuesta_texto,
        'msg_user_id': msg_user.pk,
        'msg_assistant_id': msg_assistant.pk,
        'tools_llamadas': tools_llamadas,
        'intent_detectado': 'llm',
        'modo': 'llm',
    }
