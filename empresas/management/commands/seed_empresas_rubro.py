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

# Trabajadores demo por rubro (apellidos_nombres, cargo, tipo_trab, sueldo, extra).
# Construcción usa jornal como sueldo_base + categoría; minería usa régimen 14x7.
TRAB_RUBRO = {
    'CONSTRUCCION': [
        ('PÉREZ QUISPE, JUAN CARLOS', 'Operario Albañil', 'Obrero', '89.30',
         {'regimen_laboral': 'CONSTRUCCION', 'categoria_construccion': 'OPERARIO'}),
        ('MAMANI FLORES, LUIS ALBERTO', 'Oficial', 'Obrero', '69.75',
         {'regimen_laboral': 'CONSTRUCCION', 'categoria_construccion': 'OFICIAL'}),
        ('HUAMÁN ROJAS, PEDRO', 'Peón', 'Obrero', '62.80',
         {'regimen_laboral': 'CONSTRUCCION', 'categoria_construccion': 'PEON'}),
    ],
    'MINERIA': [
        ('CONDORI APAZA, MARIO', 'Operador de Mina', 'Obrero', '3500',
         {'regimen_laboral': 'MINERIA', 'regimen_turno': '14x7', 'condicion': 'FORANEO'}),
        ('CHOQUE VILCA, JOSÉ LUIS', 'Perforista', 'Obrero', '3200',
         {'regimen_laboral': 'MINERIA', 'regimen_turno': '14x7', 'condicion': 'FORANEO'}),
        ('QUISPE MAMANI, RAÚL', 'Ayudante de Mina', 'Obrero', '2800',
         {'regimen_laboral': 'MINERIA', 'regimen_turno': '14x7', 'condicion': 'FORANEO'}),
    ],
    'GASTRONOMIA': [
        ('ROJAS DÍAZ, ANA MARÍA', 'Chef', 'Empleado', '3500', {}),
        ('TORRES LEÓN, CARLA', 'Cocinera', 'Empleado', '1800', {}),
        ('VEGA SOTO, MARÍA', 'Mesera', 'Empleado', '1300', {}),
    ],
    'AUDIOVISUAL': [
        ('MENDOZA RÍOS, CARLOS', 'Director Creativo', 'Empleado', '5000', {}),
        ('SILVA PONCE, LAURA', 'Editora de Video', 'Empleado', '3000', {}),
        ('CASTRO NÚÑEZ, DIEGO', 'Diseñador Gráfico', 'Empleado', '2500', {}),
    ],
    'GENERAL': [
        ('GARCÍA LÓPEZ, SOFÍA', 'Gerente Administrativo', 'Empleado', '5000', {}),
        ('RAMÍREZ VARGAS, JORGE', 'Analista', 'Empleado', '2800', {}),
        ('FERNÁNDEZ CRUZ, ELENA', 'Asistente', 'Empleado', '1500', {}),
    ],
}


class Command(BaseCommand):
    help = 'Crea una empresa genérica por rubro (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--solo', default='',
                            help='Lista de rubros separados por coma (ej. CONSTRUCCION,MINERIA).')

    def handle(self, *args, **opts):
        from empresas.models import Empresa

        filtro = {r.strip().upper() for r in opts['solo'].split(',') if r.strip()}
        subarea = self._subarea()
        creadas, actualizadas, trab = 0, 0, 0
        for idx, (ruc, razon, comercial, rubro, ciiu, depto) in enumerate(EMPRESAS_RUBRO):
            if filtro and rubro not in filtro:
                continue
            emp, created = Empresa.objects.get_or_create(
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
                Empresa.objects.filter(ruc=ruc).update(rubro=rubro)  # asegura rubro
                actualizadas += 1
            trab += self._crear_trabajadores(emp, rubro, subarea, idx)
            self.stdout.write(f'  [{rubro}] {razon} ({ruc})')

        self.stdout.write(self.style.SUCCESS(
            f'Empresas por rubro: {creadas} creadas, {actualizadas} actualizadas. '
            f'Trabajadores demo: {trab}.'
        ))

    def _subarea(self):
        """Área/subárea compartida para los trabajadores demo (get_or_create)."""
        from personal.models import Area, SubArea
        area, _ = Area.objects.get_or_create(nombre='Demo Rubros')
        sub, _ = SubArea.objects.get_or_create(nombre='General', area=area)
        return sub

    def _crear_trabajadores(self, empresa, rubro, subarea, rubro_idx) -> int:
        from datetime import date
        from decimal import Decimal
        from personal.models import Personal

        creados = 0
        for wi, (nombre, cargo, tipo_trab, sueldo, extra) in enumerate(TRAB_RUBRO.get(rubro, [])):
            dni = f'{90000000 + rubro_idx * 10 + wi + 1:08d}'
            defaults = dict(
                apellidos_nombres=nombre, cargo=cargo, tipo_trab=tipo_trab,
                subarea=subarea, empresa=empresa, estado='Activo',
                fecha_alta=date(2025, 1, 1), sueldo_base=Decimal(sueldo),
                regimen_laboral=extra.get('regimen_laboral', 'GENERAL'),
                categoria_construccion=extra.get('categoria_construccion', ''),
                regimen_turno=extra.get('regimen_turno', ''),
                condicion=extra.get('condicion', 'LOCAL'),
            )
            _, created = Personal.objects.get_or_create(nro_doc=dni, defaults=defaults)
            if created:
                creados += 1
        return creados
