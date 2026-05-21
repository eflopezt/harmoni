"""Modelos para cumplimiento DS 009-2011-TR: consentimiento + acuse."""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documentos', '0011_logactividadtrabajador'),
        ('personal', '0001_initial'),
        ('nominas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentimientoBoletaElectronica',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('aceptado', models.BooleanField(default=False)),
                ('fecha_aceptacion', models.DateTimeField(null=True, blank=True)),
                ('ip_aceptacion', models.GenericIPAddressField(null=True, blank=True)),
                ('user_agent', models.CharField(max_length=500, blank=True)),
                ('aviso_version', models.CharField(
                    max_length=20, blank=True,
                    help_text='Versión del texto de aviso aceptado',
                )),
                ('revocado', models.BooleanField(default=False)),
                ('fecha_revocacion', models.DateTimeField(null=True, blank=True)),
                ('motivo_revocacion', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('personal', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='consentimiento_boleta_electronica',
                    to='personal.personal',
                )),
            ],
            options={
                'verbose_name': 'Consentimiento Boleta Electrónica',
                'verbose_name_plural': 'Consentimientos Boleta Electrónica',
            },
        ),
        migrations.CreateModel(
            name='AcuseReciboBoleta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('fecha_confirmacion', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('ip', models.GenericIPAddressField(null=True, blank=True)),
                ('user_agent', models.CharField(max_length=500, blank=True)),
                ('hash_boleta', models.CharField(
                    max_length=32, blank=True,
                    help_text='Hash de integridad de la boleta al momento de confirmar',
                )),
                ('personal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='acuses_recibo',
                    to='personal.personal',
                )),
                ('registro_nomina', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='acuse_recibo',
                    to='nominas.registronomina',
                )),
            ],
            options={
                'verbose_name': 'Acuse de Recibo de Boleta',
                'verbose_name_plural': 'Acuses de Recibo de Boleta',
                'ordering': ['-fecha_confirmacion'],
            },
        ),
    ]
