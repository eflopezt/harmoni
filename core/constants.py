"""
Constantes legales y de negocio para el sistema Harmoni.

Referencias legales (Perú):
- D.L. 728: Ley de Productividad y Competitividad Laboral
- D.S. 003-97-TR: TUO de la Ley de Productividad y Competitividad Laboral
- D.S. 007-2002-TR: TUO de la Ley de Jornada de Trabajo
- D.Leg. 713: Descansos remunerados
- D.S. 012-92-TR: Reglamento del D.Leg. 713
- D.S. 001-97-TR: TUO de la Ley de CTS
- D.L. 25897: Sistema Privado de Pensiones
"""
from decimal import Decimal


# ──────────────────────────────────────────────
# JORNADA LABORAL (D.S. 007-2002-TR, Art. 1)
# ──────────────────────────────────────────────
JORNADA_MAXIMA_DIARIA = Decimal("8")       # horas
JORNADA_MAXIMA_SEMANAL = Decimal("48")     # horas
JORNADA_LOCAL_DEFAULT = Decimal("8.5")     # incluye 0.5h almuerzo
JORNADA_FORANEO_DEFAULT = Decimal("11")    # sin deducción almuerzo
JORNADA_LIMA_DEFAULT = Decimal("8.5")      # incluye 0.5h almuerzo
ALMUERZO_MINUTOS_DEFAULT = 30              # minutos


# ──────────────────────────────────────────────
# SOBRETIEMPO / HORAS EXTRA (D.S. 007-2002-TR, Art. 10)
# ──────────────────────────────────────────────
HE_UMBRAL_TASA_25 = Decimal("2")    # primeras 2 horas: 25% recargo
HE_TASA_25 = Decimal("0.25")        # recargo sobre remuneración ordinaria
HE_TASA_35 = Decimal("0.35")        # a partir de la 3ra hora
HE_TASA_100 = Decimal("1.00")       # feriado laborado + descanso semanal trabajado

# Horas al 100% aplican cuando:
# 1. Feriado laborado (D.Leg. 713, Art. 9)
# 2. Descanso semanal obligatorio trabajado (D.Leg. 713, Art. 3-4)
#    Incluye: domingos y cualquier día de descanso semanal según régimen


# ──────────────────────────────────────────────
# DESCANSOS REMUNERADOS (D.Leg. 713)
# ──────────────────────────────────────────────
DIA_DESCANSO_SEMANAL = 6  # domingo (0=lunes en Python)
VACACIONES_DIAS_ANUALES = 30  # Art. 10


# ──────────────────────────────────────────────
# CICLO DE PLANILLA
# ──────────────────────────────────────────────
CICLO_PLANILLA_DIA_CORTE = 20  # día del mes: ciclo 21 mes ant → 20 mes actual


# ──────────────────────────────────────────────
# GRUPOS DE PERSONAL
# ──────────────────────────────────────────────
GRUPO_STAFF = "STAFF"
GRUPO_RCO = "RCO"
GRUPO_OTRO = "OTRO"

GRUPO_CHOICES = [
    (GRUPO_STAFF, "Staff"),
    # Valor interno 'RCO' preservado por compat datos; label visible "Operativo"
    # cubre tanto gastronomía/servicios como construcción civil.
    (GRUPO_RCO, "Operativo (Recibo de Honorarios)"),
    (GRUPO_OTRO, "Otro"),
]


# ──────────────────────────────────────────────
# CONDICIONES DE TRABAJO
# ──────────────────────────────────────────────
CONDICION_LOCAL = "FORANEO"
CONDICION_FORANEO = "FORANEO"
CONDICION_LIMA = "LIMA"

CONDICION_CHOICES = [
    ("FORANEO", "Foráneo"),
    ("LOCAL", "Local"),
    ("LIMA", "Lima"),
]


# ──────────────────────────────────────────────
# CÓDIGOS DE JORNADA (Registro Tareo)
# ──────────────────────────────────────────────
CODIGO_ASISTENCIA = "A"
CODIGO_NORMAL = "NOR"
CODIGO_TRABAJO = "T"
CODIGO_DESCANSO_LIBRE = "DL"      # Descanso Semanal Obligatorio
CODIGO_DLA = "DLA"                 # Día Libre Acumulado
CODIGO_VACACIONES = "VAC"          # Descanso Vacacional
CODIGO_DESCANSO_MEDICO = "DM"     # Descanso Médico
CODIGO_LICENCIA_CON_GOCE = "LCG"  # Licencia con Goce de Haber
CODIGO_LICENCIA_SIN_GOCE = "LSG"  # Licencia sin Goce de Haber
CODIGO_FALTA = "FA"                # Inasistencia Injustificada
CODIGO_CHE = "CHE"                 # Compensación por Sobretiempo
CODIGO_SIN_SALIDA = "SS"          # Sin Marca de Salida
CODIGO_FERIADO = "FER"            # Feriado
CODIGO_FERIADO_LABORADO = "FL"    # Feriado Laborado
CODIGO_SUSPENSION = "SUS"         # Suspensión

# Códigos que cuentan como día trabajado
CODIGOS_ASISTENCIA = {CODIGO_ASISTENCIA, CODIGO_NORMAL, CODIGO_TRABAJO, CODIGO_SIN_SALIDA}

# Códigos que no generan sobretiempo
CODIGOS_SIN_HE = {
    CODIGO_DESCANSO_LIBRE, CODIGO_DLA, CODIGO_VACACIONES,
    CODIGO_DESCANSO_MEDICO, CODIGO_LICENCIA_CON_GOCE,
    CODIGO_LICENCIA_SIN_GOCE, CODIGO_FALTA, CODIGO_CHE,
    CODIGO_SUSPENSION,
}


# ──────────────────────────────────────────────
# TERMINOLOGÍA ESTANDARIZADA (verbose_name)
# Para usar en modelos: field = DecimalField(verbose_name=TERM_HE_25)
# ──────────────────────────────────────────────
TERM_HE_25 = "Sobretiempo al 25%"
TERM_HE_35 = "Sobretiempo al 35%"
TERM_HE_100 = "Sobretiempo al 100%"
TERM_BANCO_HORAS = "Compensación por Sobretiempo"
TERM_FALTA = "Inasistencia Injustificada"
TERM_DESCANSO_MEDICO = "Descanso Médico"
TERM_VACACIONES = "Descanso Vacacional"
TERM_LSG = "Licencia sin Goce de Haber"
TERM_LCG = "Licencia con Goce de Haber"
TERM_DSO = "Descanso Semanal Obligatorio"
TERM_SIN_SALIDA = "Sin Marca de Salida"
TERM_REMUNERACION = "Remuneración Básica"
TERM_CTS = "Compensación por Tiempo de Servicios"
TERM_AFP = "Sistema Privado de Pensiones"


# ──────────────────────────────────────────────
# ROLES DEL SISTEMA
# ──────────────────────────────────────────────
ROL_ADMIN = "admin"
ROL_GERENTE = "gerente"
ROL_RESPONSABLE = "responsable"
ROL_COLABORADOR = "colaborador"

ROL_CHOICES = [
    (ROL_ADMIN, "Administrador"),
    (ROL_GERENTE, "Gerente"),
    (ROL_RESPONSABLE, "Responsable de Área"),
    (ROL_COLABORADOR, "Colaborador"),
]
