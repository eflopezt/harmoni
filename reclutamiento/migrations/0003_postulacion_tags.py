"""Tags JSONField en Postulacion (etiquetas power-user)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reclutamiento', '0002_postulacion_cv_idiomas_postulacion_cv_parsed_at_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='postulacion',
            name='tags',
            field=models.JSONField(
                blank=True,
                default=list,
                help_text='Lista de etiquetas (TAG_CHOICES codes) asignadas al candidato.',
                verbose_name='Etiquetas',
            ),
        ),
    ]
