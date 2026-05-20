"""
seed_demo_prestamos.py
Genera 4 préstamos de demostración en distintos estados con cuotas pagadas/pendientes.
Idempotente: si ya hay préstamos en BD, no crea más.
"""
import random
from datetime import date
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand

from personal.models import Personal
from prestamos.models import Prestamo, TipoPrestamo, CuotaPrestamo

random.seed(42)


class Command(BaseCommand):
    help = 'Genera préstamos demo en distintos estados con cuotas'

    def handle(self, *args, **options):
        self.stdout.write('\n=== SEED DEMO PRESTAMOS ===')

        if not TipoPrestamo.objects.exists():
            self.stdout.write('  Tipos no existen, ejecutando seed_tipos_prestamo...')
            call_command('seed_tipos_prestamo')

        existing = Prestamo.objects.count()
        if existing >= 3:
            self.stdout.write(f'  [SKIP] Ya hay {existing} préstamos en BD')
            return

        personal_qs = list(Personal.objects.filter(estado='Activo').order_by('?')[:6])
        if len(personal_qs) < 4:
            self.stdout.write('  [ERROR] Necesita al menos 4 empleados activos')
            return

        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.filter(is_superuser=True).first()

        tipo_personal = TipoPrestamo.objects.get(codigo='prestamo-personal')
        tipo_adelanto = TipoPrestamo.objects.get(codigo='adelanto-sueldo')

        plantillas = [
            # (personal_idx, tipo, monto, cuotas, estado_final, cuotas_pagadas, motivo)
            (0, tipo_personal,  Decimal('3000.00'), 6, 'EN_CURSO', 2, 'Compra de equipo para teletrabajo.'),
            (1, tipo_personal,  Decimal('1500.00'), 3, 'EN_CURSO', 1, 'Gasto médico familiar urgente.'),
            (2, tipo_adelanto,  Decimal('800.00'),  1, 'PENDIENTE', 0, 'Emergencia económica del mes.'),
            (3, tipo_personal,  Decimal('5000.00'), 10, 'PAGADO', 10, 'Mejora de vivienda (concluido).'),
        ]

        created = 0
        for idx, tipo, monto, cuotas, estado, cuotas_pagadas, motivo in plantillas:
            p = Prestamo.objects.create(
                personal=personal_qs[idx],
                tipo=tipo,
                monto_solicitado=monto,
                num_cuotas=cuotas,
                fecha_solicitud=date.today().replace(day=1),
                motivo=motivo,
                solicitado_por=admin,
            )
            if estado in ('EN_CURSO', 'PAGADO'):
                p.aprobar(admin, fecha_descuento=date.today().replace(day=1))
                # Pagar las primeras N cuotas
                for cuota in p.cuotas.order_by('numero')[:cuotas_pagadas]:
                    cuota.registrar_pago(
                        fecha=cuota.periodo,
                        referencia=f'NOM-{cuota.periodo.strftime("%Y%m")}-DEMO',
                    )
            elif estado == 'PENDIENTE':
                p.estado = 'PENDIENTE'
                p.save(update_fields=['estado'])
            created += 1

        self.stdout.write(self.style.SUCCESS(f'  [OK] {created} préstamos creados'))
        self.stdout.write('=== FIN SEED PRESTAMOS ===\n')
