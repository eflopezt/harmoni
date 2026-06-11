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

from core.crypto_fields import EncryptedCharField


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

    # Día de la semana de descanso fijo (para regímenes semanales).
    # Convención: misma numeración que Python date.weekday() (0=Lun..6=Dom).
    # En regímenes acumulativos / rotativos (FORÁNEO 21×7, turnos rotativos)
    # NO aplica: el día de descanso se determina por el ciclo, no por el día.
    DIA_DESCANSO_CHOICES = [
        (0, 'Lunes'),
        (1, 'Martes'),
        (2, 'Miércoles'),
        (3, 'Jueves'),
        (4, 'Viernes'),
        (5, 'Sábado'),
        (6, 'Domingo'),
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

    # Día de descanso semanal (solo aplica a regímenes SEMANAL/NOCTURNA con
    # descanso fijo, ej. 6×1 gastronomía, 5×2 oficina). Para ACUMULATIVA y
    # ROTATIVA este campo no se usa — el día libre lo determina el ciclo.
    dia_descanso = models.PositiveSmallIntegerField(
        choices=DIA_DESCANSO_CHOICES,
        default=6,
        verbose_name="Día de Descanso Semanal",
        help_text="Domingo por defecto. Solo aplica a regímenes semanales "
                  "con descanso fijo (gastronomía 6×1, oficina 5×2). En "
                  "regímenes acumulativos/rotativos no se usa."
    )

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

    @property
    def es_semanal_descanso_fijo(self):
        """True para regímenes con día libre fijo (6×1, 5×2, etc.).

        Estos regímenes nunca generan "DL" (día libre ganado del ciclo
        acumulativo) — su día libre es DS (descanso semanal). Aplica a
        gastronomía, oficina, comercio y régimen general semanal.
        """
        return self.jornada_tipo in ('SEMANAL', 'NOCTURNA') and self.dias_descanso_ciclo <= 1

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


class CompensacionFeriado(models.Model):
    """
    Traslado configurable de un feriado oficial a otro día laborable.

    Ejemplo típico: el Gobierno decreta que el 2 de abril (feriado oficial)
    se trabaja normalmente y el descanso se toma el 4 de abril.
    En ese caso:
        fecha_feriado    = 2026-04-02  ← deja de ser feriado
        fecha_compensada = 2026-04-04  ← toma el tratamiento de feriado

    El importer y los procesadores de tareo consultan esta tabla para
    ajustar qué días aplican el 100% de HE adicional.
    """

    fecha_feriado = models.DateField(
        verbose_name="Fecha del Feriado Original",
        help_text="Día oficial de feriado que se traslada (se trabaja normalmente).",
    )
    fecha_compensada = models.DateField(
        verbose_name="Fecha Compensada (nuevo feriado)",
        help_text="Día que toma el tratamiento de feriado en sustitución.",
    )
    descripcion = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Descripción",
        help_text="Ej: 'Feriado 02-Abr trasladado al 04-Abr por D.S. 012-2026'",
    )
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo",
        help_text="Desactivar sin borrar si el traslado fue revertido.",
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Compensación de Feriado"
        verbose_name_plural = "Compensaciones de Feriado"
        ordering = ['fecha_feriado']
        unique_together = [['fecha_feriado', 'fecha_compensada']]

    def __str__(self):
        return f"{self.fecha_feriado} → {self.fecha_compensada} | {self.descripcion or 'Traslado de feriado'}"


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
        ('ZK', 'ZKTeco — Sincronización Directa'),
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
        ('REGLA_ESPECIAL', 'Regla Especial por Empleado'),
        ('DESCANSO_SEMANAL', 'Descanso Semanal Automático'),
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
        max_length=30, choices=FUENTE_CODIGO,
        default='RELOJ',
        verbose_name="Fuente del Código")

    # Almuerzo manual (None = automático)
    almuerzo_manual = models.DecimalField(
        max_digits=3, decimal_places=1,
        null=True, blank=True, default=None,
        verbose_name="Almuerzo manual (horas)",
        help_text="None=automático (>7h→1h), 0=sin descuento, 0.5, 1.0")

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
    Papeleta unificada — puede ser importada desde Synkro/Excel O creada
    manualmente en el sistema (por admin o por el trabajador vía portal).

    Cubre TODOS los tipos de permiso, licencia, compensación, vacaciones, etc.
    Actúa como override sobre RegistroTareo en el rango de fechas indicado.

    Para compensaciones (CPF/CDT): fecha_referencia guarda la fecha trabajada
    (feriado/DSO) que originó la compensación. fecha_inicio/fin es el día libre.
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
        ('LICENCIA_MATERNIDAD', 'Licencia por Maternidad (LM)'),
        ('COMISION_TRABAJO', 'Comisión de Trabajo (CT)'),
        ('COMPENSACION_FERIADO', 'Compensación por Feriado (CPF)'),
        ('COMP_DIA_TRABAJO', 'Compensación de Día por Trabajo (CDT)'),
        ('SUSPENSION', 'Suspensión Disciplinaria'),
        ('SUSPENSION_ACTO_INSEGURO', 'Suspensión por Acto Inseguro (SAI)'),
        ('CAPACITACION', 'Capacitación (CAP)'),
        ('TRABAJO_REMOTO', 'Trabajo Remoto (TR)'),
        ('OTRO', 'Otro'),
    ]

    ORIGEN_CHOICES = [
        ('IMPORTACION', 'Importación (Synkro/Excel)'),
        ('SISTEMA', 'Creada por Administrador'),
        ('PORTAL', 'Solicitada por Trabajador'),
    ]

    ESTADO_CHOICES = [
        ('APROBADA', 'Aprobada'),
        ('PENDIENTE', 'Pendiente de aprobación'),
        ('RECHAZADA', 'Rechazada'),
        ('EJECUTADA', 'Ejecutada'),
        ('ANULADA', 'Anulada'),
    ]

    # ── Origen y trazabilidad ──
    importacion = models.ForeignKey(
        TareoImportacion,
        on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='papeletas',
        verbose_name="Importación Origen",
        help_text="Solo para papeletas importadas; null si fue creada en el sistema")
    origen = models.CharField(
        max_length=15, choices=ORIGEN_CHOICES, default='IMPORTACION',
        verbose_name="Origen")

    # ── Trabajador ──
    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='papeletas_tareo',
        verbose_name="Personal")
    dni = models.CharField(max_length=20, verbose_name="DNI/Doc")
    nombre_archivo = models.CharField(max_length=250, blank=True,
                                       verbose_name="Nombre (del archivo)")

    # ── Tipo y fechas ──
    tipo_permiso = models.CharField(max_length=30, choices=TIPO_PERMISO_CHOICES,
                                     verbose_name="Tipo de Permiso")
    tipo_permiso_raw = models.CharField(
        max_length=100, blank=True,
        verbose_name="Tipo Permiso Original (texto del archivo)")
    iniciales = models.CharField(max_length=10, blank=True,
                                  verbose_name="Iniciales del Código")
    fecha_inicio = models.DateField(verbose_name="Fecha de Inicio")
    fecha_fin = models.DateField(verbose_name="Fecha de Fin")
    fecha_referencia = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha Referencia",
        help_text="Para compensaciones: fecha del feriado/DSO trabajado que origina esta papeleta")
    detalle = models.TextField(blank=True, verbose_name="Detalle / Motivo")
    dias_habiles = models.PositiveSmallIntegerField(
        default=0, verbose_name="Días Hábiles Cubiertos")

    area_trabajo = models.CharField(max_length=150, blank=True,
                                     verbose_name="Área de Trabajo")
    cargo = models.CharField(max_length=150, blank=True, verbose_name="Cargo")

    # ── Workflow ──
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='APROBADA',
        verbose_name="Estado",
        help_text="Importadas = Aprobada por defecto; manuales = Pendiente")
    creado_por = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='papeletas_creadas',
        verbose_name="Creado por")
    aprobado_por = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='papeletas_aprobadas',
        verbose_name="Aprobado por")
    fecha_aprobacion = models.DateField(null=True, blank=True,
                                         verbose_name="Fecha Aprobación")
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Papeleta"
        verbose_name_plural = "Papeletas"
        ordering = ['-fecha_inicio', 'dni']
        indexes = [
            models.Index(fields=['dni', 'fecha_inicio', 'fecha_fin']),
            models.Index(fields=['personal', 'estado', 'tipo_permiso']),
        ]

    def __str__(self):
        nombre = self.personal.apellidos_nombres if self.personal else self.dni
        return f"{nombre} | {self.get_tipo_permiso_display()} | {self.fecha_inicio} → {self.fecha_fin} [{self.get_estado_display()}]"

    @property
    def es_compensacion(self):
        """True si es una papeleta de compensación (CPF o CDT)."""
        return self.tipo_permiso in ('COMPENSACION_FERIADO', 'COMP_DIA_TRABAJO')

    @property
    def es_importada(self):
        return self.origen == 'IMPORTACION'


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


# ─────────────────────────────────────────────────────────────
# SECCIÓN 6b ▸ ENVÍO DE REPORTES POR ÁREA
# ─────────────────────────────────────────────────────────────

class ConfiguracionReporteArea(models.Model):
    """
    Configuración de envío de reportes de asistencia por área.
    Almacena los destinatarios (jefaturas) y CC por área.
    """
    area = models.OneToOneField(
        'personal.Area',
        on_delete=models.CASCADE,
        related_name='config_reporte',
        verbose_name='Área',
    )
    emails_jefatura = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Emails jefatura (destinatarios)',
        help_text='Lista de correos principales. Ej: ["jefe@empresa.com"]',
    )
    emails_cc = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Emails con copia (CC)',
        help_text='Lista de correos en copia.',
    )
    asunto_template = models.CharField(
        max_length=300,
        default='Reporte de Asistencia - {area} - {periodo}',
        verbose_name='Plantilla de asunto',
        help_text='Vars: {area}, {periodo}, {empresa}',
    )
    cuerpo_template = models.TextField(
        blank=True,
        default='',
        verbose_name='Plantilla de cuerpo del correo',
        help_text='Vars: {area}, {periodo}, {empresa}, {total_empleados}. Dejar vacío para usar el predeterminado.',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    # Jefe/responsable del área (nombre para mostrar en UI)
    nombre_jefe = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name='Nombre del jefe / responsable',
        help_text='Nombre de referencia para mostrar en el panel',
    )
    # Historial de cambios de emails (auditoría)
    historial_emails = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Historial de cambios de emails',
        help_text='Registro automático de cada vez que se cambian los destinatarios',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Configuración Reporte por Área'
        verbose_name_plural = 'Configuraciones Reporte por Área'
        ordering = ['area__nombre']

    def __str__(self):
        n = len(self.emails_jefatura or [])
        return f'{self.area.nombre} ({n} destinatario{"s" if n != 1 else ""})'

    def get_emails_jefatura(self) -> list[str]:
        return [e.strip() for e in (self.emails_jefatura or []) if e.strip()]

    def get_emails_cc(self) -> list[str]:
        return [e.strip() for e in (self.emails_cc or []) if e.strip()]

    def render_asunto(self, area_nombre: str, periodo: str, empresa: str = '') -> str:
        tpl = self.asunto_template or 'Reporte de Asistencia - {area} - {periodo}'
        return tpl.format(area=area_nombre, periodo=periodo, empresa=empresa)

    def render_cuerpo(self, area_nombre: str, periodo: str, empresa: str = '', total: int = 0) -> str:
        if self.cuerpo_template:
            return self.cuerpo_template.format(
                area=area_nombre, periodo=periodo, empresa=empresa,
                total_empleados=total,
            )
        return (
            f'Estimado equipo,\n\n'
            f'Adjunto encontrará el paquete de reportes de asistencia del área '
            f'{area_nombre} correspondiente al periodo {periodo}.\n\n'
            f'Los reportes están organizados por colaborador en el archivo ZIP adjunto.\n\n'
            f'Ante cualquier consulta o discrepancia, comunicarse con el área de '
            f'Gestión Humana a la brevedad, ya que esta información impacta en el '
            f'cálculo de la nómina.\n\n'
            f'Saludos,\n'
            f'{empresa or "Recursos Humanos"}'
        )


class EnvioReporteArea(models.Model):
    """Log de cada envío de reporte de asistencia por área."""
    TIPO_CHOICES = [
        ('SEMANAL', 'Semanal'),
        ('QUINCENAL', 'Quincenal'),
        ('MENSUAL', 'Mensual'),
        ('PERSONALIZADO', 'Personalizado'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('ENVIADO', 'Enviado'),
        ('PARCIAL', 'Enviado con errores'),
        ('ERROR', 'Error'),
    ]

    area = models.ForeignKey(
        'personal.Area',
        on_delete=models.CASCADE,
        related_name='envios_reporte',
        verbose_name='Área',
    )
    tipo_periodo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='PERSONALIZADO')
    fecha_inicio = models.DateField(verbose_name='Fecha inicio')
    fecha_fin = models.DateField(verbose_name='Fecha fin')
    emails_destino = models.JSONField(default=list)
    emails_cc = models.JSONField(default=list)
    asunto = models.CharField(max_length=300, blank=True)
    cuerpo = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE')
    empleados_total = models.PositiveIntegerField(default=0)
    empleados_enviados = models.PositiveIntegerField(default=0)
    errores = models.JSONField(default=list)
    creado_por = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='envios_reporte_area',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Envío de Reporte por Área'
        verbose_name_plural = 'Envíos de Reporte por Área'
        ordering = ['-creado_en']

    def __str__(self):
        return f'{self.area.nombre} | {self.fecha_inicio}→{self.fecha_fin} | {self.estado}'


# ─────────────────────────────────────────────────────────────
# SECCIÓN 7 ▸ CONFIGURACIÓN DEL SISTEMA
# ─────────────────────────────────────────────────────────────

class ConfiguracionSistema(models.Model):
    """
    Configuración global del sistema de tareo/planilla.
    Singleton — solo puede existir un registro.

    Centraliza todas las reglas de negocio configurables:
    ciclo de HE, corte de planilla, correos, etc.
    """

    # ── Datos empresa ──
    empresa_nombre = models.CharField(max_length=200, default='',
                                       verbose_name="Nombre de la Empresa")
    ruc = models.CharField(max_length=11, blank=True, verbose_name="RUC")

    # ── Identidad Visual / Membrete ──
    empresa_direccion = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name="Dirección",
        help_text="Dirección completa de la empresa. Aparece en membretes y constancias.")
    empresa_telefono = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name="Teléfono / Anexo",
        help_text="Ej: (01) 234-5678 / Nextel 123*456")
    empresa_email = models.EmailField(
        blank=True, default='',
        verbose_name="Email corporativo",
        help_text="Email de contacto que aparece en documentos")
    empresa_web = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Sitio web",
        help_text="Ej: www.empresa.com.pe")
    logo = models.ImageField(
        upload_to='empresa/logo/', blank=True, null=True,
        verbose_name="Logo empresa",
        help_text="PNG o JPG con fondo transparente. Recomendado: 300×100px.")
    membrete_color = models.CharField(
        max_length=7, default='#0f766e',
        verbose_name="Color membrete",
        help_text="Color principal del membrete en formato HEX. Ej: #0f766e")
    membrete_mostrar = models.BooleanField(
        default=True,
        verbose_name="Usar membrete en documentos",
        help_text="Si está activo, agrega el membrete automáticamente a todas las constancias generadas.")
    firma_nombre = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Nombre del firmante",
        help_text="Ej: Juan Pérez García")
    firma_cargo = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Cargo del firmante",
        help_text="Ej: Jefe de Recursos Humanos")
    firma_imagen = models.ImageField(
        upload_to='empresa/firmas/', blank=True, null=True,
        verbose_name="Imagen de firma",
        help_text="PNG con fondo transparente. Recomendado: 200×80px.")

    # ── Modo del Sistema ──
    MODO_SISTEMA_CHOICES = [
        ('ASISTENCIA', 'Solo Asistencia'),
        ('ASISTENCIA_NOMINA', 'Asistencia + Nómina'),
        ('ERP_COMPLETO', 'ERP Completo'),
    ]
    modo_sistema = models.CharField(
        max_length=20, choices=MODO_SISTEMA_CHOICES, default='ASISTENCIA',
        verbose_name="Modo del Sistema",
        help_text="Define el alcance: Solo tareo/reloj, con nómina integrada, o ERP completo")

    PROGRAMA_NOMINA_CHOICES = [
        ('NINGUNO', 'Sin programa externo'),
        ('S10', 'S10 — Costos y Presupuestos'),
        ('SAP', 'SAP'),
        ('EXCEL', 'Excel manual'),
        ('OTRO', 'Otro sistema'),
    ]
    programa_nomina = models.CharField(
        max_length=20, choices=PROGRAMA_NOMINA_CHOICES, default='S10',
        verbose_name="Programa de Nómina Destino",
        help_text="Sistema donde se procesa la nómina. Determina formato de exportación.")
    programa_nomina_nombre = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Nombre del Programa (si es Otro)",
        help_text="Solo si eligió 'Otro'. Ej: Exactus, Contasis, Starsoft")

    # ── Módulos Activos ──
    mod_prestamos = models.BooleanField(
        default=True, verbose_name="Préstamos y Adelantos")
    mod_viaticos = models.BooleanField(
        default=False, verbose_name="Viáticos y CDT")
    mod_documentos = models.BooleanField(
        default=True, verbose_name="Legajo Digital y Constancias")
    mod_evaluaciones = models.BooleanField(
        default=False, verbose_name="Evaluaciones de Desempeño")
    mod_capacitaciones = models.BooleanField(
        default=False, verbose_name="Capacitaciones / LMS")
    mod_reclutamiento = models.BooleanField(
        default=False, verbose_name="Reclutamiento y Selección")
    mod_encuestas = models.BooleanField(
        default=False, verbose_name="Encuestas y Clima Laboral")
    mod_salarios = models.BooleanField(
        default=False, verbose_name="Estructura Salarial")

    # ── Roster / Control proyectado ──
    mod_roster = models.BooleanField(
        default=False,
        verbose_name="Roster (Control Proyectado)",
        help_text=(
            "Activa el panel matricial de roster para planificar bajadas y pasajes. "
            "Solo es necesario si tienes personal foráneo con régimen de turnos (14x7, 21x7, etc.). "
            "Empresas con personal Lima/Local pueden desactivarlo — los días libres "
            "se gestionan directamente como permisos/vacaciones."
        ))

    ROSTER_APLICA_CHOICES = [
        ('FORANEOS', 'Solo Personal Foráneo'),
        ('TODOS',    'Todos los trabajadores'),
    ]
    roster_aplica_a = models.CharField(
        max_length=10, choices=ROSTER_APLICA_CHOICES, default='FORANEOS',
        verbose_name="Roster aplica a",
        help_text=(
            "Define qué personal aparece en el panel de roster. "
            "'Solo Foráneo' es lo habitual (régimen acumulativo, pasajes aéreos). "
            "'Todos' si el turno rotativo aplica también a personal Lima/Local."
        ))

    # ── Formato de Exportación ──
    export_incluir_sueldo = models.BooleanField(
        default=False, verbose_name="Incluir Sueldo Base en exportación")
    export_incluir_faltas = models.BooleanField(
        default=True, verbose_name="Incluir Faltas/Descuentos")
    export_incluir_banco_horas = models.BooleanField(
        default=True, verbose_name="Incluir Banco de Horas")
    export_separar_staff_rco = models.BooleanField(
        default=True, verbose_name="Separar STAFF / RCO en archivos distintos")
    EXPORT_FORMATO_CHOICES = [
        ('XLSX', 'Excel (.xlsx)'),
        ('CSV', 'CSV'),
        ('PDF', 'PDF'),
    ]
    export_formato = models.CharField(
        max_length=10, choices=EXPORT_FORMATO_CHOICES, default='XLSX',
        verbose_name="Formato de exportación por defecto")

    # ── Ciclo de planilla ──
    fecha_apertura = models.DateField(
        null=True, blank=True,
        verbose_name="Fecha de Apertura del Sistema",
        help_text=(
            "Fecha desde la que el cliente usa Harmoni. "
            "El importador advertirá si se intentan cargar datos anteriores a esta fecha. "
            "Dejar en blanco para no validar."
        ))

    dia_corte_planilla = models.PositiveSmallIntegerField(
        default=20,
        verbose_name="Día de Corte de Planilla",
        help_text="Día del mes en que cierra el ciclo de HE. Ej: 20")
    # Ciclo HE: del día (dia_corte+1) del mes anterior al dia_corte del mes actual
    # Ej con corte=20: ciclo HE = 21/mes_anterior → 20/mes_actual
    # Ciclo asistencia: 01 → último día del mes

    regularizacion_activa = models.BooleanField(
        default=True,
        verbose_name="Activar Regularización de Fin de Mes",
        help_text=(
            "Si está activo, los descuentos (faltas, LSG) entre el día "
            "(corte+1) y fin de mes se difieren al siguiente mes como regularización."
        ))

    # ── Jornada por defecto (se puede sobreescribir en Personal) ──
    jornada_local_horas = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('8.5'),
        verbose_name="Jornada Local Lun–Vie (h/día)",
        help_text="Ej: 8.5 para personal LOCAL 7:30–17:00 (incluye 30 min almuerzo pagado)")
    jornada_sabado_horas = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('5.5'),
        verbose_name="Jornada Local Sábado (h/día)",
        help_text="Ej: 5.5 para personal LOCAL sábados 07:30–13:00 (sin descuento almuerzo)")
    jornada_domingo_horas = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('4.0'),
        verbose_name="Jornada Domingo (h/día)",
        help_text="Ej: 4.0 para domingos trabajados (LOCAL y FORÁNEO)")
    jornada_foraneo_horas = models.DecimalField(
        max_digits=4, decimal_places=1, default=Decimal('11.0'),
        verbose_name="Jornada Foráneo (h/día)",
        help_text="Ej: 11.0 para personal FORÁNEO 7:30–18:30")

    # ── Parámetros Legales Perú ──
    uit_valor = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('5500.00'),
        verbose_name="UIT (S/)",
        help_text="Unidad Impositiva Tributaria vigente. 2026: S/ 5,500 (DS 233-2025-EF). "
                  "Impacta IR 5ta categoría, gratificaciones y otros cálculos.")
    uit_anno = models.PositiveSmallIntegerField(
        default=2026,
        verbose_name="Año UIT",
        help_text="Año de vigencia del valor UIT configurado.")
    rmv_valor = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal('1130.00'),
        verbose_name="RMV / Sueldo Mínimo (S/)",
        help_text="Remuneración Mínima Vital vigente. Desde ene-2025: S/ 1,130 (DS 006-2024-TR). "
                  "Se usa para asignación familiar (10% RMV = S/ 113.00) y otros cálculos.")
    usar_metodo_sunat_ir5ta = models.BooleanField(
        default=False,
        verbose_name="IR 5ta: usar método SUNAT (retención mensual acumulada)",
        help_text="Si está activo, IR 5ta usa el método oficial SUNAT con proyección mes-a-mes "
                  "(remuneración fija proyectada + variables percibidas). Recomendado para "
                  "evitar sobre-estimación en empleados con HE/bonos variables o cese a mitad "
                  "de año. Default: False (método legacy proyección × 14).")

    # ── Tasas AFP — override por configuración (sin redeploy) ──
    # SBS publica nuevas tasas cada cuatrimestre. Si este campo está
    # poblado, el engine usa estos valores en lugar de los hardcoded.
    afp_tasas_override = models.JSONField(
        null=True, blank=True,
        verbose_name="Override de tasas AFP (SBS)",
        help_text='JSON con tasas por AFP. Formato: '
                  '{"Habitat": {"comision_flujo": "1.47", "seguro": "1.74"}, ...}. '
                  'Si está vacío, usa valores predeterminados del engine.')
    afp_tope_rma = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name="Tope RMA AFP — Prima Seguro (S/)",
        help_text="Remuneración Máxima Asegurable para cálculo de prima de "
                  "seguro AFP. Si está vacío, usa S/ 12,131.49 (Q2 2026). "
                  "SBS lo actualiza cuatrimestralmente.")
    afp_tasas_vigencia = models.CharField(
        max_length=20, blank=True,
        verbose_name="Vigencia tasas AFP",
        help_text="Cuatrimestre de vigencia (ej. 'Q2-2026' o '2026-04 a 2026-07').")

    # ── Synkro (nombres de hojas) ──
    synkro_hoja_reloj = models.CharField(
        max_length=60, default='Reloj',
        verbose_name="Nombre Hoja Reloj en Synkro",
        help_text="Nombre exacto de la hoja del reporte de reloj biométrico")
    synkro_hoja_papeletas = models.CharField(
        max_length=60, default='Papeletas',
        verbose_name="Nombre Hoja Papeletas en Synkro")

    # ── Columnas del Reloj (posiciones 0-based, configurables) ──
    reloj_col_dni = models.PositiveSmallIntegerField(
        default=0, verbose_name="Columna DNI en Reloj")
    reloj_col_nombre = models.PositiveSmallIntegerField(
        default=1, verbose_name="Columna Nombre en Reloj")
    reloj_col_condicion = models.PositiveSmallIntegerField(
        default=5, verbose_name="Columna Condición en Reloj")
    reloj_col_tipo_trab = models.PositiveSmallIntegerField(
        default=6, verbose_name="Columna Tipo Trabajador en Reloj")
    reloj_col_area = models.PositiveSmallIntegerField(
        default=7, verbose_name="Columna Área en Reloj")
    reloj_col_cargo = models.PositiveSmallIntegerField(
        default=8, verbose_name="Columna Cargo en Reloj")
    reloj_col_inicio_dias = models.PositiveSmallIntegerField(
        default=9,
        verbose_name="Primera Columna de Días en Reloj",
        help_text="Índice de la primera columna con fechas/días (0-based)")

    # ── Notificaciones ──
    email_habilitado = models.BooleanField(
        default=False,
        verbose_name="Habilitar Notificaciones por Email")
    email_desde = models.EmailField(
        blank=True,
        verbose_name="Email Remitente",
        help_text="Ej: tareo@empresa.com")
    email_asunto_semanal = models.CharField(
        max_length=200,
        default='Tu resumen de asistencia semanal — {empresa}',
        verbose_name="Asunto Email Semanal",
        help_text="Usa {empresa}, {semana}, {empleado} como variables")
    email_dia_envio = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Día de Envío (0=Lun … 6=Dom)",
        help_text="Día de la semana para enviar el resumen semanal")

    # ── IA / Multi-Provider (Fase 4.4) ──
    IA_PROVIDER_CHOICES = [
        ('GEMINI',    'Gemini (Google — recomendado)'),
        ('DEEPSEEK',  'DeepSeek (más económico)'),
        ('OPENAI',    'OpenAI (GPT-4o-mini)'),
        ('ANTHROPIC', 'Anthropic (Claude)'),
        ('OLLAMA',    'Ollama (Local — sin costo)'),
        ('NINGUNO',   'Sin IA'),
    ]
    IA_OCR_PROVIDER_CHOICES = [
        ('GEMINI',  'Gemini 2.5 Flash (PDF nativos)'),
        ('NINGUNO', 'Sin OCR IA'),
    ]
    ia_provider = models.CharField(
        max_length=20, choices=IA_PROVIDER_CHOICES, default='NINGUNO',
        verbose_name="Proveedor de IA (Chat/RAG)",
        help_text="Proveedor para chat, análisis y mapeo de columnas")
    ia_api_key = EncryptedCharField(
        max_length=500, blank=True, default='',
        verbose_name="API Key del proveedor",
        help_text="Clave API de Gemini, DeepSeek u OpenAI. No aplica para Ollama.")
    ia_endpoint = models.CharField(
        max_length=200, blank=True, default='http://localhost:11434',
        verbose_name="Endpoint (Ollama / DeepSeek custom)",
        help_text="URL del servidor. Ollama: http://localhost:11434 | DeepSeek: https://api.deepseek.com/v1")
    ia_modelo = models.CharField(
        max_length=100, blank=True, default='gemini-2.5-flash',
        verbose_name="Modelo",
        help_text="Gemini: gemini-2.5-flash | gemini-2.5-pro | DeepSeek: deepseek-chat | OpenAI: gpt-4o-mini | Ollama: llama3.2")
    ia_ocr_provider = models.CharField(
        max_length=20, choices=IA_OCR_PROVIDER_CHOICES, default='NINGUNO',
        verbose_name="Proveedor OCR (PDFs escaneados)",
        help_text="Gemini Files API para OCR de PDFs escaneados.")
    ia_gemini_api_key = EncryptedCharField(
        max_length=500, blank=True, default='',
        verbose_name="API Key Gemini (OCR)",
        help_text=(
            "Clave API de Gemini exclusiva para OCR de PDFs escaneados. "
            "Permite usar DeepSeek para chat y Gemini para OCR simultáneamente. "
            "Si está vacía y el proveedor principal es Gemini, se usa ia_api_key."
        ))
    ia_mapeo_activo = models.BooleanField(
        default=False,
        verbose_name="Activar Mapeo IA de Columnas",
        help_text="Detecta automáticamente columnas en archivos de importación desconocidos")


    # ── ZapSign Firma Digital ────────────────────────────────────────
    zapsign_api_key = EncryptedCharField(
        max_length=200, blank=True,
        verbose_name='ZapSign API Key',
        help_text='Token API de ZapSign para firma digital. Obtener en app.zapsign.com.br/settings/tokens',
    )
    zapsign_activo = models.BooleanField(
        default=False,
        verbose_name='Firma Digital Activa',
        help_text='Habilitar modulo de firma digital con ZapSign',
    )

    # ── Control de Horas Extra ──
    he_requiere_solicitud = models.BooleanField(
        default=False,
        verbose_name="Requiere solicitud previa para HE",
        help_text="Si activo, las HE solo se registran si hay una SolicitudHE aprobada. "
                  "Sin solicitud aprobada el exceso se ignora (no va a banco ni nómina).")
    HE_TIPO_CHOICES = [
        ('PAGABLE',      'Pagable (se liquida en planilla: 25%/35%/100%)'),
        ('COMPENSABLE',  'Compensable (va al Banco de Horas; se paga en liquidación si no se compensa)'),
    ]
    he_tipo_default = models.CharField(
        max_length=20, choices=HE_TIPO_CHOICES, default='PAGABLE',
        verbose_name="Tipo de HE por defecto",
        help_text="Tipo aplicado cuando la solicitud no especifica tipo. "
                  "STAFF por naturaleza es compensable; RCO es pagable.")

    # ── S10 Export ──
    s10_nombre_concepto_he25 = models.CharField(
        max_length=100,
        default='HORAS EXTRAS 25%',
        verbose_name="Nombre Concepto HE 25% en S10")
    s10_nombre_concepto_he35 = models.CharField(
        max_length=100,
        default='HORAS EXTRAS 35%',
        verbose_name="Nombre Concepto HE 35% en S10")
    s10_nombre_concepto_he100 = models.CharField(
        max_length=100,
        default='HORAS EXTRAS 100%',
        verbose_name="Nombre Concepto HE 100% en S10")

    # ── Integraciones: Telegram Bot ──────────────────────────────────────────
    telegram_bot_token = EncryptedCharField(
        max_length=200, blank=True, default='',
        verbose_name="Token del Bot de Telegram",
        help_text="Token del bot de Telegram (obtenido desde @BotFather).")
    telegram_channel_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="ID / Username del Canal",
        help_text="@username para canales públicos o -100XXXXXXX para privados.")

    # ── Integraciones: WhatsApp Business Cloud API ───────────────────────────
    WHATSAPP_PROVIDER_CHOICES = [
        ('NONE', 'Sin WhatsApp'),
        ('META_CLOUD', 'Meta Cloud API'),
        ('OPENCLAW', 'OpenClaw Gateway'),
    ]
    whatsapp_provider = models.CharField(
        max_length=12, choices=WHATSAPP_PROVIDER_CHOICES, default='NONE',
        verbose_name="Proveedor WhatsApp",
        help_text="Seleccione el proveedor para enviar mensajes de WhatsApp.")
    whatsapp_phone_number_id = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="WhatsApp Phone Number ID",
        help_text="ID del número en Meta Developer Console (no el número real).")
    whatsapp_access_token = EncryptedCharField(
        max_length=500, blank=True, default='',
        verbose_name="WhatsApp Access Token",
        help_text="Token permanente de la Meta Business App para WhatsApp Cloud API.")
    whatsapp_to_number = models.CharField(
        max_length=500, blank=True, default='',
        verbose_name="Número(s) Destino WhatsApp",
        help_text="Formato 51XXXXXXXXX. Separar por coma para múltiples destinatarios.")
    openclaw_gateway_url = models.CharField(
        max_length=200, blank=True, default='http://localhost:19000',
        verbose_name="OpenClaw Gateway URL",
        help_text="URL del gateway OpenClaw para envío de WhatsApp.")
    openclaw_gateway_token = EncryptedCharField(
        max_length=200, blank=True, default='',
        verbose_name="OpenClaw Gateway Token",
        help_text="Token de autenticación para OpenClaw (si aplica).")

    actualizado_en = models.DateTimeField(auto_now=True)
    actualizado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name="Actualizado por")

    class Meta:
        verbose_name = "Configuración del Sistema"
        verbose_name_plural = "Configuración del Sistema"

    def __str__(self):
        return f"Configuración — {self.empresa_nombre} | Corte: día {self.dia_corte_planilla}"

    def save(self, *args, **kwargs):
        """Singleton: siempre usa pk=1. Invalida caché al guardar."""
        self.pk = 1
        super().save(*args, **kwargs)
        # Invalidar todas las cachés que dependen de la configuración
        from django.core.cache import cache
        cache.delete_many([
            'harmoni_config_v1',          # ConfiguracionSistema.get()
            'harmoni_ctx_config_v4',      # context_processor config
        ])

    @classmethod
    def get(cls):
        """
        Obtiene (o crea) la instancia de configuración.

        Cacheada 5 minutos en Django cache framework.
        Se invalida automáticamente en save().
        Con 25+ call sites en el sistema, evita 25 queries por request.
        """
        from django.core.cache import cache
        _CACHE_KEY = 'harmoni_config_v1'
        obj = cache.get(_CACHE_KEY)
        if obj is None:
            obj, _ = cls.objects.get_or_create(pk=1, defaults={'empresa_nombre': 'Mi Empresa'})
            cache.set(_CACHE_KEY, obj, 300)  # 5 minutos
        return obj

    @property
    def logo_base64(self):
        """Convierte el logo a base64 para embeber en PDFs (xhtml2pdf no soporta rutas relativas)."""
        if not self.logo:
            return None
        try:
            import base64
            with self.logo.open('rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            ext = self.logo.name.rsplit('.', 1)[-1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            return f'data:{mime};base64,{data}'
        except Exception:
            return None

    @property
    def firma_base64(self):
        """Convierte la imagen de firma a base64 para embeber en PDFs."""
        if not self.firma_imagen:
            return None
        try:
            import base64
            with self.firma_imagen.open('rb') as f:
                data = base64.b64encode(f.read()).decode('utf-8')
            ext = self.firma_imagen.name.rsplit('.', 1)[-1].lower()
            mime = 'image/png' if ext == 'png' else 'image/jpeg'
            return f'data:{mime};base64,{data}'
        except Exception:
            return None

    def get_ciclo_he(self, anio, mes):
        """
        Retorna (fecha_inicio, fecha_fin) del ciclo de HE para un mes dado.
        Con corte=20: ciclo HE de febrero 2026 = 21/ene/2026 → 20/feb/2026
        """
        import calendar
        corte = self.dia_corte_planilla
        # Inicio: día (corte+1) del mes anterior
        if mes == 1:
            mes_ant, anio_ant = 12, anio - 1
        else:
            mes_ant, anio_ant = mes - 1, anio
        inicio = datetime.date(anio_ant, mes_ant, corte + 1)
        fin = datetime.date(anio, mes, corte)
        return inicio, fin

    def get_ciclo_asistencia(self, anio, mes):
        """
        Retorna (fecha_inicio, fecha_fin) del ciclo de asistencia.
        Siempre es del 01 al último día del mes.
        """
        import calendar
        ultimo_dia = calendar.monthrange(anio, mes)[1]
        return datetime.date(anio, mes, 1), datetime.date(anio, mes, ultimo_dia)

    def es_regularizacion(self, fecha, anio_planilla, mes_planilla):
        """
        Retorna True si una fecha de descuento debe ir al mes siguiente
        (entre día corte+1 y fin de mes).
        """
        if not self.regularizacion_activa:
            return False
        import calendar
        ultimo_dia = calendar.monthrange(anio_planilla, mes_planilla)[1]
        inicio_regularizacion = datetime.date(anio_planilla, mes_planilla,
                                               self.dia_corte_planilla + 1)
        fin_mes = datetime.date(anio_planilla, mes_planilla, ultimo_dia)
        return inicio_regularizacion <= fecha <= fin_mes


# ─────────────────────────────────────────────────────────────
# SECCIÓN 7 ▸ GESTIÓN DE HE Y COMPENSACIONES
# ─────────────────────────────────────────────────────────────

class PapeletaCompensacion(models.Model):
    """
    Acuerdo formal (D.Leg. 713 Art. 6) entre empleador y trabajador:
    en vez de pagar HE 100% por feriado/DSO trabajado, se otorga
    un día compensatorio equivalente.

    Mientras la papeleta esté APROBADA o EJECUTADA:
    - fecha_trabajada → NO genera HE 100% (se trata como día normal)
    - fecha_compensacion → la ausencia ese día se anula (ya está compensada)
    """

    TIPO_CHOICES = [
        ('FERIADO', 'Feriado Trabajado'),
        ('DSO',     'Descanso Semanal Trabajado'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE',  'Pendiente de aprobación'),
        ('APROBADA',   'Aprobada'),
        ('RECHAZADA',  'Rechazada'),
        ('EJECUTADA',  'Ejecutada — compensación tomada'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='papeletas_compensacion',
        verbose_name='Trabajador')
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES,
                            verbose_name='Tipo')
    fecha_trabajada = models.DateField(
        verbose_name='Fecha Trabajada',
        help_text='Día feriado o DSO en que el trabajador laboró')
    fecha_compensacion = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha Compensación',
        help_text='Día libre que se otorga como compensación')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE',
        verbose_name='Estado')
    aprobado_por = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='papeletas_comp_aprobadas',
        verbose_name='Aprobado por')
    fecha_aprobacion = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de Aprobación')
    observaciones = models.TextField(blank=True, verbose_name='Observaciones')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Papeleta de Compensación'
        verbose_name_plural = 'Papeletas de Compensación'
        ordering = ['-fecha_trabajada']
        unique_together = [('personal', 'fecha_trabajada')]

    def __str__(self):
        return (f"{self.personal} — {self.get_tipo_display()} "
                f"{self.fecha_trabajada} [{self.get_estado_display()}]")


class SolicitudHE(models.Model):
    """
    Solicitud de autorización de Horas Extra (DL 728 + DS 007-2002-TR).

    Cuando ConfiguracionSistema.he_requiere_solicitud = True,
    el processor solo registra HE si existe una SolicitudHE APROBADA
    para (personal, fecha). Sin solicitud aprobada, el exceso de horas
    se ignora automáticamente.

    Las HE compensables van al BancoHoras pero siguen siendo una deuda
    del empleador: se pagan en liquidación si no se compensan antes.
    """

    TIPO_CHOICES = [
        ('PAGABLE',     'Pagable (planilla)'),
        ('COMPENSABLE', 'Compensable (banco de horas)'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE',  'Pendiente de aprobación'),
        ('APROBADA',   'Aprobada'),
        ('RECHAZADA',  'Rechazada'),
        ('ANULADA',    'Anulada'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='solicitudes_he',
        verbose_name='Trabajador')
    fecha = models.DateField(
        verbose_name='Fecha',
        help_text='Día en que se realizarán/realizaron las HE')
    horas_estimadas = models.DecimalField(
        max_digits=4, decimal_places=2, default=0,
        verbose_name='Horas Estimadas',
        help_text='Estimación de HE a trabajar ese día')
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES, default='PAGABLE',
        verbose_name='Tipo de HE')
    motivo = models.TextField(
        verbose_name='Motivo / Justificación')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE',
        verbose_name='Estado')
    aprobado_por = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='solicitudes_he_aprobadas',
        verbose_name='Aprobado por')
    fecha_aprobacion = models.DateField(null=True, blank=True,
                                        verbose_name='Fecha Aprobación')
    observaciones = models.TextField(blank=True,
                                     verbose_name='Observaciones del aprobador')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Solicitud de Horas Extra'
        verbose_name_plural = 'Solicitudes de Horas Extra'
        ordering = ['-fecha', '-creado_en']
        unique_together = [('personal', 'fecha')]

    def __str__(self):
        return (f"{self.personal} — {self.fecha} "
                f"{self.horas_estimadas}h [{self.get_estado_display()}]")


class JustificacionNoMarcaje(models.Model):
    """
    Justificación enviada por el trabajador desde el portal cuando no registró
    su asistencia (tardanza, falta justificada, trabajo remoto, etc.).
    RR.HH. revisa y aprueba o rechaza.
    """
    TIPO_CHOICES = [
        ('TARDANZA',         'Tardanza justificada'),
        ('FALTA_JUSTIFICADA','Falta justificada'),
        ('TRABAJO_REMOTO',   'Trabajo remoto / Teletrabajo'),
        ('SALIDA_TEMPRANA',  'Salida temprana autorizada'),
        ('COMISION',         'Comisión de servicios / Viaje'),
        ('CAPACITACION',     'Capacitación externa'),
        ('MEDICO',           'Cita médica / EPS'),
        ('OTRO',             'Otro'),
    ]
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente de revisión'),
        ('APROBADA',  'Aprobada'),
        ('RECHAZADA', 'Rechazada'),
    ]

    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='justificaciones_marcaje',
        verbose_name='Trabajador')
    fecha = models.DateField(verbose_name='Fecha justificada')
    tipo = models.CharField(max_length=25, choices=TIPO_CHOICES, verbose_name='Tipo')
    motivo = models.TextField(verbose_name='Motivo / Detalle')
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='PENDIENTE',
        verbose_name='Estado')
    revisado_por = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='justificaciones_revisadas',
        verbose_name='Revisado por')
    fecha_revision = models.DateField(null=True, blank=True,
                                       verbose_name='Fecha revisión')
    comentario_revisor = models.TextField(blank=True,
                                          verbose_name='Comentario del revisor')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Justificación de No-Marcaje'
        verbose_name_plural = 'Justificaciones de No-Marcaje'
        ordering = ['-fecha', '-creado_en']
        unique_together = [('personal', 'fecha')]

    def __str__(self):
        return (f"{self.personal} — {self.fecha} "
                f"[{self.get_tipo_display()}] [{self.get_estado_display()}]")


class ConceptoMapeoS10(models.Model):
    """
    Mapeo entre código interno de tareo y columna/concepto del archivo CargaS10.

    Permite configurar qué conceptos de S10 se generan automáticamente
    a partir de los registros de tareo. Cada código tareo puede mapear
    a un nombre de columna específico del CargaS10.
    """

    TIPO_VALOR = [
        ('HORAS', 'Horas (decimal)'),
        ('DIAS', 'Días (entero)'),
        ('MONTO', 'Monto S/ (decimal)'),
    ]

    codigo_tareo = models.CharField(
        max_length=20,
        verbose_name="Código Tareo",
        help_text="Ej: HE25, HE35, HE100, DM, LF, LSG, FA, VAC")
    nombre_concepto_s10 = models.CharField(
        max_length=150,
        verbose_name="Nombre Concepto S10",
        help_text="Nombre exacto de la columna en el archivo CargaS10")
    tipo_valor = models.CharField(
        max_length=10, choices=TIPO_VALOR, default='HORAS',
        verbose_name="Tipo de Valor")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    descripcion = models.CharField(max_length=200, blank=True,
                                    verbose_name="Descripción")

    class Meta:
        verbose_name = "Mapeo Concepto S10"
        verbose_name_plural = "Mapeos de Conceptos S10"
        ordering = ['codigo_tareo']
        unique_together = ['codigo_tareo', 'nombre_concepto_s10']

    def __str__(self):
        return f"{self.codigo_tareo} → {self.nombre_concepto_s10} ({self.tipo_valor})"


# ─────────────────────────────────────────────────────────────
# SECCIÓN 10 ▸ RELOJES BIOMÉTRICOS ZKTECO
# ─────────────────────────────────────────────────────────────

class RelojBiometrico(models.Model):
    """
    Configuración de un reloj biométrico ZKTeco (o compatible ZK).

    Permite conexión directa via protocolo ZK (TCP/UDP, puerto 4370 por defecto).
    Soporta huellas dactilares, reconocimiento facial y lectores de tarjeta RFID.

    Marcas compatibles: ZKTeco, Anviz, FingerTec, Nitgen, Hikvision (protocolo ZK).

    Para conectar: el dispositivo y el servidor Harmoni deben estar en la misma LAN
    o conectados via VPN. Puerto 4370 debe estar habilitado en el firewall.
    """

    PROTOCOLO_CHOICES = [
        ('TCP', 'TCP — Recomendado (dispositivos ZKTeco 2015+)'),
        ('UDP', 'UDP — Dispositivos antiguos / firmware legacy'),
    ]

    CAMPO_ID_CHOICES = [
        ('USER_ID', 'User ID del dispositivo (igual al DNI del empleado)'),
        ('CARD', 'Número de tarjeta / badge registrado'),
    ]

    ESTADO_CHOICES = [
        ('SIN_VERIFICAR', 'Sin verificar'),
        ('CONECTADO', '✓ Conectado'),
        ('DESCONECTADO', '✗ Desconectado'),
        ('ERROR', '⚠ Error de comunicación'),
    ]

    # ── Identificación ──────────────────────────────────────
    nombre = models.CharField(
        max_length=100, verbose_name='Nombre del dispositivo',
        help_text='Ej: Reloj Planta Principal, Control Acceso Lima')
    ubicacion = models.CharField(
        max_length=200, blank=True, verbose_name='Ubicación física',
        help_text='Ej: Planta Arequipa — Control de acceso principal')
    descripcion = models.TextField(
        blank=True, verbose_name='Notas / descripción')

    # ── Conexión ─────────────────────────────────────────────
    ip = models.GenericIPAddressField(
        protocol='IPv4', verbose_name='Dirección IP',
        help_text='IP del dispositivo en la red local. Ej: 192.168.1.100')
    puerto = models.PositiveIntegerField(
        default=4370, verbose_name='Puerto TCP/UDP',
        help_text='Puerto ZK. Estándar: 4370. No cambiar sin acceso al firmware.')
    timeout = models.PositiveSmallIntegerField(
        default=10, verbose_name='Timeout (segundos)',
        help_text='Tiempo máximo de espera para conectar al dispositivo')
    protocolo = models.CharField(
        max_length=5, choices=PROTOCOLO_CHOICES, default='TCP',
        verbose_name='Protocolo')

    # ── Mapeo de empleados ───────────────────────────────────
    campo_id_empleado = models.CharField(
        max_length=20, choices=CAMPO_ID_CHOICES, default='USER_ID',
        verbose_name='Campo para identificar empleado',
        help_text='Cómo se almacena el DNI en el dispositivo')

    # ── Estado ───────────────────────────────────────────────
    activo = models.BooleanField(
        default=True, verbose_name='Activo',
        help_text='Los relojes inactivos no se sincronizan en procesos automáticos')
    estado_conexion = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default='SIN_VERIFICAR',
        verbose_name='Estado de conexión')

    # ── Info del dispositivo (se rellena al conectar) ────────
    numero_serie = models.CharField(
        max_length=50, blank=True, verbose_name='Número de serie')
    modelo_dispositivo = models.CharField(
        max_length=100, blank=True, verbose_name='Modelo / Firmware')

    # ── Control de sincronización ────────────────────────────
    ultima_sincronizacion = models.DateTimeField(
        null=True, blank=True, verbose_name='Última sincronización')
    ultima_verificacion = models.DateTimeField(
        null=True, blank=True, verbose_name='Última verificación de conexión')

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Reloj Biométrico'
        verbose_name_plural = 'Relojes Biométricos'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.ip}:{self.puerto})'

    @property
    def esta_conectado(self):
        return self.estado_conexion == 'CONECTADO'

    @property
    def total_marcaciones(self):
        return self.marcaciones.count()


class MarcacionBiometrica(models.Model):
    """
    Marcación raw capturada directamente desde un reloj biométrico ZKTeco.

    Un empleado puede tener múltiples marcaciones por día (entrada, salida,
    descanso, etc.). La vista de tareo agrupa por (user_id, fecha) para
    determinar la jornada: primera ENTRADA y última SALIDA.

    Se usa unique_together para evitar duplicados en re-sincronizaciones.
    """

    TIPO_MARCACION_CHOICES = [
        ('ENTRADA', 'Entrada / Check-in'),
        ('SALIDA', 'Salida / Check-out'),
        ('DESCANSO_SALIDA', 'Salida de descanso'),
        ('DESCANSO_REGRESO', 'Regreso de descanso'),
        ('HE_SALIDA', 'Salida por horas extra'),
        ('OTRO', 'Otro / Desconocido'),
    ]

    reloj = models.ForeignKey(
        RelojBiometrico, on_delete=models.CASCADE,
        related_name='marcaciones', verbose_name='Reloj')

    # ID del empleado según el dispositivo (puede ser DNI u otro código)
    user_id_dispositivo = models.CharField(
        max_length=20, verbose_name='ID en dispositivo',
        help_text='Valor del user_id registrado en el ZKTeco')

    # Enlace a Personal (null si no se encontró match)
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='marcaciones_biometricas',
        verbose_name='Personal')

    # Fecha y hora exacta de la marcación
    timestamp = models.DateTimeField(verbose_name='Fecha / Hora de marcación')

    # Tipo de punch
    tipo_marcacion = models.CharField(
        max_length=20, choices=TIPO_MARCACION_CHOICES,
        default='ENTRADA', verbose_name='Tipo de marcación')
    punch_raw = models.SmallIntegerField(
        default=0, verbose_name='Código punch (raw)',
        help_text='Valor original del ZKTeco: 0=entrada, 1=salida, 4=HE salida…')

    # Control de procesamiento → RegistroTareo
    procesado = models.BooleanField(
        default=False, verbose_name='Procesado',
        help_text='True cuando ya fue incluido en una importación de tareo')
    importacion = models.ForeignKey(
        'tareo.TareoImportacion', on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='marcaciones_biometricas',
        verbose_name='Importación de tareo generada')

    class Meta:
        verbose_name = 'Marcación Biométrica'
        verbose_name_plural = 'Marcaciones Biométricas'
        ordering = ['timestamp']
        unique_together = [['reloj', 'user_id_dispositivo', 'timestamp']]
        indexes = [
            models.Index(fields=['reloj', 'timestamp']),
            models.Index(fields=['personal', 'timestamp']),
            models.Index(fields=['procesado', 'timestamp']),
        ]

    def __str__(self):
        ts = self.timestamp.strftime('%d/%m/%Y %H:%M')
        return (f'[{self.reloj.nombre}] {self.user_id_dispositivo} — '
                f'{ts} [{self.get_tipo_marcacion_display()}]')

    @property
    def fecha(self):
        return self.timestamp.date()

    @property
    def hora(self):
        return self.timestamp.time()


class CambioCodigoLog(models.Model):
    """Audit log para cambios manuales de codigo_dia desde el calendario."""
    registro = models.ForeignKey(RegistroTareo, on_delete=models.CASCADE, related_name='cambios_log')
    codigo_anterior = models.CharField(max_length=20)
    codigo_nuevo = models.CharField(max_length=20)
    observacion = models.TextField(blank=True)
    sustento = models.FileField(upload_to='asistencia/sustentos/%Y/%m/', blank=True, null=True)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']
        verbose_name = 'Cambio de Código'
        verbose_name_plural = 'Cambios de Código'

    def __str__(self):
        return f'{self.registro.dni} {self.registro.fecha}: {self.codigo_anterior} → {self.codigo_nuevo}'


# ═══════════════════════════════════════════════════════════
#  REGLAS ESPECIALES POR EMPLEADO
# ═══════════════════════════════════════════════════════════

DIAS_SEMANA_CHOICES = [
    (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'),
    (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
]


class ReglaEspecialPersonal(models.Model):
    """
    Regla de excepción recurrente para un empleado específico.

    Se evalúa en el processor entre Papeleta (prioridad 1) y Feriado (prioridad 2).
    Ejemplo: "Palma Barrera, sábados siempre = DL por régimen 21×7".

    Todas las condiciones deben cumplirse para que la regla aplique (AND lógico).
    Si un campo de condición es null/vacío, se ignora (= acepta cualquier valor).
    """
    # ── A quién aplica ───────────────────────────────
    personal = models.ForeignKey(
        'personal.Personal', on_delete=models.CASCADE,
        related_name='reglas_asistencia',
        verbose_name='Empleado')

    # ── Condiciones (cuándo aplica) ──────────────────
    dias_semana = models.JSONField(
        default=list, blank=True,
        verbose_name='Días de la semana',
        help_text='Lista de enteros: 0=Lun..6=Dom. Vacío = todos los días.')
    condicion_laboral = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Condición laboral',
        help_text='LOCAL, FORÁNEO, LIMA. Vacío = cualquiera.')
    codigo_reloj_trigger = models.CharField(
        max_length=20, blank=True, default='',
        verbose_name='Código reloj trigger',
        help_text='Solo aplica si el reloj muestra este código. Vacío = cualquiera.')
    solo_feriados = models.BooleanField(
        default=False,
        verbose_name='Solo en feriados',
        help_text='Si True, solo aplica cuando el día es feriado.')

    # ── Vigencia ─────────────────────────────────────
    fecha_desde = models.DateField(
        verbose_name='Vigente desde')
    fecha_hasta = models.DateField(
        null=True, blank=True,
        verbose_name='Vigente hasta',
        help_text='Dejar vacío = vigencia indefinida.')

    # ── Resultado ────────────────────────────────────
    codigo_resultado = models.CharField(
        max_length=10,
        verbose_name='Código resultante',
        help_text='Código de asistencia a aplicar: DL, FA, DS, T, VAC, etc.')
    horas_override = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name='Horas override',
        help_text='Si se especifica, overridea las horas calculadas.')

    # ── Metadata ─────────────────────────────────────
    descripcion = models.CharField(
        max_length=300,
        verbose_name='Descripción',
        help_text='Descripción corta para la tabla.')
    descripcion_natural = models.TextField(
        blank=True, default='',
        verbose_name='Descripción original',
        help_text='Texto original que el usuario escribió en el chat IA.')
    conversacion_ia = models.JSONField(
        default=list, blank=True,
        verbose_name='Conversación IA',
        help_text='Historial del chat que generó esta regla (auditoría).')
    prioridad = models.PositiveSmallIntegerField(
        default=10,
        verbose_name='Prioridad',
        help_text='Menor número = mayor prioridad. Primera regla que matchea gana.')
    activa = models.BooleanField(
        default=True,
        verbose_name='Activa')
    aplicar_retroactivamente = models.BooleanField(
        default=False,
        verbose_name='Aplicar retroactivamente',
        help_text='Si True, al guardar se recalculan registros pasados.')

    # ── Auditoría ────────────────────────────────────
    creado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='reglas_asistencia_creadas',
        verbose_name='Creado por')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tareo'
        ordering = ['personal', 'prioridad']
        verbose_name = 'Regla Especial de Asistencia'
        verbose_name_plural = 'Reglas Especiales de Asistencia'

    def __str__(self):
        dias_str = ', '.join(
            dict(DIAS_SEMANA_CHOICES).get(d, '?') for d in (self.dias_semana or [])
        ) or 'Todos'
        return f'{self.personal} → {self.codigo_resultado} ({dias_str})'

    def aplica_a(self, fecha, dia_semana: int, condicion: str,
                 codigo_reloj: str, es_feriado: bool) -> bool:
        """Evalúa si esta regla aplica al registro dado (AND lógico)."""
        if not self.activa:
            return False
        if self.fecha_desde and fecha < self.fecha_desde:
            return False
        if self.fecha_hasta and fecha > self.fecha_hasta:
            return False
        if self.dias_semana and dia_semana not in self.dias_semana:
            return False
        if self.condicion_laboral:
            cond_norm = (condicion or '').upper().replace('\xc1', 'A')
            regla_norm = self.condicion_laboral.upper().replace('\xc1', 'A')
            if cond_norm != regla_norm:
                return False
        if self.codigo_reloj_trigger:
            if (codigo_reloj or '').upper().strip() != self.codigo_reloj_trigger.upper().strip():
                return False
        if self.solo_feriados and not es_feriado:
            return False
        return True


# ═══════════════════════════════════════════════════════════════════
#  BRIEFING DEL DÍA — Pre-shift handover (gastronomía premium)
# ═══════════════════════════════════════════════════════════════════

class BriefingServicio(models.Model):
    """Briefing publicado por el jefe de local antes del servicio.

    Patrón de brigade kitchen (Escoffier): 15-30 min antes del servicio,
    el jefe comunica a la brigada lo crítico del día — covers esperados,
    VIPs/alergias, especiales del chef, items 86'd (sin stock), notas
    operativas, dress code.

    Los trabajadores asignados al turno reciben push notification + lo
    ven en su portal del trabajador al hacer login.

    Trail auditable: queda registro firmado de qué se comunicó y a quién.
    """
    SERVICIO_CHOICES = [
        ('DESAYUNO',  'Desayuno'),
        ('ALMUERZO',  'Almuerzo'),
        ('CENA',      'Cena'),
        ('CONTINUO',  'Servicio continuo'),
        ('EVENTO',    'Evento especial'),
    ]
    ESTADO_CHOICES = [
        ('BORRADOR',  'Borrador'),
        ('PUBLICADO', 'Publicado'),
        ('CERRADO',   'Cerrado'),
    ]

    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.CASCADE,
        related_name='briefings',
        help_text='Local / RUC al que corresponde el briefing.',
    )
    fecha = models.DateField(
        verbose_name='Fecha del servicio',
        db_index=True,
    )
    servicio = models.CharField(
        max_length=12, choices=SERVICIO_CHOICES, default='ALMUERZO',
    )
    estado = models.CharField(
        max_length=10, choices=ESTADO_CHOICES, default='BORRADOR',
    )

    covers_esperados = models.IntegerField(
        default=0,
        verbose_name='Covers esperados',
        help_text='Reservaciones confirmadas + walk-ins estimados.',
    )
    notas_chef = models.TextField(
        blank=True,
        verbose_name='Notas del Chef',
        help_text='Mensaje del chef ejecutivo a la brigada.',
    )
    especiales = models.TextField(
        blank=True,
        verbose_name='Platos especiales del día',
        help_text='Sugerencias del día / off-menu. Uno por línea.',
    )
    items_86 = models.TextField(
        blank=True,
        verbose_name='Items 86\'d (sin stock)',
        help_text='Platos NO disponibles. Crítico comunicar al salón.',
    )
    vips_alergias = models.TextField(
        blank=True,
        verbose_name='VIPs / Alergias / Cumpleaños',
        help_text='Mesas con atención especial. Ej: Mesa 4: alergia gluten severa.',
    )
    dress_code = models.CharField(
        max_length=100, blank=True,
        verbose_name='Dress code',
        help_text='Uniforme del día. Ej: Protocolo formal, evento blanco, etc.',
    )
    notas_operativas = models.TextField(
        blank=True,
        verbose_name='Notas operativas',
        help_text='Otros: corte de servicio, prueba de menú, visita inspección, etc.',
    )

    publicado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='briefings_publicados',
    )
    publicado_en = models.DateTimeField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'tareo'
        verbose_name = 'Briefing del Día'
        verbose_name_plural = 'Briefings del Día'
        ordering = ['-fecha', 'servicio']
        unique_together = [('empresa', 'fecha', 'servicio')]
        indexes = [
            models.Index(fields=['fecha', 'estado'], name='brf_fecha_estado_idx'),
        ]

    def __str__(self):
        return f'{self.empresa} · {self.fecha} · {self.get_servicio_display()}'

    @property
    def is_publicado(self):
        return self.estado == 'PUBLICADO'

    def publicar(self, user):
        from django.utils import timezone
        self.estado = 'PUBLICADO'
        self.publicado_por = user
        self.publicado_en = timezone.now()
        self.save(update_fields=['estado', 'publicado_por', 'publicado_en', 'actualizado_en'])
        # Crear notificaciones in-app para los trabajadores del local
        self._crear_notificaciones_trabajadores()

    def _crear_notificaciones_trabajadores(self):
        """Crea Notificacion in-app por cada trabajador activo del local."""
        try:
            from comunicaciones.models import Notificacion
            from personal.models import Personal
            workers = Personal.objects.filter(
                empresa=self.empresa, estado='Activo',
            )
            asunto = (
                f"Briefing del Día — {self.get_servicio_display()} "
                f"({self.fecha.strftime('%d/%m')})"
            )
            covers = (f"<p><strong>{self.covers_esperados} covers esperados.</strong></p>"
                      if self.covers_esperados else "")
            cuerpo = (
                f"<p>El jefe de local publicó el briefing del {self.get_servicio_display().lower()}.</p>"
                f"{covers}"
                f"<p><a href='/mi-portal/'>Ver briefing en mi portal</a></p>"
            )
            created = 0
            for w in workers:
                # Una sola notif por (briefing, trabajador): usar metadata para idempotencia
                if Notificacion.objects.filter(
                    destinatario=w,
                    metadata__briefing_id=self.pk,
                ).exists():
                    continue
                Notificacion.objects.create(
                    destinatario=w,
                    asunto=asunto,
                    cuerpo=cuerpo,
                    tipo='IN_APP',
                    estado='ENVIADA',
                    metadata={
                        'briefing_id': self.pk,
                        'empresa_id':  self.empresa_id,
                        'fecha':       self.fecha.isoformat(),
                        'servicio':    self.servicio,
                    },
                )
                created += 1
            return created
        except Exception as e:
            import logging
            logging.getLogger('briefing').warning(
                'Error creando notif briefing %s: %s', self.pk, e
            )
            return 0


class BriefingLectura(models.Model):
    """Registro de cuándo un trabajador leyó el briefing.

    Útil para compliance: el jefe puede ver quién no leyó aún el briefing
    antes del servicio y mandarles recordatorio.
    """
    briefing = models.ForeignKey(
        BriefingServicio,
        on_delete=models.CASCADE,
        related_name='lecturas',
    )
    personal = models.ForeignKey(
        'personal.Personal',
        on_delete=models.CASCADE,
        related_name='briefings_leidos',
    )
    leido_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'tareo'
        verbose_name = 'Lectura de Briefing'
        verbose_name_plural = 'Lecturas de Briefings'
        unique_together = [('briefing', 'personal')]
        indexes = [
            models.Index(fields=['briefing', 'leido_en'], name='brfl_brf_fecha_idx'),
        ]

    def __str__(self):
        return f'{self.personal} leyó {self.briefing} en {self.leido_en}'
