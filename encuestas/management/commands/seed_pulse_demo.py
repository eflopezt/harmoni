"""
Seed: Pulse Semanal demo (12 semanas, ~70% participación, gastronomía).

Genera respuestas realistas para Grupo EDO y similares.

Uso:
    python manage.py seed_pulse_demo
    python manage.py seed_pulse_demo --semanas 12 --participacion 0.7 --reset
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from encuestas.models import PulseSemanal
from personal.models import Personal


PROPUESTAS_GASTRONOMIA = [
    'Necesitamos turnos más equilibrados, algunos compañeros hacen doble seguido.',
    'Falta material de limpieza en cocina los fines de semana.',
    'Sería bueno un bono por covers altos en cenas grandes.',
    'El uniforme nuevo es muy ajustado, sugiero revisar tallas.',
    'Propongo capacitación en el menú nuevo, no todos conocemos los platos.',
    'Necesitamos un break más largo en el doble turno (almuerzo + cena).',
    'Falta comunicación entre cocina y salón en horas pico.',
    'Sería ideal contar con vasos de agua individuales para el staff.',
    'Las propinas tardan en llegar, propongo digitalizar el reparto.',
    'Hace falta climatización en la cocina, especialmente en verano.',
    'Propongo una reunión semanal corta de equipo para alinear servicio.',
    'El sueldo se queda corto con la inflación, evaluar aumento.',
    'Faltan cuchillos en buen estado, los actuales están muy gastados.',
    'Sugiero rotar tareas para que todos aprendamos estaciones.',
    'Necesitamos descansos planificados, no improvisados.',
    'El parqueo es complicado en cenas, podría haber convenio cercano.',
    'Falta reconocimiento al empleado del mes, motivaría mucho.',
    'Propongo cursos cortos de coctelería para el equipo de salón.',
    'Tenemos que mejorar el manejo del rush de cumpleaños y eventos.',
    'Faltan delantales nuevos, los actuales están manchados.',
]

QUE_FALTA_GASTRONOMIA = [
    'Más coordinación entre cocina y salón.',
    'Materiales de limpieza al día.',
    'Reconocimiento por buen servicio.',
    'Reuniones cortas de equipo.',
    'Capacitación en menú nuevo.',
    'Turnos más equilibrados.',
    'Comunicación clara de cambios.',
    'Insumos completos a tiempo.',
    'Pago de horas extra puntual.',
    'Mejor ambiente en cocina.',
    'Liderazgo más cercano.',
    'Espacio para el descanso.',
    '',
    '',
    '',
]


class Command(BaseCommand):
    help = 'Crea pulses semanales demo para las últimas N semanas (default 12).'

    def add_arguments(self, parser):
        parser.add_argument('--semanas', type=int, default=12,
                            help='Cuántas semanas hacia atrás (default 12).')
        parser.add_argument('--participacion', type=float, default=0.70,
                            help='Porcentaje participación 0.0-1.0 (default 0.70).')
        parser.add_argument('--reset', action='store_true',
                            help='Borrar todos los PulseSemanal previos antes de seedear.')
        parser.add_argument('--empresa', type=int, default=None,
                            help='Filtrar trabajadores por empresa ID.')

    def handle(self, *args, **opts):
        if opts['reset']:
            n = PulseSemanal.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f'⤺ Eliminados {n} pulses previos.'))

        trabajadores = Personal.objects.filter(estado='Activo')
        if opts['empresa']:
            trabajadores = trabajadores.filter(empresa_id=opts['empresa'])
        trabajadores = list(trabajadores)

        if not trabajadores:
            self.stdout.write(self.style.ERROR('No hay trabajadores activos para seedear.'))
            return

        self.stdout.write(f'  Trabajadores activos: {len(trabajadores)}')

        hoy = date.today()
        n_semanas = opts['semanas']
        part_target = opts['participacion']

        # Distribución del ánimo (3-5 más común)
        # animo, peso
        animo_weights = [
            (1, 3),   # Muy mal — minoritario
            (2, 8),   # Mal
            (3, 25),  # Regular
            (4, 40),  # Bien
            (5, 24),  # Excelente
        ]
        flat_animo = [a for a, w in animo_weights for _ in range(w)]

        # NPS distribución: 50% promotor (9-10), 30% neutro (7-8), 20% detractor (0-6)
        def random_nps():
            r = random.random()
            if r < 0.50:
                return random.choice([9, 10])
            if r < 0.80:
                return random.choice([7, 8])
            return random.randint(0, 6)

        creados = 0
        skipped = 0

        # Generar lista de (anio, semana) hacia atrás
        cur = hoy
        semanas = []
        seen = set()
        while len(semanas) < n_semanas:
            iso = cur.isocalendar()
            key = (iso.year, iso.week)
            if key not in seen:
                seen.add(key)
                semanas.append(key)
            cur -= timedelta(days=7)

        with transaction.atomic():
            for anio, semana in semanas:
                # Sub-conjunto que respondió esta semana
                k = max(1, int(len(trabajadores) * part_target))
                # Variación natural ±10%
                k_variado = max(1, min(len(trabajadores), int(k * random.uniform(0.85, 1.15))))
                sample = random.sample(trabajadores, k_variado)

                for trab in sample:
                    if PulseSemanal.objects.filter(personal=trab, anio=anio, semana=semana).exists():
                        skipped += 1
                        continue

                    animo = random.choice(flat_animo)
                    incluye_texto = random.random() < 0.55
                    que_falta = random.choice(QUE_FALTA_GASTRONOMIA) if incluye_texto else ''
                    propuestas = random.choice(PROPUESTAS_GASTRONOMIA) if random.random() < 0.45 else ''

                    # NPS opcional ~75% de las veces
                    nps = random_nps() if random.random() < 0.75 else None

                    PulseSemanal.objects.create(
                        semana=semana,
                        anio=anio,
                        empresa=trab.empresa,
                        personal=trab,
                        animo=animo,
                        que_falta=que_falta,
                        propuestas=propuestas,
                        nps=nps,
                    )
                    creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✓ {creados} pulses creados, {skipped} omitidos (ya existían). '
            f'Semanas: {n_semanas} · Participación target: {part_target:.0%}'
        ))
