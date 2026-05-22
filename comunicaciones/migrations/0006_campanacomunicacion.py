# Generated for CampanaComunicacion (campañas masivas segmentadas)
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicaciones', '0005_add_notification_preferences_fields'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CampanaComunicacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('asunto', models.CharField(max_length=200, verbose_name='Asunto')),
                ('cuerpo', models.TextField(verbose_name='Cuerpo (HTML)')),
                ('canal', models.CharField(
                    choices=[('EMAIL', 'Email'), ('WHATSAPP', 'WhatsApp'),
                             ('IN_APP', 'In-App'),
                             ('MULTI', 'Email + WhatsApp + In-App')],
                    default='IN_APP', max_length=15,
                    verbose_name='Canal de envío')),
                ('estado', models.CharField(
                    choices=[('BORRADOR', 'Borrador'), ('PROGRAMADA', 'Programada'),
                             ('ENVIANDO', 'Enviando'), ('ENVIADA', 'Enviada'),
                             ('CANCELADA', 'Cancelada')],
                    default='BORRADOR', max_length=12, verbose_name='Estado')),
                ('filtro_area_ids', models.JSONField(
                    blank=True, default=list,
                    help_text='Lista de IDs de Area. Vacío = todas.',
                    verbose_name='IDs de áreas')),
                ('filtro_subarea_ids', models.JSONField(
                    blank=True, default=list, verbose_name='IDs de subáreas')),
                ('filtro_cargo', models.CharField(
                    blank=True, default='',
                    help_text='Substring match en cargo (icontains)',
                    max_length=100, verbose_name='Cargo (substring)')),
                ('filtro_grupo_tareo', models.CharField(
                    blank=True, default='',
                    help_text='STAFF | RCO | vacío para todos',
                    max_length=20, verbose_name='Grupo de tareo')),
                ('filtro_empresa_ids', models.JSONField(
                    blank=True, default=list, verbose_name='IDs de empresas')),
                ('filtro_solo_activos', models.BooleanField(
                    default=True, verbose_name='Solo trabajadores activos')),
                ('programada_para', models.DateTimeField(
                    blank=True, null=True, verbose_name='Programada para')),
                ('destinatarios_count', models.PositiveIntegerField(
                    default=0, verbose_name='Total destinatarios')),
                ('enviados_ok', models.PositiveIntegerField(
                    default=0, verbose_name='Enviados OK')),
                ('enviados_fallidos', models.PositiveIntegerField(
                    default=0, verbose_name='Fallidos')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('enviada_en', models.DateTimeField(
                    blank=True, null=True, verbose_name='Enviada en')),
                ('creado_por', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='campanas_creadas',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Creado por')),
            ],
            options={
                'verbose_name': 'Campaña de Comunicación',
                'verbose_name_plural': 'Campañas de Comunicación',
                'ordering': ['-creado_en'],
            },
        ),
        migrations.AddIndex(
            model_name='campanacomunicacion',
            index=models.Index(fields=['estado'],
                               name='com_campana_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='campanacomunicacion',
            index=models.Index(fields=['-creado_en'],
                               name='com_campana_creado_idx'),
        ),
    ]
