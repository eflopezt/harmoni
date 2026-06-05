"""
Cambia el plan comercial de una empresa (Empresa.plan).

Uso:
    # Activar Plan Starter para empresa con RUC X
    python manage.py set_empresa_plan 20612345678 STARTER

    # Cambiar a Enterprise
    python manage.py set_empresa_plan 20100000111 ENTERPRISE

    # Listar planes actuales
    python manage.py set_empresa_plan --list
"""
from django.core.management.base import BaseCommand, CommandError

from empresas.models import Empresa


PLANES_VALIDOS = {choice[0] for choice in Empresa.PLAN_CHOICES}


class Command(BaseCommand):
    help = 'Cambia Empresa.plan o lista los planes vigentes'
    requires_system_checks = []  # skip checks (demo tiene admin checks rotos)

    def add_arguments(self, parser):
        parser.add_argument('ruc',  nargs='?', help='RUC de la empresa')
        parser.add_argument('plan', nargs='?', help='Nuevo plan ({})'.format(' | '.join(sorted(PLANES_VALIDOS))))
        parser.add_argument(
            '--list', action='store_true',
            help='Lista todas las empresas con su plan actual y sale'
        )

    def handle(self, *args, **opts):
        if opts.get('list'):
            self._listar()
            return

        ruc  = opts.get('ruc')
        plan = (opts.get('plan') or '').upper()

        if not ruc or not plan:
            raise CommandError(
                'Uso: set_empresa_plan <RUC> <PLAN> | set_empresa_plan --list\n'
                f'  Planes válidos: {", ".join(sorted(PLANES_VALIDOS))}'
            )

        if plan not in PLANES_VALIDOS:
            raise CommandError(
                f'Plan inválido: {plan!r}. '
                f'Opciones: {", ".join(sorted(PLANES_VALIDOS))}'
            )

        try:
            empresa = Empresa.objects.get(ruc=ruc)
        except Empresa.DoesNotExist:
            raise CommandError(f'No existe empresa con RUC {ruc}')

        plan_anterior = empresa.plan
        empresa.plan = plan
        empresa.save(update_fields=['plan', 'actualizado_en'])

        self.stdout.write(self.style.SUCCESS(
            f'✓ {empresa.razon_social} (RUC {empresa.ruc}): '
            f'{plan_anterior} → {plan}'
        ))

        # Hints útiles — tope de colaboradores del plan (si lo tiene)
        from core.planes import plan_max_trabajadores
        tope = plan_max_trabajadores(plan)
        if tope:
            from personal.models import Personal
            count = Personal.objects.filter(empresa=empresa, estado='Activo').count()
            self.stdout.write(self.style.NOTICE(
                f'\n  Trabajadores activos: {count} / {tope} (límite del plan {plan})'
            ))
            if count > tope:
                self.stdout.write(self.style.WARNING(
                    f'  ⚠ La empresa tiene {count} workers — supera el tope del plan.'
                ))

    def _listar(self):
        empresas = Empresa.objects.all().order_by('plan', 'razon_social')
        self.stdout.write('═' * 80)
        self.stdout.write('{:<12} {:<15} {:<50} {}'.format(
            'RUC', 'PLAN', 'RAZÓN SOCIAL', '# WORKERS'
        ))
        self.stdout.write('─' * 80)
        from personal.models import Personal
        for e in empresas:
            n = Personal.objects.filter(empresa=e, estado='Activo').count()
            self.stdout.write('{:<12} {:<15} {:<50} {}'.format(
                e.ruc, e.plan, e.razon_social[:48], n,
            ))
        self.stdout.write('═' * 80)
        self.stdout.write(f'Total: {empresas.count()} empresas')
