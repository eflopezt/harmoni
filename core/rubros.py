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

# Preset de flags MODULARES OPERATIVOS por rubro. Se listan los toggles que
# varían por giro (Roster, viáticos, documentos). Los módulos de nivel superior
# (evaluaciones, capacitaciones, reclutamiento, etc.) NO se tocan aquí: los
# gobierna el PLAN (core/planes.py), que es el techo.
PRESETS: dict[str, dict] = {
    GENERAL:      {'mod_roster': False, 'mod_viaticos': False},
    AUDIOVISUAL:  {'mod_roster': False, 'mod_viaticos': False},
    GASTRONOMIA:  {'mod_roster': True,  'roster_aplica_a': 'TODOS',    'mod_viaticos': False},
    CONSTRUCCION: {'mod_roster': True,  'roster_aplica_a': 'FORANEOS', 'mod_viaticos': True},
    MINERIA:      {'mod_roster': True,  'roster_aplica_a': 'FORANEOS', 'mod_viaticos': True},
}

# Régimen laboral por defecto para trabajadores nuevos según el rubro
# (enlaza con nominas: construcción/minería tienen estrategia de cálculo propia).
REGIMEN_DEFAULT: dict[str, str] = {
    CONSTRUCCION: 'CONSTRUCCION',
    MINERIA:      'MINERIA',
}


def preset_rubro(rubro: str) -> dict:
    """Devuelve el dict de flags a aplicar para un rubro (copia)."""
    return dict(PRESETS.get(rubro, {}))


def rubro_requiere_roster(rubro: str) -> bool:
    """True si el rubro implica jornada atípica y por tanto Roster Matricial."""
    return rubro in RUBROS_CON_ROSTER


def regimen_default(rubro: str) -> str:
    """Régimen laboral por defecto para el rubro (GENERAL si no aplica)."""
    return REGIMEN_DEFAULT.get(rubro, 'GENERAL')


def aplicar_preset(config, rubro: str) -> list:
    """Fija `config.rubro` y aplica su preset de módulos sobre una
    ConfiguracionSistema (sin guardar). Devuelve la lista de campos cambiados.
    """
    config.rubro = rubro
    cambios = ['rubro']
    for campo, valor in preset_rubro(rubro).items():
        if hasattr(config, campo):
            setattr(config, campo, valor)
            cambios.append(campo)
    return list(dict.fromkeys(cambios))
