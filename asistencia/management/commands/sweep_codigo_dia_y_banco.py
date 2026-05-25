"""
Sweep automático de asistencia:
  1. Detecta RegistroTareo con codigo_dia='SS' o 'SE' que tienen entrada+salida
     válidas → los corrige a 'A' y recalcula HE.
  2. Re-propaga HE→BancoHoras para STAFF en los meses afectados.

Idempotente: solo toca lo que tiene inconsistencia. Respeta:
  - fuente_codigo MANUAL/PAPELETA (no sobrescribe)
  - meses con BancoHoras.cerrado=True (no reescribe auditados)
  - PeriodoCierre.estado='CERRADO' (no toca meses cerrados)

Uso:
    # Default: últimos 6 meses
    python manage.py sweep_codigo_dia_y_banco

    # Rango custom
    python manage.py sweep_codigo_dia_y_banco --desde 2026-01-01 --hasta 2026-12-31

    # Solo reportar (no escribir)
    python manage.py sweep_codigo_dia_y_banco --dry-run

Schedule: corre vía celery beat (cada noche, post-backup).
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Q, Sum
from django.utils import timezone


class Command(BaseCommand):
    help = (
        'Sweep nocturno: corrige codigos SS/SE con marcas válidas (→ A) y '
        're-propaga HE → BancoHoras para STAFF. Idempotente.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--desde', type=str, default=None,
            help='Fecha inicio (YYYY-MM-DD). Default: hace 180 días.'
        )
        parser.add_argument(
            '--hasta', type=str, default=None,
            help='Fecha fin (YYYY-MM-DD). Default: hoy.'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo reportar conteos, sin escribir.'
        )

    def handle(self, *args, **opts):
        from asistencia.models import RegistroTareo, BancoHoras
        from asistencia.views.calendario import _recalcular_horas
        from cierre.models import PeriodoCierre

        hoy = timezone.now().date()
        desde = (
            date.fromisoformat(opts['desde']) if opts['desde']
            else hoy - timedelta(days=180)
        )
        hasta = (
            date.fromisoformat(opts['hasta']) if opts['hasta']
            else hoy
        )
        dry = opts['dry_run']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'Sweep asistencia · {desde} → {hasta} · '
            f'{"DRY-RUN" if dry else "WRITE"}'
        ))

        # Meses cerrados (no tocar)
        cerrados = set(
            PeriodoCierre.objects.filter(estado='CERRADO')
            .values_list('anio', 'mes')
        )

        # ── Paso 1: SS/SE con marcas válidas → A
        qs = RegistroTareo.objects.filter(
            fecha__range=(desde, hasta),
            codigo_dia__in=('SS', 'SE'),
            hora_entrada_real__isnull=False,
            hora_salida_real__isnull=False,
            fuente_codigo__in=['RELOJ', 'IMPORT', ''],
        ).exclude(
            # Excluir meses cerrados
            **{}
        )

        total_candidatos = qs.count()
        self.stdout.write(f'  Paso 1: candidatos SS/SE→A: {total_candidatos}')

        if dry:
            self.stdout.write('  (dry-run) no se modifica nada')
            return

        n_corregidos = 0
        n_he_generadas = 0
        meses_afectados = set()

        for reg in qs.select_related('personal').iterator(chunk_size=500):
            # Saltar si el mes del registro está cerrado
            if (reg.fecha.year, reg.fecha.month) in cerrados:
                continue

            reg.codigo_dia = 'A'
            reg.fuente_codigo = 'RELOJ'
            try:
                _recalcular_horas(reg)
                reg.save(update_fields=[
                    'codigo_dia', 'fuente_codigo',
                    'horas_marcadas', 'horas_efectivas', 'horas_normales',
                    'he_25', 'he_35', 'he_100',
                ])
                n_corregidos += 1
                if (reg.he_25 or 0) > 0 or (reg.he_35 or 0) > 0 or (reg.he_100 or 0) > 0:
                    n_he_generadas += 1
                meses_afectados.add((reg.fecha.year, reg.fecha.month))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(
                    f'    err reg {reg.id}: {exc}'
                ))

        self.stdout.write(
            f'  Paso 1 OK: {n_corregidos} corregidos · '
            f'{n_he_generadas} con HE > 0 · '
            f'{len(meses_afectados)} meses afectados'
        )

        # ── Paso 2: propagar a BancoHoras
        if not meses_afectados:
            self.stdout.write('  Paso 2: nada que propagar')
            return

        nb_creados = nb_actualizados = nb_omitidos = 0
        for anio, mes in meses_afectados:
            if (anio, mes) in cerrados:
                continue

            # Cerrados en BancoHoras (no reescribir)
            cerrados_banco = set(BancoHoras.objects.filter(
                periodo_anio=anio, periodo_mes=mes, cerrado=True,
            ).values_list('personal_id', flat=True))

            he_por = (
                RegistroTareo.objects.filter(
                    fecha__year=anio, fecha__month=mes,
                    grupo='STAFF', personal__isnull=False,
                )
                .exclude(personal_id__in=cerrados_banco)
                .values('personal_id')
                .annotate(
                    s25=Sum('he_25'), s35=Sum('he_35'), s100=Sum('he_100'),
                )
                .filter(Q(s25__gt=0) | Q(s35__gt=0) | Q(s100__gt=0))
            )

            for r in he_por:
                s25 = r['s25'] or Decimal('0')
                s35 = r['s35'] or Decimal('0')
                s100 = r['s100'] or Decimal('0')
                total = s25 + s35 + s100

                banco, created = BancoHoras.objects.get_or_create(
                    personal_id=r['personal_id'],
                    periodo_anio=anio,
                    periodo_mes=mes,
                    defaults={
                        'he_25_acumuladas': s25,
                        'he_35_acumuladas': s35,
                        'he_100_acumuladas': s100,
                        'saldo_horas': total,
                        'observaciones': 'Sweep automático',
                    },
                )
                if created:
                    nb_creados += 1
                    continue
                if banco.cerrado:
                    nb_omitidos += 1
                    continue
                cambio = (
                    banco.he_25_acumuladas != s25
                    or banco.he_35_acumuladas != s35
                    or banco.he_100_acumuladas != s100
                )
                if cambio:
                    banco.he_25_acumuladas = s25
                    banco.he_35_acumuladas = s35
                    banco.he_100_acumuladas = s100
                    banco.saldo_horas = total - (banco.he_compensadas or Decimal('0'))
                    banco.save(update_fields=[
                        'he_25_acumuladas', 'he_35_acumuladas',
                        'he_100_acumuladas', 'saldo_horas', 'actualizado_en',
                    ])
                    nb_actualizados += 1

        self.stdout.write(
            f'  Paso 2 OK: banco — creados {nb_creados} · '
            f'actualizados {nb_actualizados} · cerrados {nb_omitidos}'
        )

        self.stdout.write(self.style.SUCCESS(
            f'Sweep completado: {n_corregidos} regs corregidos, '
            f'{nb_creados + nb_actualizados} entradas banco tocadas.'
        ))
