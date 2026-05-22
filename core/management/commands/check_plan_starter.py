"""
Diagnóstico del Plan Starter en una instancia Harmoni.

Verifica que toda la infra del feature gating está OK:
- Middleware activo en MIDDLEWARE settings
- Context processor activo en TEMPLATES
- App signals registradas
- Empresa.plan field existe
- URLs registradas (/upgrade/, /d/, /onboarding/starter/, /cuenta/plan/, /api/v1/me/plan/)

Uso:
    python manage.py check_plan_starter
    python manage.py check_plan_starter --verbose
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import NoReverseMatch, reverse


class Command(BaseCommand):
    help = 'Diagnóstico del Plan Starter — verifica que toda la infra está OK'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--detail', action='store_true', help='Output detallado')

    def handle(self, *args, **opts):
        verbose = opts.get('verbose', False)
        errors = []

        self.stdout.write('═' * 70)
        self.stdout.write('  Plan Starter — Diagnóstico de instancia')
        self.stdout.write('═' * 70)

        # ── 1. MIDDLEWARE activo ──
        self.stdout.write('\n1. Middleware')
        mw = 'core.middleware_plan_starter.PlanStarterMiddleware'
        if mw in settings.MIDDLEWARE:
            self.stdout.write(self.style.SUCCESS(f'  ✓ {mw}'))
        else:
            self.stdout.write(self.style.ERROR(f'  ✗ {mw} NO está en MIDDLEWARE'))
            errors.append('PlanStarterMiddleware no registrado')

        # ── 2. Context processor activo ──
        self.stdout.write('\n2. Context processor')
        try:
            tps = settings.TEMPLATES[0].get('OPTIONS', {}).get('context_processors', [])
            cp = 'core.context_processors.plan_starter_context'
            if cp in tps:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {cp}'))
            else:
                self.stdout.write(self.style.ERROR(f'  ✗ {cp} NO está en context_processors'))
                errors.append('context processor no registrado')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ Error: {e}'))
            errors.append(f'TEMPLATES config: {e}')

        # ── 3. Empresa.plan field ──
        self.stdout.write('\n3. Modelo Empresa.plan')
        try:
            from empresas.models import Empresa
            Empresa._meta.get_field('plan')
            self.stdout.write(self.style.SUCCESS('  ✓ Empresa.plan field existe'))

            counts = {}
            for p, _ in Empresa.PLAN_CHOICES:
                counts[p] = Empresa.objects.filter(plan=p).count()
            for p, n in counts.items():
                marker = self.style.SUCCESS if n > 0 else self.style.WARNING
                self.stdout.write(marker(f'    {p:15} {n} empresa(s)'))
            if sum(counts.values()) == 0:
                errors.append('No hay empresas en la DB')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ {e}'))
            errors.append(f'Empresa.plan: {e}')

        # ── 4. Signals registradas ──
        self.stdout.write('\n4. Signals Plan Starter')
        try:
            from django.db.models.signals import pre_save, post_save
            from personal.models import Personal
            # _live_receivers devuelve (sync_list, async_list)
            pre_r  = pre_save._live_receivers(sender=Personal)
            post_r = post_save._live_receivers(sender=Personal)
            all_receivers = []
            for r in (pre_r, post_r):
                if isinstance(r, tuple):
                    for sub in r:
                        all_receivers.extend(sub)
                else:
                    all_receivers.extend(r)
            handler_names = [r.__name__ for r in all_receivers if hasattr(r, '__name__')]
            if 'enforce_plan_worker_cap' in handler_names:
                self.stdout.write(self.style.SUCCESS('  ✓ enforce_plan_worker_cap (pre_save)'))
            else:
                self.stdout.write(self.style.WARNING('  ⚠ enforce_plan_worker_cap NO registrado'))
                errors.append('signal pre_save no registrado')
            if 'alert_on_personal_save' in handler_names:
                self.stdout.write(self.style.SUCCESS('  ✓ alert_on_personal_save (post_save)'))
            else:
                self.stdout.write(self.style.WARNING('  ⚠ alert_on_personal_save NO registrado'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ✗ {e}'))

        # ── 5. URLs registradas ──
        self.stdout.write('\n5. URLs registradas')
        url_names = [
            'upgrade_plan',
            'demo_autologin',
            'mi_cuenta_plan',
            'onboarding_starter_step1',
            'api_me_plan',
        ]
        for name in url_names:
            try:
                if name == 'demo_autologin':
                    url = reverse(name, kwargs={'slug': 'starter'})
                else:
                    url = reverse(name)
                self.stdout.write(self.style.SUCCESS(f'  ✓ {name:30} → {url}'))
            except NoReverseMatch:
                self.stdout.write(self.style.ERROR(f'  ✗ {name} NO registrado'))
                errors.append(f'URL {name} missing')

        # ── 6. Comandos CLI ──
        self.stdout.write('\n6. Comandos CLI')
        from django.core.management import get_commands
        cmds = get_commands()
        for cmd_name in ('set_empresa_plan', 'seed_demo_audiovisual', 'check_plan_starter'):
            if cmd_name in cmds:
                self.stdout.write(self.style.SUCCESS(f'  ✓ {cmd_name}'))
            else:
                self.stdout.write(self.style.WARNING(f'  ⚠ {cmd_name} NO registrado'))

        # ── Resumen ──
        self.stdout.write('\n' + '═' * 70)
        if errors:
            self.stdout.write(self.style.ERROR(f'  ✗ {len(errors)} PROBLEMA(S) ENCONTRADO(S):'))
            for e in errors:
                self.stdout.write(self.style.ERROR(f'    - {e}'))
            self.stdout.write('═' * 70)
            return  # exit con resultado
        else:
            self.stdout.write(self.style.SUCCESS('  ✓ Plan Starter — TODO OK'))
            self.stdout.write('═' * 70)
