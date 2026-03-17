"""
knowledge_service.py — Motor RAG para el asistente IA de Harmoni.

FASE A (siempre disponible): búsqueda por keywords con re-ranking.
  - Sin dependencias extra.  Works on SQLite dev y PostgreSQL prod.
  - Tokeniza la pregunta, busca en título / contenido / tags (ilike).
  - Devuelve artículos ordenados por relevancia.

FASE B (activa cuando hay API key + embeddings pre-calculados):
  - text-embedding-3-small de OpenAI (1536 dims, $0.02/M tokens).
  - PostgreSQL + pgvector: CosineDistance en SQL con índice HNSW → O(log n).
  - SQLite fallback: cosine similarity con numpy en Python → O(n).
  - Activar: python manage.py index_knowledge_embeddings

Uso:
    from core.knowledge_service import get_knowledge_context
    ctx = get_knowledge_context("¿Cuántos días de vacaciones corresponden?")
    # ctx es un bloque markdown listo para inyectar en el system prompt
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import Optional

logger = logging.getLogger('harmoni.knowledge')

# ─── pgvector availability ────────────────────────────────────────────────────
try:
    from pgvector.django import CosineDistance  # noqa: PLC0415
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False

# ─── Configuración ─────────────────────────────────────────────────────────────
EMBEDDING_MODEL   = 'text-embedding-3-small'
EMBEDDING_DIM     = 1536
SIMILARITY_CUTOFF = 0.40   # umbral mínimo de similitud coseno (Phase B)
PHASE_B_ENABLED   = True   # se puede desactivar globalmente con False

# ─── Stopwords ────────────────────────────────────────────────────────────────
_STOPWORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'en', 'con', 'por', 'para', 'que',
    'es', 'son', 'fue', 'era', 'ser', 'hay', 'tiene',
    'me', 'se', 'le', 'lo', 'mi', 'tu', 'su',
    'como', 'cuando', 'donde', 'cuanto', 'cuantos',
    'cual', 'que', 'quien',
    'mas', 'muy', 'bien', 'mal', 'todo', 'cada',
}


def _tokenize(text: str) -> list[str]:
    """Extrae palabras significativas (>3 chars, no stopwords)."""
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if len(w) > 3 and w not in _STOPWORDS]


# ═══════════════════════════════════════════════════════════════════════════════
# FASE B — Embeddings semánticos
# ═══════════════════════════════════════════════════════════════════════════════

def _get_openai_api_key() -> str:
    """Lee la API key de ConfiguracionSistema (lazy import para evitar circulares)."""
    try:
        from asistencia.models import ConfiguracionSistema  # noqa: PLC0415
        config = ConfiguracionSistema.get_config()
        # Soporta provider OPENAI y DEEPSEEK-via-OpenAI; para embeddings siempre usamos OpenAI
        # Si el usuario tiene ia_gemini_api_key, puede usarla también (Gemini embeddings)
        # Por ahora usamos ia_api_key si el provider es OPENAI o DeepSeek (que no tiene embeddings)
        if config.ia_provider == 'OPENAI' and config.ia_api_key:
            return config.ia_api_key
        # Si hay una API key de OpenAI guardada de cualquier forma
        if config.ia_api_key and 'sk-' in config.ia_api_key:
            return config.ia_api_key
        return ''
    except Exception:
        return ''


def _cosine_similarity(a, b) -> float:
    """Cosine similarity entre dos arrays (numpy o listas)."""
    try:
        import numpy as np
        a, b = np.array(a, dtype=float), np.array(b, dtype=float)
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))
    except ImportError:
        # Fallback puro Python si numpy no está disponible
        dot = sum(x * y for x, y in zip(a, b))
        mag_a = sum(x * x for x in a) ** 0.5
        mag_b = sum(x * x for x in b) ** 0.5
        if mag_a == 0 or mag_b == 0:
            return 0.0
        return dot / (mag_a * mag_b)


def embed_text(text: str, api_key: str = '') -> list[float] | None:
    """
    Genera un vector de embedding para el texto dado.

    Args:
        text: Texto a embeddear.
        api_key: OpenAI API key. Si no se provee, se lee de ConfiguracionSistema.

    Returns:
        Lista de floats (1536 dims) o None si falla.
    """
    if not api_key:
        api_key = _get_openai_api_key()
    if not api_key:
        return None

    try:
        from openai import OpenAI  # noqa: PLC0415
        client = OpenAI(api_key=api_key)
        response = client.embeddings.create(
            input=text[:8000],  # máx ~2000 tokens para text-embedding-3-small
            model=EMBEDDING_MODEL,
        )
        return response.data[0].embedding
    except Exception as exc:
        logger.warning('knowledge_service.embed_text error: %s', exc)
        return None


def _is_phase_b_ready() -> bool:
    """Verifica si Phase B está disponible: API key configurada + hay artículos con embeddings."""
    if not PHASE_B_ENABLED:
        return False
    try:
        from core.models import KnowledgeArticle  # noqa: PLC0415
        # Check pgvector VectorField first, then fall back to embedding_json
        if HAS_PGVECTOR:
            has_embeddings = KnowledgeArticle.objects.filter(
                activo=True, embedding__isnull=False,
            ).exists()
            if has_embeddings:
                return bool(_get_openai_api_key())
        # Fallback: check embedding_json (SQLite dev or pre-migration)
        has_embeddings = KnowledgeArticle.objects.filter(
            activo=True,
        ).exclude(embedding_json__isnull=True).exclude(embedding_json='').exists()
        if not has_embeddings:
            return False
        return bool(_get_openai_api_key())
    except Exception:
        return False


def _search_pgvector(query_vec: list[float], limit: int) -> list[dict]:
    """
    Búsqueda semántica via pgvector CosineDistance — single SQL query con HNSW index.
    CosineDistance retorna distancia coseno en [0, 2]; similitud = 1 - distancia.
    """
    from core.models import KnowledgeArticle  # noqa: PLC0415

    max_distance = 1.0 - SIMILARITY_CUTOFF
    articles = (
        KnowledgeArticle.objects
        .filter(activo=True, embedding__isnull=False)
        .annotate(cosine_dist=CosineDistance('embedding', query_vec))
        .filter(cosine_dist__lte=max_distance)
        .order_by('cosine_dist')
        [:limit]
    )

    result = []
    for art in articles:
        sim = 1.0 - (art.cosine_dist or 0.0)
        contenido = art.contenido.strip()
        if len(contenido) > 800:
            contenido = contenido[:800] + '…'
        result.append({
            'titulo':    art.titulo,
            'categoria': art.get_categoria_display(),
            'contenido': contenido,
            '_sim':      round(sim, 3),
        })
    return result


def _search_python_fallback(query_vec: list[float], limit: int) -> list[dict]:
    """
    Fallback semántico Python-level: carga todos los embeddings de embedding_json
    y calcula cosine similarity en memoria. O(n) — para SQLite dev o pre-migration.
    """
    from core.models import KnowledgeArticle  # noqa: PLC0415

    articles = list(
        KnowledgeArticle.objects
        .filter(activo=True)
        .exclude(embedding_json__isnull=True)
        .exclude(embedding_json='')
    )
    if not articles:
        return []

    scored: list[tuple[float, object]] = []
    for art in articles:
        try:
            art_vec = json.loads(art.embedding_json)
            sim = _cosine_similarity(query_vec, art_vec)
            scored.append((sim, art))
        except Exception:
            continue

    scored.sort(key=lambda x: -x[0])
    result = []
    for sim, art in scored[:limit]:
        if sim < SIMILARITY_CUTOFF:
            break
        contenido = art.contenido.strip()
        if len(contenido) > 800:
            contenido = contenido[:800] + '…'
        result.append({
            'titulo':    art.titulo,
            'categoria': art.get_categoria_display(),
            'contenido': contenido,
            '_sim':      round(sim, 3),
        })
    return result


def search_knowledge_semantic(query: str, limit: int = 5) -> list[dict]:
    """
    FASE B: Búsqueda semántica por similitud de embeddings.

    - PostgreSQL + pgvector: CosineDistance en SQL con índice HNSW → O(log n).
    - SQLite / sin pgvector: cosine similarity en Python → O(n) fallback.

    Returns:
        Lista de dicts: {titulo, categoria, contenido} ordenados por similitud.
        Lista vacía si Phase B no está disponible o falla.
    """
    api_key = _get_openai_api_key()
    if not api_key:
        return []

    query_vec = embed_text(query, api_key=api_key)
    if not query_vec:
        return []

    # Try pgvector SQL path first (PostgreSQL production)
    if HAS_PGVECTOR:
        try:
            from core.models import KnowledgeArticle  # noqa: PLC0415
            has_vec = KnowledgeArticle.objects.filter(
                activo=True, embedding__isnull=False,
            ).exists()
            if has_vec:
                results = _search_pgvector(query_vec, limit)
                if results:
                    logger.debug('knowledge_service: pgvector search returned %d results.', len(results))
                    return results
        except Exception as exc:
            logger.warning('knowledge_service: pgvector search failed, falling back to Python. Error: %s', exc)

    # Fallback: Python-level cosine similarity (SQLite dev or no pgvector)
    try:
        return _search_python_fallback(query_vec, limit)
    except Exception as exc:
        logger.warning('knowledge_service.search_knowledge_semantic fallback error: %s', exc)
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# FASE A — Búsqueda por keywords
# ═══════════════════════════════════════════════════════════════════════════════

def _relevance_score(art, tokens: list[str]) -> int:
    """
    Score por tokens en título y tags.
    Título: 3 pts por token.  Tags: 2 pts por token.
    """
    title = art.titulo.lower()
    tags  = art.tags.lower()
    score = 0
    for t in tokens:
        if t in title:
            score += 3
        if t in tags:
            score += 2
    return score


def search_knowledge_keywords(query: str, limit: int = 5) -> list[dict]:
    """
    FASE A: Búsqueda por keywords con re-ranking por relevancia.

    1. Filtra por OR de tokens en título / contenido / tags.
    2. Recupera hasta limit×4 candidatos (ordenados por prioridad).
    3. Re-rankea en Python: tokens en título/tags dan más peso.
    4. Devuelve los top-N más relevantes.
    """
    from django.db.models import Q  # noqa: PLC0415
    try:
        from core.models import KnowledgeArticle  # noqa: PLC0415
    except ImportError:
        return []

    tokens = _tokenize(query)[:8]
    if not tokens:
        return []

    q = Q()
    for token in tokens:
        q |= (
            Q(titulo__icontains=token)
            | Q(contenido__icontains=token)
            | Q(tags__icontains=token)
        )

    try:
        candidates = list(
            KnowledgeArticle.objects
            .filter(q, activo=True)
            .order_by('prioridad', 'id')
            .distinct()
            [: limit * 4]
        )
    except Exception as exc:
        logger.warning('knowledge_service.search_knowledge_keywords error: %s', exc)
        return []

    # Re-rank
    candidates.sort(key=lambda a: (-_relevance_score(a, tokens), a.prioridad))
    candidates = candidates[:limit]

    result = []
    for art in candidates:
        contenido = art.contenido.strip()
        if len(contenido) > 800:
            contenido = contenido[:800] + '…'
        result.append({
            'titulo':    art.titulo,
            'categoria': art.get_categoria_display(),
            'contenido': contenido,
            '_kw_score': _relevance_score(art, tokens),  # debug: keyword relevance score
        })

    return result


# ═══════════════════════════════════════════════════════════════════════════════
# API PÚBLICA
# ═══════════════════════════════════════════════════════════════════════════════

def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    """
    Búsqueda unificada: intenta Phase B (semántica) y cae a Phase A (keywords).

    Phase B se activa automáticamente cuando:
    - Hay una API key de OpenAI configurada en ConfiguracionSistema.
    - Existe al menos un artículo con embedding pre-calculado.

    Para calcular embeddings: python manage.py index_knowledge_embeddings
    """
    # Intentar Phase B (semántica)
    if PHASE_B_ENABLED and _is_phase_b_ready():
        try:
            results = search_knowledge_semantic(query, limit=limit)
            if results:
                logger.debug('knowledge_service: Phase B retornó %d resultados.', len(results))
                return results
        except Exception as exc:
            logger.warning('knowledge_service: Phase B falló, usando Phase A. Error: %s', exc)

    # Fallback a Phase A (keywords)
    return search_knowledge_keywords(query, limit=limit)


def get_knowledge_context(query: str, limit: int = 4, min_kw_score: int = 2) -> str:
    """
    Retorna bloque de conocimiento relevante para inyectar en el system prompt.

    Framing intencional: el modelo integra esto como expertise propio,
    no como fuente externa a citar textualmente.

    Args:
        query: Pregunta del usuario.
        limit: Máximo de artículos a retornar.
        min_kw_score: Puntuación mínima de relevancia para artículos por keywords
            (Phase A). Artículos con score menor se descartan para evitar inyectar
            contenido irrelevante. No aplica a Phase B (tiene SIMILARITY_CUTOFF).

    Returns:
        String formateado listo para concatenar al system prompt.
        String vacío si no hay resultados relevantes.
    """
    articles = search_knowledge(query, limit=limit)
    if not articles:
        return ''

    # Filtrar artículos de baja relevancia (Phase A keyword results)
    filtered = []
    for art in articles:
        kw_score = art.get('_kw_score')
        sim = art.get('_sim')
        if sim is not None:
            # Phase B result — already filtered by SIMILARITY_CUTOFF
            logger.debug('RAG article "%s" sim=%.3f', art['titulo'], sim)
            filtered.append(art)
        elif kw_score is not None and kw_score < min_kw_score:
            logger.debug(
                'RAG article "%s" dropped (kw_score=%d < min=%d)',
                art['titulo'], kw_score, min_kw_score,
            )
        else:
            logger.debug(
                'RAG article "%s" kw_score=%s',
                art['titulo'], kw_score,
            )
            filtered.append(art)

    if not filtered:
        return ''

    lines = [
        'Normativa y políticas aplicables (aplícalas como expertise propio; '
        'cita solo el decreto o artículo cuando corresponda, no menciones '
        '"base de conocimiento" ni reproduzcas párrafos enteros):'
    ]
    for art in filtered:
        lines.append(f'\n• {art["titulo"]} ({art["categoria"]}):')
        lines.append(art['contenido'])

    logger.info(
        'RAG context: %d/%d articles injected for query "%.60s"',
        len(filtered), len(articles), query,
    )
    return '\n'.join(lines)


def get_embedding_stats() -> dict:
    """
    Retorna estadísticas sobre el estado de los embeddings.
    Útil para la UI de configuración.
    """
    try:
        from core.models import KnowledgeArticle  # noqa: PLC0415
        total = KnowledgeArticle.objects.filter(activo=True).count()
        with_emb = KnowledgeArticle.objects.filter(
            activo=True
        ).exclude(embedding_json__isnull=True).exclude(embedding_json='').count()
        with_pgvec = 0
        if HAS_PGVECTOR:
            try:
                with_pgvec = KnowledgeArticle.objects.filter(
                    activo=True, embedding__isnull=False,
                ).count()
            except Exception:
                pass
        return {
            'total': total,
            'with_embedding': with_emb,
            'with_pgvector': with_pgvec,
            'without_embedding': total - with_emb,
            'phase_b_ready': _is_phase_b_ready(),
            'pgvector_available': HAS_PGVECTOR,
            'embedding_model': EMBEDDING_MODEL,
        }
    except Exception:
        return {
            'total': 0,
            'with_embedding': 0,
            'with_pgvector': 0,
            'without_embedding': 0,
            'phase_b_ready': False,
            'pgvector_available': HAS_PGVECTOR,
            'embedding_model': EMBEDDING_MODEL,
        }
