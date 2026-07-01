"""
Management command: configurar_rubro

Fija el rubro de la instancia (ConfiguracionSistema) y aplica su preset de
módulos (ver core/rubros.py). Ej. construcción/minería encienden el Roster.

Uso:
  python manage.py configurar_rubro --rubro CONSTRUCCION
  python manage.py configurar_rubro --rubro GENERAL --no-preset   # solo fija el rubro
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Fija el rubro de la instancia y aplica su preset de módulos.'

    def add_arguments(self, parser):
        from core.rubros import RUBRO_CHOICES
        parser.add_argument('--rubro', required=True,
                            choices=[c[0] for c in RUBRO_CHOICES],
                            help='Rubro a fijar.')
        parser.add_argument('--no-preset', action='store_true',
                            help='No aplica el preset de módulos; solo fija el rubro.')

    def handle(self, *args, **opts):
        from asistencia.models import ConfiguracionSistema
        from core.rubros import aplicar_preset

        rubro = opts['rubro']
        config = ConfiguracionSistema.get()

        if opts['no_preset']:
            config.rubro = rubro
            cambios = ['rubro']
        else:
            cambios = aplicar_preset(config, rubro)

        config.save(update_fields=cambios)
        self.stdout.write(self.style.SUCCESS(
            f'Rubro fijado en {rubro}. Roster activo: {config.roster_activo()}. '
            f'Campos actualizados: {", ".join(dict.fromkeys(cambios))}.'
        ))
