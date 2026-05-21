"""
Seed: Saldos de Apertura para demo.

Crea SaldoAperturaTrabajador para todos los trabajadores activos,
con valores realistas. Marca la apertura como COMPLETADA al 31/05/2026.
"""
import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from personal.models import Personal
from nominas.models import SaldoAperturaTrabajador, ConfiguracionApertura


class Command(BaseCommand):
    help = 'Carga saldos de apertura realistas para demo (todos los activos).'

    def add_arguments(self, parser):
        parser.add_argument('--fecha-corte', default='2026-05-31',
                            help='Fecha de corte (YYYY-MM-DD). Default 2026-05-31.')
        parser.add_argument('--clear', action='store_true',
                            help='Borrar saldos previos antes de crear.')

    @transaction.atomic
    def handle(self, *args, **opts):
        try:
            anio, mes, dia = opts['fecha_corte'].split('-')
            fecha_corte = date(int(anio), int(mes), int(dia))
        except (ValueError, AttributeError):
            self.stdout.write(self.style.ERROR('Fecha inválida.'))
            return

        if opts['clear']:
            n = SaldoAperturaTrabajador.objects.count()
            SaldoAperturaTrabajador.objects.all().delete()
            ConfiguracionApertura.objects.all().delete()
            self.stdout.write(f'  Eliminados {n} saldos previos.')

        # User para creado_por (busca un superuser)
        from django.contrib.auth import get_user_model
        U = get_user_model()
        admin_user = U.objects.filter(is_superuser=True).first()

        trabajadores = Personal.objects.filter(estado='Activo').order_by('id')
        creados = 0
        actualizados = 0
        random.seed(42)  # determinístico

        for p in trabajadores:
            # Estimar antigüedad para provisiones realistas
            if p.fecha_alta:
                meses_antig = max(1, (fecha_corte - p.fecha_alta).days // 30)
            else:
                meses_antig = random.randint(6, 36)

            # Sueldo base estimado
            sueldo = float(p.sueldo_base or 1500)

            # Provisiones realistas:
            # CTS = (sueldo / 12) * meses_no_depositados_aún (típico 4-5 meses entre depósitos)
            prov_cts = round(sueldo / 12 * random.uniform(3, 5), 2)

            # Gratificación proporcional al semestre en curso (1-6 meses al corte de mayo)
            prov_gratif = round(sueldo / 6 * random.randint(2, 5), 2)

            # Vacaciones devengadas pero no gozadas
            dias_vac = random.randint(0, 15)
            prov_vac = round((sueldo / 30) * dias_vac, 2)

            # IR 5ta acumulado del año (depende del nivel salarial)
            if sueldo > 6000:
                ir5 = round(random.uniform(400, 1800), 2)
            elif sueldo > 3500:
                ir5 = round(random.uniform(0, 350), 2)
            else:
                ir5 = 0

            # Préstamos vigentes (solo 30% de trabajadores)
            if random.random() < 0.30:
                prestamo = round(random.uniform(500, 4500), 2)
            else:
                prestamo = 0

            obj, created = SaldoAperturaTrabajador.objects.update_or_create(
                personal=p,
                defaults={
                    'fecha_corte':                fecha_corte,
                    'prov_cts':                   Decimal(str(prov_cts)),
                    'prov_gratificacion':         Decimal(str(prov_gratif)),
                    'prov_vacaciones':            Decimal(str(prov_vac)),
                    'dias_vacaciones_pendientes': dias_vac,
                    'ir5_acumulado':              Decimal(str(ir5)),
                    'prestamo_saldo':             Decimal(str(prestamo)),
                    'creado_por':                 admin_user,
                    'notas':                      'Seed automático para demo.',
                },
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        # Marcar configuración como completada
        cfg, _ = ConfiguracionApertura.objects.update_or_create(
            empresa=None,
            defaults={
                'fecha_corte':        fecha_corte,
                'completado':         True,
                'total_trabajadores': creados + actualizados,
                'confirmado_en':      timezone.now(),
                'confirmado_por':     admin_user,
                'notas':              'Apertura sembrada para demo.',
            },
        )

        from django.db.models import Sum
        agg = SaldoAperturaTrabajador.objects.aggregate(
            total_cts=Sum('prov_cts'),
            total_gratif=Sum('prov_gratificacion'),
            total_ir5=Sum('ir5_acumulado'),
        )

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Saldos de Apertura ===\n'
            f'  Fecha corte:           {fecha_corte}\n'
            f'  Trabajadores creados:  {creados}\n'
            f'  Trabajadores actualizados: {actualizados}\n'
            f'  Total Prov. CTS:       S/ {agg["total_cts"] or 0:,.2f}\n'
            f'  Total Prov. Gratif:    S/ {agg["total_gratif"] or 0:,.2f}\n'
            f'  Total IR5 acumulado:   S/ {agg["total_ir5"] or 0:,.2f}\n'
            f'  Apertura marcada como COMPLETADA.\n'
        ))
