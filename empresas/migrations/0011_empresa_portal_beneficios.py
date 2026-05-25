from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('empresas', '0010_empresa_plan'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='portal_beneficios_nombre',
            field=models.CharField(
                blank=True, default='', max_length=80,
                help_text='Ej: "Beneficios Stiler", "EDO Bienestar". Visible para el trabajador.',
                verbose_name='Nombre del portal de beneficios',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='portal_beneficios_url',
            field=models.URLField(
                blank=True, default='',
                help_text='URL externa a la que se redirige al trabajador desde el portal.',
                verbose_name='URL del portal de beneficios',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='portal_beneficios_logo_url',
            field=models.URLField(
                blank=True, default='',
                help_text='URL del logo para mostrar junto al botón. PNG/SVG recomendado.',
                verbose_name='Logo del portal de beneficios (opcional)',
            ),
        ),
    ]
