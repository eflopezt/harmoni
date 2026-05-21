"""
Seed: Roster semanal demo para los trabajadores activos.

Asigna turnos rotativos a TODOS los trabajadores activos para las
próximas 2 semanas. Patrón realista gastronomía:
- 6 días trabajo + 1 descanso (rotativo)
- Mezcla mañana/tarde/noche/quebrado según rol
- Algunos trabajadores con vacaciones programadas
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from personal.models import Personal, Roster


class Command(BaseCommand):
    help = 'Crea Roster semanal para los trabajadores activos (2 semanas).'

    def add_arguments(self, parser):
        parser.add_argument('--semanas', type=int, default=2,
                            help='Cuántas semanas crear (default 2).')
        parser.add_argument('--clear', action='store_true',
                            help='Eliminar roster previo del rango antes de crear.')

    def handle(self, *args, **opts):
        n_semanas = opts['semanas']
        random.seed(42)

        hoy = timezone.localdate()
        inicio = hoy - timedelta(days=hoy.weekday())  # lunes de esta semana
        fin = inicio + timedelta(days=7 * n_semanas - 1)

        if opts['clear']:
            n_del = Roster.objects.filter(fecha__gte=inicio, fecha__lte=fin).delete()
            self.stdout.write(f'  Eliminados {n_del[0]} registros previos.')

        trabajadores = list(Personal.objects.filter(estado='Activo').order_by('id'))
        creados = 0
        ya_existian = 0

        # Patrones de turnos según orden cíclico del trabajador
        # Para que parezca rotativo y variado
        PATRONES = [
            # (cargo_keyword, lista_codigos_por_dia_semana_iniciando_lunes)
            # Cada lista tiene 7 elementos para una semana, se repite
            (['cocin', 'chef', 'parrill'],   ['T', 'T', 'D', 'T', 'T', 'T', 'T']),   # cocina cena
            (['cocin', 'chef', 'parrill'],   ['M', 'M', 'M', 'D', 'M', 'M', 'M']),   # cocina almuerzo
            (['meser', 'mozo', 'salon'],     ['T', 'T', 'D', 'T', 'T', 'T', 'T']),   # salon cena
            (['meser', 'mozo', 'salon'],     ['M', 'M', 'M', 'D', 'M', 'M', 'M']),   # salon almuerzo
            (['somm', 'bartender', 'cantin'], ['T', 'T', 'D', 'T', 'T', 'N', 'N']),  # noche
            (['cajer', 'host', 'recepc'],    ['M', 'T', 'D', 'M', 'T', 'M', 'T']),   # rotativo
            ([],                              ['M', 'M', 'D', 'T', 'T', 'Q', 'Q']),   # default rotativo
        ]

        def pick_patron(personal):
            cargo = (personal.cargo or '').lower()
            for keywords, patron in PATRONES:
                if any(k in cargo for k in keywords):
                    return patron
            return PATRONES[-1][1]  # default

        for i, t in enumerate(trabajadores):
            patron_base = pick_patron(t)
            # Variar levemente entre trabajadores con el mismo cargo
            offset = i % 3
            for s in range(n_semanas):
                for d in range(7):
                    fecha = inicio + timedelta(days=s * 7 + d)
                    codigo = patron_base[(d + offset) % 7]

                    # Probabilidad pequeña de vacaciones o falta
                    rnd = random.random()
                    if rnd < 0.02:
                        codigo = 'V'  # vacaciones
                    elif rnd < 0.025 and codigo != 'D':
                        codigo = 'FA'  # falta esporádica

                    obj, created = Roster.objects.get_or_create(
                        personal=t, fecha=fecha,
                        defaults={'codigo': codigo, 'fuente': 'seed_demo'},
                    )
                    if created:
                        creados += 1
                    else:
                        ya_existian += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Roster Demo ===\n'
            f'  Rango: {inicio} → {fin}\n'
            f'  Trabajadores: {len(trabajadores)}\n'
            f'  Creados:      {creados}\n'
            f'  Ya existían:  {ya_existian}\n'
        ))
