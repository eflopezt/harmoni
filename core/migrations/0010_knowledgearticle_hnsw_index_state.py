"""Sincroniza el indice HNSW de KnowledgeArticle con el estado de Django."""
from django.db import migrations

try:
    from pgvector.django import HnswIndex

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


def crear_indice_hnsw(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql' or not HAS_PGVECTOR:
        return
    schema_editor.execute(
        'CREATE INDEX IF NOT EXISTS "ka_embedding_hnsw_idx" '
        'ON "core_knowledgearticle" USING hnsw '
        '(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64)'
    )


def eliminar_indice_hnsw(apps, schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute('DROP INDEX IF EXISTS "ka_embedding_hnsw_idx"')


def operaciones():
    if not HAS_PGVECTOR:
        return []
    return [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(crear_indice_hnsw, eliminar_indice_hnsw),
            ],
            state_operations=[
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
            ],
        ),
    ]


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0009_preferenciausuario_landing_default'),
    ]

    operations = operaciones()
