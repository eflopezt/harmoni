"""
Servicio de IA — Multi-Provider (Fase 4.4).

Proveedores soportados:
  GEMINI    → Google Gemini 2.0 Flash / 2.5 Flash (via google-genai SDK)
  DEEPSEEK  → DeepSeek-V3 (API compatible OpenAI, via openai SDK)
  OPENAI    → GPT-4o-mini (via openai SDK)
  OLLAMA    → Ollama local (llama3.2, mistral, etc.)
  NINGUNO   → Sin IA (fallback a respuestas directas desde BD)

Interfaz pública (invariante al provider):
  get_service()          → IAService | None
  ia_disponible()        → bool
  mapear_columnas_ia()   → dict

Métodos de IAService:
  test_connection()      → dict{ok, info, error}
  generate(prompt, system)     → str | None
  chat(messages, system)       → str | None
  chat_stream(messages, system, temperature, num_predict) → Generator[str]
  generate_stream(prompt, ...)  → Generator[str]
  mapear_columnas(columnas, campos_target) → dict
  resumir_texto(texto, max_palabras)      → str | None
  clasificar_falta(descripcion)           → str | None

Decisión arquitectural (MEMORY.md — actualizada 2026-03-05):
  Migración Ollama → Cloud providers por costo de infraestructura.
  Privacidad LPDP deprioritizada año 1 (datos no sensibles).
"""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger('harmoni.ai')

# Timeouts
TIMEOUT_TEST = 8
TIMEOUT_GENERAR = 120

# Descripciones campos RRHH (para prompt mapeo columnas)
_CAMPO_DESCRIPCION: dict[str, str] = {
    'dni':            'número de documento de identidad del trabajador (DNI, RUC, CE)',
    'nombre':         'apellidos y nombres completos del trabajador',
    'codigo_s10':     'código interno del trabajador en el sistema S10 de obras',
    'fecha':          'fecha del registro de asistencia (formato DD/MM/AAAA o similar)',
    'entrada':        'hora de entrada o marcación de ingreso',
    'salida':         'hora de salida o marcación de egreso',
    'area':           'área, departamento o sección del trabajador',
    'cargo':          'cargo, puesto o categoría laboral del trabajador',
    'sueldo':         'remuneración, sueldo básico o salario del trabajador',
    'categoria_cod':  'código de categoría laboral',
    'categoria':      'nombre de la categoría o tipo de trabajador',
    'afp':            'nombre de la AFP (fondo de pensiones) del trabajador',
    'regimen_pension':'régimen previsional (AFP o ONP)',
    'cuspp':          'código único del sistema privado de pensiones',
    'correo':         'correo electrónico del trabajador',
    'celular':        'número de teléfono o celular',
}

# ═══════════════════════════════════════════════════════════════════════════
# Clase base — interfaz común a todos los providers
# ═══════════════════════════════════════════════════════════════════════════

class IAService(ABC):
    """Interfaz común. Cada provider implementa estos métodos."""

    provider_name: str = 'base'

    # ── Conectividad ────────────────────────────────────────────────────────

    @abstractmethod
    def test_connection(self) -> dict:
        """
        Verifica conectividad con el provider.
        Returns: {'ok': bool, 'info': str, 'error': str | None}
        """

    # ── Generación ──────────────────────────────────────────────────────────

    @abstractmethod
    def generate(self, prompt: str, system: str | None = None) -> str | None:
        """Single-turn, sin streaming. Retorna texto o None."""

    @abstractmethod
    def chat(self, messages: list, system: str | None = None) -> str | None:
        """Multi-turn, sin streaming. messages: [{'role':'user','content':'...'}]"""

    def chat_stream(
        self,
        messages: list,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        """
        Multi-turn con streaming. Yields chunks de texto.
        Implementación por defecto: llama chat() y yield todo de una vez
        (providers que no soporten streaming real lo pueden heredar).
        """
        result = self.chat(messages, system=system)
        if result:
            yield result

    def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        """Streaming single-turn. Implementación por defecto no-streaming."""
        result = self.generate(prompt, system=system)
        if result:
            yield result

    # ── Casos de uso RRHH ───────────────────────────────────────────────────

    def mapear_columnas(
        self,
        columnas: list[str],
        campos_target: list[str],
    ) -> dict[str, str]:
        """Detecta qué columna del archivo corresponde a cada campo RRHH."""
        if not columnas or not campos_target:
            return {}

        descripciones = '\n'.join(
            f'- "{c}": {_CAMPO_DESCRIPCION.get(c, c)}'
            for c in campos_target
        )
        prompt = (
            f'Tengo un archivo Excel con las siguientes columnas:\n'
            f'{json.dumps(columnas, ensure_ascii=False)}\n\n'
            f'Necesito mapear estas columnas a los siguientes campos:\n'
            f'{descripciones}\n\n'
            f'Responde ÚNICAMENTE con un objeto JSON válido, sin ningún texto adicional.\n'
            f'Formato exacto: {{"campo": "nombre_columna_excel"}}\n'
            f'Reglas:\n'
            f'  1. Solo incluye los campos que puedas identificar con certeza.\n'
            f'  2. Los valores deben ser el nombre exacto de la columna del archivo.\n'
            f'  3. Si no encuentras un campo, omítelo del JSON.\n'
            f'  4. No inventes columnas que no estén en la lista.'
        )
        system = (
            'Eres un asistente especializado en datos de RRHH y planillas peruanas. '
            'Tu única función es identificar columnas de archivos Excel. '
            'Respondes ÚNICAMENTE con JSON válido, sin texto adicional.'
        )

        respuesta = self.generate(prompt, system=system)
        if not respuesta:
            return {}

        try:
            match = re.search(r'\{[^{}]+\}', respuesta, re.DOTALL)
            if match:
                mapping = json.loads(match.group())
                valido = {
                    k: v for k, v in mapping.items()
                    if isinstance(k, str) and isinstance(v, str)
                    and k in campos_target and v in columnas
                }
                logger.info(f'IA [{self.provider_name}] mapeó columnas: {valido}')
                return valido
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f'Error parseando JSON de IA: {e}\nRespuesta: {respuesta[:200]}')
        return {}

    def resumir_texto(self, texto: str, max_palabras: int = 80) -> str | None:
        """Resume un texto en español en máximo `max_palabras` palabras."""
        prompt = (
            f'Resume el siguiente texto en máximo {max_palabras} palabras, '
            f'en español, conservando los puntos clave:\n\n{texto}'
        )
        return self.generate(prompt)

    def clasificar_falta(self, descripcion: str) -> str | None:
        """Sugiere el tipo de falta disciplinaria según DS 003-97-TR."""
        prompt = (
            'Según el DS 003-97-TR (Perú), clasifica la siguiente situación '
            'en uno de estos tipos de falta: ABANDONO_TRABAJO, INCUMPLIMIENTO_TAREAS, '
            'FALTA_HONESTIDAD, HOSTIGAMIENTO, OTRAS_FALTAS, GRAVE_CONDUCTA, INJURIA.\n\n'
            f'Situación: {descripcion}\n\n'
            'Responde ÚNICAMENTE con el nombre del tipo de falta, sin explicaciones.'
        )
        return self.generate(prompt)


# ═══════════════════════════════════════════════════════════════════════════
# Provider: GEMINI  (usa google-genai SDK v1+ — el antiguo google-generativeai está deprecado)
# ═══════════════════════════════════════════════════════════════════════════

class GeminiService(IAService):
    """
    Google Gemini via google-genai SDK (v1+).
    Modelos: gemini-2.5-flash, gemini-2.0-flash, gemini-2.5-pro
    Streaming nativo soportado.

    Nota: se usa `google.genai` (nuevo) NO `google.generativeai` (deprecado).
    Instalar: pip install google-genai
    """
    provider_name = 'GEMINI'

    def __init__(self, api_key: str, modelo: str = 'gemini-2.5-flash'):
        self.api_key = api_key
        self.modelo = modelo
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import google.genai as genai  # type: ignore
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise RuntimeError(
                    'google-genai no instalado. Ejecuta: pip install google-genai'
                )
        return self._client

    def _build_contents(self, messages: list) -> list:
        """Convierte formato OpenAI messages a formato Gemini contents.
        Soporta mensajes de texto (str) y multimodales (list of parts).
        """
        contents = []
        for m in messages:
            role = 'user' if m['role'] == 'user' else 'model'
            content = m.get('content', '')
            if isinstance(content, list):
                # Mensaje multimodal: lista de partes {type, text/mime_type/data}
                parts = []
                for part in content:
                    if part.get('type') == 'text':
                        parts.append({'text': part.get('text', '')})
                    elif part.get('type') == 'image':
                        parts.append({
                            'inline_data': {
                                'mime_type': part.get('mime_type', 'image/jpeg'),
                                'data': part.get('data', ''),
                            }
                        })
                contents.append({'role': role, 'parts': parts})
            else:
                contents.append({'role': role, 'parts': [{'text': str(content)}]})
        return contents

    def test_connection(self) -> dict:
        try:
            import google.genai as genai  # type: ignore
            client = genai.Client(api_key=self.api_key)
            # Llamada mínima para verificar API key
            resp = client.models.generate_content(
                model=self.modelo,
                contents='di "ok"',
            )
            return {
                'ok': True,
                'info': f'Gemini conectado. Modelo: {self.modelo}. Respuesta: {(resp.text or "")[:40]}',
                'error': None,
            }
        except ImportError:
            return {'ok': False, 'info': '', 'error': 'Instala: pip install google-genai'}
        except Exception as e:
            return {'ok': False, 'info': '', 'error': str(e)}

    def generate(self, prompt: str, system: str | None = None) -> str | None:
        try:
            import google.genai as genai  # type: ignore
            client = self._get_client()
            config = genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                max_output_tokens=400,
            ) if system else genai.types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=400,
            )
            resp = client.models.generate_content(
                model=self.modelo,
                contents=prompt,
                config=config,
            )
            return (resp.text or '').strip() or None
        except Exception as e:
            logger.warning(f'Gemini generate falló: {e}')
            return None

    def chat(self, messages: list, system: str | None = None) -> str | None:
        try:
            import google.genai as genai  # type: ignore
            client = self._get_client()
            contents = self._build_contents(messages)
            config = genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=0.1,
                max_output_tokens=600,
            )
            resp = client.models.generate_content(
                model=self.modelo,
                contents=contents,
                config=config,
            )
            return (resp.text or '').strip() or None
        except Exception as e:
            logger.warning(f'Gemini chat falló: {e}')
            return None

    def chat_stream(
        self,
        messages: list,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        try:
            import google.genai as genai  # type: ignore
            client = self._get_client()
            contents = self._build_contents(messages)
            config = genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=num_predict,
            )
            for chunk in client.models.generate_content_stream(
                model=self.modelo,
                contents=contents,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.warning(f'Gemini chat_stream falló: {e}')
            raise ConnectionError(f'Gemini stream: {e}') from e

    def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        try:
            import google.genai as genai  # type: ignore
            client = self._get_client()
            config = genai.types.GenerateContentConfig(
                system_instruction=system,
                temperature=temperature,
                max_output_tokens=num_predict,
            )
            for chunk in client.models.generate_content_stream(
                model=self.modelo,
                contents=prompt,
                config=config,
            ):
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.warning(f'Gemini generate_stream falló: {e}')
            raise ConnectionError(f'Gemini stream: {e}') from e


# ═══════════════════════════════════════════════════════════════════════════
# Provider: OPENAI-COMPATIBLE (DeepSeek + OpenAI)
# ═══════════════════════════════════════════════════════════════════════════

class OpenAICompatibleService(IAService):
    """
    Proveedor compatible con API OpenAI.
    Sirve para DeepSeek (api.deepseek.com) y OpenAI (api.openai.com).
    Usa el SDK openai que soporta base_url custom.
    Streaming nativo soportado.
    """

    def __init__(
        self,
        api_key: str,
        modelo: str = 'deepseek-chat',
        base_url: str = 'https://api.deepseek.com/v1',
        provider_label: str = 'DEEPSEEK',
    ):
        self.api_key = api_key
        self.modelo = modelo
        self.base_url = base_url
        self.provider_name = provider_label
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI  # type: ignore
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
            except ImportError:
                raise RuntimeError(
                    'openai no instalado. Ejecuta: pip install openai'
                )
        return self._client

    def test_connection(self) -> dict:
        try:
            client = self._get_client()
            # Llamada mínima para verificar API key
            resp = client.chat.completions.create(
                model=self.modelo,
                messages=[{'role': 'user', 'content': 'Hola'}],
                max_tokens=5,
            )
            content = resp.choices[0].message.content or ''
            return {
                'ok': True,
                'info': f'{self.provider_name} conectado. Modelo: {self.modelo}. Respuesta: {content[:30]}',
                'error': None,
            }
        except ImportError:
            return {'ok': False, 'info': '', 'error': 'Instala: pip install openai'}
        except Exception as e:
            return {'ok': False, 'info': '', 'error': str(e)}

    def generate(self, prompt: str, system: str | None = None) -> str | None:
        try:
            client = self._get_client()
            msgs = []
            if system:
                msgs.append({'role': 'system', 'content': system})
            msgs.append({'role': 'user', 'content': prompt})
            resp = client.chat.completions.create(
                model=self.modelo,
                messages=msgs,
                max_tokens=400,
                temperature=0.1,
            )
            return (resp.choices[0].message.content or '').strip()
        except Exception as e:
            logger.warning(f'{self.provider_name} generate falló: {e}')
            return None

    def chat(self, messages: list, system: str | None = None) -> str | None:
        try:
            client = self._get_client()
            msgs = []
            if system:
                msgs.append({'role': 'system', 'content': system})
            msgs.extend(messages)
            resp = client.chat.completions.create(
                model=self.modelo,
                messages=msgs,
                max_tokens=600,
                temperature=0.1,
            )
            return (resp.choices[0].message.content or '').strip()
        except Exception as e:
            logger.warning(f'{self.provider_name} chat falló: {e}')
            return None

    def chat_stream(
        self,
        messages: list,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        try:
            client = self._get_client()
            msgs = []
            if system:
                msgs.append({'role': 'system', 'content': system})
            msgs.extend(messages)
            stream = client.chat.completions.create(
                model=self.modelo,
                messages=msgs,
                max_tokens=num_predict,
                temperature=temperature,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
        except Exception as e:
            logger.warning(f'{self.provider_name} chat_stream falló: {e}')
            raise ConnectionError(f'{self.provider_name} stream: {e}') from e

    def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        msgs = []
        if system:
            msgs.append({'role': 'system', 'content': system})
        msgs.append({'role': 'user', 'content': prompt})
        yield from self.chat_stream(
            messages=msgs,
            system=None,  # ya incluido en msgs
            temperature=temperature,
            num_predict=num_predict,
        )


# ═══════════════════════════════════════════════════════════════════════════
# Provider: OLLAMA (local)
# ═══════════════════════════════════════════════════════════════════════════

# Cache global de resolución de modelo (evita re-queries a /api/tags)
_modelo_cache: dict[str, str] = {}
_modelo_cache_ts: float = 0
_MODELO_CACHE_TTL = 300  # 5 minutos


class OllamaService(IAService):
    """
    Cliente para el servidor Ollama local.
    Compatible con la interfaz IAService.
    """
    provider_name = 'OLLAMA'

    def __init__(
        self,
        endpoint: str = 'http://localhost:11434',
        modelo: str = 'llama3.2',
    ):
        self.endpoint = endpoint.rstrip('/')
        self.modelo = modelo
        self._modelo_resuelto: str | None = None

    def _resolver_modelo(self) -> str:
        global _modelo_cache, _modelo_cache_ts
        if self._modelo_resuelto:
            return self._modelo_resuelto
        now = time.time()
        base = self.modelo.split(':')[0].lower()
        if now - _modelo_cache_ts < _MODELO_CACHE_TTL and base in _modelo_cache:
            self._modelo_resuelto = _modelo_cache[base]
            return self._modelo_resuelto
        try:
            resp = requests.get(f'{self.endpoint}/api/tags', timeout=TIMEOUT_TEST)
            resp.raise_for_status()
            modelos = [m['name'] for m in resp.json().get('models', [])]
            for m in modelos:
                if m.lower() == self.modelo.lower():
                    self._modelo_resuelto = m
                    _modelo_cache[base] = m
                    _modelo_cache_ts = now
                    return m
            for m in modelos:
                if m.lower().startswith(base):
                    self._modelo_resuelto = m
                    _modelo_cache[base] = m
                    _modelo_cache_ts = now
                    logger.info(f'Modelo Ollama resuelto: {self.modelo} → {m}')
                    return m
        except Exception:
            pass
        self._modelo_resuelto = self.modelo
        return self.modelo

    def test_connection(self) -> dict:
        try:
            resp = requests.get(f'{self.endpoint}/api/tags', timeout=TIMEOUT_TEST)
            resp.raise_for_status()
            data = resp.json()
            modelos = [m['name'] for m in data.get('models', [])]
            base = self.modelo.split(':')[0].lower()
            modelo_activo = any(m.lower().startswith(base) for m in modelos)
            return {
                'ok': True,
                'info': f'Ollama conectado. {len(modelos)} modelos instalados.',
                'modelos': modelos,
                'modelo_activo': modelo_activo,
                'error': None,
            }
        except requests.exceptions.ConnectionError:
            return {
                'ok': False, 'info': '', 'modelos': [], 'modelo_activo': False,
                'error': (
                    f'No se puede conectar a Ollama en {self.endpoint}. '
                    '¿Está corriendo? Ejecuta: ollama serve'
                ),
            }
        except requests.exceptions.Timeout:
            return {
                'ok': False, 'info': '', 'modelos': [], 'modelo_activo': False,
                'error': f'Timeout al conectar con {self.endpoint}.',
            }
        except Exception as e:
            return {'ok': False, 'info': '', 'modelos': [], 'modelo_activo': False, 'error': str(e)}

    def generate(self, prompt: str, system: str | None = None) -> str | None:
        modelo = self._resolver_modelo()
        payload: dict = {
            'model': modelo, 'prompt': prompt, 'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 300},
        }
        if system:
            payload['system'] = system
        try:
            resp = requests.post(
                f'{self.endpoint}/api/generate', json=payload, timeout=TIMEOUT_GENERAR,
            )
            resp.raise_for_status()
            return resp.json().get('response', '').strip()
        except Exception as e:
            logger.warning(f'Ollama generate falló: {e}')
            return None

    def chat(self, messages: list, system: str | None = None) -> str | None:
        modelo = self._resolver_modelo()
        payload: dict = {
            'model': modelo, 'messages': messages, 'stream': False,
            'options': {'temperature': 0.1, 'num_predict': 300},
        }
        if system:
            payload['system'] = system
        try:
            resp = requests.post(
                f'{self.endpoint}/api/chat', json=payload, timeout=TIMEOUT_GENERAR,
            )
            resp.raise_for_status()
            return resp.json().get('message', {}).get('content', '').strip()
        except Exception as e:
            logger.warning(f'Ollama chat falló: {e}')
            return None

    def chat_stream(
        self,
        messages: list,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        modelo = self._resolver_modelo()
        payload: dict = {
            'model': modelo, 'messages': messages, 'stream': True,
            'options': {'temperature': temperature, 'num_predict': num_predict},
        }
        if system:
            payload['system'] = system
        try:
            resp = requests.post(
                f'{self.endpoint}/api/chat', json=payload,
                timeout=TIMEOUT_GENERAR, stream=True,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get('message', {}).get('content', '')
                    if content:
                        yield content
                    if data.get('done', False):
                        break
        except Exception as e:
            logger.warning(f'Ollama chat_stream falló: {e}')
            raise ConnectionError(f'Ollama chat_stream: {e}') from e

    def generate_stream(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.3,
        num_predict: int = 500,
    ):
        modelo = self._resolver_modelo()
        payload: dict = {
            'model': modelo, 'prompt': prompt, 'stream': True,
            'options': {'temperature': temperature, 'num_predict': num_predict},
        }
        if system:
            payload['system'] = system
        try:
            resp = requests.post(
                f'{self.endpoint}/api/generate', json=payload,
                timeout=TIMEOUT_GENERAR, stream=True,
            )
            resp.raise_for_status()
            for line in resp.iter_lines():
                if line:
                    data = json.loads(line)
                    content = data.get('response', '')
                    if content:
                        yield content
                    if data.get('done', False):
                        break
        except Exception as e:
            logger.warning(f'Ollama generate_stream falló: {e}')
            raise ConnectionError(f'Ollama generate_stream: {e}') from e


# ═══════════════════════════════════════════════════════════════════════════
# Fábrica — get_service() devuelve el provider configurado
# ═══════════════════════════════════════════════════════════════════════════

_service_cache: dict = {'svc': None, 'ts': 0, 'key': ''}
_SERVICE_CACHE_TTL = 60  # re-read config cada 60s


def get_service() -> IAService | None:
    """
    Devuelve el servicio IA configurado en ConfiguracionSistema.
    Returns None si ia_provider == 'NINGUNO' o si faltan datos requeridos.
    Usa cache de 60s para no re-leer config en cada request.
    """
    global _service_cache
    now = time.time()
    if (now - _service_cache['ts'] < _SERVICE_CACHE_TTL
            and _service_cache['svc'] is not None):
        return _service_cache['svc']

    svc = None
    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        provider = config.ia_provider
        api_key  = getattr(config, 'ia_api_key', '') or ''
        modelo   = config.ia_modelo or ''
        endpoint = config.ia_endpoint or ''

        if provider == 'GEMINI' and api_key:
            svc = GeminiService(
                api_key=api_key,
                modelo=modelo or 'gemini-2.5-flash',
            )
        elif provider == 'DEEPSEEK' and api_key:
            svc = OpenAICompatibleService(
                api_key=api_key,
                modelo=modelo or 'deepseek-chat',
                base_url=endpoint or 'https://api.deepseek.com/v1',
                provider_label='DEEPSEEK',
            )
        elif provider == 'OPENAI' and api_key:
            svc = OpenAICompatibleService(
                api_key=api_key,
                modelo=modelo or 'gpt-4o-mini',
                base_url='https://api.openai.com/v1',
                provider_label='OPENAI',
            )
        elif provider == 'OLLAMA':
            svc = OllamaService(
                endpoint=endpoint or 'http://localhost:11434',
                modelo=modelo or 'llama3.2',
            )
        # NINGUNO → svc remains None

        cache_key = f'{provider}|{api_key[:8]}|{modelo}|{endpoint}'
        _service_cache.update(svc=svc, ts=now, key=cache_key)

    except Exception as e:
        logger.debug(f'get_service: {e}')
        _service_cache.update(svc=None, ts=now, key='')

    return svc


# Cache de conectividad (para _is_ollama_reachable / ia_disponible)
_connectivity_cache: dict = {'ok': False, 'ts': 0}
_CONNECTIVITY_TTL = 30  # 30s


def _is_ollama_reachable() -> bool:
    """Compatibilidad legacy — usa ia_disponible internamente."""
    return ia_disponible()


def ia_disponible() -> bool:
    """
    ¿Está la IA habilitada en configuración Y el servidor responde?
    Usa cache de 30s para no hacer llamadas en cada request.
    """
    global _connectivity_cache
    now = time.time()
    if now - _connectivity_cache['ts'] < _CONNECTIVITY_TTL:
        return _connectivity_cache['ok']

    svc = get_service()
    ok = False
    if svc is not None:
        try:
            result = svc.test_connection()
            ok = result.get('ok', False)
        except Exception:
            ok = False

    _connectivity_cache.update(ok=ok, ts=now)
    return ok


def get_ocr_service() -> 'GeminiService | None':
    """
    Devuelve un GeminiService configurado para OCR de PDFs.

    Lógica de selección de API key:
      1. Si ia_ocr_provider == 'GEMINI' y ia_gemini_api_key está definida → usa ia_gemini_api_key
      2. Si ia_ocr_provider == 'GEMINI' y ia_gemini_api_key está vacía + ia_provider == 'GEMINI' → usa ia_api_key
      3. Cualquier otro caso → None (OCR no disponible)

    Esto permite el setup dual: DeepSeek para chat + Gemini para OCR.
    """
    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        if config.ia_ocr_provider != 'GEMINI':
            return None
        # Priorizar key OCR dedicada, caer a key principal si es también Gemini
        ocr_key = getattr(config, 'ia_gemini_api_key', '') or ''
        if not ocr_key and config.ia_provider == 'GEMINI':
            ocr_key = getattr(config, 'ia_api_key', '') or ''
        if not ocr_key:
            return None
        modelo = config.ia_modelo or 'gemini-2.5-flash'
        return GeminiService(api_key=ocr_key, modelo=modelo)
    except Exception as e:
        logger.debug(f'get_ocr_service: {e}')
        return None


def mapear_columnas_ia(
    columnas: list[str],
    campos_target: list[str],
) -> dict[str, str]:
    """
    Wrapper de conveniencia para mapeo de columnas.
    Solo actúa si ia_mapeo_activo=True en configuración.
    Returns {} si la IA no está disponible o falla.
    """
    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        if not config.ia_mapeo_activo:
            return {}
        svc = get_service()
        if svc is None:
            return {}
        return svc.mapear_columnas(columnas, campos_target)
    except Exception as e:
        logger.warning(f'mapear_columnas_ia: {e}')
        return {}
