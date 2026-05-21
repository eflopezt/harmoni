"""
Sincroniza las plantillas hardcoded de reclutamiento.emails.TEMPLATES
hacia la BD (PlantillaNotificacion) para que sean editables desde admin.

Uso:
    python manage.py sync_plantillas_email

Idempotente: usa update_or_create con codigo `reclutamiento_<key>`.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sincroniza plantillas hardcoded de reclutamiento.emails a la BD.'

    def handle(self, *args, **options):
        from reclutamiento.emails import sincronizar_plantillas_default
        creadas = sincronizar_plantillas_default()
        self.stdout.write(self.style.SUCCESS(
            f'Plantillas sincronizadas. {creadas} nuevas creadas '
            f'(las existentes fueron actualizadas).'
        ))
