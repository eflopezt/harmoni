"""
Management command: poblar_asistencia_roster

Puebla los contadores de asistencia (dias_trabajados/dias_descanso/dias_falta,
y opcionalmente horas extra) de todos los RegistroNomina de un período, leyendo
el Roster (y el Tareo real). Cierra la brecha Roster → Nómina.

La convención de "día trabajado" se elige por régimen del trabajador:
  - CONSTRUCCION → 'jornal' (se paga por día efectivamente trabajado)
  - resto        → 'mensual' (30 − faltas)

Ejemplos:
  python manage.py poblar_asistencia_roster --periodo 12
  python manage.py poblar_asistencia_roster --periodo 12 --con-tareo --dry-run
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Puebla asistencia de un período de nómina desde el Roster (y Tareo).'

    def add_arguments(self, parser):
        parser.add_argument('--periodo', type=int, required=True,
                            help='ID del PeriodoNomina a poblar.')
        parser.add_argument('--con-tareo', action='store_true',
                            help='También puebla horas extra desde el Tareo real.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra lo que haría sin guardar.')

    def handle(self, *args, **opts):
        from nominas.models import PeriodoNomina
        from nominas.regimenes import regimen_de_calculo, CALC_CONSTRUCCION
        from nominas.services.asistencia_link import (
            poblar_registro_desde_roster, poblar_he_desde_tareo,
        )

        try:
            periodo = PeriodoNomina.objects.get(pk=opts['periodo'])
        except PeriodoNomina.DoesNotExist:
            raise CommandError(f'No existe PeriodoNomina id={opts["periodo"]}.')

        registros = periodo.registros.select_related('personal').all()
        if not registros:
            self.stdout.write(self.style.WARNING('El período no tiene registros.'))
            return

        guardar = not opts['dry_run']
        n = 0
        for reg in registros:
            convencion = 'jornal' if regimen_de_calculo(reg) == CALC_CONSTRUCCION else 'mensual'
            resumen = poblar_registro_desde_roster(reg, convencion=convencion, guardar=guardar)
            if opts['con_tareo']:
                poblar_he_desde_tareo(reg, guardar=guardar)
            n += 1
            if opts['dry_run'] and n <= 20:
                self.stdout.write(
                    f'  {reg.personal} [{convencion}] → trab={reg.dias_trabajados} '
                    f'desc={reg.dias_descanso} falta={reg.dias_falta} '
                    f'(roster: {resumen["trabajados"]}T/{resumen["descanso"]}D/'
                    f'{resumen["falta"]}F, sin_registro={resumen["sin_registro"]})'
                )

        estilo = self.style.WARNING if opts['dry_run'] else self.style.SUCCESS
        self.stdout.write(estilo(
            f'{"[DRY RUN] " if opts["dry_run"] else ""}Procesados {n} registros '
            f'del período {periodo}.'
        ))
