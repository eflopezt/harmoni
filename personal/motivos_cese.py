"""
Catálogo ÚNICO de motivos de cese y sus mapeos entre módulos.

Antes de este módulo existían 3 catálogos independientes con mapeos ad-hoc
regados por el código (13 motivos en Personal, 5 en ProcesoOffboarding,
8 en LiquidacionLaboral), lo que garantizaba inconsistencias al agregar
un motivo nuevo. Ahora:

  - `MOTIVO_CESE_CHOICES` es el catálogo canónico (el que ve RRHH al cesar).
  - `MOTIVOS_OFFBOARDING` y `MOTIVOS_LIQUIDACION` son las vistas reducidas
    que necesitan esos módulos (offboarding agrupa; liquidación distingue
    por efecto de cálculo legal, ej. DESPIDO_ARB → indemnización).
  - Los mapeos PERSONAL_A_* son explícitos y se validan al importar: si se
    agrega un motivo canónico sin mapear, el arranque falla en dev/test en
    lugar de producir un cese con motivo inconsistente en producción.

Los VALORES almacenados en BD no cambian: este módulo solo centraliza las
definiciones que antes vivían duplicadas en personal/models.py,
onboarding/models.py, nominas/models.py, nominas/signals.py,
personal/views/cese.py y personal/views/cesar.py.
"""

# ─── Catálogo canónico (Personal.motivo_cese) ────────────────────────────────
MOTIVO_CESE_CHOICES = [
    # Voluntarios
    ('RENUNCIA',         'Renuncia voluntaria'),
    ('MUTUO_ACUERDO',    'Mutuo acuerdo'),
    ('JUBILACION',       'Jubilacion'),
    # Por el empleador (DS 003-97-TR)
    ('VENCIMIENTO',      'Vencimiento de contrato'),
    ('TERMINO_CONTRATO', 'Termino de contrato'),
    ('NO_RENOVACION',    'No renovacion'),
    ('DESPIDO_CAUSA',    'Despido con causa justificada'),
    ('CESE_COLECTIVO',   'Cese colectivo'),
    ('LIQUIDACION',      'Liquidacion / Disolucion empresa'),
    # Especiales
    ('FALLECIMIENTO',    'Fallecimiento'),
    ('INVALIDEZ',        'Invalidez permanente'),
    ('ABANDONO',         'Abandono de trabajo'),
    ('OTRO',             'Otro'),
]

# ─── Vista reducida: ProcesoOffboarding.motivo_cese ──────────────────────────
MOTIVOS_OFFBOARDING = [
    ('RENUNCIA',      'Renuncia Voluntaria'),
    ('DESPIDO',       'Despido'),
    ('MUTUO_ACUERDO', 'Mutuo Acuerdo'),
    ('FIN_CONTRATO',  'Fin de Contrato'),
    ('JUBILACION',    'Jubilación'),
]

# ─── Vista de cálculo legal: LiquidacionLaboral.motivo_cese ──────────────────
MOTIVOS_LIQUIDACION = [
    ('RENUNCIA',       'Renuncia voluntaria'),
    ('DESPIDO',        'Despido (causa justa)'),
    ('DESPIDO_ARB',    'Despido arbitrario (indemnización)'),
    ('MUTUO',          'Mutuo disenso'),
    ('CADUCIDAD',      'Caducidad de contrato'),
    ('JUBILACION',     'Jubilación'),
    ('FALLECIMIENTO',  'Fallecimiento'),
    ('PERIODO_PRUEBA', 'No supera período de prueba'),
]

# ─── Mapeos canónico → vistas reducidas ──────────────────────────────────────
PERSONAL_A_OFFBOARDING = {
    'RENUNCIA':         'RENUNCIA',
    'MUTUO_ACUERDO':    'MUTUO_ACUERDO',
    'JUBILACION':       'JUBILACION',
    'VENCIMIENTO':      'FIN_CONTRATO',
    'TERMINO_CONTRATO': 'FIN_CONTRATO',
    'NO_RENOVACION':    'FIN_CONTRATO',
    'DESPIDO_CAUSA':    'DESPIDO',
    'CESE_COLECTIVO':   'DESPIDO',
    'LIQUIDACION':      'MUTUO_ACUERDO',
    'FALLECIMIENTO':    'FIN_CONTRATO',
    'INVALIDEZ':        'FIN_CONTRATO',
    'ABANDONO':         'DESPIDO',
    'OTRO':             'FIN_CONTRATO',
}

PERSONAL_A_LIQUIDACION = {
    'RENUNCIA':         'RENUNCIA',
    'MUTUO_ACUERDO':    'MUTUO',
    'JUBILACION':       'JUBILACION',
    'VENCIMIENTO':      'CADUCIDAD',
    'TERMINO_CONTRATO': 'CADUCIDAD',
    'NO_RENOVACION':    'CADUCIDAD',
    'DESPIDO_CAUSA':    'DESPIDO',
    'CESE_COLECTIVO':   'CADUCIDAD',
    'LIQUIDACION':      'CADUCIDAD',
    'FALLECIMIENTO':    'FALLECIMIENTO',
    'INVALIDEZ':        'JUBILACION',
    'ABANDONO':         'DESPIDO',
    'OTRO':             'RENUNCIA',
}

# Mapeo inverso liquidación → canónico (para el wizard de cese, que pide el
# motivo en términos de liquidación y debe persistir el canónico en Personal).
LIQUIDACION_A_PERSONAL = {
    'RENUNCIA':       'RENUNCIA',
    'DESPIDO':        'DESPIDO_CAUSA',
    'DESPIDO_ARB':    'DESPIDO_CAUSA',
    'MUTUO':          'MUTUO_ACUERDO',
    'CADUCIDAD':      'VENCIMIENTO',
    'JUBILACION':     'JUBILACION',
    'FALLECIMIENTO':  'FALLECIMIENTO',
    'PERIODO_PRUEBA': 'DESPIDO_CAUSA',
}


# ─── Validación de integridad al importar ────────────────────────────────────
def _codigos(choices):
    return {c for c, _ in choices}


_canonicos = _codigos(MOTIVO_CESE_CHOICES)
_off = _codigos(MOTIVOS_OFFBOARDING)
_liq = _codigos(MOTIVOS_LIQUIDACION)

assert set(PERSONAL_A_OFFBOARDING) == _canonicos, (
    'PERSONAL_A_OFFBOARDING desincronizado del catálogo canónico: '
    f'faltan {_canonicos - set(PERSONAL_A_OFFBOARDING)}, '
    f'sobran {set(PERSONAL_A_OFFBOARDING) - _canonicos}')
assert set(PERSONAL_A_LIQUIDACION) == _canonicos, (
    'PERSONAL_A_LIQUIDACION desincronizado del catálogo canónico: '
    f'faltan {_canonicos - set(PERSONAL_A_LIQUIDACION)}, '
    f'sobran {set(PERSONAL_A_LIQUIDACION) - _canonicos}')
assert set(PERSONAL_A_OFFBOARDING.values()) <= _off, (
    'PERSONAL_A_OFFBOARDING apunta a motivos inexistentes en MOTIVOS_OFFBOARDING')
assert set(PERSONAL_A_LIQUIDACION.values()) <= _liq, (
    'PERSONAL_A_LIQUIDACION apunta a motivos inexistentes en MOTIVOS_LIQUIDACION')
assert set(LIQUIDACION_A_PERSONAL) == _liq, (
    'LIQUIDACION_A_PERSONAL desincronizado de MOTIVOS_LIQUIDACION')
assert set(LIQUIDACION_A_PERSONAL.values()) <= _canonicos, (
    'LIQUIDACION_A_PERSONAL apunta a motivos inexistentes en el catálogo canónico')
