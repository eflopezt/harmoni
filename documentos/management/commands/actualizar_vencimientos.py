"""
Management command: actualizar_vencimientos

Recalcula el estado y la fecha de vencimiento de DocumentoTrabajador:
- Si fecha_vencimiento es null y el tipo tiene vigencia_dias + fecha_emision,
  calcula fecha_vencimiento.
- Marca VENCIDO los que ya pasaron de fecha_vencimiento.
- Marca POR_VENCER los próximos N días (según dias_alerta_vencimiento de cada tipo).
- Mantiene VIGENTE los que aún están dentro del período.

Pensado para correr en cron diario:
    0 6 * * *  /opt/harmoni/manage.py actualizar_vencimientos
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from documentos.models import DocumentoTrabajador


class Command(BaseCommand):
    help = 'Recalcula fecha_vencimiento y estado de los documentos del legajo.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra cambios sin guardarlos.',
        )

    def handle(self, *args, **opts):
        dry = opts.get('dry_run', False)
        hoy = date.today()

        # 1) Calcular fecha_vencimiento donde falta
        calculados = 0
        qs_calc = (
            DocumentoTrabajador.objects
            .filter(
                tipo__vence=True,
                tipo__vigencia_dias__isnull=False,
                fecha_emision__isnull=False,
                fecha_vencimiento__isnull=True,
            )
            .exclude(estado='ANULADO')
            .select_related('tipo')
        )
        with transaction.atomic():
            for d in qs_calc:
                d.fecha_vencimiento = d.fecha_emision + timedelta(days=d.tipo.vigencia_dias)
                if not dry:
                    d.save(update_fields=['fecha_vencimiento', 'actualizado_en'])
                calculados += 1

        # 2) Marcar vencidos
        qs_vencidos = DocumentoTrabajador.objects.filter(
            tipo__vence=True,
            fecha_vencimiento__lt=hoy,
            estado__in=['VIGENTE', 'POR_VENCER'],
        )
        n_vencidos = qs_vencidos.count()
        if not dry:
            qs_vencidos.update(estado='VENCIDO')

        # 3) Marcar por_vencer (próximos 30 días por defecto)
        qs_por_vencer = DocumentoTrabajador.objects.filter(
            tipo__vence=True,
            fecha_vencimiento__gte=hoy,
            fecha_vencimiento__lte=hoy + timedelta(days=30),
            estado='VIGENTE',
        )
        n_por_vencer = qs_por_vencer.count()
        if not dry:
            qs_por_vencer.update(estado='POR_VENCER')

        # 4) Marcar VIGENTE los que ya no están en ventana de alerta (recuperación)
        qs_recovered = DocumentoTrabajador.objects.filter(
            tipo__vence=True,
            fecha_vencimiento__gt=hoy + timedelta(days=30),
            estado='POR_VENCER',
        )
        n_recovered = qs_recovered.count()
        if not dry:
            qs_recovered.update(estado='VIGENTE')

        prefix = '[DRY-RUN] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f'{prefix}OK · fecha_vencimiento calculada: {calculados} | '
            f'marcados VENCIDO: {n_vencidos} | '
            f'marcados POR_VENCER: {n_por_vencer} | '
            f'recuperados a VIGENTE: {n_recovered}'
        ))
