"""
Rubros (industrias) y sus presets de módulos.

Un rubro preconfigura qué módulos vienen encendidos por defecto para una
empresa/instancia (ej. construcción → Roster Matricial ON). El admin puede
luego hacer override de toggles puntuales (`ConfiguracionSistema.mod_*`).
El plan (core/planes.py) sigue siendo el techo de lo contratable.

Capas:  RUBRO (preset)  →  toggles mod_* (override)  →  PLAN (techo)
"""
from __future__ import annotations

GENERAL      = 'GENERAL'
GASTRONOMIA  = 'GASTRONOMIA'
CONSTRUCCION = 'CONSTRUCCION'
MINERIA      = 'MINERIA'
AUDIOVISUAL  = 'AUDIOVISUAL'

RUBRO_CHOICES = [
    (GENERAL,      'General / Oficina'),
    (GASTRONOMIA,  'Gastronomía'),
    (CONSTRUCCION, 'Construcción Civil'),
    (MINERIA,      'Minería'),
    (AUDIOVISUAL,  'Audiovisual / Agencia'),
]

# Rubros con jornada atípica (14x7/21x7 o turnos rotativos) → Roster ON por defecto.
RUBROS_CON_ROSTER = {GASTRONOMIA, CONSTRUCCION, MINERIA}

# Preset de flags por rubro. Solo se listan los que se ENCIENDEN respecto del
# default; el resto de módulos queda en su default de ConfiguracionSistema.
PRESETS: dict[str, dict] = {
    GENERAL:      {'mod_roster': False},
    AUDIOVISUAL:  {'mod_roster': False},
    GASTRONOMIA:  {'mod_roster': True, 'roster_aplica_a': 'TODOS'},
    CONSTRUCCION: {'mod_roster': True, 'roster_aplica_a': 'FORANEOS'},
    MINERIA:      {'mod_roster': True, 'roster_aplica_a': 'FORANEOS', 'mod_viaticos': True},
}


def preset_rubro(rubro: str) -> dict:
    """Devuelve el dict de flags a aplicar para un rubro (copia)."""
    return dict(PRESETS.get(rubro, {}))


def rubro_requiere_roster(rubro: str) -> bool:
    """True si el rubro implica jornada atípica y por tanto Roster Matricial."""
    return rubro in RUBROS_CON_ROSTER
