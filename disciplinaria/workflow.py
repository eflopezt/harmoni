"""
Workflow escalonado para medidas disciplinarias.

Sugiere la siguiente medida (verbal → escrita → suspensión → despido) en base
al historial del trabajador para un tipo de falta determinado.

Base legal:
- DS 003-97-TR (TUO DL 728): Art. 24-28 faltas, Art. 31 procedimiento.
- Principio de proporcionalidad y razonabilidad — la sanción debe ser
  progresiva, salvo faltas graves que admitan despido directo.

Las claves de ESCALAS se relacionan a códigos de TipoFalta (o se infieren
por gravedad). El llamador puede pasar un código directo o un tipo lógico:

    sugerir_proxima_medida(personal, 'TARDANZA')
    sugerir_proxima_medida(personal, tipo_falta_obj)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────
# DEFINICIÓN DE ESCALAS
# Niveles lógicos:
#   VERBAL          → Amonestación verbal (tipo_medida='VERBAL')
#   ESCRITA         → Memorándum / carta de amonestación
#                     (tipo_medida='ESCRITA')
#   SUSPENSION_1D   → Suspensión sin goce 1 día
#                     (tipo_medida='SUSPENSION', dias=1)
#   SUSPENSION_3D   → Suspensión sin goce 3 días
#                     (tipo_medida='SUSPENSION', dias=3)
#   DESPIDO         → Despido con causa justa (tipo_medida='DESPIDO')
# ──────────────────────────────────────────────────────────────

ESCALAS: Dict[str, List[str]] = {
    'TARDANZA':       ['VERBAL', 'ESCRITA', 'SUSPENSION_1D', 'SUSPENSION_3D'],
    'FALTA_INJ':      ['ESCRITA', 'SUSPENSION_1D', 'SUSPENSION_3D', 'DESPIDO'],
    'INCUMPLIMIENTO': ['VERBAL', 'ESCRITA', 'SUSPENSION_3D', 'DESPIDO'],
    'INDISCIPLINA':   ['ESCRITA', 'SUSPENSION_1D', 'SUSPENSION_3D', 'DESPIDO'],
    'HIGIENE':        ['VERBAL', 'ESCRITA', 'SUSPENSION_3D'],   # gastro-specific
    'FALTA_GRAVE':    ['SUSPENSION_3D', 'DESPIDO'],
}

ESCALA_DEFAULT = 'INCUMPLIMIENTO'

# Etiquetas user-friendly para los niveles lógicos
NIVEL_LABELS = {
    'VERBAL':        'Amonestación Verbal',
    'ESCRITA':       'Amonestación Escrita / Memorándum',
    'SUSPENSION_1D': 'Suspensión sin goce — 1 día',
    'SUSPENSION_3D': 'Suspensión sin goce — 3 días',
    'DESPIDO':       'Despido con causa justa',
}

# Mapeo de cada nivel lógico a (tipo_medida, dias_suspension)
NIVEL_TO_TIPO_MEDIDA = {
    'VERBAL':        ('VERBAL', 0),
    'ESCRITA':       ('ESCRITA', 0),
    'SUSPENSION_1D': ('SUSPENSION', 1),
    'SUSPENSION_3D': ('SUSPENSION', 3),
    'DESPIDO':       ('DESPIDO', 0),
}

# Mapeo (tipo_medida, dias_suspension) → nivel lógico
def _tipo_a_nivel(tipo_medida: str, dias_suspension: int = 0) -> str:
    if tipo_medida == 'VERBAL':
        return 'VERBAL'
    if tipo_medida == 'ESCRITA':
        return 'ESCRITA'
    if tipo_medida == 'SUSPENSION':
        return 'SUSPENSION_3D' if dias_suspension and dias_suspension >= 2 else 'SUSPENSION_1D'
    if tipo_medida == 'DESPIDO':
        return 'DESPIDO'
    return 'VERBAL'


# Diccionario auxiliar: tipo_falta.codigo o slug → clave de escala
# Se pueden agregar más mappings sin tocar la lógica.
CODIGO_A_ESCALA = {
    'tardanza':                        'TARDANZA',
    'inasistencia-injustificada':      'FALTA_INJ',
    'abandono':                        'FALTA_GRAVE',
    'incumplimiento-obligaciones':     'INCUMPLIMIENTO',
    'disminucion-rendimiento':         'INCUMPLIMIENTO',
    'vestimenta':                      'HIGIENE',
    'higiene':                         'HIGIENE',
    'incumplimiento-ssoma':            'INCUMPLIMIENTO',
    'falta-respeto-menor':             'INDISCIPLINA',
    'uso-indebido-equipos':            'INDISCIPLINA',
    'embriaguez':                      'FALTA_GRAVE',
    'violencia':                       'FALTA_GRAVE',
    'apropiacion-bienes':              'FALTA_GRAVE',
    'dano-bienes':                     'FALTA_GRAVE',
    'hostigamiento-sexual':            'FALTA_GRAVE',
    'info-indebida':                   'FALTA_GRAVE',
}


def resolver_clave_escala(tipo_falta_or_codigo: Any) -> str:
    """
    Resuelve la clave de ESCALAS a partir de:
      - un str que ya es una clave (ej: 'TARDANZA')
      - un str que es un código de TipoFalta (ej: 'tardanza')
      - una instancia de TipoFalta (usa .codigo o .gravedad)
    """
    if tipo_falta_or_codigo is None:
        return ESCALA_DEFAULT

    # ── String directo ──
    if isinstance(tipo_falta_or_codigo, str):
        clave = tipo_falta_or_codigo.strip()
        if clave in ESCALAS:
            return clave
        # Buscar por código
        clave_norm = clave.lower().replace('_', '-')
        if clave_norm in CODIGO_A_ESCALA:
            return CODIGO_A_ESCALA[clave_norm]
        return ESCALA_DEFAULT

    # ── Instancia TipoFalta ──
    codigo = getattr(tipo_falta_or_codigo, 'codigo', '') or ''
    if codigo in CODIGO_A_ESCALA:
        return CODIGO_A_ESCALA[codigo]

    # Fallback por gravedad
    gravedad = getattr(tipo_falta_or_codigo, 'gravedad', '')
    if gravedad == 'MUY_GRAVE':
        return 'FALTA_GRAVE'
    if gravedad == 'GRAVE':
        return 'INCUMPLIMIENTO'
    return 'TARDANZA'  # leve


def sugerir_proxima_medida(personal, tipo_falta_or_codigo: Any) -> Dict[str, Any]:
    """
    Calcula la siguiente medida en la escala basado en el historial.

    Cuenta cuántas medidas del mismo tipo de escala se han aplicado al
    trabajador (excluyendo ANULADAS), y devuelve el siguiente nivel.

    Returns:
        {
            'nivel':           'ESCRITA',          # nivel lógico
            'tipo_medida':     'ESCRITA',          # campo MedidaDisciplinaria.tipo_medida
            'dias_suspension': 0,
            'label':           'Amonestación Escrita / Memorándum',
            'escala':          'TARDANZA',
            'index':           1,                  # 0-based
            'total_previas':   1,
            'escala_completa': True,               # si llegó al último nivel
            'historial_resumen': [{'nivel': 'VERBAL', 'fecha': ...}, ...],
        }
    """
    from .models import MedidaDisciplinaria

    clave = resolver_clave_escala(tipo_falta_or_codigo)
    escala = ESCALAS.get(clave, ESCALAS[ESCALA_DEFAULT])

    # Contar medidas previas del mismo trabajador en esta escala
    # (no anuladas, ni borrador opcional)
    estados_validos = ['NOTIFICADA', 'EN_DESCARGO', 'DESCARGO_RECIBIDO', 'RESUELTA']
    historial_qs = MedidaDisciplinaria.objects.none()
    try:
        historial_qs = MedidaDisciplinaria.objects.filter(
            personal=personal,
            estado__in=estados_validos,
        ).order_by('fecha_hechos')
    except Exception:
        # Caso raro: si personal no es válido, fallback a 0 previas
        pass

    # Filtrar histórico por tipo_falta de la misma escala lógica
    historial_resumen: List[Dict[str, Any]] = []
    previas_escala = 0
    for m in historial_qs:
        try:
            clave_m = resolver_clave_escala(m.tipo_falta)
        except Exception:
            clave_m = ESCALA_DEFAULT
        if clave_m == clave:
            previas_escala += 1
            historial_resumen.append({
                'nivel': _tipo_a_nivel(m.tipo_medida, m.dias_suspension or 0),
                'fecha': m.fecha_hechos,
                'tipo_medida': m.tipo_medida,
            })

    # Index siguiente nivel
    index = min(previas_escala, len(escala) - 1)
    nivel = escala[index]
    tipo_medida, dias = NIVEL_TO_TIPO_MEDIDA[nivel]

    return {
        'nivel': nivel,
        'tipo_medida': tipo_medida,
        'dias_suspension': dias,
        'label': NIVEL_LABELS.get(nivel, nivel),
        'escala': clave,
        'index': index,
        'total_previas': previas_escala,
        'escala_completa': index >= len(escala) - 1,
        'historial_resumen': historial_resumen,
    }


def descripcion_escala(clave: str) -> List[Dict[str, str]]:
    """Devuelve la escala resuelta como lista de {nivel, label}."""
    escala = ESCALAS.get(clave, ESCALAS[ESCALA_DEFAULT])
    return [
        {'nivel': n, 'label': NIVEL_LABELS.get(n, n)}
        for n in escala
    ]
