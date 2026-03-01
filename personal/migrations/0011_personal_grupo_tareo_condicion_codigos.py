"""
Migración: agrega campos de tareo al modelo Personal.

Nuevos campos:
- grupo_tareo   → STAFF (banco HE) | RCO (HE pagadas) | OTRO
- condicion     → FORANEO | LOCAL | LIMA
- codigo_sap    → código en SAP
- codigo_s10    → código en S10
- partida_control → partida de costo para CargaS10
- jornada_horas → horas de jornada diaria (para cálculo de HE)
"""
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("personal", "0010_alter_area_responsables"),
    ]

    operations = [
        migrations.AddField(
            model_name="personal",
            name="grupo_tareo",
            field=models.CharField(
                choices=[
                    ("STAFF", "RC Staff (HE compensatorias — banco de horas)"),
                    ("RCO", "RC Operativos (HE pagadas 25/35/100%)"),
                    ("OTRO", "Otro / No aplica"),
                ],
                default="STAFF",
                help_text="Determina cómo se tratan las HE: banco (STAFF) o pago (RCO)",
                max_length=10,
                verbose_name="Grupo Tareo",
            ),
        ),
        migrations.AddField(
            model_name="personal",
            name="condicion",
            field=models.CharField(
                blank=True,
                choices=[
                    ("FORANEO", "Foráneo (régimen acumulativo)"),
                    ("LOCAL", "Local (jornada fija en obra/sede)"),
                    ("LIMA", "Lima (jornada fija en oficina Lima)"),
                ],
                help_text="LOCAL = jornada fija | FORÁNEO = régimen acumulativo",
                max_length=10,
                verbose_name="Condición",
            ),
        ),
        migrations.AddField(
            model_name="personal",
            name="codigo_sap",
            field=models.CharField(
                blank=True,
                help_text="Código del trabajador en el sistema SAP",
                max_length=30,
                verbose_name="Código SAP",
            ),
        ),
        migrations.AddField(
            model_name="personal",
            name="codigo_s10",
            field=models.CharField(
                blank=True,
                help_text="Código del recurso en el sistema S10",
                max_length=30,
                verbose_name="Código S10",
            ),
        ),
        migrations.AddField(
            model_name="personal",
            name="partida_control",
            field=models.CharField(
                blank=True,
                help_text="Partida de costo para generación de CargaS10",
                max_length=100,
                verbose_name="Partida de Control",
            ),
        ),
        migrations.AddField(
            model_name="personal",
            name="jornada_horas",
            field=models.DecimalField(
                decimal_places=1,
                default=Decimal("8"),
                help_text="LOCAL=8.5, FORÁNEO=11.0. Usado para calcular HE.",
                max_digits=4,
                verbose_name="Horas de Jornada Diaria",
            ),
        ),
    ]
