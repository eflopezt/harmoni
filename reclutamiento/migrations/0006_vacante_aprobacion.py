from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('reclutamiento', '0005_alter_postulacion_fuente'),
    ]

    operations = [
        migrations.AlterField(
            model_name='vacante',
            name='estado',
            field=models.CharField(
                choices=[
                    ('BORRADOR', 'Borrador'),
                    ('POR_APROBAR', 'Por aprobar'),
                    ('PUBLICADA', 'Publicada'),
                    ('EN_PROCESO', 'En Proceso'),
                    ('CUBIERTA', 'Cubierta'),
                    ('CANCELADA', 'Cancelada'),
                ],
                default='BORRADOR', max_length=20, verbose_name='Estado',
            ),
        ),
        migrations.AddField(
            model_name='vacante',
            name='justificacion',
            field=models.TextField(
                blank=True,
                help_text='Necesidad que sustenta la vacante (para aprobación)',
                verbose_name='Justificación del requerimiento',
            ),
        ),
        migrations.AddField(
            model_name='vacante',
            name='aprobada_por',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='vacantes_aprobadas',
                to=settings.AUTH_USER_MODEL,
                verbose_name='Aprobada por',
            ),
        ),
        migrations.AddField(
            model_name='vacante',
            name='fecha_aprobacion',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='Fecha de aprobación',
            ),
        ),
    ]
