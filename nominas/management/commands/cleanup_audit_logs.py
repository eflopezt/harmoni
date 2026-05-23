"""
Limpia audit logs antiguos según retention policy.

Compliance: muchos clientes tienen política de retener bitácoras
solo N años (SOX: 7 años, GDPR: 6 años por defecto, fiscal peruano: 5 años).

Uso:
    python manage.py cleanup_audit_logs                          # purge >365 días
    python manage.py cleanup_audit_logs --dias 730                # 2 años
    python manage.py cleanup_audit_logs --dry-run                 # simulación
    python manage.py cleanup_audit_logs --dias 365 --conservar-creates
        # Borra UPDATE/ACTIVAR/etc pero conserva CREATE/DELETE para trail completo
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from nominas.models import ConceptoAuditLog


class Command(BaseCommand):
    help = 'Purga audit logs antiguos según retention policy.'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=365,
            help='Retención en días (default 365). Logs más antiguos se borran.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo cuenta cuántos logs serían borrados — no toca DB.',
        )
        parser.add_argument(
            '--conservar-creates', action='store_true',
            help='Mantiene CREATE/DELETE incluso si están viejos (trail completo).',
        )

    def handle(self, *args, **opts):
        dias = opts['dias']
        if dias < 30:
            self.stdout.write(self.style.ERROR(
                f'[ERROR] Retención mínima recomendada: 30 días. Recibido: {dias}.'
            ))
            return

        cutoff = timezone.now() - timedelta(days=dias)
        qs = ConceptoAuditLog.objects.filter(fecha__lt=cutoff)

        if opts['conservar_creates']:
            qs = qs.exclude(accion__in=['CREATE', 'DELETE'])

        total_old = qs.count()
        total_all = ConceptoAuditLog.objects.count()

        self.stdout.write(
            f'[CUTOFF] {cutoff:%Y-%m-%d} ({dias} días atrás)'
        )
        self.stdout.write(
            f'  Total logs en DB:        {total_all}'
        )
        self.stdout.write(
            f'  Logs antiguos a purgar:  {total_old}'
        )

        if opts['conservar_creates']:
            self.stdout.write(
                self.style.WARNING(
                    f'  --conservar-creates: CREATE/DELETE preservados'
                )
            )

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'  [DRY RUN] No se aplican cambios.'
            ))
            return

        if total_old == 0:
            self.stdout.write(self.style.SUCCESS('  [OK] Nada que purgar.'))
            return

        deleted, breakdown = qs.delete()
        self.stdout.write(self.style.SUCCESS(
            f'  [OK] {deleted} logs purgados.'
        ))
