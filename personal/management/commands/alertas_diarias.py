"""
Management command: alertas_diarias

Genera alertas automáticas de contratos, período de prueba y vacaciones.
Diseñado para ejecutarse diariamente (cron o Render cron job).

Uso:
    python manage.py alertas_diarias
    python manage.py alertas_diarias --solo-contratos
    python manage.py alertas_diarias --dry-run
"""
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Genera alertas automáticas diarias (contratos, período de prueba, vacaciones)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Solo muestra lo que haría, sin crear alertas',
        )
        parser.add_argument(
            '--solo-contratos',
            action='store_true',
            help='Solo procesa alertas de contratos',
        )
        parser.add_argument(
            '--solo-vacaciones',
            action='store_true',
            help='Solo procesa alertas de vacaciones',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy = timezone.localdate()

        self.stdout.write(self.style.SUCCESS(
            f'\n{"=" * 50}\n  Harmoni | Alertas Diarias | {hoy}\n{"=" * 50}\n'
        ))

        total_creadas = 0

        if not options['solo_vacaciones']:
            total_creadas += self._alertas_contratos(hoy, dry_run)
            total_creadas += self._alertas_periodo_prueba(hoy, dry_run)

        if not options['solo_contratos']:
            total_creadas += self._alertas_vacaciones(hoy, dry_run)

        # Ejecutar también las alertas generales del módulo analytics
        try:
            from analytics.services import generar_alertas
            nuevas = generar_alertas()
            if not dry_run:
                total_creadas += len(nuevas)
                if nuevas:
                    self.stdout.write(f'  Analytics: {len(nuevas)} alerta(s) generada(s)')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Analytics: error — {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Total alertas creadas hoy: {total_creadas}'
            + (' (DRY RUN — nada guardado)' if dry_run else '')
        ))

    def _alertas_contratos(self, hoy, dry_run):
        """Genera alertas para contratos por vencer y vencidos."""
        from analytics.models import AlertaRRHH
        from personal.models import Personal

        activos = Personal.objects.filter(estado='Activo')
        creadas = 0

        # Contratos vencidos sin renovar
        vencidos = activos.filter(fecha_fin_contrato__lt=hoy)
        self.stdout.write(f'  Contratos vencidos: {vencidos.count()}')

        for p in vencidos[:50]:
            if not dry_run:
                alerta, created = AlertaRRHH.objects.get_or_create(
                    titulo=f'Contrato vencido: {p.apellidos_nombres}',
                    categoria='CONTRATOS',
                    estado='ACTIVA',
                    defaults={
                        'descripcion': (
                            f'{p.apellidos_nombres} tiene contrato vencido desde '
                            f'{p.fecha_fin_contrato.strftime("%d/%m/%Y")}. '
                            f'Regularizar urgente.'
                        ),
                        'severidad': 'CRITICAL',
                    },
                )
                if created:
                    creadas += 1
            else:
                self.stdout.write(f'    [DRY] Alerta CRITICAL: {p.apellidos_nombres}')

        # Contratos por vencer en 30/15/7 días
        for dias in [30, 15, 7]:
            por_vencer = activos.filter(
                fecha_fin_contrato__gte=hoy,
                fecha_fin_contrato__lte=hoy + timedelta(days=dias),
                fecha_fin_contrato__gt=hoy + timedelta(days=dias - 1 if dias > 7 else 0),
            )
            if dias == 30:
                por_vencer = activos.filter(
                    fecha_fin_contrato__gte=hoy + timedelta(days=16),
                    fecha_fin_contrato__lte=hoy + timedelta(days=30),
                )
            elif dias == 15:
                por_vencer = activos.filter(
                    fecha_fin_contrato__gte=hoy + timedelta(days=8),
                    fecha_fin_contrato__lte=hoy + timedelta(days=15),
                )
            else:
                por_vencer = activos.filter(
                    fecha_fin_contrato__gte=hoy,
                    fecha_fin_contrato__lte=hoy + timedelta(days=7),
                )

            self.stdout.write(f'  Por vencer en {dias}d: {por_vencer.count()}')

            for p in por_vencer[:20]:
                sev = 'CRITICAL' if dias <= 7 else ('WARN' if dias <= 15 else 'INFO')
                if not dry_run:
                    alerta, created = AlertaRRHH.objects.get_or_create(
                        titulo=f'Contrato vence en {dias}d: {p.apellidos_nombres}',
                        categoria='CONTRATOS',
                        estado='ACTIVA',
                        defaults={
                            'descripcion': (
                                f'{p.apellidos_nombres} tiene contrato que vence el '
                                f'{p.fecha_fin_contrato.strftime("%d/%m/%Y")} '
                                f'({dias} días). Revisar renovación.'
                            ),
                            'severidad': sev,
                        },
                    )
                    if created:
                        creadas += 1
                else:
                    self.stdout.write(f'    [DRY] Alerta {sev}: {p.apellidos_nombres} ({dias}d)')

        return creadas

    def _alertas_periodo_prueba(self, hoy, dry_run):
        """Genera alertas para empleados cuyo período de prueba termina pronto."""
        from analytics.models import AlertaRRHH
        from personal.models import Personal

        # Buscamos empleados ingresados en los últimos 12 meses
        desde = hoy - relativedelta(months=12)
        candidatos = Personal.objects.filter(
            estado='Activo',
            fecha_alta__gte=desde,
        ).select_related('subarea__area')

        creadas = 0
        alertas_pp = 0

        for p in candidatos:
            fin = p.fecha_fin_periodo_prueba
            if not fin:
                continue
            dias = (fin - hoy).days
            if 0 <= dias <= 15:
                alertas_pp += 1
                if not dry_run:
                    alerta, created = AlertaRRHH.objects.get_or_create(
                        titulo=f'Fin período prueba: {p.apellidos_nombres}',
                        categoria='CONTRATOS',
                        estado='ACTIVA',
                        defaults={
                            'descripcion': (
                                f'{p.apellidos_nombres} finaliza su período de prueba '
                                f'({p.periodo_prueba_meses} meses) el {fin.strftime("%d/%m/%Y")} '
                                f'— {dias} días. Evaluar continuidad.'
                            ),
                            'severidad': 'WARN' if dias > 7 else 'CRITICAL',
                        },
                    )
                    if created:
                        creadas += 1
                else:
                    self.stdout.write(f'    [DRY] Fin prueba {dias}d: {p.apellidos_nombres}')

        self.stdout.write(f'  Período de prueba terminando (<=15d): {alertas_pp}')
        return creadas

    def _alertas_vacaciones(self, hoy, dry_run):
        """Alerta sobre vacaciones vencidas o acumuladas > umbral."""
        creadas = 0
        try:
            from analytics.models import AlertaRRHH
            from vacaciones.models import SaldoVacacional
            from decimal import Decimal

            criticos = SaldoVacacional.objects.filter(
                estado='VIGENTE',
                dias_pendientes__gte=30,
            ).select_related('personal')

            self.stdout.write(f'  Vacaciones acumuladas (>=30d): {criticos.count()}')

            for saldo in criticos[:30]:
                if not dry_run:
                    alerta, created = AlertaRRHH.objects.get_or_create(
                        titulo=f'Vacaciones acumuladas: {saldo.personal.apellidos_nombres}',
                        categoria='VACACIONES',
                        estado='ACTIVA',
                        defaults={
                            'descripcion': (
                                f'{saldo.personal.apellidos_nombres} tiene '
                                f'{saldo.dias_pendientes} días de vacaciones pendientes '
                                f'(período {saldo.periodo}).'
                            ),
                            'severidad': 'CRITICAL' if saldo.dias_pendientes >= 45 else 'WARN',
                            'valor_actual': Decimal(str(saldo.dias_pendientes)),
                            'valor_umbral': Decimal('30'),
                        },
                    )
                    if created:
                        creadas += 1
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  Vacaciones: error — {e}'))

        return creadas
