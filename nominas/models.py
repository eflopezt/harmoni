"""
Módulo de Nóminas — Cálculo y Gestión de Planilla.

Base legal:
- DL 728: Ley de Productividad y Competitividad Laboral
- Ley 27735 + DS 005-2002-TR: Gratificaciones (2 × sueldo/año, bonif. extra 9%)
- DL 650 + DS 004-97-TR: CTS (1 sueldo/año, mayo y noviembre)
- DL 19990 + DL 25897 (SPP): ONP 13% / AFP 10% + comisión + seguro
- Art. 75° TUO Ley IR: IR 5ta categoría (retención mensual)
- DS 003-97-TR: RMV — Remuneración Mínima Vital
- Ley 29351: EsSalud 9% aporte empleador

UIT 2026: S/ 5,500  |  RMV 2025: S/ 1,025
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from personal.models import Personal


# ── Constantes Legales Perú 2026 ─────────────────────────────────────
UIT_2026 = Decimal('5500.00')   # DS 233-2025-EF
RMV_2025 = Decimal('1025.00')
ASIG_FAM = RMV_2025 * Decimal('0.10')   # S/ 102.50


# ══════════════════════════════════════════════════════════════════════
# CONCEPTOS REMUNERATIVOS
# Catálogo configurable de todos los conceptos que aparecen en planilla
# ══════════════════════════════════════════════════════════════════════

class ConceptoRemunerativo(models.Model):
    TIPO_CHOICES = [
        ('INGRESO',          'Ingreso'),
        ('DESCUENTO',        'Descuento trabajador'),
        ('APORTE_EMPLEADOR', 'Aporte empleador'),
    ]
    SUBTIPO_CHOICES = [
        ('REMUNERATIVO',    'Remunerativo'),
        ('NO_REMUNERATIVO', 'No remunerativo'),
        ('PROVISION',       'Provisión (Gratif/CTS)'),
    ]
    FORMULA_CHOICES = [
        ('FIJO',            'Monto fijo'),
        ('PORCENTAJE',      'Porcentaje de remuneración computable'),
        ('DIAS_TRABAJADOS', 'Proporcional a días trabajados (sueldo base)'),
        ('HE_25',           'Horas extra 25%'),
        ('HE_35',           'Horas extra 35%'),
        ('HE_100',          'Horas extra 100%'),
        ('AFP_APORTE',      'AFP — Aporte obligatorio 10%'),
        ('AFP_COMISION',    'AFP — Comisión flujo'),
        ('AFP_SEGURO',      'AFP — Prima de seguro'),
        ('ONP',             'ONP — Sistema Nacional 13%'),
        ('ESSALUD',         'EsSalud — Aporte empleador 9%'),
        ('IR_5TA',          'IR 5ta categoría (retención)'),
        ('GRATIFICACION',   'Gratificación (julio/dic)'),
        ('CTS',             'CTS (mayo/nov)'),
        ('MANUAL',          'Entrada manual'),
    ]

    codigo     = models.SlugField(max_length=30, unique=True)
    nombre     = models.CharField(max_length=150)
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    subtipo    = models.CharField(max_length=20, choices=SUBTIPO_CHOICES, default='REMUNERATIVO')
    formula    = models.CharField(max_length=20, choices=FORMULA_CHOICES, default='FIJO')
    porcentaje = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal('0.00'),
        help_text='Para fórmula PORCENTAJE: valor en %. Ej: 10 = 10%',
    )

    # Afectaciones legales
    afecto_essalud = models.BooleanField(default=False)
    afecto_renta   = models.BooleanField(default=False)
    afecto_cts     = models.BooleanField(default=False)
    afecto_gratif  = models.BooleanField(default=False)

    es_sistema = models.BooleanField(default=False, help_text='Protegido — no eliminar.')
    activo     = models.BooleanField(default=True)
    orden      = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Concepto Remunerativo'
        verbose_name_plural = 'Conceptos Remunerativos'
        ordering = ['tipo', 'orden', 'nombre']

    def __str__(self):
        return f'[{self.codigo}] {self.nombre}'


# ══════════════════════════════════════════════════════════════════════
# PERÍODO DE NÓMINA
# ══════════════════════════════════════════════════════════════════════

class PeriodoNomina(models.Model):
    TIPO_CHOICES = [
        ('REGULAR',       'Planilla Regular'),
        ('GRATIFICACION', 'Gratificación'),
        ('CTS',           'CTS'),
        ('UTILIDADES',    'Utilidades'),
        ('LIQUIDACION',   'Liquidación'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR',  'Borrador'),
        ('CALCULADO', 'Calculado'),
        ('APROBADO',  'Aprobado'),
        ('CERRADO',   'Cerrado'),
        ('ANULADO',   'Anulado'),
    ]

    tipo         = models.CharField(max_length=15, choices=TIPO_CHOICES, default='REGULAR')
    anio         = models.SmallIntegerField()
    mes          = models.SmallIntegerField(help_text='1-12')
    descripcion  = models.CharField(max_length=200, blank=True)
    fecha_inicio = models.DateField()
    fecha_fin    = models.DateField()
    fecha_pago   = models.DateField(null=True, blank=True)
    estado       = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    empresa      = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='periodos_nomina',
        verbose_name='Empresa',
    )

    # Totales (calculados al generar)
    total_trabajadores   = models.SmallIntegerField(default=0)
    total_bruto          = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_descuentos     = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_neto           = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    total_costo_empresa  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               help_text='Neto + EsSalud + SCTR empleador')

    generado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    generado_en  = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    aprobado_en  = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Período de Nómina'
        verbose_name_plural = 'Períodos de Nómina'
        ordering = ['-anio', '-mes', 'tipo']
        unique_together = [['tipo', 'anio', 'mes']]

    def __str__(self):
        return self.descripcion or f'{self.get_tipo_display()} {self.mes:02d}/{self.anio}'

    @property
    def mes_nombre(self):
        MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return MESES[self.mes] if 1 <= self.mes <= 12 else ''

    @property
    def color_estado(self):
        return {
            'BORRADOR': 'secondary', 'CALCULADO': 'info',
            'APROBADO': 'primary',   'CERRADO': 'success', 'ANULADO': 'muted',
        }.get(self.estado, 'secondary')


# ══════════════════════════════════════════════════════════════════════
# REGISTRO DE NÓMINA (por empleado × período)
# ══════════════════════════════════════════════════════════════════════

class RegistroNomina(models.Model):
    ESTADO_CHOICES = [
        ('CALCULADO', 'Calculado'),
        ('REVISADO',  'Revisado'),
        ('APROBADO',  'Aprobado'),
        ('OBSERVADO', 'Observado'),
    ]

    periodo  = models.ForeignKey(PeriodoNomina, on_delete=models.CASCADE, related_name='registros')
    personal = models.ForeignKey(Personal, on_delete=models.PROTECT, related_name='nominas')

    # Snapshot de datos del trabajador al momento del cálculo (inmutable)
    sueldo_base     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    regimen_pension = models.CharField(max_length=12, default='AFP')
    afp             = models.CharField(max_length=20, blank=True)
    grupo           = models.CharField(max_length=10, blank=True)

    # Asistencia del período
    dias_trabajados = models.SmallIntegerField(default=30)
    dias_descanso   = models.SmallIntegerField(default=0)
    dias_falta      = models.SmallIntegerField(default=0)
    horas_extra_25  = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    horas_extra_35  = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))
    horas_extra_100 = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0'))

    # Flags y montos manuales
    asignacion_familiar  = models.BooleanField(default=False)
    descuento_prestamo   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    otros_ingresos       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    otros_descuentos     = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    # Totales calculados
    total_ingresos        = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    total_descuentos      = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    neto_a_pagar          = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    aporte_essalud        = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    costo_total_empresa   = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))

    estado        = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='CALCULADO')
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Registro de Nómina'
        verbose_name_plural = 'Registros de Nómina'
        ordering = ['personal__apellidos_nombres']
        unique_together = [['periodo', 'personal']]

    def __str__(self):
        return f'{self.personal} — {self.periodo}'


class LineaNomina(models.Model):
    """Una línea (concepto × monto) del registro. = una fila de la boleta."""
    registro  = models.ForeignKey(RegistroNomina, on_delete=models.CASCADE, related_name='lineas')
    concepto  = models.ForeignKey(ConceptoRemunerativo, on_delete=models.PROTECT)

    base_calculo        = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    porcentaje_aplicado = models.DecimalField(max_digits=7, decimal_places=4, default=Decimal('0'))
    monto               = models.DecimalField(max_digits=12, decimal_places=2)
    observacion         = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'Línea de Nómina'
        verbose_name_plural = 'Líneas de Nómina'
        ordering = ['concepto__tipo', 'concepto__orden']

    def __str__(self):
        return f'{self.concepto.nombre}: S/ {self.monto}'


# ══════════════════════════════════════════════════════════════════════
# PRESUPUESTO DE PLANILLA
# Permite comparar proyección vs. presupuesto en el flujo de caja
# ══════════════════════════════════════════════════════════════════════

class PresupuestoPlanilla(models.Model):
    """
    Presupuesto mensual de planilla para flujo de caja proyectado.
    Permite definir montos presupuestados por mes/año y compararlos
    con la proyección calculada a partir del personal activo.
    """
    MESES_ES = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

    anio    = models.SmallIntegerField(verbose_name="Año")
    mes     = models.SmallIntegerField(verbose_name="Mes", help_text="1-12")
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='presupuestos_planilla',
        verbose_name='Empresa',
    )

    # Componentes presupuestados (alineados con engine de proyección)
    presup_rem_bruta     = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Rem. Bruta presupuestada")
    presup_cond_trabajo  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Cond. Trabajo/Hospedaje (presup.)")
    presup_alimentacion  = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Alimentación (presup.)")
    presup_essalud       = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="EsSalud/PLAME (presup.)")
    presup_gratif        = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Gratificaciones provisión (presup.)")
    presup_cts           = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="CTS provisión (presup.)")
    presup_liquidaciones = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Liquidaciones (presup.)")
    presup_total         = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'),
                                               verbose_name="Total desembolso presupuestado")

    observaciones = models.TextField(blank=True)
    creado_por    = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                      null=True, blank=True, related_name='+')
    creado_en     = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Presupuesto de Planilla'
        verbose_name_plural = 'Presupuestos de Planilla'
        ordering = ['-anio', '-mes']
        unique_together = [['anio', 'mes', 'empresa']]

    def __str__(self):
        label = self.MESES_ES[self.mes] if 1 <= self.mes <= 12 else str(self.mes)
        return f"Presupuesto Planilla {label}-{self.anio}"

    @property
    def mes_label(self):
        label = self.MESES_ES[self.mes] if 1 <= self.mes <= 12 else str(self.mes)
        return f"{label}-{str(self.anio)[2:]}"
