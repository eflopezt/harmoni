"""
Management command: seed_empresas_rubro

Crea (idempotente) una empresa genérica por rubro, para demos y pruebas.
Cada empresa lleva su `rubro` operativo alineado (Constructora → CONSTRUCCION,
Minera → MINERIA, etc.).

Uso:
  python manage.py seed_empresas_rubro
  python manage.py seed_empresas_rubro --solo CONSTRUCCION,MINERIA
"""
from django.core.management.base import BaseCommand


# (ruc, razon_social, nombre_comercial, rubro, actividad_economica, departamento)
EMPRESAS_RUBRO = [
    ('20600000011', 'CONSTRUCTORA GENÉRICA S.A.C.', 'Constructora Demo',
     'CONSTRUCCION', 'Construcción de edificios completos', 'LIMA'),
    ('20600000029', 'MINERA GENÉRICA S.A.C.', 'Minera Demo',
     'MINERIA', 'Extracción de minerales metalíferos', 'AREQUIPA'),
    ('20600000037', 'RESTAURANTE GENÉRICO S.A.C.', 'Sabores Demo',
     'GASTRONOMIA', 'Restaurantes, bares y cantinas', 'LIMA'),
    ('20600000045', 'AGENCIA CREATIVA GENÉRICA S.A.C.', 'Pixel Demo',
     'AUDIOVISUAL', 'Producción audiovisual y publicidad', 'LIMA'),
    ('20600000053', 'EMPRESA GENÉRICA S.A.C.', 'Oficina Demo',
     'GENERAL', 'Actividades administrativas de oficina', 'LIMA'),
]


class Command(BaseCommand):
    help = 'Crea una empresa genérica por rubro (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--solo', default='',
                            help='Lista de rubros separados por coma (ej. CONSTRUCCION,MINERIA).')

    def handle(self, *args, **opts):
        from empresas.models import Empresa

        filtro = {r.strip().upper() for r in opts['solo'].split(',') if r.strip()}
        creadas, actualizadas = 0, 0
        for ruc, razon, comercial, rubro, ciiu, depto in EMPRESAS_RUBRO:
            if filtro and rubro not in filtro:
                continue
            _, created = Empresa.objects.get_or_create(
                ruc=ruc,
                defaults=dict(
                    razon_social=razon, nombre_comercial=comercial,
                    rubro=rubro, actividad_economica=ciiu,
                    departamento=depto, sector='PRIVADO',
                ),
            )
            if created:
                creadas += 1
            else:
                # Asegura el rubro aunque la empresa ya existiera.
                Empresa.objects.filter(ruc=ruc).update(rubro=rubro)
                actualizadas += 1
            self.stdout.write(f'  [{rubro}] {razon} ({ruc})')

        self.stdout.write(self.style.SUCCESS(
            f'Empresas por rubro: {creadas} creadas, {actualizadas} actualizadas.'
        ))
