"""
Migración: ConfiguracionSistema (singleton) y ConceptoMapeoS10.

ConfiguracionSistema centraliza todas las reglas de negocio configurables:
  - ciclo HE (corte_planilla)
  - jornadas por condición
  - config Synkro (nombres de hojas, columnas)
  - notificaciones email
  - Claude API key para mapeo IA
  - nombres de conceptos S10

ConceptoMapeoS10 mapea códigos tareo → columnas CargaS10.
"""
from decimal import Decimal

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tareo", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionSistema",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("empresa_nombre", models.CharField(default="", max_length=200, verbose_name="Nombre de la Empresa")),
                ("ruc", models.CharField(blank=True, max_length=11, verbose_name="RUC")),
                ("dia_corte_planilla", models.PositiveSmallIntegerField(
                    default=20,
                    help_text="Día del mes en que cierra el ciclo de HE. Ej: 20",
                    verbose_name="Día de Corte de Planilla",
                )),
                ("regularizacion_activa", models.BooleanField(
                    default=True,
                    help_text="Si está activo, los descuentos entre el día (corte+1) y fin de mes se difieren al siguiente mes.",
                    verbose_name="Activar Regularización de Fin de Mes",
                )),
                ("jornada_local_horas", models.DecimalField(
                    decimal_places=1, default=Decimal("8.5"), max_digits=4,
                    verbose_name="Jornada Local (h/día)",
                    help_text="Ej: 8.5 para personal LOCAL 7:30–17:00",
                )),
                ("jornada_foraneo_horas", models.DecimalField(
                    decimal_places=1, default=Decimal("11.0"), max_digits=4,
                    verbose_name="Jornada Foráneo (h/día)",
                    help_text="Ej: 11.0 para personal FORÁNEO 7:30–18:30",
                )),
                ("synkro_hoja_reloj", models.CharField(
                    default="Reloj", max_length=60,
                    verbose_name="Nombre Hoja Reloj en Synkro",
                    help_text="Nombre exacto de la hoja del reporte de reloj biométrico",
                )),
                ("synkro_hoja_papeletas", models.CharField(
                    default="Papeletas", max_length=60,
                    verbose_name="Nombre Hoja Papeletas en Synkro",
                )),
                ("reloj_col_dni", models.PositiveSmallIntegerField(default=0, verbose_name="Columna DNI en Reloj")),
                ("reloj_col_nombre", models.PositiveSmallIntegerField(default=1, verbose_name="Columna Nombre en Reloj")),
                ("reloj_col_condicion", models.PositiveSmallIntegerField(default=5, verbose_name="Columna Condición en Reloj")),
                ("reloj_col_tipo_trab", models.PositiveSmallIntegerField(default=6, verbose_name="Columna Tipo Trabajador en Reloj")),
                ("reloj_col_area", models.PositiveSmallIntegerField(default=7, verbose_name="Columna Área en Reloj")),
                ("reloj_col_cargo", models.PositiveSmallIntegerField(default=8, verbose_name="Columna Cargo en Reloj")),
                ("reloj_col_inicio_dias", models.PositiveSmallIntegerField(
                    default=9,
                    verbose_name="Primera Columna de Días en Reloj",
                    help_text="Índice de la primera columna con fechas/días (0-based)",
                )),
                ("email_habilitado", models.BooleanField(default=False, verbose_name="Habilitar Notificaciones por Email")),
                ("email_desde", models.EmailField(blank=True, verbose_name="Email Remitente")),
                ("email_asunto_semanal", models.CharField(
                    default="Tu resumen de asistencia semanal — {empresa}",
                    max_length=200,
                    verbose_name="Asunto Email Semanal",
                )),
                ("email_dia_envio", models.PositiveSmallIntegerField(
                    default=0,
                    verbose_name="Día de Envío (0=Lun … 6=Dom)",
                )),
                ("anthropic_api_key", models.CharField(
                    blank=True, max_length=200,
                    verbose_name="Anthropic API Key",
                    help_text="Para detección inteligente de columnas en importaciones",
                )),
                ("ia_mapeo_activo", models.BooleanField(
                    default=False,
                    verbose_name="Activar Mapeo IA de Columnas",
                    help_text="Usa Claude API para detectar columnas en archivos desconocidos",
                )),
                ("s10_nombre_concepto_he25", models.CharField(
                    default="HORAS EXTRAS 25%", max_length=100,
                    verbose_name="Nombre Concepto HE 25% en S10",
                )),
                ("s10_nombre_concepto_he35", models.CharField(
                    default="HORAS EXTRAS 35%", max_length=100,
                    verbose_name="Nombre Concepto HE 35% en S10",
                )),
                ("s10_nombre_concepto_he100", models.CharField(
                    default="HORAS EXTRAS 100%", max_length=100,
                    verbose_name="Nombre Concepto HE 100% en S10",
                )),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                ("actualizado_por", models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    verbose_name="Actualizado por",
                )),
            ],
            options={
                "verbose_name": "Configuración del Sistema",
                "verbose_name_plural": "Configuración del Sistema",
            },
        ),
        migrations.CreateModel(
            name="ConceptoMapeoS10",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo_tareo", models.CharField(
                    max_length=20,
                    verbose_name="Código Tareo",
                    help_text="Ej: HE25, HE35, HE100, DM, LF, LSG, FA, VAC",
                )),
                ("nombre_concepto_s10", models.CharField(
                    max_length=150,
                    verbose_name="Nombre Concepto S10",
                    help_text="Nombre exacto de la columna en el archivo CargaS10",
                )),
                ("tipo_valor", models.CharField(
                    choices=[
                        ("HORAS", "Horas (decimal)"),
                        ("DIAS", "Días (entero)"),
                        ("MONTO", "Monto S/ (decimal)"),
                    ],
                    default="HORAS",
                    max_length=10,
                    verbose_name="Tipo de Valor",
                )),
                ("activo", models.BooleanField(default=True, verbose_name="Activo")),
                ("descripcion", models.CharField(blank=True, max_length=200, verbose_name="Descripción")),
            ],
            options={
                "verbose_name": "Mapeo Concepto S10",
                "verbose_name_plural": "Mapeos de Conceptos S10",
                "ordering": ["codigo_tareo"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="conceptomapeos10",
            unique_together={("codigo_tareo", "nombre_concepto_s10")},
        ),
    ]
