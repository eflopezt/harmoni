"""
Format overrides para locale es_PE.

Django default español usa coma decimal (DECIMAL_SEPARATOR=',') + non-breaking
space como separador de miles. En Perú (y la mayoría de Latam financiero) se
usa PUNTO decimal + COMA separador miles.

Sin este override, montos como S/ 1,458.00 se renderizan como 'S/ 1,458,00'
que es ambiguo e ilegible.

Fix: forzar el formato peruano financiero estándar.
"""
# Separadores numéricos (estándar Perú/Latam)
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3

# Formato fecha (compatible es Latam)
DATE_FORMAT = "j \\d\\e F \\d\\e Y"
TIME_FORMAT = "H:i"
DATETIME_FORMAT = "j \\d\\e F \\d\\e Y \\a \\l\\a\\s H:i"
YEAR_MONTH_FORMAT = "F \\d\\e Y"
MONTH_DAY_FORMAT = "j \\d\\e F"
SHORT_DATE_FORMAT = "d/m/Y"
SHORT_DATETIME_FORMAT = "d/m/Y H:i"
FIRST_DAY_OF_WEEK = 1  # Lunes

# Input parsing
DATE_INPUT_FORMATS = [
    "%d/%m/%Y",
    "%d/%m/%y",
    "%Y-%m-%d",
]
DATETIME_INPUT_FORMATS = [
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
]
TIME_INPUT_FORMATS = [
    "%H:%M:%S",
    "%H:%M",
]
