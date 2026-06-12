"""
Modelos del módulo Comunicaciones Inteligentes.

Motor de notificaciones y comunicados masivos para todos los módulos de Harmoni.
Otros módulos importan:
    from comunicaciones.services import NotificacionService
"""
from django.db import models
from django.contrib.auth.models import User
from core.crypto_fields import EncryptedCharField
from personal.models import Personal, Area


# ─────────────────────────────────────────────────────────────
# 1. PlantillaNotificacion
# ─────────────────────────────────────────────────────────────

class PlantillaNotificacion(models.Model):
    """
    Plantilla reutilizable para generar notificaciones.
    El asunto y cuerpo usan sintaxis de template Django ({{ variable }}).
    """

    TIPO_CHOICES = [
        ('EMAIL', 'Email'),
        ('IN_APP', 'In-App'),
        ('WHATSAPP', 'WhatsApp'),
        ('AMBOS', 'Ambos'),
    ]
    MODULO_CHOICES = [
        ('RRHH', 'RRHH'),
        ('ASISTENCIA', 'Asistencia'),
        ('ONBOARDING', 'Onboarding'),
        ('VACACIONES', 'Vacaciones'),
        ('DISCIPLINARIA', 'Disciplinaria'),
        ('EVALUACIONES', 'Evaluaciones'),
        ('ENCUESTAS', 'Encuestas'),
        ('SISTEMA', 'Sistema'),
    ]

    nombre = models.CharField(max_length=200, verbose_name="Nombre")
    codigo = models.SlugField(max_length=100, unique=True, verbose_name="Código",
                              help_text="Identificador único (slug). Ej: bienvenida_onboarding")
    asunto_template = models.CharField(
        max_length=200,
        verbose_name="Asunto (template)",
        help_text="Admite sintaxis Django: {{ nombre }}, {{ fecha }}, etc."
    )
    cuerpo_template = models.TextField(
        verbose_name="Cuerpo (template HTML)",
        help_text="HTML con variables Django: {{ nombre }}, {{ cargo }}, {{ empresa }}, etc."
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='IN_APP',
                            verbose_name="Canal de envío")
    modulo = models.CharField(max_length=20, choices=MODULO_CHOICES, default='SISTEMA',
                              verbose_name="Módulo")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    variables_disponibles = models.TextField(
        blank=True,
        verbose_name="Variables disponibles",
        help_text="Documentación de variables: {{ nombre }}, {{ fecha }}, {{ cargo }}, {{ empresa }}, {{ url }}"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Notificación"
        verbose_name_plural = "Plantillas de Notificación"
        ordering = ['modulo', 'nombre']

    def __str__(self):
        return f"[{self.modulo}] {self.nombre}"


# ─────────────────────────────────────────────────────────────
# 2. Notificacion
# ─────────────────────────────────────────────────────────────

class Notificacion(models.Model):
    """
    Notificación individual enviada a un destinatario.
    Puede ser generada desde una plantilla o directamente.
    """

    TIPO_CHOICES = [
        ('EMAIL', 'Email'),
        ('IN_APP', 'In-App'),
        ('WHATSAPP', 'WhatsApp'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADA', 'Enviada'),
        ('FALLIDA', 'Fallida'),
        ('LEIDA', 'Leída'),
    ]

    destinatario = models.ForeignKey(
        Personal, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notificaciones', verbose_name="Destinatario"
    )
    destinatario_email = models.EmailField(
        blank=True, verbose_name="Email destinatario",
        help_text="Usado cuando el destinatario no tiene registro en Personal"
    )
    asunto = models.CharField(max_length=200, verbose_name="Asunto")
    cuerpo = models.TextField(verbose_name="Cuerpo (HTML)")
    destinatario_telefono = models.CharField(
        max_length=20, blank=True, default='', verbose_name="Telefono destinatario",
        help_text="Numero WhatsApp en formato internacional sin '+' (ej: 51999888777)"
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='IN_APP',
                            verbose_name="Tipo")
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE',
                              verbose_name="Estado")
    plantilla = models.ForeignKey(
        PlantillaNotificacion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='notificaciones_generadas', verbose_name="Plantilla usada"
    )

    enviada_en = models.DateTimeField(null=True, blank=True, verbose_name="Enviada en")
    leida_en = models.DateTimeField(null=True, blank=True, verbose_name="Leída en")
    snoozed_until = models.DateTimeField(
        null=True, blank=True, verbose_name="Snoozed hasta",
        help_text="Si está en el futuro, la notificación se oculta del inbox "
                  "principal hasta esa fecha (tab Snoozed la muestra)."
    )
    archivada_en = models.DateTimeField(
        null=True, blank=True, verbose_name="Archivada en",
        help_text="Si está seteado, va al tab Archivadas y se excluye del inbox principal."
    )
    error_detalle = models.TextField(blank=True, verbose_name="Detalle de error")
    metadata = models.JSONField(default=dict, blank=True, verbose_name="Metadatos",
                                help_text="Datos extra de contexto en formato JSON")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['destinatario', 'tipo', 'estado']),
            models.Index(fields=['-creado_en']),
            models.Index(fields=['estado']),
            models.Index(fields=['destinatario', 'archivada_en']),
            models.Index(fields=['destinatario', 'snoozed_until']),
        ]

    def __str__(self):
        dest = self.destinatario or self.destinatario_email or "Sin destinatario"
        return f"{self.asunto} -> {dest}"


# ─────────────────────────────────────────────────────────────
# 3. ComunicadoMasivo
# ─────────────────────────────────────────────────────────────

class ComunicadoMasivo(models.Model):
    """
    Comunicado, memo o política enviada a múltiples destinatarios.
    """

    TIPO_CHOICES = [
        ('COMUNICADO', 'Comunicado'),
        ('MEMO', 'Memo'),
        ('POLITICA', 'Política'),
        ('AVISO', 'Aviso'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PROGRAMADO', 'Programado'),
        ('ENVIADO', 'Enviado'),
        ('ARCHIVADO', 'Archivado'),
    ]
    DESTINATARIOS_TIPO_CHOICES = [
        ('TODOS', 'Todos'),
        ('AREA', 'Por Área'),
        ('GRUPO', 'Por Grupo'),
        ('INDIVIDUAL', 'Individual'),
    ]
    GRUPO_CHOICES = [
        ('STAFF', 'STAFF'),
        ('RCO', 'RCO'),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Título")
    cuerpo = models.TextField(verbose_name="Cuerpo (HTML)")
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='COMUNICADO',
                            verbose_name="Tipo")
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR',
                              verbose_name="Estado")

    # ── Destinatarios ──
    destinatarios_tipo = models.CharField(max_length=12, choices=DESTINATARIOS_TIPO_CHOICES,
                                          default='TODOS', verbose_name="Tipo de destinatarios")
    areas = models.ManyToManyField(Area, blank=True, verbose_name="Áreas",
                                   help_text="Solo si el tipo de destinatarios es 'Por Área'")
    grupo = models.CharField(max_length=10, choices=GRUPO_CHOICES, blank=True,
                             verbose_name="Grupo",
                             help_text="Solo si el tipo de destinatarios es 'Por Grupo'")
    personal_individual = models.ManyToManyField(Personal, blank=True,
                                                  related_name='comunicados_directos',
                                                  verbose_name="Personal individual")

    adjunto = models.FileField(upload_to='comunicaciones/adjuntos/%Y/%m/', blank=True, null=True,
                               verbose_name="Adjunto")
    requiere_confirmacion = models.BooleanField(default=False,
                                                 verbose_name="Requiere confirmación de lectura")

    programado_para = models.DateTimeField(null=True, blank=True,
                                           verbose_name="Programado para")
    enviado_en = models.DateTimeField(null=True, blank=True, verbose_name="Enviado en")

    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='comunicados_creados',
                                    verbose_name="Creado por")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Comunicado Masivo"
        verbose_name_plural = "Comunicados Masivos"
        ordering = ['-creado_en']

    def __str__(self):
        return f"{self.get_tipo_display()}: {self.titulo}"

    # ── Propiedades ──

    @property
    def total_destinatarios(self):
        """Calcula total de destinatarios según el tipo seleccionado."""
        return self._resolver_destinatarios().count()

    @property
    def confirmaciones_recibidas(self):
        return self.confirmaciones.filter(confirmado=True).count()

    @property
    def tasa_lectura(self):
        total = self.total_destinatarios
        if total == 0:
            return 0
        return round(self.confirmaciones_recibidas / total * 100, 1)

    def _resolver_destinatarios(self):
        """Retorna queryset de Personal según el tipo de destinatarios."""
        qs = Personal.objects.filter(estado='Activo')
        if self.destinatarios_tipo == 'TODOS':
            return qs
        elif self.destinatarios_tipo == 'AREA':
            area_ids = self.areas.values_list('pk', flat=True)
            return qs.filter(subarea__area_id__in=area_ids)
        elif self.destinatarios_tipo == 'GRUPO':
            if self.grupo:
                return qs.filter(grupo_tareo=self.grupo)
            return qs.none()
        elif self.destinatarios_tipo == 'INDIVIDUAL':
            return self.personal_individual.filter(estado='Activo')
        return qs.none()


# ─────────────────────────────────────────────────────────────
# 4. ConfirmacionLectura
# ─────────────────────────────────────────────────────────────

class ConfirmacionLectura(models.Model):
    """
    Registro de confirmación de lectura de un comunicado masivo.
    """
    comunicado = models.ForeignKey(ComunicadoMasivo, on_delete=models.CASCADE,
                                    related_name='confirmaciones',
                                    verbose_name="Comunicado")
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE,
                                  related_name='confirmaciones_comunicados',
                                  verbose_name="Personal")
    fecha_lectura = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de lectura")
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP")
    confirmado = models.BooleanField(default=True, verbose_name="Confirmado")

    class Meta:
        verbose_name = "Confirmación de Lectura"
        verbose_name_plural = "Confirmaciones de Lectura"
        unique_together = ['comunicado', 'personal']
        ordering = ['-fecha_lectura']

    def __str__(self):
        return f"{self.personal} -> {self.comunicado.titulo}"


# ─────────────────────────────────────────────────────────────
# 5. PreferenciaNotificacion
# ─────────────────────────────────────────────────────────────

class PreferenciaNotificacion(models.Model):
    """
    Preferencias de notificación por empleado.
    Incluye toggles por canal y por tipo/módulo de notificación.
    """

    FRECUENCIA_CHOICES = [
        ('INMEDIATO', 'Inmediato'),
        ('DIARIO', 'Resumen diario'),
        ('SEMANAL', 'Resumen semanal'),
    ]

    personal = models.OneToOneField(Personal, on_delete=models.CASCADE,
                                     related_name='preferencia_notificacion',
                                     verbose_name="Personal")

    # ── Canales ──
    recibir_email = models.BooleanField(default=True, verbose_name="Recibir emails")
    recibir_in_app = models.BooleanField(default=True, verbose_name="Recibir notificaciones in-app")
    recibir_whatsapp = models.BooleanField(default=True, verbose_name="Recibir WhatsApp")
    recibir_push = models.BooleanField(default=True, verbose_name="Recibir push en navegador")

    # ── Por tipo/módulo (toggles in-app) ──
    notif_vacaciones = models.BooleanField(default=True, verbose_name="Vacaciones")
    notif_nominas = models.BooleanField(default=True, verbose_name="Nóminas / Boletas")
    notif_workflows = models.BooleanField(default=True, verbose_name="Aprobaciones / Workflows")
    notif_asistencia = models.BooleanField(default=True, verbose_name="Asistencia / Tareo")
    notif_comunicados = models.BooleanField(default=True, verbose_name="Comunicados")
    notif_sistema = models.BooleanField(default=True, verbose_name="Sistema / Alertas")
    notif_evaluaciones = models.BooleanField(default=True, verbose_name="Evaluaciones")
    notif_capacitaciones = models.BooleanField(default=True, verbose_name="Capacitaciones")
    notif_disciplinaria = models.BooleanField(default=True, verbose_name="Disciplinaria")
    notif_onboarding = models.BooleanField(default=True, verbose_name="Onboarding")

    # ── Comportamiento ──
    frecuencia_resumen = models.CharField(max_length=10, choices=FRECUENCIA_CHOICES,
                                          default='INMEDIATO',
                                          verbose_name="Frecuencia de resumen")
    horario_silencio_inicio = models.TimeField(null=True, blank=True,
                                                verbose_name="Silencio desde")
    horario_silencio_fin = models.TimeField(null=True, blank=True,
                                             verbose_name="Silencio hasta")
    sonido_habilitado = models.BooleanField(default=True, verbose_name="Sonido de notificación")
    toast_habilitado = models.BooleanField(default=True, verbose_name="Toast emergente")

    class Meta:
        verbose_name = "Preferencia de Notificación"
        verbose_name_plural = "Preferencias de Notificación"

    def __str__(self):
        return f"Preferencias de {self.personal}"


# ─────────────────────────────────────────────────────────────
# 6. ConfiguracionSMTP (singleton)
# ─────────────────────────────────────────────────────────────

class ConfiguracionSMTP(models.Model):
    """
    Configuración SMTP para envío de emails.
    Usa patrón singleton: solo puede existir una fila.
    """
    smtp_host = models.CharField(max_length=200, default='smtp.gmail.com',
                                  verbose_name="Servidor SMTP")
    smtp_port = models.IntegerField(default=587, verbose_name="Puerto")
    smtp_user = models.CharField(max_length=200, blank=True, verbose_name="Usuario SMTP")
    smtp_password = EncryptedCharField(max_length=200, blank=True, verbose_name="Contraseña SMTP")
    smtp_use_tls = models.BooleanField(default=True, verbose_name="Usar TLS")
    email_from = models.EmailField(blank=True, verbose_name="Email remitente")
    email_reply_to = models.EmailField(blank=True, verbose_name="Email de respuesta")
    firma_html = models.TextField(blank=True, verbose_name="Firma HTML",
                                   help_text="Firma HTML que se agrega al final de cada email")
    activa = models.BooleanField(default=False, verbose_name="Activa",
                                  help_text="Activar para habilitar el envío de emails")

    class Meta:
        verbose_name = "Configuración SMTP"
        verbose_name_plural = "Configuración SMTP"

    def __str__(self):
        estado = "Activa" if self.activa else "Inactiva"
        return f"SMTP {self.smtp_host}:{self.smtp_port} ({estado})"

    @classmethod
    def get(cls):
        """Retorna la instancia singleton, creándola si no existe."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def test_connection(self):
        """Prueba la conexión SMTP. Retorna (ok, mensaje)."""
        import smtplib
        try:
            if self.smtp_use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10)
            if self.smtp_user:
                server.login(self.smtp_user, self.smtp_password)
            server.quit()
            return True, "Conexión exitosa"
        except Exception as e:
            return False, str(e)


# ─────────────────────────────────────────────────────────────
# 5. CampanaComunicacion (campañas masivas segmentadas)
# ─────────────────────────────────────────────────────────────

class CampanaComunicacion(models.Model):
    """Campaña masiva con segmentación dinámica.

    Resuelve destinatarios via filtros (área, cargo, grupo, empresa)
    y envía via NotificacionService + WhatsAppService.
    """
    CANAL_CHOICES = [
        ('EMAIL',    'Email'),
        ('WHATSAPP', 'WhatsApp'),
        ('IN_APP',   'In-App'),
        ('MULTI',    'Email + WhatsApp + In-App'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR',   'Borrador'),
        ('PROGRAMADA', 'Programada'),
        ('ENVIANDO',   'Enviando'),
        ('ENVIADA',    'Enviada'),
        ('CANCELADA',  'Cancelada'),
    ]

    nombre = models.CharField(max_length=200, verbose_name='Nombre')
    asunto = models.CharField(max_length=200, verbose_name='Asunto')
    cuerpo = models.TextField(verbose_name='Cuerpo (HTML)')
    canal = models.CharField(max_length=15, choices=CANAL_CHOICES,
                              default='IN_APP', verbose_name='Canal de envío')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES,
                               default='BORRADOR', verbose_name='Estado')

    # Filtros de segmentación
    filtro_area_ids = models.JSONField(default=list, blank=True,
        verbose_name='IDs de áreas',
        help_text='Lista de IDs de Area. Vacío = todas.')
    filtro_subarea_ids = models.JSONField(default=list, blank=True,
        verbose_name='IDs de subáreas')
    filtro_cargo = models.CharField(max_length=100, blank=True, default='',
        verbose_name='Cargo (substring)',
        help_text='Substring match en cargo (icontains)')
    filtro_grupo_tareo = models.CharField(max_length=20, blank=True, default='',
        verbose_name='Grupo de tareo',
        help_text='STAFF | RCO | vacío para todos')
    filtro_empresa_ids = models.JSONField(default=list, blank=True,
        verbose_name='IDs de empresas')
    filtro_solo_activos = models.BooleanField(default=True,
        verbose_name='Solo trabajadores activos')

    programada_para = models.DateTimeField(null=True, blank=True,
        verbose_name='Programada para')

    # Stats
    destinatarios_count = models.PositiveIntegerField(default=0,
        verbose_name='Total destinatarios')
    enviados_ok = models.PositiveIntegerField(default=0,
        verbose_name='Enviados OK')
    enviados_fallidos = models.PositiveIntegerField(default=0,
        verbose_name='Fallidos')

    creado_por = models.ForeignKey(User, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='campanas_creadas',
        verbose_name='Creado por')
    creado_en = models.DateTimeField(auto_now_add=True)
    enviada_en = models.DateTimeField(null=True, blank=True,
        verbose_name='Enviada en')

    class Meta:
        verbose_name = 'Campaña de Comunicación'
        verbose_name_plural = 'Campañas de Comunicación'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['estado'], name='com_campana_estado_idx'),
            models.Index(fields=['-creado_en'], name='com_campana_creado_idx'),
        ]

    def __str__(self):
        return f'[{self.get_estado_display()}] {self.nombre}'

    @property
    def tasa_exito_pct(self):
        if not self.destinatarios_count:
            return 0
        return round(self.enviados_ok / self.destinatarios_count * 100, 1)

    @property
    def tasa_exito(self):
        """Alias de tasa_exito_pct (nombre que usan templates y tests)."""
        return self.tasa_exito_pct

    @property
    def es_editable(self):
        """Solo los borradores se editan; una campaña enviada es histórica."""
        return self.estado == 'BORRADOR'
