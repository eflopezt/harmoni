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
        from core.rubros import preset_rubro

        rubro = opts['rubro']
        config = ConfiguracionSistema.get()
        config.rubro = rubro
        cambios = ['rubro']

        if not opts['no_preset']:
            for campo, valor in preset_rubro(rubro).items():
                if hasattr(config, campo):
                    setattr(config, campo, valor)
                    cambios.append(campo)

        config.save(update_fields=list(dict.fromkeys(cambios)))
        self.stdout.write(self.style.SUCCESS(
            f'Rubro fijado en {rubro}. Roster activo: {config.roster_activo()}. '
            f'Campos actualizados: {", ".join(dict.fromkeys(cambios))}.'
        ))
