"""
Tests de rubro + presets + roster_activo (core/rubros.py, ConfiguracionSistema).
"""
import pytest

from core import rubros


# ── Pure ───────────────────────────────────────────────────────────

def test_preset_construccion_enciende_roster():
    p = rubros.preset_rubro('CONSTRUCCION')
    assert p['mod_roster'] is True
    assert p['roster_aplica_a'] == 'FORANEOS'


def test_preset_general_apaga_roster():
    assert rubros.preset_rubro('GENERAL').get('mod_roster') is False


def test_rubro_requiere_roster():
    assert rubros.rubro_requiere_roster('MINERIA')
    assert rubros.rubro_requiere_roster('GASTRONOMIA')
    assert not rubros.rubro_requiere_roster('GENERAL')
    assert not rubros.rubro_requiere_roster('AUDIOVISUAL')


def test_regimen_default_por_rubro():
    assert rubros.regimen_default('CONSTRUCCION') == 'CONSTRUCCION'
    assert rubros.regimen_default('MINERIA') == 'MINERIA'
    assert rubros.regimen_default('GASTRONOMIA') == 'GENERAL'
    assert rubros.regimen_default('GENERAL') == 'GENERAL'


class _FakeConfig:
    rubro = 'GENERAL'
    mod_roster = False
    mod_viaticos = False
    roster_aplica_a = 'FORANEOS'


def test_aplicar_preset_construccion():
    c = _FakeConfig()
    cambios = rubros.aplicar_preset(c, 'CONSTRUCCION')
    assert c.rubro == 'CONSTRUCCION'
    assert c.mod_roster is True
    assert c.roster_aplica_a == 'FORANEOS'
    assert c.mod_viaticos is True
    assert 'rubro' in cambios and 'mod_roster' in cambios


# ── roster_activo (DB) ─────────────────────────────────────────────

@pytest.mark.django_db
def test_roster_activo_por_rubro():
    from asistencia.models import ConfiguracionSistema
    c = ConfiguracionSistema.get()

    c.rubro = 'GENERAL'; c.mod_roster = False; c.save()
    assert c.roster_activo() is False

    c.rubro = 'CONSTRUCCION'; c.save()
    assert c.roster_activo() is True   # el rubro lo enciende

    c.rubro = 'GENERAL'; c.mod_roster = True; c.save()
    assert c.roster_activo() is True   # toggle explícito


@pytest.mark.django_db
def test_roster_activo_por_regimen_acumulativo():
    from asistencia.models import ConfiguracionSistema, RegimenTurno
    c = ConfiguracionSistema.get()
    c.rubro = 'GENERAL'; c.mod_roster = False; c.save()
    assert c.roster_activo() is False

    # Existe un régimen de turno acumulativo (14x7) → Roster necesario
    RegimenTurno.objects.create(
        nombre='14x7 Foráneo', codigo='14X7', jornada_tipo='ACUMULATIVA',
        dias_trabajo_ciclo=14, dias_descanso_ciclo=7, activo=True,
    )
    assert c.roster_activo() is True


@pytest.mark.django_db
def test_personalform_regimen_default_por_rubro():
    """R5: al crear un trabajador nuevo, regimen_laboral viene del rubro."""
    from asistencia.models import ConfiguracionSistema
    from personal.forms import PersonalForm

    c = ConfiguracionSistema.get()
    c.rubro = 'CONSTRUCCION'; c.save()
    assert PersonalForm().initial.get('regimen_laboral') == 'CONSTRUCCION'

    c.rubro = 'MINERIA'; c.save()
    assert PersonalForm().initial.get('regimen_laboral') == 'MINERIA'

    c.rubro = 'GENERAL'; c.save()
    assert PersonalForm().initial.get('regimen_laboral') == 'GENERAL'


@pytest.mark.django_db
def test_comando_configurar_rubro_aplica_preset():
    from django.core.management import call_command
    from asistencia.models import ConfiguracionSistema

    call_command('configurar_rubro', '--rubro', 'MINERIA', verbosity=0)
    c = ConfiguracionSistema.get()
    assert c.rubro == 'MINERIA'
    assert c.mod_roster is True
    assert c.mod_viaticos is True
    assert c.roster_aplica_a == 'FORANEOS'


@pytest.mark.django_db
def test_seed_demo_rubro_construccion():
    """R4: seed_demo_rubro configura rubro + corre el seed del giro."""
    from django.core.management import call_command
    from asistencia.models import ConfiguracionSistema
    from nominas.models import JornalConstruccion

    call_command('seed_demo_rubro', '--rubro', 'CONSTRUCCION', verbosity=0)
    c = ConfiguracionSistema.get()
    assert c.rubro == 'CONSTRUCCION'
    assert c.mod_roster is True
    assert JornalConstruccion.objects.count() > 0   # corrió seed_construccion
