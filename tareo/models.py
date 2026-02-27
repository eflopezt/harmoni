"""
Módulo Tareo — Modelos de datos.

Módulo independiente para gestión de marcación real de asistencia,
cálculo de horas extra y banco de horas compensatorias.

Puede funcionar sin el módulo Roster pero está diseñado para cruzarse
con él en Fase 2 (comparativo real vs proyectado).
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
import datetime


# ─────────────────────────────────────────────────────────────
# SECCIÓN 1 ▸ CONFIGURACIÓN DE REGÍMENES Y HORARIOS
# ─────────────────────────────────────────────────────────────

class RegimenTurno(models.Model):
    """
    Régimen de trabajo configurable.
    Ejemplos: 21×7 (foráneo), 5×2 semana normal, 6×1,
    turno rotativo, régimen semanal sin descanso fijo, etc.

    La jornada máxima promedio se calcula automáticamente
    según la normativa: 48 h/semana × ciclo_semanas.
    """

    JORNADA_TIPO = [
        ('ACUMULATIVA', 'Jornada Acumulativa / Atípica (Art. 9 DS 007-2002)'),
        ('SEMANAL', 'Jornada Semanal Fija (máx. 48 h/semana)'),
        ('ROTATIVA', 'Turno Rotativo (descanso no fijo)'),
        ('NOCTURNA', 'Turno Nocturno (+35% recargo mínimo legal)'),
        ('ESPECIAL', 'Régimen Especial (configuración manual)'),
    ]

    nombre = models.CharField(max_length=60, unique=True,
                               verbose_name="Nombre del Régimen",
                               help_text="Ej: '21x7 Foráneo', '5x2 Local', 'Turno Noche'")
    codigo = models.CharField(max_length=10, unique=True,
                               verbose_name="Código",
                               help_text="Ej: 21X7, 5X2, TN")
    jornada_tipo = models.CharField(max_length=15, choices=JORNADA_TIPO,
                                    default='SEMANAL',
                                    verbose_name="Tipo de Jornada")

    # Ciclo de trabajo/descanso
    dias_trabajo_ciclo = models.PositiveSmallIntegerField(
        verbose_name="Días de Trabajo por Ciclo",
        help_text="Ej: 21 para régimen 21×7")
    dias_descanso_ciclo = models.PositiveSmallIntegerField(
        verbose_name="Días de Descanso por Ciclo",
        help_text="Ej: 7 para régimen 21×7")

    # Almuerzo
    minutos_almuerzo = models.PositiveSmallIntegerField(
        default=60,
        verbose_name="Minutos de Almuerzo",
        help_text="Descontados del tiempo bruto para calcular horas efectivas")

    # Recargo nocturno (Ley: turno nocturno si la mayor parte es entre 22:00–06:00)
    es_nocturno = models.BooleanField(default=False,
                                      verbose_name="¿Es Turno Nocturno?",
                                      help_text="Activa recargo mínimo del 35% sobre RMV")
    recargo_nocturno_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('35.00'),
        verbose_name="% Recargo Nocturno",
        help_text="Porcentaje mínimo legal 35%; puede ser mayor por negociación")

    descripcion = models.TextField(blank=True, verbose_name="Descripción / Notas")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Régimen de Turno"
        verbose_name_plural = "Regímenes de Turno"
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"

    @property
    def ciclo_total_dias(self):
        return self.dias_trabajo_ciclo + self.dias_descanso_ciclo

    @property
    def semanas_por_ciclo(self):
        """Número de semanas completas que cubre el ciclo."""
        return self.ciclo_total_dias / 7

    @property
    def horas_max_ciclo(self):
        """
        Máximo de horas ordinarias permitidas por ciclo
        bajo la normativa de 48 h/semana promedio.
        21x7 → 28 días / 7 = 4 semanas × 48 h = 192 h
        """
        return Decimal('48') * Decimal(str(self.semanas_por_ciclo))

    def clean(self):
        if self.dias_trabajo_ciclo < 1:
            raise ValidationError("Los días de trabajo por ciclo deben ser al menos 1.")
        if self.dias_descanso_ciclo < 0:
            raise ValidationError("Los días de descanso no pueden ser negativos.")


class TipoHorario(models.Model):
    """
    Tipo de horario de un turno específico.
    Se conecta con un régimen y define la hora de entrada/salida
    según el tipo de día (laboral, sábado, domingo, rotativo, noche, etc.).

    Un RegimenTurno puede tener múltiples TipoHorario para cubrir
    días distintos (L-V, Sáb, Dom) o rotación de turnos.
    """

    TIPO_DIA = [
        ('LUNES_VIERNES', 'Lunes a Viernes'),
        ('SABADO', 'Sábado'),
        ('DOMINGO', 'Domingo'),
        ('LUNES_SABADO', 'Lunes a Sábado'),
        ('TODOS', 'Todos los días del ciclo'),
        ('TURNO_A', 'Turno A (rotativo)'),
        ('TURNO_B', 'Turno B (rotativo)'),
        ('TURNO_C', 'Turno C (rotativo)'),
        ('ESPECIAL', 'Especial / Personalizado'),
    ]

    regimen = models.ForeignKey(
        RegimenTurno,
        on_delete=models.CASCADE,
        related_name='horarios',
        verbose_name="Régimen de Turno")

    nombre = models.CharField(max_length=60, verbose_name="Nombre del Horario",
                               help_text="Ej: 'Foráneo L-S', 'Local Domingo'")
    tipo_dia = models.CharField(max_length=20, choices=TIPO_DIA,
                                 verbose_name="Tipo de Día")

    hora_entrada = models.TimeField(verbose_name="Hora de Entrada")
    hora_salida = models.TimeField(verbose_name="Hora de Salida")

    # Cruce medianoche (turno nocturno que termina al día siguiente)
    salida_dia_siguiente = models.BooleanField(
        default=False,
        verbose_name="¿Salida al día siguiente?",
        help_text="Activar para turnos nocturnos que cruzan medianoche")

    activo = models.BooleanField(default=True, verbose_name="Activo")

    class Meta:
        verbose_name = "Tipo de Horario"
        verbose_name_plural = "Tipos de Horario"
        ordering = ['regimen', 'tipo_dia']
        unique_together = ['regimen', 'tipo_dia']

    def __str__(self):
        return (f"{self.regimen.codigo} | {self.get_tipo_dia_display()} "
                f"{self.hora_entrada}–{self.hora_salida}")

    @property
    def horas_brutas(self):
        """Horas brutas entre entrada y salida (considerando cruce de medianoche)."""
        entrada = datetime.datetime.combine(datetime.date.today(), self.hora_entrada)
        if self.salida_dia_siguiente:
            salida = datetime.datetime.combine(
                datetime.date.today() + datetime.timedelta(days=1), self.hora_salida)
        else:
            salida = datetime.datetime.combine(datetime.date.today(), self.hora_salida)
        delta = salida - entrada
        return Decimal(str(round(delta.total_seconds() / 3600, 4)))

    @property
    def horas_efectivas(self):
        """Horas efectivas = brutas − almuerzo."""
        almuerzo_h = Decimal(str(self.regimen.minutos_almuerzo / 60))
        return max(Decimal('0'), self.horas_brutas - almuerzo_h)


class FeriadoCalendario(models.Model):
    """
    Calendario de feriados oficiales.
    Cargado desde la hoja Parametros del Excel, luego mantenido en BD.
    """

    TIPO_FERIADO = [
        ('NO_RECUPERABLE', 'Feriado No Recuperable (remunerado)'),
        ('RECUPERABLE', 'Feriado Recuperable'),
        ('PUENTE', 'Puente / Decreto'),
    ]

    fecha = models.DateField(unique=True, verbose_name="Fecha del Feriado")
    nombre = models.CharField(max_length=150, verbose_name="Nombre del Feriado")
    tipo = models.CharField(max_length=20, choices=TIPO_FERIADO,
                             default='NO_RECUPERABLE', verbose_name="Tipo")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Feriado"
        verbose_name_plural = "Feriados"
        ordering = ['fecha']

    def __str__(self):
        return f"{self.fecha} — {self.nombre}"


class HomologacionCodigo(models.Model):
    """
    Tabla de equivalencias entre códigos del sistema de asistencia
    (lo que pega en la hoja Reloj) y los códigos internos del Tareo.

    Configurable — no hard-coded en Python —
    para admitir nuevos sistemas de asistencia o cambios de nomenclatura.
    """

    TIPO_EVENTO = [
        ('ASISTENCIA', 'Asistencia efectiva'),
        ('AUSENCIA', 'Ausencia no justificada (Falta)'),
        ('PERMISO', 'Permiso / Licencia'),
        ('DESCANSO', 'Descanso del ciclo / DL'),
        ('VACACIONES', 'Vacaciones'),
        ('SUSPENSION', 'Suspensión disciplinaria'),
        ('FERIADO', 'Feriado'),
        ('FERIADO_LABORADO', 'Feriado laborado'),
        ('TELETRABAJO', 'Trabajo remoto'),
        ('COMPENSACION', 'Compensación de horas'),
        ('DESCANSO_MEDICO', 'Descanso médico'),
        ('OTRO', 'Otro'),
    ]

    SIGNO = [
        ('+', 'Suma (cuenta como día trabajado / hábil)'),
        ('-', 'Resta (descuenta remuneración o no cuenta)'),
        ('N', 'Neutral (no suma ni resta)'),
    ]

    codigo_origen = models.CharField(
        max_length=20, unique=True,
        verbose_name="Código Origen (sistema asistencia)",
        help_text="Ej: 'B', 'V', 'SS', 'DM', '>0' para cualquier número positivo")
    codigo_tareo = models.CharField(
        max_length=20,
        verbose_name="Código Tareo (interno)",
        help_text="Ej: 'DL', 'VAC', 'A', 'F', 'DM'")
    codigo_roster = models.CharField(
        max_length=20, blank=True,
        verbose_name="Código Roster (para cruce Fase 2)",
        help_text="Vacío si no aplica cruce con roster")

    descripcion = models.CharField(max_length=200, verbose_name="Descripción")
    tipo_evento = models.CharField(max_length=20, choices=TIPO_EVENTO,
                                    verbose_name="Tipo de Evento")
    signo = models.CharField(max_length=1, choices=SIGNO, default='+',
                               verbose_name="Signo (impacto remunerativo)")
    cuenta_asistencia = models.BooleanField(
        default=True,
        verbose_name="¿Cuenta como asistencia?")
    genera_he = models.BooleanField(
        default=False,
        verbose_name="¿Puede generar HE?",
        help_text="True para asistencias donde el exceso de horas sea HE")
    es_numerico = models.BooleanField(
        default=False,
        verbose_name="¿El valor origen es numérico (horas)?")
    prioridad = models.PositiveSmallIntegerField(
        default=10,
        verbose_name="Prioridad",
        help_text="1=Papeleta > 5=Feriado > 10=Reloj > 99=Falta por defecto")

    activo = models.BooleanField(default=True, verbose_name="Activo")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Homologación de Código"
        verbose_name_plural = "Homologaciones de Código"
        ordering = ['prioridad', 'codigo_origen']

    def __str__(self):
        return f"{self.codigo_origen} → {self.codigo_tareo} | {self.descripcion}"


# ─────────────────────────────────────────────────────────────
# SECCIÓN 2 ▸ IMPORTACIONES
# ─────────────────────────────────────────────────────────────

class TareoImportacion(models.Model):
    """
    Sesión de importación de datos al módulo Tareo.

    Soporta cuatro fuentes:
      RELOJ      → archivo del sistema de asistencia biométrica (hoja Reloj)
      PAPELETAS  → justificaciones/permisos (hoja Papeletas)
      SUNAT      → reporte PDT / PLAME para cruce de trabajadores
      S10        → reporte de trabajadores desde S10 (nómina)
    """

    TIPO_FUENTE = [
        ('RELOJ', 'Sistema de Asistencia / Reloj Biométrico'),
        ('PAPELETAS', 'Papeletas de Permisos y Ausencias'),
        ('SUNAT', 'Reporte SUNAT / PLAME'),
        ('S10', 'Reporte S10 (Nómina)'),
    ]

    ESTADO = [
        ('PENDIENTE', 'Pendiente de Procesamiento'),
        ('PROCESANDO', 'En Proceso'),
        ('COMPLETADO', 'Completado sin Errores'),
        ('COMPLETADO_CON_ERRORES', 'Completado con Errores'),
        ('FALLIDO', 'Fallido'),
    ]

    tipo = models.CharField(max_length=20, choices=TIPO_FUENTE,
                             verbose_name="Tipo de Fuente")
    periodo_inicio = models.DateField(verbose_name="Inicio del Período de Tareo")
    periodo_fin = models.DateField(verbose_name="Fin del Período de Tareo")

    archivo_nombre = models.CharField(max_length=255, blank=True,
                                       verbose_name="Nombre del Archivo Original")
    archivo = models.FileField(
        upload_to='tareo/importaciones/%Y/%m/',
        blank=True, null=True,
        verbose_name="Archivo Cargado")

    estado = models.CharField(max_length=25, choices=ESTADO,
                               default='PENDIENTE', verbose_name="Estado")

    total_registros = models.PositiveIntegerField(default=0,
                                                   verbose_name="Total de Registros")
    registros_ok = models.PositiveIntegerField(default=0,
                                                verbose_name="Registros OK")
    registros_error = models.PositiveIntegerField(default=0,
                                                   verbose_name="Registros con Error")
    registros_sin_match = models.PositiveIntegerField(
        default=0,
        verbose_name="Sin Match con Personal (DNI no en BD)")

    errores = models.JSONField(
        default=list,
        verbose_name="Errores",
        help_text="Lista de {'fila': N, 'dni': '...', 'mensaje': '...'}")
    advertencias = models.JSONField(default=list, verbose_name="Advertencias")
    metadata = models.JSONField(
        default=dict,
        verbose_name="Metadatos",
        help_text="Hoja origen, ciclo detectado, sistema, etc.")

    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='tareo_importaciones',
        verbose_name="Importado por")

    creado_en = models.DateTimeField(auto_now_add=True)
    procesado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Importación de Tareo"
        verbose_name_plural = "Importaciones de Tareo"
        ordering = ['-creado_en']

    def __str__(self):
        return (f"[{self.get_tipo_display()}] "
                f"{self.periodo_inicio} → {self.periodo_fin} | "
                f"{self.get_estado_display()}")

    @property
    def periodo_label(self):
        return (f"{self.periodo_inicio.strftime('%d/%m/%Y')} – "
                f"{self.periodo_fin.strftime('%d/%m/%Y')}")


# ─────────────────────────────────────────────────────────────
# SECCIÓN 3 ▸ REGISTROS DIARIOS DEL TAREO
# ─────────────────────────────────────────────────────────────

class RegistroTareo(models.Model):
    """
    Registro diario de asistencia y horas para una persona en una fecha.

    Cada fila del Reloj procesado genera un RegistroTareo.
    Las Papeletas pueden sobrescribir el codigo_dia.
    STAFF → horas extras van al BancoHoras (compensatorio).
    RCO   → horas extras se pagan en nómina (S10).
    """

    GRUPO = [
        ('STAFF', 'CSRT STAFF (compensatorio — sin pago directo de HE)'),
        ('RCO', 'CSRT RCO (pago de HE en nómina S10)'),
        ('OTRO', 'Otro / Por definir'),
    ]

    CONDICION = [
        ('LOCAL', 'Local (jornada fija en sede)'),
        ('FORANEO', 'Foráneo (régimen acumulativo 21×7)'),
        ('LIMA', 'Lima (hereda horario Local)'),
    ]

    FUENTE_CODIGO = [
        ('RELOJ', 'Sistema de Asistencia'),
        ('PAPELETA', 'Papeleta de Permiso/Ausencia'),
        ('FERIADO', 'Feriado del Calendario'),
        ('FALTA_AUTO', 'Falta Automática (sin marca ni papeleta)'),
        ('MANUAL', 'Corrección Manual'),
    ]

    importacion = models.ForeignKey(
        TareoImportacion,
        on_delete=models.CASCADE,
        related_name='registros',
        verbose_name="Importación Origen")

    # Persona — FK opcional (puede haber DNI sin match en BD)
    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registros_tareo',
        verbose_name="Personal (BD)")
    dni = models.CharField(max_length=20, verbose_name="DNI/Doc (del archivo)")
    nombre_archivo = models.CharField(
        max_length=250, blank=True,
        verbose_name="Nombre (del archivo)")

    grupo = models.CharField(max_length=10, choices=GRUPO,
                              verbose_name="Grupo")
    condicion = models.CharField(max_length=10, choices=CONDICION,
                                  blank=True, verbose_name="Condición")
    regimen = models.ForeignKey(
        RegimenTurno,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registros_tareo',
        verbose_name="Régimen Aplicado")

    fecha = models.DateField(verbose_name="Fecha")
    dia_semana = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name="Día Semana (0=Lun, 6=Dom)")
    es_feriado = models.BooleanField(default=False, verbose_name="¿Es Feriado?")

    # Marcación bruta del reloj
    valor_reloj_raw = models.CharField(
        max_length=20, blank=True,
        verbose_name="Valor Crudo del Reloj",
        help_text="Sin procesar: número de horas, 'B', 'V', 'SS', en blanco, etc.")
    hora_entrada_real = models.TimeField(null=True, blank=True,
                                          verbose_name="Hora Entrada Real")
    hora_salida_real = models.TimeField(null=True, blank=True,
                                         verbose_name="Hora Salida Real")
    horas_marcadas = models.DecimalField(
        max_digits=5, decimal_places=2,
        null=True, blank=True,
        verbose_name="Horas Marcadas (brutas del reloj)")

    # Código procesado final
    codigo_dia = models.CharField(
        max_length=20, blank=True,
        verbose_name="Código Día (procesado)",
        help_text="Ej: A, NOR, DL, VAC, F, DM, FL, CHE")
    fuente_codigo = models.CharField(
        max_length=15, choices=FUENTE_CODIGO,
        default='RELOJ',
        verbose_name="Fuente del Código")

    # Horas calculadas
    horas_efectivas = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Horas Efectivas",
        help_text="Horas marcadas − almuerzo")
    horas_normales = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        verbose_name="Horas Normales (dentro de jornada)")
    he_25 = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="HE 25% (1ra y 2da hora extra)")
    he_35 = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="HE 35% (3ra hora extra en adelante)")
    he_100 = models.DecimalField(
        max_digits=5, decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name="HE 100% (Feriado Laborado)")

    he_al_banco = models.BooleanField(
        default=False,
        verbose_name="¿HE van al Banco?",
        help_text="True = STAFF (compensatorio); False = RCO (pago nómina)")

    papeleta_ref = models.CharField(
        max_length=100, blank=True,
        verbose_name="Referencia Papeleta Override")

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Registro de Tareo"
        verbose_name_plural = "Registros de Tareo"
        ordering = ['fecha', 'dni']
        unique_together = ['importacion', 'dni', 'fecha']
        indexes = [
            models.Index(fields=['dni', 'fecha']),
            models.Index(fields=['importacion', 'grupo']),
            models.Index(fields=['personal', 'fecha']),
            models.Index(fields=['fecha', 'grupo']),
        ]

    def __str__(self):
        return f"{self.dni} | {self.fecha} | {self.codigo_dia}"

    @property
    def total_he(self):
        return self.he_25 + self.he_35 + self.he_100


class RegistroPapeleta(models.Model):
    """
    Papeleta de permiso o justificación importada desde el sistema.
    Generada al importar la hoja Papeletas.
    Actúa como override sobre RegistroTareo en el rango de fechas indicado.
    """

    TIPO_PERMISO_CHOICES = [
        ('COMPENSACION_HE', 'Compensación por Horario Extendido (CHE)'),
        ('BAJADAS', 'Bajadas / Día Libre (DL)'),
        ('BAJADAS_ACUMULADAS', 'Bajadas Acumuladas (DLA)'),
        ('VACACIONES', 'Vacaciones (VAC)'),
        ('DESCANSO_MEDICO', 'Descanso Médico (DM)'),
        ('LICENCIA_CON_GOCE', 'Licencia con Goce (LCG)'),
        ('LICENCIA_SIN_GOCE', 'Licencia sin Goce (LSG)'),
        ('LICENCIA_FALLECIMIENTO', 'Licencia por Fallecimiento (LF)'),
        ('LICENCIA_PATERNIDAD', 'Licencia por Paternidad (LP)'),
        ('COMISION_TRABAJO', 'Comisión de Trabajo (CT)'),
        ('COMPENSACION_FERIADO', 'Compensación por Feriado (CPF)'),
        ('COMP_DIA_TRABAJO', 'Compensación de Día por Trabajo (CDT)'),
        ('SUSPENSION', 'Suspensión Disciplinaria'),
        ('OTRO', 'Otro'),
    ]

    importacion = models.ForeignKey(
        TareoImportacion,
        on_delete=models.CASCADE,
        related_name='papeletas',
        verbose_name="Importación Origen")

    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='papeletas_tareo',
        verbose_name="Personal (BD)")
    dni = models.CharField(max_length=20, verbose_name="DNI/Doc")
    nombre_archivo = models.CharField(max_length=250, blank=True,
                                       verbose_name="Nombre (del archivo)")

    tipo_permiso = models.CharField(max_length=30, choices=TIPO_PERMISO_CHOICES,
                                     verbose_name="Tipo de Permiso")
    tipo_permiso_raw = models.CharField(
        max_length=100, blank=True,
        verbose_name="Tipo Permiso Original (texto del archivo)")
    iniciales = models.CharField(max_length=10, blank=True,
                                  verbose_name="Iniciales del Código")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    detalle = models.TextField(blank=True, verbose_name="Detalle / Motivo")
    dias_habiles = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Hábiles Cubiertos")

    area_trabajo = models.CharField(max_length=150, blank=True,
                                     verbose_name="Área de Trabajo")
    cargo = models.CharField(max_length=150, blank=True, verbose_name="Cargo")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Papeleta"
        verbose_name_plural = "Papeletas"
        ordering = ['fecha_inicio', 'dni']
        indexes = [
            models.Index(fields=['dni', 'fecha_inicio', 'fecha_fin']),
        ]

    def __str__(self):
        return f"{self.dni} | {self.tipo_permiso} | {self.fecha_inicio} → {self.fecha_fin}"


# ─────────────────────────────────────────────────────────────
# SECCIÓN 4 ▸ BANCO DE HORAS (solo STAFF)
# ─────────────────────────────────────────────────────────────

class BancoHoras(models.Model):
    """
    Banco de horas extras compensatorias — solo personal STAFF.

    Por ley, cuando las HE se compensan en lugar de pagarse,
    el empleador debe llevar registro individual del saldo.

    Un registro por persona × mes/año.
    """

    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.CASCADE,
        related_name='banco_horas',
        verbose_name="Personal")

    periodo_anio = models.PositiveSmallIntegerField(verbose_name="Año")
    periodo_mes = models.PositiveSmallIntegerField(
        verbose_name="Mes",
        validators=[MinValueValidator(1), MaxValueValidator(12)])

    he_25_acumuladas = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        verbose_name="HE 25% Acumuladas (h)")
    he_35_acumuladas = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        verbose_name="HE 35% Acumuladas (h)")
    he_100_acumuladas = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        verbose_name="HE 100% Acumuladas (feriado, h)")
    he_compensadas = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        verbose_name="HE Compensadas (h usadas como CHE/descanso)")
    saldo_horas = models.DecimalField(
        max_digits=7, decimal_places=2, default=Decimal('0.00'),
        verbose_name="Saldo al Cierre del Período",
        help_text="Total acumuladas − compensadas")

    cerrado = models.BooleanField(
        default=False,
        verbose_name="Período Cerrado",
        help_text="True cuando fue auditado y no puede modificarse")

    observaciones = models.TextField(blank=True, verbose_name="Observaciones")
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Banco de Horas"
        verbose_name_plural = "Banco de Horas"
        ordering = ['-periodo_anio', '-periodo_mes', 'personal']
        unique_together = ['personal', 'periodo_anio', 'periodo_mes']
        indexes = [
            models.Index(fields=['personal', 'periodo_anio', 'periodo_mes']),
        ]

    def __str__(self):
        return (f"{self.personal.apellidos_nombres} | "
                f"{self.periodo_mes:02d}/{self.periodo_anio} | "
                f"Saldo: {self.saldo_horas} h")

    @property
    def total_acumulado(self):
        return self.he_25_acumuladas + self.he_35_acumuladas + self.he_100_acumuladas


class MovimientoBancoHoras(models.Model):
    """
    Movimiento individual en el banco de horas de un empleado STAFF.
    Trazabilidad completa de cada acumulación o uso de horas compensatorias.
    """

    TIPO_MOV = [
        ('ACUMULACION', 'Acumulación (HE generadas en tareo)'),
        ('COMPENSACION', 'Compensación (horas usadas como descanso/CHE)'),
        ('VENCIMIENTO', 'Vencimiento / Caducidad de horas'),
        ('AJUSTE_MANUAL', 'Ajuste Manual'),
        ('LIQUIDACION', 'Liquidación al cese'),
    ]

    TASA_HE = [
        ('25', 'HE 25%'),
        ('35', 'HE 35%'),
        ('100', 'HE 100% (Feriado)'),
        ('NA', 'No aplica (compensación directa)'),
    ]

    banco = models.ForeignKey(
        BancoHoras,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name="Banco de Horas")

    tipo = models.CharField(max_length=20, choices=TIPO_MOV,
                             verbose_name="Tipo de Movimiento")
    tasa = models.CharField(max_length=3, choices=TASA_HE, default='NA',
                             verbose_name="Tasa HE")
    fecha = models.DateField(verbose_name="Fecha del Movimiento")
    horas = models.DecimalField(
        max_digits=6, decimal_places=2,
        verbose_name="Horas (+ acumulación / − compensación)")

    registro_tareo = models.ForeignKey(
        RegistroTareo,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimientos_banco',
        verbose_name="Registro Tareo Origen")

    papeleta_ref = models.ForeignKey(
        RegistroPapeleta,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='movimientos_banco',
        verbose_name="Papeleta Origen")

    descripcion = models.CharField(max_length=300, blank=True,
                                    verbose_name="Descripción")
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Usuario que registró")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Movimiento de Banco de Horas"
        verbose_name_plural = "Movimientos de Banco de Horas"
        ordering = ['-fecha', '-creado_en']
        indexes = [
            models.Index(fields=['banco', 'fecha']),
        ]

    def __str__(self):
        signo = "+" if self.horas >= 0 else ""
        return (f"{self.banco.personal} | {self.fecha} | "
                f"{self.get_tipo_display()} | {signo}{self.horas} h")


# ─────────────────────────────────────────────────────────────
# SECCIÓN 5 ▸ IMPORTACIONES CRUCE: SUNAT / S10
# ─────────────────────────────────────────────────────────────

class RegistroSUNAT(models.Model):
    """
    Registro importado desde el reporte SUNAT/PLAME.
    Permite cruzar el personal reportado a SUNAT contra tareo y BD.
    """

    importacion = models.ForeignKey(
        TareoImportacion,
        on_delete=models.CASCADE,
        related_name='registros_sunat',
        verbose_name="Importación Origen")

    tipo_doc = models.CharField(max_length=20, blank=True,
                                 verbose_name="Tipo de Documento")
    nro_doc = models.CharField(max_length=20, verbose_name="Nro. Documento")
    apellidos_nombres = models.CharField(max_length=250, blank=True,
                                          verbose_name="Apellidos y Nombres")
    periodo = models.CharField(max_length=7, blank=True,
                                verbose_name="Período (MM/AAAA)")
    fecha_ingreso = models.DateField(null=True, blank=True,
                                      verbose_name="Fecha de Ingreso")
    fecha_cese = models.DateField(null=True, blank=True,
                                   verbose_name="Fecha de Cese")
    remuneracion_basica = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Remuneración Básica (S/)")
    dias_laborados = models.PositiveSmallIntegerField(
        null=True, blank=True,
        verbose_name="Días Laborados")
    horas_extras_reportadas = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="Horas Extras Reportadas a SUNAT")
    essalud = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="EsSalud (S/)")
    aporte_pension = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Aporte Pensión (S/)")
    tipo_trabajador_sunat = models.CharField(
        max_length=20, blank=True,
        verbose_name="Tipo Trabajador SUNAT")
    datos_extra = models.JSONField(default=dict,
                                    verbose_name="Campos Adicionales (JSON)")

    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registros_sunat',
        verbose_name="Personal (BD)")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro SUNAT"
        verbose_name_plural = "Registros SUNAT"
        ordering = ['periodo', 'nro_doc']
        indexes = [
            models.Index(fields=['nro_doc', 'periodo']),
        ]

    def __str__(self):
        return f"{self.nro_doc} | {self.apellidos_nombres} | {self.periodo}"


class RegistroS10(models.Model):
    """
    Registro importado desde el reporte del sistema S10 (nómina/planilla).
    Permite cruzar personal activo en S10 contra tareo y SUNAT.
    """

    importacion = models.ForeignKey(
        TareoImportacion,
        on_delete=models.CASCADE,
        related_name='registros_s10',
        verbose_name="Importación Origen")

    codigo_s10 = models.CharField(max_length=20, blank=True,
                                   verbose_name="Código S10")
    tipo_doc = models.CharField(max_length=20, blank=True,
                                 verbose_name="Tipo de Documento")
    nro_doc = models.CharField(max_length=20, verbose_name="Nro. Documento")
    apellidos_nombres = models.CharField(max_length=250, blank=True,
                                          verbose_name="Apellidos y Nombres")
    categoria = models.CharField(max_length=100, blank=True,
                                  verbose_name="Categoría")
    ocupacion = models.CharField(max_length=150, blank=True,
                                  verbose_name="Ocupación / Cargo")
    condicion = models.CharField(max_length=20, blank=True,
                                  verbose_name="Condición")

    periodo = models.CharField(max_length=7, blank=True,
                                verbose_name="Período (MM/AAAA)")
    fecha_ingreso = models.DateField(null=True, blank=True,
                                      verbose_name="Fecha de Ingreso")
    fecha_cese = models.DateField(null=True, blank=True,
                                   verbose_name="Fecha de Cese")
    en_tareo = models.BooleanField(default=True,
                                    verbose_name="¿En Tareo? (flag S10)")

    adelanto_condicion_trabajo = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Adelanto Condición de Trabajo (S/)")
    horas_extra_25 = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="HE 25% (h) en S10")
    horas_extra_35 = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="HE 35% (h) en S10")
    horas_extra_100 = models.DecimalField(
        max_digits=7, decimal_places=2, null=True, blank=True,
        verbose_name="HE 100% (h) en S10")

    partida_control = models.CharField(max_length=100, blank=True,
                                        verbose_name="Partida de Control")
    codigo_proyecto = models.CharField(max_length=50, blank=True,
                                        verbose_name="Código Proyecto Destino")
    regimen_pension = models.CharField(max_length=50, blank=True,
                                        verbose_name="Régimen Pensión")

    datos_extra = models.JSONField(default=dict,
                                    verbose_name="Campos Adicionales (JSON)")

    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='registros_s10',
        verbose_name="Personal (BD)")

    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro S10"
        verbose_name_plural = "Registros S10"
        ordering = ['periodo', 'nro_doc']
        indexes = [
            models.Index(fields=['nro_doc', 'periodo']),
            models.Index(fields=['codigo_s10']),
        ]

    def __str__(self):
        return f"{self.codigo_s10} | {self.nro_doc} | {self.apellidos_nombres} | {self.periodo}"


# ─────────────────────────────────────────────────────────────
# SECCIÓN 6 ▸ CRUCE TAREO vs ROSTER (Fase 2)
# ─────────────────────────────────────────────────────────────

class CruceTareoRoster(models.Model):
    """
    Resultado del cruce entre marcación real (Tareo)
    y la programación proyectada (Roster) por persona-fecha.

    Se genera al ejecutar el proceso de comparación (Fase 2).
    """

    VARIACION = [
        ('COINCIDE', 'Coincide — real igual al proyectado'),
        ('TRABAJO_SIN_ROSTER', 'Trabajó sin estar en Roster'),
        ('AUSENTE_PROYECTADO', 'Ausente aunque Roster marcaba trabajo'),
        ('ROTACION_ANTICIPADA', 'Rotación anticipada (llegó antes)'),
        ('ROTACION_EXTENDIDA', 'Rotación extendida (permaneció más días)'),
        ('LICENCIA_NO_PROYECTADA', 'Licencia/Permiso no proyectado en Roster'),
        ('FALTA_NO_PROYECTADA', 'Falta no proyectada'),
        ('DL_ADELANTADO', 'Día Libre tomado antes de lo proyectado'),
        ('DL_POSTERGADO', 'Día Libre postergado'),
        ('NO_EN_TAREO', 'En Roster pero sin registro de asistencia'),
        ('NO_EN_ROSTER', 'En Tareo pero sin entrada en Roster'),
    ]

    registro_tareo = models.OneToOneField(
        RegistroTareo,
        on_delete=models.CASCADE,
        related_name='cruce_roster',
        verbose_name="Registro de Tareo")

    roster_codigo = models.CharField(
        max_length=20, blank=True,
        verbose_name="Código Roster Proyectado")
    roster_id = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="ID del Registro Roster")

    variacion = models.CharField(
        max_length=25, choices=VARIACION,
        verbose_name="Tipo de Variación")
    detalle_variacion = models.TextField(
        blank=True,
        verbose_name="Detalle de la Variación")

    impacta_pasaje = models.BooleanField(
        default=False,
        verbose_name="¿Impacta en Pasajes?",
        help_text="True si la variación altera el día libre proyectado para pasaje")
    dias_libres_diff = models.DecimalField(
        max_digits=4, decimal_places=1,
        default=Decimal('0.0'),
        verbose_name="Diferencia en Días Libres (real − proyectado)")

    generado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Cruce Tareo–Roster"
        verbose_name_plural = "Cruces Tareo–Roster"
        ordering = ['-registro_tareo__fecha']
        indexes = [
            models.Index(fields=['variacion']),
            models.Index(fields=['impacta_pasaje']),
        ]

    def __str__(self):
        return (f"{self.registro_tareo.dni} | "
                f"{self.registro_tareo.fecha} | "
                f"{self.get_variacion_display()}")
