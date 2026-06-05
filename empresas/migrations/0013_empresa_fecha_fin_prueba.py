from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0012_planes_por_modulos'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='fecha_fin_prueba',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Fin de la prueba gratuita',
                help_text='Fecha de vencimiento del trial. Vacío = cuenta de pago (sin prueba).',
            ),
        ),
    ]
