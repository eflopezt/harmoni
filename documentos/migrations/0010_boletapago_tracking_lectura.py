# Generated for DS 009-2011-TR tracking — campos de lectura y canal de acceso
# en BoletaPago para la constancia de recepción.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0009_firmadigital_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='boletapago',
            name='user_agent',
            field=models.CharField(
                blank=True,
                help_text='User-Agent del navegador al momento de la lectura',
                max_length=500,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='boletapago',
            name='metodo_acceso',
            field=models.CharField(
                choices=[
                    ('PORTAL_WEB', 'Portal Web'),
                    ('EMAIL', 'Email'),
                    ('PDF_DESCARGA', 'Descarga PDF'),
                ],
                default='PORTAL_WEB',
                help_text='Canal por el que el trabajador accedió a la boleta',
                max_length=15,
            ),
        ),
    ]
