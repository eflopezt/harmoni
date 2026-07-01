"""
Management command: seed_demo_rubro

Configura la instancia actual como DEMO de un rubro: fija el rubro (aplica su
preset de módulos) y corre los seeds propios del giro. Pensado para levantar
demos por rubro (una instancia por rubro: construccion.demo, mineria.demo, ...),
alineado con provision_enterprise_client --rubro.

Uso:
  python manage.py seed_demo_rubro --rubro CONSTRUCCION
  python manage.py seed_demo_rubro --rubro MINERIA
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand


# Seeds específicos a correr por rubro (los que existan).
SEEDS_POR_RUBRO = {
    'CONSTRUCCION': ['seed_construccion'],
    'MINERIA':      ['seed_mineria'],
    'GASTRONOMIA':  [],   # ya cubierto por seed_demo_gastronomia
    'AUDIOVISUAL':  [],   # ya cubierto por seed_demo_audiovisual
    'GENERAL':      [],
}


class Command(BaseCommand):
    help = 'Configura la instancia como demo de un rubro (rubro + preset + seeds).'

    def add_arguments(self, parser):
        from core.rubros import RUBRO_CHOICES
        parser.add_argument('--rubro', required=True,
                            choices=[c[0] for c in RUBRO_CHOICES])

    def handle(self, *args, **opts):
        rubro = opts['rubro']

        # 1. Fijar rubro + aplicar preset de módulos (enciende Roster/viáticos).
        call_command('configurar_rubro', '--rubro', rubro, verbosity=0)

        # 2. Seeds propios del rubro (conceptos, tablas, etc.).
        corridos = []
        for seed in SEEDS_POR_RUBRO.get(rubro, []):
            try:
                call_command(seed, verbosity=0)
                corridos.append(seed)
            except Exception as exc:  # noqa: BLE001 — un seed opcional no debe abortar
                self.stdout.write(self.style.WARNING(f'  seed {seed} falló: {exc}'))

        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        self.stdout.write(self.style.SUCCESS(
            f'Demo configurada como rubro {rubro}. Roster activo: {config.roster_activo()}. '
            f'Seeds: {", ".join(corridos) or "ninguno específico"}.'
        ))
