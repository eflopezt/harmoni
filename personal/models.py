"""
Modelos de datos para el sistema de gestión de personal.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils.functional import cached_property
from decimal import Decimal


class Area(models.Model):
    """
    Áreas o departamentos de alto nivel.
    Cada área puede tener uno o varios responsables y un jefe principal.
    """
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre de Área")
    codigo = models.CharField(
        max_length=20, blank=True, verbose_name="Código / Centro de Costo",
        help_text="Código interno o de centro de costo (ej: ADM, OPS-01, GG)"
    )
    jefe_area = models.ForeignKey(
        'Personal',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='area_jefatura',
        verbose_name="Jefe de Área",
        help_text="Responsable principal del área (jefe inmediato SUNAT)"
    )
    responsables = models.ManyToManyField(
        'Personal',
        blank=True,
        related_name='areas_responsable',
        verbose_name="Responsables adicionales",
        help_text="Personas con acceso de gestión al área (además del jefe)"
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")

    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Área"
        verbose_name_plural = "Áreas"
        ordering = ['nombre']
        indexes = [
            models.Index(fields=['nombre']),
            models.Index(fields=['activa']),
        ]

    def __str__(self):
        return self.nombre

    @property
    def display_nombre(self):
        """Muestra código + nombre si el código existe."""
        if self.codigo:
            return f"[{self.codigo}] {self.nombre}"
        return self.nombre

    def clean(self):
        """Validación del modelo usando validadores centralizados."""
        super().clean()


class SubArea(models.Model):
    """
    SubÁreas de trabajo bajo un área.
    """
    nombre = models.CharField(max_length=150, verbose_name="Nombre de SubÁrea")
    area = models.ForeignKey(
        Area,
        on_delete=models.CASCADE,
        related_name='subareas',
        verbose_name="Área"
    )
    descripcion = models.TextField(blank=True, verbose_name="Descripción")
    activa = models.BooleanField(default=True, verbose_name="Activa")
    
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "SubÁrea"
        verbose_name_plural = "SubÁreas"
        ordering = ['area', 'nombre']
        unique_together = ['nombre', 'area']
        indexes = [
            models.Index(fields=['area', 'activa']),
            models.Index(fields=['nombre']),
        ]
    
    def __str__(self):
        return f"{self.area.nombre} - {self.nombre}"


class Cargo(models.Model):
    """
    Cargos/puestos de trabajo normalizados.
    Sirve para: organigrama, funciones en contratos, clasificación confianza/fiscalizable.
    """
    NIVEL_CHOICES = [
        (1, 'Alta Dirección'),
        (2, 'Gerencia'),
        (3, 'Jefatura / Coordinación'),
        (4, 'Especialista / Profesional'),
        (5, 'Técnico / Asistente'),
        (6, 'Operativo'),
    ]
    nombre = models.CharField(
        max_length=150, unique=True,
        verbose_name='Nombre del Cargo',
    )
    descripcion = models.TextField(
        blank=True,
        verbose_name='Descripción',
    )
    nivel = models.PositiveSmallIntegerField(
        choices=NIVEL_CHOICES, default=5,
        verbose_name='Nivel jerárquico',
        help_text='1=Alta Dirección, 2=Gerencia, 3=Jefatura, 4=Especialista, 5=Técnico, 6=Operativo',
    )
    funciones = models.TextField(
        blank=True,
        verbose_name='Funciones del cargo',
        help_text='Lista de funciones para insertar en contratos laborales. Una función por línea.',
    )
    es_confianza = models.BooleanField(
        default=False,
        verbose_name='Personal de confianza',
        help_text='Art. 43 DL 728. No sujeto a fiscalización de jornada. Período de prueba 6 meses.',
    )
    es_fiscalizable = models.BooleanField(
        default=True,
        verbose_name='Sujeto a fiscalización',
        help_text='Sujeto a control de asistencia y jornada laboral (48h semanales).',
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cargo'
        verbose_name_plural = 'Cargos'
        ordering = ['nivel', 'nombre']
        indexes = [
            models.Index(fields=['nivel', 'nombre']),
            models.Index(fields=['activo']),
            models.Index(fields=['es_confianza']),
        ]

    def __str__(self):
        return self.nombre

    @property
    def funciones_lista(self):
        """Retorna las funciones como lista (para iterar en templates/contratos)."""
        if not self.funciones:
            return []
        return [f.strip() for f in self.funciones.strip().split('\n') if f.strip()]


class Personal(models.Model):
    """
    Personal disponible - tabla principal del sistema.
    Todo el personal activo figura aquí.
    """
    
    # Opciones para campos
    TIPO_DOC_CHOICES = [
        ('DNI', 'DNI'),
        ('CE', 'Carné de Extranjería'),
        ('Pasaporte', 'Pasaporte'),
    ]
    
    TIPO_TRAB_CHOICES = [
        ('Empleado', 'Empleado'),
        ('Obrero', 'Obrero'),
    ]
    
    SEXO_CHOICES = [
        ('M', 'Masculino'),
        ('F', 'Femenino'),
    ]
    
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
        ('Suspendido', 'Suspendido'),
        ('Cesado', 'Cesado'),
    ]

    MOTIVO_CESE_CHOICES = [
        # Voluntarios
        ('RENUNCIA',        'Renuncia voluntaria'),
        ('MUTUO_ACUERDO',   'Mutuo acuerdo'),
        ('JUBILACION',      'Jubilacion'),
        # Por el empleador (DS 003-97-TR)
        ('VENCIMIENTO',     'Vencimiento de contrato'),
        ('TERMINO_CONTRATO', 'Termino de contrato'),
        ('NO_RENOVACION',   'No renovacion'),
        ('DESPIDO_CAUSA',   'Despido con causa justificada'),
        ('CESE_COLECTIVO',  'Cese colectivo'),
        ('LIQUIDACION',     'Liquidacion / Disolucion empresa'),
        # Especiales
        ('FALLECIMIENTO',   'Fallecimiento'),
        ('INVALIDEZ',       'Invalidez permanente'),
        ('ABANDONO',        'Abandono de trabajo'),
        ('OTRO',            'Otro'),
    ]

    AFP_CHOICES = [
        ('Habitat', 'Habitat'),
        ('Integra', 'Integra'),
        ('Prima', 'Prima'),
        ('Profuturo', 'Profuturo'),
    ]
    
    BANCO_CHOICES = [
        ('BCP', 'BCP'),
        ('BBVA', 'BBVA'),
        ('Scotiabank', 'Scotiabank'),
        ('Interbank', 'Interbank'),
        ('Banco de la Nación', 'Banco de la Nación'),
        ('Falabella', 'Falabella'),
    ]
    
    # --- Multi-empresa ---
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='personal',
        verbose_name='Empresa',
        db_index=True,
    )

    # --- Vinculación con usuario del sistema ---
    usuario = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="personal_data",
        verbose_name="Usuario del Sistema",
        help_text="Cuenta de acceso si aplica"
    )
    
    # --- Datos de identificación ---
    tipo_doc = models.CharField(
        max_length=20,
        choices=TIPO_DOC_CHOICES,
        default='DNI',
        verbose_name="Tipo de Documento"
    )
    nro_doc = models.CharField(
        max_length=20,
        unique=True,
        verbose_name="Número de Documento"
    )
    apellidos_nombres = models.CharField(
        max_length=250,
        verbose_name="Apellidos y Nombres"
    )
    codigo_fotocheck = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Código Fotocheck",
        help_text="Código de barras del fotocheck"
    )
    
    # --- Datos laborales ---
    cargo = models.CharField(max_length=150, verbose_name="Cargo")
    cargo_obj = models.ForeignKey(
        'Cargo',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='personal_asignado',
        verbose_name='Cargo (normalizado)',
        help_text='Cargo del catálogo. Usado para funciones en contratos y organigrama.',
    )
    tipo_trab = models.CharField(
        max_length=20,
        choices=TIPO_TRAB_CHOICES,
        verbose_name="Tipo de Trabajador"
    )
    CATEGORIA_CHOICES = [
        ('NORMAL', 'Normal'),
        ('CONFIANZA', 'Personal de Confianza'),
        ('DIRECCION', 'Personal de Dirección'),
    ]
    categoria = models.CharField(
        max_length=12,
        choices=CATEGORIA_CHOICES,
        default='NORMAL',
        verbose_name="Categoría",
        help_text="Confianza/Dirección: excluidos de jornada máxima (D.Leg. 854 art.5). Sin HE ni control de faltas."
    )
    REGIMEN_PENSION_CHOICES = [
        ('AFP', 'AFP'),
        ('ONP', 'ONP'),
        ('SIN_PENSION', 'Sin Régimen'),
    ]
    regimen_pension = models.CharField(
        max_length=12,
        choices=REGIMEN_PENSION_CHOICES,
        default='AFP',
        verbose_name="Régimen Pensionario"
    )
    cuspp = models.CharField(
        max_length=20,
        blank=True,
        verbose_name="CUSPP",
        help_text="Código Único del SPP (solo AFP)"
    )
    asignacion_familiar = models.BooleanField(
        default=False,
        verbose_name="Asignación Familiar",
        help_text="Percibe 10% RMV por hijo(s) menor(es)"
    )
    subarea = models.ForeignKey(
        SubArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_asignado',
        verbose_name="SubÁrea Asignada"
    )
    reporta_a = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinados',
        verbose_name="Reporta a",
        help_text="Superior directo en el organigrama"
    )
    fecha_alta = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Alta"
    )
    fecha_cese = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Cese"
    )
    motivo_cese = models.CharField(
        max_length=20,
        choices=MOTIVO_CESE_CHOICES,
        blank=True,
        verbose_name="Motivo de Cese",
        help_text="Causa del cese laboral (DS 003-97-TR). Requerido al cesar al trabajador.",
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='Activo',
        verbose_name="Estado"
    )

    # --- Datos personales ---
    fecha_nacimiento = models.DateField(
        null=True,
        blank=True,
        verbose_name="Fecha de Nacimiento"
    )
    sexo = models.CharField(
        max_length=1,
        choices=SEXO_CHOICES,
        blank=True,
        verbose_name="Sexo"
    )
    celular = models.CharField(max_length=20, blank=True, verbose_name="Celular")
    correo_personal = models.EmailField(blank=True, verbose_name="Correo Personal")
    correo_corporativo = models.EmailField(blank=True, verbose_name="Correo Corporativo")
    direccion = models.CharField(max_length=300, blank=True, verbose_name="Dirección")
    ubigeo = models.CharField(max_length=100, blank=True, verbose_name="Ubigeo")
    
    # --- Datos financieros ---
    afp = models.CharField(
        max_length=20,
        choices=AFP_CHOICES,
        blank=True,
        verbose_name="AFP"
    )
    banco = models.CharField(
        max_length=30,
        choices=BANCO_CHOICES,
        blank=True,
        verbose_name="Banco"
    )
    cuenta_ahorros = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Cuenta de Ahorros"
    )
    cuenta_cci = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Cuenta CCI"
    )
    cuenta_cts = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Cuenta CTS"
    )

    # --- Pago por billetera digital (Ley 32413 + D.S. 011-2026-EF) ---
    # El pago de haberes/CTS/gratificaciones por billetera (Yape, Plin, etc.)
    # es legal SOLO con acuerdo previo del trabajador; el empleador no puede
    # imponerlo. Sin acuerdo, el pago sigue por cuenta bancaria.
    MEDIO_PAGO_CHOICES = [
        ('CUENTA',    'Cuenta bancaria'),
        ('BILLETERA', 'Billetera digital'),
    ]
    BILLETERA_CHOICES = [
        ('YAPE',    'Yape'),
        ('PLIN',    'Plin'),
        ('LIGO',    'Ligo'),
        ('KONTIGO', 'Kontigo'),
        ('OTRA',    'Otra billetera'),
    ]
    medio_pago_haberes = models.CharField(
        max_length=10,
        choices=MEDIO_PAGO_CHOICES,
        default='CUENTA',
        verbose_name="Medio de pago de haberes",
    )
    billetera_tipo = models.CharField(
        max_length=10,
        choices=BILLETERA_CHOICES,
        blank=True,
        verbose_name="Billetera digital",
    )
    billetera_celular = models.CharField(
        max_length=9,
        blank=True,
        verbose_name="Celular de la billetera",
        help_text="9 dígitos, empieza en 9",
    )
    billetera_acuerdo = models.BooleanField(
        default=False,
        verbose_name="Acuerdo del trabajador (Ley 32413)",
        help_text="El pago por billetera requiere acuerdo previo del trabajador; "
                  "el empleador no puede imponerlo.",
    )

    # --- Datos económicos ---
    sueldo_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Sueldo Base"
    )
    bonos = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Bonos"
    )
    # EPS — Entidad Prestadora de Salud (alternativa a EsSalud)
    tiene_eps = models.BooleanField(
        default=False,
        verbose_name="Tiene EPS",
        help_text=(
            "El empleador contrata EPS para este trabajador en lugar de EsSalud. "
            "Si el trabajador paga un co-seguro, registrar el monto mensual abajo."
        )
    )
    eps_descuento_mensual = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Aporte EPS trabajador (mensual)",
        help_text=(
            "Co-pago mensual del trabajador a la EPS. Deducible de la base de IR 5ta "
            "(Art. 46° TUO LIR). Cero si el empleador asume el 100% de la prima."
        )
    )
    # SCTR — actividad de alto riesgo (Anexo 5 DS 009-97-SA). Solo a estos
    # trabajadores se les calcula el aporte SCTR Salud/Pensión del empleador.
    afecto_sctr = models.BooleanField(
        default=False,
        verbose_name="Afecto SCTR (actividad de riesgo)",
        help_text=(
            "Marca a los trabajadores en actividades de alto riesgo (construcción, "
            "minería, etc., Anexo 5 DS 009-97-SA). El empleador aporta SCTR Salud y "
            "Pensión solo por ellos. El personal administrativo NO debe marcarse."
        )
    )
    # Viáticos fijos — monto mensual no remunerativo (excluido de IR 5ta)
    viaticos_mensual = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Viáticos fijos mensuales",
        help_text=(
            "Asignación mensual fija de viáticos. No es remuneración (D.Leg. 728 Art. 19°) "
            "y NO forma parte de la base de IR 5ta. Solo para referencia y planilla."
        )
    )
    # Condición de Trabajo / Hospedaje — no remunerativo
    cond_trabajo_mensual = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Condición de Trabajo / Hospedaje (mensual)",
        help_text=(
            "Asignación mensual no remunerativa por condiciones de trabajo (hospedaje en "
            "proyecto/obra). No forma parte de la base remunerativa ni de IR 5ta. "
            "Se incluye en el flujo de caja de planilla."
        )
    )
    # Alimentación mensual — no remunerativa
    alimentacion_mensual = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name="Alimentación mensual",
        help_text=(
            "Asignación mensual de alimentación. No remunerativa (D.Leg. 728 Art. 19°). "
            "Se incluye en el flujo de caja de planilla."
        )
    )

    # --- Clasificación de tareo ---
    # Nota: el valor interno 'RCO' se conserva por compatibilidad de datos.
    # En UI el label visible es "Operativo" (aplica a gastronomía/servicios
    # tanto como a construcción civil).
    GRUPO_TAREO_CHOICES = [
        ('STAFF', 'Staff (HE compensatorias — banco de horas)'),
        ('RCO', 'Operativo (HE pagadas 25/35/100%)'),
        ('OTRO', 'Otro / No aplica'),
    ]
    CONDICION_CHOICES = [
        ('FORANEO', 'Foráneo (régimen acumulativo)'),
        ('LOCAL', 'Local (jornada fija en obra/sede)'),
        ('LIMA', 'Lima (jornada fija en oficina Lima)'),
    ]
    grupo_tareo = models.CharField(
        max_length=10,
        choices=GRUPO_TAREO_CHOICES,
        default='STAFF',
        verbose_name="Grupo Tareo",
        help_text="Determina cómo se tratan las HE: banco (Staff) o pago (Operativo)"
    )
    condicion = models.CharField(
        max_length=10,
        choices=CONDICION_CHOICES,
        blank=True,
        verbose_name="Condición",
        help_text="LOCAL = jornada fija | FORÁNEO = régimen acumulativo"
    )

    # ── Organigrama ──────────────────────────────────────────────────────────
    NIVEL_ORG_CHOICES = [
        ('GG',      'Gerente General'),
        ('CTA',     'Representante Cliente (CTA/KP)'),
        ('DIR',     'Director / Alta Gerencia'),
        ('GER',     'Gerente de Área'),
        ('JEFE_SR', 'Jefe Senior / Subgerente'),
        ('JEFE',    'Jefe / Coordinador / Responsable'),
        ('ESP',     'Especialista / Ingeniero / Analista'),
        ('ASIST',   'Asistente / Técnico / Auxiliar'),
        ('LIBERTY', 'Liberty (contrato especial)'),
        ('EXPAT',   'Expatriado'),
    ]
    nivel_org = models.CharField(
        max_length=10,
        choices=NIVEL_ORG_CHOICES,
        blank=True,
        default='',
        verbose_name="Nivel Organigrama",
        help_text="Color y jerarquía en el organigrama visual"
    )
    personal_clave = models.BooleanField(
        default=False,
        verbose_name="Personal Clave",
        help_text="Marcado con ícono 'C' en el organigrama"
    )
    # ─────────────────────────────────────────────────────────────────────────

    codigo_sap = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Código SAP",
        help_text="Código del trabajador en el sistema SAP"
    )
    codigo_s10 = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Código S10",
        help_text="Código del recurso en el sistema S10"
    )
    partida_control = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Partida de Control",
        help_text="Partida de costo para generación de CargaS10"
    )
    jornada_horas = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=8,
        verbose_name="Horas de Jornada Diaria",
        help_text="LOCAL=8.5, FORÁNEO=11.0. Usado para calcular HE."
    )

    # --- Régimen laboral ---
    # Códigos canónicos (alineados con importar_maestro_empleados y la
    # plantilla del maestro). El motor de planilla usa CONSTRUCCION y MINERIA
    # para estrategias de cálculo propias; el resto se calcula con el régimen
    # general. La normalización a estrategia vive en nominas/regimenes.py.
    REGIMEN_LABORAL_CHOICES = [
        ('GENERAL', 'Régimen General (D.Leg. 728)'),
        ('MICROEMPRESA', 'Microempresa (REMYPE)'),
        ('PEQUEÑA', 'Pequeña Empresa (REMYPE)'),
        ('AGRARIO', 'Agrario (Ley 31110)'),
        ('CONSTRUCCION', 'Construcción Civil (CAPECO-FTCCP)'),
        ('MINERIA', 'Minería (D.S. 030-89-TR)'),
    ]
    regimen_laboral = models.CharField(
        max_length=50,
        blank=True,
        choices=REGIMEN_LABORAL_CHOICES,
        default='GENERAL',
        verbose_name="Régimen Laboral",
        help_text="Determina la estrategia de cálculo de planilla "
                  "(CONSTRUCCION y MINERIA tienen reglas propias)."
    )
    regimen_turno = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Régimen de Turno",
        help_text="Ej: 14x7, 21x7, etc."
    )

    # ── Día de descanso semanal (gastronomía / oficina / comercio) ──
    # Para regímenes semanales con descanso rotativo (típico de gastronomía
    # y servicios) el día libre puede caer cualquier día de la semana
    # (no necesariamente domingo). Este campo permite registrar el día
    # específico de descanso de este trabajador.
    #
    # NULL/blank = no configurado → se asume domingo para LOCAL/LIMA
    # (compatibilidad con datos existentes).
    #
    # En regímenes acumulativos/foráneos (21×7, 14×7) NO aplica: el día
    # libre se determina por el ciclo del roster, no por la semana.
    DIA_DESCANSO_CHOICES = [
        ('', 'Domingo (por defecto)'),
        ('0', 'Lunes'),
        ('1', 'Martes'),
        ('2', 'Miércoles'),
        ('3', 'Jueves'),
        ('4', 'Viernes'),
        ('5', 'Sábado'),
        ('6', 'Domingo'),
    ]
    dia_descanso_semanal = models.CharField(
        max_length=2,
        choices=DIA_DESCANSO_CHOICES,
        blank=True,
        default='',
        verbose_name="Día de Descanso Semanal",
        help_text="Solo aplica a regímenes con descanso fijo (gastronomía 6×1, "
                  "oficina 5×2). En blanco = domingo. Para roster acumulativo "
                  "21×7/14×7 este campo no se usa."
    )

    # --- Contrato laboral (D.Leg. 728) ---
    TIPO_CONTRATO_CHOICES = [
        ('INDEFINIDO', 'Contrato Indefinido'),
        ('PLAZO_FIJO', 'Contrato a Plazo Fijo (Modal)'),
        ('INICIO_ACTIVIDAD', 'Inicio de Actividad'),
        ('NECESIDAD_MERCADO', 'Necesidad de Mercado'),
        ('RECONVERSION_EMPRESARIAL', 'Reconversión Empresarial'),
        ('OBRA_SERVICIO', 'Para Obra o Servicio'),
        ('DISCONTINUO', 'Intermitente / Discontinuo'),
        ('TEMPORADA', 'De Temporada'),
        ('SUPLENCIA', 'De Suplencia'),
        ('EMERGENCIA', 'Emergencia Accidental'),
        ('SNP', 'Locación de Servicios (SNP)'),
        ('PRACTICANTE', 'Practicante Pre/Profesional'),
        ('OTRO', 'Otro'),
    ]
    tipo_contrato = models.CharField(
        max_length=25,
        choices=TIPO_CONTRATO_CHOICES,
        blank=True,
        verbose_name="Modalidad de Contrato",
        help_text="Modalidad contractual según D.Leg. 728"
    )
    fecha_inicio_contrato = models.DateField(
        null=True,
        blank=True,
        verbose_name="Inicio del contrato vigente",
        help_text="Fecha de inicio del contrato actual"
    )
    fecha_fin_contrato = models.DateField(
        null=True,
        blank=True,
        verbose_name="Vencimiento del contrato",
        help_text="Fecha de vencimiento. Vacío = indefinido o sin fecha pactada."
    )
    renovacion_automatica = models.BooleanField(
        default=False,
        verbose_name="Renovación automática",
        help_text="Marcar si el contrato se renueva automáticamente al vencer"
    )
    observaciones_contrato = models.TextField(
        blank=True,
        verbose_name="Observaciones del contrato"
    )
    
    # --- Roster ---
    dias_libres_corte_2025 = models.DecimalField(
        max_digits=5,
        decimal_places=1,
        default=0,
        validators=[MinValueValidator(Decimal('0.0'))],
        verbose_name="Días Libres al 31/12/25",
        help_text="Días libres acumulados al corte del 31 de diciembre de 2025 (valor manual)"
    )

    def calcular_dias_libres_ganados(self):
        """
        Calcula días libres ganados basados en el régimen de turno.
        Por ejemplo:
        - 21x7: cada 3 días T genera 1 día libre (21/7 = 3)
        - 15x3: cada 5 días T genera 1 día libre (15/3 = 5)
        - TR siempre es 5x2: cada 5 días TR genera 2 días libres
        
        Acumula fracciones y redondea al entero más próximo al final.
        """
        rosters = Roster.objects.filter(personal=self)
        count_t = rosters.filter(codigo="T").count()
        count_tr = rosters.filter(codigo="TR").count()
        
        # Calcular factor para T según régimen de turno
        factor_t = 3  # Por defecto 21x7 -> 21/7 = 3
        if self.regimen_turno:
            try:
                # Extraer días de trabajo y descanso del formato "NxM"
                partes = self.regimen_turno.strip().split('x')
                if len(partes) == 2:
                    dias_trabajo = int(partes[0])
                    dias_descanso = int(partes[1])
                    if dias_descanso > 0:
                        factor_t = dias_trabajo / dias_descanso
            except (ValueError, ZeroDivisionError):
                pass  # Usar factor por defecto
        
        # TR siempre es 5x2 (cada 5 días genera 2 libres)
        factor_tr = 5.0 / 2.0  # 2.5 días TR por cada día libre
        
        # Calcular días libres con decimales
        dias_libres_de_t = count_t / factor_t
        dias_libres_de_tr = count_tr / factor_tr
        
        # Sumar y redondear al entero más próximo
        total_dias_libres = round(dias_libres_de_t + dias_libres_de_tr)
        
        return total_dias_libres

    def calcular_dias_dl_usados(self):
        """
        Calcula cuántos días DL ha usado el personal en el roster.
        """
        return Roster.objects.filter(personal=self, codigo="DL").count()
    
    def calcular_dias_dla_usados(self):
        """
        Calcula cuántos días DLA (Día Libre Acumulado) ha usado el personal en el roster.
        """
        return Roster.objects.filter(personal=self, codigo="DLA").count()
    
    def validar_dla_consecutivos(self, fecha_nueva):
        """
        Valida que no se ingresen más de 7 días DLA consecutivos.
        Retorna (es_valido, mensaje)
        """
        from datetime import timedelta
        
        # Obtener todos los registros DLA del personal ordenados por fecha
        rosters_dla = Roster.objects.filter(
            personal=self, 
            codigo="DLA"
        ).order_by('fecha')
        
        # Agregar la nueva fecha para validar
        fechas_dla = list(rosters_dla.values_list('fecha', flat=True))
        fechas_dla.append(fecha_nueva)
        fechas_dla.sort()
        
        # Contar días consecutivos
        max_consecutivos = 0
        consecutivos = 1
        for i in range(1, len(fechas_dla)):
            if fechas_dla[i] - fechas_dla[i-1] == timedelta(days=1):
                consecutivos += 1
                max_consecutivos = max(max_consecutivos, consecutivos)
                if consecutivos > 7:
                    return False, f"No se pueden ingresar más de 7 días DLA consecutivos. Ya tiene {consecutivos} días consecutivos incluyendo este"
            else:
                consecutivos = 1
        
        return True, ""
    
    def validar_saldo_dla(self, nueva_dla=False):
        """
        Valida que el saldo de días al 31/12/25 no sea negativo después de descontar DLA.
        Retorna (es_valido, mensaje, saldo_actual)
        """
        dias_dla_usados = self.calcular_dias_dla_usados()
        if nueva_dla:
            dias_dla_usados += 1
        
        saldo = float(self.dias_libres_corte_2025) - dias_dla_usados
        
        if saldo < 0:
            return False, f"No hay suficientes días acumulados al 31/12/25. Saldo actual: {self.dias_libres_corte_2025}, DLA usados: {dias_dla_usados-1}", saldo
        
        return True, "", saldo
    
    def validar_saldo_dl(self, nuevo_dl=False):
        """
        Valida que los días libres pendientes no sean negativos después de usar DL.
        Retorna (es_valido, mensaje, dias_pendientes)
        """
        dias_ganados = self.calcular_dias_libres_ganados()
        dias_dl_usados = self.calcular_dias_dl_usados()
        dias_dla_usados = self.calcular_dias_dla_usados()
        
        # Si estamos intentando agregar un nuevo DL, incrementar el contador
        if nuevo_dl:
            dias_dl_usados += 1
        
        # DLA descuenta del corte 2025
        saldo_corte_2025 = float(self.dias_libres_corte_2025) - dias_dla_usados
        
        # Días pendientes = saldo del corte + ganados - DL usados
        dias_pendientes = saldo_corte_2025 + dias_ganados - dias_dl_usados
        
        if dias_pendientes < 0:
            return False, f"No tiene más días libres pendientes disponibles. Días libres pendientes actuales: {dias_pendientes + 1:.0f}", dias_pendientes
        
        return True, "", dias_pendientes

    @cached_property
    def dias_libres_ganados(self):
        """
        Días libres ganados desde el roster (T y TR).
        cached_property: se calcula una sola vez por instancia en el request.
        """
        return self.calcular_dias_libres_ganados()

    @cached_property
    def dias_libres_pendientes(self):
        """
        Días Libres Pendientes = (Días Libres al 31/12/25 + Días Libres Ganados) - Días DL usados - Días DLA usados
        DLA descuenta del saldo al 31/12/25, no de los ganados.

        cached_property: evita re-calcular en cada acceso del template.
        Antes generaba 3 SELECT COUNT por acceso; ahora: 0 si ya fue calculado.
        """
        dias_ganados    = self.calcular_dias_libres_ganados()
        dias_dl_usados  = self.calcular_dias_dl_usados()
        dias_dla_usados = self.calcular_dias_dla_usados()
        saldo_corte_2025 = float(self.dias_libres_corte_2025) - dias_dla_usados
        return saldo_corte_2025 + dias_ganados - dias_dl_usados
    
    # --- Perfil de Acceso (RBAC) ---
    perfil_acceso = models.ForeignKey(
        'core.PerfilAcceso',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_asignados',
        verbose_name='Perfil de Acceso',
        help_text=(
            'Define qué módulos del sistema puede ver este usuario. '
            'Dejar vacío si el usuario no tiene cuenta de sistema, '
            'o si es superusuario (acceso total siempre).'
        ),
    )

    # --- Observaciones ---
    observaciones = models.TextField(blank=True, verbose_name="Observaciones")

    # --- Metadatos ---
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Personal"
        verbose_name_plural = "Personal"
        ordering = ['apellidos_nombres']
        indexes = [
            # Lookups básicos
            models.Index(fields=['nro_doc']),
            models.Index(fields=['estado']),
            models.Index(fields=['subarea']),
            # Filtros compuestos más usados en vistas y services
            models.Index(fields=['estado', 'grupo_tareo'],
                         name='personal_estado_grupo_idx'),
            models.Index(fields=['estado', 'condicion'],
                         name='personal_estado_condicion_idx'),
            models.Index(fields=['estado', 'categoria'],
                         name='personal_estado_categoria_idx'),
            # Búsquedas de contratos próximos a vencer
            models.Index(fields=['fecha_fin_contrato'],
                         name='personal_fin_contrato_idx'),
            # Multi-tenant (audit perf 2026-05-20): con 24 RUCs cada query
            # "activos de empresa X" puede usar index compuesto.
            models.Index(fields=['empresa', 'estado'],
                         name='personal_empresa_estado_idx'),
            models.Index(fields=['empresa', 'grupo_tareo', 'estado'],
                         name='personal_emp_grupo_est_idx'),
        ]
    
    def __str__(self):
        return f"{self.apellidos_nombres} ({self.nro_doc})"
    
    @property
    def nombre_completo(self):
        return self.apellidos_nombres
    
    def clean(self):
        """Validación del modelo usando validadores centralizados."""
        from .validators import PersonalValidator
        
        # Validar número de documento
        if self.nro_doc:
            PersonalValidator.validar_nro_doc(self.nro_doc, self.tipo_doc)
        
        # Validar régimen de turno
        if self.regimen_turno:
            PersonalValidator.validar_regimen_turno(self.regimen_turno)
        
        # Validar fechas
        if self.fecha_alta and self.fecha_cese:
            PersonalValidator.validar_rango_fechas(self.fecha_alta, self.fecha_cese)
        
        # Validar montos (0 es válido para empleados sin sueldo asignado)
        if self.sueldo_base and self.sueldo_base > 0:
            PersonalValidator.validar_monto(
                self.sueldo_base,
                campo='sueldo base',
                minimo=0,
                maximo=999999.99
            )
        
        if self.bonos:
            PersonalValidator.validar_monto(
                self.bonos,
                campo='bonos',
                minimo=0,
                maximo=999999.99
            )

        # ── Hard cap por plan comercial ──
        # Plan Starter (S/149/mes) tope 30 trabajadores activos.
        # Bloqueamos altas (pk=None) cuando ya hay 30 en la empresa.
        # Aplica solo si la empresa tiene plan='STARTER'.
        if self.pk is None and self.empresa_id and self.estado != 'Inactivo':
            try:
                plan = getattr(self.empresa, 'plan', None)
            except Exception:
                plan = None
            limites = {
                'STARTER':     30,
                'PROFESIONAL': 100,
                'BUSINESS':    300,
                # ENTERPRISE: sin tope
            }
            tope = limites.get(plan)
            if tope is not None:
                from django.core.exceptions import ValidationError
                actuales = Personal.objects.filter(
                    empresa=self.empresa,
                    estado='Activo',
                ).count()
                if actuales >= tope:
                    raise ValidationError({
                        'empresa': (
                            f'El Plan {plan} permite hasta {tope} trabajadores activos. '
                            f'Esta empresa ya tiene {actuales}. '
                            f'Actualiza a un plan superior en /upgrade/ para agregar más.'
                        )
                    })

    @property
    def esta_activo(self):
        return self.estado == 'Activo'

    @property
    def es_confianza_o_direccion(self):
        """D.Leg. 854 art. 5: excluidos de jornada máxima, sin HE ni faltas."""
        return self.categoria in ('CONFIANZA', 'DIRECCION')

    @property
    def paga_por_billetera(self):
        """True si el pago de haberes va por billetera digital (Ley 32413):
        requiere medio BILLETERA + acuerdo del trabajador + celular válido
        (9 dígitos, empieza en 9). Sin eso, paga por cuenta bancaria."""
        cel = (self.billetera_celular or '').strip()
        return (
            self.medio_pago_haberes == 'BILLETERA'
            and self.billetera_acuerdo
            and len(cel) == 9 and cel.isdigit() and cel.startswith('9')
        )

    @property
    def fecha_ingreso(self):
        """Alias para fecha_alta (terminología estándar planilla)."""
        return self.fecha_alta

    @property
    def periodo_prueba_meses(self):
        """Meses de período de prueba según categoría (D.Leg. 728 art. 10).
        Normal: 3 meses | Confianza: 6 meses | Dirección: 12 meses."""
        if self.categoria == 'DIRECCION':
            return 12
        elif self.categoria == 'CONFIANZA':
            return 6
        return 3

    @property
    def fecha_fin_periodo_prueba(self):
        """Fecha de fin del período de prueba calculada desde fecha_alta."""
        from dateutil.relativedelta import relativedelta
        if not self.fecha_alta:
            return None
        return self.fecha_alta + relativedelta(months=self.periodo_prueba_meses)

    @property
    def en_periodo_prueba(self):
        """True si hoy está dentro del período de prueba."""
        from django.utils import timezone
        fin = self.fecha_fin_periodo_prueba
        if not fin or self.estado != 'Activo':
            return False
        return timezone.localdate() <= fin

    @property
    def dias_para_vencimiento_contrato(self):
        """Días hasta el vencimiento del contrato. None si no hay fecha fin."""
        if not self.fecha_fin_contrato:
            return None
        from django.utils import timezone
        delta = self.fecha_fin_contrato - timezone.localdate()
        return delta.days


# ─────────────────────────────────────────────────────────────────────────────
# CONTRATOS LABORALES
# ─────────────────────────────────────────────────────────────────────────────

class Contrato(models.Model):
    """
    Contrato laboral individual. Permite llevar historial de contratos
    por trabajador (no solo el vigente), con archivo PDF adjunto.
    Complementa los campos de contrato en Personal (que reflejan el contrato actual).
    """
    ESTADO_CHOICES = [
        ('VIGENTE', 'Vigente'),
        ('VENCIDO', 'Vencido'),
        ('RENOVADO', 'Renovado'),
        ('RESCINDIDO', 'Rescindido'),
        ('FINALIZADO', 'Finalizado'),
    ]

    personal = models.ForeignKey(
        Personal,
        on_delete=models.CASCADE,
        related_name='contratos',
        verbose_name='Trabajador',
    )
    tipo_contrato = models.CharField(
        max_length=25,
        choices=Personal.TIPO_CONTRATO_CHOICES,
        verbose_name='Modalidad de Contrato',
        help_text='Según D.Leg. 728 — Ley de Productividad y Competitividad Laboral',
    )
    numero_contrato = models.CharField(
        max_length=50,
        blank=True,
        verbose_name='Número de Contrato',
        help_text='Código interno o número de registro del contrato',
    )
    fecha_inicio = models.DateField(verbose_name='Fecha de Inicio')
    fecha_fin = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de Fin',
        help_text='Dejar vacío para contratos indefinidos',
    )
    estado = models.CharField(
        max_length=12,
        choices=ESTADO_CHOICES,
        default='VIGENTE',
        verbose_name='Estado',
    )
    renovacion_automatica = models.BooleanField(
        default=False,
        verbose_name='Renovación automática',
        help_text='El contrato se renueva sin trámite al vencer',
    )
    sueldo_pactado = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True, blank=True,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Sueldo pactado',
        help_text='Remuneración mensual acordada en el contrato',
    )
    cargo_contrato = models.CharField(
        max_length=150,
        blank=True,
        verbose_name='Cargo en contrato',
        help_text='Cargo que figura en el contrato (puede diferir del cargo actual)',
    )
    jornada_semanal = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        default=Decimal('48.0'),
        verbose_name='Jornada semanal (horas)',
        help_text='Jornada máxima legal en Perú: 48 horas semanales (D.Leg. 854)',
    )
    archivo_pdf = models.FileField(
        upload_to='contratos/%Y/%m/',
        blank=True,
        verbose_name='Archivo PDF',
        help_text='Documento escaneado del contrato firmado',
    )
    observaciones = models.TextField(
        blank=True,
        verbose_name='Observaciones',
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='contratos_registrados',
        verbose_name='Registrado por',
    )
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Contrato'
        verbose_name_plural = 'Contratos'
        ordering = ['-fecha_inicio']
        indexes = [
            models.Index(fields=['personal', '-fecha_inicio'], name='contrato_personal_inicio_idx'),
            models.Index(fields=['estado'], name='contrato_estado_idx'),
            models.Index(fields=['fecha_fin'], name='contrato_fecha_fin_idx'),
            models.Index(fields=['tipo_contrato'], name='contrato_tipo_idx'),
        ]
        constraints = [
            # Un empleado solo puede tener un contrato VIGENTE a la vez.
            # Otros estados (VENCIDO, RENOVADO, etc.) pueden coexistir.
            models.UniqueConstraint(
                fields=['personal'],
                condition=models.Q(estado='VIGENTE'),
                name='personal_contrato_one_vigente_per_person',
            ),
        ]

    def __str__(self):
        tipo = self.get_tipo_contrato_display()
        return f"{self.personal.apellidos_nombres} — {tipo} ({self.fecha_inicio})"

    @property
    def dias_restantes(self):
        """Días hasta el vencimiento. None si es indefinido."""
        if not self.fecha_fin:
            return None
        from django.utils import timezone
        return (self.fecha_fin - timezone.localdate()).days

    @property
    def esta_vencido(self):
        if not self.fecha_fin:
            return False
        from django.utils import timezone
        return self.fecha_fin < timezone.localdate()

    @property
    def esta_por_vencer(self):
        """True si vence en los próximos 30 días."""
        dias = self.dias_restantes
        if dias is None:
            return False
        return 0 <= dias <= 30

    def sincronizar_con_personal(self):
        """Actualiza los campos de contrato en Personal con los datos de este contrato."""
        p = self.personal
        p.tipo_contrato = self.tipo_contrato
        p.fecha_inicio_contrato = self.fecha_inicio
        p.fecha_fin_contrato = self.fecha_fin
        p.renovacion_automatica = self.renovacion_automatica
        p.save(update_fields=[
            'tipo_contrato', 'fecha_inicio_contrato', 'fecha_fin_contrato',
            'renovacion_automatica',
        ])


class RenovacionContrato(models.Model):
    """
    Registro de renovación de un contrato. Vincula el contrato original
    con el nuevo contrato generado por la renovación.
    """
    contrato_original = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='renovaciones_salientes',
        verbose_name='Contrato original',
    )
    contrato_nuevo = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='renovaciones_entrantes',
        verbose_name='Contrato renovado',
    )
    fecha_renovacion = models.DateField(verbose_name='Fecha de renovación')
    motivo = models.TextField(
        blank=True,
        verbose_name='Motivo de renovación',
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Registrado por',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Renovación de Contrato'
        verbose_name_plural = 'Renovaciones de Contrato'
        ordering = ['-fecha_renovacion']

    def __str__(self):
        return f"Renovación {self.contrato_original} → {self.contrato_nuevo}"


class Adenda(models.Model):
    """
    Adenda (modificación) a un contrato existente.
    Registra cambios específicos sin necesidad de crear un contrato nuevo.
    """
    TIPO_MODIFICACION_CHOICES = [
        ('SUELDO', 'Modificación de sueldo'),
        ('CARGO', 'Cambio de cargo / puesto'),
        ('HORARIO', 'Cambio de horario / jornada'),
        ('CONDICIONES', 'Cambio de condiciones'),
        ('EXTENSION', 'Extensión de plazo'),
        ('AREA', 'Cambio de área / sede'),
        ('OTRO', 'Otro'),
    ]

    contrato = models.ForeignKey(
        Contrato,
        on_delete=models.CASCADE,
        related_name='adendas',
        verbose_name='Contrato',
    )
    fecha = models.DateField(verbose_name='Fecha de adenda')
    tipo_modificacion = models.CharField(
        max_length=15,
        choices=TIPO_MODIFICACION_CHOICES,
        verbose_name='Tipo de modificación',
    )
    detalle = models.TextField(
        verbose_name='Detalle de la modificación',
        help_text='Describa los cambios realizados al contrato',
    )
    valor_anterior = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Valor anterior',
        help_text='Valor o condición antes del cambio',
    )
    valor_nuevo = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Valor nuevo',
        help_text='Valor o condición después del cambio',
    )
    archivo = models.FileField(
        upload_to='adendas/%Y/%m/',
        blank=True,
        verbose_name='Archivo adjunto',
    )
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Registrado por',
    )
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Adenda'
        verbose_name_plural = 'Adendas'
        ordering = ['-fecha']

    def __str__(self):
        return f"Adenda {self.get_tipo_modificacion_display()} — {self.contrato}"


class PlantillaContrato(models.Model):
    """
    Plantilla HTML reutilizable para generar contratos, prórrogas y adendas laborales.
    Soporta placeholders como {{nombre_empleado}}, {{cargo}}, {{funciones_cargo}}, etc.
    """
    TIPO_DOCUMENTO_CHOICES = [
        ('CONTRATO', 'Contrato'),
        ('PRORROGA', 'Prórroga'),
        ('ADENDA', 'Adenda'),
        ('RENOVACION', 'Renovación'),
    ]
    CATEGORIA_CHOICES = [
        ('', '--- Sin categoría ---'),
        ('CONFIANZA', 'Personal de Confianza (no fiscalizable)'),
        ('FISCALIZABLE', 'Personal Fiscalizable (ordinario)'),
        ('OBRA_DETERMINADA', 'Obra Determinada (genérico)'),
        ('INDEFINIDO', 'Indefinido'),
        ('NECESIDAD_MERCADO', 'Necesidad de Mercado'),
        ('AUMENTO_SALARIAL', 'Adenda — Aumento Salarial'),
        ('CAMBIO_CARGO', 'Adenda — Cambio de Cargo'),
        ('CAMBIO_CONDICIONES', 'Adenda — Cambio de Condiciones'),
    ]
    nombre = models.CharField(
        max_length=150,
        verbose_name='Nombre de la plantilla',
    )
    tipo_documento = models.CharField(
        max_length=15,
        choices=TIPO_DOCUMENTO_CHOICES,
        default='CONTRATO',
        verbose_name='Tipo de documento',
    )
    categoria = models.CharField(
        max_length=25,
        choices=CATEGORIA_CHOICES,
        blank=True,
        verbose_name='Categoría',
        help_text='Subcategoría para filtrar plantillas (ej: Confianza vs Fiscalizable)',
    )
    tipo_contrato = models.CharField(
        max_length=25,
        choices=Personal.TIPO_CONTRATO_CHOICES,
        blank=True,
        verbose_name='Tipo de contrato asociado',
        help_text='Tipo de contrato al que aplica esta plantilla (vacio = generico)',
    )
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='plantillas_contrato',
        verbose_name='Empresa',
        help_text='Si se asigna, esta plantilla solo aplica a esta empresa. Vacío = todas.',
    )
    contenido_html = models.TextField(
        verbose_name='Contenido HTML',
        help_text=(
            'Placeholders disponibles: {{nombre_empleado}}, {{cargo}}, {{funciones_cargo}}, '
            '{{fecha_inicio}}, {{fecha_fin}}, {{remuneracion}}, {{remuneracion_letras}}, '
            '{{dni}}, {{tipo_doc_trabajador}}, {{domicilio}}, {{distrito}}, {{provincia}}, '
            '{{departamento}}, {{email_trabajador}}, {{empresa}}, {{ruc_empresa}}, '
            '{{direccion_empresa}}, {{representante_legal}}, {{cargo_representante}}, '
            '{{tipo_doc_representante}}, {{nro_doc_representante}}, {{jornada_semanal}}, '
            '{{periodo_prueba}}, {{fecha_inicio_original}}, {{fecha_fin_anterior}}, '
            '{{sueldo_anterior}}, {{sueldo_nuevo}}, {{cargo_anterior}}, {{cargo_nuevo}}, '
            '{{obra_nombre}}, {{obra_cliente}}, {{logo}}, {{firma_representante}}, '
            '{{fecha_firma}}, {{ciudad_firma}}'
        ),
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Fecha de creacion',
    )

    class Meta:
        verbose_name = 'Plantilla de Contrato'
        verbose_name_plural = 'Plantillas de Contrato'
        ordering = ['tipo_documento', 'nombre']
        indexes = [
            models.Index(fields=['tipo_documento', 'categoria', 'activo']),
        ]

    def __str__(self):
        return f"[{self.get_tipo_documento_display()}] {self.nombre}"


class Roster(models.Model):
    """
    Programación de turnos del personal por día.
    """
    personal = models.ForeignKey(
        Personal,
        on_delete=models.CASCADE,
        related_name='roster_dias',
        verbose_name="Personal"
    )
    fecha = models.DateField(verbose_name="Fecha")
    codigo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Código de Turno",
        help_text="Código del turno asignado"
    )
    
    # --- Información adicional ---
    observaciones = models.CharField(
        max_length=300,
        blank=True,
        verbose_name="Observaciones"
    )
    fuente = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Fuente",
        help_text="Origen del registro (archivo, usuario, etc.)"
    )
    
    # --- Sistema de aprobaciones ---
    ESTADO_CHOICES = [
        ('aprobado', 'Aprobado'),
        ('pendiente', 'Pendiente de Aprobación'),
        ('borrador', 'Borrador'),
    ]
    
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='aprobado',
        verbose_name="Estado",
        help_text="Estado del registro: borrador, pendiente o aprobado"
    )
    
    modificado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roster_modificaciones',
        verbose_name="Modificado por"
    )
    
    aprobado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roster_aprobaciones',
        verbose_name="Aprobado por"
    )
    
    aprobado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Aprobación"
    )
    
    # --- Metadatos ---
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Roster"
        verbose_name_plural = "Roster"
        ordering = ['fecha', 'personal']
        unique_together = ['personal', 'fecha']
        indexes = [
            models.Index(fields=['personal', 'fecha']),
            models.Index(fields=['fecha']),
            models.Index(fields=['estado']),
        ]
    
    def __str__(self):
        return f"{self.personal} - {self.fecha} - {self.codigo}"
    
    def puede_editar(self, usuario):
        """Verifica si un usuario puede editar este registro de roster."""
        from datetime import date
        
        # Admin puede editar todo
        if usuario.is_superuser:
            return True, ""
        
        # No se puede editar antes de enero 2026
        if self.fecha.year < 2026:
            return False, "No se puede editar registros anteriores a enero 2026"
        
        # Solo se puede editar del día actual en adelante (excepto admin)
        if self.fecha < date.today():
            return False, "Solo el administrador puede editar días anteriores"
        
        # Verificar si es responsable del área del personal
        from .permissions import puede_editar_roster
        if puede_editar_roster(usuario, self.personal):
            return True, ""
        
        return False, "No tiene permisos para editar este registro"
    
    def puede_aprobar(self, usuario):
        """Verifica si un usuario puede aprobar cambios en este registro."""
        from .permissions import get_areas_responsable
        
        # Admin puede aprobar todo
        if usuario.is_superuser:
            return True
        
        # Verificar si es responsable del área del personal
        areas = get_areas_responsable(usuario)
        if self.personal.subarea and areas.filter(pk=self.personal.subarea.area_id).exists():
            return True
        
        return False
    
    def clean(self):
        """Validación del modelo usando validadores centralizados."""
        from .validators import RosterValidator
        import logging
        
        logger = logging.getLogger('personal.business')
        
        # Validar código
        if self.codigo:
            self.codigo = RosterValidator.validar_codigo(self.codigo)
        
        # Validar duplicados (solo si es un nuevo registro o cambió personal/fecha)
        if not self.pk or self._state.adding:
            RosterValidator.validar_duplicado(self.personal, self.fecha)
        
        logger.info(f"Roster validado: {self.personal} - {self.fecha} - {self.codigo}")


class RosterAudit(models.Model):
    """
    Auditoría de cambios en el roster.
    Registra todas las modificaciones realizadas.
    """
    personal = models.ForeignKey(
        Personal,
        on_delete=models.CASCADE,
        related_name='roster_audits',
        verbose_name="Personal"
    )
    fecha = models.DateField(verbose_name="Fecha del Registro")
    
    campo_modificado = models.CharField(
        max_length=50,
        verbose_name="Campo Modificado",
        help_text="Nombre del campo que fue modificado"
    )
    valor_anterior = models.TextField(
        blank=True,
        verbose_name="Valor Anterior"
    )
    valor_nuevo = models.TextField(
        blank=True,
        verbose_name="Valor Nuevo"
    )
    
    usuario = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Usuario que realizó el cambio"
    )
    
    creado_en = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Auditoría")
    
    class Meta:
        verbose_name = "Auditoría de Roster"
        verbose_name_plural = "Auditorías de Roster"
        ordering = ['-creado_en']
        indexes = [
            models.Index(fields=['personal', 'fecha']),
            models.Index(fields=['-creado_en']),
        ]
    
    def __str__(self):
        return f"{self.personal} - {self.fecha} - {self.campo_modificado}"


# ═══════════════════════════════════════════════════════════
#  CONTROL DE ACTIVOS / HERRAMIENTAS ASIGNADAS
# ═══════════════════════════════════════════════════════════

class ActivoAsignado(models.Model):
    """
    Registro de activos, herramientas o equipos asignados a un trabajador.
    Integrado con offboarding para checklist de devolución al cese.
    """
    TIPO_CHOICES = [
        ('LAPTOP', 'Laptop / Computador'),
        ('CELULAR', 'Celular / Smartphone'),
        ('RADIO', 'Radio / Walkie-Talkie'),
        ('TABLET', 'Tablet'),
        ('HERRAMIENTA', 'Herramienta de Trabajo'),
        ('VEHICULO', 'Vehículo'),
        ('LLAVE', 'Llave / Tarjeta de Acceso'),
        ('MOBILIARIO', 'Mobiliario de Oficina'),
        ('OTRO', 'Otro'),
    ]

    ESTADO_CHOICES = [
        ('ASIGNADO', 'Asignado al trabajador'),
        ('DEVUELTO', 'Devuelto'),
        ('EXTRAVIADO', 'Extraviado / Perdido'),
        ('DANADO', 'Dañado'),
    ]

    personal = models.ForeignKey(
        'Personal', on_delete=models.CASCADE,
        related_name='activos_asignados',
        verbose_name='Trabajador')
    tipo = models.CharField(
        max_length=20, choices=TIPO_CHOICES,
        verbose_name='Tipo de Activo')
    descripcion = models.CharField(
        max_length=200,
        verbose_name='Descripción',
        help_text='Ej: Laptop Dell Latitude 5520, S/N ABC123')
    serial = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name='N° Serie / Código')
    fecha_asignacion = models.DateField(
        verbose_name='Fecha de Asignación')
    fecha_devolucion = models.DateField(
        null=True, blank=True,
        verbose_name='Fecha de Devolución')
    estado = models.CharField(
        max_length=15, choices=ESTADO_CHOICES, default='ASIGNADO')
    valor_estimado = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        verbose_name='Valor Estimado (S/)')
    observaciones = models.TextField(blank=True, default='')
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True,
        related_name='activos_registrados')
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_asignacion']
        verbose_name = 'Activo Asignado'
        verbose_name_plural = 'Activos Asignados'

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.descripcion[:40]} → {self.personal}'

    @property
    def pendiente_devolucion(self):
        return self.estado == 'ASIGNADO'


# ═══════════════════════════════════════════════════════════
#  ROSTER QUINCENAL GASTRONOMICO
#  Turnos rotativos visuales con drag&drop + validacion 6+1
#  (DS 003-97-TR Art. 25 — minimo 1 dia libre cada 7 dias)
# ═══════════════════════════════════════════════════════════

class TurnoGastronomia(models.Model):
    """Definicion de turno gastronomico (Desayuno, Almuerzo, Cena, etc.)."""
    codigo = models.CharField(max_length=10, unique=True, verbose_name='Codigo')
    nombre = models.CharField(max_length=80, verbose_name='Nombre')
    hora_entrada = models.TimeField(verbose_name='Hora entrada')
    hora_salida = models.TimeField(verbose_name='Hora salida')
    color = models.CharField(
        max_length=7, default='#0f766e',
        verbose_name='Color',
        help_text='HEX color para badge en el grid (ej: #0f766e)'
    )
    activo = models.BooleanField(default=True, verbose_name='Activo')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Turno Gastronomia'
        verbose_name_plural = 'Turnos Gastronomia'
        ordering = ['hora_entrada', 'codigo']
        indexes = [
            models.Index(fields=['activo']),
        ]

    def __str__(self):
        return f'{self.codigo} - {self.nombre}'

    @property
    def label_horario(self):
        return f'{self.hora_entrada.strftime("%H:%M")}-{self.hora_salida.strftime("%H:%M")}'


class AsignacionRosterQuincena(models.Model):
    """Asignacion de turno a un trabajador para una fecha (1 fila = 1 dia)."""
    personal = models.ForeignKey(
        Personal,
        on_delete=models.CASCADE,
        related_name='asignaciones_roster',
        verbose_name='Personal',
    )
    fecha = models.DateField(verbose_name='Fecha')
    turno = models.ForeignKey(
        TurnoGastronomia,
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='asignaciones',
        verbose_name='Turno',
        help_text='Null = dia libre',
    )
    notas = models.TextField(blank=True, default='', verbose_name='Notas')
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='asignaciones_roster_creadas',
        verbose_name='Creado por',
    )

    class Meta:
        verbose_name = 'Asignacion Roster Quincena'
        verbose_name_plural = 'Asignaciones Roster Quincena'
        unique_together = [('personal', 'fecha')]
        ordering = ['fecha', 'personal']
        indexes = [
            models.Index(fields=['fecha']),
            models.Index(fields=['personal', 'fecha']),
        ]

    def __str__(self):
        t = self.turno.codigo if self.turno else 'LIBRE'
        return f'{self.personal} - {self.fecha} - {t}'

    @property
    def es_libre(self):
        return self.turno_id is None
