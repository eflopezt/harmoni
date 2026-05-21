"""
Seed: 6 empresas/locales adicionales para simular Grupo EDO premium.

Crea RUCs gastronómicos de fantasía estilo Acurio Group:
  - Restaurante Insignia (fine dining)
  - Bistró Costero (mar y leña)
  - Cocina Nikkei (fusión peruana-japonesa)
  - Cafetería Boutique (desayunos)
  - Wine Bar Anidado (cava)
  - Cocina de Producción (catering / dark kitchen)

Asigna trabajadores de Personal entre las nuevas empresas (rota).
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from empresas.models import Empresa
from personal.models import Personal


LOCALES_EDO = [
    {
        'ruc':              '20100000111',
        'razon_social':     'Inversiones Gastronómicas del Sur S.A.C.',
        'nombre_comercial': 'Restaurante Insignia',
        'subdominio':       'insignia',
        'direccion':        'Av. La Mar 458, Miraflores',
        'email_rrhh':       'rrhh.insignia@edo.com.pe',
    },
    {
        'ruc':              '20100000222',
        'razon_social':     'Operadora Costera S.A.C.',
        'nombre_comercial': 'Bistró Costero',
        'subdominio':       'costero',
        'direccion':        'Malecón Cisneros 245, Miraflores',
        'email_rrhh':       'rrhh.costero@edo.com.pe',
    },
    {
        'ruc':              '20100000333',
        'razon_social':     'Cocina Nikkei Premium S.A.C.',
        'nombre_comercial': 'Nikkei House',
        'subdominio':       'nikkei',
        'direccion':        'Calle Berlín 384, Miraflores',
        'email_rrhh':       'rrhh.nikkei@edo.com.pe',
    },
    {
        'ruc':              '20100000444',
        'razon_social':     'Café Boutique del Olivar S.A.C.',
        'nombre_comercial': 'Café del Olivar',
        'subdominio':       'olivar',
        'direccion':        'Av. Pardo y Aliaga 695, San Isidro',
        'email_rrhh':       'rrhh.cafe@edo.com.pe',
    },
    {
        'ruc':              '20100000555',
        'razon_social':     'Vinos y Sabores del Pacífico S.A.C.',
        'nombre_comercial': 'Anidado Wine Bar',
        'subdominio':       'anidado',
        'direccion':        'Av. La Encalada 1257, Surco',
        'email_rrhh':       'rrhh.anidado@edo.com.pe',
    },
    {
        'ruc':              '20100000666',
        'razon_social':     'Cocina Central de Producción S.A.C.',
        'nombre_comercial': 'Cocina Central',
        'subdominio':       'central',
        'direccion':        'Calle Los Tornos 198, Ate',
        'email_rrhh':       'logistica@edo.com.pe',
    },
]


class Command(BaseCommand):
    help = 'Crea 6 empresas gastronómicas del Grupo EDO + asigna trabajadores rotando.'

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
