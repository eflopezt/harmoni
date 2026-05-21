"""
Módulo de Descuentos por Planilla — distinto de Préstamos.

Préstamo: la empresa entrega dinero al trabajador, se recupera por planilla.
Descuento: el trabajador debe dinero a la empresa, se descuenta por planilla.

Casuísticas frecuentes:
  - Rotura/pérdida de herramienta o equipo
  - Reposición de uniforme, fotocheck, equipamiento
  - Consumo de insumos / productos de la empresa
  - Multa o sanción interna (ej. impuntualidad recurrente)
  - Embargo judicial (orden judicial)
  - Pensión alimenticia (orden judicial)
  - Devolución de gastos personales
  - Otros conceptos

Normativa relevante (Perú):
  - El monto descontado mensualmente no puede exceder lo permitido por
    la legislación. Para embargo judicial, el límite es 30% de la
    remuneración (DS 003-97-TR Art. 648 CPC).
  - El descuento debe estar autorizado por escrito del trabajador,
    salvo orden judicial (embargo / alimentos).
"""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from personal.models import Personal


class DescuentoPlanilla(models.Model):
    """Un descuento puntual o en cuotas que se aplica a la planilla del trabajador."""

    CAUSAL_CHOICES = [
        ('ROTURA_HERRAMIENTA', 'Rotura / pérdida de herramienta o equipo'),
        ('REPOSICION_UNIFORME', 'Reposición de uniforme o fotocheck'),
        ('CONSUMO_INTERNO', 'Consumo de insumos o productos'),
        ('MULTA_INTERNA', 'Multa o sanción interna'),
        ('EMBARGO_JUDICIAL', 'Embargo judicial'),
        ('PENSION_ALIMENTICIA', 'Pensión alimenticia (orden judicial)'),
        ('DEVOLUCION', 'Devolución de gastos personales'),
        ('ADELANTO_EFECTIVO', 'Adelanto en efectivo (no formal)'),
        ('OTROS', 'Otros'),
    ]

    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('EN_CURSO', 'En Curso'),
        ('PAGADO', 'Pagado / Liquidado'),
        ('ANULADO', 'Anulado'),
    ]

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='descuentos', verbose_name='Trabajador',
    )

    causal = models.CharField(
        max_length=25, choices=CAUSAL_CHOICES,
        verbose_name='Causal del Descuento',
    )
    detalle = models.TextField(
        verbose_name='Detalle / Descripción',
        help_text='Describe el motivo específico del descuento.',
    )

    monto_total = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Total a Descontar (S/)',
    )
    num_cuotas = models.PositiveSmallIntegerField(
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(36)],
        verbose_name='N° de Cuotas',
        help_text='En cuántos períodos de planilla se aplicará el descuento.',
    )
    cuota_mensual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Cuota Mensual (S/)',
        help_text='Se calcula automáticamente si se deja vacío.',
    )

    # Fechas
    fecha_registro = models.DateField(
        default=date.today, verbose_name='Fecha de Registro',
    )
    fecha_inicio_descuento = models.DateField(
        null=True, blank=True,
        verbose_name='Inicio del Descuento',
        help_text='Período de planilla en el que empieza a descontarse.',
    )

    # Trazabilidad
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='PENDIENTE',
        db_index=True,
    )
    requiere_consentimiento = models.BooleanField(
        default=True,
        verbose_name='Requiere Consentimiento Escrito',
        help_text='Embargos y pensiones judiciales no lo requieren.',
    )
    consentimiento_firmado = models.BooleanField(
        default=False,
        verbose_name='Consentimiento Firmado',
    )
    documento_soporte = models.FileField(
        upload_to='descuentos/%Y/%m/', null=True, blank=True,
        verbose_name='Documento de Soporte',
        help_text='Foto del daño, acta firmada, orden judicial, etc.',
    )

    # Auditoría
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='descuentos_solicitados',
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='descuentos_aprobados',
    )
    fecha_aprobacion = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Descuento por Planilla'
        verbose_name_plural = 'Descuentos por Planilla'
        ordering = ['-fecha_registro', '-id']
        indexes = [
            models.Index(fields=['personal', 'estado']),
            models.Index(fields=['estado', 'fecha_inicio_descuento']),
        ]

    def __str__(self):
        return f'[{self.get_causal_display()}] {self.personal} — S/ {self.monto_total}'

    # ── Lógica de negocio ────────────────────────────────────────────

    def save(self, *args, **kwargs):
        """Calcula cuota_mensual automáticamente si está vacía."""
        if self.monto_total and self.num_cuotas and not self.cuota_mensual:
            self.cuota_mensual = (
                self.monto_total / self.num_cuotas
            ).quantize(Decimal('0.01'))
        # Embargo y pensión judicial no requieren consentimiento
        if self.causal in ('EMBARGO_JUDICIAL', 'PENSION_ALIMENTICIA'):
            self.requiere_consentimiento = False
        super().save(*args, **kwargs)

    @property
    def cuotas_aplicadas(self):
        """Cantidad de cuotas ya aplicadas a planillas."""
        return self.aplicaciones.count()

    @property
    def cuotas_pendientes(self):
        return max(0, self.num_cuotas - self.cuotas_aplicadas)

    @property
    def saldo_pendiente(self):
        """Monto que aún falta descontar."""
        from django.db.models import Sum
        aplicado = self.aplicaciones.aggregate(
            total=Sum('monto_aplicado'),
        )['total'] or Decimal('0')
        return max(Decimal('0'), self.monto_total - aplicado)

    @property
    def progreso_pct(self):
        """% pagado del total (0-100)."""
        if not self.monto_total or self.monto_total == 0:
            return 0
        aplicado = self.monto_total - self.saldo_pendiente
        return round(float(aplicado / self.monto_total * 100), 1)

    @property
    def color_estado(self):
        return {
            'BORRADOR': '#94a3b8',
            'PENDIENTE': '#f59e0b',
            'APROBADO': '#3b82f6',
            'EN_CURSO': '#10b981',
            'PAGADO': '#064e3b',
            'ANULADO': '#94a3b8',
        }.get(self.estado, '#64748b')

    @classmethod
    def descuentos_activos_para(cls, personal):
        """Descuentos en curso aplicables al trabajador este período."""
        return cls.objects.filter(
            personal=personal,
            estado__in=['APROBADO', 'EN_CURSO'],
        )


class AplicacionDescuento(models.Model):
    """Registro de cada cuota aplicada a una planilla concreta."""

    descuento = models.ForeignKey(
        DescuentoPlanilla, on_delete=models.CASCADE,
        related_name='aplicaciones',
    )
    periodo_anio = models.PositiveSmallIntegerField()
    periodo_mes = models.PositiveSmallIntegerField()
    monto_aplicado = models.DecimalField(
        max_digits=10, decimal_places=2,
    )
    registro_nomina = models.ForeignKey(
        'nominas.RegistroNomina', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='descuentos_aplicados',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Aplicación de Descuento'
        verbose_name_plural = 'Aplicaciones de Descuento'
        unique_together = [['descuento', 'periodo_anio', 'periodo_mes']]
        ordering = ['-periodo_anio', '-periodo_mes']

    def __str__(self):
        return f'{self.descuento} — {self.periodo_anio}/{self.periodo_mes:02d}'
