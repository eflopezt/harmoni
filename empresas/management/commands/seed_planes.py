"""
Management command: crear los 3 planes default de Harmoni SaaS.

Uso: python manage.py seed_planes
"""
from django.core.management.base import BaseCommand

from empresas.models_billing import Plan


PLANES_DEFAULT = [
    {
        'nombre': 'Starter',
        'codigo': 'starter',
        'descripcion': 'Ideal para empresas pequeñas que inician su digitalización de RRHH.',
        'precio_mensual': 149,
        'precio_anual': 1490,  # ~17% descuento
        'max_empleados': 30,
        'orden': 1,
        'destacado': False,
        'modulos_incluidos': [
            'personal',
            'asistencia',
            'vacaciones',
            'nominas',
            'portal',
            'documentos',
        ],
        'features': [
            'Hasta 30 empleados',
            'Personal y asistencia',
            'Nóminas básicas',
            'Vacaciones',
            'Portal del empleado',
            'Documentos',
            'Soporte por email',
        ],
    },
    {
        'nombre': 'Profesional',
        'codigo': 'profesional',
        'descripcion': 'Para empresas en crecimiento que necesitan gestión integral de RRHH.',
        'precio_mensual': 349,
        'precio_anual': 3490,  # ~17% descuento
        'max_empleados': 100,
        'orden': 2,
        'destacado': True,
        'modulos_incluidos': [
            'personal',
            'asistencia',
            'vacaciones',
            'nominas',
            'portal',
            'documentos',
            'prestamos',
            'viaticos',
            'capacitaciones',
            'evaluaciones',
            'calendario',
            'onboarding',
            'comunicaciones',
            'analytics',
            'salarios',
        ],
        'features': [
            'Hasta 100 empleados',
            'Todos los módulos Starter',
            'Préstamos y viáticos',
            'Capacitaciones',
            'Evaluaciones de desempeño',
            'Onboarding digital',
            'Analytics y KPIs',
            'Calendario integrado',
            'Chat AI incluido',
            'Soporte prioritario',
        ],
    },
    {
        'nombre': 'Enterprise',
        'codigo': 'enterprise',
        'descripcion': 'Solución completa para empresas grandes con necesidades avanzadas.',
        'precio_mensual': 799,
        'precio_anual': 7990,  # ~17% descuento
        'max_empleados': 0,  # unlimited
        'orden': 3,
        'destacado': False,
        'modulos_incluidos': [
            'personal',
            'asistencia',
            'vacaciones',
            'nominas',
            'portal',
            'documentos',
            'prestamos',
            'viaticos',
            'capacitaciones',
            'evaluaciones',
            'calendario',
            'onboarding',
            'comunicaciones',
            'analytics',
            'salarios',
            'reclutamiento',
            'disciplinaria',
            'encuestas',
            'cierre',
            'integraciones',
            'workflows',
        ],
        'features': [
            'Empleados ilimitados',
            'Todos los módulos',
            'Reclutamiento y selección',
            'Workflows personalizados',
            'Integraciones (SUNAT, S10)',
            'Encuestas de clima',
            'Disciplinaria',
            'Cierre de mes automatizado',
            'AI avanzado con OCR',
            'Multi-empresa',
            'Soporte dedicado 24/7',
            'SLA garantizado',
        ],
    },
]


class Command(BaseCommand):
    help = 'Crea los 3 planes default de Harmoni SaaS (Starter, Profesional, Enterprise)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobrescribir planes existentes',
        )

    def handle(self, *args, **options):
        force = options['force']
        created = 0
        updated = 0

        for plan_data in PLANES_DEFAULT:
            codigo = plan_data['codigo']
            existing = Plan.objects.filter(codigo=codigo).first()

            if existing and not force:
                self.stdout.write(
                    self.style.WARNING(f'  Plan "{codigo}" ya existe — omitido (use --force)')
                )
                continue

            if existing and force:
                for key, value in plan_data.items():
                    setattr(existing, key, value)
                existing.save()
                updated += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  Plan "{codigo}" actualizado')
                )
            else:
                Plan.objects.create(**plan_data)
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f'  Plan "{codigo}" creado')
                )

        self.stdout.write('')
        self.stdout.write(
            self.style.SUCCESS(
                f'Listo: {created} creados, {updated} actualizados.'
            )
        )
