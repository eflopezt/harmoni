"""
Empresas — Modelo multi-empresa para Harmoni ERP.

Permite gestionar múltiples empresas (RUC) dentro de la misma instancia.
Cada empresa tiene su propia configuración, personal y nóminas.

Architecture: Row-level tenancy
- Personal.empresa FK → Empresa
- PeriodoNomina.empresa FK → Empresa
- Session: 'empresa_actual_id' → filtra datos por empresa
"""
from django.conf import settings
from django.db import models


class Empresa(models.Model):
    """
    Empresa empleadora (persona jurídica o natural con RUC).

    Una instancia Harmoni puede gestionar múltiples empresas.
    Ejemplo: Holding con subsidiarias, grupo económico, etc.
    """
    REGIMEN_CHOICES = [
        ('GENERAL',  'Régimen General'),
        ('MYPE',     'Régimen MYPE Tributario'),
        ('ESPECIAL', 'Régimen Especial Renta'),
        ('NRUS',     'Nuevo RUS'),
    ]
    SECTOR_CHOICES = [
        ('PRIVADO',   'Privado'),
        ('PUBLICO',   'Público'),
        ('MIXTO',     'Economía mixta'),
        ('SIN_FINES', 'Sin fines de lucro'),
    ]

    ruc              = models.CharField(max_length=11, unique=True, verbose_name='RUC')
    razon_social     = models.CharField(max_length=200, verbose_name='Razón Social')
    nombre_comercial = models.CharField(max_length=200, blank=True, verbose_name='Nombre Comercial')

    # Dirección
    direccion    = models.CharField(max_length=300, blank=True)
    ubigeo       = models.CharField(max_length=6, blank=True, help_text='Código UBIGEO 6 dígitos')
    distrito     = models.CharField(max_length=100, blank=True)
    provincia    = models.CharField(max_length=100, blank=True)
    departamento = models.CharField(max_length=100, blank=True)

    # Contacto
    telefono   = models.CharField(max_length=20, blank=True)
    email_rrhh = models.EmailField(blank=True, verbose_name='Email RRHH')
    web        = models.URLField(blank=True)

    # Clasificación
    regimen_laboral     = models.CharField(max_length=12, choices=REGIMEN_CHOICES, default='GENERAL')
    sector              = models.CharField(max_length=10, choices=SECTOR_CHOICES, default='PRIVADO')
    actividad_economica = models.CharField(max_length=200, blank=True, help_text='CIIU')

    # SUNAT / PLAME
    codigo_empleador = models.CharField(
        max_length=20, blank=True,
        help_text='Código empleador SUNAT (si aplica)'
    )

    # ── Configuración contable por empresa ─────────────────────────────
    # Permite sobreescribir cuentas del PCGE 2020 default por RUC.
    # Formato JSON: {"sueldos_debe": ["6211", "Sueldos y salarios"], ...}
    # Si está vacío o nulo, se usa el plan global (ConfiguracionSistema) o
    # el PLAN_CUENTAS_DEFAULT de integraciones/contables.py.
    plan_cuentas = models.JSONField(
        null=True, blank=True,
        verbose_name='Plan de cuentas (override)',
        help_text=(
            'JSON con cuentas contables personalizadas para esta empresa. '
            'Llaves esperadas: sueldos_debe, gratif_debe, essalud_debe, '
            'rem_pagar_haber, afp_pagar_haber, onp_pagar_haber, '
            'essalud_pagar_haber. Cada valor es [codigo, nombre].'
        ),
    )

    # ── Configuración SMTP (email por empresa) ──────────────
    PROVEEDOR_EMAIL_CHOICES = [
        ('GMAIL',     'Gmail (SMTP)'),
        ('OFFICE365',  'Microsoft 365 / Outlook'),
        ('CUSTOM',    'SMTP personalizado'),
        ('NONE',      'Sin correo configurado'),
    ]

    email_proveedor = models.CharField(
        max_length=10, choices=PROVEEDOR_EMAIL_CHOICES,
        default='NONE', verbose_name='Proveedor de correo',
    )
    email_host = models.CharField(
        max_length=200, blank=True, default='',
        help_text='Servidor SMTP (ej: smtp.gmail.com, smtp.office365.com)',
    )
    email_port = models.PositiveSmallIntegerField(
        default=587, help_text='Puerto SMTP (587=TLS, 465=SSL)',
    )
    email_use_tls = models.BooleanField(default=True)
    email_use_ssl = models.BooleanField(default=False)
    email_host_user = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Usuario SMTP',
        help_text='Email o usuario para autenticación',
    )
    email_host_password = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Contraseña SMTP',
        help_text='Contraseña o App Password',
    )
    email_from = models.EmailField(
        blank=True, default='',
        verbose_name='Email remitente',
        help_text='Dirección "De:" (ej: rrhh@empresa.com)',
    )
    email_reply_to = models.EmailField(
        blank=True, default='',
        verbose_name='Reply-To',
        help_text='Dirección de respuesta (opcional)',
    )

    # ── Configuración WhatsApp ────────────────────────────────
    WHATSAPP_PROVIDER_CHOICES = [
        ('NONE', 'Sin WhatsApp'),
        ('META_CLOUD', 'Meta Cloud API'),
        ('OPENCLAW', 'OpenClaw Gateway'),
    ]

    whatsapp_provider = models.CharField(
        max_length=12, choices=WHATSAPP_PROVIDER_CHOICES,
        default='NONE', verbose_name='Proveedor WhatsApp',
    )
    whatsapp_access_token = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name='WhatsApp Access Token',
        help_text='Token permanente de la Meta Business App (solo para Meta Cloud API)',
    )
    whatsapp_phone_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='WhatsApp Phone Number ID',
        help_text='ID del numero en Meta Developer Console (no el numero real)',
    )
    openclaw_gateway_url = models.CharField(
        max_length=200, blank=True, default='http://localhost:19000',
        verbose_name='OpenClaw Gateway URL',
        help_text='URL del gateway OpenClaw (default: http://localhost:19000)',
    )
    openclaw_gateway_token = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='OpenClaw Gateway Token',
        help_text='Token de autenticacion para OpenClaw (si aplica)',
    )

    # ── Identidad visual / documentos ────────────────────────────
    logo = models.ImageField(
        upload_to='empresas/logos/', blank=True,
        verbose_name='Logotipo',
        help_text='Logotipo de la empresa para documentos PDF, contratos y reportes',
    )
    membrete_header = models.ImageField(
        upload_to='empresas/membretes/', blank=True,
        verbose_name='Membrete (cabecera)',
        help_text='Imagen de cabecera para documentos oficiales',
    )
    firma_representante = models.ImageField(
        upload_to='empresas/firmas/', blank=True,
        verbose_name='Firma del representante legal',
        help_text='Imagen de la firma escaneada del representante',
    )
    representante_legal = models.CharField(
        max_length=200, blank=True,
        verbose_name='Representante legal',
    )
    cargo_representante = models.CharField(
        max_length=100, blank=True,
        verbose_name='Cargo del representante',
        help_text='Ej: Gerente General, Director Ejecutivo',
    )
    TIPO_DOC_REPRESENTANTE_CHOICES = [
        ('DNI', 'DNI'),
        ('CE', 'Carné de Extranjería'),
        ('Pasaporte', 'Pasaporte'),
    ]
    tipo_doc_representante = models.CharField(
        max_length=20,
        choices=TIPO_DOC_REPRESENTANTE_CHOICES,
        default='DNI', blank=True,
        verbose_name='Tipo doc. representante',
    )
    nro_doc_representante = models.CharField(
        max_length=20, blank=True,
        verbose_name='Nro. documento representante',
    )

    # ── Configuración de corte de planilla ──────────────────
    dia_inicio_corte = models.PositiveSmallIntegerField(
        default=22,
        verbose_name='Día inicio corte',
        help_text='Día del mes anterior donde inicia el corte de planilla',
    )
    dia_fin_corte = models.PositiveSmallIntegerField(
        default=21,
        verbose_name='Día fin corte',
        help_text='Día del mes actual donde termina el corte de planilla',
    )

    # Multi-tenant subdomain
    subdominio = models.SlugField(
        max_length=50, unique=True, blank=True, null=True,
        help_text='Subdominio para acceso (ej: miempresa → miempresa.harmoni.pe)',
    )

    # Estado
    activa       = models.BooleanField(default=True)
    es_principal = models.BooleanField(
        default=False,
        help_text='Empresa principal/default del sistema'
    )

    # ── Plan / tier comercial de Harmoni ─────────────────────────────
    PLAN_CHOICES = [
        ('STARTER',     'Starter — S/ 149/mes (hasta 30 colaboradores)'),
        ('PROFESIONAL', 'Profesional — S/ 399/mes (hasta 100 colaboradores)'),
        ('BUSINESS',    'Business — S/ 799/mes (hasta 300 colaboradores)'),
        ('ENTERPRISE',  'Enterprise — Personalizado (300+ colaboradores)'),
    ]
    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default='PROFESIONAL',
        verbose_name='Plan Harmoni',
        help_text=(
            'Plan contratado por esta empresa. Determina qué módulos y '
            'features están habilitados. El middleware PlanStarterMiddleware '
            'restringe acceso para empresas con plan=STARTER.'
        ),
    )

    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    # ── Portal de beneficios externo (opcional) ──
    # Algunas empresas usan plataformas externas para beneficios sociales
    # (Crehana, Coursera empresarial, Rappi Empresas, etc.). Harmoni expone
    # un botón "Mis beneficios" en el portal del trabajador que redirige
    # a esta URL cuando está configurada.
    portal_beneficios_nombre = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name='Nombre del portal de beneficios',
        help_text='Ej: "Beneficios Stiler", "EDO Bienestar". Visible para el trabajador.',
    )
    portal_beneficios_url = models.URLField(
        blank=True, default='',
        verbose_name='URL del portal de beneficios',
        help_text='URL externa a la que se redirige al trabajador desde el portal.',
    )
    portal_beneficios_logo_url = models.URLField(
        blank=True, default='',
        verbose_name='Logo del portal de beneficios (opcional)',
        help_text='URL del logo para mostrar junto al botón. PNG/SVG recomendado.',
    )

    class Meta:
        verbose_name        = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering            = ['razon_social']
        indexes             = [
            models.Index(fields=['ruc'], name='empresa_ruc_idx'),
            models.Index(fields=['activa', 'es_principal'], name='empresa_activa_idx'),
        ]

    def __str__(self):
        return f'{self.nombre_comercial or self.razon_social} ({self.ruc})'

    def save(self, *args, **kwargs):
        # Solo una empresa puede ser principal
        if self.es_principal:
            Empresa.objects.filter(es_principal=True).exclude(pk=self.pk).update(es_principal=False)
        super().save(*args, **kwargs)
        # Invalidar cache de empresas disponibles en sidebar
        try:
            from personal.context_processors import invalidar_empresas
            invalidar_empresas()
        except Exception:
            pass

    @property
    def nombre_display(self):
        return self.nombre_comercial or self.razon_social

    @property
    def tiene_whatsapp_configurado(self):
        return self.whatsapp_provider != 'NONE'

    @property
    def tiene_email_configurado(self):
        return (
            self.email_proveedor != 'NONE'
            and self.email_host
            and self.email_host_user
            and self.email_host_password
        )

    def get_smtp_config(self):
        """Retorna dict con configuración SMTP para esta empresa."""
        if not self.tiene_email_configurado:
            return None
        return {
            'host': self.email_host,
            'port': self.email_port,
            'username': self.email_host_user,
            'password': self.email_host_password,
            'use_tls': self.email_use_tls,
            'use_ssl': self.email_use_ssl,
            'from_email': self.email_from or self.email_host_user,
            'reply_to': self.email_reply_to,
        }

    def auto_fill_smtp(self):
        """Auto-llena host/port según el proveedor seleccionado."""
        SMTP_DEFAULTS = {
            'GMAIL': {'host': 'smtp.gmail.com', 'port': 587, 'tls': True, 'ssl': False},
            'OFFICE365': {'host': 'smtp.office365.com', 'port': 587, 'tls': True, 'ssl': False},
        }
        defaults = SMTP_DEFAULTS.get(self.email_proveedor)
        if defaults and not self.email_host:
            self.email_host = defaults['host']
            self.email_port = defaults['port']
            self.email_use_tls = defaults['tls']
            self.email_use_ssl = defaults['ssl']
