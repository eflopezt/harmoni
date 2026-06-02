"""
Módulo de Préstamos al Personal.
Gestiona préstamos, adelantos de sueldo/gratificación, y descuentos en nómina.
Referencia: BUK, Odoo hr_loan — adaptado a legislación peruana.
"""
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from personal.models import Personal


class TipoPrestamo(models.Model):
    """
    Tipos de préstamo configurables.
    Ejemplos: Préstamo personal, Adelanto de sueldo, Adelanto de gratificación,
    Adelanto de vacaciones, Préstamo de emergencia.
    """
    nombre = models.CharField(max_length=100, unique=True)
    codigo = models.SlugField(max_length=30, unique=True)
    descripcion = models.TextField(blank=True)

    max_cuotas = models.PositiveSmallIntegerField(
        default=12,
        verbose_name="Máximo de Cuotas",
    )
    tasa_interes_mensual = models.DecimalField(
        max_digits=5, decimal_places=3, default=Decimal('0.000'),
        verbose_name="Tasa Interés Mensual (%)",
        help_text="0 = sin interés"
    )
    monto_maximo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Monto Máximo",
        help_text="Vacío = sin límite"
    )
    requiere_aprobacion = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Tipo de Préstamo"
        verbose_name_plural = "Tipos de Préstamo"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Prestamo(models.Model):
    # Workflow: BORRADOR -> PENDIENTE (solicitado) -> APROBADO -> EN_CURSO (desembolsado)
    # -> PAGADO  /  RECHAZADO  /  CANCELADO
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente Aprobación'),
        ('APROBADO', 'Aprobado'),
        ('EN_CURSO', 'Desembolsado / En Curso'),
        ('PAGADO', 'Pagado'),
        ('RECHAZADO', 'Rechazado'),
        ('CANCELADO', 'Cancelado'),
    ]

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='prestamos', verbose_name="Trabajador"
    )
    tipo = models.ForeignKey(
        TipoPrestamo, on_delete=models.PROTECT,
        related_name='prestamos', verbose_name="Tipo"
    )

    monto_solicitado = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('1.00'))],
        verbose_name="Monto Solicitado"
    )
    monto_aprobado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Monto Aprobado"
    )
    num_cuotas = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(60)],
        verbose_name="N° Cuotas"
    )
    cuota_mensual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Cuota Mensual"
    )
    tasa_interes = models.DecimalField(
        max_digits=5, decimal_places=3, default=Decimal('0.000'),
        verbose_name="Tasa Interés (%)"
    )

    fecha_solicitud = models.DateField(default=date.today, verbose_name="Fecha Solicitud")
    fecha_aprobacion = models.DateField(null=True, blank=True)
    fecha_desembolso = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Desembolso",
        help_text="Fecha en la que se entregó el dinero al trabajador"
    )
    fecha_primer_descuento = models.DateField(
        null=True, blank=True,
        verbose_name="Inicio Descuento",
        help_text="Período desde el cual se descuenta"
    )

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    motivo = models.TextField(blank=True, verbose_name="Motivo")
    motivo_rechazo = models.TextField(
        blank=True,
        verbose_name="Motivo del Rechazo",
        help_text="Si fue rechazado, motivo dado por el aprobador",
    )
    observaciones = models.TextField(blank=True)

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prestamos_registrados'
    )
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='prestamos_aprobados'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Préstamo"
        verbose_name_plural = "Préstamos"
        ordering = ['-fecha_solicitud']
        indexes = [
            models.Index(fields=['personal', 'estado']),
            models.Index(fields=['-fecha_solicitud']),
        ]

    def __str__(self):
        return f"{self.tipo} — {self.personal.apellidos_nombres} — S/ {self.monto_solicitado}"

    @property
    def monto_efectivo(self):
        return self.monto_aprobado or self.monto_solicitado

    @property
    def saldo_pendiente(self):
        pagado = self.cuotas.filter(estado='PAGADO').aggregate(
            t=models.Sum('monto_pagado')
        )['t'] or Decimal('0.00')
        return self.monto_efectivo - pagado

    @property
    def cuotas_pagadas(self):
        return self.cuotas.filter(estado='PAGADO').count()

    @property
    def porcentaje_avance(self):
        if not self.num_cuotas:
            return 0
        return round((self.cuotas_pagadas / self.num_cuotas) * 100)

    def generar_cuotas(self):
        """Genera las cuotas del cronograma al aprobar/desembolsar.

        Delega el cálculo a `calcular_cronograma`, que incluye interés (tipo
        francés) si `tasa_interes > 0` y es idéntico a monto/num_cuotas cuando
        la tasa es 0 (préstamo blanco). Así las cuotas que se descuentan en
        planilla coinciden con el cronograma del contrato PDF (que usa la misma
        función). La última cuota ajusta el residuo de redondeo.
        """
        from datetime import datetime

        from .cronograma import calcular_cronograma

        inicio = self.fecha_primer_descuento or date.today().replace(day=1)
        if isinstance(inicio, str):
            inicio = datetime.strptime(inicio, '%Y-%m-%d').date()

        cronograma = calcular_cronograma(
            monto=self.monto_efectivo,
            num_cuotas=self.num_cuotas,
            fecha_desembolso=inicio,   # primera fecha de descuento
            tasa_interes=self.tasa_interes,
        )

        CuotaPrestamo.objects.filter(prestamo=self).delete()
        CuotaPrestamo.objects.bulk_create([
            CuotaPrestamo(
                prestamo=self, numero=row['numero'],
                periodo=row['fecha_vencimiento'], monto=row['monto'],
            )
            for row in cronograma
        ])
        if cronograma:
            self.cuota_mensual = cronograma[0]['monto']
            self.save(update_fields=['cuota_mensual'])

    def aprobar(self, usuario, monto_aprobado=None, fecha_descuento=None,
                num_cuotas=None):
        """Workflow corto: aprueba + genera cuotas (preserva tests existentes).

        Para el workflow largo BORRADOR→PENDIENTE→APROBADO→DESEMBOLSADO usar
        ``marcar_aprobado()`` + ``desembolsar()``.
        """
        self.estado = 'EN_CURSO'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.monto_aprobado = monto_aprobado or self.monto_solicitado
        if num_cuotas:
            self.num_cuotas = int(num_cuotas)
        self.tasa_interes = self.tipo.tasa_interes_mensual
        if fecha_descuento:
            # Asegurar tipo date
            if isinstance(fecha_descuento, str):
                from datetime import datetime
                fecha_descuento = datetime.strptime(fecha_descuento, '%Y-%m-%d').date()
            self.fecha_primer_descuento = fecha_descuento
        if not self.fecha_desembolso:
            self.fecha_desembolso = date.today()
        self.save()
        self.refresh_from_db()  # Garantizar tipos correctos
        self.generar_cuotas()

    def marcar_aprobado(self, usuario, monto_aprobado=None, num_cuotas=None):
        """Workflow largo paso 1: APROBADO (sin desembolsar ni generar cuotas)."""
        if self.estado not in ('BORRADOR', 'PENDIENTE'):
            raise ValueError(f'No se puede aprobar desde estado {self.estado}')
        self.estado = 'APROBADO'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.monto_aprobado = monto_aprobado or self.monto_solicitado
        if num_cuotas:
            self.num_cuotas = int(num_cuotas)
        self.tasa_interes = self.tipo.tasa_interes_mensual
        self.save()

    def desembolsar(self, usuario, fecha_desembolso=None, fecha_descuento=None):
        """Workflow largo paso 2: DESEMBOLSADO (EN_CURSO) + genera cuotas."""
        if self.estado not in ('APROBADO', 'PENDIENTE', 'BORRADOR'):
            raise ValueError(f'No se puede desembolsar desde estado {self.estado}')
        if self.estado != 'APROBADO':
            self.marcar_aprobado(usuario)
        fecha_desembolso = fecha_desembolso or date.today()
        if isinstance(fecha_desembolso, str):
            from datetime import datetime
            fecha_desembolso = datetime.strptime(fecha_desembolso, '%Y-%m-%d').date()
        if fecha_descuento and isinstance(fecha_descuento, str):
            from datetime import datetime
            fecha_descuento = datetime.strptime(fecha_descuento, '%Y-%m-%d').date()
        self.fecha_desembolso = fecha_desembolso
        if fecha_descuento:
            self.fecha_primer_descuento = fecha_descuento
        self.estado = 'EN_CURSO'
        self.save()
        self.refresh_from_db()
        self.generar_cuotas()

    def rechazar(self, usuario, motivo=''):
        """Rechaza préstamo en BORRADOR/PENDIENTE."""
        if self.estado not in ('BORRADOR', 'PENDIENTE'):
            raise ValueError(f'No se puede rechazar desde estado {self.estado}')
        self.estado = 'RECHAZADO'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.motivo_rechazo = motivo or ''
        self.save()


class CuotaPrestamo(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('DESCONTADA', 'Descontada en planilla'),
        ('PAGADO', 'Pagado'),
        ('PARCIAL', 'Pago Parcial'),
        ('VENCIDA', 'Vencida'),
        ('CONDONADO', 'Condonado'),
    ]

    prestamo = models.ForeignKey(
        Prestamo, on_delete=models.CASCADE, related_name='cuotas'
    )
    numero = models.PositiveSmallIntegerField(verbose_name="N°")
    periodo = models.DateField(verbose_name="Período")
    monto = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto")
    monto_pagado = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal('0.00')
    )
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE')
    fecha_pago = models.DateField(null=True, blank=True)
    referencia_nomina = models.CharField(max_length=100, blank=True)
    descuento_planilla = models.ForeignKey(
        'descuentos.DescuentoPlanilla', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='cuotas_prestamo',
        help_text='Si se descontó en una planilla específica (DescuentoPlanilla)',
    )

    class Meta:
        verbose_name = "Cuota"
        verbose_name_plural = "Cuotas"
        ordering = ['prestamo', 'numero']
        unique_together = ['prestamo', 'numero']

    def __str__(self):
        return f"Cuota {self.numero}/{self.prestamo.num_cuotas} — S/ {self.monto}"

    @property
    def fecha_vencimiento(self):
        """Alias semántico de ``periodo``."""
        return self.periodo

    @property
    def esta_vencida(self):
        if self.estado in ('PAGADO', 'CONDONADO', 'DESCONTADA'):
            return False
        return self.periodo < date.today()

    def actualizar_estado_vencimiento(self):
        """Marca como VENCIDA si pendiente y fecha pasada. Idempotente."""
        if self.estado == 'PENDIENTE' and self.esta_vencida:
            self.estado = 'VENCIDA'
            self.save(update_fields=['estado'])
            return True
        return False

    def registrar_pago(self, monto=None, fecha=None, referencia='',
                       descuento_planilla=None):
        self.monto_pagado = monto or self.monto
        self.fecha_pago = fecha or date.today()
        self.referencia_nomina = referencia
        if descuento_planilla is not None:
            self.descuento_planilla = descuento_planilla
        self.estado = 'PAGADO' if self.monto_pagado >= self.monto else 'PARCIAL'
        self.save()
        # Auto-cerrar préstamo si todas las cuotas están pagadas
        if not self.prestamo.cuotas.exclude(estado__in=['PAGADO', 'CONDONADO']).exists():
            self.prestamo.estado = 'PAGADO'
            self.prestamo.save(update_fields=['estado'])
