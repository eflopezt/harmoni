"""
Health check: detecta inconsistencias entre RegistroPapeleta y RegistroTareo.

Casos detectados:
  1. Día con código FA pero existe papeleta APROBADA/EJECUTADA cubriendo →
     auto-corregir aplicando la papeleta.
  2. Día con código de papeleta (VAC, DL, CHE, etc.) sin papeleta APROBADA
     cubriéndolo → revertir a default.
  3. Papeletas APROBADAS huérfanas: días marcados con su pap_ref pero el
     codigo_dia no coincide con el tipo_permiso.

Uso:
    python manage.py health_check_papeletas              # auto-fix
    python manage.py health_check_papeletas --dry-run    # solo reportar
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from asistencia.models import RegistroPapeleta, RegistroTareo
from asistencia.services.papeletas_sync import (
    aplicar_papeleta, reset_caches,
    TIPO_A_CODIGO,
)


class Command(BaseCommand):
    help = 'Detecta y auto-corrige inconsistencias entre papeletas y RegistroTareo.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--fecha-ini', help='YYYY-MM-DD')
        parser.add_argument('--fecha-fin', help='YYYY-MM-DD')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        fecha_ini = (date.fromisoformat(opts['fecha_ini'])
                     if opts['fecha_ini'] else date.today() - timedelta(days=90))
        fecha_fin = (date.fromisoformat(opts['fecha_fin'])
                     if opts['fecha_fin'] else date.today() + timedelta(days=60))

        self.stdout.write(f'Rango: {fecha_ini} → {fecha_fin}')

        # Períodos CERRADOS: días en estos meses se ignoran (no se modifican).
        from cierre.models import PeriodoCierre
        cerrados = set(
            PeriodoCierre.objects.filter(estado='CERRADO')
            .values_list('anio', 'mes')
        )

        def _en_periodo_cerrado(f):
            return (f.year, f.month) in cerrados

        # ── 1) FA con papeleta APROBADA cubriéndolo ─────────────
        fa_problemas = []
        fa_qs = RegistroTareo.objects.filter(
            codigo_dia__in=['FA', 'F'],
            fecha__gte=fecha_ini, fecha__lte=fecha_fin,
            personal__isnull=False,
        ).select_related('personal')

        for r in fa_qs.iterator(chunk_size=500):
            if _en_periodo_cerrado(r.fecha):
                continue
            pap = RegistroPapeleta.objects.filter(
                personal_id=r.personal_id,
                estado__in=['APROBADA', 'EJECUTADA'],
                fecha_inicio__lte=r.fecha,
                fecha_fin__gte=r.fecha,
            ).first()
            if pap and TIPO_A_CODIGO.get(pap.tipo_permiso):
                fa_problemas.append((r, pap))

        self.stdout.write(self.style.WARNING(
            f'\n[1] FA cubiertos por papeleta APROBADA: {len(fa_problemas)}'
        ))
        if not dry and fa_problemas:
            reset_caches()
            paps_aplicar = {p.pk: p for _, p in fa_problemas}
            for pap in paps_aplicar.values():
                aplicar_papeleta(pap)
            self.stdout.write(f'    ✓ Aplicadas {len(paps_aplicar)} papeletas')

        # ── 2) Códigos de papeleta sin papeleta APROBADA ────────
        codigos_pap = set(TIPO_A_CODIGO.values())
        zombies_qs = RegistroTareo.objects.filter(
            codigo_dia__in=codigos_pap,
            fuente_codigo='PAPELETA',
            fecha__gte=fecha_ini, fecha__lte=fecha_fin,
            personal__isnull=False,
        ).select_related('personal')

        zombies = []
        for r in zombies_qs.iterator(chunk_size=500):
            if _en_periodo_cerrado(r.fecha):
                continue
            tiene_pap = RegistroPapeleta.objects.filter(
                personal_id=r.personal_id,
                estado__in=['APROBADA', 'EJECUTADA'],
                fecha_inicio__lte=r.fecha,
                fecha_fin__gte=r.fecha,
            ).exists()
            if not tiene_pap:
                zombies.append(r)

        self.stdout.write(self.style.WARNING(
            f'[2] Códigos de papeleta sin papeleta vigente: {len(zombies)}'
        ))
        if not dry and zombies:
            from asistencia.services.papeletas_sync import _codigo_default, _feriados_cache
            feriados = _feriados_cache(fecha_ini, fecha_fin)
            from decimal import Decimal
            CERO = Decimal('0')
            for r in zombies:
                codigo, fuente = _codigo_default(
                    r.personal, r.fecha, r.fecha in feriados,
                )
                r.codigo_dia = codigo
                r.fuente_codigo = fuente
                r.papeleta_ref = ''
                r.horas_efectivas = CERO
                r.horas_normales = CERO
                r.he_25 = CERO
                r.he_35 = CERO
                r.he_100 = CERO
                r.save(update_fields=['codigo_dia', 'fuente_codigo',
                                       'papeleta_ref', 'horas_efectivas',
                                       'horas_normales', 'he_25', 'he_35',
                                       'he_100'])
            self.stdout.write(f'    ✓ Revertidos {len(zombies)} días a default')

        # ── 3) Resumen final ────────────────────────────────────
        total = len(fa_problemas) + len(zombies)
        if total == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ Sin inconsistencias.'))
        else:
            modo = 'detectadas' if dry else 'corregidas'
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ {total} inconsistencias {modo}.'
            ))
