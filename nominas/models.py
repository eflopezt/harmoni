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

UIT 2026: S/ 5,500  |  RMV 2025: S/ 1,130
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from personal.models import Personal


# ── Constantes Legales Perú 2026 ─────────────────────────────────────
UIT_2026 = Decimal('5500.00')   # DS 233-2025-EF
RMV_2026 = Decimal('1130.00')
ASIG_FAM = RMV_2026 * Decimal('0.10')   # S/ 113.00


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

    CATEGORIA_CHOICES = [
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
    ]

    codigo     = models.SlugField(max_length=30, unique=True)
    nombre     = models.CharField(max_length=150)
    descripcion = models.TextField(blank=True, help_text='Explicación del concepto (visible en tooltip)')
    categoria  = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='OTRO')
    tipo       = models.CharField(max_length=20, choices=TIPO_CHOICES)
    subtipo    = models.CharField(max_length=20, choices=SUBTIPO_CHOICES, default='REMUNERATIVO')
    formula    = models.CharField(max_length=20, choices=FORMULA_CHOICES, default='FIJO')
    porcentaje = models.DecimalField(
        max_digits=7, decimal_places=4, default=Decimal('0.00'),
        help_text='Para fórmula PORCENTAJE: valor en %. Ej: 10 = 10%',
    )
    monto_fijo = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00'),
        help_text='Para fórmula FIJO: monto en S/ que aplica por defecto. Ej: 200 (Vale canasta)',
    )

    # ── Afectaciones legales (qué cargas paga este concepto) ──
    afecto_essalud     = models.BooleanField(default=False, verbose_name='Afecto ESSALUD 9%')
    afecto_afp         = models.BooleanField(default=False, verbose_name='Afecto AFP (10% + comisión + prima)')
    afecto_onp         = models.BooleanField(default=False, verbose_name='Afecto ONP 13%')
    afecto_renta       = models.BooleanField(default=False, verbose_name='Afecto IR 5ta categoría')
    afecto_cts         = models.BooleanField(default=False, verbose_name='Afecto CTS (mayo/nov)')
    afecto_gratif      = models.BooleanField(default=False, verbose_name='Afecto Gratificación (jul/dic)')
    afecto_vacaciones  = models.BooleanField(default=False, verbose_name='Afecto Vacaciones truncas')

    # ── Mapeo SUNAT / PLAME ──
    codigo_plame   = models.CharField(
        max_length=10, blank=True,
        help_text='Código SUNAT del concepto para PLAME. Ej: 0121 = Sueldos básicos. Ver tabla SUNAT.',
    )
    casilla_plame  = models.CharField(
        max_length=10, blank=True,
        help_text='Casilla/columna del archivo plano PLAME donde sumar este concepto',
    )
    codigo_tregistro = models.CharField(
        max_length=10, blank=True,
        help_text='Código T-Registro SUNAT (si aplica)',
    )

    es_sistema = models.BooleanField(default=False, help_text='Protegido — no eliminar.')
    activo     = models.BooleanField(default=True)
    orden      = models.PositiveSmallIntegerField(default=0)
    creado_en  = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True, null=True, blank=True)

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

    # ── Snapshot de parámetros legales al momento de crear el período ──
    # Congela el RMV/UIT vigentes cuando se calcula el período, para que
    # recálculos posteriores (si el admin cambia ConfiguracionSistema) usen
    # ese mismo valor y no distorsionen boletas históricas.
    rmv_snapshot = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('1130.00'),
        verbose_name='RMV congelada al período',
        help_text='RMV vigente al generar el período. Usada en asignación familiar '
                  'y otros cálculos derivados de la RMV.',
    )
    uit_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('5500.00'),
        verbose_name='UIT congelada al período',
        help_text='UIT vigente al generar el período. Usada en IR 5ta categoría.',
    )

    generado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    generado_en  = models.DateTimeField(null=True, blank=True)
    aprobado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                     null=True, blank=True, related_name='+')
    aprobado_en  = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    # ── Tracking de contabilización (audit perf 2026-05-20) ─────────────
    # Indica si el período ya fue exportado al sistema contable. Evita
    # doble-contabilización y permite filtrar "pendientes de contabilizar".
    contabilizado    = models.BooleanField(
        default=False,
        verbose_name='Contabilizado',
        help_text='Marcado al exportar el asiento a CONCAR/Siscont/SAP/SIRE.',
    )
    contabilizado_en = models.DateTimeField(null=True, blank=True)
    contabilizado_formato = models.CharField(
        max_length=20, blank=True,
        help_text='Formato usado: CONCAR, SISCONT, SAP_EXCEL, SIRE_PLE, SIGO.',
    )

    class Meta:
        verbose_name = 'Período de Nómina'
        verbose_name_plural = 'Períodos de Nómina'
        ordering = ['-anio', '-mes', 'tipo']
        constraints = [
            # Permite solo un período de cada tipo (REGULAR, GRATIFICACION, etc.) por mes,
            # excepto LIQUIDACION donde puede haber uno por empleado cesado en el mismo mes.
            models.UniqueConstraint(
                fields=['tipo', 'anio', 'mes'],
                condition=~Q(tipo='LIQUIDACION'),
                name='nominas_periodo_unique_no_liquidacion',
            ),
        ]

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

    # Hash de integridad: SHA-256 truncado del snapshot inmutable de la boleta.
    # Permite que el verificador público y la propia boleta declaren la misma huella.
    hash_integridad = models.CharField(
        max_length=16,
        blank=True,
        db_index=True,
        help_text='SHA-256 truncado de los datos críticos de la boleta (neto, fecha, DNI, periodo).'
    )

    class Meta:
        verbose_name = 'Registro de Nómina'
        verbose_name_plural = 'Registros de Nómina'
        ordering = ['personal__apellidos_nombres']
        unique_together = [['periodo', 'personal']]
        # Audit perf 2026-05-20: con 800 trabajadores las listas y reportes
        # filtran constantemente por periodo+estado y por personal+periodo.
        indexes = [
            models.Index(fields=['periodo', 'estado'], name='regnom_periodo_estado_idx'),
            models.Index(fields=['personal', '-periodo'], name='regnom_personal_periodo_idx'),
        ]

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
        # Audit perf: 800 reg x ~18 lineas = 14400 filas. Index (registro, concepto)
        # acelera la query "todas las lineas de este registro ordenadas por concepto".
        indexes = [
            models.Index(fields=['registro', 'concepto'], name='linom_reg_concepto_idx'),
        ]

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


# ══════════════════════════════════════════════════════════════════════
# PLAN DE PLANTILLA — Workforce Planning (SAP/Workday style)
# El presupuesto se asigna a PUESTOS, no a personas.
# Un puesto puede estar ocupado (→ Personal) o vacante.
# Soporta dos modos:
#   OBRA    → cada puesto tiene INICIO y FIN (proyecto con fases)
#   EMPRESA → puestos por área, horizonte indefinido o fiscal
# ══════════════════════════════════════════════════════════════════════

class PlanPlantilla(models.Model):
    """
    Plan de dotación presupuestada. Agrupa un conjunto de puestos (LineaPlan)
    con su horizonte temporal y datos de contexto (obra o área corporativa).
    """
    TIPO_CHOICES = [
        ('OBRA',    'Obra / Proyecto'),
        ('EMPRESA', 'Empresa / Área'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('APROBADO', 'Aprobado'),
        ('VIGENTE',  'Vigente'),
        ('CERRADO',  'Cerrado'),
    ]
    _BADGE = {'BORRADOR': 'secondary', 'APROBADO': 'primary',
              'VIGENTE': 'success',   'CERRADO':  'dark'}

    nombre       = models.CharField(max_length=200, verbose_name='Nombre del Plan')
    tipo         = models.CharField(max_length=10, choices=TIPO_CHOICES)
    descripcion  = models.TextField(blank=True, verbose_name='Descripción / Alcance')
    fecha_inicio = models.DateField(verbose_name='Inicio del horizonte')
    fecha_fin    = models.DateField(
        null=True, blank=True,
        verbose_name='Fin del horizonte',
        help_text='Vacío = indefinido. Para OBRA es obligatorio.',
    )
    estado   = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='BORRADOR')
    empresa  = models.ForeignKey(
        'empresas.Empresa', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='planes_plantilla',
    )
    area     = models.ForeignKey(
        'personal.Area', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Área responsable',
        help_text='Para EMPRESA: área/departamento que administra el plan.',
    )
    creado_por   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    creado_en    = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan de Plantilla'
        verbose_name_plural = 'Planes de Plantilla'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_display()})'

    @property
    def badge_estado(self):
        return self._BADGE.get(self.estado, 'secondary')

    @property
    def n_meses_horizonte(self):
        """Meses entre fecha_inicio y fecha_fin (inclusive). None si sin fecha_fin."""
        if not self.fecha_fin:
            return None
        from dateutil.relativedelta import relativedelta
        d = relativedelta(self.fecha_fin, self.fecha_inicio)
        return d.years * 12 + d.months + 1

    @property
    def total_cabezas(self):
        return sum(l.cantidad for l in self.lineas.all())

    @property
    def tiene_lineas(self):
        return self.lineas.exists()


class LineaPlan(models.Model):
    """
    Un puesto presupuestado dentro de un PlanPlantilla.
    Representa N posiciones del mismo cargo durante un rango de fechas.
    Puede estar opcionalmente asignado a una persona real (Personal).
    """
    AFP_CHOICES = [
        ('Habitat',   'Habitat'),
        ('Integra',   'Integra'),
        ('Prima',     'Prima'),
        ('Profuturo', 'Profuturo'),
    ]
    REGIMEN_CHOICES = [
        ('AFP',        'AFP'),
        ('ONP',        'ONP'),
        ('SIN_PENSION','Sin Régimen'),
    ]

    plan     = models.ForeignKey(PlanPlantilla, on_delete=models.CASCADE, related_name='lineas')
    cargo    = models.CharField(max_length=150, verbose_name='Cargo / Puesto')
    area     = models.ForeignKey(
        'personal.Area', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Área',
    )
    cantidad = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1)],
        verbose_name='N° de posiciones',
        help_text='Número de personas para este cargo en el plan.',
    )
    sueldo_base = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Sueldo base (por persona)',
    )
    asignacion_familiar = models.BooleanField(default=False, verbose_name='Asignación familiar')
    regimen_pension     = models.CharField(max_length=12, choices=REGIMEN_CHOICES, default='AFP')
    afp                 = models.CharField(
        max_length=20, choices=AFP_CHOICES, blank=True,
        help_text='Solo si régimen es AFP.',
    )
    cond_trabajo_mensual = models.DecimalField(
        max_digits=9, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Cond. Trabajo / Hospedaje (mensual, por persona)',
    )
    alimentacion_mensual = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Alimentación (mensual, por persona)',
    )
    fecha_inicio_puesto = models.DateField(verbose_name='Inicio del puesto')
    fecha_fin_puesto    = models.DateField(
        null=True, blank=True,
        verbose_name='Fin del puesto',
        help_text='Vacío = hasta el fin del plan.',
    )
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='lineas_plan',
        verbose_name='Persona asignada (opcional)',
        help_text='Si ya se sabe quién ocupa el puesto.',
    )
    notas = models.CharField(max_length=300, blank=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Línea de Plan'
        verbose_name_plural = 'Líneas de Plan'
        ordering = ['orden', 'cargo']

    def __str__(self):
        return f'{self.cargo} × {self.cantidad} ({self.plan.nombre})'

    def es_activo_en_mes(self, mes_inicio, mes_fin):
        """True si el puesto está activo durante algún día del mes."""
        if self.fecha_inicio_puesto > mes_fin:
            return False
        fin = self.fecha_fin_puesto or self.plan.fecha_fin
        if fin and fin < mes_inicio:
            return False
        return True


# ═══════════════════════════════════════════════════════════
#  RECARGA DE TARJETAS DE ALIMENTACIÓN
# ═══════════════════════════════════════════════════════════

class RecargaAlimentacion(models.Model):
    """
    Control de recargas mensuales de tarjetas de alimentación (Edenred, Sodexo).
    Cada registro = una recarga mensual para un empleado.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de Procesamiento'),
        ('PROCESADA', 'Procesada (enviada al proveedor)'),
        ('RECHAZADA', 'Rechazada'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='recargas_alimentacion')
    anio = models.PositiveSmallIntegerField(verbose_name='Año')
    mes = models.PositiveSmallIntegerField(verbose_name='Mes')
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Monto Recarga')
    comision = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name='Comisión Proveedor')
    total = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name='Total (monto + comisión)')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE')
    proveedor = models.CharField(
        max_length=50, default='EDENRED',
        verbose_name='Proveedor',
        help_text='Edenred, Sodexo, etc.')
    numero_tarjeta = models.CharField(
        max_length=30, blank=True, default='')
    procesado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('personal', 'anio', 'mes')]
        ordering = ['-anio', '-mes', 'personal__apellidos_nombres']
        verbose_name = 'Recarga de Alimentación'
        verbose_name_plural = 'Recargas de Alimentación'

    def __str__(self):
        return f'{self.personal} — {self.mes:02d}/{self.anio} — S/{self.monto}'

    def save(self, *args, **kwargs):
        self.total = self.monto + self.comision
        super().save(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════════
#  SALDOS DE APERTURA — Onboarding Express (no migración histórica)
# ═══════════════════════════════════════════════════════════════════

class SaldoAperturaTrabajador(models.Model):
    """Saldos iniciales de un trabajador al momento de arrancar Harmoni.

    Reemplaza la necesidad de migrar 12 meses de planillas históricas.
    Se llenan vía wizard /nominas/apertura/ con plantilla Excel.

    El engine de planilla consulta estos saldos para arrancar acumulados
    de CTS, gratificación, vacaciones, IR5 y préstamos vigentes.
    """
    personal = models.OneToOneField(
        Personal,
        on_delete=models.CASCADE,
        related_name='saldo_apertura',
    )
    fecha_corte = models.DateField(
        verbose_name='Fecha de corte',
        help_text='Fecha hasta la cual el sistema anterior procesó planilla. '
                  'Desde el día siguiente, Harmoni asume el cálculo.',
    )
    prov_cts = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Provisión CTS acumulada',
    )
    prov_gratificacion = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Provisión Gratificación',
    )
    prov_vacaciones = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Provisión Vacaciones',
    )
    dias_vacaciones_pendientes = models.IntegerField(
        default=0,
        verbose_name='Días vacaciones pendientes',
    )
    ir5_acumulado = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='IR 5ta acumulado del año',
    )
    prestamo_saldo = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Saldo préstamo vigente',
    )
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    class Meta:
        verbose_name = 'Saldo de Apertura'
        verbose_name_plural = 'Saldos de Apertura'
        ordering = ['personal__apellidos_nombres']

    def __str__(self):
        return f'Apertura {self.personal} @ {self.fecha_corte}'


class ConfiguracionApertura(models.Model):
    """Estado global del onboarding por empresa.

    Marca si la empresa ya completó el wizard de apertura y la fecha
    de corte usada como referencia.
    """
    empresa = models.OneToOneField(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='configuracion_apertura',
        null=True, blank=True,
        help_text='Vacío = configuración global (multi-empresa).',
    )
    fecha_corte = models.DateField()
    completado = models.BooleanField(default=False)
    total_trabajadores = models.IntegerField(default=0)
    creado_en = models.DateTimeField(auto_now_add=True)
    confirmado_en = models.DateTimeField(null=True, blank=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Configuración de Apertura'
        verbose_name_plural = 'Configuraciones de Apertura'

    def __str__(self):
        emp = self.empresa.razon_social if self.empresa else 'Global'
        return f'Apertura {emp} @ {self.fecha_corte}'


# ══════════════════════════════════════════════════════════════════════
# AUDIT LOG — Conceptos Remunerativos
# Trail de cambios para compliance + recuperación + diagnóstico
# ══════════════════════════════════════════════════════════════════════

class ConceptoAuditLog(models.Model):
    """
    Bitácora de cambios sobre ConceptoRemunerativo.

    Captura: quién, cuándo, qué campo, valor anterior y nuevo.
    Usado para:
    - Compliance fiscal (¿quién cambió afecto_renta antes del cierre?)
    - Recuperar configuración perdida ("vuelve esto a como estaba ayer")
    - Diagnóstico de cálculos raros ("¿cuándo bajó la tasa AFP?")
    """
    ACCION_CHOICES = [
        ('CREATE', 'Creado'),
        ('UPDATE', 'Modificado'),
        ('DELETE', 'Eliminado'),
        ('ACTIVAR', 'Activado'),
        ('DESACTIVAR', 'Desactivado'),
        ('AUTOFIX', 'Auto-fix aplicado'),
        ('TEMPLATE', 'Aplicado desde template'),
        ('CSV_IMPORT', 'Importado desde CSV'),
    ]

    # ¿En qué empresa ocurrió? (multi-tenant filter — ADR-001)
    empresa        = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text='Empresa del contexto en que se hizo el cambio. Null = global/sistema.',
    )

    # ¿Qué cambió?
    concepto       = models.ForeignKey(
        ConceptoRemunerativo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_log',
        help_text='Concepto afectado (null si fue eliminado).',
    )
    concepto_codigo = models.CharField(
        max_length=30,
        help_text='Código del concepto (persiste aunque el concepto se elimine).',
    )
    concepto_nombre = models.CharField(max_length=150, blank=True)

    # ¿Qué tipo de acción?
    accion         = models.CharField(max_length=20, choices=ACCION_CHOICES)

    # Detalle del cambio (JSON-ish: campo → {antes, despues})
    campos_cambiados = models.JSONField(
        default=dict, blank=True,
        help_text='{"campo": {"antes": X, "despues": Y}, ...}',
    )

    # ¿Quién y cuándo?
    usuario        = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    usuario_username = models.CharField(
        max_length=150, blank=True,
        help_text='Username congelado (persiste aunque el usuario se elimine).',
    )
    fecha          = models.DateTimeField(auto_now_add=True, db_index=True)

    # Contexto opcional
    ip             = models.GenericIPAddressField(null=True, blank=True)
    user_agent     = models.CharField(max_length=300, blank=True)
    contexto       = models.CharField(
        max_length=200, blank=True,
        help_text='URL o vista donde se originó el cambio.',
    )

    class Meta:
        verbose_name = 'Audit log de concepto'
        verbose_name_plural = 'Audit log de conceptos'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['concepto_codigo', '-fecha']),
            models.Index(fields=['accion', '-fecha']),
        ]

    def __str__(self):
        u = self.usuario_username or 'sistema'
        return f'[{self.fecha:%Y-%m-%d %H:%M}] {u} {self.get_accion_display()} {self.concepto_codigo}'

    @property
    def num_cambios(self):
        return len(self.campos_cambiados or {})

    @property
    def resumen_cambios(self):
        """Lista de strings cortos: 'afecto_essalud: False → True'."""
        if not self.campos_cambiados:
            return []
        items = []
        for campo, valores in (self.campos_cambiados or {}).items():
            antes = valores.get('antes', '—') if isinstance(valores, dict) else '—'
            despues = valores.get('despues', '—') if isinstance(valores, dict) else valores
            items.append(f'{campo}: {antes} → {despues}')
        return items


# ══════════════════════════════════════════════════════════════════════
# AGENTE IA NÓMINAS — Conversaciones, reintegros, audit
# ══════════════════════════════════════════════════════════════════════

class ConversacionAgenteIA(models.Model):
    """
    Sesión de chat con el agente IA de Nóminas.

    Cada conversación tiene un hilo de mensajes (MensajeAgenteIA).
    El agente puede ejecutar tools que modifican propuestas de reintegros.
    """
    usuario      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='conversaciones_nominas_ia',
    )
    empresa      = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    titulo       = models.CharField(
        max_length=200, blank=True,
        help_text='Título auto-generado a partir del primer mensaje',
    )
    contexto     = models.JSONField(
        default=dict, blank=True,
        help_text='Contexto persistente: trabajador en foco, período, etc.',
    )
    creada_en    = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizada_en = models.DateTimeField(auto_now=True)
    archivada    = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Conversación Agente IA'
        verbose_name_plural = 'Conversaciones Agente IA'
        ordering = ['-actualizada_en']

    def __str__(self):
        return f'{self.titulo or "Sin título"} ({self.usuario_id})'


class MensajeAgenteIA(models.Model):
    """Mensaje individual dentro de una conversación con el agente."""
    ROL_CHOICES = [
        ('user',      'Usuario'),
        ('assistant', 'Asistente IA'),
        ('tool',      'Tool (resultado de función)'),
        ('system',    'Sistema (instrucciones)'),
    ]

    conversacion = models.ForeignKey(
        ConversacionAgenteIA,
        on_delete=models.CASCADE,
        related_name='mensajes',
    )
    rol          = models.CharField(max_length=15, choices=ROL_CHOICES)
    contenido    = models.TextField()
    # Si rol='tool': nombre de la función y args + resultado
    tool_name    = models.CharField(max_length=80, blank=True)
    tool_args    = models.JSONField(default=dict, blank=True)
    tool_result  = models.JSONField(default=dict, blank=True)
    # Tokens consumidos por el modelo (para cost tracking)
    tokens_input  = models.PositiveIntegerField(default=0)
    tokens_output = models.PositiveIntegerField(default=0)
    modelo       = models.CharField(
        max_length=80, blank=True,
        help_text='ej: deepseek-chat, gemini-1.5-pro, gpt-4o-mini',
    )
    fecha        = models.DateTimeField(auto_now_add=True, db_index=True)
    # Si el mensaje propone una acción que requiere aprobación
    requiere_aprobacion = models.BooleanField(default=False)
    accion_propuesta    = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Mensaje Agente IA'
        verbose_name_plural = 'Mensajes Agente IA'
        ordering = ['fecha']

    def __str__(self):
        return f'[{self.rol}] {self.contenido[:60]}'


class ReintegroNomina(models.Model):
    """
    Reintegro a un trabajador por error o corrección de planilla anterior.

    Estados:
    - PROPUESTO: calculado por el agente o admin, aún no aplicado
    - APROBADO:  admin aprobó, pendiente de aplicar al próximo período
    - APLICADO:  se generó la línea en el período actual de planilla
    - REVERSADO: se canceló el reintegro (con motivo)
    """
    ESTADO_CHOICES = [
        ('PROPUESTO', 'Propuesto'),
        ('APROBADO',  'Aprobado'),
        ('APLICADO',  'Aplicado'),
        ('REVERSADO', 'Reversado'),
    ]

    MOTIVO_CHOICES = [
        ('ERROR_SUELDO',          'Error en sueldo base'),
        ('AUMENTO_RETROACTIVO',   'Aumento de sueldo retroactivo'),
        ('HE_NO_PAGADAS',         'Horas extra no pagadas'),
        ('ASIG_FAMILIAR_OMITIDA', 'Asignación familiar omitida'),
        ('BONIF_OMITIDA',         'Bonificación omitida'),
        ('GRATIF_MAL_CALCULADA',  'Gratificación mal calculada'),
        ('SENTENCIA_JUDICIAL',    'Sentencia judicial'),
        ('OTRO',                  'Otro (especificar)'),
    ]

    # ── Quién y por qué ──
    personal       = models.ForeignKey(
        'personal.Personal',
        on_delete=models.PROTECT,
        related_name='reintegros',
    )
    empresa        = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    motivo         = models.CharField(max_length=30, choices=MOTIVO_CHOICES)
    descripcion    = models.TextField(
        help_text='Justificación clara — irá en la boleta como detalle',
    )

    # ── Período de origen del error ──
    periodo_origen_anio = models.SmallIntegerField(
        help_text='Año del período donde ocurrió el error',
    )
    periodo_origen_mes  = models.SmallIntegerField(
        help_text='Mes del período donde ocurrió el error',
    )

    # ── Montos ──
    monto_que_se_pago = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Lo que el trabajador efectivamente recibió',
    )
    monto_correcto    = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Lo que debió haber recibido según corrección',
    )
    monto_reintegro   = models.DecimalField(
        max_digits=14, decimal_places=2,
        help_text='Diferencia a pagar (positiva) o a descontar (negativa)',
    )

    # ── Impacto fiscal (calculado por simular_impacto_aportes) ──
    impacto_ir_5ta    = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0'))
    impacto_aportes   = models.JSONField(
        default=dict, blank=True,
        help_text='ej: {"AFP_aporte": 50.00, "ESSALUD_emp": 27.00, ...}',
    )
    monto_neto_reintegro = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal('0'),
        help_text='Líquido después de descontar aportes adicionales',
    )

    # ── Período donde se va a aplicar (próxima planilla) ──
    periodo_aplicar = models.ForeignKey(
        'nominas.PeriodoNomina',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reintegros_aplicados',
        help_text='Período donde se generará la línea de reintegro',
    )
    linea_generada  = models.ForeignKey(
        'nominas.LineaNomina',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        help_text='Línea creada al aplicar el reintegro',
    )

    # ── Estado + audit ──
    estado          = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='PROPUESTO')
    propuesto_por   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reintegros_propuestos',
    )
    propuesto_por_ia = models.BooleanField(
        default=False,
        help_text='True si fue propuesto por el agente IA (vs admin manual)',
    )
    conversacion_ia = models.ForeignKey(
        ConversacionAgenteIA,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reintegros_propuestos',
    )
    aprobado_por    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reintegros_aprobados',
    )
    aprobado_en     = models.DateTimeField(null=True, blank=True)
    aplicado_en     = models.DateTimeField(null=True, blank=True)
    revertido_por   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reintegros_revertidos',
    )
    revertido_en    = models.DateTimeField(null=True, blank=True)
    motivo_reversion = models.TextField(blank=True)

    creado_en       = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en  = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reintegro de Nómina'
        verbose_name_plural = 'Reintegros de Nómina'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['personal', '-creado_en']),
            models.Index(fields=['estado', '-creado_en']),
        ]

    def __str__(self):
        signo = '+' if self.monto_reintegro >= 0 else ''
        return f'Reintegro {self.personal} {signo}S/{self.monto_reintegro} ({self.get_estado_display()})'

    @property
    def es_a_favor_trabajador(self):
        """True si el reintegro AUMENTA lo que recibe el trabajador."""
        return self.monto_reintegro > 0

    @property
    def es_descuento(self):
        """True si en realidad es un descuento (cobramos al trabajador algo que se pagó de más)."""
        return self.monto_reintegro < 0

    @property
    def periodo_origen_str(self):
        return f'{self.periodo_origen_mes:02d}/{self.periodo_origen_anio}'


class AuditAgenteIA(models.Model):
    """
    Bitácora de TODA acción del agente IA.

    Mucho más detallado que ConceptoAuditLog: registra cada tool call,
    cada input/output del modelo, cada decisión. Crítico para compliance.
    """
    ACCION_CHOICES = [
        ('CONSULTA_NORMATIVA',  'Consulta a normativa (RAG)'),
        ('OBTENER_BOLETA',      'Lectura de boleta histórica'),
        ('CALCULO_REINTEGRO',   'Cálculo de reintegro'),
        ('SIMULAR_IMPACTO',     'Simulación de impacto'),
        ('PROPONER_REINTEGRO',  'Propuesta de reintegro (estado PROPUESTO)'),
        ('APLICAR_REINTEGRO',   'Aplicación de reintegro (genera LineaNomina)'),
        ('REVERTIR_REINTEGRO',  'Reversión de reintegro'),
        ('CONVERSACION',        'Mensaje conversacional (sin tool)'),
        ('ERROR',               'Error / rechazo'),
    ]

    conversacion  = models.ForeignKey(
        ConversacionAgenteIA,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audits',
    )
    usuario       = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    accion        = models.CharField(max_length=30, choices=ACCION_CHOICES)
    detalle       = models.JSONField(default=dict, blank=True)
    fecha         = models.DateTimeField(auto_now_add=True, db_index=True)
    ip            = models.GenericIPAddressField(null=True, blank=True)
    exito         = models.BooleanField(default=True)
    error_mensaje = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Audit Agente IA'
        verbose_name_plural = 'Audit Agente IA'
        ordering = ['-fecha']
        indexes = [
            models.Index(fields=['-fecha']),
            models.Index(fields=['accion', '-fecha']),
        ]

    def __str__(self):
        return f'[{self.fecha:%Y-%m-%d %H:%M}] {self.get_accion_display()}'


# ══════════════════════════════════════════════════════════════════════
# LIQUIDACIÓN LABORAL — proceso unificado al cese
# ══════════════════════════════════════════════════════════════════════
# Modelo header que centraliza TODOS los conceptos que se le pagan a un
# trabajador cuando deja la empresa (vacaciones truncas, gratif trunca,
# CTS trunca, sueldo del mes en curso, HE no compensadas, indemnización
# por despido arbitrario, etc.) menos descuentos (préstamos, embargos).
#
# Reutiliza `engine.calcular_gratificacion` y `engine.calcular_cts` —
# NO duplica lógica. Sprint 1 según docs/internal/DISEÑO_LIQUIDACIONES_…
# ══════════════════════════════════════════════════════════════════════

class LiquidacionLaboral(models.Model):
    """
    Liquidación final al cese del trabajador.

    Se crea (a) manualmente desde la ficha del empleado o (b) automáticamente
    vía signal `post_save` en Personal cuando el estado cambia a 'Cesado'.

    Flujo de estados:
        BORRADOR → CALCULADA → APROBADA → FIRMADA → PAGADA → CERRADA
    """

    MOTIVO_CESE_CHOICES = [
        ('RENUNCIA',        'Renuncia voluntaria'),
        ('DESPIDO',         'Despido (causa justa)'),
        ('DESPIDO_ARB',     'Despido arbitrario (indemnización)'),
        ('MUTUO',           'Mutuo disenso'),
        ('CADUCIDAD',       'Caducidad de contrato'),
        ('JUBILACION',      'Jubilación'),
        ('FALLECIMIENTO',   'Fallecimiento'),
        ('PERIODO_PRUEBA',  'No supera período de prueba'),
    ]

    ESTADO_CHOICES = [
        ('BORRADOR',  'Borrador'),
        ('CALCULADA', 'Calculada'),
        ('APROBADA',  'Aprobada por RRHH'),
        ('FIRMADA',   'Firmada por trabajador'),
        ('PAGADA',    'Pagada'),
        ('CERRADA',   'Cerrada'),
    ]

    personal      = models.OneToOneField(
        Personal,
        on_delete=models.PROTECT,
        related_name='liquidacion',
        verbose_name='Trabajador cesado',
    )
    fecha_cese    = models.DateField(verbose_name='Fecha de cese')
    motivo_cese   = models.CharField(
        max_length=20,
        choices=MOTIVO_CESE_CHOICES,
        default='RENUNCIA',
        verbose_name='Motivo del cese',
    )
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')

    # ── Conceptos calculados (haberes) ───────────────────────────────────
    vacaciones_truncas = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='Vacaciones truncas')
    gratif_trunca      = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='Gratificación trunca')
    cts_trunca         = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='CTS trunca')
    sueldo_mes_curso   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='Sueldo del mes en curso')
    he_no_compensadas  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='Horas extra no compensadas')
    indemnizacion      = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0'),
        verbose_name='Indemnización por despido arbitrario',
        help_text='1.5 sueldos × año (máx 12 sueldos) — solo motivo DESPIDO_ARB. Art. 38 DS 003-97-TR.',
    )
    otros_pagos        = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                             verbose_name='Otros pagos')

    # ── Descuentos ───────────────────────────────────────────────────────
    prestamos_pendientes = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                               verbose_name='Préstamos pendientes')
    adelantos_pendientes = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                               verbose_name='Adelantos pendientes')
    embargo              = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                               verbose_name='Embargo judicial')
    otros_descuentos     = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                               verbose_name='Otros descuentos')

    # ── Totales ──────────────────────────────────────────────────────────
    total_bruto = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                      verbose_name='Total bruto (haberes)')
    total_neto  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'),
                                      verbose_name='Total neto (bruto − descuentos)')

    # ── Workflow ─────────────────────────────────────────────────────────
    estado       = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='BORRADOR',
        verbose_name='Estado', db_index=True,
    )
    aprobada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='liquidaciones_aprobadas',
        verbose_name='Aprobada por',
    )
    firmada_en   = models.DateTimeField(null=True, blank=True, verbose_name='Firmada el')
    pagada_en    = models.DateTimeField(null=True, blank=True, verbose_name='Pagada el')

    # ── Vínculos con boleta y workflow offboarding ───────────────────────
    registro_nomina = models.OneToOneField(
        'nominas.RegistroNomina',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='liquidacion_origen',
        verbose_name='Registro de nómina (boleta unificada)',
    )
    instancia_flujo = models.OneToOneField(
        'workflows.InstanciaFlujo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='liquidacion_origen',
        verbose_name='Instancia de flujo offboarding',
    )

    # ── Audit ────────────────────────────────────────────────────────────
    creado_en      = models.DateTimeField(auto_now_add=True, db_index=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Liquidación Laboral'
        verbose_name_plural = 'Liquidaciones Laborales'
        ordering            = ['-fecha_cese', '-creado_en']
        indexes = [
            models.Index(fields=['estado', '-fecha_cese']),
            models.Index(fields=['motivo_cese', '-fecha_cese']),
        ]

    def __str__(self):
        return f'Liquidación {self.personal} — {self.fecha_cese:%d/%m/%Y} ({self.get_estado_display()})'

    # ── Cálculo ──────────────────────────────────────────────────────────
    def calcular(self, persist=True):
        """
        Calcula todos los conceptos truncos reutilizando engine.

        Reusa:
          - `engine.calcular_gratificacion` con dias_trabajados = meses
             completos en el semestre actual de gratificación.
          - `engine.calcular_cts` con dias_trabajados = meses cumplidos
             en el semestre actual de CTS.
          - `engine.calcular_renta` indirectamente vía descuentos (no aplica
             a CTS ni vacaciones — solo a sueldo del mes).

        Calcula además:
          - Vacaciones truncas = días pendientes + truncos × (sueldo/30).
          - Sueldo del mes en curso = sueldo/30 × días trabajados del mes.
          - Indemnización (DS 003-97-TR Art. 38) si motivo = DESPIDO_ARB.

        Suma haberes, resta descuentos, persiste y cambia estado a CALCULADA.
        """
        from decimal import ROUND_HALF_UP
        from .engine import calcular_gratificacion, calcular_cts

        personal   = self.personal
        fecha_cese = self.fecha_cese
        sueldo     = Decimal(str(personal.sueldo_base or 0))
        valor_dia  = (sueldo / Decimal('30')).quantize(Decimal('0.01'), ROUND_HALF_UP)

        # ── 1. Sueldo del mes en curso ────────────────────────────────────
        # Días del 1 al día del cese, ambos inclusive.
        dias_mes = fecha_cese.day
        self.sueldo_mes_curso = (valor_dia * Decimal(dias_mes)).quantize(
            Decimal('0.01'), ROUND_HALF_UP,
        )

        # ── 2. Gratificación trunca (reusa engine) ────────────────────────
        meses_gratif = _meses_semestre_gratif(fecha_cese)
        if meses_gratif > 0:
            shim_grat = _LiquidacionShimRegistro(personal, dias_trabajados=meses_gratif)
            res_grat  = calcular_gratificacion(shim_grat)
            self.gratif_trunca = Decimal(str(res_grat.get('gratif_bruto', 0))).quantize(
                Decimal('0.01'), ROUND_HALF_UP,
            )
        else:
            self.gratif_trunca = Decimal('0.00')

        # ── 3. CTS trunca (reusa engine) ──────────────────────────────────
        meses_cts = _meses_semestre_cts(fecha_cese)
        if meses_cts > 0:
            shim_cts = _LiquidacionShimRegistro(personal, dias_trabajados=meses_cts)
            res_cts  = calcular_cts(shim_cts)
            self.cts_trunca = Decimal(str(res_cts.get('total_ingresos', 0))).quantize(
                Decimal('0.01'), ROUND_HALF_UP,
            )
        else:
            self.cts_trunca = Decimal('0.00')

        # ── 4. Vacaciones truncas (pendientes + truncos) ──────────────────
        dias_vac = Decimal('0')
        try:
            from vacaciones.models import SaldoVacacional
            sv = SaldoVacacional.objects.filter(personal=personal)\
                .order_by('-periodo_inicio').first()
            if sv:
                dias_vac = (
                    Decimal(str(sv.dias_pendientes or 0))
                    + Decimal(str(sv.dias_truncos or 0))
                )
        except Exception:
            dias_vac = Decimal('0')
        self.vacaciones_truncas = (valor_dia * dias_vac).quantize(
            Decimal('0.01'), ROUND_HALF_UP,
        )

        # ── 5. Indemnización (Art. 38 DS 003-97-TR) ───────────────────────
        if self.motivo_cese == 'DESPIDO_ARB':
            self.indemnizacion = self._calcular_indemnizacion(personal, sueldo, fecha_cese)
        else:
            self.indemnizacion = Decimal('0.00')

        # ── 6. Préstamos pendientes (descuento automático) ────────────────
        try:
            from prestamos.models import Prestamo
            saldo = Decimal('0')
            for p in Prestamo.objects.filter(personal=personal, estado='EN_CURSO'):
                saldo += Decimal(str(p.saldo_pendiente or 0))
            # Solo sobrescribimos si no estaba ya seteado a mano.
            if self.prestamos_pendientes == Decimal('0'):
                self.prestamos_pendientes = saldo.quantize(Decimal('0.01'), ROUND_HALF_UP)
        except Exception:
            pass

        # ── 7. Totales ────────────────────────────────────────────────────
        self.total_bruto = (
            self.vacaciones_truncas + self.gratif_trunca + self.cts_trunca
            + self.sueldo_mes_curso + self.he_no_compensadas
            + self.indemnizacion + self.otros_pagos
        ).quantize(Decimal('0.01'), ROUND_HALF_UP)

        total_desc = (
            self.prestamos_pendientes + self.adelantos_pendientes
            + self.embargo + self.otros_descuentos
        ).quantize(Decimal('0.01'), ROUND_HALF_UP)

        self.total_neto = (self.total_bruto - total_desc).quantize(
            Decimal('0.01'), ROUND_HALF_UP,
        )

        if self.estado == 'BORRADOR':
            self.estado = 'CALCULADA'

        if persist:
            self.save()

        return self

    @staticmethod
    def _calcular_indemnizacion(personal, sueldo: Decimal, fecha_cese=None) -> Decimal:
        """
        Indemnización por despido arbitrario — Art. 38 DS 003-97-TR.

        Fórmula: 1.5 sueldos × año completo de servicios, con tope de
        12 sueldos (18 meses de remuneración). Fracciones de año se
        pagan en treintavos por mes y dozavos por día.

        `fecha_cese` se prefiere desde la liquidación (puede no estar en
        Personal si se calcula antes de marcar el cese formalmente).
        """
        from decimal import ROUND_HALF_UP

        fecha_alta = personal.fecha_alta
        if fecha_cese is None:
            fecha_cese = personal.fecha_cese
        if not (fecha_alta and fecha_cese):
            return Decimal('0.00')

        delta_dias = (fecha_cese - fecha_alta).days
        if delta_dias <= 0:
            return Decimal('0.00')

        # Años completos
        anios = delta_dias // 365
        dias_restantes = delta_dias % 365

        # 1.5 sueldos por año
        indem = sueldo * Decimal('1.5') * Decimal(anios)
        # Treintavos por días restantes (1.5 sueldos / 12 meses / 30 días)
        indem += (sueldo * Decimal('1.5') / Decimal('360')) * Decimal(dias_restantes)

        # Tope: 12 sueldos
        tope = sueldo * Decimal('12')
        if indem > tope:
            indem = tope

        return indem.quantize(Decimal('0.01'), ROUND_HALF_UP)


def _meses_semestre_gratif(fecha_cese):
    """
    Meses completos en el semestre de gratificación vigente a fecha_cese.
    Ley 27735: solo meses íntegros trabajados.
    Semestre 1: ene–jun (pago julio).  Semestre 2: jul–dic (pago diciembre).
    """
    import calendar
    m = fecha_cese.month
    inicio = 1 if m <= 6 else 7
    meses = max(0, m - inicio)
    ultimo_dia = calendar.monthrange(fecha_cese.year, fecha_cese.month)[1]
    if fecha_cese.day >= ultimo_dia:
        meses += 1
    return min(meses, 6)


def _meses_semestre_cts(fecha_cese):
    """
    Meses cumplidos en el semestre de CTS vigente a fecha_cese.
    Período 1: nov–abr (depósito mayo).  Período 2: may–oct (depósito nov).
    """
    m = fecha_cese.month
    if m <= 4:
        return m + 2          # ene=3, feb=4, mar=5, abr=6
    elif m <= 10:
        return m - 4          # may=1, … oct=6
    else:
        return m - 10         # nov=1, dic=2


class _LiquidacionShimRegistro:
    """
    Shim que imita la interfaz de RegistroNomina que necesitan
    `engine.calcular_gratificacion` y `engine.calcular_cts`.

    Evita persistir un RegistroNomina fantasma solo para cálculos.
    """
    def __init__(self, personal, dias_trabajados):
        self.personal            = personal
        self.sueldo_base         = Decimal(str(personal.sueldo_base or 0))
        self.dias_trabajados     = dias_trabajados
        self.regimen_pension     = getattr(personal, 'regimen_pension', 'AFP')
        self.afp                 = getattr(personal, 'afp', 'Prima') or 'Prima'
        self.asignacion_familiar = bool(getattr(personal, 'asignacion_familiar', False))
        self.periodo             = None   # no hay PeriodoNomina → usa RMV live


# ══════════════════════════════════════════════════════════════════════
# Pool de Propinas (gastronomía) — modelos en módulo dedicado
# ══════════════════════════════════════════════════════════════════════
from .models_propinas import *  # noqa: E402,F401,F403
