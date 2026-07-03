"""
Modelos para WhatsApp Marketing de Harmoni (no confundir con `comunicaciones`,
que envía notificaciones a empleados de cada Empresa cliente).

Aquí se trackean las conversaciones entrantes/salientes del número comercial
+51 906 602 313 — leads, prospects, soporte a clientes potenciales.
"""
from django.db import models
from django.conf import settings


class WaConversacion(models.Model):
    """Una conversación = 1 número de teléfono."""

    ESTADO_BOT = 'BOT'
    ESTADO_HANDOFF = 'HANDOFF'
    ESTADO_CERRADO = 'CERRADO'
    ESTADO_CHOICES = [
        (ESTADO_BOT, 'Bot atendiendo'),
        (ESTADO_HANDOFF, 'Asignado a humano'),
        (ESTADO_CERRADO, 'Cerrado'),
    ]

    MENU_INICIO = 'INICIO'
    MENU_ESPERA_DEMO_NOMBRE = 'ESPERA_DEMO_NOMBRE'
    MENU_ESPERA_DEMO_EMPRESA = 'ESPERA_DEMO_EMPRESA'
    MENU_ESPERA_DEMO_EMPLEADOS = 'ESPERA_DEMO_EMPLEADOS'
    MENU_CHOICES = [
        (MENU_INICIO, 'Menú inicio'),
        (MENU_ESPERA_DEMO_NOMBRE, 'Esperando nombre (flujo demo)'),
        (MENU_ESPERA_DEMO_EMPRESA, 'Esperando empresa (flujo demo)'),
        (MENU_ESPERA_DEMO_EMPLEADOS, 'Esperando #empleados (flujo demo)'),
    ]

    telefono = models.CharField(max_length=20, unique=True, db_index=True,
                                help_text='Número en formato internacional sin +, ej. 51987654321')
    nombre_wa = models.CharField(max_length=120, blank=True, default='',
                                 help_text='pushName visible en WhatsApp')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ESTADO_BOT, db_index=True)
    menu_state = models.CharField(max_length=30, choices=MENU_CHOICES, default=MENU_INICIO)
    asignado_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                   null=True, blank=True, related_name='wa_conversaciones')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True, db_index=True)
    ultimo_mensaje_at = models.DateTimeField(null=True, blank=True, db_index=True)
    no_leidos = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Conversación WhatsApp'
        verbose_name_plural = 'Conversaciones WhatsApp'
        ordering = ['-ultimo_mensaje_at']

    def __str__(self):
        return f'{self.telefono} ({self.nombre_wa or "sin nombre"})'


class WaMensaje(models.Model):
    """Mensaje individual dentro de una conversación."""

    DIR_IN = 'IN'
    DIR_OUT = 'OUT'
    DIR_CHOICES = [(DIR_IN, 'Entrante'), (DIR_OUT, 'Saliente')]

    TIPO_TEXTO = 'TEXTO'
    TIPO_MENU = 'MENU'
    TIPO_SISTEMA = 'SISTEMA'  # mensaje interno (no enviado al cliente)
    TIPO_CHOICES = [
        (TIPO_TEXTO, 'Texto'),
        (TIPO_MENU, 'Menú/lista'),
        (TIPO_SISTEMA, 'Sistema (interno)'),
    ]

    conversacion = models.ForeignKey(WaConversacion, on_delete=models.CASCADE, related_name='mensajes')
    direccion = models.CharField(max_length=3, choices=DIR_CHOICES, db_index=True)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_TEXTO)
    cuerpo = models.TextField()
    wa_message_id = models.CharField(max_length=120, blank=True, default='',
                                     help_text='ID externo del mensaje (Baileys/Meta)')
    enviado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                    null=True, blank=True,
                                    help_text='User que envió manualmente (handoff). Null si fue el bot.')
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Mensaje WhatsApp'
        verbose_name_plural = 'Mensajes WhatsApp'
        ordering = ['creado_en']
        indexes = [models.Index(fields=['conversacion', 'creado_en'])]

    def __str__(self):
        return f'[{self.direccion}] {self.cuerpo[:50]}'


class WaLead(models.Model):
    """Lead capturado a través del flujo del bot (botón 'Solicitar demo')."""

    ORIGEN_BOT_DEMO = 'BOT_DEMO'
    ORIGEN_MANUAL = 'MANUAL'
    ORIGEN_CHOICES = [
        (ORIGEN_BOT_DEMO, 'Bot — flujo demo'),
        (ORIGEN_MANUAL, 'Capturado manualmente'),
    ]

    conversacion = models.ForeignKey(WaConversacion, on_delete=models.CASCADE,
                                     related_name='leads', null=True, blank=True)
    nombre = models.CharField(max_length=120)
    empresa = models.CharField(max_length=180, blank=True, default='')
    num_empleados = models.CharField(max_length=40, blank=True, default='',
                                     help_text='Texto libre porque el cliente puede escribir "más de 100"')
    telefono = models.CharField(max_length=20, db_index=True)
    notas = models.TextField(blank=True, default='')
    origen = models.CharField(max_length=20, choices=ORIGEN_CHOICES, default=ORIGEN_BOT_DEMO)
    contactado = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = 'Lead WhatsApp'
        verbose_name_plural = 'Leads WhatsApp'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.nombre} — {self.empresa or self.telefono}'
