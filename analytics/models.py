"""
Analytics & People Intelligence — Modelos.

Snapshots periódicos de KPIs para dashboards ejecutivos y tendencias históricas.
Los datos se calculan desde los módulos existentes y se almacenan como snapshots
para consulta rápida sin queries pesados en tiempo real.
"""
from django.db import models
from django.contrib.auth.models import User


class KPISnapshot(models.Model):
    """
    Snapshot mensual de KPIs de RRHH.
    Se genera al cierre de cada mes o bajo demanda.
    """
    periodo = models.DateField(
        verbose_name="Periodo",
        help_text="Primer día del mes del snapshot")

    # ── Headcount ──
    total_empleados = models.PositiveIntegerField(default=0)
    empleados_staff = models.PositiveIntegerField(default=0)
    empleados_rco = models.PositiveIntegerField(default=0)
    altas_mes = models.PositiveIntegerField(default=0, verbose_name="Ingresos del mes")
    bajas_mes = models.PositiveIntegerField(default=0, verbose_name="Ceses del mes")

    # ── Rotación ──
    tasa_rotacion = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Tasa de Rotación %")
    tasa_rotacion_voluntaria = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Rotación Voluntaria %")

    # ── Asistencia ──
    tasa_asistencia = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Tasa de Asistencia %")
    total_he_mes = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Total HE del mes")
    promedio_he_persona = models.DecimalField(
        max_digits=7, decimal_places=2, default=0,
        verbose_name="Promedio HE/persona")

    # ── Vacaciones ──
    dias_vacaciones_pendientes = models.PositiveIntegerField(
        default=0, verbose_name="Días vacaciones pendientes (total)")
    promedio_dias_pendientes = models.DecimalField(
        max_digits=5, decimal_places=1, default=0,
        verbose_name="Promedio días pendientes/persona")

    # ── Capacitación ──
    horas_capacitacion_mes = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        verbose_name="Horas capacitación del mes")
    empleados_capacitados = models.PositiveIntegerField(
        default=0, verbose_name="Empleados capacitados")
    cobertura_capacitacion = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Cobertura capacitación %")

    # ── Costo ──
    costo_nomina_bruto = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        verbose_name="Costo nómina bruto S/")
    costo_promedio_empleado = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        verbose_name="Costo promedio/empleado S/")

    # ── Metadata ──
    generado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Snapshot KPI"
        verbose_name_plural = "Snapshots KPIs"
        ordering = ['-periodo']
        unique_together = ['periodo']

    def __str__(self):
        return f"KPI {self.periodo.strftime('%Y-%m')}"


class AlertaRRHH(models.Model):
    """
    Alertas automáticas generadas por el sistema de analytics.
    Ej: rotación alta en un área, vencimiento masivo de documentos, etc.
    """
    SEVERIDAD_CHOICES = [
        ('INFO', 'Informativa'),
        ('WARN', 'Advertencia'),
        ('CRITICAL', 'Crítica'),
    ]
    ESTADO_CHOICES = [
        ('ACTIVA', 'Activa'),
        ('RESUELTA', 'Resuelta'),
        ('DESCARTADA', 'Descartada'),
    ]
    CATEGORIA_CHOICES = [
        ('ROTACION', 'Rotación'),
        ('ASISTENCIA', 'Asistencia'),
        ('DOCUMENTOS', 'Documentos vencidos'),
        ('VACACIONES', 'Vacaciones pendientes'),
        ('CAPACITACION', 'Capacitación'),
        ('DISCIPLINARIA', 'Disciplinaria'),
        ('CONTRATOS', 'Contratos y período de prueba'),
        ('OTRO', 'Otro'),
    ]

    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    categoria = models.CharField(max_length=20, choices=CATEGORIA_CHOICES)
    severidad = models.CharField(max_length=10, choices=SEVERIDAD_CHOICES, default='INFO')
    estado = models.CharField(max_length=15, choices=ESTADO_CHOICES, default='ACTIVA')

    area = models.ForeignKey(
        'personal.Area', on_delete=models.CASCADE,
        null=True, blank=True, verbose_name="Área afectada")
    valor_actual = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Valor actual")
    valor_umbral = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Umbral de alerta")

    resuelta_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='alertas_resueltas')
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    notas_resolucion = models.TextField(blank=True)

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Alerta RRHH"
        verbose_name_plural = "Alertas RRHH"
        ordering = ['-creado_en']

    def __str__(self):
        return f"[{self.severidad}] {self.titulo}"


class DashboardWidget(models.Model):
    """
    Gráfico personalizado guardado por el usuario en su dashboard de IA.
    Creado cuando el usuario le pide a Harmoni AI "fijar en el dashboard".
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='dashboard_widgets',
        verbose_name="Usuario")
    titulo = models.CharField(max_length=200, verbose_name="Título")
    chart_type = models.CharField(
        max_length=50, verbose_name="Tipo de gráfico",
        help_text="bar, line, doughnut, etc.")
    data_source = models.CharField(
        max_length=100, verbose_name="Fuente de datos",
        help_text="areas, headcount, genero, etc.")
    config_json = models.JSONField(
        default=dict, verbose_name="Configuración del gráfico",
        help_text="Spec completo del gráfico (labels, values, colors, etc.)")
    posicion = models.PositiveIntegerField(default=0, verbose_name="Posición")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Widget Dashboard"
        verbose_name_plural = "Widgets Dashboard"
        ordering = ['posicion', '-creado_en']

    def __str__(self):
        return f"{self.titulo} ({self.user.username})"
