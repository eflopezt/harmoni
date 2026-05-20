"""
Modelos del módulo Documentos - Legajo Digital del Trabajador.

Gestión de documentos laborales: contratos, certificados, DNI,
antecedentes, exámenes médicos, SCTR, SSOMA, etc.

Base legal:
- DS 003-97-TR: conservación de documentos laborales
- Ley 29783: documentación SSOMA obligatoria
- DS 005-2012-TR: registros obligatorios SST
"""
from django.conf import settings
from django.db import models


class CategoriaDocumento(models.Model):
    """Categoría para agrupar tipos de documento (ej: Contractual, SSOMA, Legal)."""
    nombre = models.CharField(max_length=100, unique=True)
    icono = models.CharField(
        max_length=50, default='fa-folder',
        help_text='Clase FontAwesome (ej: fa-folder, fa-hard-hat, fa-file-contract)',
    )
    orden = models.PositiveSmallIntegerField(default=0)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'Categoría de Documento'
        verbose_name_plural = 'Categorías de Documento'

    def __str__(self):
        return self.nombre


class TipoDocumento(models.Model):
    """Tipo de documento laboral (ej: Contrato, DNI, Examen Médico)."""
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(
        CategoriaDocumento, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='tipos',
    )
    obligatorio = models.BooleanField(
        default=False,
        help_text='Si es obligatorio, aparecerá como "faltante" cuando no exista.',
    )
    vence = models.BooleanField(
        default=False,
        help_text='Indica si este tipo de documento tiene fecha de vencimiento.',
    )
    dias_alerta_vencimiento = models.PositiveSmallIntegerField(
        default=30,
        help_text='Días antes del vencimiento para generar alerta.',
    )
    aplica_staff = models.BooleanField(default=True)
    aplica_rco = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['categoria__orden', 'orden', 'nombre']
        verbose_name = 'Tipo de Documento'
        verbose_name_plural = 'Tipos de Documento'

    def __str__(self):
        return self.nombre


class PlantillaConstancia(models.Model):
    """Plantilla HTML para generación de constancias/documentos laborales.

    Usa Django template syntax. Variables disponibles:
    - {{ personal.* }} - datos del empleado
    - {{ empresa.* }} - datos de la empresa (ConfiguracionSistema)
    - {{ hoy }} - fecha actual
    - {{ hoy_texto }} - fecha en texto (ej: "01 de marzo de 2026")
    - {{ antiguedad }} - antigüedad calculada del empleado
    """

    CATEGORIA_CHOICES = [
        ('CONSTANCIA', 'Constancia'),
        ('CERTIFICADO', 'Certificado'),
        ('CARTA', 'Carta'),
        ('MEMO', 'Memorándum'),
        ('OTRO', 'Otro'),
    ]

    nombre = models.CharField(max_length=200, help_text='Ej: Constancia de Trabajo')
    codigo = models.SlugField(
        max_length=50, unique=True,
        help_text='Código único (ej: constancia-trabajo). Se usa internamente.',
    )
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, default='CONSTANCIA')
    descripcion = models.TextField(blank=True, help_text='Descripción de uso.')
    contenido_html = models.TextField(
        help_text='HTML con variables Django template. Use {{ personal.apellidos_nombres }}, etc.',
    )
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=0)

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['orden', 'nombre']
        verbose_name = 'Plantilla de Constancia'
        verbose_name_plural = 'Plantillas de Constancias'

    def __str__(self):
        return self.nombre


class ConstanciaGenerada(models.Model):
    """
    Registro histórico de cada constancia/certificado generado.
    Permite auditar quién generó qué documento y cuándo,
    tanto desde el panel administrativo como desde el portal del trabajador.
    """
    ORIGEN_CHOICES = [
        ('ADMIN', 'Administración'),
        ('PORTAL', 'Portal del Trabajador'),
    ]

    plantilla = models.ForeignKey(
        PlantillaConstancia, on_delete=models.PROTECT,
        related_name='generaciones', verbose_name='Plantilla',
    )
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='constancias_generadas', verbose_name='Trabajador',
    )
    generado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Generado por',
    )
    origen = models.CharField(
        max_length=10, choices=ORIGEN_CHOICES, default='ADMIN',
        verbose_name='Origen',
    )
    ip_solicitud = models.GenericIPAddressField(null=True, blank=True)
    fecha_generacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_generacion']
        verbose_name = 'Constancia Generada'
        verbose_name_plural = 'Constancias Generadas'
        indexes = [
            models.Index(fields=['personal', '-fecha_generacion']),
            models.Index(fields=['plantilla', '-fecha_generacion']),
        ]

    def __str__(self):
        return (
            f'{self.plantilla.nombre} - {self.personal.apellidos_nombres}'
            f' ({self.fecha_generacion.strftime("%d/%m/%Y")})'
        )


class DocumentoTrabajador(models.Model):
    """Documento del legajo digital de un trabajador."""

    ESTADO_CHOICES = [
        ('VIGENTE', 'Vigente'),
        ('VENCIDO', 'Vencido'),
        ('POR_VENCER', 'Por Vencer'),
        ('ANULADO', 'Anulado'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='documentos',
    )
    tipo = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT,
        related_name='documentos',
    )
    archivo = models.FileField(
        upload_to='documentos/%Y/%m/',
        help_text='PDF, imagen u otro archivo del documento.',
    )
    nombre_archivo = models.CharField(
        max_length=255, blank=True,
        help_text='Nombre descriptivo (se auto-genera si se deja vacío).',
    )
    fecha_emision = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(
        null=True, blank=True,
        help_text='Solo para documentos con vencimiento.',
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='VIGENTE',
    )
    notas = models.TextField(blank=True)
    version = models.PositiveSmallIntegerField(
        default=1,
        help_text='Versión del documento (incrementar al reemplazar).',
    )

    # Auditoría
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Documento del Trabajador'
        verbose_name_plural = 'Documentos de Trabajadores'

    def __str__(self):
        return f'{self.tipo.nombre} - {self.personal}'

    def save(self, *args, **kwargs):
        if not self.nombre_archivo and self.archivo:
            self.nombre_archivo = self.archivo.name.split('/')[-1]
        # Auto-calcular estado basado en vencimiento
        if self.tipo.vence and self.fecha_vencimiento:
            from datetime import date, timedelta
            hoy = date.today()
            if self.fecha_vencimiento < hoy:
                self.estado = 'VENCIDO'
            elif self.fecha_vencimiento <= hoy + timedelta(days=self.tipo.dias_alerta_vencimiento):
                self.estado = 'POR_VENCER'
            else:
                self.estado = 'VIGENTE'
        super().save(*args, **kwargs)

    @property
    def extension(self):
        """Extensión del archivo (pdf, jpg, etc.)."""
        if self.archivo and self.archivo.name:
            return self.archivo.name.rsplit('.', 1)[-1].lower()
        return ''

    @property
    def es_imagen(self):
        return self.extension in ('jpg', 'jpeg', 'png', 'gif', 'webp')

    @property
    def es_pdf(self):
        return self.extension == 'pdf'

    @property
    def icono_archivo(self):
        ext = self.extension
        if ext == 'pdf':
            return 'fa-file-pdf text-danger'
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            return 'fa-file-image text-primary'
        if ext in ('doc', 'docx'):
            return 'fa-file-word text-info'
        if ext in ('xls', 'xlsx'):
            return 'fa-file-excel text-success'
        return 'fa-file text-muted'


# ═══════════════════════════════════════════════════════════════
# BOLETAS DE PAGO DIGITAL
# Base legal: DS 009-2011-TR + DS 003-2013-TR
# Boleta electrónica válida si: acceso al medio + constancia de visualización
# ═══════════════════════════════════════════════════════════════

class BoletaPago(models.Model):
    """
    Boleta de pago digital.
    Cada registro es un PDF (o generación futura) de la boleta de remuneraciones
    de un trabajador en un período específico.
    """
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PUBLICADA', 'Publicada'),
        ('LEIDA', 'Leída'),
        ('ANULADA', 'Anulada'),
    ]
    TIPO_CHOICES = [
        ('MENSUAL', 'Remuneración Mensual'),
        ('GRATIFICACION', 'Gratificación'),
        ('CTS', 'CTS'),
        ('LIQUIDACION', 'Liquidación'),
        ('UTILIDADES', 'Utilidades'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='boletas_pago', verbose_name="Trabajador"
    )
    periodo = models.DateField(
        verbose_name="Período",
        help_text="Primer día del mes de la boleta"
    )
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='MENSUAL')
    archivo = models.FileField(
        upload_to='boletas/%Y/%m/',
        verbose_name="Archivo PDF",
        help_text="PDF de la boleta de pago"
    )
    nombre_archivo = models.CharField(max_length=255, blank=True)

    # Montos resumen (para estadísticas sin abrir PDF)
    remuneracion_bruta = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Rem. Bruta"
    )
    descuentos = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Descuentos"
    )
    neto_pagar = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Neto a Pagar"
    )

    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    # Constancia de lectura (DS 009-2011-TR)
    fecha_lectura = models.DateTimeField(null=True, blank=True)
    ip_lectura = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(
        max_length=500, blank=True, null=True,
        help_text="User-Agent del navegador al momento de la lectura"
    )
    METODO_ACCESO_CHOICES = [
        ('PORTAL_WEB', 'Portal Web'),
        ('EMAIL', 'Email'),
        ('PDF_DESCARGA', 'Descarga PDF'),
    ]
    metodo_acceso = models.CharField(
        max_length=15, choices=METODO_ACCESO_CHOICES, default='PORTAL_WEB',
        help_text="Canal por el que el trabajador accedió a la boleta"
    )
    confirmada = models.BooleanField(
        default=False,
        help_text="Trabajador confirmó recepción de la boleta"
    )
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)

    # Auditoría
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+'
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Boleta de Pago"
        verbose_name_plural = "Boletas de Pago"
        ordering = ['-periodo', 'personal__apellidos_nombres']
        unique_together = ['personal', 'periodo', 'tipo']
        indexes = [
            models.Index(fields=['personal', 'estado']),
            models.Index(fields=['-periodo']),
        ]

    def __str__(self):
        return f"Boleta {self.get_tipo_display()} - {self.personal} - {self.periodo.strftime('%m/%Y')}"

    def save(self, *args, **kwargs):
        if not self.nombre_archivo and self.archivo:
            self.nombre_archivo = self.archivo.name.split('/')[-1]
        super().save(*args, **kwargs)

    def publicar(self):
        """Publica la boleta para que el trabajador la vea."""
        from django.utils import timezone
        self.estado = 'PUBLICADA'
        self.fecha_publicacion = timezone.now()
        self.save(update_fields=['estado', 'fecha_publicacion'])

    def registrar_lectura(self, ip=None):
        """Registra que el trabajador leyó la boleta."""
        from django.utils import timezone
        if not self.fecha_lectura:
            self.fecha_lectura = timezone.now()
            self.ip_lectura = ip
            self.estado = 'LEIDA'
            self.save(update_fields=['fecha_lectura', 'ip_lectura', 'estado'])

    def confirmar_recepcion(self):
        """Trabajador confirma recepción (constancia legal)."""
        from django.utils import timezone
        self.confirmada = True
        self.fecha_confirmacion = timezone.now()
        self.save(update_fields=['confirmada', 'fecha_confirmacion'])


# ═══════════════════════════════════════════════════════════════
# DOCUMENTOS LABORALES (Fase 6.3)
# Distribución formal de políticas, reglamentos y comunicados
# con constancia de entrega y confirmación de recepción.
#
# Base legal:
# - DS 003-97-TR Art. 35: obligación de poner en conocimiento el RISST
# - Ley 29783 Art. 35: difusión de política SST y reglamento
# - DL 728: comunicación de reglamento interno de trabajo
# ═══════════════════════════════════════════════════════════════

class DocumentoLaboral(models.Model):
    """
    Documento laboral formal emitido por la empresa.
    Ej: Reglamento Interno, Políticas, Memos, Cartas Circulares.
    Al publicarse genera entregas individuales para cada destinatario.
    """
    TIPO_CHOICES = [
        ('REGLAMENTO', 'Reglamento Interno'),
        ('POLITICA', 'Política'),
        ('COMUNICADO', 'Comunicado'),
        ('MEMO', 'Memorándum'),
        ('CARTA', 'Carta Circular'),
        ('SST', 'Política SST'),
        ('OTRO', 'Otro'),
    ]
    DESTINATARIOS_CHOICES = [
        ('TODOS', 'Todos los trabajadores'),
        ('STAFF', 'Solo STAFF'),
        ('RCO', 'Solo RCO'),
        ('AREA', 'Por Área(s)'),
        ('INDIVIDUAL', 'Individual'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PUBLICADO', 'Publicado'),
        ('ARCHIVADO', 'Archivado'),
    ]

    titulo = models.CharField(max_length=300, verbose_name='Título')
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='COMUNICADO')
    descripcion = models.TextField(blank=True, verbose_name='Descripción / Resumen')
    archivo = models.FileField(
        upload_to='documentos_laborales/%Y/%m/',
        null=True, blank=True,
        verbose_name='Archivo (PDF/DOC)',
        help_text='Sube el documento en formato PDF o Word.',
    )
    contenido_html = models.TextField(
        blank=True,
        verbose_name='Contenido inline',
        help_text='Alternativo al archivo - se mostrará directamente en pantalla.',
    )

    # Destinatarios
    destinatarios_tipo = models.CharField(
        max_length=15, choices=DESTINATARIOS_CHOICES, default='TODOS',
        verbose_name='Destinatarios',
    )
    areas = models.ManyToManyField(
        'personal.Area', blank=True, related_name='docs_laborales',
        verbose_name='Áreas destino',
        help_text='Solo aplica cuando Destinatarios = Por Área(s).',
    )
    personal_especifico = models.ManyToManyField(
        'personal.Personal', blank=True, related_name='docs_laborales_individuales',
        verbose_name='Personal específico',
        help_text='Solo aplica cuando Destinatarios = Individual.',
    )

    # Control
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    requiere_confirmacion = models.BooleanField(
        default=True,
        verbose_name='Requiere confirmación',
        help_text='El trabajador debe confirmar recepción del documento.',
    )
    vigente_hasta = models.DateField(
        null=True, blank=True,
        verbose_name='Vigente hasta',
        help_text='Fecha límite de vigencia del documento.',
    )

    # Auditoría
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Documento Laboral'
        verbose_name_plural = 'Documentos Laborales'
        indexes = [
            models.Index(fields=['estado', '-creado_en']),
        ]

    def __str__(self):
        return f'[{self.get_tipo_display()}] {self.titulo}'

    @property
    def total_destinatarios(self):
        return self.entregas.count()

    @property
    def total_confirmados(self):
        return self.entregas.filter(confirmado=True).count()

    @property
    def tasa_confirmacion(self):
        total = self.total_destinatarios
        if total == 0:
            return 0
        return round(self.total_confirmados / total * 100)

    def publicar(self, usuario=None):
        """
        Publica el documento y genera EntregaDocumento para cada destinatario.
        Idempotente: no crea duplicados si ya fue publicado antes.
        """
        from django.utils import timezone
        from personal.models import Personal

        self.estado = 'PUBLICADO'
        self.fecha_publicacion = timezone.now()
        self.save(update_fields=['estado', 'fecha_publicacion'])

        # Determinar destinatarios
        qs = Personal.objects.filter(estado='Activo')
        dt = self.destinatarios_tipo
        if dt == 'STAFF':
            qs = qs.filter(grupo_tareo='STAFF')
        elif dt == 'RCO':
            qs = qs.filter(grupo_tareo='RCO')
        elif dt == 'AREA':
            qs = qs.filter(subarea__area__in=self.areas.all()).distinct()
        elif dt == 'INDIVIDUAL':
            qs = self.personal_especifico.filter(estado='Activo')

        # Crear entregas sin duplicar
        existentes = set(self.entregas.values_list('personal_id', flat=True))
        nuevas = [
            EntregaDocumento(documento=self, personal=p)
            for p in qs if p.pk not in existentes
        ]
        EntregaDocumento.objects.bulk_create(nuevas, ignore_conflicts=True)
        return len(nuevas)


class EntregaDocumento(models.Model):
    """
    Registro de entrega individual de un DocumentoLaboral a un trabajador.
    Generado automáticamente al publicar el documento.
    Constancia legal de recepción.
    """
    documento = models.ForeignKey(
        DocumentoLaboral, on_delete=models.CASCADE,
        related_name='entregas',
    )
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='documentos_recibidos',
    )

    # Tracking visualización
    visto = models.BooleanField(default=False)
    fecha_visto = models.DateTimeField(null=True, blank=True)

    # Constancia de confirmación
    confirmado = models.BooleanField(default=False)
    fecha_confirmacion = models.DateTimeField(null=True, blank=True)
    ip_confirmacion = models.GenericIPAddressField(null=True, blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['documento', 'personal']
        ordering = ['personal__apellidos_nombres']
        verbose_name = 'Entrega de Documento'
        verbose_name_plural = 'Entregas de Documentos'
        indexes = [
            models.Index(fields=['personal', 'confirmado']),
        ]

    def __str__(self):
        return f'{self.personal} ← {self.documento.titulo}'

    def marcar_visto(self):
        """Marca el documento como visto por el trabajador."""
        if not self.visto:
            from django.utils import timezone
            self.visto = True
            self.fecha_visto = timezone.now()
            self.save(update_fields=['visto', 'fecha_visto'])

    def confirmar(self, ip=None):
        """Trabajador confirma recepción (constancia legal)."""
        from django.utils import timezone
        now = timezone.now()
        self.confirmado = True
        self.fecha_confirmacion = now
        self.ip_confirmacion = ip
        if not self.visto:
            self.visto = True
            self.fecha_visto = now
        self.save(update_fields=[
            'confirmado', 'fecha_confirmacion', 'ip_confirmacion',
            'visto', 'fecha_visto',
        ])


# ═══════════════════════════════════════════════════════════════
# DOSSIER DOCUMENTARIO
# Paquete de documentación laboral organizado para proyectos,
# licitaciones o auditorías (común en construcción / minería).
#
# Flujo: PlantillaDossier → Dossier (por proyecto) →
#        vincular Personal → generar DossierItem (auto desde legajo)
#
# Base legal:
# - Ley 30225 (Contrataciones Estado): documentación RRHH para obras
# - DS 011-2019-TR: registros SST en contratistas
# - ISO 45001: documentación de personal en gestión SST
# ═══════════════════════════════════════════════════════════════

class PlantillaDossier(models.Model):
    """
    Plantilla que define los documentos requeridos en un dossier
    y el orden en que deben presentarse.

    Ejemplos: 'Dossier Obra Minera SSOMA', 'Entregable Licitación OSCE',
              'Auditoría ISO 45001', 'Cierre de Proyecto'.
    """
    TIPO_CHOICES = [
        ('PROYECTO',    'Cierre de Proyecto'),
        ('LICITACION',  'Licitación / Concurso'),
        ('AUDITORIA',   'Auditoría'),
        ('CLIENTE',     'Entregable a Cliente'),
        ('INTERNO',     'Control Interno'),
        ('OTRO',        'Otro'),
    ]

    nombre      = models.CharField(max_length=200)
    codigo      = models.SlugField(max_length=80, unique=True,
                    help_text='Identificador único (auto-generado).')
    tipo        = models.CharField(max_length=15, choices=TIPO_CHOICES, default='PROYECTO')
    descripcion = models.TextField(blank=True)
    activa      = models.BooleanField(default=True)

    creado_por  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    creado_en   = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['nombre']
        verbose_name = 'Plantilla de Dossier'
        verbose_name_plural = 'Plantillas de Dossier'

    def __str__(self):
        return f'{self.nombre} [{self.get_tipo_display()}]'

    def save(self, *args, **kwargs):
        if not self.codigo:
            from django.utils.text import slugify
            base = slugify(self.nombre)[:70]
            slug = base
            n = 1
            while PlantillaDossier.objects.filter(codigo=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.codigo = slug
        super().save(*args, **kwargs)

    @property
    def total_items(self):
        return self.items.count()


class PlantillaDossierItem(models.Model):
    """
    Ítem ordenado dentro de una PlantillaDossier.
    Define qué TipoDocumento se necesita, en qué orden,
    bajo qué sección y si es obligatorio para esa plantilla.
    """
    plantilla       = models.ForeignKey(
        PlantillaDossier, on_delete=models.CASCADE, related_name='items',
    )
    tipo_documento  = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name='+',
    )
    seccion         = models.CharField(
        max_length=150, blank=True,
        help_text='Sección o capítulo (ej: "I. Documentos de Identidad").',
    )
    orden           = models.PositiveSmallIntegerField(default=0)
    obligatorio     = models.BooleanField(
        default=True,
        help_text='Si es obligatorio para esta plantilla (override por plantilla).',
    )
    instruccion     = models.CharField(
        max_length=300, blank=True,
        help_text='Nota específica para este ítem (ej: "Vigente al momento de la obra").',
    )

    class Meta:
        ordering = ['orden', 'seccion']
        unique_together = ['plantilla', 'tipo_documento']
        verbose_name = 'Ítem de Plantilla Dossier'
        verbose_name_plural = 'Ítems de Plantilla Dossier'

    def __str__(self):
        return f'[{self.orden}] {self.tipo_documento.nombre}'


class Dossier(models.Model):
    """
    Dossier documentario para un proyecto/obra específico.
    Agrupa los documentos RRHH de los trabajadores asignados,
    organizados según una PlantillaDossier.
    """
    ESTADO_CHOICES = [
        ('BORRADOR',    'Borrador'),
        ('EN_REVISION', 'En Revisión'),
        ('APROBADO',    'Aprobado'),
        ('ENTREGADO',   'Entregado'),
        ('ARCHIVADO',   'Archivado'),
    ]

    plantilla               = models.ForeignKey(
        PlantillaDossier, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossiers',
        help_text='Plantilla base. Puede dejarse vacía para armar ad-hoc.',
    )
    nombre                  = models.CharField(
        max_length=250,
        help_text='Ej: "Dossier RRHH - Proyecto Expansión Norte Q1-2026"',
    )
    proyecto                = models.CharField(max_length=200, blank=True,
                                help_text='Nombre / código del proyecto u obra.')
    cliente                 = models.CharField(max_length=200, blank=True)
    estado                  = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='BORRADOR',
    )
    fecha_inicio            = models.DateField(null=True, blank=True)
    fecha_entrega_prevista  = models.DateField(null=True, blank=True)
    fecha_entrega_real      = models.DateField(null=True, blank=True)
    observaciones           = models.TextField(blank=True)

    responsable             = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='dossiers_responsable',
    )
    creado_por              = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='dossiers_creados',
    )
    creado_en               = models.DateTimeField(auto_now_add=True)
    actualizado_en          = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Dossier'
        verbose_name_plural = 'Dossiers'
        indexes = [
            models.Index(fields=['estado', '-creado_en']),
        ]

    def __str__(self):
        return self.nombre

    # ── Helpers de progreso ──────────────────────────────────────

    @property
    def total_personal(self):
        return self.personal_dossier.count()

    @property
    def total_items(self):
        return self.items.exclude(estado='NO_APLICA').count()

    @property
    def items_completos(self):
        return self.items.filter(estado='COMPLETO').count()

    @property
    def progreso(self):
        """Porcentaje de ítems completos (excluyendo NO_APLICA)."""
        total = self.total_items
        if total == 0:
            return 0
        return round(self.items_completos / total * 100)

    @property
    def color_estado(self):
        return {
            'BORRADOR':    'secondary',
            'EN_REVISION': 'warning',
            'APROBADO':    'success',
            'ENTREGADO':   'primary',
            'ARCHIVADO':   'dark',
        }.get(self.estado, 'secondary')

    # ── Lógica de negocio ────────────────────────────────────────

    def generar_items(self):
        """
        Genera DossierItem para todos los DossierPersonal × ítems de la plantilla.
        Idempotente: no duplica si ya existen.
        Devuelve (creados, existentes).
        """
        if not self.plantilla:
            return 0, 0

        plantilla_items = list(self.plantilla.items.select_related('tipo_documento'))
        trabajadores = list(self.personal_dossier.select_related('personal'))

        creados = existentes = 0
        for dp in trabajadores:
            for pi in plantilla_items:
                _, created = DossierItem.objects.get_or_create(
                    dossier=self,
                    personal=dp.personal,
                    tipo_documento=pi.tipo_documento,
                    defaults={
                        'orden': pi.orden,
                        'seccion': pi.seccion,
                        'obligatorio': pi.obligatorio,
                        'instruccion': pi.instruccion,
                    },
                )
                if created:
                    creados += 1
                else:
                    existentes += 1

        return creados, existentes

    def vincular_documentos(self):
        """
        Vincula automáticamente DocumentoTrabajador vigentes existentes en el legajo
        a los DossierItem pendientes.
        Devuelve cantidad de ítems vinculados.
        """
        vinculados = 0
        items_pendientes = self.items.filter(
            estado='PENDIENTE', documento__isnull=True,
        ).select_related('personal', 'tipo_documento')

        for item in items_pendientes:
            doc = DocumentoTrabajador.objects.filter(
                personal=item.personal,
                tipo=item.tipo_documento,
                estado__in=['VIGENTE', 'POR_VENCER'],
            ).order_by('-creado_en').first()

            if doc:
                item.documento = doc
                item.estado = 'COMPLETO'
                item.save(update_fields=['documento', 'estado'])
                vinculados += 1

        return vinculados

    def progreso_por_personal(self):
        """Devuelve lista de {personal, total, completos, pct} para el detalle."""
        resultado = []
        for dp in self.personal_dossier.select_related('personal').order_by(
            'personal__apellidos_nombres'
        ):
            total = self.items.filter(
                personal=dp.personal,
            ).exclude(estado='NO_APLICA').count()
            completos = self.items.filter(
                personal=dp.personal, estado='COMPLETO',
            ).count()
            pct = round(completos / total * 100) if total else 0
            resultado.append({
                'dp': dp,
                'personal': dp.personal,
                'total': total,
                'completos': completos,
                'pct': pct,
                'color': 'success' if pct == 100 else ('warning' if pct >= 50 else 'danger'),
            })
        return resultado


class DossierPersonal(models.Model):
    """Trabajador incluido en un Dossier."""
    dossier  = models.ForeignKey(
        Dossier, on_delete=models.CASCADE, related_name='personal_dossier',
    )
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE, related_name='dossiers',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['dossier', 'personal']
        ordering = ['personal__apellidos_nombres']
        verbose_name = 'Personal del Dossier'
        verbose_name_plural = 'Personal del Dossier'

    def __str__(self):
        return f'{self.personal} → {self.dossier}'


class DossierItem(models.Model):
    """
    Slot de documento dentro de un Dossier para un trabajador específico.
    Se genera automáticamente desde la PlantillaDossier al llamar
    Dossier.generar_items(). Puede vincularse al DocumentoTrabajador existente.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE',  'Pendiente'),
        ('COMPLETO',   'Completo'),
        ('OBSERVADO',  'Observado'),
        ('NO_APLICA',  'No Aplica'),
    ]

    dossier         = models.ForeignKey(
        Dossier, on_delete=models.CASCADE, related_name='items',
    )
    personal        = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE, related_name='+',
    )
    tipo_documento  = models.ForeignKey(
        TipoDocumento, on_delete=models.PROTECT, related_name='+',
    )
    documento       = models.ForeignKey(
        DocumentoTrabajador, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='dossier_items',
        help_text='Documento del legajo vinculado a este ítem.',
    )
    orden       = models.PositiveSmallIntegerField(default=0)
    seccion     = models.CharField(max_length=150, blank=True)
    obligatorio = models.BooleanField(default=True)
    instruccion = models.CharField(max_length=300, blank=True)
    estado      = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE',
    )
    observacion = models.TextField(blank=True)

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['dossier', 'personal', 'tipo_documento']
        ordering = ['personal__apellidos_nombres', 'orden']
        verbose_name = 'Ítem de Dossier'
        verbose_name_plural = 'Ítems de Dossier'
        indexes = [
            models.Index(fields=['dossier', 'estado']),
            models.Index(fields=['dossier', 'personal']),
        ]

    def __str__(self):
        return f'{self.personal} | {self.tipo_documento.nombre} [{self.get_estado_display()}]'

    @property
    def color_estado(self):
        return {
            'PENDIENTE': 'warning',
            'COMPLETO':  'success',
            'OBSERVADO': 'danger',
            'NO_APLICA': 'secondary',
        }.get(self.estado, 'secondary')



class FirmaDigital(models.Model):
    """
    Firma digital con captura en canvas (signature pad).
    Almacena la imagen de la firma como base64 PNG + hash SHA-256
    del documento al momento de firmar para verificacion de integridad.

    Legalmente util: hash_documento demuestra que el documento
    no fue modificado despues de la firma.

    Base legal:
    - Ley 27269: Ley de Firmas y Certificados Digitales (Peru)
    - DS 052-2008-PCM: Reglamento de firma electronica
    """

    TIPO_DOCUMENTO_CHOICES = [
        ('CONSTANCIA', 'Constancia Generada'),
        ('DOCUMENTO', 'Documento del Trabajador'),
        ('LABORAL', 'Documento Laboral'),
        ('BOLETA', 'Boleta de Pago'),
        ('OTRO', 'Otro'),
    ]

    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de firma'),
        ('FIRMADO', 'Firmado'),
        ('RECHAZADO', 'Rechazado'),
        ('VENCIDO', 'Link vencido'),
    ]

    # Referencia al documento (flexible: puede ser constancia, doc laboral, etc.)
    tipo_documento = models.CharField(
        max_length=20, choices=TIPO_DOCUMENTO_CHOICES, default='CONSTANCIA',
    )
    constancia = models.ForeignKey(
        ConstanciaGenerada, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='firmas',
        verbose_name='Constancia (si aplica)',
    )
    documento_trabajador = models.ForeignKey(
        DocumentoTrabajador, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='firmas',
        verbose_name='Documento del trabajador (si aplica)',
    )
    documento_laboral = models.ForeignKey(
        'documentos.DocumentoLaboral', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='firmas',
        verbose_name='Documento laboral (si aplica)',
    )
    titulo_documento = models.CharField(
        max_length=300, blank=True,
        help_text='Titulo descriptivo del documento firmado.',
    )

    # Firmante
    firmante = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='firmas_digitales',
        verbose_name='Firmante',
    )

    # Firma capturada
    firma_imagen = models.TextField(
        blank=True,
        help_text='Imagen de la firma en base64 (data:image/png;base64,...)',
    )

    # Integridad del documento
    hash_documento = models.CharField(
        max_length=64, blank=True, db_index=True,
        help_text='SHA-256 del contenido del documento al momento de firmar.',
    )

    # Trazabilidad
    ip_address = models.GenericIPAddressField(
        null=True, blank=True,
        verbose_name='Direccion IP',
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User-Agent del navegador',
    )

    # Token unico para link de firma (sin login requerido)
    token = models.CharField(
        max_length=64, unique=True, db_index=True,
        help_text='Token unico para URL de firma.',
    )

    # Estado y fechas
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE',
    )
    solicitado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Solicitado por',
    )
    solicitado_en = models.DateTimeField(auto_now_add=True)
    firmado_en = models.DateTimeField(null=True, blank=True)
    vence_en = models.DateField(
        null=True, blank=True,
        help_text='Fecha limite para firmar.',
    )
    motivo_rechazo = models.TextField(blank=True)
    notas = models.TextField(blank=True)

    class Meta:
        ordering = ['-solicitado_en']
        verbose_name = 'Firma Digital (Interna)'
        verbose_name_plural = 'Firmas Digitales (Internas)'
        indexes = [
            models.Index(fields=['firmante', 'estado']),
            models.Index(fields=['token']),
            models.Index(fields=['hash_documento']),
        ]

    def __str__(self):
        return f'Firma: {self.titulo_documento} - {self.firmante} [{self.get_estado_display()}]'

    def save(self, *args, **kwargs):
        if not self.token:
            import secrets
            self.token = secrets.token_urlsafe(48)
        super().save(*args, **kwargs)

    @property
    def esta_vencido(self):
        from datetime import date
        if self.vence_en and self.estado == 'PENDIENTE':
            return date.today() > self.vence_en
        return False

    @property
    def color_estado(self):
        return {
            'PENDIENTE': 'warning',
            'FIRMADO': 'success',
            'RECHAZADO': 'danger',
            'VENCIDO': 'secondary',
        }.get(self.estado, 'secondary')

    @property
    def icono_estado(self):
        return {
            'PENDIENTE': 'fa-clock',
            'FIRMADO': 'fa-check-circle',
            'RECHAZADO': 'fa-times-circle',
            'VENCIDO': 'fa-calendar-times',
        }.get(self.estado, 'fa-file')

    @property
    def documento_referencia(self):
        """Retorna el objeto documento relacionado (cualquiera de los tipos)."""
        if self.constancia:
            return self.constancia
        if self.documento_trabajador:
            return self.documento_trabajador
        if self.documento_laboral:
            return self.documento_laboral
        return None

    def verificar_integridad(self, contenido_actual_hash):
        """Verifica que el hash del documento no haya cambiado."""
        return self.hash_documento == contenido_actual_hash


class DocumentoFirmaDigital(models.Model):
    """
    Documento enviado a ZapSign para firma electronica.

    Flujo:
    1. Admin sube PDF + selecciona firmante(s)
    2. Sistema envia a ZapSign API -> obtiene token + link firma
    3. Trabajador recibe email con link para firmar
    4. Sistema monitorea estado via API
    5. PDF firmado disponible para descarga
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente envio'),
        ('ENVIADO',   'Enviado a ZapSign'),
        ('FIRMANDO',  'En proceso de firma'),
        ('FIRMADO',   'Firmado completamente'),
        ('RECHAZADO', 'Rechazado por firmante'),
        ('VENCIDO',   'Link vencido'),
        ('CANCELADO', 'Cancelado'),
        ('ERROR',     'Error de envio'),
    ]

    TIPO_CHOICES = [
        ('CONTRATO',     'Contrato de Trabajo'),
        ('ADENDA',       'Adenda / Modificacion'),
        ('CARTA',        'Carta'),
        ('MEMORANDUM',   'Memorandum'),
        ('ACTA',         'Acta'),
        ('CONFIDENCIAL', 'Acuerdo Confidencialidad'),
        ('RENUNCIA',     'Carta de Renuncia'),
        ('FINIQUITO',    'Finiquito / Liquidacion'),
        ('OTRO',         'Otro'),
    ]

    personal    = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='documentos_firma',
        verbose_name='Trabajador',
    )
    nombre      = models.CharField(max_length=200, verbose_name='Nombre del documento')
    tipo        = models.CharField(max_length=20, choices=TIPO_CHOICES, default='OTRO')
    descripcion = models.TextField(blank=True)

    # Archivo PDF original
    archivo_pdf = models.FileField(
        upload_to='firma_digital/%Y/%m/',
        verbose_name='PDF a firmar',
        help_text='Sube el documento PDF que debe ser firmado.',
    )

    # ZapSign tokens y URLs
    zapsign_token    = models.CharField(max_length=200, blank=True, db_index=True,
                                        verbose_name='Token ZapSign')
    zapsign_doc_url  = models.URLField(blank=True, verbose_name='URL documento ZapSign')
    signer_token     = models.CharField(max_length=200, blank=True,
                                        verbose_name='Token firmante')
    signer_url       = models.URLField(blank=True, verbose_name='URL para firmar')

    # Estado
    estado       = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='PENDIENTE')
    error_detalle = models.TextField(blank=True, verbose_name='Detalle del error')

    # Fechas
    creado_en  = models.DateTimeField(auto_now_add=True)
    enviado_en = models.DateTimeField(null=True, blank=True)
    firmado_en = models.DateTimeField(null=True, blank=True)
    vence_en   = models.DateField(null=True, blank=True,
                                  help_text='Fecha limite para firmar.')

    # PDF firmado (URL devuelta por ZapSign)
    pdf_firmado_url = models.URLField(blank=True, verbose_name='URL PDF firmado')

    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    notas = models.TextField(blank=True)

    class Meta:
        ordering            = ['-creado_en']
        verbose_name        = 'Documento para Firma Digital'
        verbose_name_plural = 'Documentos para Firma Digital'
        indexes             = [
            models.Index(fields=['personal', 'estado'], name='firma_personal_estado_idx'),
            models.Index(fields=['estado', 'creado_en'], name='firma_estado_fecha_idx'),
        ]

    def __str__(self):
        return f'{self.nombre} - {self.personal} [{self.get_estado_display()}]'

    @property
    def color_estado(self):
        return {
            'PENDIENTE': 'secondary',
            'ENVIADO':   'info',
            'FIRMANDO':  'warning',
            'FIRMADO':   'success',
            'RECHAZADO': 'danger',
            'VENCIDO':   'muted',
            'CANCELADO': 'muted',
            'ERROR':     'danger',
        }.get(self.estado, 'secondary')

    @property
    def icono_estado(self):
        return {
            'PENDIENTE': 'fa-clock',
            'ENVIADO':   'fa-paper-plane',
            'FIRMANDO':  'fa-pen',
            'FIRMADO':   'fa-check-circle',
            'RECHAZADO': 'fa-times-circle',
            'VENCIDO':   'fa-calendar-times',
            'CANCELADO': 'fa-ban',
            'ERROR':     'fa-exclamation-triangle',
        }.get(self.estado, 'fa-file')


# ═══════════════════════════════════════════════════════════════
# ARCHIVOS HR — Envío de archivos de RRHH al trabajador
# Permite subir cualquier archivo (informes, comunicados, etc.)
# para que el trabajador lo descargue desde su portal.
# ═══════════════════════════════════════════════════════════════

class ArchivoHR(models.Model):
    """
    Archivo enviado por RRHH a un trabajador específico para descarga desde el portal.
    Diferente a DocumentoTrabajador (legajo) y BoletaPago (nómina):
    este modelo cubre comunicados, informes, memos y cualquier archivo ad-hoc.
    """
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='archivos_hr', verbose_name='Trabajador',
    )
    nombre = models.CharField(max_length=255, verbose_name='Nombre del archivo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    archivo = models.FileField(
        upload_to='archivos_hr/%Y/%m/',
        verbose_name='Archivo',
    )
    periodo = models.CharField(
        max_length=7, blank=True,
        help_text='Período referencial, ej: 2026-03',
        verbose_name='Período',
    )
    visible = models.BooleanField(
        default=True,
        help_text='Si está activo, el trabajador puede verlo y descargarlo.',
        verbose_name='Visible para el trabajador',
    )

    # Auditoría
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+', verbose_name='Subido por',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    # Registro de descarga
    descargado = models.BooleanField(default=False)
    fecha_descarga = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Archivo HR'
        verbose_name_plural = 'Archivos HR'
        indexes = [
            models.Index(fields=['personal', '-creado_en']),
        ]

    def __str__(self):
        return f'{self.nombre} → {self.personal}'

    @property
    def extension(self):
        if self.archivo and self.archivo.name:
            return self.archivo.name.rsplit('.', 1)[-1].lower()
        return ''

    @property
    def icono_archivo(self):
        ext = self.extension
        if ext == 'pdf':
            return 'fa-file-pdf text-danger'
        if ext in ('jpg', 'jpeg', 'png', 'gif', 'webp'):
            return 'fa-file-image text-primary'
        if ext in ('doc', 'docx'):
            return 'fa-file-word text-info'
        if ext in ('xls', 'xlsx'):
            return 'fa-file-excel text-success'
        if ext in ('zip', 'rar', '7z'):
            return 'fa-file-zipper text-warning'
        return 'fa-file text-muted'
