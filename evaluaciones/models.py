"""
Módulo de Evaluaciones de Desempeño.
Incluye ciclos 360°, competencias, evaluaciones, 9-Box y planes de desarrollo.
"""
from decimal import Decimal

from django.conf import settings
from django.db import models

from personal.models import Personal, Area


# ══════════════════════════════════════════════════════════════
# COMPETENCIAS Y PLANTILLAS
# ══════════════════════════════════════════════════════════════

class Competencia(models.Model):
    """Competencia evaluable (ej: Liderazgo, Trabajo en equipo, Puntualidad)."""
    nombre = models.CharField(max_length=100)
    codigo = models.SlugField(max_length=30, unique=True)
    descripcion = models.TextField(blank=True)
    categoria = models.CharField(
        max_length=20,
        choices=[
            ('CORE', 'Core / Organizacional'),
            ('LIDERAZGO', 'Liderazgo'),
            ('TECNICA', 'Técnica'),
            ('INTERPERSONAL', 'Interpersonal'),
        ],
        default='CORE',
    )
    activa = models.BooleanField(default=True)
    orden = models.PositiveSmallIntegerField(default=10)

    class Meta:
        verbose_name = 'Competencia'
        verbose_name_plural = 'Competencias'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class PlantillaEvaluacion(models.Model):
    """Plantilla reutilizable con competencias y pesos."""
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    escala_max = models.PositiveSmallIntegerField(
        default=5, verbose_name='Escala Máxima',
        help_text='Puntaje máximo por competencia (ej: 5)',
    )
    competencias = models.ManyToManyField(
        Competencia,
        through='PlantillaCompetencia',
        related_name='plantillas',
    )
    aplica_autoevaluacion = models.BooleanField(default=True)
    aplica_jefe = models.BooleanField(default=True, verbose_name='Evaluación Jefe')
    aplica_pares = models.BooleanField(default=False, verbose_name='Evaluación Pares')
    aplica_subordinados = models.BooleanField(default=False, verbose_name='Evaluación Subordinados')
    activa = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Plantilla de Evaluación'
        verbose_name_plural = 'Plantillas de Evaluación'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class PlantillaCompetencia(models.Model):
    """Through model: competencia + peso dentro de plantilla."""
    plantilla = models.ForeignKey(PlantillaEvaluacion, on_delete=models.CASCADE, related_name='items')
    competencia = models.ForeignKey(Competencia, on_delete=models.CASCADE)
    peso = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('1.00'),
        verbose_name='Peso', help_text='Factor de ponderación',
    )
    orden = models.PositiveSmallIntegerField(default=10)

    class Meta:
        verbose_name = 'Competencia en Plantilla'
        unique_together = ['plantilla', 'competencia']
        ordering = ['orden']

    def __str__(self):
        return f'{self.plantilla.nombre} → {self.competencia.nombre} (x{self.peso})'


# ══════════════════════════════════════════════════════════════
# CICLOS Y EVALUACIONES
# ══════════════════════════════════════════════════════════════

class CicloEvaluacion(models.Model):
    """Ciclo de evaluación (ej: "Evaluación Anual 2026")."""
    TIPO_CHOICES = [
        ('90', 'Evaluación 90° (Jefe)'),
        ('180', 'Evaluación 180° (Jefe + Auto)'),
        ('360', 'Evaluación 360°'),
        ('OKR', 'Revisión OKR'),
        ('PRUEBA', 'Evaluación Periodo de Prueba'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('ABIERTO', 'Abierto'),
        ('EN_EVALUACION', 'En Evaluación'),
        ('CALIBRACION', 'En Calibración'),
        ('CERRADO', 'Cerrado'),
    ]

    nombre = models.CharField(max_length=200)
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default='180')
    plantilla = models.ForeignKey(
        PlantillaEvaluacion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='ciclos',
    )
    fecha_inicio = models.DateField(verbose_name='Fecha Inicio')
    fecha_fin = models.DateField(verbose_name='Fecha Fin')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='BORRADOR')
    descripcion = models.TextField(blank=True)
    aplica_areas = models.ManyToManyField(
        Area, blank=True, related_name='ciclos_evaluacion',
        verbose_name='Áreas participantes',
        help_text='Vacío = aplica a todas las áreas',
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ciclo de Evaluación'
        verbose_name_plural = 'Ciclos de Evaluación'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f'{self.nombre} ({self.get_tipo_display()})'

    @property
    def total_evaluaciones(self):
        return self.evaluaciones.count()

    @property
    def completadas(self):
        return self.evaluaciones.filter(estado='COMPLETADA').count()

    @property
    def porcentaje_avance(self):
        total = self.total_evaluaciones
        if total == 0:
            return 0
        return round((self.completadas / total) * 100)


class Evaluacion(models.Model):
    """Una evaluación individual: evaluador evalúa a evaluado."""
    RELACION_CHOICES = [
        ('JEFE', 'Jefe Directo'),
        ('AUTO', 'Autoevaluación'),
        ('PAR', 'Par / Colega'),
        ('SUBORDINADO', 'Subordinado'),
        ('CLIENTE', 'Cliente Interno'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADA', 'Completada'),
        ('CALIBRADA', 'Calibrada'),
    ]

    ciclo = models.ForeignKey(CicloEvaluacion, on_delete=models.CASCADE, related_name='evaluaciones')
    evaluado = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='evaluaciones_recibidas',
    )
    evaluador = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='evaluaciones_realizadas',
        null=True, blank=True,
    )
    evaluador_usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    relacion = models.CharField(max_length=12, choices=RELACION_CHOICES, default='JEFE')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='PENDIENTE')
    puntaje_total = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puntaje Total',
    )
    puntaje_calibrado = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puntaje Calibrado',
    )
    comentario_general = models.TextField(blank=True, verbose_name='Comentarios Generales')
    fortalezas = models.TextField(blank=True)
    areas_mejora = models.TextField(blank=True, verbose_name='Áreas de Mejora')
    fecha_completada = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Evaluación'
        verbose_name_plural = 'Evaluaciones'
        ordering = ['evaluado__apellidos_nombres']

    def __str__(self):
        return f'{self.evaluado.apellidos_nombres} ← {self.get_relacion_display()}'

    def calcular_puntaje(self):
        """Calcula puntaje ponderado a partir de respuestas."""
        respuestas = self.respuestas.select_related('competencia_plantilla')
        if not respuestas.exists():
            return None

        total_peso = Decimal('0')
        total_ponderado = Decimal('0')
        for r in respuestas:
            peso = r.competencia_plantilla.peso
            total_peso += peso
            total_ponderado += r.puntaje * peso

        if total_peso > 0:
            self.puntaje_total = total_ponderado / total_peso
            self.save(update_fields=['puntaje_total'])
        return self.puntaje_total

    @property
    def puntaje_final(self):
        return self.puntaje_calibrado or self.puntaje_total


class RespuestaEvaluacion(models.Model):
    """Respuesta individual por competencia dentro de una evaluación."""
    evaluacion = models.ForeignKey(Evaluacion, on_delete=models.CASCADE, related_name='respuestas')
    competencia_plantilla = models.ForeignKey(
        PlantillaCompetencia, on_delete=models.CASCADE,
        related_name='respuestas',
    )
    puntaje = models.DecimalField(
        max_digits=3, decimal_places=1,
        verbose_name='Puntaje',
    )
    comentario = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Respuesta'
        unique_together = ['evaluacion', 'competencia_plantilla']

    def __str__(self):
        return f'{self.competencia_plantilla.competencia.nombre}: {self.puntaje}'


# ══════════════════════════════════════════════════════════════
# RESULTADO CONSOLIDADO (9-BOX)
# ══════════════════════════════════════════════════════════════

class ResultadoConsolidado(models.Model):
    """Resultado consolidado de un evaluado en un ciclo (para 9-Box)."""
    DESEMPENO_CHOICES = [
        ('BAJO', 'Bajo'),
        ('MEDIO', 'Medio'),
        ('ALTO', 'Alto'),
    ]
    POTENCIAL_CHOICES = [
        ('BAJO', 'Bajo'),
        ('MEDIO', 'Medio'),
        ('ALTO', 'Alto'),
    ]

    ciclo = models.ForeignKey(CicloEvaluacion, on_delete=models.CASCADE, related_name='resultados')
    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='resultados_evaluacion')
    puntaje_promedio = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Puntaje Promedio',
    )
    puntaje_jefe = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje_auto = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    puntaje_pares = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    clasificacion_desempeno = models.CharField(
        max_length=5, choices=DESEMPENO_CHOICES, blank=True,
        verbose_name='Desempeño',
    )
    clasificacion_potencial = models.CharField(
        max_length=5, choices=POTENCIAL_CHOICES, blank=True,
        verbose_name='Potencial',
    )
    nine_box_position = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name='Posición 9-Box',
        help_text='1-9 (1=bajo-bajo, 9=alto-alto)',
    )
    observaciones = models.TextField(blank=True)
    consolidado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    fecha_consolidacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Resultado Consolidado'
        verbose_name_plural = 'Resultados Consolidados'
        unique_together = ['ciclo', 'personal']
        ordering = ['-puntaje_promedio']

    def __str__(self):
        return f'{self.personal.apellidos_nombres} — {self.ciclo.nombre}'

    def calcular_nine_box(self):
        """Calcula posición 9-Box basada en desempeño y potencial."""
        mapping = {
            ('BAJO', 'BAJO'): 1, ('BAJO', 'MEDIO'): 2, ('BAJO', 'ALTO'): 3,
            ('MEDIO', 'BAJO'): 4, ('MEDIO', 'MEDIO'): 5, ('MEDIO', 'ALTO'): 6,
            ('ALTO', 'BAJO'): 7, ('ALTO', 'MEDIO'): 8, ('ALTO', 'ALTO'): 9,
        }
        key = (self.clasificacion_desempeno, self.clasificacion_potencial)
        self.nine_box_position = mapping.get(key)
        self.save(update_fields=['nine_box_position'])
        return self.nine_box_position


# ══════════════════════════════════════════════════════════════
# PLAN DE DESARROLLO INDIVIDUAL (PDI)
# ══════════════════════════════════════════════════════════════

class PlanDesarrollo(models.Model):
    """Plan de desarrollo individual post-evaluación."""
    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('ACTIVO', 'Activo'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    ]

    personal = models.ForeignKey(Personal, on_delete=models.CASCADE, related_name='planes_desarrollo')
    ciclo = models.ForeignKey(
        CicloEvaluacion, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='planes',
    )
    titulo = models.CharField(max_length=200, verbose_name='Título')
    objetivo = models.TextField(verbose_name='Objetivo del Plan')
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default='BORRADOR')
    fecha_inicio = models.DateField(verbose_name='Fecha Inicio')
    fecha_fin = models.DateField(verbose_name='Fecha Fin')
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
        verbose_name='Responsable Seguimiento',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plan de Desarrollo Individual'
        verbose_name_plural = 'Planes de Desarrollo'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f'PDI: {self.personal.apellidos_nombres} — {self.titulo}'

    @property
    def porcentaje_avance(self):
        acciones = self.acciones.count()
        if acciones == 0:
            return 0
        completadas = self.acciones.filter(completada=True).count()
        return round((completadas / acciones) * 100)


class AccionDesarrollo(models.Model):
    """Acción concreta dentro de un PDI."""
    TIPO_CHOICES = [
        ('CAPACITACION', 'Capacitación'),
        ('PROYECTO', 'Proyecto/Asignación'),
        ('MENTORIA', 'Mentoría'),
        ('LECTURA', 'Lectura/Estudio'),
        ('PRACTICA', 'Práctica'),
        ('OTRO', 'Otro'),
    ]

    plan = models.ForeignKey(PlanDesarrollo, on_delete=models.CASCADE, related_name='acciones')
    descripcion = models.CharField(max_length=300)
    tipo = models.CharField(max_length=15, choices=TIPO_CHOICES, default='CAPACITACION')
    fecha_limite = models.DateField(verbose_name='Fecha Límite')
    completada = models.BooleanField(default=False)
    fecha_completada = models.DateField(null=True, blank=True)
    observaciones = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Acción de Desarrollo'
        verbose_name_plural = 'Acciones de Desarrollo'
        ordering = ['fecha_limite']

    def __str__(self):
        return self.descripcion


# ══════════════════════════════════════════════════════════════
# OKRs — OBJETIVOS Y RESULTADOS CLAVE
# Metodología: Objectives & Key Results (Intel/Google/OKR estándar)
# Referencia: Workday, Lattice, BambooHR
# ══════════════════════════════════════════════════════════════

class ObjetivoClave(models.Model):
    """
    Objetivo estratégico (O) de empresa, área o individual.
    Puede cascadear: empresa → área → individual.
    """
    NIVEL_CHOICES = [
        ('EMPRESA',    'Empresa'),
        ('AREA',       'Área'),
        ('INDIVIDUAL', 'Individual'),
    ]
    PERIODO_CHOICES = [
        ('TRIMESTRAL', 'Trimestral'),
        ('SEMESTRAL',  'Semestral'),
        ('ANUAL',      'Anual'),
    ]
    STATUS_CHOICES = [
        ('BORRADOR',   'Borrador'),
        ('ACTIVO',     'Activo'),
        ('EN_RIESGO',  'En Riesgo'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO',  'Cancelado'),
    ]

    # Descripción
    titulo = models.CharField(max_length=300, verbose_name='Objetivo')
    descripcion = models.TextField(blank=True, verbose_name='Descripción / Contexto')

    # Cascada jerárquica
    objetivo_padre = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='objetivos_hijo',
        verbose_name='Objetivo padre',
        help_text='Objetivo de nivel superior al que contribuye este objetivo.',
    )

    # Alcance
    nivel = models.CharField(max_length=12, choices=NIVEL_CHOICES, default='INDIVIDUAL')
    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE, null=True, blank=True,
        related_name='okrs', verbose_name='Responsable (individual)',
        help_text='Solo para objetivos individuales.',
    )
    area = models.ForeignKey(
        Area, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='okrs', verbose_name='Área',
        help_text='Para objetivos de área o empresa.',
    )

    # Período
    periodo = models.CharField(max_length=12, choices=PERIODO_CHOICES, default='TRIMESTRAL')
    anio = models.SmallIntegerField(verbose_name='Año', default=2026)
    trimestre = models.SmallIntegerField(
        null=True, blank=True, verbose_name='Trimestre (1-4)',
        help_text='Solo para períodos trimestrales.',
    )

    # Control
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='BORRADOR')
    peso = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('100.00'),
        verbose_name='Peso (%)',
        help_text='Importancia relativa dentro del período (suma debería ser 100%).',
    )

    # Vinculación con ciclo de evaluación (opcional)
    ciclo_evaluacion = models.ForeignKey(
        CicloEvaluacion, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='okrs',
        verbose_name='Ciclo de evaluación',
        help_text='Si aplica, vincula este OKR a un ciclo de evaluación.',
    )

    # Auditoría
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Objetivo Clave (OKR)'
        verbose_name_plural = 'Objetivos Clave (OKR)'
        ordering = ['-anio', 'trimestre', 'nivel', 'titulo']
        indexes = [
            models.Index(fields=['anio', 'trimestre', 'status']),
            models.Index(fields=['personal', 'status']),
        ]

    def __str__(self):
        return self.titulo

    @property
    def avance_promedio(self):
        """Promedio de avance de todos los KRs del objetivo."""
        krs = self.resultados_clave.all()
        if not krs:
            return 0
        avances = [kr.porcentaje_avance for kr in krs]
        return round(sum(avances) / len(avances))

    @property
    def periodo_display(self):
        if self.periodo == 'TRIMESTRAL' and self.trimestre:
            return f'Q{self.trimestre} {self.anio}'
        if self.periodo == 'SEMESTRAL':
            return f'S{1 if (self.trimestre or 1) <= 2 else 2} {self.anio}'
        return str(self.anio)

    @property
    def color_status(self):
        return {
            'BORRADOR':   'secondary',
            'ACTIVO':     'primary',
            'EN_RIESGO':  'warning',
            'COMPLETADO': 'success',
            'CANCELADO':  'muted',
        }.get(self.status, 'secondary')


class ResultadoClave(models.Model):
    """
    Key Result (KR): resultado medible que indica si el objetivo fue alcanzado.
    Cada objetivo tiene 2-5 KRs recomendados (estándar OKR).
    """
    UNIDAD_CHOICES = [
        ('PORCENTAJE', '%'),
        ('NUMERO',     'Número'),
        ('MONEDA',     'S/'),
        ('SI_NO',      'Sí / No'),
        ('PUNTOS',     'Puntos (0-10)'),
        ('DIAS',       'Días'),
        ('HORAS',      'Horas'),
        ('PERSONALIZADO', 'Personalizado'),
    ]

    objetivo = models.ForeignKey(
        ObjetivoClave, on_delete=models.CASCADE, related_name='resultados_clave',
    )
    descripcion = models.CharField(max_length=400, verbose_name='Resultado Clave')
    unidad = models.CharField(max_length=15, choices=UNIDAD_CHOICES, default='PORCENTAJE')
    unidad_personalizada = models.CharField(
        max_length=30, blank=True,
        help_text='Solo si unidad = Personalizado (ej: "clientes", "tickets").',
    )

    # Valores de medición
    valor_inicial  = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    valor_meta     = models.DecimalField(max_digits=12, decimal_places=2)
    valor_actual   = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    # Si es SI_NO, guardar como 0/1
    completado_binario = models.BooleanField(
        default=False,
        help_text='Para KRs de tipo Sí/No.',
    )

    fecha_limite  = models.DateField(null=True, blank=True, verbose_name='Fecha Límite')
    responsable   = models.ForeignKey(
        Personal, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='krs_responsable',
        verbose_name='Responsable',
    )
    orden         = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Resultado Clave (KR)'
        verbose_name_plural = 'Resultados Clave (KR)'
        ordering = ['orden', 'descripcion']

    def __str__(self):
        return f'{self.descripcion} ({self.objetivo.titulo})'

    @property
    def porcentaje_avance(self):
        """Calcula % de avance del KR respecto a meta."""
        if self.unidad == 'SI_NO':
            return 100 if self.completado_binario else 0
        rango = self.valor_meta - self.valor_inicial
        if rango == 0:
            return 100 if self.valor_actual >= self.valor_meta else 0
        avance = (self.valor_actual - self.valor_inicial) / rango * 100
        return min(100, max(0, int(avance)))

    @property
    def unidad_label(self):
        if self.unidad == 'PERSONALIZADO':
            return self.unidad_personalizada or '—'
        return dict(self.UNIDAD_CHOICES).get(self.unidad, self.unidad)

    @property
    def color_avance(self):
        p = self.porcentaje_avance
        if p >= 70:
            return 'success'
        if p >= 40:
            return 'warning'
        return 'danger'


class CheckInOKR(models.Model):
    """
    Actualización periódica del progreso de un Key Result.
    Permite tracking histórico y comentarios de bloqueos.
    """
    resultado_clave = models.ForeignKey(
        ResultadoClave, on_delete=models.CASCADE, related_name='checkins',
    )
    fecha        = models.DateField(verbose_name='Fecha de actualización')
    valor_nuevo  = models.DecimalField(
        max_digits=12, decimal_places=2,
        verbose_name='Valor actualizado',
    )
    comentario   = models.TextField(blank=True, verbose_name='Comentario / Bloqueos')
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Check-in OKR'
        verbose_name_plural = 'Check-ins OKR'
        ordering = ['-fecha']

    def __str__(self):
        return f'Check-in {self.fecha} — {self.resultado_clave.descripcion[:50]}'


# ══════════════════════════════════════════════════════════════
# EVALUACIONES 360° — MODELO DEDICADO
# Distinto al Evaluacion genérico: agrupa todos los participantes
# (auto / manager / peers / subordinados / clientes internos) en
# torno a un único evaluado para análisis comparativo.
# ══════════════════════════════════════════════════════════════

# Competencias gastronomía sugeridas (codigo, nombre) — usadas como
# fallback cuando no hay registros en Competencia y por el seed demo.
COMPETENCIAS_GASTRO_360 = [
    ('liderazgo',     'Liderazgo'),
    ('equipo',        'Trabajo en Equipo'),
    ('servicio',      'Calidad de Servicio'),
    ('conflictos',    'Resolución de Conflictos'),
    ('iniciativa',    'Iniciativa'),
    ('comunicacion',  'Comunicación'),
]


class Evaluacion360(models.Model):
    """
    Evaluación 360° dedicada: agrupa todos los puntos de vista sobre
    una persona (auto, manager, pares, subordinados, cliente interno)
    para producir una vista comparativa y un plan de desarrollo.
    """
    ESTADO_CHOICES = [
        ('BORRADOR',   'Borrador'),
        ('EN_CURSO',   'En curso'),
        ('CERRADA',    'Cerrada'),
    ]

    personal_evaluado = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='evaluaciones_360',
        verbose_name='Evaluado',
    )
    periodo = models.CharField(
        max_length=20,
        help_text='Ej: 2026-Q2, 2026-Anual',
    )
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='BORRADOR',
    )
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_cierre = models.DateField(null=True, blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Evaluación 360°'
        verbose_name_plural = 'Evaluaciones 360°'
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['estado', 'periodo']),
            models.Index(fields=['personal_evaluado', 'periodo']),
        ]

    def __str__(self):
        try:
            return f'360° {self.personal_evaluado.apellidos_nombres} — {self.periodo}'
        except Exception:
            return f'Evaluación 360° #{self.pk}'

    # ── Helpers de agregación ──────────────────────────────────

    @property
    def total_participantes(self):
        return self.participantes.count()

    @property
    def completadas(self):
        return self.participantes.filter(completada=True).count()

    @property
    def porcentaje_avance(self):
        total = self.total_participantes
        if not total:
            return 0
        return round((self.completadas / total) * 100)

    @property
    def puntaje_global(self):
        """Promedio simple de puntajes globales de participantes completados."""
        from django.db.models import Avg
        agg = self.participantes.filter(
            completada=True, puntaje_global__isnull=False,
        ).aggregate(p=Avg('puntaje_global'))
        return agg['p']

    def matriz_comparativa(self):
        """
        Construye matriz: { competencia_codigo: { tipo: {avg, label, count} } }
        Útil para tabla comparativa y radar chart.
        """
        tipos_orden = ['AUTOEVALUACION', 'MANAGER', 'PEER', 'SUBORDINADO', 'CLIENTE_INTERNO']
        matriz = {}
        respuestas = RespuestaCompetencia360.objects.filter(
            participante__evaluacion=self,
            participante__completada=True,
        ).select_related('participante')

        for resp in respuestas:
            cod = resp.competencia_codigo
            label = resp.competencia_label
            tipo = resp.participante.tipo
            if cod not in matriz:
                matriz[cod] = {'label': label, 'tipos': {}}
            data = matriz[cod]['tipos'].setdefault(tipo, {'sum': Decimal('0'), 'count': 0})
            data['sum'] += resp.puntaje
            data['count'] += 1

        # Promediar
        out = {}
        for cod, info in matriz.items():
            promedios = {}
            for tipo in tipos_orden:
                if tipo in info['tipos']:
                    d = info['tipos'][tipo]
                    if d['count']:
                        promedios[tipo] = round(d['sum'] / d['count'], 2)
                    else:
                        promedios[tipo] = None
                else:
                    promedios[tipo] = None
            out[cod] = {
                'label': info['label'],
                'promedios': promedios,
            }
        return out

    def gaps_auto_manager(self):
        """
        Detecta gaps autoevaluación vs manager por competencia.
        Retorna lista [{competencia, auto, manager, gap, severidad}].
        Severidad: 'critical' si |gap|>=2, 'warning' si |gap|>=1.5, else 'ok'.
        """
        matriz = self.matriz_comparativa()
        gaps = []
        for cod, info in matriz.items():
            auto = info['promedios'].get('AUTOEVALUACION')
            mgr = info['promedios'].get('MANAGER')
            if auto is None or mgr is None:
                continue
            gap = Decimal(str(auto)) - Decimal(str(mgr))
            severidad = 'ok'
            abs_gap = abs(gap)
            if abs_gap >= Decimal('2'):
                severidad = 'critical'
            elif abs_gap >= Decimal('1.5'):
                severidad = 'warning'
            gaps.append({
                'codigo': cod,
                'competencia': info['label'],
                'auto': auto,
                'manager': mgr,
                'gap': gap,
                'severidad': severidad,
            })
        # Ordenar por gap más grande primero
        gaps.sort(key=lambda x: abs(x['gap']), reverse=True)
        return gaps


class ParticipanteEvaluacion360(models.Model):
    """
    Cada perspectiva (auto / manager / peer / subordinado / cliente)
    es un participante distinto que llena su propio cuestionario.
    """
    TIPO_CHOICES = [
        ('AUTOEVALUACION',  'Autoevaluación'),
        ('MANAGER',         'Manager'),
        ('PEER',            'Par / Colega'),
        ('SUBORDINADO',     'Subordinado'),
        ('CLIENTE_INTERNO', 'Cliente interno'),
    ]

    evaluacion = models.ForeignKey(
        Evaluacion360, on_delete=models.CASCADE, related_name='participantes',
    )
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    personal_evaluador = models.ForeignKey(
        Personal, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='participaciones_360',
        verbose_name='Evaluador',
    )
    completada = models.BooleanField(default=False)
    puntaje_global = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text='Promedio 0-5',
    )
    comentario_general = models.TextField(blank=True)
    fortalezas = models.TextField(blank=True)
    areas_mejora = models.TextField(blank=True)
    fecha_completada = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Participante 360°'
        verbose_name_plural = 'Participantes 360°'
        ordering = ['tipo', 'creado_en']
        indexes = [
            models.Index(fields=['evaluacion', 'tipo']),
            models.Index(fields=['personal_evaluador', 'completada']),
        ]

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.evaluacion_id}'

    def calcular_puntaje_global(self, persist=True):
        """Promedia respuestas de competencias."""
        respuestas = self.respuestas.all()
        if not respuestas.exists():
            return None
        total = sum((r.puntaje for r in respuestas), Decimal('0'))
        promedio = total / Decimal(str(respuestas.count()))
        # Redondeo a 2 decimales
        promedio = promedio.quantize(Decimal('0.01'))
        if persist:
            self.puntaje_global = promedio
            self.save(update_fields=['puntaje_global'])
        return promedio


class RespuestaCompetencia360(models.Model):
    """
    Respuesta por competencia dentro de un participante 360°.
    Se almacena tanto el FK a Competencia (si existe) como
    código + nombre snapshot por si la lista cambia con el tiempo.
    """
    participante = models.ForeignKey(
        ParticipanteEvaluacion360, on_delete=models.CASCADE,
        related_name='respuestas',
    )
    competencia = models.ForeignKey(
        Competencia, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    competencia_codigo = models.SlugField(max_length=40)
    competencia_label = models.CharField(max_length=120)
    puntaje = models.DecimalField(
        max_digits=3, decimal_places=1,
        help_text='Escala 0-5',
    )
    comentario = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Respuesta 360°'
        verbose_name_plural = 'Respuestas 360°'
        ordering = ['competencia_codigo']
        unique_together = [('participante', 'competencia_codigo')]

    def __str__(self):
        return f'{self.competencia_label}: {self.puntaje}'
