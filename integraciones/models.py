"""
Integraciones Perú — Modelos.

Registra el historial de exportaciones hacia sistemas externos:
T-Registro SUNAT, PLAME, AFPNet, bancos, ESSALUD y publicacion de vacantes.
También gestiona pólizas SCTR (Seguro Complementario de Trabajo de Riesgo).
"""
from django.conf import settings
from django.db import models
from django.utils import timezone


class LogExportacion(models.Model):
    """Registro de cada exportación de archivo hacia sistema externo."""

    TIPO_CHOICES = [
        ('T_REGISTRO_ALTA', 'T-Registro — Altas'),
        ('T_REGISTRO_BAJA', 'T-Registro — Bajas'),
        ('T_REGISTRO_MODIF', 'T-Registro — Modificaciones'),
        ('PLAME', 'PDT PLAME'),
        ('AFP_NET', 'AFP Net — Aportes'),
        ('BANCO_BCP', 'Banco BCP — Telecrédito'),
        ('BANCO_BBVA', 'Banco BBVA — Pagos'),
        ('BANCO_IBK', 'Banco Interbank — Pagos'),
        ('BANCO_SCO', 'Banco Scotiabank — Pagos'),
        ('BANCO_NACION', 'Banco de la Nación — Pagos'),
        ('ESSALUD', 'ESSALUD — Declaración'),
        ('PLANILLA_EXCEL', 'Planilla Excel resumen'),
        # Contabilidad
        ('CONCAR', 'Asiento CONCAR'),
        ('SIGO', 'Asiento SIGO / Softpyme'),
        ('SAP_EXCEL', 'Asiento SAP Excel (BAPI FB50)'),
        ('SIRE_PLE', 'SIRE PLE 5.1 — Libro Diario'),
        ('OTRO', 'Otro'),
    ]

    ESTADO_CHOICES = [
        ('OK', 'Exitoso'),
        ('ERROR', 'Error'),
        ('PARCIAL', 'Parcial'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    periodo = models.CharField(
        max_length=7, blank=True,
        help_text='Período en formato YYYY-MM (ej: 2026-03)',
    )
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='OK')
    registros = models.PositiveIntegerField(default=0, help_text='Cantidad de registros exportados')
    nombre_archivo = models.CharField(max_length=200, blank=True)
    notas = models.TextField(blank=True)

    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    generado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generado_en']
        verbose_name = 'Log de Exportación'
        verbose_name_plural = 'Logs de Exportación'

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.periodo} ({self.registros} reg.)'


# ══════════════════════════════════════════════════════════════
# LOG PUBLICACION VACANTE
# ══════════════════════════════════════════════════════════════

class LogPublicacionVacante(models.Model):
    """
    Registro de cada intento de publicacion de una vacante en plataformas externas.

    Plataformas soportadas:
        - COMPUTRABAJO: export XML/JSON para feed masivo Computrabajo Peru
        - BUMERAN:      export XML/JSON para feed masivo Bumeran Peru
        - LINKEDIN:     publicacion via API OAuth2 (simpleJobPostings)
        - TELEGRAM:     publicacion via Telegram Bot API (sendMessage HTML)
        - PORTAL:       activacion en el portal de empleo propio (interno)
    """

    PLATAFORMA_CHOICES = [
        ('COMPUTRABAJO', 'Computrabajo Peru'),
        ('BUMERAN',      'Bumeran Peru'),
        ('LINKEDIN',     'LinkedIn Jobs'),
        ('TELEGRAM',     'Telegram Bot'),
        ('WHATSAPP',     'WhatsApp Business'),
        ('PORTAL',       'Portal de Empleo Propio'),
    ]

    ESTADO_CHOICES = [
        ('OK',    'Exitoso'),
        ('ERROR', 'Error'),
    ]

    vacante = models.ForeignKey(
        'reclutamiento.Vacante',
        on_delete=models.CASCADE,
        related_name='logs_publicacion',
        verbose_name='Vacante',
    )
    plataforma = models.CharField(
        max_length=15,
        choices=PLATAFORMA_CHOICES,
        verbose_name='Plataforma',
    )
    estado = models.CharField(
        max_length=5,
        choices=ESTADO_CHOICES,
        default='OK',
        verbose_name='Estado',
    )
    url_publicada = models.URLField(
        blank=True,
        verbose_name='URL Publicada',
        help_text='URL de la oferta en la plataforma externa (si aplica)',
    )
    respuesta_api = models.TextField(
        blank=True,
        verbose_name='Respuesta API',
        help_text='JSON o mensaje de respuesta devuelto por la plataforma',
    )
    mensaje = models.TextField(
        blank=True,
        verbose_name='Mensaje',
        help_text='Mensaje de exito o descripcion del error',
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
        verbose_name='Publicado por',
    )
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Fecha/Hora')

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Log de Publicacion de Vacante'
        verbose_name_plural = 'Logs de Publicacion de Vacantes'
        indexes = [
            models.Index(fields=['vacante', 'plataforma']),
            models.Index(fields=['-creado_en']),
        ]

    def __str__(self):
        return (
            f'{self.get_plataforma_display()} — {self.vacante.titulo} '
            f'({self.get_estado_display()}) [{self.creado_en:%d/%m/%Y %H:%M}]'
        )


# ══════════════════════════════════════════════════════════════
# SCTR — SEGURO COMPLEMENTARIO DE TRABAJO DE RIESGO
# ══════════════════════════════════════════════════════════════

class PolizaSCTR(models.Model):
    """
    Póliza SCTR (Seguro Complementario de Trabajo de Riesgo).

    Base legal:
    - Ley 26790 (Ley de Modernización de la Seguridad Social)
    - DS 003-98-SA (Reglamento SCTR)
    - Obligatorio para trabajadores en actividades de alto riesgo (anexo 5 DS 009-97-SA)
    """

    TIPO_CHOICES = [
        ('SALUD',   'SCTR Salud (cobertura médica)'),
        ('PENSION', 'SCTR Pensión (invalidez/sepelio)'),
        ('AMBOS',   'SCTR Ambos (Salud + Pensión)'),
    ]

    PROVEEDOR_CHOICES = [
        ('RIMAC',    'Rímac Seguros'),
        ('AXA',      'Axa Colpatria'),
        ('MAPFRE',   'Mapfre Perú'),
        ('POSITIVA', 'Positiva Seguros'),
        ('PACIFICO', 'Pacífico Seguros'),
        ('LA_POSITIVA', 'La Positiva Vida'),
        ('OTRO',     'Otro'),
    ]

    ESTADO_CHOICES = [
        ('VIGENTE',    'Vigente'),
        ('VENCIDA',    'Vencida'),
        ('CANCELADA',  'Cancelada'),
        ('RENOVACION', 'En Renovación'),
    ]

    # ── Identificación de la póliza ──
    tipo            = models.CharField(max_length=10, choices=TIPO_CHOICES, verbose_name='Tipo SCTR')
    numero_poliza   = models.CharField(max_length=100, verbose_name='Número de Póliza')
    proveedor       = models.CharField(max_length=15, choices=PROVEEDOR_CHOICES, verbose_name='Aseguradora')
    proveedor_otro  = models.CharField(max_length=100, blank=True, verbose_name='Aseguradora (otro)')

    # ── Vigencia ──
    fecha_inicio    = models.DateField(verbose_name='Vigencia Desde')
    fecha_fin       = models.DateField(verbose_name='Vigencia Hasta')

    # ── Cobertura y costo ──
    monto_asegurado = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        verbose_name='Monto Asegurado (S/)',
        help_text='Generalmente 4 UIT por trabajador cubierto',
    )
    aporte_pct      = models.DecimalField(
        max_digits=6, decimal_places=4, default=0,
        verbose_name='Tasa Aporte Empleador (%)',
        help_text='Porcentaje sobre remuneración computable. Varía por nivel de riesgo (0.66%–3.22%).',
    )
    trabajadores_cubiertos = models.PositiveIntegerField(
        default=0,
        verbose_name='N° Trabajadores Cubiertos',
        help_text='Número de empleados incluidos en esta póliza',
    )

    # ── Estado y gestión ──
    estado          = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='VIGENTE',
                                       verbose_name='Estado')
    activa          = models.BooleanField(default=True, verbose_name='Activa')
    renovacion_auto = models.BooleanField(
        default=False, verbose_name='Renovación Automática',
        help_text='Marcar si la póliza se renueva automáticamente al vencimiento',
    )
    dias_alerta     = models.PositiveSmallIntegerField(
        default=30, verbose_name='Días de Alerta Previos',
        help_text='Cuántos días antes del vencimiento se activa la alerta',
    )
    observaciones   = models.TextField(blank=True, verbose_name='Observaciones')
    archivo         = models.FileField(
        upload_to='integraciones/sctr/', null=True, blank=True,
        verbose_name='PDF de Póliza',
    )

    # ── Auditoría ──
    creado_por      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Creado por',
    )
    creado_en       = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    modificado_en   = models.DateTimeField(auto_now=True, verbose_name='Modificado en')

    class Meta:
        verbose_name        = 'Póliza SCTR'
        verbose_name_plural = 'Pólizas SCTR'
        ordering            = ['-fecha_fin', 'tipo']
        indexes = [
            models.Index(fields=['estado', 'fecha_fin']),
            models.Index(fields=['tipo']),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.numero_poliza} ({self.get_proveedor_display()})'

    @property
    def dias_para_vencer(self):
        """Días calendario hasta el vencimiento. Negativo si ya venció."""
        return (self.fecha_fin - timezone.localdate()).days

    @property
    def esta_proxima_a_vencer(self):
        return 0 < self.dias_para_vencer <= self.dias_alerta

    @property
    def esta_vencida(self):
        return self.dias_para_vencer < 0

    @property
    def proveedor_nombre(self):
        return self.proveedor_otro if self.proveedor == 'OTRO' else self.get_proveedor_display()
