"""
Aplica reglas Semana Santa 2026 a los RegistroTareo ya creados:

1. Feriados no laborados (02/04 Jueves Santo y 03/04 Viernes Santo):
     FA → FER   (día feriado pagado, no falta)
     Aplica a TODOS los empleados sin distinción de condición.

2. Compensaciones FORÁNEO por trabajar feriado:
     Si FORÁNEO trabajó 02/04 (ef>0) Y el 04/04 está FA → 04/04 = CPF
     Si FORÁNEO trabajó 03/04 Y el 05/04 está FA       → 05/04 = CPF
     Si FORÁNEO trabajó 03/04 Y el 12/04 está FA       → 12/04 = CPF

     Si el día compensado ya lo trabajó (codigo=A/SS, ef>0), se respeta —
     feriado laborado sigue pagándose como tal, no hay descanso que compensar.
     LOCAL/LIMA no tienen compensación adicional: trabajar feriado = HE100.

No modifica horas (FER y CPF van con ef=norm=HE=0, pagados en planilla).
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from asistencia.models import RegistroTareo


CERO = Decimal('0')


class Command(BaseCommand):
    help = 'Aplica FER (feriado no laborado) y CPF (compensación) a Semana Santa 2026.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        fer_jue, fer_vie = date(2026, 4, 2), date(2026, 4, 3)
        comp_sab, comp_dom1, comp_dom2 = date(2026, 4, 4), date(2026, 4, 5), date(2026, 4, 12)

        # ─── 1. FA → FER en feriados (todos los empleados) ───────────────
        qs_fer = RegistroTareo.objects.filter(
            fecha__in=[fer_jue, fer_vie], codigo_dia='FA',
        )
        self.stdout.write(f'FA → FER en 02/04 y 03/04: {qs_fer.count()}')
        for r in qs_fer[:5]:
            self.stdout.write(
                f'  {r.fecha} {r.condicion:8s} {r.dni} {r.personal.apellidos_nombres[:35]}')

        if not dry:
            qs_fer.update(
                codigo_dia='FER',
                fuente_codigo='FERIADO',
                horas_efectivas=CERO,
                horas_normales=CERO,
                he_25=CERO, he_35=CERO, he_100=CERO,
                es_feriado=True,
            )

        # ─── 2. Compensaciones ───────────────────────────────────────────
        # 02/04 trabajado (TODAS las condiciones) → compensa 04/04 sábado
        #   LOCAL sábado = 5.5h laborables → CPF reemplaza FA
        #   FORÁNEO sábado = 10h laborables → CPF reemplaza FA
        trabajaron_02 = set(
            RegistroTareo.objects.filter(
                fecha=fer_jue, horas_efectivas__gt=0,
            ).values_list('personal_id', flat=True)
        )
        qs_04 = RegistroTareo.objects.filter(
            personal_id__in=trabajaron_02, fecha=comp_sab, codigo_dia='FA',
        )
        self.stdout.write(
            f'\nTrabajaron 02/04 (todas condiciones): {len(trabajaron_02)} → 04/04 FA a CPF: {qs_04.count()}')
        for r in qs_04[:5]:
            self.stdout.write(f'  {r.personal.apellidos_nombres[:35]}')

        # 03/04 trabajado → compensa 05/04 y 12/04 (solo FORÁNEO)
        # Los LOCAL no tienen compensación adicional: sus domingos ya son DS.
        # El LOCAL que trabajó 03/04 recibe pago 100% HE ese mismo día.
        cond_filter = {'condicion__in': ['FORANEO', 'FORÁNEO']}
        trabajaron_03 = set(
            RegistroTareo.objects.filter(
                fecha=fer_vie, horas_efectivas__gt=0, **cond_filter,
            ).values_list('personal_id', flat=True)
        )
        qs_05 = RegistroTareo.objects.filter(
            personal_id__in=trabajaron_03, fecha=comp_dom1, codigo_dia='FA',
        )
        qs_12 = RegistroTareo.objects.filter(
            personal_id__in=trabajaron_03, fecha=comp_dom2, codigo_dia='FA',
        )
        self.stdout.write(
            f'\nFORÁNEOs trabajaron 03/04: {len(trabajaron_03)}\n'
            f'  05/04 FA a CPF: {qs_05.count()}\n'
            f'  12/04 FA a CPF: {qs_12.count()}')

        if not dry:
            for qs in (qs_04, qs_05, qs_12):
                qs.update(
                    codigo_dia='CPF',
                    fuente_codigo='COMPENSACION',
                    horas_efectivas=CERO,
                    horas_normales=CERO,
                    he_25=CERO, he_35=CERO, he_100=CERO,
                )

        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Completado{" (DRY RUN)" if dry else ""}.'))
