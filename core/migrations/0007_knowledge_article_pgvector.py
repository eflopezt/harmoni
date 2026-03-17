"""
Add pgvector VectorField to KnowledgeArticle for semantic search.

This migration is safe for both PostgreSQL (with pgvector) and SQLite (dev).
On SQLite, the field becomes a nullable BinaryField placeholder.
On PostgreSQL with pgvector, it creates a vector(1536) column with HNSW index.
"""
import django.db.models
from django.db import connection, migrations

# Try to import pgvector; if unavailable, use BinaryField as placeholder.
try:
    from pgvector.django import VectorField, HnswIndex
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


def _make_field():
    if HAS_PGVECTOR:
        return VectorField(
            dimensions=1536,
            null=True,
            blank=True,
            help_text='pgvector embedding (1536 dims). Auto-populated.',
        )
    return django.db.models.BinaryField(
        null=True,
        blank=True,
        editable=False,
        help_text='Placeholder — install pgvector for vector search.',
    )


def _make_operations():
    ops = [
        migrations.AddField(
            model_name='knowledgearticle',
            name='embedding',
            field=_make_field(),
        ),
    ]
    if HAS_PGVECTOR:
        ops.append(
            migrations.AddIndex(
                model_name='knowledgearticle',
                index=HnswIndex(
                    name='ka_embedding_hnsw_idx',
                    fields=['embedding'],
                    m=16,
                    ef_construction=64,
                    opclasses=['vector_cosine_ops'],
                ),
            ),
        )
    return ops


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_knowledge_article_embedding_json'),
    ]

    operations = _make_operations()
