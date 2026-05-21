# Generated for ChecklistGastronomia (Harmoni)
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0033_personal_personal_empresa_estado_idx_and_more'),
        ('onboarding', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ChecklistGastronomia',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha_ingreso', models.DateField(verbose_name='Fecha de Ingreso')),
                ('contrato_firmado', models.BooleanField(default=False, verbose_name='Contrato firmado')),
                ('contrato_firmado_fecha', models.DateField(blank=True, null=True)),
                ('examen_medico', models.BooleanField(default=False, verbose_name='Examen médico ocupacional')),
                ('examen_medico_fecha', models.DateField(blank=True, null=True)),
                ('uniforme_entregado', models.BooleanField(default=False, verbose_name='Uniforme entregado')),
                ('uniforme_entregado_fecha', models.DateField(blank=True, null=True)),
                ('induccion_general', models.BooleanField(default=False, verbose_name='Inducción general')),
                ('induccion_general_fecha', models.DateField(blank=True, null=True)),
                ('bpm_certificado', models.BooleanField(default=False, verbose_name='Certificación BPM')),
                ('bpm_certificado_fecha', models.DateField(blank=True, null=True)),
                ('haccp_certificado', models.BooleanField(default=False, verbose_name='Certificación HACCP')),
                ('haccp_certificado_fecha', models.DateField(blank=True, null=True)),
                ('manipulacion_alimentos', models.BooleanField(default=False, verbose_name='Manipulación de alimentos')),
                ('manipulacion_alimentos_fecha', models.DateField(blank=True, null=True)),
                ('carne_sanitario', models.BooleanField(default=False, verbose_name='Carné sanitario')),
                ('carne_sanitario_fecha', models.DateField(blank=True, null=True)),
                ('evaluacion_30', models.BooleanField(default=False, verbose_name='Evaluación 30 días')),
                ('evaluacion_30_fecha', models.DateField(blank=True, null=True)),
                ('evaluacion_30_calificacion', models.PositiveIntegerField(blank=True, help_text='Calificación 1-10', null=True)),
                ('evaluacion_30_notas', models.TextField(blank=True)),
                ('evaluacion_60', models.BooleanField(default=False, verbose_name='Evaluación 60 días')),
                ('evaluacion_60_fecha', models.DateField(blank=True, null=True)),
                ('evaluacion_60_calificacion', models.PositiveIntegerField(blank=True, help_text='Calificación 1-10', null=True)),
                ('evaluacion_60_notas', models.TextField(blank=True)),
                ('evaluacion_90', models.BooleanField(default=False, verbose_name='Evaluación 90 días')),
                ('evaluacion_90_fecha', models.DateField(blank=True, null=True)),
                ('evaluacion_90_calificacion', models.PositiveIntegerField(blank=True, help_text='Calificación 1-10', null=True)),
                ('evaluacion_90_notas', models.TextField(blank=True)),
                ('completado', models.BooleanField(default=False, verbose_name='Completado')),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('personal', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='checklist_gastro',
                    to='personal.personal',
                    verbose_name='Trabajador',
                )),
                ('responsable', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='checklists_gastro',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Responsable',
                )),
            ],
            options={
                'verbose_name': 'Checklist de Onboarding Gastronomía',
                'verbose_name_plural': 'Checklists de Onboarding Gastronomía',
                'ordering': ['-fecha_ingreso'],
            },
        ),
    ]
