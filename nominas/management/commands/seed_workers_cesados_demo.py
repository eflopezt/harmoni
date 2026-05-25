"""
Seed: workers cesados para demo de Liquidación al Cese.

Crea 3 trabajadores con estado=Cesado y motivo distinto para que el
panel /nominas/liquidaciones/ muestre el flujo end-to-end:
  1. Cesado por renuncia voluntaria (reciente)
  2. Cesado por vencimiento de contrato (obra/servicio)
  3. Cesado por mutuo acuerdo

Idempotente: si ya existen, los reutiliza.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand


CESADOS_SPECS = [
    # (DNI, apellidos_nombres, cargo, sueldo, motivo, dias_atras)
    ('48119876', 'TORRES MENDOZA, Carlos Alberto', 'Sub Chef',           3200,
     'RENUNCIA',         18, '5x2', 'AFP', 'Integra'),
    ('46778321', 'QUISPE FLORES, Maria Elena',     'Mesera Senior',      1800,
     'VENCIMIENTO',      35, '6x1', 'AFP', 'Prima'),
    ('44993100', 'CASTRO DELGADO, Roberto',        'Cocinero Polivalente', 2000,
     'MUTUO_ACUERDO',    62, '5x2', 'ONP', ''),
]


class Command(BaseCommand):
    help = 'Crea 3 workers cesados para demo de Liquidación al Cese'

    def handle(self, *args, **kw):
        from personal.models import Personal
        from empresas.models import Empresa

        empresa = Empresa.objects.filter(
            razon_social__icontains='Sabores del Sur',
        ).first() or Empresa.objects.first()
        if not empresa:
            self.stdout.write(self.style.ERROR(
                'No hay empresas. Aborta.'
            ))
            return

        hoy = date.today()
        creados = 0
        for spec in CESADOS_SPECS:
            (dni, nombre, cargo, sueldo, motivo, dias_atras,
             regimen_turno, regimen_pension, afp) = spec
            f_cese = hoy - timedelta(days=dias_atras)
            f_ingreso = hoy - timedelta(days=dias_atras + 365 * 2)  # 2 años antiguedad

            personal, was_created = Personal.objects.update_or_create(
                nro_doc=dni,
                defaults=dict(
                    empresa=empresa,
                    tipo_doc='DNI',
                    apellidos_nombres=nombre,
                    cargo=cargo,
                    sueldo_base=Decimal(sueldo),
                    estado='Cesado',
                    motivo_cese=motivo,
                    fecha_alta=f_ingreso,
                    fecha_cese=f_cese,
                    tipo_trab='Empleado',
                    grupo_tareo='STAFF',
                    regimen_pension=regimen_pension,
                    afp=afp,
                    asignacion_familiar=True,
                ),
            )
            self.stdout.write(
                f"  {'[NEW]' if was_created else '[upd]'} "
                f"{nombre[:35]:<35} DNI {dni} · {motivo:<15} · "
                f"cesado hace {dias_atras}d"
            )
            if was_created:
                creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nListo. {creados} nuevos. '
            f'Total cesados activos: '
            f'{Personal.objects.filter(estado="Cesado").count()}'
        ))
        self.stdout.write(
            'Ver: https://demo.harmoni.pe/nominas/liquidaciones/'
        )
