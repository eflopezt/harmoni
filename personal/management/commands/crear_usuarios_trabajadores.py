"""
crear_usuarios_trabajadores.py
Crea cuentas User para todos los Personal activos que no tengan usuario vinculado.

- username = nro_doc (DNI / CE / Pasaporte)
- password = (configurable, default 'demo123') — los trabajadores entran con su DNI
  como usuario y la clave que el admin les comunique.

Idempotente: salta los Personal que ya tienen usuario.

Uso:
    python manage.py crear_usuarios_trabajadores
    python manage.py crear_usuarios_trabajadores --password=miempresa2026
    python manage.py crear_usuarios_trabajadores --solo-activos
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from personal.models import Personal

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea User para cada Personal sin usuario vinculado.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password', default='demo123',
            help='Contraseña inicial para todos los nuevos usuarios (default: demo123).',
        )
        parser.add_argument(
            '--solo-activos', action='store_true',
            help='Solo crear usuarios para Personal con estado=Activo (default: incluye todos).',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo mostrar qué se haría sin crear nada.',
        )

    def handle(self, *args, **options):
        qs = Personal.objects.filter(usuario__isnull=True)
        if options['solo_activos']:
            qs = qs.filter(estado='Activo')

        total = qs.count()
        self.stdout.write(f'\n=== CREAR USUARIOS TRABAJADORES ===')
        self.stdout.write(f'Personal sin usuario: {total}')

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nada por hacer — todos los Personal ya tienen usuario.'))
            return

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('[DRY RUN] No se creará nada.'))
            for p in qs[:20]:
                self.stdout.write(f'  {p.nro_doc:>12s}  {p.apellidos_nombres[:45]}  ({p.estado})')
            if total > 20:
                self.stdout.write(f'  ... y {total - 20} más')
            return

        password = options['password']
        created = 0
        skipped_collision = 0

        with transaction.atomic():
            for p in qs.select_related():
                username = p.nro_doc.strip()
                if not username:
                    self.stdout.write(self.style.WARNING(
                        f'  [SKIP] Personal #{p.pk} ({p.apellidos_nombres}) sin nro_doc'
                    ))
                    continue

                # Si ya existe un User con ese username (colisión), lo vinculamos en vez de crear.
                user, was_created = User.objects.get_or_create(
                    username=username,
                    defaults={
                        'first_name': p.apellidos_nombres.split(',')[1].strip()[:30] if ',' in p.apellidos_nombres else '',
                        'last_name':  p.apellidos_nombres.split(',')[0].strip()[:150] if ',' in p.apellidos_nombres else p.apellidos_nombres[:150],
                        'is_active': True,
                    },
                )
                if was_created:
                    user.set_password(password)
                    user.save()
                else:
                    skipped_collision += 1

                p.usuario = user
                p.save(update_fields=['usuario'])
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n  [OK] {created} Personal vinculados a usuario'
        ))
        if skipped_collision:
            self.stdout.write(self.style.WARNING(
                f'  [INFO] {skipped_collision} usuarios ya existían — vinculados al Personal (no se cambió su clave).'
            ))
        self.stdout.write(f'\nLos trabajadores nuevos pueden entrar con:')
        self.stdout.write(f'  Usuario:  su nro de documento (DNI)')
        self.stdout.write(f'  Clave:    {password}')
        self.stdout.write('=== FIN ===\n')
