from decimal import Decimal

import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('personal', '0001_initial'),
        ('nominas', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='DescuentoPlanilla',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('causal', models.CharField(
                    max_length=25,
                    choices=[
                        ('ROTURA_HERRAMIENTA', 'Rotura / pérdida de herramienta o equipo'),
                        ('REPOSICION_UNIFORME', 'Reposición de uniforme o fotocheck'),
                        ('CONSUMO_INTERNO', 'Consumo de insumos o productos'),
                        ('MULTA_INTERNA', 'Multa o sanción interna'),
                        ('EMBARGO_JUDICIAL', 'Embargo judicial'),
                        ('PENSION_ALIMENTICIA', 'Pensión alimenticia (orden judicial)'),
                        ('DEVOLUCION', 'Devolución de gastos personales'),
                        ('ADELANTO_EFECTIVO', 'Adelanto en efectivo (no formal)'),
                        ('OTROS', 'Otros'),
                    ],
                    verbose_name='Causal del Descuento',
                )),
                ('detalle', models.TextField(verbose_name='Detalle / Descripción')),
                ('monto_total', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                    verbose_name='Monto Total a Descontar (S/)',
                )),
                ('num_cuotas', models.PositiveSmallIntegerField(
                    default=1,
                    validators=[
                        django.core.validators.MinValueValidator(1),
                        django.core.validators.MaxValueValidator(36),
                    ],
                    verbose_name='N° de Cuotas',
                )),
                ('cuota_mensual', models.DecimalField(
                    max_digits=10, decimal_places=2, null=True, blank=True,
                    verbose_name='Cuota Mensual (S/)',
                )),
                ('fecha_registro', models.DateField(
                    default=django.utils.timezone.now,
                    verbose_name='Fecha de Registro',
                )),
                ('fecha_inicio_descuento', models.DateField(
                    null=True, blank=True,
                    verbose_name='Inicio del Descuento',
                )),
                ('estado', models.CharField(
                    max_length=12, default='PENDIENTE', db_index=True,
                    choices=[
                        ('BORRADOR', 'Borrador'),
                        ('PENDIENTE', 'Pendiente Aprobación'),
                        ('APROBADO', 'Aprobado'),
                        ('EN_CURSO', 'En Curso'),
                        ('PAGADO', 'Pagado / Liquidado'),
                        ('ANULADO', 'Anulado'),
                    ],
                )),
                ('requiere_consentimiento', models.BooleanField(
                    default=True, verbose_name='Requiere Consentimiento Escrito',
                )),
                ('consentimiento_firmado', models.BooleanField(
                    default=False, verbose_name='Consentimiento Firmado',
                )),
                ('documento_soporte', models.FileField(
                    upload_to='descuentos/%Y/%m/', null=True, blank=True,
                    verbose_name='Documento de Soporte',
                )),
                ('fecha_aprobacion', models.DateField(null=True, blank=True)),
                ('observaciones', models.TextField(blank=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('personal', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='descuentos',
                    to='personal.personal',
                    verbose_name='Trabajador',
                )),
                ('solicitado_por', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='descuentos_solicitados',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('aprobado_por', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='descuentos_aprobados',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Descuento por Planilla',
                'verbose_name_plural': 'Descuentos por Planilla',
                'ordering': ['-fecha_registro', '-id'],
            },
        ),
        migrations.AddIndex(
            model_name='DescuentoPlanilla',
            index=models.Index(fields=['personal', 'estado'], name='desc_personal_estado_idx'),
        ),
        migrations.AddIndex(
            model_name='DescuentoPlanilla',
            index=models.Index(fields=['estado', 'fecha_inicio_descuento'], name='desc_estado_inicio_idx'),
        ),
        migrations.CreateModel(
            name='AplicacionDescuento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('periodo_anio', models.PositiveSmallIntegerField()),
                ('periodo_mes', models.PositiveSmallIntegerField()),
                ('monto_aplicado', models.DecimalField(max_digits=10, decimal_places=2)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('descuento', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='aplicaciones',
                    to='descuentos.descuentoplanilla',
                )),
                ('registro_nomina', models.ForeignKey(
                    null=True, blank=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='descuentos_aplicados',
                    to='nominas.registronomina',
                )),
            ],
            options={
                'verbose_name': 'Aplicación de Descuento',
                'verbose_name_plural': 'Aplicaciones de Descuento',
                'ordering': ['-periodo_anio', '-periodo_mes'],
                'unique_together': {('descuento', 'periodo_anio', 'periodo_mes')},
            },
        ),
    ]
