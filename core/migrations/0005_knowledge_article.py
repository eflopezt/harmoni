from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_add_perfil_acceso'),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeArticle',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=300)),
                ('categoria', models.CharField(
                    choices=[
                        ('ley_laboral',   'Ley Laboral Perú'),
                        ('beneficios',    'Beneficios Sociales (CTS, Grat., etc.)'),
                        ('planilla',      'Planilla y Remuneraciones'),
                        ('asistencia',    'Asistencia y Jornada'),
                        ('vacaciones',    'Vacaciones y Permisos'),
                        ('disciplinaria', 'Procedimiento Disciplinario'),
                        ('politica_rrhh', 'Políticas RRHH Internas'),
                        ('proceso',       'Procesos del Sistema Harmoni'),
                        ('onboarding',    'Onboarding y Offboarding'),
                        ('faq',           'Preguntas Frecuentes'),
                        ('otro',          'Otro'),
                    ],
                    db_index=True,
                    max_length=20,
                )),
                ('contenido', models.TextField(
                    help_text='Texto en markdown. Sé específico y conciso — la IA usa esto como contexto directo.'
                )),
                ('tags', models.CharField(
                    blank=True,
                    help_text='Palabras clave separadas por coma. Mejoran la búsqueda. Ej: horas extra, 25%, artículo 10',
                    max_length=500,
                )),
                ('prioridad', models.PositiveSmallIntegerField(
                    default=5,
                    help_text='1=alta, 10=baja. Artículos de menor número aparecen primero en resultados.',
                )),
                ('activo', models.BooleanField(db_index=True, default=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Artículo de Conocimiento IA',
                'verbose_name_plural': 'Base de Conocimiento IA',
                'ordering': ['prioridad', 'categoria', 'titulo'],
            },
        ),
    ]
