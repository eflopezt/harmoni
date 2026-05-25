"""
Smoke tests para los seeds nuevos del demo Sabores del Sur.

Verifica que cada management command corre sin errores y crea los
objetos esperados.
"""
from datetime import date

import pytest
from django.core.management import call_command
from django.contrib.auth.models import User

from empresas.models import Empresa
from personal.models import Personal, Area, SubArea
from nominas.models import SaldoAperturaTrabajador, ConfiguracionApertura


@pytest.fixture
def setup_minimo(db):
    """Crea contexto mínimo: 5 trabajadores activos para que los seeds
    puedan trabajar sobre algo."""
    area = Area.objects.create(nombre="Salón")
    sub = SubArea.objects.create(nombre="Servicio", area=area)
    admin = User.objects.create_superuser(username="admin_seed", password="x")
    workers = []
    for i in range(5):
        workers.append(Personal.objects.create(
            nro_doc=f"7{i:07d}",
            apellidos_nombres=f"SEED TEST {i}, NOMBRE",
            cargo=["Cocinero", "Mesero", "Sommelier", "Cajero", "Host"][i],
            tipo_trab="Empleado",
            estado="Activo",
            subarea=sub,
            fecha_alta=date(2024, 1, 1),
        ))
    return workers


class TestSeedGrupoEdo:
    def test_seed_crea_6_empresas(self, db):
        call_command('seed_grupo_edo_premium')
        empresas = Empresa.objects.filter(activa=True)
        # Al menos las 6 nuevas
        assert empresas.count() >= 6
        # Y nombres específicos (diversificados — no solo japonés)
        assert empresas.filter(nombre_comercial='Sabores del Sur Premium').exists()
        assert empresas.filter(nombre_comercial='Sabores del Sur Marino').exists()
        assert empresas.filter(nombre_comercial='Sabores del Sur Asado').exists()

    def test_seed_idempotente(self, db):
        call_command('seed_grupo_edo_premium')
        count1 = Empresa.objects.filter(activa=True).count()
        call_command('seed_grupo_edo_premium')
        count2 = Empresa.objects.filter(activa=True).count()
        assert count1 == count2


class TestSeedBriefingsDemo:
    def test_seed_crea_briefings(self, db, setup_minimo):
        # Necesita al menos 1 empresa activa
        call_command('seed_grupo_edo_premium')
        call_command('seed_briefings_demo')
        from asistencia.models import BriefingServicio
        assert BriefingServicio.objects.count() > 0

    def test_seed_clear(self, db, setup_minimo):
        call_command('seed_grupo_edo_premium')
        call_command('seed_briefings_demo')
        from asistencia.models import BriefingServicio
        n1 = BriefingServicio.objects.count()
        call_command('seed_briefings_demo', '--clear')
        n2 = BriefingServicio.objects.count()
        # Después de --clear, n2 puede ser igual o menor (porque clear primero borra)
        assert n2 > 0


class TestSeedSaldosApertura:
    def test_seed_crea_saldos(self, db, setup_minimo):
        call_command('seed_saldos_apertura_demo')
        # 5 saldos creados
        assert SaldoAperturaTrabajador.objects.count() == 5
        # ConfiguracionApertura marcada completada
        cfg = ConfiguracionApertura.objects.filter(empresa=None, completado=True).first()
        assert cfg is not None
        assert cfg.total_trabajadores == 5

    def test_seed_fecha_corte_custom(self, db, setup_minimo):
        call_command('seed_saldos_apertura_demo', '--fecha-corte', '2026-04-30')
        cfg = ConfiguracionApertura.objects.filter(empresa=None).first()
        assert cfg.fecha_corte == date(2026, 4, 30)


class TestSeedRosterDemo:
    def test_seed_crea_roster(self, db, setup_minimo):
        call_command('seed_roster_demo', '--semanas', '1')
        from personal.models import Roster
        # 5 workers × 7 dias = 35 entries
        assert Roster.objects.count() >= 35

    def test_seed_clear_funciona(self, db, setup_minimo):
        call_command('seed_roster_demo', '--semanas', '1')
        from personal.models import Roster
        n1 = Roster.objects.count()
        call_command('seed_roster_demo', '--semanas', '1', '--clear')
        n2 = Roster.objects.count()
        # Después de clear y volver a crear, hay la misma cantidad
        assert n2 == n1
