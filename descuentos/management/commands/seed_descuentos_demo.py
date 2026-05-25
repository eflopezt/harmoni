"""Seed 5 escenarios reales de descuentos por planilla para Sabores del Sur."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Crea descuentos demo para Sabores del Sur (rotura vajilla, uniforme, pensión, etc.)"

    def handle(self, *args, **kw):
        from personal.models import Personal
        from descuentos.models import DescuentoPlanilla

        hoy = date.today()
        hans = Personal.objects.filter(nro_doc='71445678').first()
        yes = Personal.objects.filter(nro_doc='73000005').first()
        bruno = Personal.objects.filter(nro_doc='73000002').first()
        andrea = Personal.objects.filter(nro_doc='73000004').first()
        carmen = Personal.objects.filter(nro_doc='73000006').first()

        casos = [
            dict(
                personal=yes,
                causal='ROTURA_HERRAMIENTA',
                detalle=(
                    'Rotura de 3 vasos de cristal premium y 1 plato '
                    'cuadrado pizarra durante turno cena del 12/05.'
                ),
                monto_total=Decimal('85.00'),
                num_cuotas=1,
                estado='APROBADO',
                consentimiento_firmado=True,
                fecha_aprobacion=hoy - timedelta(days=3),
                fecha_inicio_descuento=date(hoy.year, hoy.month, 1),
                observaciones='Cliente reclamó por bebida en mesa 4.',
            ),
            dict(
                personal=bruno,
                causal='REPOSICION_UNIFORME',
                detalle=(
                    'Reposición uniforme completo: 2 camisas + 1 mandil '
                    'corporativo (deterioro fuera de uso normal).'
                ),
                monto_total=Decimal('120.00'),
                num_cuotas=2,
                estado='EN_CURSO',
                consentimiento_firmado=True,
                fecha_aprobacion=hoy - timedelta(days=30),
                fecha_inicio_descuento=date(
                    hoy.year, hoy.month if hoy.month > 1 else 12, 1
                ),
            ),
            dict(
                personal=andrea,
                causal='CONSUMO_INTERNO',
                detalle=(
                    'Consumo de bebidas alcohólicas premium fuera del '
                    'horario y monto autorizado (Política RIT Art. 24).'
                ),
                monto_total=Decimal('250.00'),
                num_cuotas=2,
                estado='APROBADO',
                consentimiento_firmado=True,
                fecha_aprobacion=hoy - timedelta(days=2),
                fecha_inicio_descuento=date(hoy.year, hoy.month, 1),
            ),
            dict(
                personal=hans,
                causal='PENSION_ALIMENTICIA',
                detalle=(
                    'Pensión alimenticia ordenada por Juzgado de Familia '
                    'de Lima — Exp 1842-2025. 30% mensual sobre '
                    'remuneración bruta hasta diciembre 2027.'
                ),
                monto_total=Decimal('19800.00'),
                num_cuotas=30,
                cuota_mensual=Decimal('660.00'),
                estado='EN_CURSO',
                requiere_consentimiento=False,
                consentimiento_firmado=False,
                fecha_aprobacion=hoy - timedelta(days=90),
                fecha_inicio_descuento=date(
                    hoy.year, hoy.month if hoy.month > 3 else 1, 1
                ),
            ),
            dict(
                personal=carmen,
                causal='MULTA_INTERNA',
                detalle=(
                    'Multa por impuntualidad recurrente (5+ tardanzas '
                    'en mes según Política RIT Art. 18).'
                ),
                monto_total=Decimal('50.00'),
                num_cuotas=1,
                estado='PENDIENTE',
                consentimiento_firmado=False,
            ),
        ]

        count = 0
        for c in casos:
            if not c['personal']:
                continue
            obj, created = DescuentoPlanilla.objects.update_or_create(
                personal=c['personal'],
                causal=c['causal'],
                defaults=c,
            )
            self.stdout.write(
                f"  [{'CREATE' if created else 'UPDATE'}] {obj}"
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\nTotal: {count} descuentos seedados"
        ))
