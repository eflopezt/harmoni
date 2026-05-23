"""
Audit log de Conceptos Remunerativos.

Captura cambios para compliance + recuperación + diagnóstico de cálculos raros.
"""
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0015_concepto_ampliado_plame'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConceptoAuditLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('concepto_codigo', models.CharField(
                    help_text='Código del concepto (persiste aunque el concepto se elimine).',
                    max_length=30,
                )),
                ('concepto_nombre', models.CharField(blank=True, max_length=150)),
                ('accion', models.CharField(
                    choices=[
                        ('CREATE', 'Creado'),
                        ('UPDATE', 'Modificado'),
                        ('DELETE', 'Eliminado'),
                        ('ACTIVAR', 'Activado'),
                        ('DESACTIVAR', 'Desactivado'),
                        ('AUTOFIX', 'Auto-fix aplicado'),
                        ('TEMPLATE', 'Aplicado desde template'),
                        ('CSV_IMPORT', 'Importado desde CSV'),
                    ],
                    max_length=20,
                )),
                ('campos_cambiados', models.JSONField(
                    blank=True, default=dict,
                    help_text='{"campo": {"antes": X, "despues": Y}, ...}',
                )),
                ('usuario_username', models.CharField(
                    blank=True,
                    help_text='Username congelado (persiste aunque el usuario se elimine).',
                    max_length=150,
                )),
                ('fecha', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, max_length=300)),
                ('contexto', models.CharField(
                    blank=True,
                    help_text='URL o vista donde se originó el cambio.',
                    max_length=200,
                )),
                ('concepto', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='audit_log',
                    to='nominas.conceptoremunerativo',
                    help_text='Concepto afectado (null si fue eliminado).',
                )),
                ('usuario', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=models.deletion.SET_NULL,
                    related_name='+',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Audit log de concepto',
                'verbose_name_plural': 'Audit log de conceptos',
                'ordering': ['-fecha'],
            },
        ),
        migrations.AddIndex(
            model_name='conceptoauditlog',
            index=models.Index(fields=['-fecha'], name='nominas_con_fecha_67877d_idx'),
        ),
        migrations.AddIndex(
            model_name='conceptoauditlog',
            index=models.Index(
                fields=['concepto_codigo', '-fecha'],
                name='nominas_con_concept_6beef3_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='conceptoauditlog',
            index=models.Index(
                fields=['accion', '-fecha'],
                name='nominas_con_accion_c2d27e_idx',
            ),
        ),
    ]
