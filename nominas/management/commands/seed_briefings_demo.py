"""
Seed: Briefings del Día para demo.

Crea ~10 briefings entre AYER, HOY, MAÑANA para cubrir distintos servicios
y estados (BORRADOR / PUBLICADO / CERRADO).
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from empresas.models import Empresa
from asistencia.models import BriefingServicio


BRIEFINGS_DATA = [
    # (delta_dias, servicio, estado, covers, especiales, items_86, vips, notas_chef, dress_code)
    (-1, 'CENA', 'CERRADO', 78,
     'Tiradito de bonito con leche de tigre amazónica\nRavioli de cordero, salsa de menta\nCheesecake de lúcuma flambeado',
     'Ceviche clásico (mar agitado, no llegó pescado)\nPalta entera',
     'Mesa 4: cumpleaños 25 años Sra. González (cortesía del chef)\nMesa 9: ALERGIA AL GLUTEN SEVERA',
     'Equipo, anoche tuvimos una noche redonda. Hoy 78 covers. Mantengamos la consistencia en los emplatados — el detalle hace la diferencia.',
     'Protocolo formal · uniforme blanco impecable'),

    (0, 'ALMUERZO', 'PUBLICADO', 52,
     'Tiradito del día: lenguado con ají amarillo\nSeco de cabrito a la norteña',
     'Ensalada César (sin pollo de stock)',
     'Mesa 3: empresarios corporativos (3 personas) — atención prioritaria\nMesa 7: vegetariano confirmado',
     'Servicio tranquilo, aprovechemos para pulir mise en place de la cena (reserva: 95 covers). Pastelería: sacar la base de tarta de manzana a temperatura ambiente.',
     'Estándar de salón · mandil limpio'),

    (0, 'CENA', 'BORRADOR', 95,
     'Degustación 5 tiempos del chef\nMaridaje sommelier disponible',
     '',
     'Mesa 4: aniversario de bodas — preparar postre con vela\nMesa 11: VIP recurrente Sr. Andrade — verificar mesa de la ventana',
     '',
     ''),

    (1, 'ALMUERZO', 'BORRADOR', 0,
     '',
     '',
     '',
     '',
     ''),

    (-1, 'ALMUERZO', 'CERRADO', 45,
     'Causa rellena de pulpo al olivo',
     'Tartar de atún',
     '',
     'Buen ritmo de servicio. Felicitaciones a la brigada de fríos.',
     'Estándar'),

    (0, 'DESAYUNO', 'PUBLICADO', 32,
     'Pan de chacra con palta y huevo orgánico\nPanqueque de lúcuma',
     '',
     'Mesa 2: corporativos — café americano y omelette\nMesa 5: turistas (inglés) — menu en EN preparado',
     'Bienvenidos a un nuevo día. Servicio rápido y sonrisa. Las paltas están en su punto.',
     'Mandil blanco · gorra'),

    (1, 'CENA', 'BORRADOR', 88,
     'Especiales viernes:\n- Pulpo al olivo con vinagreta de aceitunas\n- Risotto de hongos silvestres\n- Suspiro a la limeña con espuma de pisco',
     '',
     '',
     '',
     'Protocolo formal'),
]


class Command(BaseCommand):
    help = 'Crea briefings demo en varios locales/fechas/servicios para mostrar la feature.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Limpia briefings existentes antes de sembrar.')

    def handle(self, *args, **opts):
        if opts['clear']:
            n = BriefingServicio.objects.count()
            BriefingServicio.objects.all().delete()
            self.stdout.write(f'  Eliminados {n} briefings previos.')

        empresas = list(Empresa.objects.filter(activa=True).order_by('id'))
        if not empresas:
            self.stdout.write(self.style.ERROR(
                'No hay empresas activas. Corre primero seed_grupo_edo_premium.'
            ))
            return

        hoy = timezone.localdate()
        creados = 0
        ya_existian = 0

        for i, (delta, servicio, estado, covers, especiales, items_86,
                vips, notas_chef, dress_code) in enumerate(BRIEFINGS_DATA):
            empresa = empresas[i % len(empresas)]
            fecha = hoy + timedelta(days=delta)

            # unique_together (empresa, fecha, servicio)
            if BriefingServicio.objects.filter(
                empresa=empresa, fecha=fecha, servicio=servicio,
            ).exists():
                ya_existian += 1
                continue

            b = BriefingServicio.objects.create(
                empresa=empresa,
                fecha=fecha,
                servicio=servicio,
                estado=estado,
                covers_esperados=covers,
                especiales=especiales,
                items_86=items_86,
                vips_alergias=vips,
                notas_chef=notas_chef,
                dress_code=dress_code,
                notas_operativas=(
                    'Briefing demo generado automáticamente.'
                    if estado != 'PUBLICADO'
                    else ''
                ),
            )

            # Marcar timestamps de publicación si corresponde
            if estado in ('PUBLICADO', 'CERRADO'):
                # Publicado retroactivo: 30 min antes del servicio típico
                publicado_at = timezone.now() - timedelta(days=-delta)
                b.publicado_en = publicado_at
                b.save(update_fields=['publicado_en'])

            creados += 1
            self.stdout.write(
                f'  ✓ {empresa.nombre_comercial[:25]:25s} · {fecha} · '
                f'{servicio:9s} · {estado}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Resumen Briefings ===\n'
            f'  Creados:        {creados}\n'
            f'  Ya existían:    {ya_existian}\n'
            f'  Total en sistema: {BriefingServicio.objects.count()}\n'
        ))
