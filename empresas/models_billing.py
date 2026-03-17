"""
Billing & Subscription — Modelos para gestión de planes, suscripciones y pagos.

Sistema SaaS de facturación manual (Yape/Plin/Transferencia).
Sin gateway de pago integrado — registro manual de pagos.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """
    Plan de suscripción SaaS.

    Ejemplos: Starter (S/149, 30 empleados), Profesional (S/349, 100 empleados),
    Enterprise (S/799, ilimitado).
    """
    nombre = models.CharField(max_length=50, verbose_name='Nombre del plan')
    codigo = models.SlugField(max_length=30, unique=True, verbose_name='Código')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')

    precio_mensual = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Precio mensual (S/)',
    )
    precio_anual = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name='Precio anual (S/)',
        help_text='Precio anual con descuento. Dejar vacío = precio_mensual * 12.',
    )

    max_empleados = models.IntegerField(
        default=30,
        verbose_name='Máx. empleados',
        help_text='0 = ilimitado',
    )
    modulos_incluidos = models.JSONField(
        default=list, blank=True,
        verbose_name='Módulos incluidos',
        help_text='Lista de códigos de módulo (ej: ["nominas", "asistencia", "vacaciones"])',
    )
    features = models.JSONField(
        default=list, blank=True,
        verbose_name='Características destacadas',
        help_text='Lista de textos para mostrar en la tarjeta del plan',
    )

    orden = models.PositiveSmallIntegerField(default=0, help_text='Orden de visualización')
    activo = models.BooleanField(default=True)
    destacado = models.BooleanField(
        default=False,
        help_text='Mostrar como "Recomendado" en la página de planes',
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'
        ordering = ['orden', 'precio_mensual']

    def __str__(self):
        return f'{self.nombre} (S/ {self.precio_mensual}/mes)'

    @property
    def es_ilimitado(self):
        return self.max_empleados == 0

    @property
    def precio_anual_efectivo(self):
        if self.precio_anual:
            return self.precio_anual
        return self.precio_mensual * 12


class Suscripcion(models.Model):
    """
    Suscripción de una empresa a un plan.

    OneToOne con Empresa: cada empresa tiene exactamente una suscripción activa.
    """
    ESTADO_CHOICES = [
        ('TRIAL',      'Periodo de prueba'),
        ('ACTIVA',     'Activa'),
        ('SUSPENDIDA', 'Suspendida'),
        ('CANCELADA',  'Cancelada'),
    ]
    CICLO_CHOICES = [
        ('MENSUAL', 'Mensual'),
        ('ANUAL',   'Anual'),
    ]

    empresa = models.OneToOneField(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='suscripcion',
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name='suscripciones',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADO_CHOICES,
        default='TRIAL',
    )
    ciclo = models.CharField(
        max_length=10,
        choices=CICLO_CHOICES,
        default='MENSUAL',
    )

    fecha_inicio = models.DateField(verbose_name='Fecha de inicio')
    fecha_fin = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de fin',
        help_text='Null = suscripción vigente sin fecha de término',
    )
    dias_trial = models.IntegerField(
        default=15,
        verbose_name='Días de trial',
    )
    proximo_pago = models.DateField(
        verbose_name='Próximo pago',
    )

    notas = models.TextField(blank=True, verbose_name='Notas internas')

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'

    def __str__(self):
        return f'{self.empresa} — {self.plan.nombre} ({self.get_estado_display()})'

    @property
    def esta_activa(self):
        return self.estado in ('ACTIVA', 'TRIAL')

    @property
    def es_trial(self):
        return self.estado == 'TRIAL'

    @property
    def dias_trial_restantes(self):
        if not self.es_trial:
            return 0
        from datetime import date
        fin_trial = self.fecha_inicio + timezone.timedelta(days=self.dias_trial)
        remaining = (fin_trial - date.today()).days
        return max(remaining, 0)

    @property
    def trial_vencido(self):
        return self.es_trial and self.dias_trial_restantes <= 0

    @property
    def esta_suspendida(self):
        return self.estado == 'SUSPENDIDA'

    @property
    def esta_cancelada(self):
        return self.estado == 'CANCELADA'

    @property
    def empleados_count(self):
        """Cantidad actual de empleados activos de la empresa."""
        try:
            from personal.models import Personal
            return Personal.objects.filter(
                empresa=self.empresa,
                activo=True,
            ).count()
        except Exception:
            return 0

    @property
    def uso_empleados_pct(self):
        """Porcentaje de uso del límite de empleados."""
        if self.plan.es_ilimitado:
            return 0
        count = self.empleados_count
        if self.plan.max_empleados == 0:
            return 0
        return min(round(count / self.plan.max_empleados * 100), 100)

    @property
    def puede_agregar_empleados(self):
        """True si aún hay espacio para más empleados."""
        if self.plan.es_ilimitado:
            return True
        return self.empleados_count < self.plan.max_empleados

    @property
    def monto_periodo(self):
        """Monto a cobrar según ciclo."""
        if self.ciclo == 'ANUAL':
            return self.plan.precio_anual_efectivo
        return self.plan.precio_mensual


class HistorialPago(models.Model):
    """
    Registro de pago manual de suscripción.

    Peru: mayoritariamente Yape, Plin, transferencia bancaria.
    """
    METODO_CHOICES = [
        ('YAPE',          'Yape'),
        ('PLIN',          'Plin'),
        ('TRANSFERENCIA', 'Transferencia bancaria'),
        ('TARJETA',       'Tarjeta de crédito/débito'),
        ('EFECTIVO',      'Efectivo'),
        ('OTRO',          'Otro'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('PAGADO',    'Pagado'),
        ('VENCIDO',   'Vencido'),
        ('ANULADO',   'Anulado'),
    ]
    COMPROBANTE_TIPO_CHOICES = [
        ('BOLETA',  'Boleta de venta'),
        ('FACTURA', 'Factura'),
        ('RECIBO',  'Recibo'),
    ]

    suscripcion = models.ForeignKey(
        Suscripcion,
        on_delete=models.CASCADE,
        related_name='pagos',
    )
    monto = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name='Monto (S/)',
    )
    fecha_pago = models.DateField(verbose_name='Fecha de pago')
    fecha_vencimiento = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de vencimiento',
    )
    metodo_pago = models.CharField(
        max_length=15,
        choices=METODO_CHOICES,
        default='YAPE',
    )
    referencia = models.CharField(
        max_length=100, blank=True,
        verbose_name='Nro. referencia / operación',
    )
    comprobante = models.FileField(
        upload_to='billing/comprobantes/%Y/%m/',
        null=True, blank=True,
        verbose_name='Comprobante adjunto',
    )
    comprobante_tipo = models.CharField(
        max_length=10,
        choices=COMPROBANTE_TIPO_CHOICES,
        default='BOLETA',
        verbose_name='Tipo de comprobante',
    )
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='PENDIENTE',
    )
    periodo_desde = models.DateField(
        null=True, blank=True,
        verbose_name='Periodo desde',
    )
    periodo_hasta = models.DateField(
        null=True, blank=True,
        verbose_name='Periodo hasta',
    )
    notas = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Historial de pagos'
        ordering = ['-fecha_pago', '-creado_en']

    def __str__(self):
        return (
            f'S/ {self.monto} — {self.get_metodo_pago_display()} '
            f'({self.get_estado_display()}) — {self.fecha_pago}'
        )
