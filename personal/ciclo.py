"""
Ciclo de vida del empleado: etapas calculadas + metadata para la UI.

La etapa NO se guarda en BD: se DERIVA de datos que ya existen (Personal.estado,
Contrato vigente, ProcesoOnboarding, RegistroNomina, LiquidacionLaboral). Ver
`Personal.etapa_ciclo`. Esto evita doble captura y migraciones.

Etapas (codigo -> label, orden, color, icono FontAwesome):
    candidato  -> Postulacion activa sin convertir (vive en reclutamiento)
    contratado -> Personal creado, sin contrato vigente / aun Inactivo
    onboarding -> ProcesoOnboarding EN_CURSO
    activo     -> Activo con contrato vigente y onboarding terminado
    cese       -> Cesado, liquidacion no cerrada
    cerrado    -> Cesado, liquidacion PAGADA/CERRADA
"""

# codigo -> (label, orden, color hex, icono)
ETAPAS = {
    'candidato':  ('Candidato',     0, '#94a3b8', 'fa-user-plus'),
    'contratado': ('Contratado',    1, '#0ea5e9', 'fa-file-signature'),
    'onboarding': ('En onboarding', 2, '#a855f7', 'fa-clipboard-check'),
    'activo':     ('Activo',        3, '#22c55e', 'fa-user-check'),
    'cese':       ('En cese',       4, '#f59e0b', 'fa-door-open'),
    'cerrado':    ('Cerrado',       5, '#64748b', 'fa-lock'),
}

# Nodos del ciclo en orden, para dibujar la barra de estado.
ETAPAS_ORDEN = ['candidato', 'contratado', 'onboarding', 'activo', 'cese', 'cerrado']


def etapa_info(code):
    """Metadata de una etapa. Cae a 'activo' si el code es desconocido."""
    label, orden, color, icono = ETAPAS.get(code, ETAPAS['activo'])
    return {'code': code, 'label': label, 'orden': orden, 'color': color, 'icono': icono}


def barra_etapas(actual):
    """Lista de nodos para la barra de estado, marcando pasado/actual/futuro.

    Para empleados (no candidatos) empezamos la barra en 'contratado'.
    """
    info_actual = etapa_info(actual)
    orden_actual = info_actual['orden']
    nodos = []
    for code in ETAPAS_ORDEN:
        if code == 'candidato' and actual != 'candidato':
            continue  # la barra del empleado arranca en Contratado
        info = etapa_info(code)
        if info['orden'] < orden_actual:
            estado = 'pasado'
        elif info['orden'] == orden_actual:
            estado = 'actual'
        else:
            estado = 'futuro'
        nodos.append({**info, 'estado': estado})
    return nodos
