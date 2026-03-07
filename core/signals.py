"""
core/signals.py — Señales Django para el módulo Core.

Incluye auto-embedding de KnowledgeArticles cuando se crean o actualizan.
El embedding se calcula en background (thread) para no bloquear el guardado.
"""
from __future__ import annotations

import json
import logging
import threading

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger('harmoni.knowledge')


def _embed_article_async(article_pk: int, text: str) -> None:
    """
    Calcula y guarda el embedding de un artículo en un thread separado.
    No bloquea la respuesta HTTP del admin.
    """
    try:
        from core.knowledge_service import embed_text, _get_openai_api_key
        from core.models import KnowledgeArticle

        api_key = _get_openai_api_key()
        if not api_key:
            return  # No hay API key configurada — silencioso, no es un error

        vec = embed_text(text, api_key=api_key)
        if vec is None:
            logger.warning('auto-embed: embed_text retornó None para artículo pk=%s', article_pk)
            return

        # Actualizar solo el campo embedding_json (evitar re-trigger de señal)
        KnowledgeArticle.objects.filter(pk=article_pk).update(
            embedding_json=json.dumps(vec)
        )
        logger.info('auto-embed: embedding calculado para artículo pk=%s', article_pk)

    except Exception as exc:
        logger.warning('auto-embed: error en artículo pk=%s: %s', article_pk, exc)


@receiver(post_save, sender='core.KnowledgeArticle')
def auto_embed_knowledge_article(sender, instance, created: bool, **kwargs):
    """
    Señal post_save en KnowledgeArticle.

    Cuando se crea o actualiza un artículo:
    - Si tiene API key configurada → calcula embedding en background (thread).
    - Si no hay API key → no hace nada (Phase A sigue funcionando).

    La actualización via `update_fields=['embedding_json']` NO re-dispara esta
    señal gracias al chequeo de 'update_fields' vs campos de contenido.
    """
    # Evitar loop si el guardado fue solo para actualizar embedding_json
    update_fields = kwargs.get('update_fields')
    if update_fields and set(update_fields) == {'embedding_json'}:
        return

    # Si el artículo está inactivo, no embeddear
    if not instance.activo:
        return

    # Texto a embeddear: título + contenido
    text = f'{instance.titulo}\n\n{instance.contenido}'

    # Lanzar en thread para no bloquear
    t = threading.Thread(
        target=_embed_article_async,
        args=(instance.pk, text),
        daemon=True,
        name=f'embed-article-{instance.pk}',
    )
    t.start()
