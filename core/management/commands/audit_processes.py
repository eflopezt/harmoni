"""Audita bloqueos del ciclo de personas usando la misma logica de la UI."""
import json
from types import SimpleNamespace

from django.core.management.base import BaseCommand, CommandError

from core.process_journey import build_process_journey
from empresas.models import Empresa


class _PlatformUser:
    is_authenticated = True
    is_superuser = True


class Command(BaseCommand):
    help = 'Audita Preparar→Atraer→Incorporar→Operar→Pagar→Desvincular.'

    def add_arguments(self, parser):
        parser.add_argument('--empresa', type=int, help='ID de empresa; sin valor audita consolidado.')
        parser.add_argument('--json', action='store_true', dest='as_json')
        parser.add_argument('--fail-on-critical', action='store_true')

    def handle(self, *args, **options):
        empresa = None
        if options['empresa']:
            try:
                empresa = Empresa.objects.get(pk=options['empresa'], activa=True)
            except Empresa.DoesNotExist as exc:
                raise CommandError('Empresa activa no encontrada.') from exc

        request = SimpleNamespace(
            user=_PlatformUser(),
            empresa_actual=empresa,
            modo_consolidado=empresa is None,
        )
        snapshot = build_process_journey(request)
        result = {
            'alcance': empresa.nombre_display if empresa else 'CONSOLIDADO',
            'empresas': snapshot['total_empresas'],
            'personas_activas': snapshot['total_workers'],
            'frentes': len(snapshot['issues']),
            'etapas': [
                {
                    'codigo': stage['key'],
                    'estado': stage['status'],
                    'metrica': stage['metric'],
                    'unidad': stage['metric_label'],
                }
                for stage in snapshot['stages']
            ],
            'incidencias': snapshot['issues'],
        }

        if options['as_json']:
            self.stdout.write(json.dumps(result, ensure_ascii=False, default=str))
        else:
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'Auditoria de procesos — {result["alcance"]}'))
            for stage in result['etapas']:
                self.stdout.write(
                    f'[{stage["estado"].upper():8}] {stage["codigo"]}: '
                    f'{stage["metrica"]} {stage["unidad"]}')
            if result['incidencias']:
                self.stdout.write('')
                for issue in result['incidencias']:
                    self.stdout.write(
                        f'- {issue["priority"].upper()} · {issue["stage"]}: '
                        f'{issue["title"]}')
            else:
                self.stdout.write(self.style.SUCCESS('Sin bloqueos operativos.'))

        if options['fail_on_critical'] and any(
                issue['priority'] == 'critical' for issue in result['incidencias']):
            raise CommandError('La auditoria encontro bloqueos criticos.')
