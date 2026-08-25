"""
Modelos del modulo de Reclutamiento y Seleccion.

Modelos:
    - Vacante: posicion abierta para cubrir
    - EtapaPipeline: etapas configurables del proceso de seleccion
    - Postulacion: candidato aplicando a una vacante
    - NotaPostulacion: notas y evaluaciones sobre un candidato
    - EntrevistaPrograma: entrevistas programadas
"""
from datetime import date

from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from decimal import Decimal

from personal.models import Area, Personal
from .managers import PostulacionManager, VacanteManager


# ══════════════════════════════════════════════════════════════
# VACANTE
# ══════════════════════════════════════════════════════════════

class Vacante(models.Model):
    """Posicion abierta para cubrir."""

    EDUCACION_CHOICES = [
        ('NO_REQUERIDO', 'No Requerido'),
        ('SECUNDARIA', 'Secundaria'),
        ('TECNICO', 'Tecnico'),
        ('UNIVERSITARIO', 'Universitario'),
        ('MAESTRIA', 'Maestria'),
        ('DOCTORADO', 'Doctorado'),
    ]

    TIPO_CONTRATO_CHOICES = [
        ('INDETERMINADO', 'Plazo Indeterminado'),
        ('PLAZO_FIJO', 'Plazo Fijo'),
        ('PROYECTO', 'Por Proyecto'),
        ('SUPLENCIA', 'Suplencia'),
    ]

    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('POR_APROBAR', 'Por aprobar'),
        ('APROBADA', 'Aprobada'),
        ('PUBLICADA', 'Publicada'),
        ('EN_PROCESO', 'En Proceso'),
        ('CUBIERTA', 'Cubierta'),
        ('CANCELADA', 'Cancelada'),
    ]

    PRIORIDAD_CHOICES = [
        ('BAJA', 'Baja'),
        ('MEDIA', 'Media'),
        ('ALTA', 'Alta'),
        ('URGENTE', 'Urgente'),
    ]

    MONEDA_CHOICES = [
        ('PEN', 'PEN'),
        ('USD', 'USD'),
    ]

    titulo = models.CharField(max_length=200, verbose_name="Titulo del Puesto")
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='vacantes_harmoni',
        verbose_name='Empresa',
        help_text='RUC empleador al que pertenece la requisicion.',
    )
    area = models.ForeignKey(
        Area,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vacantes',
        verbose_name="Area"
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripcion")
    requisitos = models.TextField(blank=True, verbose_name="Requisitos")
    experiencia_minima = models.PositiveIntegerField(
        default=0,
        verbose_name="Experiencia Minima (anios)",
        help_text="Anios de experiencia requeridos"
    )
    educacion_minima = models.CharField(
        max_length=15,
        choices=EDUCACION_CHOICES,
        default='NO_REQUERIDO',
        verbose_name="Educacion Minima"
    )
    tipo_contrato = models.CharField(
        max_length=15,
        choices=TIPO_CONTRATO_CHOICES,
        default='INDETERMINADO',
        verbose_name="Tipo de Contrato"
    )
    salario_min = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Salario Minimo"
    )
    salario_max = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Salario Maximo"
    )
    moneda = models.CharField(
        max_length=3,
        choices=MONEDA_CHOICES,
        default='PEN',
        verbose_name="Moneda"
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
        verbose_name="Estado"
    )
    prioridad = models.CharField(
        max_length=10,
        choices=PRIORIDAD_CHOICES,
        default='MEDIA',
        verbose_name="Prioridad"
    )
    fecha_publicacion = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Publicacion"
    )
    fecha_limite = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha Limite"
    )
    responsable = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vacantes_responsable',
        verbose_name="Responsable"
    )
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vacantes_creadas',
        verbose_name="Creado por"
    )
    publica = models.BooleanField(
        default=False,
        verbose_name="Visible en Portal de Empleo",
        help_text="Si esta marcada, aparece en la pagina publica de empleo"
    )

    # ── Aprobación de requisición (paso previo a publicar) ──
    justificacion = models.TextField(
        blank=True,
        verbose_name="Justificación del requerimiento",
        help_text="Necesidad que sustenta la vacante (para aprobación)"
    )
    aprobada_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vacantes_aprobadas',
        verbose_name="Aprobada por"
    )
    fecha_aprobacion = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha de aprobación"
    )

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = VacanteManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Vacante"
        verbose_name_plural = "Vacantes"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['empresa', 'estado'], name='vacante_empresa_estado_idx'),
            models.Index(fields=['estado']),
            models.Index(fields=['area']),
            models.Index(fields=['prioridad']),
            models.Index(fields=['-creado_en']),
        ]

    def __str__(self):
        return f"{self.titulo} ({self.get_estado_display()})"

    @property
    def total_postulaciones(self):
        return self.postulaciones.count()

    @property
    def postulaciones_activas(self):
        return self.postulaciones.filter(estado='ACTIVA').count()

    @property
    def postulaciones_por_etapa(self):
        """Retorna dict {etapa_id: count} de postulaciones activas."""
        from django.db.models import Count
        return dict(
            self.postulaciones.filter(estado='ACTIVA')
            .values_list('etapa_id')
            .annotate(total=Count('id'))
            .values_list('etapa_id', 'total')
        )

    @property
    def esta_vencida(self):
        if self.fecha_limite:
            return date.today() > self.fecha_limite
        return False


# ══════════════════════════════════════════════════════════════
# ETAPA PIPELINE
# ══════════════════════════════════════════════════════════════

class EtapaPipeline(models.Model):
    """Etapas del pipeline de seleccion (configurables)."""

    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    codigo = models.SlugField(max_length=50, unique=True, verbose_name="Codigo")
    orden = models.PositiveIntegerField(default=0, verbose_name="Orden")
    color = models.CharField(
        max_length=7, default='#94a3b8',
        verbose_name="Color",
        help_text="Color hexadecimal para la columna"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")
    eliminable = models.BooleanField(
        default=True,
        verbose_name="Eliminable",
        help_text="Las etapas del sistema no pueden eliminarse"
    )

    class Meta:
        verbose_name = "Etapa del Pipeline"
        verbose_name_plural = "Etapas del Pipeline"
        ordering = ['orden']

    def __str__(self):
        return self.nombre

    @property
    def total_postulaciones(self):
        return self.postulaciones.filter(estado='ACTIVA').count()


# ══════════════════════════════════════════════════════════════
# POSTULACION
# ══════════════════════════════════════════════════════════════

class Postulacion(models.Model):
    """Candidato postulando a una vacante."""

    EDUCACION_CHOICES = Vacante.EDUCACION_CHOICES

    FUENTE_CHOICES = [
        ('PORTAL', 'Portal de Empleo'),
        ('LINKEDIN', 'LinkedIn'),
        ('REFERIDO', 'Referido'),
        ('HEADHUNTER', 'Headhunter'),
        ('BANCO', 'Banco de Talento'),
        ('OTRO', 'Otro'),
    ]

    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('DESCARTADA', 'Descartada'),
        ('CONTRATADA', 'Contratada'),
    ]

    vacante = models.ForeignKey(
        Vacante,
        on_delete=models.CASCADE,
        related_name='postulaciones',
        verbose_name="Vacante"
    )
    etapa = models.ForeignKey(
        EtapaPipeline,
        on_delete=models.SET_NULL,
        null=True,
        related_name='postulaciones',
        verbose_name="Etapa Actual"
    )
    nombre_completo = models.CharField(max_length=250, verbose_name="Nombre Completo")
    email = models.EmailField(blank=True, verbose_name="Correo Electronico")
    telefono = models.CharField(max_length=30, blank=True, verbose_name="Telefono")
    cv = models.FileField(
        upload_to='reclutamiento/cvs/',
        blank=True, null=True,
        verbose_name="CV"
    )
    experiencia_anos = models.PositiveIntegerField(
        default=0,
        verbose_name="Anios de Experiencia"
    )
    educacion = models.CharField(
        max_length=15,
        choices=EDUCACION_CHOICES,
        default='NO_REQUERIDO',
        verbose_name="Nivel Educativo"
    )
    salario_pretendido = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        verbose_name="Salario Pretendido"
    )
    fuente = models.CharField(
        max_length=12,
        choices=FUENTE_CHOICES,
        default='PORTAL',
        verbose_name="Fuente"
    )
    notas = models.TextField(blank=True, verbose_name="Notas")
    estado = models.CharField(
        max_length=12,
        choices=ESTADO_CHOICES,
        default='ACTIVA',
        verbose_name="Estado"
    )
    fecha_postulacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Postulacion")
    personal_creado = models.ForeignKey(
        Personal,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='postulacion_origen',
        verbose_name="Personal Creado",
        help_text="Vinculo al registro de Personal si fue contratado"
    )

    # ─── CV Parser (importado de NexoTalent) ─────────────────────
    cv_texto_extraido = models.TextField(
        blank=True, default='',
        verbose_name="Texto extraído del CV",
        help_text="Texto plano extraído del PDF/DOCX vía pipeline NexoTalent (PyMuPDF/pdfplumber/python-docx).",
    )
    cv_skills = models.JSONField(
        default=list, blank=True,
        verbose_name="Skills detectados",
        help_text="Lista de skills (JSON array) detectados en el CV.",
    )
    cv_idiomas = models.JSONField(
        default=list, blank=True,
        verbose_name="Idiomas detectados",
    )
    cv_parsed_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Fecha de parseo",
    )
    cv_score = models.IntegerField(
        default=0,
        verbose_name="Score de matching",
        help_text="Puntaje 0-100 de match con la vacante (calculado).",
    )

    # ─── Tags / Etiquetas (gestion power-user) ──────────────────
    TAG_CHOICES = [
        ('top_talent',   'Top Talent'),
        ('prioritario',  'Prioritario'),
        ('referido',     'Referido Interno'),
        ('no_show',      'No Show'),
        ('reubicar',     'Reubicar a otra vacante'),
        ('en_espera',    'En espera'),
        ('seguimiento',  'Seguimiento'),
    ]
    tags = models.JSONField(
        default=list, blank=True,
        verbose_name="Etiquetas",
        help_text="Lista de etiquetas (TAG_CHOICES codes) asignadas al candidato.",
    )

    objects = PostulacionManager()
    all_objects = models.Manager()

    class Meta:
        verbose_name = "Postulacion"
        verbose_name_plural = "Postulaciones"
        ordering = ['-fecha_postulacion']
        indexes = [
            models.Index(fields=['vacante', 'estado']),
            models.Index(fields=['etapa']),
            models.Index(fields=['-fecha_postulacion']),
            # Audit perf 2026-05-24: pipeline_panel filtra Postulacion.objects.filter(estado='ACTIVA')
            # como punto de entrada del kanban. Sin índice estado-leading, PG hace seq scan
            # cuando hay >5K candidatos históricos. Este índice (estado, etapa) cubre el
            # filtro principal + el GROUP BY por etapa.
            models.Index(fields=['estado', 'etapa'],
                         name='postulacion_estado_etapa_idx'),
        ]

    def __str__(self):
        return f"{self.nombre_completo} - {self.vacante.titulo}"

    @property
    def dias_en_proceso(self):
        from django.utils import timezone
        delta = timezone.now() - self.fecha_postulacion
        return delta.days

    # ─── Tags helpers ───────────────────────────────────────
    @property
    def tags_display(self):
        """Lista de tuplas (code, label) para iterar en template."""
        d = dict(self.TAG_CHOICES)
        return [(code, d.get(code, code)) for code in (self.tags or [])]

    def has_tag(self, code):
        return code in (self.tags or [])

    def add_tag(self, code):
        tags = list(self.tags or [])
        if code not in tags:
            tags.append(code)
            self.tags = tags
            self.save(update_fields=['tags'])
        return tags

    def remove_tag(self, code):
        tags = [t for t in (self.tags or []) if t != code]
        self.tags = tags
        self.save(update_fields=['tags'])
        return tags

    def toggle_tag(self, code):
        if self.has_tag(code):
            return self.remove_tag(code)
        return self.add_tag(code)


# ══════════════════════════════════════════════════════════════
# NOTA POSTULACION
# ══════════════════════════════════════════════════════════════

class NotaPostulacion(models.Model):
    """Notas, evaluaciones y observaciones sobre un candidato."""

    TIPO_CHOICES = [
        ('NOTA', 'Nota'),
        ('ENTREVISTA', 'Entrevista'),
        ('EVALUACION', 'Evaluacion'),
        ('REFERENCIA', 'Referencia'),
    ]

    postulacion = models.ForeignKey(
        Postulacion,
        on_delete=models.CASCADE,
        related_name='notas_detalle',
        verbose_name="Postulacion"
    )
    autor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Autor"
    )
    texto = models.TextField(verbose_name="Texto")
    fecha = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")
    tipo = models.CharField(
        max_length=12,
        choices=TIPO_CHOICES,
        default='NOTA',
        verbose_name="Tipo"
    )

    class Meta:
        verbose_name = "Nota de Postulacion"
        verbose_name_plural = "Notas de Postulacion"
        ordering = ['-fecha']

    def __str__(self):
        return f"Nota de {self.autor} sobre {self.postulacion.nombre_completo}"


# ══════════════════════════════════════════════════════════════
# ENTREVISTA PROGRAMA
# ══════════════════════════════════════════════════════════════

class EntrevistaPrograma(models.Model):
    """Entrevistas programadas para un candidato."""

    TIPO_CHOICES = [
        ('RRHH', 'RRHH'),
        ('TECNICA', 'Tecnica'),
        ('GERENCIAL', 'Gerencial'),
        ('GRUPAL', 'Grupal'),
    ]

    MODALIDAD_CHOICES = [
        ('PRESENCIAL', 'Presencial'),
        ('VIRTUAL', 'Virtual'),
        ('TELEFONICA', 'Telefonica'),
    ]

    RESULTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('APROBADO', 'Aprobado'),
        ('RECHAZADO', 'Rechazado'),
        ('REPROGRAMAR', 'Reprogramar'),
    ]

    postulacion = models.ForeignKey(
        Postulacion,
        on_delete=models.CASCADE,
        related_name='entrevistas',
        verbose_name="Postulacion"
    )
    fecha_hora = models.DateTimeField(verbose_name="Fecha y Hora")
    duracion_minutos = models.PositiveIntegerField(
        default=60,
        verbose_name="Duracion (minutos)"
    )
    entrevistador = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='entrevistas_asignadas',
        verbose_name="Entrevistador"
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPO_CHOICES,
        default='RRHH',
        verbose_name="Tipo"
    )
    modalidad = models.CharField(
        max_length=12,
        choices=MODALIDAD_CHOICES,
        default='PRESENCIAL',
        verbose_name="Modalidad"
    )
    ubicacion = models.CharField(
        max_length=200, blank=True,
        verbose_name="Ubicacion"
    )
    enlace_virtual = models.URLField(
        blank=True,
        verbose_name="Enlace Virtual",
        help_text="Link de Meet, Zoom, Teams, etc."
    )
    notas_pre = models.TextField(
        blank=True,
        verbose_name="Notas Previas",
        help_text="Puntos a evaluar, preguntas clave"
    )
    resultado = models.CharField(
        max_length=12,
        choices=RESULTADO_CHOICES,
        default='PENDIENTE',
        verbose_name="Resultado"
    )
    calificacion = models.PositiveIntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(10)],
        verbose_name="Calificacion (1-10)"
    )
    notas_post = models.TextField(
        blank=True,
        verbose_name="Notas Post-Entrevista",
        help_text="Observaciones y conclusiones"
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrevista Programada"
        verbose_name_plural = "Entrevistas Programadas"
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.postulacion.nombre_completo} ({self.fecha_hora:%d/%m/%Y %H:%M})"
