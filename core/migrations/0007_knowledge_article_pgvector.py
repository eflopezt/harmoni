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


def _conditional_hnsw_sql(apps, schema_editor):
    """Crear el indice HNSW solo en Postgres con pgvector."""
    if schema_editor.connection.vendor != 'postgresql':
        return
    if not HAS_PGVECTOR:
        return
    try:
        schema_editor.execute(
            'CREATE INDEX IF NOT EXISTS "ka_embedding_hnsw_idx" '
            'ON "core_knowledgearticle" USING hnsw '
            '(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)'
        )
    except Exception:
        # No romper migracion si por algun motivo pgvector no esta listo
        pass


def _conditional_hnsw_sql_reverse(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    try:
        schema_editor.execute('DROP INDEX IF EXISTS "ka_embedding_hnsw_idx"')
    except Exception:
        pass


def _make_operations():
    return [
        migrations.AddField(
            model_name='knowledgearticle',
            name='embedding',
            field=_make_field(),
        ),
        migrations.RunPython(
            _conditional_hnsw_sql,
            reverse_code=_conditional_hnsw_sql_reverse,
        ),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_knowledge_article_embedding_json'),
    ]

    operations = _make_operations()
