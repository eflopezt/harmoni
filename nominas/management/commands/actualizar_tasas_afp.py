"""
Actualiza las tasas AFP en ConfiguracionSistema sin redeploy.

SBS publica nuevas tasas cada cuatrimestre. Este comando permite cargarlas
al sistema vía CLI sin tocar código ni reiniciar el container.

Uso:
    # Aplicar valores predeterminados Q2 2026 (lo mismo que el engine hardcoded)
    python manage.py actualizar_tasas_afp --vigencia "Q2-2026"

    # Personalizar:
    python manage.py actualizar_tasas_afp \\
        --vigencia "Q3-2026" \\
        --habitat 1.50 1.74 \\
        --integra 1.58 1.74 \\
        --prima 1.62 1.74 \\
        --profuturo 1.70 1.74 \\
        --tope-rma 12500.00

    # Borrar override (volver a hardcoded):
    python manage.py actualizar_tasas_afp --reset
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError


# Defaults Q2 2026 (Resolución SBS vigente abril-julio 2026)
TASAS_Q2_2026 = {
    'Habitat':   {'comision_flujo': '1.47', 'seguro': '1.74'},
    'Integra':   {'comision_flujo': '1.55', 'seguro': '1.74'},
    'Prima':     {'comision_flujo': '1.60', 'seguro': '1.74'},
    'Profuturo': {'comision_flujo': '1.69', 'seguro': '1.74'},
}
TOPE_RMA_Q2_2026 = Decimal('12131.49')


class Command(BaseCommand):
    help = (
        "Actualiza tasas AFP (comisión flujo + prima seguro) en "
        "ConfiguracionSistema. Sin redeploy."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--vigencia', type=str, default='',
            help='Etiqueta de vigencia (ej. "Q2-2026" o "2026-04 a 2026-07").',
        )
        parser.add_argument(
            '--habitat', nargs=2, metavar=('COMISION', 'SEGURO'),
            help='Tasas Habitat: comision_flujo seguro (ej. 1.47 1.74).',
        )
        parser.add_argument(
            '--integra', nargs=2, metavar=('COMISION', 'SEGURO'),
        )
        parser.add_argument(
            '--prima', nargs=2, metavar=('COMISION', 'SEGURO'),
        )
        parser.add_argument(
            '--profuturo', nargs=2, metavar=('COMISION', 'SEGURO'),
        )
        parser.add_argument(
            '--tope-rma', type=str, default='',
            help='Remuneración Máxima Asegurable (ej. 12131.49). '
                 'Si no se especifica, mantiene el valor actual.',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help='Borra el override → vuelve a usar valores hardcoded del engine.',
        )
        parser.add_argument(
            '--mostrar', action='store_true',
            help='Solo muestra la configuración actual sin modificar.',
        )

    def handle(self, *args, **opts):
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()

        if opts['mostrar']:
            self._mostrar(config)
            return

        if opts['reset']:
            config.afp_tasas_override = None
            config.afp_tope_rma = None
            config.afp_tasas_vigencia = ''
            config.save(update_fields=[
                'afp_tasas_override', 'afp_tope_rma', 'afp_tasas_vigencia',
            ])
            self.stdout.write(self.style.SUCCESS(
                'Override AFP borrado. El engine volverá a usar tasas hardcoded.'
            ))
            return

        # Construir override
        override = dict(config.afp_tasas_override or TASAS_Q2_2026)

        # Aplicar valores específicos por AFP
        for afp_arg, afp_name in [
            ('habitat', 'Habitat'),
            ('integra', 'Integra'),
            ('prima', 'Prima'),
            ('profuturo', 'Profuturo'),
        ]:
            v = opts.get(afp_arg)
            if v:
                try:
                    comision = Decimal(v[0])
                    seguro = Decimal(v[1])
                except Exception as e:
                    raise CommandError(
                        f'--{afp_arg}: valores inválidos. Esperaba 2 decimales. '
                        f'Recibido: {v}. Error: {e}'
                    )
                # Validación rango razonable
                if not (Decimal('0.50') <= comision <= Decimal('3.00')):
                    raise CommandError(
                        f'--{afp_arg}: comisión {comision}% fuera de rango razonable '
                        '(0.50% - 3.00%). Verificar valor.'
                    )
                if not (Decimal('1.00') <= seguro <= Decimal('2.50')):
                    raise CommandError(
                        f'--{afp_arg}: prima seguro {seguro}% fuera de rango '
                        'razonable (1.00% - 2.50%). Verificar valor.'
                    )
                override[afp_name] = {
                    'comision_flujo': str(comision),
                    'seguro': str(seguro),
                }
                self.stdout.write(
                    f'  {afp_name}: comisión {comision}% / seguro {seguro}%'
                )

        config.afp_tasas_override = override

        # Tope RMA
        if opts['tope_rma']:
            try:
                config.afp_tope_rma = Decimal(opts['tope_rma'])
                self.stdout.write(f'  Tope RMA: S/ {config.afp_tope_rma}')
            except Exception as e:
                raise CommandError(f'--tope-rma inválido: {e}')

        # Vigencia
        if opts['vigencia']:
            config.afp_tasas_vigencia = opts['vigencia']

        config.save(update_fields=[
            'afp_tasas_override', 'afp_tope_rma', 'afp_tasas_vigencia',
        ])

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Tasas AFP actualizadas. Vigencia: {config.afp_tasas_vigencia or "—"}'
        ))
        self.stdout.write('')
        self.stdout.write(
            'NOTA: las planillas YA calculadas mantienen sus valores. '
            'Para regenerar, ejecuta:'
        )
        self.stdout.write(
            '  python manage.py shell -c "from nominas.engine import generar_periodo; '
            'from nominas.models import PeriodoNomina; '
            '[generar_periodo(p) for p in PeriodoNomina.objects.filter(estado=\'CALCULADO\')]"'
        )

    def _mostrar(self, config):
        """Muestra la configuración actual."""
        from nominas.engine import AFP_TASAS, AFP_TOPE_REM_ASEGURABLE
        self.stdout.write('═' * 60)
        self.stdout.write('  TASAS AFP ACTIVAS')
        self.stdout.write('═' * 60)

        override = config.afp_tasas_override
        if override:
            self.stdout.write(self.style.SUCCESS(
                f'  Override activo (vigencia: {config.afp_tasas_vigencia or "—"})'
            ))
            tasas_efectivas = override
        else:
            self.stdout.write(
                '  Sin override — usando hardcoded del engine'
            )
            tasas_efectivas = AFP_TASAS

        self.stdout.write('')
        self.stdout.write(
            f'  {"AFP":12} {"Comisión":>10} {"Prima Seg.":>12}'
        )
        self.stdout.write('  ' + '-' * 36)
        for afp, t in tasas_efectivas.items():
            comision = t.get('comision_flujo') if isinstance(t, dict) else t['comision_flujo']
            seguro = t.get('seguro') if isinstance(t, dict) else t['seguro']
            self.stdout.write(
                f'  {afp:12} {str(comision)+"%":>10} {str(seguro)+"%":>12}'
            )

        self.stdout.write('')
        tope = config.afp_tope_rma or AFP_TOPE_REM_ASEGURABLE
        marker = '(override)' if config.afp_tope_rma else '(hardcoded)'
        self.stdout.write(f'  Tope RMA: S/ {tope}  {marker}')
        self.stdout.write('')
