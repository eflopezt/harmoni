"""
Módulo de Encuestas y Clima Laboral.
Incluye encuestas configurables, eNPS, pulsos rápidos, análisis anónimo.
"""
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from personal.models import Personal, Area


class Encuesta(models.Model):
    """Encuesta configurable con soporte anónimo."""
    TIPO_CHOICES = [
        ('CLIMA', 'Clima Laboral'),
        ('PULSO', 'Pulso Rápido'),
        ('SATISFACCION', 'Satisfacción'),
        ('ENPS', 'eNPS'),
        ('SALIDA', 'Encuesta de Salida'),
        ('ONBOARDING', 'Encuesta Onboarding'),
        ('CUSTOM', 'Personalizada'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PROGRAMADA', 'Programada'),
        ('ACTIVA', 'Activa'),
        ('CERRADA', 'Cerrada'),
        ('ARCHIVADA', 'Archivada'),
    ]

    titulo = models.CharField(max_length=300, verbose_name='Título')
    descripcion = models.TextField(blank=True)
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES, default='CLIMA')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    anonima = models.BooleanField(
        default=True,
        verbose_name='Anónima',
        help_text='Si es anónima, no se vincula respuesta con trabajador',
    )
    fecha_inicio = models.DateField(verbose_name='Fecha Inicio')
    fecha_fin = models.DateField(verbose_name='Fecha Fin')
    aplica_areas = models.ManyToManyField(
        Area, blank=True, related_name='encuestas',
        verbose_name='Áreas participantes',
        help_text='Vacío = aplica a todas',
    )
    aplica_grupos = models.CharField(
        max_length=20, blank=True,
        choices=[('', 'Todos'), ('STAFF', 'Solo STAFF'), ('RCO', 'Solo RCO')],
        verbose_name='Grupo',
    )
    max_respuestas = models.PositiveIntegerField(
        default=0, help_text='0 = sin límite',
    )
    recordatorio_dias = models.PositiveSmallIntegerField(
        default=3, verbose_name='Recordatorio cada (días)',
        help_text='0 = sin recordatorios',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Encuesta'
        verbose_name_plural = 'Encuestas'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f'{self.titulo} ({self.get_tipo_display()})'

    @property
    def total_preguntas(self):
        return self.preguntas.count()

    @property
    def total_respuestas(self):
        return self.respuestas.count()

    @property
    def tasa_participacion(self):
        """Porcentaje de participación (requiere calcular universo)."""
        total = self.total_respuestas
        if total == 0:
            return 0
        # Universo aproximado
        from personal.models import Personal
        qs = Personal.objects.filter(estado='Activo')
        if self.aplica_grupos:
            qs = qs.filter(grupo_tareo=self.aplica_grupos)
        universo = qs.count()
        if universo == 0:
            return 0
        return round((total / universo) * 100)


class PreguntaEncuesta(models.Model):
    """Pregunta dentro de una encuesta."""
    TIPO_CHOICES = [
        ('ESCALA_5', 'Escala 1-5'),
        ('ESCALA_10', 'Escala 0-10 (NPS)'),
        ('OPCION', 'Opción Múltiple'),
        ('SI_NO', 'Sí / No'),
        ('TEXTO', 'Texto Libre'),
        ('MATRIZ', 'Matriz'),
    ]

    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE, related_name='preguntas')
    texto = models.CharField(max_length=500, verbose_name='Pregunta')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='ESCALA_5')
    obligatoria = models.BooleanField(default=True)
    opciones = models.JSONField(
        default=list, blank=True,
        verbose_name='Opciones',
        help_text='Lista de opciones para preguntas de opción múltiple. Ej: ["Muy bueno","Bueno","Regular","Malo"]',
    )
    categoria = models.CharField(
        max_length=50, blank=True,
        verbose_name='Categoría/Dimensión',
        help_text='Ej: Liderazgo, Comunicación, Ambiente, Compensación',
    )
    orden = models.PositiveSmallIntegerField(default=10)

    class Meta:
        verbose_name = 'Pregunta'
        verbose_name_plural = 'Preguntas'
        ordering = ['orden']

    def __str__(self):
        return f'{self.texto[:60]}...' if len(self.texto) > 60 else self.texto


class RespuestaEncuesta(models.Model):
    """Respuesta completa de una persona a una encuesta."""
    encuesta = models.ForeignKey(Encuesta, on_delete=models.CASCADE, related_name='respuestas')
    # Si la encuesta es anónima, personal es NULL
    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='respuestas_encuestas',
    )
    # Metadata anónima (solo grupo y área, sin identificar persona)
    area_anonima = models.CharField(max_length=100, blank=True)
    grupo_anonimo = models.CharField(max_length=10, blank=True)
    respuestas = models.JSONField(
        default=dict,
        verbose_name='Respuestas',
        help_text='Dict { pregunta_id: valor }',
    )
    comentarios = models.TextField(blank=True, verbose_name='Comentarios Adicionales')
    fecha_respuesta = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        verbose_name = 'Respuesta a Encuesta'
        verbose_name_plural = 'Respuestas a Encuestas'
        ordering = ['-fecha_respuesta']

    def __str__(self):
        if self.personal:
            return f'{self.personal.apellidos_nombres} → {self.encuesta.titulo}'
        return f'Anónimo ({self.area_anonima}) → {self.encuesta.titulo}'


class ResultadoEncuesta(models.Model):
    """Resultado agregado de una encuesta (calculado al cerrar)."""
    encuesta = models.OneToOneField(Encuesta, on_delete=models.CASCADE, related_name='resultado')
    total_participantes = models.PositiveIntegerField(default=0)
    tasa_participacion = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    # eNPS
    enps_score = models.IntegerField(
        null=True, blank=True,
        verbose_name='eNPS Score',
        help_text='Employee Net Promoter Score (-100 a +100)',
    )
    enps_promotores = models.PositiveIntegerField(default=0)
    enps_pasivos = models.PositiveIntegerField(default=0)
    enps_detractores = models.PositiveIntegerField(default=0)
    # Puntajes por dimensión (JSON: {categoria: promedio})
    puntajes_dimension = models.JSONField(
        default=dict, blank=True,
        verbose_name='Puntajes por Dimensión',
    )
    # Puntaje general
    puntaje_general = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
    )
    calculado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Resultado de Encuesta'
        verbose_name_plural = 'Resultados de Encuestas'

    def __str__(self):
        return f'Resultado: {self.encuesta.titulo}'

    def calcular_enps(self):
        """Calcula eNPS a partir de respuestas NPS (0-10)."""
        preguntas_nps = self.encuesta.preguntas.filter(tipo='ESCALA_10')
        if not preguntas_nps.exists():
            return

        promotores = 0
        detractores = 0
        total = 0

        for resp in self.encuesta.respuestas.all():
            for preg in preguntas_nps:
                val = resp.respuestas.get(str(preg.pk))
                if val is not None:
                    val = int(val)
                    total += 1
                    if val >= 9:
                        promotores += 1
                    elif val <= 6:
                        detractores += 1

        self.enps_promotores = promotores
        self.enps_detractores = detractores
        self.enps_pasivos = total - promotores - detractores
        if total > 0:
            self.enps_score = round(((promotores - detractores) / total) * 100)
        self.save()


# ──────────────────────────────────────────────────────────────────────────────
# Pulse Semanal — encuesta corta semanal de clima laboral por trabajador.
# Diseñada para gastronomía: una respuesta por semana ISO, 3 preguntas + NPS opc.
# ──────────────────────────────────────────────────────────────────────────────


class PulseSemanal(models.Model):
    """Encuesta pulse semanal por trabajador.

    A diferencia de RespuestaEncuesta (atado a una Encuesta configurable),
    este modelo es un formato fijo y ligero: 3 preguntas + NPS opcional.
    Una respuesta por trabajador por semana (unique_together).

    En el dashboard se trata de forma agregada — los textos individuales
    se muestran sin identificación del autor.
    """
    ESTADO_ANIMO = [
        (1, '😡 Muy mal'),
        (2, '😟 Mal'),
        (3, '😐 Regular'),
        (4, '🙂 Bien'),
        (5, '😄 Excelente'),
    ]

    semana = models.PositiveIntegerField(
        help_text='Número ISO de semana (1-53)',
    )
    anio = models.PositiveIntegerField()
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='pulses_semanales',
    )
    personal = models.ForeignKey(
        Personal,
        on_delete=models.CASCADE,
        related_name='pulses_semanales',
    )

    # 3 preguntas core
    animo = models.PositiveSmallIntegerField(
        choices=ESTADO_ANIMO,
        help_text='¿Cómo te sentiste esta semana?',
    )
    que_falta = models.TextField(
        blank=True,
        help_text='¿Qué falta para mejorar?',
    )
    propuestas = models.TextField(
        blank=True,
        help_text='Una propuesta concreta',
    )

    # NPS opcional (0-10)
    nps = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text='¿Recomendarías trabajar aquí? (0-10)',
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pulse Semanal'
        verbose_name_plural = 'Pulses Semanales'
        unique_together = [('personal', 'semana', 'anio')]
        ordering = ['-anio', '-semana']
        indexes = [
            models.Index(fields=['empresa', 'anio', 'semana']),
            models.Index(fields=['anio', 'semana']),
        ]

    def __str__(self):
        return f'Pulse S{self.semana}/{self.anio} · animo={self.animo}'

    @property
    def categoria_nps(self):
        """Clasifica el NPS en promotor/neutro/detractor."""
        if self.nps is None:
            return None
        if self.nps >= 9:
            return 'promotor'
        if self.nps >= 7:
            return 'neutro'
        return 'detractor'
