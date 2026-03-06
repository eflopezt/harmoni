from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('analytics', '0002_add_contratos_categoria'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DashboardWidget',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('titulo', models.CharField(max_length=200, verbose_name='Título')),
                ('chart_type', models.CharField(help_text='bar, line, doughnut, etc.', max_length=50, verbose_name='Tipo de gráfico')),
                ('data_source', models.CharField(help_text='areas, headcount, genero, etc.', max_length=100, verbose_name='Fuente de datos')),
                ('config_json', models.JSONField(default=dict, help_text='Spec completo del gráfico (labels, values, colors, etc.)', verbose_name='Configuración del gráfico')),
                ('posicion', models.PositiveIntegerField(default=0, verbose_name='Posición')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='dashboard_widgets', to=settings.AUTH_USER_MODEL, verbose_name='Usuario')),
            ],
            options={
                'verbose_name': 'Widget Dashboard',
                'verbose_name_plural': 'Widgets Dashboard',
                'ordering': ['posicion', '-creado_en'],
            },
        ),
    ]
