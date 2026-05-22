"""
Seed data para SolicitudVacacion.

Genera 10 solicitudes en diferentes estados para demo del workflow:
- 5 APROBADAS (pasadas)
- 3 PENDIENTES (próximas semanas)
- 1 RECHAZADA
- 1 EN_GOCE (en curso ahora)

Uso:
    python manage.py seed_solicitudes_vacacion [--reset]
"""
from datetime import date, timedelta
import random

from django.core.management.base import BaseCommand
from django.db import transaction

from personal.models import Personal
from vacaciones.models import SolicitudVacacion, SaldoVacacional


class Command(BaseCommand):
    help = 'Genera solicitudes de vacaciones demo en distintos estados.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Borra solicitudes previas (que no estén APROBADAS reales) antes de crear nuevas.'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        hoy = date.today()
        reset = options.get('reset', False)

        # Universo: empleados activos con fecha_alta >= 12 meses atrás
        candidatos = list(
            Personal.objects.filter(
                estado='Activo',
                fecha_alta__isnull=False,
                fecha_alta__lte=hoy - timedelta(days=365),
            ).order_by('?')[:15]
        )

        if len(candidatos) < 4:
            self.stdout.write(self.style.ERROR(
                f'No hay suficientes empleados activos con >1 año de servicio '
                f'(encontrados: {len(candidatos)}). Aborto.'
            ))
            return

        if reset:
            borradas = SolicitudVacacion.objects.filter(
                motivo__startswith='[SEED]'
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'Borradas {borradas[0]} solicitudes seed previas.'
            ))

        created = 0

        def _get_saldo(emp):
            return SaldoVacacional.objects.filter(
                personal=emp, estado__in=['PENDIENTE', 'PARCIAL']
            ).first()

        # ── 5 APROBADAS (pasadas, últimos 6 meses) ──
        emps_aprob = random.sample(candidatos, min(5, len(candidatos)))
        for emp in emps_aprob:
            dias_atras = random.randint(60, 180)
            f_ini = hoy - timedelta(days=dias_atras)
            duracion = random.choice([7, 8, 10, 15])
            f_fin = f_ini + timedelta(days=duracion - 1)
            saldo = _get_saldo(emp)
            sol = SolicitudVacacion.objects.create(
                personal=emp,
                saldo=saldo,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                dias_calendario=0,  # auto en save()
                motivo='[SEED] Vacaciones gozadas',
                estado='APROBADA',
                fecha_aprobacion=f_ini - timedelta(days=15),
            )
            created += 1
            self.stdout.write(
                f'  [APROBADA] #{sol.pk:04d} '
                f'{emp.apellidos_nombres[:30]} '
                f'{f_ini} → {f_fin} ({duracion}d)'
            )

        # ── 3 PENDIENTES (próximas 2-8 semanas) ──
        restantes = [e for e in candidatos if e not in emps_aprob]
        if not restantes:
            restantes = candidatos
        emps_pend = random.sample(restantes, min(3, len(restantes)))
        for emp in emps_pend:
            dias_adelante = random.randint(14, 56)
            f_ini = hoy + timedelta(days=dias_adelante)
            duracion = random.choice([7, 10, 14])
            f_fin = f_ini + timedelta(days=duracion - 1)
            saldo = _get_saldo(emp)
            sol = SolicitudVacacion.objects.create(
                personal=emp,
                saldo=saldo,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                dias_calendario=0,
                motivo='[SEED] Solicitud pendiente de aprobación',
                estado='PENDIENTE',
            )
            created += 1
            self.stdout.write(
                f'  [PENDIENTE] #{sol.pk:04d} '
                f'{emp.apellidos_nombres[:30]} '
                f'{f_ini} → {f_fin} ({duracion}d)'
            )

        # ── 1 RECHAZADA ──
        usados = set(emps_aprob) | set(emps_pend)
        restantes2 = [e for e in candidatos if e not in usados]
        if restantes2:
            emp = random.choice(restantes2)
            f_ini = hoy - timedelta(days=30)
            f_fin = f_ini + timedelta(days=7)
            sol = SolicitudVacacion.objects.create(
                personal=emp,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                dias_calendario=0,
                motivo='[SEED] Solicitud rechazada',
                estado='RECHAZADA',
                motivo_rechazo='Período de alta demanda operativa — reprogramar.',
                fecha_aprobacion=f_ini - timedelta(days=10),
            )
            created += 1
            self.stdout.write(
                f'  [RECHAZADA] #{sol.pk:04d} '
                f'{emp.apellidos_nombres[:30]} '
                f'{f_ini} → {f_fin}'
            )
            usados.add(emp)

        # ── 1 EN_GOCE / DISFRUTANDO (en curso ahora) ──
        restantes3 = [e for e in candidatos if e not in usados]
        if restantes3:
            emp = random.choice(restantes3)
            f_ini = hoy - timedelta(days=3)
            f_fin = hoy + timedelta(days=7)
            saldo = _get_saldo(emp)
            sol = SolicitudVacacion.objects.create(
                personal=emp,
                saldo=saldo,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                dias_calendario=0,
                motivo='[SEED] Disfrutando vacaciones ahora',
                estado='EN_GOCE',
                fecha_aprobacion=f_ini - timedelta(days=14),
            )
            created += 1
            self.stdout.write(
                f'  [EN_GOCE] #{sol.pk:04d} '
                f'{emp.apellidos_nombres[:30]} '
                f'{f_ini} → {f_fin}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n{created} solicitudes seed creadas correctamente.'
        ))
