"""
knowledge_service.py — Motor de búsqueda de la base de conocimiento IA.

FASE A (actual): búsqueda por keywords con PostgreSQL ilike.
  - Sin dependencias extra, funciona en SQLite dev y PostgreSQL prod.
  - Tokeniza la pregunta del usuario, busca en título + contenido + tags.
  - Devuelve artículos ordenados por prioridad.

FASE B (futura, pgvector): reemplazar `search_knowledge()` con:
  1. embed(query) → vector[1536]  (text-embedding-3-small o similar)
  2. KnowledgeArticle.objects.order_by(L2Distance('embedding', vector))[:k]
  - Todo lo demás (get_knowledge_context, inyección en system prompt) queda igual.

Uso:
    from core.knowledge_service import get_knowledge_context
    ctx = get_knowledge_context("¿Cuántos días de vacaciones corresponden?")
    # ctx es un string markdown listo para inyectar en el system prompt
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache

logger = logging.getLogger('harmoni.knowledge')

# Palabras vacías en español que se ignoran para la búsqueda
_STOPWORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'al', 'en', 'con', 'por', 'para', 'que',
    'es', 'son', 'fue', 'era', 'ser', 'hay', 'hay', 'tiene',
    'me', 'se', 'le', 'lo', 'mi', 'tu', 'su',
    'como', 'cuando', 'donde', 'cuanto', 'cuantos',
    'cuál', 'cual', 'qué', 'que', 'quién', 'quien',
    'más', 'mas', 'muy', 'bien', 'mal', 'todo', 'cada',
}


def _tokenize(text: str) -> list[str]:
    """Extrae palabras significativas (>3 chars, no stopwords)."""
    words = re.findall(r'\w+', text.lower())
    return [w for w in words if len(w) > 3 and w not in _STOPWORDS]


def _relevance_score(art, tokens: list[str]) -> int:
    """
    Score rápido por número de tokens que aparecen en título y tags.
    Título y tags tienen más peso que el cuerpo del artículo.
    Un match en título vale 3 pts, en tags vale 2 pts.
    """
    title  = art.titulo.lower()
    tags   = art.tags.lower()
    score  = 0
    for t in tokens:
        if t in title:
            score += 3
        if t in tags:
            score += 2
    return score


def search_knowledge(query: str, limit: int = 5) -> list[dict]:
    """
    FASE A: Búsqueda por keywords con re-ranking por relevancia.

    1. Filtra por OR de tokens en título / contenido / tags.
    2. Recupera hasta limit×3 candidatos (ordenados por prioridad).
    3. Re-rankea en Python: tokens en título/tags dan más peso.
    4. Devuelve los top-N más relevantes.

    Retorna lista de dicts: titulo, categoria, contenido (truncado a 800 chars).
    """
    from django.db.models import Q
    try:
        from core.models import KnowledgeArticle
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
        # Fetch more candidates so re-ranking can surface buried articles
        candidates = list(
            KnowledgeArticle.objects
            .filter(q, activo=True)
            .order_by('prioridad', 'id')
            .distinct()
            [: limit * 4]
        )
    except Exception as e:
        logger.warning('knowledge_service.search_knowledge error: %s', e)
        return []

    # Re-rank: higher score first, then lower prioridad number first
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
        })

    return result


def get_knowledge_context(query: str, limit: int = 4) -> str:
    """
    Retorna un bloque con artículos relevantes para inyectar en el system prompt.

    El framing es intencional: le dice al modelo que use el conocimiento como
    expertise propio, no que lo cite como "base de conocimiento" o "normativa interna".
    Así las respuestas suenan naturales y expertas, no mecánicas.

    Si no hay artículos relevantes, retorna string vacío (sin ruido en el prompt).
    """
    articles = search_knowledge(query, limit=limit)
    if not articles:
        return ''

    # Framing natural: el modelo integra esto como expertise propio,
    # no como fuente externa a citar textualmente.
    lines = [
        'Normativa y políticas aplicables (aplícalas como expertise propio; '
        'cita solo el decreto o artículo cuando corresponda, no menciones '
        '"base de conocimiento" ni reproduzcas párrafos enteros):'
    ]
    for art in articles:
        lines.append(f'\n• {art["titulo"]} ({art["categoria"]}):')
        lines.append(art['contenido'])

    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# FASE B: upgrade path a pgvector (implementar cuando se active Fase 4.4)
# ─────────────────────────────────────────────────────────────────────────────
#
# 1. Instalar: pip install pgvector openai
# 2. Activar extensión en PostgreSQL: CREATE EXTENSION vector;
# 3. Agregar campo al modelo:
#       from pgvector.django import VectorField
#       embedding = VectorField(dimensions=1536, null=True)
# 4. Crear función de embedding:
#       from openai import OpenAI
#       _oai = OpenAI(api_key=settings.OPENAI_API_KEY)
#       def embed(text: str) -> list[float]:
#           resp = _oai.embeddings.create(input=text, model='text-embedding-3-small')
#           return resp.data[0].embedding
# 5. Reemplazar search_knowledge() con:
#       from pgvector.django import CosineDistance
#       vector = embed(query)
#       articles = KnowledgeArticle.objects.order_by(
#           CosineDistance('embedding', vector)
#       ).filter(activo=True)[:limit]
# 6. Script de indexación (ejecutar una vez + al guardar nuevos artículos):
#       for art in KnowledgeArticle.objects.all():
#           art.embedding = embed(art.titulo + '\n' + art.contenido)
#           art.save(update_fields=['embedding'])
# ─────────────────────────────────────────────────────────────────────────────
