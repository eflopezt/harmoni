"""
Seed: 6 empresas/locales adicionales para simular Grupo Sabores premium.

Crea RUCs gastronómicos de fantasía — grupo de restaurantes peruanos diversos:
  - Sabores del Sur Premium (matriz / fine dining criollo)
  - Sabores del Sur Marino (cevichería)
  - Sabores del Sur Express (delivery / dark kitchen)
  - Sabores del Sur Asado (parrilla)
  - Sabores del Sur Café (boutique de desayunos)
  - Sabores del Sur Central (cocina de producción / catering)

Asigna trabajadores de Personal entre las nuevas empresas (rota).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from empresas.models import Empresa
from personal.models import Personal


LOCALES_EDO = [
    {
        'ruc':              '20100000111',
        'razon_social':     'Sabores del Sur Premium S.A.C.',
        'nombre_comercial': 'Sabores del Sur Premium',
        'subdominio':       'premium',
        'direccion':        'Av. La Mar 458, Miraflores',
        'email_rrhh':       'rrhh.premium@saboresdelsur.com.pe',
    },
    {
        'ruc':              '20100000222',
        'razon_social':     'Sabores del Sur Marino S.A.C.',
        'nombre_comercial': 'Sabores del Sur Marino',
        'subdominio':       'marino',
        'direccion':        'Malecón Cisneros 245, Miraflores',
        'email_rrhh':       'rrhh.marino@saboresdelsur.com.pe',
    },
    {
        'ruc':              '20100000333',
        'razon_social':     'Sabores del Sur Asado S.A.C.',
        'nombre_comercial': 'Sabores del Sur Asado',
        'subdominio':       'asado',
        'direccion':        'Calle Berlín 384, Miraflores',
        'email_rrhh':       'rrhh.asado@saboresdelsur.com.pe',
    },
    {
        'ruc':              '20100000444',
        'razon_social':     'Sabores del Sur Café S.A.C.',
        'nombre_comercial': 'Sabores del Sur Café',
        'subdominio':       'cafe',
        'direccion':        'Av. Pardo y Aliaga 695, San Isidro',
        'email_rrhh':       'rrhh.cafe@saboresdelsur.com.pe',
    },
    {
        'ruc':              '20100000555',
        'razon_social':     'Sabores del Sur Express S.A.C.',
        'nombre_comercial': 'Sabores del Sur Express',
        'subdominio':       'express',
        'direccion':        'Av. La Encalada 1257, Surco',
        'email_rrhh':       'rrhh.express@saboresdelsur.com.pe',
    },
    {
        'ruc':              '20100000666',
        'razon_social':     'Sabores del Sur Central S.A.C.',
        'nombre_comercial': 'Sabores del Sur Central',
        'subdominio':       'central',
        'direccion':        'Calle Los Tornos 198, Ate',
        'email_rrhh':       'logistica@saboresdelsur.com.pe',
    },
]


class Command(BaseCommand):
    help = 'Crea 6 empresas gastronómicas del Grupo Sabores + asigna trabajadores rotando.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--rebalance',
            action='store_true',
            help='Re-asignar trabajadores existentes en rotación uniforme entre los locales.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        creados = 0
        existentes = 0
        empresas_creadas = []

        for data in LOCALES_EDO:
            emp, created = Empresa.objects.get_or_create(
                ruc=data['ruc'],
                defaults={
                    'razon_social':     data['razon_social'],
                    'nombre_comercial': data['nombre_comercial'],
                    'subdominio':       data['subdominio'],
                    'direccion':        data['direccion'],
                    'email_rrhh':       data['email_rrhh'],
                    'activa':           True,
                    'regimen_laboral':  'GENERAL',
                },
            )
            if created:
                creados += 1
                empresas_creadas.append(emp)
                self.stdout.write(f'  ✓ Creado: {emp.nombre_comercial} (RUC {emp.ruc})')
            else:
                existentes += 1
                empresas_creadas.append(emp)
                self.stdout.write(f'  · Existe: {emp.nombre_comercial} (RUC {emp.ruc})')

        # Rotación de trabajadores entre locales
        if opts['rebalance'] or creados > 0:
            trabajadores = list(
                Personal.objects.filter(estado='Activo').order_by('id')
            )
            n_locales = len(empresas_creadas)
            asignados = 0
            for i, p in enumerate(trabajadores):
                # Mantener el primero (Empresa demo principal) intacto si no es rebalance puro
                if not opts['rebalance'] and p.empresa_id and p.empresa_id == 1:
                    # Solo redistribuye 60% de los workers (mantén 40% en empresa principal)
                    if i % 5 < 2:
                        continue
                target = empresas_creadas[i % n_locales]
                if p.empresa_id != target.pk:
                    p.empresa = target
                    p.save(update_fields=['empresa'])
                    asignados += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ {asignados} trabajadores redistribuidos entre {n_locales} locales.'
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f'\n=== Resumen ===\n'
                f'  Empresas creadas:     {creados}\n'
                f'  Empresas existentes:  {existentes}\n'
                f'  Total locales activos: {Empresa.objects.filter(activa=True).count()}\n'
            )
        )
