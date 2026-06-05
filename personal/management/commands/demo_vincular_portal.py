"""
Vincula el usuario 'demo' (admin de la demo) a un registro de Personal con datos
ricos (boletas, vacaciones), para que "Mi Portal" / "Probar el portal del
trabajador" muestre un portal POBLADO en vez de "Cuenta no vinculada".

Sin esto, el prospecto que pulsa "Probar el portal del trabajador" en el home ve
un portal vacío/roto — justo la feature que se quiere lucir.

Idempotente: si 'demo' ya está vinculado a algún Personal, no hace nada.
Solo DEMO/seed (en prod cada usuario se vincula a su propio empleado real).

Uso:
    python manage.py demo_vincular_portal
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count


class Command(BaseCommand):
    help = "Vincula el usuario demo a un empleado con datos para que el portal se vea poblado"

    def add_arguments(self, parser):
        parser.add_argument('--user', default='demo',
                            help="Username a vincular (default: demo).")

    def handle(self, *args, **opts):
        from personal.models import Personal
        User = get_user_model()

        username = opts['user']
        user = User.objects.filter(username=username).first()
        if not user:
            self.stdout.write(self.style.WARNING(
                f"Usuario '{username}' no existe — nada que vincular."))
            return

        # Idempotente: ¿ya está vinculado?
        if Personal.objects.filter(usuario=user).exists():
            p = Personal.objects.get(usuario=user)
            self.stdout.write(self.style.SUCCESS(
                f"'{username}' ya vinculado a {p.apellidos_nombres}. OK."))
            return

        # Elegir el empleado activo con MÁS boletas (portal rico: Mis Boletas,
        # Mi Asistencia, Mis Vacaciones se ven con datos).
        target = (Personal.objects.filter(estado='Activo')
                  .annotate(n=Count('nominas'))
                  .order_by('-n', 'id').first())
        if not target:
            target = Personal.objects.filter(estado='Activo').order_by('id').first()
        if not target:
            self.stdout.write(self.style.WARNING("No hay empleados activos."))
            return

        # Liberar el vínculo previo del target (era su login por DNI) y asignar demo.
        target.usuario = user
        target.save(update_fields=['usuario'])
        self.stdout.write(self.style.SUCCESS(
            f"'{username}' vinculado a {target.apellidos_nombres} "
            f"(id={target.id}). El portal del trabajador ya se ve poblado."))
