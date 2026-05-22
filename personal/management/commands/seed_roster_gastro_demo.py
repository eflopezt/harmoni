"""
Seed Roster Gastronomico Demo.

Crea:
  - 5 turnos tipicos de gastronomia (Desayuno, Almuerzo, Cena, Madrugada, Quebrado)
  - Asignaciones para las proximas 2 quincenas a personal activo
  - Rotacion realista de turnos + dias libres respetando 6+1

Uso:
    python manage.py seed_roster_gastro_demo
    python manage.py seed_roster_gastro_demo --limit 30
    python manage.py seed_roster_gastro_demo --dry-run
"""
import random
from datetime import date, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from personal.models import (
    AsignacionRosterQuincena,
    Personal,
    TurnoGastronomia,
)
from personal.roster_validator import quincena_rango


TURNOS_DEFAULT = [
    {
        'codigo': 'DES', 'nombre': 'Desayuno',
        'hora_entrada': time(6, 0), 'hora_salida': time(14, 0),
        'color': '#fbbf24',
    },
    {
        'codigo': 'ALM', 'nombre': 'Almuerzo',
        'hora_entrada': time(10, 0), 'hora_salida': time(18, 0),
        'color': '#0f766e',
    },
    {
        'codigo': 'CEN', 'nombre': 'Cena',
        'hora_entrada': time(16, 0), 'hora_salida': time(0, 0),
        'color': '#1d4ed8',
    },
    {
        'codigo': 'MAD', 'nombre': 'Madrugada',
        'hora_entrada': time(22, 0), 'hora_salida': time(6, 0),
        'color': '#6b21a8',
    },
    {
        'codigo': 'QUE', 'nombre': 'Quebrado (10-15 + 19-23)',
        'hora_entrada': time(10, 0), 'hora_salida': time(23, 0),
        'color': '#db2777',
    },
]


class Command(BaseCommand):
    help = 'Seed Roster Gastronomico Demo (turnos + asignaciones 2 quincenas).'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=40,
                            help='Maximo trabajadores a asignar (default 40).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Mostrar plan sin escribir en BD.')
        parser.add_argument('--seed', type=int, default=42,
                            help='Semilla aleatoria para rotacion reproducible.')

    @transaction.atomic
    def handle(self, *args, **opts):
        limit = opts['limit']
        dry = opts['dry_run']
        seed = opts['seed']
        random.seed(seed)

        # 1. Crear/asegurar turnos
        turnos = []
        for t_def in TURNOS_DEFAULT:
            obj, created = TurnoGastronomia.objects.get_or_create(
                codigo=t_def['codigo'],
                defaults={
                    'nombre': t_def['nombre'],
                    'hora_entrada': t_def['hora_entrada'],
                    'hora_salida': t_def['hora_salida'],
                    'color': t_def['color'],
                },
            )
            turnos.append(obj)
            etiqueta = 'NUEVO' if created else 'existe'
            self.stdout.write(f'  Turno {obj.codigo:4s} {etiqueta}: {obj.nombre}')

        if not turnos:
            self.stdout.write(self.style.ERROR('No se crearon turnos.'))
            return

        # 2. Rango: 2 quincenas a partir de hoy
        hoy = date.today()
        sub_q = 1 if hoy.day <= 15 else 2
        q_idx = (hoy.month - 1) * 2 + sub_q
        q1_ini, q1_fin, _, _, _ = quincena_rango(hoy.year, q_idx)
        # Siguiente quincena
        q2 = q_idx + 1
        anio2 = hoy.year
        if q2 > 24:
            q2 = 1
            anio2 += 1
        q2_ini, q2_fin, _, _, _ = quincena_rango(anio2, q2)

        fechas = []
        f = q1_ini
        while f <= q2_fin:
            fechas.append(f)
            f += timedelta(days=1)
        self.stdout.write(
            f'  Rango: {q1_ini} a {q2_fin} ({len(fechas)} dias)'
        )

        # 3. Personal activo (limitado)
        personal_qs = Personal.objects.filter(estado='Activo').order_by('id')[:limit]
        n_personal = personal_qs.count()
        if n_personal == 0:
            self.stdout.write(self.style.WARNING(
                'No hay personal Activo. Corre seeds de personal primero.'
            ))
            return
        self.stdout.write(f'  Personal a asignar: {n_personal}')

        # 4. Generar asignaciones con rotacion + 1 libre cada 7 dias
        creadas = 0
        actualizadas = 0
        libres = 0

        for idx, persona in enumerate(personal_qs):
            # Cada persona empieza con un offset distinto
            offset_inicio = idx % 7  # dia libre dentro de la semana
            turno_base = turnos[idx % len(turnos)]
            # Lista de turnos "permitidos" para esta persona (rotacion en 3)
            rotacion = [
                turnos[idx % len(turnos)],
                turnos[(idx + 1) % len(turnos)],
                turnos[(idx + 2) % len(turnos)],
            ]

            for i, f in enumerate(fechas):
                # Dia libre cada 7 dias rodantes (respeta 6+1)
                if (i + offset_inicio) % 7 == 0:
                    turno = None
                    libres += 1
                else:
                    # Rotacion semanal: cambia de turno cada ~3-4 dias
                    turno = rotacion[(i // 3) % len(rotacion)]

                if dry:
                    continue

                _, created = AsignacionRosterQuincena.objects.update_or_create(
                    personal=persona, fecha=f,
                    defaults={'turno': turno},
                )
                if created:
                    creadas += 1
                else:
                    actualizadas += 1

        if dry:
            self.stdout.write(self.style.WARNING(
                f'DRY-RUN — Habria asignado ~{n_personal * len(fechas)} celdas, '
                f'~{libres} dias libres. No se escribio.'
            ))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Listo: {creadas} creadas, {actualizadas} actualizadas, '
            f'{libres} dias libres.'
        ))
