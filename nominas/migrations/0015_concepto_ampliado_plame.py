"""
Amplía ConceptoRemunerativo con:
- descripcion, categoria, monto_fijo
- afecto_afp, afecto_onp, afecto_vacaciones
- codigo_plame, casilla_plame, codigo_tregistro
- creado_en, actualizado_en

Esto permite crear conceptos custom (vale canasta, movilidad, etc.) con
mapeo completo SUNAT y todas las afectaciones legales.
"""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0014_configuracionapertura_saldoaperturatrabajador'),
    ]

    operations = [
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='descripcion',
            field=models.TextField(blank=True, help_text='Explicación del concepto (visible en tooltip)'),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='categoria',
            field=models.CharField(
                choices=[
                    ('SUELDO',         'Sueldo y haberes'),
                    ('BONIFICACION',   'Bonificación'),
                    ('COMISION',       'Comisión'),
                    ('GRATIFICACION',  'Gratificación'),
                    ('ALIMENTACION',   'Alimentación / Vale canasta'),
                    ('MOVILIDAD',      'Movilidad'),
                    ('REPRESENTACION', 'Representación'),
                    ('FAMILIAR',       'Asignación familiar / escolar'),
                    ('PROPINAS',       'Propinas y recargo consumo'),
                    ('OTROS_ING',      'Otros ingresos'),
                    ('IMPUESTO',       'Impuestos / Retenciones'),
                    ('APORTE',         'Aportes (AFP/ONP/ESSALUD)'),
                    ('DESCUENTO',      'Descuentos varios'),
                    ('PROVISION',      'Provisiones (CTS, gratif)'),
                    ('OTRO',           'Otro'),
                ],
                default='OTRO', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='monto_fijo',
            field=models.DecimalField(
                decimal_places=2, default=Decimal('0.00'),
                help_text='Para fórmula FIJO: monto en S/ que aplica por defecto. Ej: 200 (Vale canasta)',
                max_digits=10,
            ),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='afecto_afp',
            field=models.BooleanField(default=False, verbose_name='Afecto AFP (10% + comisión + prima)'),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='afecto_onp',
            field=models.BooleanField(default=False, verbose_name='Afecto ONP 13%'),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='afecto_vacaciones',
            field=models.BooleanField(default=False, verbose_name='Afecto Vacaciones truncas'),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='codigo_plame',
            field=models.CharField(
                blank=True,
                help_text='Código SUNAT del concepto para PLAME. Ej: 0121 = Sueldos básicos. Ver tabla SUNAT.',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='casilla_plame',
            field=models.CharField(
                blank=True,
                help_text='Casilla/columna del archivo plano PLAME donde sumar este concepto',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='codigo_tregistro',
            field=models.CharField(
                blank=True,
                help_text='Código T-Registro SUNAT (si aplica)',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='creado_en',
            field=models.DateTimeField(auto_now_add=True, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='conceptoremunerativo',
            name='actualizado_en',
            field=models.DateTimeField(auto_now=True, null=True, blank=True),
        ),
        # Cambiar afecto_essalud verbose_name (re-defino para que sea explícito)
        migrations.AlterField(
            model_name='conceptoremunerativo',
            name='afecto_essalud',
            field=models.BooleanField(default=False, verbose_name='Afecto ESSALUD 9%'),
        ),
        migrations.AlterField(
            model_name='conceptoremunerativo',
            name='afecto_renta',
            field=models.BooleanField(default=False, verbose_name='Afecto IR 5ta categoría'),
        ),
        migrations.AlterField(
            model_name='conceptoremunerativo',
            name='afecto_cts',
            field=models.BooleanField(default=False, verbose_name='Afecto CTS (mayo/nov)'),
        ),
        migrations.AlterField(
            model_name='conceptoremunerativo',
            name='afecto_gratif',
            field=models.BooleanField(default=False, verbose_name='Afecto Gratificación (jul/dic)'),
        ),
    ]
