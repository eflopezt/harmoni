"""
Modelos de datos para el sistema de gestión de personal.
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from .user_models import UserProfile


class Area(models.Model):
    """
    Áreas o departamentos de alto nivel.
    Cada área puede tener uno o varios responsables.
    """
    nombre = models.CharField(max_length=150, unique=True, verbose_name="Nombre de Área")
    responsables = models.ManyToManyField(
        'Personal',
        blank=True,
        related_name='areas_responsable',
        verbose_name="Responsables",
        help_text="Personas responsables de esta área"
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
    tipo_trab = models.CharField(
        max_length=20,
        choices=TIPO_TRAB_CHOICES,
        verbose_name="Tipo de Trabajador"
    )
    subarea = models.ForeignKey(
        SubArea,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='personal_asignado',
        verbose_name="SubÁrea Asignada"
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
    
    # --- Datos económicos ---
    sueldo_base = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.01'))],
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
    
    # --- Clasificación de tareo ---
    GRUPO_TAREO_CHOICES = [
        ('STAFF', 'RC Staff (HE compensatorias — banco de horas)'),
        ('RCO', 'RC Operativos (HE pagadas 25/35/100%)'),
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
        help_text="Determina cómo se tratan las HE: banco (STAFF) o pago (RCO)"
    )
    condicion = models.CharField(
        max_length=10,
        choices=CONDICION_CHOICES,
        blank=True,
        verbose_name="Condición",
        help_text="LOCAL = jornada fija | FORÁNEO = régimen acumulativo"
    )
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
    regimen_laboral = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Régimen Laboral"
    )
    regimen_turno = models.CharField(
        max_length=30,
        blank=True,
        verbose_name="Régimen de Turno",
        help_text="Ej: 14x7, 21x7, etc."
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

    @property
    def dias_libres_ganados(self):
        """Propiedad para obtener días libres ganados."""
        return self.calcular_dias_libres_ganados()
    
    @property
    def dias_libres_pendientes(self):
        """
        Días Libres Pendientes = (Días Libres al 31/12/25 + Días Libres Ganados) - Días DL usados - Días DLA usados
        DLA descuenta del saldo al 31/12/25, no de los ganados.
        """
        dias_ganados = self.calcular_dias_libres_ganados()
        dias_dl_usados = self.calcular_dias_dl_usados()
        dias_dla_usados = self.calcular_dias_dla_usados()
        
        # DLA descuenta del corte 2025
        saldo_corte_2025 = float(self.dias_libres_corte_2025) - dias_dla_usados
        
        # Días pendientes = saldo del corte + ganados - DL usados
        return saldo_corte_2025 + dias_ganados - dias_dl_usados
    
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
            models.Index(fields=['nro_doc']),
            models.Index(fields=['estado']),
            models.Index(fields=['subarea']),
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
        
        # Validar montos
        if self.sueldo_base:
            PersonalValidator.validar_monto(
                self.sueldo_base, 
                campo='sueldo base',
                minimo=0.01,
                maximo=999999.99
            )
        
        if self.bonos:
            PersonalValidator.validar_monto(
                self.bonos,
                campo='bonos',
                minimo=0,
                maximo=999999.99
            )
    
    @property
    def esta_activo(self):
        return self.estado == 'Activo'


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
