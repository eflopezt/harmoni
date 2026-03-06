"""
Módulo de Vacaciones y Permisos.
Gestiona saldos vacacionales, solicitudes, aprobaciones y licencias.

Base legal:
- DL 713: Descansos remunerados (30 días calendario/año)
- DS 012-92-TR: Reglamento de DL 713
- Art. 17: Mínimo 7 días consecutivos de vacaciones
- Art. 19: Venta de vacaciones: máximo 15 días por período
- Art. 23: No acumular más de 2 períodos
- Ley 29409: Licencia por paternidad (10 días consecutivos)
- Ley 26644: Licencia por maternidad (98 días)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from personal.models import Personal


class SaldoVacacional(models.Model):
    """
    Registro del saldo vacacional por período (año de servicio).
    Cada trabajador tiene un registro por cada año de servicio completado.
    """
    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='saldos_vacacionales', verbose_name="Trabajador"
    )
    periodo_inicio = models.DateField(
        verbose_name="Inicio Período",
        help_text="Fecha de inicio del año de servicio"
    )
    periodo_fin = models.DateField(
        verbose_name="Fin Período",
        help_text="Fecha de fin del año de servicio"
    )

    # Días
    dias_derecho = models.PositiveSmallIntegerField(
        default=30, verbose_name="Días de Derecho",
        help_text="30 días calendario por ley (DL 713)"
    )
    dias_gozados = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Gozados"
    )
    dias_vendidos = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Vendidos",
        help_text="Máximo 15 días (DL 713 Art. 19)"
    )
    dias_pendientes = models.PositiveSmallIntegerField(
        default=30, verbose_name="Días Pendientes"
    )

    # Para vacaciones truncas
    dias_truncos = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Días Truncos",
        help_text="Días proporcionales al cese (para liquidación)"
    )

    estado = models.CharField(
        max_length=15,
        choices=[
            ('PENDIENTE', 'Pendiente'),
            ('PARCIAL', 'Parcialmente Gozado'),
            ('GOZADO', 'Completamente Gozado'),
            ('TRUNCO', 'Trunco (Cesado)'),
        ],
        default='PENDIENTE',
    )
    observaciones = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Saldo Vacacional"
        verbose_name_plural = "Saldos Vacacionales"
        ordering = ['-periodo_inicio']
        unique_together = ['personal', 'periodo_inicio']
        indexes = [
            models.Index(fields=['personal', 'estado']),
        ]

    def __str__(self):
        return f"{self.personal.apellidos_nombres} — {self.periodo_inicio.year}/{self.periodo_fin.year} — {self.dias_pendientes}d pend."

    def recalcular(self):
        """Recalcula días pendientes."""
        self.dias_pendientes = self.dias_derecho - self.dias_gozados - self.dias_vendidos
        if self.dias_pendientes < 0:
            self.dias_pendientes = 0
        if self.dias_gozados >= self.dias_derecho:
            self.estado = 'GOZADO'
        elif self.dias_gozados > 0:
            self.estado = 'PARCIAL'
        else:
            self.estado = 'PENDIENTE'
        self.save(update_fields=['dias_pendientes', 'estado'])


class TipoPermiso(models.Model):
    """Tipos de permiso/licencia configurables."""
    nombre = models.CharField(max_length=150, unique=True)
    codigo = models.SlugField(max_length=30, unique=True)
    descripcion = models.TextField(blank=True)
    base_legal = models.CharField(
        max_length=200, blank=True,
        help_text="Referencia legal (ej: Ley 29409, DL 713 Art. 17)"
    )

    dias_max = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Máximos",
        help_text="0 = sin límite"
    )
    pagado = models.BooleanField(
        default=True, verbose_name="¿Pagado?",
        help_text="Si el permiso es con goce de remuneración"
    )
    requiere_sustento = models.BooleanField(
        default=False,
        help_text="Si requiere documento de sustento (certificado médico, etc.)"
    )
    descuenta_vacaciones = models.BooleanField(
        default=False,
        help_text="Si se descuenta del saldo vacacional"
    )
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=10)

    class Meta:
        verbose_name = "Tipo de Permiso"
        verbose_name_plural = "Tipos de Permiso"
        ordering = ['orden', 'nombre']

    def __str__(self):
        goce = "con goce" if self.pagado else "sin goce"
        return f"{self.nombre} ({goce})"


class SolicitudVacacion(models.Model):
    """Solicitud de vacaciones de un trabajador."""
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente Aprobación'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('EN_GOCE', 'En Goce'),
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    ]

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='solicitudes_vacacion', verbose_name="Trabajador"
    )
    saldo = models.ForeignKey(
        SaldoVacacional, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='solicitudes',
        verbose_name="Período Vacacional"
    )

    fecha_inicio = models.DateField(verbose_name="Fecha Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha Fin")
    dias_calendario = models.PositiveSmallIntegerField(
        verbose_name="Días Calendario",
        help_text="Días calendario solicitados"
    )
    dias_habiles = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Hábiles"
    )

    motivo = models.TextField(blank=True, verbose_name="Motivo/Observaciones")
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')

    # Aprobación
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vacaciones_aprobadas'
    )
    fecha_aprobacion = models.DateField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)

    # Trazabilidad
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='vacaciones_registradas'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Solicitud de Vacaciones"
        verbose_name_plural = "Solicitudes de Vacaciones"
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['personal', 'estado']),
            models.Index(fields=['-fecha_inicio']),
        ]

    def __str__(self):
        return f"Vacaciones {self.personal.apellidos_nombres} — {self.fecha_inicio} al {self.fecha_fin}"

    def save(self, *args, **kwargs):
        if self.fecha_inicio and self.fecha_fin:
            self.dias_calendario = (self.fecha_fin - self.fecha_inicio).days + 1
            # Días hábiles (excluir domingos)
            habiles = 0
            d = self.fecha_inicio
            while d <= self.fecha_fin:
                if d.weekday() != 6:  # No contar domingos
                    habiles += 1
                d += timedelta(days=1)
            self.dias_habiles = habiles
        super().save(*args, **kwargs)

    def aprobar(self, usuario):
        """Aprueba la solicitud y descuenta del saldo."""
        self.estado = 'APROBADA'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.save(update_fields=['estado', 'aprobado_por', 'fecha_aprobacion'])
        # Descontar del saldo
        if self.saldo:
            self.saldo.dias_gozados += self.dias_calendario
            self.saldo.recalcular()

    def rechazar(self, usuario, motivo=''):
        self.estado = 'RECHAZADA'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.motivo_rechazo = motivo
        self.save(update_fields=['estado', 'aprobado_por', 'fecha_aprobacion', 'motivo_rechazo'])

    @property
    def puede_anular(self):
        return self.estado in ('BORRADOR', 'PENDIENTE')


class SolicitudPermiso(models.Model):
    """Solicitud de permiso/licencia de un trabajador."""
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente Aprobación'),
        ('APROBADA', 'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    ]

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='solicitudes_permiso', verbose_name="Trabajador"
    )
    tipo = models.ForeignKey(
        TipoPermiso, on_delete=models.PROTECT,
        related_name='solicitudes', verbose_name="Tipo de Permiso"
    )

    fecha_inicio = models.DateField(verbose_name="Fecha Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha Fin")
    dias = models.PositiveSmallIntegerField(verbose_name="Días Solicitados")
    horas = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('0.0'),
        verbose_name="Horas (si aplica)",
        help_text="Para permisos por horas"
    )

    motivo = models.TextField(verbose_name="Motivo")
    sustento = models.FileField(
        upload_to='permisos/sustentos/%Y/%m/',
        blank=True, null=True,
        verbose_name="Documento Sustento",
        help_text="Certificado médico, partida, etc."
    )

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='permisos_aprobados'
    )
    fecha_aprobacion = models.DateField(null=True, blank=True)
    motivo_rechazo = models.TextField(blank=True)

    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='permisos_registrados'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Solicitud de Permiso"
        verbose_name_plural = "Solicitudes de Permisos"
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['personal', 'estado']),
            models.Index(fields=['tipo', 'estado']),
            models.Index(fields=['-fecha_inicio']),
        ]

    def __str__(self):
        return f"{self.tipo.nombre} — {self.personal.apellidos_nombres} — {self.fecha_inicio}"

    def save(self, *args, **kwargs):
        if self.fecha_inicio and self.fecha_fin:
            self.dias = (self.fecha_fin - self.fecha_inicio).days + 1
        super().save(*args, **kwargs)

    def aprobar(self, usuario):
        self.estado = 'APROBADA'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.save(update_fields=['estado', 'aprobado_por', 'fecha_aprobacion'])
        # Si descuenta vacaciones, actualizar saldo
        if self.tipo.descuenta_vacaciones:
            saldo = self.personal.saldos_vacacionales.filter(estado__in=['PENDIENTE', 'PARCIAL']).first()
            if saldo:
                saldo.dias_gozados += self.dias
                saldo.recalcular()

    def rechazar(self, usuario, motivo=''):
        self.estado = 'RECHAZADA'
        self.aprobado_por = usuario
        self.fecha_aprobacion = date.today()
        self.motivo_rechazo = motivo
        self.save(update_fields=['estado', 'aprobado_por', 'fecha_aprobacion', 'motivo_rechazo'])


class VentaVacaciones(models.Model):
    """Registro de venta de vacaciones (DL 713 Art. 19)."""
    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='ventas_vacaciones'
    )
    saldo = models.ForeignKey(
        SaldoVacacional, on_delete=models.CASCADE,
        related_name='ventas'
    )
    dias_vendidos = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(15)],
        verbose_name="Días Vendidos",
        help_text="Máximo 15 días por período (DL 713 Art. 19)"
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name="Monto (S/)"
    )
    fecha = models.DateField(default=date.today)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Venta de Vacaciones"
        verbose_name_plural = "Ventas de Vacaciones"
        ordering = ['-fecha']

    def __str__(self):
        return f"Venta {self.dias_vendidos}d — {self.personal} — S/ {self.monto}"

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        super().save(*args, **kwargs)
        # Actualizar saldo solo al crear (evitar double-count en re-saves)
        if is_new:
            self.saldo.dias_vendidos += self.dias_vendidos
            self.saldo.recalcular()
