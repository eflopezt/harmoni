"""
Módulo de Onboarding y Offboarding.
Gestiona procesos de incorporación y desvinculación de personal,
con plantillas configurables y checklist de pasos por responsable.
"""
from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from personal.models import Personal, Area
from personal.motivos_cese import MOTIVOS_OFFBOARDING


# ══════════════════════════════════════════════════════════════
# ONBOARDING — PLANTILLAS
# ══════════════════════════════════════════════════════════════

class PlantillaOnboarding(models.Model):
    """Plantilla reutilizable para procesos de onboarding."""
    GRUPO_CHOICES = [
        ('STAFF', 'STAFF'),
        ('RCO', 'RCO'),
        ('TODOS', 'Todos'),
    ]

    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    aplica_grupo = models.CharField(
        max_length=10, choices=GRUPO_CHOICES, default='TODOS',
        verbose_name="Aplica a Grupo",
        help_text="Grupo de tareo al que aplica esta plantilla"
    )
    aplica_areas = models.ManyToManyField(
        Area, blank=True, related_name='plantillas_onboarding',
        verbose_name="Aplica a Áreas",
        help_text="Dejar vacío para aplicar a todas las áreas"
    )
    activa = models.BooleanField(default=True, verbose_name="Activa")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Onboarding"
        verbose_name_plural = "Plantillas de Onboarding"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def total_pasos(self):
        return self.pasos.count()


class PasoPlantilla(models.Model):
    """Paso dentro de una plantilla de onboarding."""
    TIPO_CHOICES = [
        ('TAREA', 'Tarea'),
        ('DOCUMENTO', 'Documento'),
        ('CAPACITACION', 'Capacitación'),
        ('NOTIFICACION', 'Notificación'),
        ('APROBACION', 'Aprobación'),
    ]
    RESPONSABLE_CHOICES = [
        ('RRHH', 'RRHH'),
        ('JEFE', 'Jefe Directo'),
        ('TI', 'TI / Sistemas'),
        ('TRABAJADOR', 'Trabajador'),
    ]

    plantilla = models.ForeignKey(
        PlantillaOnboarding, on_delete=models.CASCADE,
        related_name='pasos', verbose_name="Plantilla"
    )
    orden = models.PositiveSmallIntegerField(default=1, verbose_name="Orden")
    titulo = models.CharField(max_length=300, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    tipo = models.CharField(
        max_length=15, choices=TIPO_CHOICES, default='TAREA',
        verbose_name="Tipo"
    )
    responsable_tipo = models.CharField(
        max_length=15, choices=RESPONSABLE_CHOICES, default='RRHH',
        verbose_name="Responsable"
    )
    dias_plazo = models.PositiveSmallIntegerField(
        default=1, verbose_name="Días de Plazo",
        help_text="Días calendario para completar este paso desde la fecha de ingreso"
    )
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Paso de Plantilla Onboarding"
        verbose_name_plural = "Pasos de Plantilla Onboarding"
        ordering = ['plantilla', 'orden']
        unique_together = ['plantilla', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo}"


# ══════════════════════════════════════════════════════════════
# ONBOARDING — PROCESOS
# ══════════════════════════════════════════════════════════════

class ProcesoOnboarding(models.Model):
    """Proceso de onboarding activo para un trabajador."""
    ESTADO_CHOICES = [
        ('EN_CURSO', 'En Curso'),
        ('COMPLETADO', 'Completado'),
        ('CANCELADO', 'Cancelado'),
    ]

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='procesos_onboarding', verbose_name="Trabajador"
    )
    plantilla = models.ForeignKey(
        PlantillaOnboarding, on_delete=models.PROTECT,
        related_name='procesos', verbose_name="Plantilla"
    )
    fecha_ingreso = models.DateField(verbose_name="Fecha de Ingreso")
    fecha_inicio = models.DateField(
        default=date.today, verbose_name="Fecha de Inicio del Proceso"
    )
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='EN_CURSO',
        verbose_name="Estado"
    )
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='onboardings_iniciados',
        verbose_name="Iniciado por"
    )
    notas = models.TextField(blank=True, verbose_name="Notas")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proceso de Onboarding"
        verbose_name_plural = "Procesos de Onboarding"
        ordering = ['-creado_en']

    def __str__(self):
        return f"Onboarding: {self.personal.apellidos_nombres}"

    @property
    def total_pasos(self):
        return self.pasos.count()

    @property
    def pasos_completados(self):
        return self.pasos.filter(estado='COMPLETADO').count()

    @property
    def porcentaje_avance(self):
        total = self.total_pasos
        if total == 0:
            return 0
        return round(self.pasos_completados * 100 / total)

    @property
    def dias_transcurridos(self):
        return (date.today() - self.fecha_inicio).days


class ChecklistTI(models.Model):
    """Provisioning TI mínimo (rec. 18 del análisis de flujo).

    Campos estructurados en vez de integraciones complejas: TI marca lo
    hecho y RRHH ve el avance desde el detalle del onboarding.
    """
    proceso = models.OneToOneField(
        ProcesoOnboarding, on_delete=models.CASCADE,
        related_name='checklist_ti', verbose_name='Proceso de Onboarding',
    )
    correo_creado = models.BooleanField(
        default=False, verbose_name='Correo corporativo creado')
    correo_corporativo = models.EmailField(
        blank=True, verbose_name='Correo corporativo')
    usuario_ad_creado = models.BooleanField(
        default=False, verbose_name='Usuario AD/SSO creado')
    usuario_ad = models.CharField(
        max_length=100, blank=True, verbose_name='Usuario AD/SSO')
    equipo_entregado = models.BooleanField(
        default=False, verbose_name='Equipo entregado')
    equipo_asignado = models.ForeignKey(
        'personal.ActivoAsignado', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklists_ti',
        verbose_name='Equipo asignado',
        help_text='Activo entregado al ingresar (laptop, celular, EPP...)',
    )
    accesos_sistemas = models.TextField(
        blank=True, verbose_name='Accesos a sistemas',
        help_text='Sistemas, carpetas o licencias habilitados')
    fotocheck_entregado = models.BooleanField(
        default=False, verbose_name='Fotocheck entregado')
    actualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklists_ti_actualizados',
    )
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Checklist TI'
        verbose_name_plural = 'Checklists TI'

    def __str__(self):
        return f'Checklist TI: {self.proceso.personal.apellidos_nombres}'

    @property
    def completado(self):
        return self.correo_creado and self.usuario_ad_creado and self.equipo_entregado

    @property
    def avance(self):
        checks = [self.correo_creado, self.usuario_ad_creado,
                  self.equipo_entregado, self.fotocheck_entregado]
        return round(sum(checks) * 100 / len(checks))


class PasoOnboarding(models.Model):
    """Paso concreto de un proceso de onboarding."""
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('EN_PROGRESO', 'En Progreso'),
        ('COMPLETADO', 'Completado'),
        ('OMITIDO', 'Omitido'),
    ]

    proceso = models.ForeignKey(
        ProcesoOnboarding, on_delete=models.CASCADE,
        related_name='pasos', verbose_name="Proceso"
    )
    paso_plantilla = models.ForeignKey(
        PasoPlantilla, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='instancias',
        verbose_name="Paso Plantilla"
    )
    orden = models.PositiveSmallIntegerField(default=1, verbose_name="Orden")
    titulo = models.CharField(max_length=300, verbose_name="Título")
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='PENDIENTE',
        verbose_name="Estado"
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pasos_onboarding_asignados',
        verbose_name="Responsable"
    )
    fecha_limite = models.DateField(
        null=True, blank=True, verbose_name="Fecha Límite"
    )
    fecha_completado = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha Completado"
    )
    completado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pasos_onboarding_completados',
        verbose_name="Completado por"
    )
    comentarios = models.TextField(blank=True, verbose_name="Comentarios")

    class Meta:
        verbose_name = "Paso de Onboarding"
        verbose_name_plural = "Pasos de Onboarding"
        ordering = ['proceso', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo} ({self.get_estado_display()})"

    @property
    def esta_vencido(self):
        if self.estado in ('COMPLETADO', 'OMITIDO'):
            return False
        if self.fecha_limite and date.today() > self.fecha_limite:
            return True
        return False


# ══════════════════════════════════════════════════════════════
# CHECKLIST GASTRONOMÍA — 30/60/90 días
# ══════════════════════════════════════════════════════════════

class ChecklistGastronomia(models.Model):
    """Checklist de onboarding específico para trabajadores nuevos en gastronomía.

    Complementa el sistema genérico de Plantillas con un checklist fijo
    orientado a documentos legales, certificaciones sanitarias obligatorias
    (BPM, HACCP, Manipulación de Alimentos, Carné Sanitario) y evaluaciones
    de desempeño a los 30/60/90 días.
    """
    personal = models.OneToOneField(
        Personal, on_delete=models.CASCADE,
        related_name='checklist_gastro', verbose_name="Trabajador"
    )
    fecha_ingreso = models.DateField(verbose_name="Fecha de Ingreso")

    # ── Documentos y firmas (semana 1) ─────────────────────────
    contrato_firmado = models.BooleanField(default=False, verbose_name="Contrato firmado")
    contrato_firmado_fecha = models.DateField(null=True, blank=True)

    examen_medico = models.BooleanField(default=False, verbose_name="Examen médico ocupacional")
    examen_medico_fecha = models.DateField(null=True, blank=True)

    uniforme_entregado = models.BooleanField(default=False, verbose_name="Uniforme entregado")
    uniforme_entregado_fecha = models.DateField(null=True, blank=True)

    induccion_general = models.BooleanField(default=False, verbose_name="Inducción general")
    induccion_general_fecha = models.DateField(null=True, blank=True)

    # ── Certificaciones sanitarias (mes 1) ─────────────────────
    bpm_certificado = models.BooleanField(default=False, verbose_name="Certificación BPM")
    bpm_certificado_fecha = models.DateField(null=True, blank=True)

    haccp_certificado = models.BooleanField(default=False, verbose_name="Certificación HACCP")
    haccp_certificado_fecha = models.DateField(null=True, blank=True)

    manipulacion_alimentos = models.BooleanField(default=False, verbose_name="Manipulación de alimentos")
    manipulacion_alimentos_fecha = models.DateField(null=True, blank=True)

    carne_sanitario = models.BooleanField(default=False, verbose_name="Carné sanitario")
    carne_sanitario_fecha = models.DateField(null=True, blank=True)

    # ── Evaluaciones 30 / 60 / 90 días ─────────────────────────
    evaluacion_30 = models.BooleanField(default=False, verbose_name="Evaluación 30 días")
    evaluacion_30_fecha = models.DateField(null=True, blank=True)
    evaluacion_30_calificacion = models.PositiveIntegerField(
        null=True, blank=True, help_text='Calificación 1-10'
    )
    evaluacion_30_notas = models.TextField(blank=True)

    evaluacion_60 = models.BooleanField(default=False, verbose_name="Evaluación 60 días")
    evaluacion_60_fecha = models.DateField(null=True, blank=True)
    evaluacion_60_calificacion = models.PositiveIntegerField(
        null=True, blank=True, help_text='Calificación 1-10'
    )
    evaluacion_60_notas = models.TextField(blank=True)

    evaluacion_90 = models.BooleanField(default=False, verbose_name="Evaluación 90 días")
    evaluacion_90_fecha = models.DateField(null=True, blank=True)
    evaluacion_90_calificacion = models.PositiveIntegerField(
        null=True, blank=True, help_text='Calificación 1-10'
    )
    evaluacion_90_notas = models.TextField(blank=True)

    # ── Estado general ─────────────────────────────────────────
    completado = models.BooleanField(default=False, verbose_name="Completado")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='checklists_gastro',
        verbose_name="Responsable"
    )

    # Lista de campos boolean que cuentan para el porcentaje
    _ITEMS_CHECKLIST = (
        'contrato_firmado', 'examen_medico', 'uniforme_entregado', 'induccion_general',
        'bpm_certificado', 'haccp_certificado', 'manipulacion_alimentos', 'carne_sanitario',
        'evaluacion_30', 'evaluacion_60', 'evaluacion_90',
    )

    class Meta:
        verbose_name = "Checklist de Onboarding Gastronomía"
        verbose_name_plural = "Checklists de Onboarding Gastronomía"
        ordering = ['-fecha_ingreso']

    def __str__(self):
        return f"Checklist {self.personal.apellidos_nombres}"

    @property
    def porcentaje_completado(self):
        items = [getattr(self, f) for f in self._ITEMS_CHECKLIST]
        if not items:
            return 0
        return int(sum(1 for i in items if i) / len(items) * 100)

    @property
    def items_completados(self):
        return sum(1 for f in self._ITEMS_CHECKLIST if getattr(self, f))

    @property
    def total_items(self):
        return len(self._ITEMS_CHECKLIST)

    @property
    def dias_desde_ingreso(self):
        return (timezone.localdate() - self.fecha_ingreso).days

    @property
    def alertas_vencidas(self):
        """Items que ya deberían estar listos pero no lo están."""
        alerts = []
        dias = self.dias_desde_ingreso
        if dias >= 7 and not self.contrato_firmado:
            alerts.append(('contrato_firmado', 'Contrato firmado (semana 1)'))
        if dias >= 14 and not self.examen_medico:
            alerts.append(('examen_medico', 'Examen médico (semana 2)'))
        if dias >= 30 and not (self.bpm_certificado and self.manipulacion_alimentos):
            alerts.append(('certs', 'Certificaciones BPM/Manipulación (mes 1)'))
        if dias >= 30 and not self.evaluacion_30:
            alerts.append(('eval_30', 'Evaluación 30 días vencida'))
        if dias >= 60 and not self.evaluacion_60:
            alerts.append(('eval_60', 'Evaluación 60 días vencida'))
        if dias >= 90 and not self.evaluacion_90:
            alerts.append(('eval_90', 'Evaluación 90 días vencida'))
        return alerts

    @property
    def en_riesgo(self):
        return len(self.alertas_vencidas) > 0

    @property
    def proximo_hito(self):
        """Devuelve string con el siguiente hito pendiente."""
        if not self.contrato_firmado:
            return "Firmar contrato"
        if not self.examen_medico:
            return "Examen médico"
        if not self.induccion_general:
            return "Inducción general"
        if not self.uniforme_entregado:
            return "Entregar uniforme"
        if not (self.bpm_certificado and self.manipulacion_alimentos):
            return "Certificaciones sanitarias"
        if not self.evaluacion_30:
            return "Evaluación 30 días"
        if not self.evaluacion_60:
            return "Evaluación 60 días"
        if not self.evaluacion_90:
            return "Evaluación 90 días"
        return "Completado"


# ══════════════════════════════════════════════════════════════
# OFFBOARDING — PLANTILLAS
# ══════════════════════════════════════════════════════════════

class PlantillaOffboarding(models.Model):
    """Plantilla reutilizable para procesos de offboarding."""
    nombre = models.CharField(max_length=200, unique=True, verbose_name="Nombre")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plantilla de Offboarding"
        verbose_name_plural = "Plantillas de Offboarding"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def total_pasos(self):
        return self.pasos.count()


class PasoPlantillaOff(models.Model):
    """Paso dentro de una plantilla de offboarding."""
    TIPO_CHOICES = PasoPlantilla.TIPO_CHOICES
    RESPONSABLE_CHOICES = PasoPlantilla.RESPONSABLE_CHOICES

    plantilla = models.ForeignKey(
        PlantillaOffboarding, on_delete=models.CASCADE,
        related_name='pasos', verbose_name="Plantilla"
    )
    orden = models.PositiveSmallIntegerField(default=1, verbose_name="Orden")
    titulo = models.CharField(max_length=300, verbose_name="Título")
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    tipo = models.CharField(
        max_length=15, choices=TIPO_CHOICES, default='TAREA',
        verbose_name="Tipo"
    )
    responsable_tipo = models.CharField(
        max_length=15, choices=RESPONSABLE_CHOICES, default='RRHH',
        verbose_name="Responsable"
    )
    dias_plazo = models.PositiveSmallIntegerField(
        default=1, verbose_name="Días de Plazo",
        help_text="Días calendario para completar este paso desde la fecha de cese"
    )
    obligatorio = models.BooleanField(default=True, verbose_name="Obligatorio")

    class Meta:
        verbose_name = "Paso de Plantilla Offboarding"
        verbose_name_plural = "Pasos de Plantilla Offboarding"
        ordering = ['plantilla', 'orden']
        unique_together = ['plantilla', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo}"


# ══════════════════════════════════════════════════════════════
# OFFBOARDING — PROCESOS
# ══════════════════════════════════════════════════════════════

class ProcesoOffboarding(models.Model):
    """Proceso de offboarding activo para un trabajador."""
    ESTADO_CHOICES = ProcesoOnboarding.ESTADO_CHOICES
    # Vista reducida del catálogo canónico — ver personal/motivos_cese.py
    MOTIVO_CHOICES = MOTIVOS_OFFBOARDING

    personal = models.ForeignKey(
        Personal, on_delete=models.CASCADE,
        related_name='procesos_offboarding', verbose_name="Trabajador"
    )
    plantilla = models.ForeignKey(
        PlantillaOffboarding, on_delete=models.PROTECT,
        related_name='procesos', verbose_name="Plantilla"
    )
    fecha_cese = models.DateField(verbose_name="Fecha de Cese")
    motivo_cese = models.CharField(
        max_length=15, choices=MOTIVO_CHOICES,
        verbose_name="Motivo de Cese"
    )
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='EN_CURSO',
        verbose_name="Estado"
    )
    iniciado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='offboardings_iniciados',
        verbose_name="Iniciado por"
    )
    notas = models.TextField(blank=True, verbose_name="Notas")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Proceso de Offboarding"
        verbose_name_plural = "Procesos de Offboarding"
        ordering = ['-creado_en']

    def __str__(self):
        return f"Offboarding: {self.personal.apellidos_nombres}"

    @property
    def total_pasos(self):
        return self.pasos.count()

    @property
    def pasos_completados(self):
        return self.pasos.filter(estado='COMPLETADO').count()

    @property
    def porcentaje_avance(self):
        total = self.total_pasos
        if total == 0:
            return 0
        return round(self.pasos_completados * 100 / total)

    @property
    def dias_transcurridos(self):
        return (date.today() - self.creado_en.date()).days


class PasoOffboarding(models.Model):
    """Paso concreto de un proceso de offboarding."""
    ESTADO_CHOICES = PasoOnboarding.ESTADO_CHOICES

    proceso = models.ForeignKey(
        ProcesoOffboarding, on_delete=models.CASCADE,
        related_name='pasos', verbose_name="Proceso"
    )
    paso_plantilla = models.ForeignKey(
        PasoPlantillaOff, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='instancias',
        verbose_name="Paso Plantilla"
    )
    orden = models.PositiveSmallIntegerField(default=1, verbose_name="Orden")
    titulo = models.CharField(max_length=300, verbose_name="Título")
    estado = models.CharField(
        max_length=12, choices=ESTADO_CHOICES, default='PENDIENTE',
        verbose_name="Estado"
    )
    responsable = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pasos_offboarding_asignados',
        verbose_name="Responsable"
    )
    fecha_limite = models.DateField(
        null=True, blank=True, verbose_name="Fecha Límite"
    )
    fecha_completado = models.DateTimeField(
        null=True, blank=True, verbose_name="Fecha Completado"
    )
    completado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='pasos_offboarding_completados',
        verbose_name="Completado por"
    )
    comentarios = models.TextField(blank=True, verbose_name="Comentarios")

    class Meta:
        verbose_name = "Paso de Offboarding"
        verbose_name_plural = "Pasos de Offboarding"
        ordering = ['proceso', 'orden']

    def __str__(self):
        return f"{self.orden}. {self.titulo} ({self.get_estado_display()})"

    @property
    def esta_vencido(self):
        if self.estado in ('COMPLETADO', 'OMITIDO'):
            return False
        if self.fecha_limite and date.today() > self.fecha_limite:
            return True
        return False
