"""
seed_prestamos_demo.py — Seeds extendidos para el workflow completo.

Genera 5 préstamos en distintos estados:
  - 1 PAGADO (todas las cuotas pagadas)
  - 1 EN_CURSO con algunas cuotas pendientes
  - 1 EN_CURSO recién desembolsado (0 cuotas pagadas)
  - 1 PENDIENTE esperando aprobación
  - 1 RECHAZADO
Idempotente.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand

from personal.models import Personal
from prestamos.models import Prestamo, TipoPrestamo


class Command(BaseCommand):
    help = 'Genera 5 préstamos demo en distintos estados del workflow'

    def handle(self, *args, **options):
        self.stdout.write('\n=== SEED PRESTAMOS DEMO (workflow completo) ===')

        if not TipoPrestamo.objects.exists():
            self.stdout.write('  Cargando tipos de préstamo...')
            try:
                call_command('seed_tipos_prestamo')
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  No se pudo cargar tipos: {e}'))

        # Si ya hay >= 5 préstamos no recreamos
        if Prestamo.objects.count() >= 5:
            self.stdout.write(self.style.WARNING(
                f'  [SKIP] Ya hay {Prestamo.objects.count()} préstamos en BD'))
            return

        personas = list(Personal.objects.filter(estado='Activo').order_by('?')[:8])
        if len(personas) < 5:
            self.stdout.write(self.style.ERROR(
                f'  [ERROR] Se necesitan 5 empleados activos. Hay {len(personas)}.'))
            return

        admin = get_user_model().objects.filter(is_superuser=True).first()
        tipo_personal = (
            TipoPrestamo.objects.filter(codigo__icontains='personal').first()
            or TipoPrestamo.objects.first()
        )
        tipo_adelanto = (
            TipoPrestamo.objects.filter(codigo__icontains='adelanto').first()
            or tipo_personal
        )
        if not tipo_personal:
            self.stdout.write(self.style.ERROR('  [ERROR] No hay tipos de préstamo'))
            return

        hoy = date.today()
        primer_dia_mes = hoy.replace(day=1)

        created = 0

        # 1) PAGADO — todas las cuotas pagadas, 5 meses atrás
        try:
            p = Prestamo.objects.create(
                personal=personas[0], tipo=tipo_personal,
                monto_solicitado=Decimal('1500.00'), num_cuotas=3,
                motivo='Compra de equipo para teletrabajo',
                solicitado_por=admin,
                fecha_solicitud=primer_dia_mes - timedelta(days=90),
                estado='PENDIENTE',
            )
            fecha_5_meses_atras = (primer_dia_mes.replace(day=1) - timedelta(days=120))
            fecha_5_meses_atras = fecha_5_meses_atras.replace(day=1)
            p.desembolsar(admin, fecha_desembolso=fecha_5_meses_atras,
                          fecha_descuento=fecha_5_meses_atras)
            for c in p.cuotas.order_by('numero'):
                c.registrar_pago(fecha=c.periodo,
                                 referencia=f'NOM-{c.periodo.strftime("%Y%m")}-DEMO')
            created += 1
            self.stdout.write(f'  [1] PAGADO: {p.personal.apellidos_nombres} — S/{p.monto_efectivo}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [1] error: {e}'))

        # 2) EN_CURSO con algunas cuotas pagadas
        try:
            p = Prestamo.objects.create(
                personal=personas[1], tipo=tipo_personal,
                monto_solicitado=Decimal('3000.00'), num_cuotas=6,
                motivo='Gasto médico familiar',
                solicitado_por=admin,
                fecha_solicitud=primer_dia_mes - timedelta(days=60),
                estado='PENDIENTE',
            )
            fecha_inicio = primer_dia_mes.replace(day=1)
            try:
                fecha_inicio = fecha_inicio.replace(month=fecha_inicio.month - 2)
            except ValueError:
                fecha_inicio = fecha_inicio.replace(year=fecha_inicio.year - 1,
                                                    month=fecha_inicio.month + 10)
            p.desembolsar(admin, fecha_desembolso=fecha_inicio,
                          fecha_descuento=fecha_inicio)
            # Pagar primeras 2 cuotas
            for c in p.cuotas.order_by('numero')[:2]:
                c.registrar_pago(fecha=c.periodo,
                                 referencia=f'NOM-{c.periodo.strftime("%Y%m")}')
            created += 1
            self.stdout.write(f'  [2] EN_CURSO (2/6 pagadas): {p.personal.apellidos_nombres} — S/{p.monto_efectivo}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [2] error: {e}'))

        # 3) EN_CURSO recién desembolsado
        try:
            p = Prestamo.objects.create(
                personal=personas[2], tipo=tipo_personal,
                monto_solicitado=Decimal('2400.00'), num_cuotas=4,
                motivo='Mejora de vivienda',
                solicitado_por=admin,
                estado='PENDIENTE',
            )
            p.desembolsar(admin, fecha_desembolso=hoy,
                          fecha_descuento=primer_dia_mes)
            created += 1
            self.stdout.write(f'  [3] EN_CURSO recién desembolsado: {p.personal.apellidos_nombres} — S/{p.monto_efectivo}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [3] error: {e}'))

        # 4) PENDIENTE — esperando aprobación
        try:
            p = Prestamo.objects.create(
                personal=personas[3], tipo=tipo_adelanto,
                monto_solicitado=Decimal('800.00'), num_cuotas=1,
                motivo='Emergencia económica del mes',
                solicitado_por=admin,
                estado='PENDIENTE',
            )
            created += 1
            self.stdout.write(f'  [4] PENDIENTE: {p.personal.apellidos_nombres} — S/{p.monto_solicitado}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [4] error: {e}'))

        # 5) RECHAZADO
        try:
            p = Prestamo.objects.create(
                personal=personas[4], tipo=tipo_personal,
                monto_solicitado=Decimal('5000.00'), num_cuotas=10,
                motivo='Préstamo grande',
                solicitado_por=admin,
                estado='PENDIENTE',
            )
            p.rechazar(admin, motivo='Saldo pendiente de préstamo anterior demasiado alto.')
            created += 1
            self.stdout.write(f'  [5] RECHAZADO: {p.personal.apellidos_nombres}')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  [5] error: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\n  [OK] {created} préstamos creados'))
        self.stdout.write('=== FIN SEED ===\n')
