"""Tests del modo LLM del Agente IA Nóminas.

Valida el flujo razonado: RAG primero → tool ejecutiva → respuesta con cita
normativa. Usa un mock del IAService para evitar costo de LLM real y para
controlar deterministicamente la salida JSON.
"""
import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model

from nominas.agente_ia.llm_orchestrator import (
    MAX_ITERACIONES,
    _parsear_respuesta_llm,
    procesar_mensaje_llm,
)
from nominas.agente_ia.orquestador import procesar_mensaje
from nominas.agente_ia.tools import tool_reintegro_masivo
from nominas.models import ConversacionAgenteIA, MensajeAgenteIA

User = get_user_model()


def _crear_personal_simple(dni, nombre, sueldo, grupo='STAFF', condicion='LOCAL'):
    """Helper compacto para tests de reintegro masivo."""
    from empresas.models import Empresa
    from personal.models import Personal
    from nominas.tests._helpers import unique_ruc
    # RUC vía counter atómico, no timestamp — evita colisión por ms en suite.
    ruc = unique_ruc()
    emp, _ = Empresa.objects.get_or_create(
        ruc=ruc, defaults={'razon_social': 'Test SAC', 'plan': 'PROFESIONAL'},
    )
    return Personal.objects.create(
        tipo_doc='DNI', nro_doc=dni,
        apellidos_nombres=nombre, cargo='Tester',
        tipo_trab='EMPLEADO', categoria='EMPLEADO',
        estado='Activo', empresa=emp,
        sueldo_base=Decimal(str(sueldo)),
        fecha_alta=date(2024, 1, 1),
        regimen_pension='ONP', tiene_eps=False,
        grupo_tareo=grupo, condicion=condicion,
    )


# ──────────────────────────────────────────────────────────────────────
# Tests unitarios — parsing JSON tolerante
# ──────────────────────────────────────────────────────────────────────


class TestParseoRespuestaLLM:
    def test_json_directo(self):
        raw = '{"action": "respond", "message": "Hola"}'
        p = _parsear_respuesta_llm(raw)
        assert p == {'action': 'respond', 'message': 'Hola'}

    def test_json_en_bloque_fence(self):
        raw = 'Pensé un rato. ```json\n{"action": "respond", "message": "ok"}\n```'
        p = _parsear_respuesta_llm(raw)
        assert p == {'action': 'respond', 'message': 'ok'}

    def test_json_en_bloque_fence_sin_lang(self):
        raw = '```\n{"action": "call_tool", "tool": "x", "args": {}}\n```'
        p = _parsear_respuesta_llm(raw)
        assert p['action'] == 'call_tool'
        assert p['tool'] == 'x'

    def test_json_embebido_en_texto(self):
        raw = 'Voy a responder: {"action": "respond", "message": "ok"} fin.'
        p = _parsear_respuesta_llm(raw)
        assert p == {'action': 'respond', 'message': 'ok'}

    def test_malformado_devuelve_none(self):
        assert _parsear_respuesta_llm('') is None
        assert _parsear_respuesta_llm('totalmente texto sin json') is None
        assert _parsear_respuesta_llm('{"action": "respond"') is None  # no cierra

    def test_dict_sin_action_devuelve_none(self):
        raw = '{"message": "hola"}'
        assert _parsear_respuesta_llm(raw) is None


# ──────────────────────────────────────────────────────────────────────
# Tests de integración con mock IAService
# ──────────────────────────────────────────────────────────────────────


def _hacer_conversacion(usuario=None):
    """Helper: crea conversación vacía para tests."""
    return ConversacionAgenteIA.objects.create(
        usuario=usuario, titulo='',
    )


def _mock_service_secuencia(*respuestas):
    """Crea un mock IAService que devuelve `respuestas` en orden por cada chat()."""
    svc = MagicMock()
    svc.provider_name = 'mock'
    svc.chat = MagicMock(side_effect=list(respuestas))
    return svc


@pytest.mark.django_db
class TestProcesarMensajeLLM:
    """Cubre el flujo completo del orquestador LLM."""

    def test_respuesta_directa_sin_tool(self):
        conv = _hacer_conversacion()
        svc = _mock_service_secuencia(
            json.dumps({'action': 'respond', 'message': 'Saludo cordial.'})
        )

        out = procesar_mensaje_llm(
            conversacion=conv, texto_usuario='Hola',
            ia_service=svc,
        )

        assert out['respuesta'] == 'Saludo cordial.'
        assert out['modo'] == 'llm'
        assert out['tools_llamadas'] == []
        # Mensajes persistidos: user + assistant
        roles = list(MensajeAgenteIA.objects.filter(conversacion=conv)
                     .order_by('fecha').values_list('rol', flat=True))
        assert roles == ['user', 'assistant']

    def test_flujo_rag_luego_respuesta(self):
        """Caso del usuario: 'olvidé aumentar S/200 a todos el mes pasado'.

        Esperado: LLM llama consultar_normativa primero, recibe el resultado
        del RAG (que ahora cubre aumento retroactivo masivo), y luego
        responde citando la base legal.
        """
        conv = _hacer_conversacion()
        svc = _mock_service_secuencia(
            # Turno 1: LLM decide consultar normativa
            json.dumps({
                'action': 'call_tool',
                'tool': 'consultar_normativa',
                'args': {'query': 'olvidé aumentar el sueldo a todos 200 soles mes pasado'},
                'reasoning': 'Validar marco legal primero',
            }),
            # Turno 2: LLM responde con la base legal citada
            json.dumps({
                'action': 'respond',
                'message': (
                    'Según el **D.S. 003-97-TR art. 6** y la **Ley 27735**, este '
                    'caso califica como reintegro de remuneración por aumento '
                    'retroactivo. Procedimiento sugerido: ... ¿Confirmas que '
                    'calcule el impacto masivo?'
                ),
            }),
        )

        out = procesar_mensaje_llm(
            conversacion=conv,
            texto_usuario='el mes pasado olvidé aumentar el sueldo a todos los trabajadores 200 soles',
            ia_service=svc,
        )

        assert out['modo'] == 'llm'
        # Llamó exactamente 1 tool: consultar_normativa
        assert len(out['tools_llamadas']) == 1
        call = out['tools_llamadas'][0]
        assert call['name'] == 'consultar_normativa'
        # Y el resultado del RAG trajo la entrada correcta
        titulos = [r['titulo'] for r in call['result'].get('resultados', [])]
        assert any('Aumento de sueldo retroactivo' in t for t in titulos), \
            f'RAG no devolvió la entrada de aumento retroactivo. Titulos: {titulos}'
        # Y la respuesta final cita la base legal
        assert 'D.S. 003-97-TR' in out['respuesta']
        assert 'Ley 27735' in out['respuesta']
        # Auditoría persisitida (3 mensajes: user + tool + assistant)
        roles = list(MensajeAgenteIA.objects.filter(conversacion=conv)
                     .order_by('fecha').values_list('rol', flat=True))
        assert roles == ['user', 'tool', 'assistant']

    def test_json_malformado_reintenta_y_se_recupera(self):
        """Si el LLM devuelve basura en el primer turno, el orquestador lo
        empuja a responder JSON válido y eventualmente se recupera."""
        conv = _hacer_conversacion()
        svc = _mock_service_secuencia(
            'esto no es JSON',
            json.dumps({'action': 'respond', 'message': 'Recuperado.'}),
        )

        out = procesar_mensaje_llm(
            conversacion=conv, texto_usuario='hola',
            ia_service=svc,
        )

        assert out['respuesta'] == 'Recuperado.'

    def test_tool_inexistente_no_explota(self):
        """Si el LLM inventa una tool, el dispatcher devuelve error y el
        orquestador continúa el loop."""
        conv = _hacer_conversacion()
        svc = _mock_service_secuencia(
            json.dumps({'action': 'call_tool', 'tool': 'tool_inventada', 'args': {}}),
            json.dumps({'action': 'respond', 'message': 'Disculpas.'}),
        )

        out = procesar_mensaje_llm(
            conversacion=conv, texto_usuario='hola',
            ia_service=svc,
        )

        assert out['respuesta'] == 'Disculpas.'
        assert len(out['tools_llamadas']) == 1
        assert 'error' in out['tools_llamadas'][0]['result']

    def test_loop_termina_en_max_iteraciones(self):
        """Si el LLM nunca responde, corta y devuelve mensaje de límite."""
        conv = _hacer_conversacion()
        # MAX_ITERACIONES tool_calls iguales
        respuestas = [
            json.dumps({'action': 'call_tool', 'tool': 'consultar_normativa',
                        'args': {'query': 'gratif'}})
        ] * (MAX_ITERACIONES + 2)
        svc = _mock_service_secuencia(*respuestas)

        out = procesar_mensaje_llm(
            conversacion=conv, texto_usuario='loop',
            ia_service=svc,
        )

        # No tiró excepción, devolvió mensaje de control
        assert 'límite' in out['respuesta'].lower() or 'reformularla' in out['respuesta']
        # Llamó tools hasta MAX_ITERACIONES (cap protector)
        assert len(out['tools_llamadas']) <= MAX_ITERACIONES


# ──────────────────────────────────────────────────────────────────────
# Test de integración: el orquestador público elige el modo correcto
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestOrquestadorPublicoEligeModoCorrecto:
    def test_sin_ia_disponible_usa_heuristico(self, monkeypatch):
        """Si ia_disponible() es False, NO debe instanciar el LLM orchestrator
        y debe devolver una respuesta del modo heurístico."""
        # Forzar ia_disponible = False
        monkeypatch.setattr(
            'asistencia.services.ai_service.ia_disponible',
            lambda: False,
        )
        conv = _hacer_conversacion()

        out = procesar_mensaje(
            conversacion=conv,
            texto_usuario='cualquier cosa que no matchee intents específicos',
            usuario=None, ip=None,
        )

        assert out['modo'] == 'heuristico'

    def test_ia_disponible_pero_falla_hace_fallback(self, monkeypatch):
        """Si ia_disponible() es True pero la importación/ejecución del LLM
        orchestrator lanza, debe caer al heurístico sin propagar el error."""
        monkeypatch.setattr(
            'asistencia.services.ai_service.ia_disponible',
            lambda: True,
        )

        def boom(*args, **kwargs):
            raise RuntimeError('Provider no responde')

        monkeypatch.setattr(
            'nominas.agente_ia.llm_orchestrator.procesar_mensaje_llm',
            boom,
        )
        conv = _hacer_conversacion()

        out = procesar_mensaje(
            conversacion=conv, texto_usuario='hola', usuario=None, ip=None,
        )

        # No crashea, responde en heurístico
        assert out['modo'] == 'heuristico'


# ──────────────────────────────────────────────────────────────────────
# Tool reintegro masivo — caso del usuario (S/200 a todos)
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestToolReintegroMasivo:
    """Cobertura de la nueva tool de aumento retroactivo masivo."""

    def test_aumento_200_a_todos_3_trabajadores(self):
        """Caso usuario: olvidé subir S/200 a todos.
        3 trabajadores con sueldos 1500, 3000, 5000 → 600 bruto total."""
        _crear_personal_simple('40000001', 'Worker A', 1500)
        _crear_personal_simple('40000002', 'Worker B', 3000)
        _crear_personal_simple('40000003', 'Worker C', 5000)

        out = tool_reintegro_masivo(
            monto_aumento=200, anio=2026, mes=4, filtro='todos',
        )

        assert out.get('simulacion') is True
        resumen = out['resumen']
        assert resumen['trabajadores_afectados'] == 3
        assert resumen['total_bruto'] == pytest.approx(600.0, abs=0.01)
        # ONP descuenta 13% por trabajador = 26 → neto por persona = 174 → 522 total
        assert resumen['total_neto_a_depositar'] == pytest.approx(522.0, abs=0.5)
        # ESSALUD 9% por trabajador = 18 → empresa = 200+18 por cabeza = 218*3 = 654
        assert resumen['total_costo_empresa'] == pytest.approx(654.0, abs=0.5)
        # Detalle con los 3
        assert len(out['detalle']) == 3
        dnis = sorted(d['dni'] for d in out['detalle'])
        assert dnis == ['40000001', '40000002', '40000003']

    def test_filtro_grupo_staff(self):
        _crear_personal_simple('41000001', 'Staff 1', 2000, grupo='STAFF')
        _crear_personal_simple('41000002', 'RCO 1', 2000, grupo='RCO')

        out = tool_reintegro_masivo(
            monto_aumento=100, anio=2026, mes=4, filtro='grupo:STAFF',
        )

        assert out['resumen']['trabajadores_afectados'] == 1
        assert out['detalle'][0]['dni'] == '41000001'

    def test_filtro_condicion_foraneo(self):
        _crear_personal_simple('42000001', 'Local 1', 2000, condicion='LOCAL')
        _crear_personal_simple('42000002', 'Foraneo 1', 2000, condicion='FORANEO')

        out = tool_reintegro_masivo(
            monto_aumento=100, anio=2026, mes=4, filtro='condicion:FORANEO',
        )

        assert out['resumen']['trabajadores_afectados'] == 1
        assert out['detalle'][0]['dni'] == '42000002'

    def test_trabajador_sin_sueldo_se_cuenta_aparte(self):
        from empresas.models import Empresa
        from personal.models import Personal
        emp, _ = Empresa.objects.get_or_create(
            ruc='20111111119', defaults={'razon_social': 'Test', 'plan': 'PROFESIONAL'})
        Personal.objects.create(
            tipo_doc='DNI', nro_doc='43000001', apellidos_nombres='Sin sueldo',
            cargo='Tester', tipo_trab='EMPLEADO', categoria='EMPLEADO',
            estado='Activo', empresa=emp, sueldo_base=Decimal('0'),
            fecha_alta=date(2024, 1, 1), regimen_pension='ONP', tiene_eps=False,
        )

        out = tool_reintegro_masivo(
            monto_aumento=200, anio=2026, mes=4, filtro='todos',
        )

        assert out['resumen']['trabajadores_afectados'] == 0
        assert out['resumen']['trabajadores_sin_sueldo_base'] == 1

    def test_monto_invalido_devuelve_error(self):
        assert 'error' in tool_reintegro_masivo(
            monto_aumento=0, anio=2026, mes=4, filtro='todos')
        assert 'error' in tool_reintegro_masivo(
            monto_aumento=-50, anio=2026, mes=4, filtro='todos')

    def test_filtro_desconocido_devuelve_error(self):
        out = tool_reintegro_masivo(
            monto_aumento=200, anio=2026, mes=4, filtro='inventado:xyz')
        assert 'error' in out
        assert 'filtro' in out['error'].lower()

    def test_periodo_invalido_devuelve_error(self):
        out = tool_reintegro_masivo(
            monto_aumento=200, anio=2026, mes=13, filtro='todos')
        assert 'error' in out

    def test_cesado_antes_del_periodo_se_excluye(self):
        from empresas.models import Empresa
        from personal.models import Personal
        emp, _ = Empresa.objects.get_or_create(
            ruc='20222222229', defaults={'razon_social': 'Test', 'plan': 'PROFESIONAL'})
        # Cesado en marzo, no debe aparecer para reintegro de abril
        Personal.objects.create(
            tipo_doc='DNI', nro_doc='44000001', apellidos_nombres='Cesado',
            cargo='Tester', tipo_trab='EMPLEADO', categoria='EMPLEADO',
            estado='Activo', empresa=emp, sueldo_base=Decimal('2000'),
            fecha_alta=date(2024, 1, 1), fecha_cese=date(2026, 3, 31),
            regimen_pension='ONP', tiene_eps=False,
        )
        Personal.objects.create(
            tipo_doc='DNI', nro_doc='44000002', apellidos_nombres='Activo',
            cargo='Tester', tipo_trab='EMPLEADO', categoria='EMPLEADO',
            estado='Activo', empresa=emp, sueldo_base=Decimal('2000'),
            fecha_alta=date(2024, 1, 1),
            regimen_pension='ONP', tiene_eps=False,
        )

        out = tool_reintegro_masivo(
            monto_aumento=200, anio=2026, mes=4, filtro='todos')

        # Solo el activo
        dnis = [d['dni'] for d in out['detalle']]
        assert '44000001' not in dnis
        assert '44000002' in dnis

    def test_limite_preview_trunca_detalle_pero_totales_completos(self):
        # Crear 5 trabajadores, pero limite_preview=2 → detalle de 2 + 3 fuera
        for i in range(5):
            _crear_personal_simple(f'4500000{i}', f'W{i}', 1000)

        out = tool_reintegro_masivo(
            monto_aumento=100, anio=2026, mes=4, filtro='todos',
            limite_preview=2,
        )

        assert out['resumen']['trabajadores_afectados'] == 5
        assert len(out['detalle']) == 2
        assert out['fuera_de_preview'] == 3
