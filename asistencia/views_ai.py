"""
Vistas para el asistente IA de Harmoni.

Endpoints:
  POST /asistencia/ia/chat/     → Chat streaming (SSE) — con fallback sin IA
  GET  /asistencia/ia/status/   → Estado de conexión IA
  GET  /asistencia/ia/context/  → Datos del sistema (JSON)
  GET  /asistencia/ia/insights/ → Insights generados por IA
  POST /asistencia/ia/analizar/ → Análisis de gráfico (SSE)
  POST /asistencia/ia/preguntar/→ Pregunta libre (SSE)
"""
from __future__ import annotations

import json
import logging
import time

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.http import require_GET, require_POST

from .services.ai_service import get_service
from .services.ai_context import (
    build_system_prompt,
    build_system_prompt_data,
    build_insights_prompt,
    detect_chart_request,
    detect_dashboard_request,
    detect_export_request,
    detect_module_context,
    generate_chart_data,
    generate_dashboard_data,
    responder_sin_ia,
)

logger = logging.getLogger('harmoni.ai')


def _sse_text(text: str) -> str:
    """
    Formatea texto multilinea para SSE.
    En SSE cada línea del mensaje debe tener su propio 'data:' prefix.
    Newlines dentro del texto rompen el mensaje si no se manejan.
    Solución: reemplazar \\n por un marcador que el JS puede reconvertir.
    """
    # Reemplazar newlines reales por \\n literal para que SSE no se rompa
    return text.replace('\n', '\\n')

# Cache de conectividad IA (evita test_connection en cada request)
_ia_cache: dict = {'ok': None, 'ts': 0}
_IA_CACHE_TTL = 30  # segundos


def _is_ollama_reachable() -> bool:
    """
    Verifica conectividad con el proveedor IA configurado, con cache de 30s.
    Nombre mantenido por compatibilidad; funciona con cualquier provider.
    """
    now = time.time()
    if now - _ia_cache['ts'] < _IA_CACHE_TTL and _ia_cache['ok'] is not None:
        return _ia_cache['ok']

    svc = get_service()
    if svc is None:
        _ia_cache.update(ok=False, ts=now)
        return False

    try:
        result = svc.test_connection()
        # Solo chequeamos 'ok' — 'modelo_activo' es exclusivo de OllamaService
        ok = result.get('ok', False)
    except Exception:
        ok = False

    _ia_cache.update(ok=ok, ts=now)
    return ok


# ─────────────────────────────────────────────────
# ESTADO DE IA
# ─────────────────────────────────────────────────

@login_required
@require_GET
def ai_status(request):
    """
    Verifica si la IA está disponible.
    El frontend usa esto para mostrar/ocultar el widget de chat.
    Usa cache de conectividad para evitar test_connection en cada page load.
    """
    ollama_ok = _is_ollama_reachable()
    svc = get_service()

    if svc is None or not ollama_ok:
        return JsonResponse({
            'available': True,
            'provider': 'FALLBACK',
            'model': None,
            'fallback': True,
        })

    return JsonResponse({
        'available': True,
        'provider': getattr(svc, 'provider_name', 'IA'),
        'model': getattr(svc, 'modelo', None),
        'fallback': False,
    })


# ─────────────────────────────────────────────────
# CONTEXTO DEL SISTEMA (datos sin IA)
# ─────────────────────────────────────────────────

@login_required
@require_GET
def ai_context(request):
    """
    Retorna datos factuales del sistema como JSON.
    No requiere Ollama — responde con datos de la BD directamente.
    """
    data = build_system_prompt_data(request.user)
    return JsonResponse(data)


# ─────────────────────────────────────────────────
# CHAT STREAMING (SSE) — con fallback
# ─────────────────────────────────────────────────

@login_required
@require_POST
def ai_chat_stream(request):
    """
    Chat con streaming via Server-Sent Events.
    Body JSON: {"message": "...", "history": [...]}

    Si Ollama no está disponible, intenta responder directamente
    con datos de la BD (fallback sin IA).
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    message = body.get('message', '').strip()
    if not message:
        return JsonResponse({'error': 'Mensaje vacío'}, status=400)

    history = body.get('history', [])

    svc = get_service()
    ollama_ok = _is_ollama_reachable()

    # ── Detectar export request (antes de todo) ──
    export_req = detect_export_request(message)
    if export_req:
        def export_stream():
            yield 'data: [FALLBACK]\n\n'
            resp_text = (
                '📊 He preparado tu **Reporte Ejecutivo** de RRHH. '
                'Haz clic para descargarlo:\\n\\n'
                f'[DOWNLOAD:{export_req["type"]}]'
            )
            yield f'data: {resp_text}\n\n'
            yield 'data: [DONE]\n\n'

        response = StreamingHttpResponse(
            export_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    # ── Detectar dashboard multi-gráfico ──
    dashboard_req = detect_dashboard_request(message)
    if dashboard_req:
        dashboard = generate_dashboard_data(request.user)
        if dashboard and dashboard.get('charts'):
            def dashboard_stream():
                yield 'data: [FALLBACK]\n\n'
                yield 'data: [MAXIMIZE]\n\n'
                for chart in dashboard['charts']:
                    chart_json = json.dumps(chart, ensure_ascii=False)
                    yield f'data: [CHART]{chart_json}[/CHART]\n\n'
                # Summary text
                summary = (
                    f'📊 **{dashboard["title"]}** — '
                    f'{len(dashboard["charts"])} indicadores clave. '
                    f'Usa el botón de maximizar para ver los gráficos en detalle.'
                )
                yield f'data: {_sse_text(summary)}\n\n'
                yield 'data: [DONE]\n\n'

            response = StreamingHttpResponse(
                dashboard_stream(), content_type='text/event-stream')
            response['Cache-Control'] = 'no-cache'
            response['X-Accel-Buffering'] = 'no'
            return response

    # ── Fallback sin IA si Ollama no está disponible ──
    if not ollama_ok:
        # Charts también funcionan sin Ollama (datos vienen de BD)
        chart_req = detect_chart_request(message)
        chart_data = None
        if chart_req:
            chart_data = generate_chart_data(
                chart_req['type'], request.user, message,
            )

        fallback = responder_sin_ia(message, request.user)

        def fallback_stream():
            yield 'data: [FALLBACK]\n\n'
            if chart_data:
                chart_json = json.dumps(chart_data, ensure_ascii=False)
                yield f'data: [CHART]{chart_json}[/CHART]\n\n'
                # Breve análisis estático del chart
                total = sum(chart_data.get('values', []))
                if total:
                    top = max(
                        zip(chart_data.get('labels', []),
                            chart_data.get('values', [])),
                        key=lambda x: x[1],
                    )
                    analysis = (
                        f'**{chart_data.get("title", "Gráfico")}** — '
                        f'Total: {total}. '
                        f'Mayor: {top[0]} con {top[1]} '
                        f'({top[1] * 100 // total}%).'
                    )
                    yield f'data: {_sse_text(analysis)}\n\n'
            elif fallback:
                yield f'data: {_sse_text(fallback)}\n\n'
            else:
                no_match = (
                    'No tengo suficiente informacion para responder '
                    'esa consulta directamente. Prueba con preguntas como:\n'
                    '- "¿Cuántos empleados activos hay?"\n'
                    '- "¿Hay aprobaciones pendientes?"\n'
                    '- "¿Cómo va la asistencia hoy?"\n'
                    '- "Muéstrame un gráfico del personal por área"\n\n'
                    'Para consultas más complejas, configura un proveedor IA en '
                    '**Asistencia > Configuración > Pestaña IA**.'
                )
                yield f'data: {_sse_text(no_match)}\n\n'
            yield 'data: [DONE]\n\n'

        response = StreamingHttpResponse(
            fallback_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    # ── Detectar si pide un gráfico ──
    chart_req = detect_chart_request(message)
    chart_data = None
    if chart_req:
        chart_data = generate_chart_data(
            chart_req['type'], request.user, message,
        )

    # ── Lazy loading: detectar módulos relevantes ──
    modules = detect_module_context(message)
    system_prompt = build_system_prompt(request.user, modules=modules)

    # Limitar historial a los últimos 10 turnos
    messages = []
    for msg in history[-10:]:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        if role in ('user', 'assistant') and content:
            messages.append({'role': role, 'content': content})

    # Si hay chart data, enriquecer el prompt para que el LLM analice
    ai_message = message
    if chart_data:
        total = sum(chart_data['values'])
        if total > 0:
            parts = [
                f'{l}: {v} ({v * 100 // total}%)'
                for l, v in zip(chart_data['labels'], chart_data['values'])
            ]
            data_summary = ', '.join(parts)
        else:
            data_summary = 'Sin datos'
        ai_message = (
            f'El usuario pidio un grafico y YA se lo estoy mostrando visualmente. '
            f'Tu solo necesitas dar un breve analisis en texto (3-4 lineas). '
            f'Los datos reales son: {data_summary}. Total: {total}. '
            f'Analiza brevemente que significan estos numeros para RRHH.'
        )

    messages.append({'role': 'user', 'content': ai_message})

    def event_stream():
        try:
            # Si hay chart, enviar marcador PRIMERO
            if chart_data:
                chart_json = json.dumps(chart_data, ensure_ascii=False)
                yield f'data: [CHART]{chart_json}[/CHART]\n\n'

            for chunk in svc.chat_stream(
                messages=messages,
                system=system_prompt,
                temperature=0.35,
                num_predict=900,
            ):
                yield f'data: {chunk}\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            logger.warning(f'ai_chat_stream error: {e}')
            # Intentar fallback en caso de error de streaming
            fallback = responder_sin_ia(message, request.user)
            if fallback:
                yield 'data: [FALLBACK]\n\n'
                yield f'data: {_sse_text(fallback)}\n\n'
            else:
                yield 'data: _Error de conexión con IA._\n\n'
            yield 'data: [DONE]\n\n'

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ─────────────────────────────────────────────────
# INSIGHTS IA (para dashboard home)
# ─────────────────────────────────────────────────

@login_required
@require_GET
def ai_insights(request):
    """
    Genera insights IA basados en KPIs actuales.
    Cachea resultado por 6 horas para performance.
    Si Ollama no está disponible, genera insights estáticos básicos.
    """
    from django.core.cache import cache
    from datetime import date

    cache_key = f'harmoni_ai_insights_{request.user.id}_{date.today().isoformat()}'
    force = request.GET.get('force', '') == '1'

    if not force:
        cached = cache.get(cache_key)
        if cached:
            return JsonResponse({'insights': cached, 'cached': True})

    ollama_ok = _is_ollama_reachable()

    if not ollama_ok:
        # Insights estáticos básicos sin IA
        data = build_system_prompt_data(request.user)
        insights = _build_static_insights(data)
        if insights:
            cache.set(cache_key, insights, timeout=3600)  # 1h para estáticos
            return JsonResponse({
                'insights': insights, 'cached': False, 'fallback': True,
            })
        return JsonResponse({'insights': None, 'error': 'IA no disponible'})

    svc = get_service()
    if svc is None:
        return JsonResponse({'insights': None, 'error': 'IA no disponible'})

    system, user_prompt = build_insights_prompt(request.user)

    try:
        result = svc.generate(
            prompt=user_prompt,
            system=system,
        )
        if result:
            cache.set(cache_key, result, timeout=3600 * 6)
            return JsonResponse({'insights': result, 'cached': False})
        else:
            return JsonResponse({'insights': None, 'error': 'Sin respuesta de IA'})
    except Exception as e:
        logger.warning(f'ai_insights error: {e}')
        return JsonResponse({'insights': None, 'error': str(e)})


def _build_static_insights(data: dict) -> str | None:
    """Genera insights básicos sin IA, basados en reglas simples."""
    lines = []

    total = data.get('total_personal', 0)
    if total:
        lines.append(f'- Plantilla actual: {total} empleados activos '
                      f'({data.get("total_staff", 0)} STAFF, '
                      f'{data.get("total_rco", 0)} RCO)')

    pend = data.get('total_pendientes', 0)
    if pend:
        lines.append(f'- ⚠ Hay {pend} aprobaciones pendientes que requieren atención')

    vencer = data.get('contratos_por_vencer', 0)
    if vencer:
        lines.append(f'- ⚠ {vencer} contratos vencen en los próximos 30 días')

    faltas = data.get('asistencia_faltas', 0)
    if faltas:
        lines.append(f'- Hoy: {faltas} faltas registradas')

    vac_pend = data.get('vacaciones_pendientes', 0)
    if vac_pend:
        lines.append(f'- {vac_pend} solicitudes de vacaciones pendientes')

    cert_venc = data.get('certificaciones_vencidas', 0)
    if cert_venc:
        lines.append(f'- ⚠ {cert_venc} certificaciones vencidas')

    disc = data.get('disciplinaria_en_descargo', 0)
    if disc:
        lines.append(f'- {disc} procesos disciplinarios en descargo')

    if data.get('kpi_rotacion') is not None:
        rot = data['kpi_rotacion']
        if rot > 5:
            lines.append(f'- ⚠ Rotación {rot:.1f}% — por encima del benchmark')
        else:
            lines.append(f'- ✓ Rotación {rot:.1f}% — dentro de rangos saludables')

    if not lines:
        return None

    return '\n'.join(lines)


def _static_chart_analysis(chart_type: str, chart_data: dict) -> str:
    """Genera análisis estático básico de un gráfico sin usar IA."""
    data = chart_data if isinstance(chart_data, dict) else {}
    items = list(zip(
        data.get('labels', []),
        data.get('values', []),
    ))
    if not items:
        return '_Sin datos suficientes para análisis._'

    total = sum(v for _, v in items)
    if total == 0:
        return '_Sin datos registrados en el período._'

    top = max(items, key=lambda x: x[1])
    bottom = min(items, key=lambda x: x[1])

    analysis_map = {
        'headcount': (
            f'**Headcount**: rango de {bottom[1]} a {top[1]} empleados. '
            f'Mayor registro en {top[0]} ({top[1]}), menor en {bottom[0]} ({bottom[1]}).'
        ),
        'rotacion': (
            f'**Rotación**: mayor en {top[0]} ({top[1]}%), menor en {bottom[0]} ({bottom[1]}%). '
            f'Se recomienda analizar causas si supera el 5% mensual.'
        ),
        'asistencia': (
            f'**Asistencia**: {len(items)} indicadores. '
            f'Mayor: {top[0]} ({top[1]}), menor: {bottom[0]} ({bottom[1]}).'
        ),
        'areas': (
            f'**Distribución**: {len(items)} áreas, total {total} empleados. '
            f'Mayor concentración en {top[0]} ({top[1]}, {top[1] * 100 // total}%). '
            f'Menor en {bottom[0]} ({bottom[1]}).'
        ),
    }
    return analysis_map.get(chart_type, (
        f'**Datos**: {len(items)} categorías, total {total}. '
        f'Mayor: {top[0]} ({top[1]}), menor: {bottom[0]} ({bottom[1]}).'
    ))


# ─────────────────────────────────────────────────
# ANÁLISIS DE GRÁFICO (para dashboard ejecutivo)
# ─────────────────────────────────────────────────

@login_required
@require_POST
def ai_analyze_chart(request):
    """
    Genera análisis narrativo de un gráfico/sección de datos.
    Body JSON: {"chart": "headcount|rotacion|asistencia|areas", "data": {...}}
    Retorna SSE streaming.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    chart_type = body.get('chart', '')
    chart_data = body.get('data', {})

    ollama_ok = _is_ollama_reachable()

    # Fallback estático para análisis de gráficos
    if not ollama_ok:
        analysis = _static_chart_analysis(chart_type, chart_data)

        def fallback_stream():
            yield f'data: {analysis}\n\n'
            yield 'data: [DONE]\n\n'

        response = StreamingHttpResponse(
            fallback_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    svc = get_service()

    # Calcular totales para enriquecer el prompt con contexto
    labels = chart_data.get('labels', [])
    values = chart_data.get('values', [])
    total = sum(v for v in values if isinstance(v, (int, float)))
    items = list(zip(labels, values))
    top3 = sorted(items, key=lambda x: x[1], reverse=True)[:3] if items else []

    prompts = {
        'headcount': (
            f'Analiza la evolucion del headcount mensual de esta empresa.\n'
            f'Datos: {json.dumps(chart_data, ensure_ascii=False)}\n\n'
            f'Instrucciones:\n'
            f'1. Identifica la tendencia general (crecimiento, reduccion, estabilidad)\n'
            f'2. Señala el mes pico y el mes mas bajo con sus valores exactos\n'
            f'3. Calcula la variacion porcentual entre primer y ultimo dato\n'
            f'4. Concluye con una interpretacion estrategica de 1 linea\n'
            f'Formato: 4-5 oraciones directas y especificas. Sin bullet points.'
        ),
        'rotacion': (
            f'Analiza la tasa de rotacion mensual de personal.\n'
            f'Datos: {json.dumps(chart_data, ensure_ascii=False)}\n\n'
            f'Instrucciones:\n'
            f'1. Indica si la rotacion esta por encima o debajo del benchmark Peru construccion (5-8% anual)\n'
            f'2. Identifica los meses con picos de rotacion y posibles causas\n'
            f'3. Calcula el promedio del periodo\n'
            f'4. Recomienda 1 accion concreta basada en los datos\n'
            f'Formato: 4-5 oraciones directas. Sin bullet points.'
        ),
        'asistencia': (
            f'Analiza los indicadores de asistencia mensual.\n'
            f'Datos: {json.dumps(chart_data, ensure_ascii=False)}\n\n'
            f'Instrucciones:\n'
            f'1. Identifica si la tasa de asistencia es saludable (benchmark: >95%)\n'
            f'2. Señala los periodos con mayor ausentismo\n'
            f'3. Detecta patrones estacionales si los hay\n'
            f'4. Sugiere 1 accion preventiva especifica\n'
            f'Formato: 4-5 oraciones directas. Sin bullet points.'
        ),
        'areas': (
            f'Analiza la distribucion de {total} empleados en {len(labels)} areas.\n'
            f'Datos: {json.dumps(chart_data, ensure_ascii=False)}\n\n'
            f'Instrucciones:\n'
            f'1. Las 3 areas mas grandes son: '
            f'{", ".join(f"{a} ({v}, {v*100//total if total else 0}%)" for a,v in top3)}. '
            f'Comenta si esta concentracion es razonable\n'
            f'2. Identifica areas posiblemente subdimensionadas (menos del 3% del total)\n'
            f'3. Evalua el balance operativo: areas de produccion vs soporte\n'
            f'4. Recomienda 1 ajuste organizacional especifico\n'
            f'Formato: 4-5 oraciones directas. Sin bullet points.'
        ),
    }

    system = (
        'Eres Harmoni AI, analista senior de RRHH especializado en empresas constructoras Peru. '
        'Responde SIEMPRE en espanol. '
        'Sé directo, especifico y usa los numeros exactos de los datos. '
        'Nunca digas "los datos muestran" o "se puede observar" — ve directo al analisis. '
        'Nunca inventes datos que no esten en el input.'
    )
    prompt = prompts.get(
        chart_type,
        f'Analiza estos datos de RRHH e identifica los 3 hallazgos mas importantes '
        f'con recomendaciones accionables.\nDatos: {json.dumps(chart_data, ensure_ascii=False)}'
    )

    def event_stream():
        try:
            for chunk in svc.generate_stream(
                prompt=prompt,
                system=system,
                temperature=0.4,
                num_predict=700,
            ):
                yield f'data: {chunk}\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            logger.warning(f'ai_analyze_chart error: {e}')
            analysis = _static_chart_analysis(chart_type, chart_data)
            yield f'data: {analysis}\n\n'
            yield 'data: [DONE]\n\n'

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@login_required
@require_POST
def ai_ask_data(request):
    """
    Responde pregunta libre sobre datos de RRHH.
    Body JSON: {"question": "..."}
    Retorna SSE streaming.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    question = body.get('question', '').strip()
    if not question:
        return JsonResponse({'error': 'Pregunta vacía'}, status=400)

    svc = get_service()
    ollama_ok = _is_ollama_reachable()

    if not ollama_ok:
        fallback = responder_sin_ia(question, request.user)

        def fallback_stream():
            yield 'data: [FALLBACK]\n\n'
            if fallback:
                yield f'data: {_sse_text(fallback)}\n\n'
            else:
                yield (
                    'data: No pude responder esa consulta sin IA. '
                    'Configura Ollama para consultas avanzadas.\n\n'
                )
            yield 'data: [DONE]\n\n'

        response = StreamingHttpResponse(
            fallback_stream(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    modules = detect_module_context(question)
    system_prompt = build_system_prompt(request.user, modules=modules)

    messages = [{'role': 'user', 'content': question}]

    def event_stream():
        try:
            for chunk in svc.chat_stream(
                messages=messages,
                system=system_prompt,
                temperature=0.35,
                num_predict=900,
            ):
                yield f'data: {chunk}\n\n'
            yield 'data: [DONE]\n\n'
        except Exception as e:
            logger.warning(f'ai_ask_data error: {e}')
            yield 'data: _No se pudo generar respuesta._\n\n'
            yield 'data: [DONE]\n\n'

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream',
    )
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


# ─────────────────────────────────────────────────
# EXPORT REPORTE EXCEL
# ─────────────────────────────────────────────────

@login_required
@require_POST
def ai_export_report(request):
    """
    Genera y descarga reporte ejecutivo en Excel (.xlsx).
    Body JSON: {"type": "gerencia"}
    """
    from django.http import HttpResponse

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    report_type = body.get('type', 'gerencia')

    if report_type != 'gerencia':
        return JsonResponse({'error': f'Tipo no soportado: {report_type}'}, status=400)

    try:
        from .services.ai_excel_export import ReporteGerenciaExporter
        exporter = ReporteGerenciaExporter(request.user)
        wb = exporter.generate()

        from io import BytesIO
        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        from datetime import date
        filename = f'reporte-ejecutivo-{date.today().isoformat()}.xlsx'

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except Exception as e:
        logger.error(f'ai_export_report error: {e}')
        return JsonResponse({'error': str(e)}, status=500)
