"""
Seed: Plan de Plantilla Sabores del Sur (Apertura Sucursal Trujillo).

Crea un plan ejemplo con 8 cargos y 27 posiciones, vigente jul-dic 2026.
Útil para que la página /nominas/planes/ del demo no esté vacía.

Idempotente: si el plan ya existe, no duplica.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand


PLAN_NOMBRE = 'Apertura Sucursal Trujillo 2026'

POSICIONES = [
    ('Chef Ejecutivo',        1, Decimal('5500.00'), 'Habitat'),
    ('Sous Chef',             2, Decimal('3200.00'), 'Integra'),
    ('Cocinero',              4, Decimal('1800.00'), 'Prima'),
    ('Ayudante Cocina',       6, Decimal('1300.00'), 'Profuturo'),
    ('Mesero',                8, Decimal('1300.00'), 'Habitat'),
    ('Cajero',                3, Decimal('1600.00'), 'Integra'),
    ('Administrador Local',   1, Decimal('4500.00'), 'Prima'),
    ('Personal Limpieza',     2, Decimal('1130.00'), ''),
]


class Command(BaseCommand):
    help = 'Seed Plan de Plantilla ejemplo (apertura sucursal Trujillo)'

    def handle(self, *args, **kw):
        from nominas.models import PlanPlantilla, LineaPlan

        plan, created = PlanPlantilla.objects.get_or_create(
            nombre=PLAN_NOMBRE,
            defaults=dict(
                tipo='PROYECTO',
                fecha_inicio=date(2026, 7, 1),
                fecha_fin=date(2026, 12, 31),
                descripcion=(
                    'Plan de plantilla para nueva sucursal Sabores del Sur en Trujillo. '
                    '6 meses, equipo cocina + servicio + administrativo.'
                ),
                estado='BORRADOR',
            ),
        )
        self.stdout.write(
            f"Plan '{plan.nombre}' "
            f"{'creado' if created else 'ya existe'}"
        )

        if LineaPlan.objects.filter(plan=plan).count() == 0:
            for cargo, cantidad, sueldo, afp in POSICIONES:
                LineaPlan.objects.create(
                    plan=plan,
                    cargo=cargo,
                    cantidad=cantidad,
                    sueldo_base=sueldo,
                    afp=afp,
                    regimen_pension='AFP' if afp else 'ONP',
                    fecha_inicio_puesto=date(2026, 7, 1),
                    fecha_fin_puesto=date(2026, 12, 31),
                )
            self.stdout.write(f'  {len(POSICIONES)} líneas creadas')

        total_lineas = LineaPlan.objects.filter(plan=plan).count()
        total_personas = sum(
            l.cantidad for l in LineaPlan.objects.filter(plan=plan)
        )
        total_costo = sum(
            (l.sueldo_base or Decimal('0')) * l.cantidad
            for l in LineaPlan.objects.filter(plan=plan)
        )
        self.stdout.write(self.style.SUCCESS(
            f'Total: {total_lineas} líneas, {total_personas} personas, '
            f'costo mensual S/ {total_costo:,.2f}'
        ))
