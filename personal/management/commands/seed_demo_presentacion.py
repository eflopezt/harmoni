"""
Seed de datos para la presentación del domingo.

Crea un escenario completo y realista de una empresa peruana mediana:
  - 1 empresa: "Grupo Andino SAC"
  - 4 áreas: Administración, Operaciones, Recursos Humanos, Finanzas
  - 8 sub-áreas
  - 20 empleados con datos peruanos reales (DNI, nombres, regímenes)
  - 5 usuarios del sistema con diferentes perfiles RBAC
  - ConfiguracionSistema configurada para demo

Uso:
    python manage.py seed_demo_presentacion
    python manage.py seed_demo_presentacion --reset  (borra y recrea)

NOTA: Este seed es idempotente — no duplica si ya existen los datos.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction


class Command(BaseCommand):
    help = 'Crea datos de demostración para la presentación del domingo.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Elimina datos demo existentes y los recrea.')

    def handle(self, *args, **options):
        self.stdout.write('\n=== Harmoni Demo — Cargando datos de presentacion ===\n')

        with transaction.atomic():
            if options['reset']:
                self._reset()

            self._setup_config()
            areas_map = self._crear_areas()
            empleados = self._crear_empleados(areas_map)
            self._crear_usuarios(empleados)

        self.stdout.write(self.style.SUCCESS('\nDatos de demo listos. El sistema esta listo para la presentacion.\n'))
        self.stdout.write('  URL:     http://127.0.0.1:8000')
        self.stdout.write('  Admin:   admin / Harmoni2026!')
        self.stdout.write('  RRHH:    rrhh.admin / Demo2026!')
        self.stdout.write('  Recl.:   reclutadora / Demo2026!')
        self.stdout.write('  Planill: planillas / Demo2026!')
        self.stdout.write('  Jefe:    jefe.ops / Demo2026!\n')

    # ── Reset ─────────────────────────────────────────────────────────────

    def _reset(self):
        from personal.models import Personal, Area, SubArea
        self.stdout.write('  Eliminando datos demo anteriores...')
        User.objects.filter(username__in=[
            'rrhh.admin', 'reclutadora', 'planillas', 'jefe.ops', 'bienestar'
        ]).delete()
        Personal.objects.filter(nro_doc__startswith='7').delete()
        self.stdout.write('  OK')

    # ── Configuracion del sistema ──────────────────────────────────────────

    def _setup_config(self):
        from asistencia.models import ConfiguracionSistema
        config, _ = ConfiguracionSistema.objects.get_or_create(pk=1)
        config.razon_social       = 'Grupo Andino SAC'
        config.ruc                = '20512345678'
        config.modo_sistema       = 'ASISTENCIA'
        config.ciclo_dia_inicio   = 21
        config.mod_prestamos      = True
        config.mod_viaticos       = True
        config.mod_documentos     = True
        config.mod_evaluaciones   = True
        config.mod_capacitaciones = True
        config.mod_reclutamiento  = True
        config.mod_encuestas      = True
        config.mod_salarios       = True
        config.mod_roster         = True
        config.roster_aplica_a    = 'FORANEOS'
        config.save()
        self.stdout.write('  [+] ConfiguracionSistema: Grupo Andino SAC — todos los modulos activos')

    # ── Areas y SubAreas ──────────────────────────────────────────────────

    def _crear_areas(self):
        from personal.models import Area, SubArea

        AREAS_DATA = [
            {
                'nombre': 'Administración',
                'codigo': 'ADM',
                'subareas': ['Recepción', 'Logística', 'Sistemas'],
            },
            {
                'nombre': 'Operaciones',
                'codigo': 'OPS',
                'subareas': ['Planta Norte', 'Planta Sur', 'Mantenimiento'],
            },
            {
                'nombre': 'Recursos Humanos',
                'codigo': 'RRHH',
                'subareas': ['Selección y Onboarding', 'Bienestar y Desarrollo', 'Planillas y Compensaciones'],
            },
            {
                'nombre': 'Finanzas',
                'codigo': 'FIN',
                'subareas': ['Contabilidad', 'Tesorería'],
            },
        ]

        areas_map = {}
        for a_data in AREAS_DATA:
            area, _ = Area.objects.get_or_create(
                nombre=a_data['nombre'],
                defaults={'codigo': a_data['codigo'], 'activa': True},
            )
            areas_map[a_data['codigo']] = {}
            for sa_nombre in a_data['subareas']:
                sa, _ = SubArea.objects.get_or_create(
                    nombre=sa_nombre, area=area,
                    defaults={'activa': True},
                )
                areas_map[a_data['codigo']][sa_nombre] = sa
            self.stdout.write(f'  [+] Area: {area.nombre} ({len(a_data["subareas"])} subareas)')

        return areas_map

    # ── Empleados ──────────────────────────────────────────────────────────

    def _crear_empleados(self, areas_map):
        from personal.models import Personal, SubArea

        # Tomamos sub-áreas
        sa = lambda cod, nombre: areas_map[cod][nombre]

        EMPLEADOS = [
            # ── Administración ──────────────────────────────────────────
            {
                'nro_doc': '70112345', 'nombres': 'Carlos Eduardo',
                'apellidos_nombres': 'QUISPE MAMANI, Carlos Eduardo',
                'cargo': 'Asistente Administrativo', 'subarea': sa('ADM', 'Recepción'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '2500.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '70223456', 'nombres': 'Ana Lucía',
                'apellidos_nombres': 'FLORES TORRES, Ana Lucía',
                'cargo': 'Coordinadora de Logística', 'subarea': sa('ADM', 'Logística'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '3800.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '70334567', 'nombres': 'Miguel Ángel',
                'apellidos_nombres': 'HUANCA CCAMA, Miguel Ángel',
                'cargo': 'Analista de Sistemas', 'subarea': sa('ADM', 'Sistemas'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '4200.00', 'regimen_turno': '5x2',
            },
            # ── Operaciones ─────────────────────────────────────────────
            {
                'nro_doc': '70445678', 'nombres': 'Roberto',
                'apellidos_nombres': 'CONDORI APAZA, Roberto',
                'cargo': 'Supervisor de Planta', 'subarea': sa('OPS', 'Planta Norte'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '5500.00', 'regimen_turno': '14x7',
            },
            {
                'nro_doc': '70556789', 'nombres': 'Jesús Manuel',
                'apellidos_nombres': 'CCALLO YANA, Jesús Manuel',
                'cargo': 'Operario Senior', 'subarea': sa('OPS', 'Planta Norte'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '3200.00', 'regimen_turno': '14x7',
            },
            {
                'nro_doc': '70667890', 'nombres': 'Yeny Patricia',
                'apellidos_nombres': 'VILCA PUMA, Yeny Patricia',
                'cargo': 'Operaria de Producción', 'subarea': sa('OPS', 'Planta Sur'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '2800.00', 'regimen_turno': '21x7',
            },
            {
                'nro_doc': '70778901', 'nombres': 'Fredy',
                'apellidos_nombres': 'COAQUIRA MAMANI, Fredy',
                'cargo': 'Técnico de Mantenimiento', 'subarea': sa('OPS', 'Mantenimiento'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '3500.00', 'regimen_turno': '14x7',
            },
            {
                'nro_doc': '70889012', 'nombres': 'Luciana',
                'apellidos_nombres': 'PILCO SUCA, Luciana',
                'cargo': 'Operaria de Control de Calidad', 'subarea': sa('OPS', 'Planta Sur'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '2600.00', 'regimen_turno': '21x7',
            },
            # ── Recursos Humanos ────────────────────────────────────────
            {
                'nro_doc': '70990123', 'nombres': 'Valeria',
                'apellidos_nombres': 'GUTIERREZ SANCHEZ, Valeria',
                'cargo': 'Gerente de RRHH', 'subarea': sa('RRHH', 'Planillas y Compensaciones'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '8500.00', 'regimen_turno': '5x2',
                'categoria': 'CONFIANZA',
            },
            {
                'nro_doc': '71001234', 'nombres': 'Stefany',
                'apellidos_nombres': 'LAZO CCORIMANYA, Stefany',
                'cargo': 'Analista de Selección', 'subarea': sa('RRHH', 'Selección y Onboarding'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '3200.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '71112345', 'nombres': 'Carmen Rosa',
                'apellidos_nombres': 'PACHECO RIOS, Carmen Rosa',
                'cargo': 'Analista de Bienestar', 'subarea': sa('RRHH', 'Bienestar y Desarrollo'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '2900.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '71223456', 'nombres': 'Diego Alonso',
                'apellidos_nombres': 'MENDOZA VARGAS, Diego Alonso',
                'cargo': 'Analista de Planillas', 'subarea': sa('RRHH', 'Planillas y Compensaciones'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '3400.00', 'regimen_turno': '5x2',
            },
            # ── Finanzas ────────────────────────────────────────────────
            {
                'nro_doc': '71334567', 'nombres': 'Paola Milagros',
                'apellidos_nombres': 'RAMOS HUANCA, Paola Milagros',
                'cargo': 'Contadora General', 'subarea': sa('FIN', 'Contabilidad'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '6200.00', 'regimen_turno': '5x2',
                'categoria': 'CONFIANZA',
            },
            {
                'nro_doc': '71445678', 'nombres': 'Hans',
                'apellidos_nombres': 'BENAVIDES QUIROZ, Hans',
                'cargo': 'Asistente Contable', 'subarea': sa('FIN', 'Contabilidad'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '2200.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '71556789', 'nombres': 'Karina',
                'apellidos_nombres': 'SALAS PINTO, Karina',
                'cargo': 'Tesorera', 'subarea': sa('FIN', 'Tesorería'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '4800.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '71667890', 'nombres': 'Marco Antonio',
                'apellidos_nombres': 'CCOPA HUANCA, Marco Antonio',
                'cargo': 'Analista Financiero', 'subarea': sa('FIN', 'Tesorería'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '4100.00', 'regimen_turno': '5x2',
            },
            # ── Más operaciones foráneo ─────────────────────────────────
            {
                'nro_doc': '71778901', 'nombres': 'Wilbert',
                'apellidos_nombres': 'CHURA QUISPE, Wilbert',
                'cargo': 'Operario de Campo', 'subarea': sa('OPS', 'Planta Norte'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '2500.00', 'regimen_turno': '14x7',
            },
            {
                'nro_doc': '71889012', 'nombres': 'Elvis',
                'apellidos_nombres': 'SUCARI CATACORA, Elvis',
                'cargo': 'Electrotecnico', 'subarea': sa('OPS', 'Mantenimiento'),
                'grupo_tareo': 'RCO', 'condicion': 'FORANEO',
                'sueldo_base': '3800.00', 'regimen_turno': '14x7',
            },
            {
                'nro_doc': '71990123', 'nombres': 'Natividad',
                'apellidos_nombres': 'CUTIPA LAURA, Natividad',
                'cargo': 'Asistente de Almacen', 'subarea': sa('ADM', 'Logística'),
                'grupo_tareo': 'STAFF', 'condicion': 'LOCAL',
                'sueldo_base': '1900.00', 'regimen_turno': '5x2',
            },
            {
                'nro_doc': '72001234', 'nombres': 'Jefe de Operaciones',
                'apellidos_nombres': 'LUNA PALACIOS, Jorge Luis',
                'cargo': 'Jefe de Operaciones', 'subarea': sa('OPS', 'Planta Norte'),
                'grupo_tareo': 'STAFF', 'condicion': 'FORANEO',
                'sueldo_base': '9000.00', 'regimen_turno': '14x7',
                'categoria': 'CONFIANZA',
            },
        ]

        creados = 0
        existentes = 0
        empleados_list = []

        for data in EMPLEADOS:
            defaults = {
                'cargo':         data.get('cargo', ''),
                'subarea':       data['subarea'],
                'grupo_tareo':   data.get('grupo_tareo', 'STAFF'),
                'condicion':     data.get('condicion', 'LOCAL'),
                'sueldo_base':   data.get('sueldo_base', '2000.00'),
                'regimen_turno': data.get('regimen_turno', '5x2'),
                'tipo_doc':      'DNI',
                'estado':        'Activo',
                'tipo_trab':     'Empleado',
                'sexo':          'M',
                'categoria':     data.get('categoria', 'NORMAL'),
            }
            emp, created = Personal.objects.get_or_create(
                nro_doc=data['nro_doc'],
                defaults={**defaults, 'apellidos_nombres': data['apellidos_nombres']},
            )
            empleados_list.append(emp)
            if created:
                creados += 1
            else:
                existentes += 1

        self.stdout.write(f'  [+] Empleados: {creados} creados, {existentes} ya existian')
        return empleados_list

    # ── Usuarios con perfiles RBAC ─────────────────────────────────────────

    def _crear_usuarios(self, empleados):
        from personal.models import Personal
        from core.models import PerfilAcceso

        perfiles = {p.codigo: p for p in PerfilAcceso.objects.all()}

        USUARIOS_DEMO = [
            {
                'username': 'rrhh.admin',
                'first_name': 'Valeria', 'last_name': 'Gutierrez',
                'email': 'rrhh@grupoandino.pe',
                'password': 'Demo2026!',
                'is_staff': True,
                'perfil_codigo': 'admin-rrhh',
                'dni_personal': '70990123',
            },
            {
                'username': 'reclutadora',
                'first_name': 'Stefany', 'last_name': 'Lazo',
                'email': 'reclutamiento@grupoandino.pe',
                'password': 'Demo2026!',
                'is_staff': True,
                'perfil_codigo': 'reclutador',
                'dni_personal': '71001234',
            },
            {
                'username': 'planillas',
                'first_name': 'Diego', 'last_name': 'Mendoza',
                'email': 'planillas@grupoandino.pe',
                'password': 'Demo2026!',
                'is_staff': True,
                'perfil_codigo': 'analista-nominas',
                'dni_personal': '71223456',
            },
            {
                'username': 'bienestar',
                'first_name': 'Carmen', 'last_name': 'Pacheco',
                'email': 'bienestar@grupoandino.pe',
                'password': 'Demo2026!',
                'is_staff': True,
                'perfil_codigo': 'bienestar',
                'dni_personal': '71112345',
            },
            {
                'username': 'jefe.ops',
                'first_name': 'Jorge', 'last_name': 'Luna',
                'email': 'jefe.ops@grupoandino.pe',
                'password': 'Demo2026!',
                'is_staff': True,
                'perfil_codigo': 'jefe-area',
                'dni_personal': '72001234',
            },
        ]

        creados = 0
        for datos in USUARIOS_DEMO:
            user, created = User.objects.get_or_create(
                username=datos['username'],
                defaults={
                    'first_name': datos['first_name'],
                    'last_name':  datos['last_name'],
                    'email':      datos['email'],
                    'is_staff':   datos.get('is_staff', False),
                    'is_active':  True,
                },
            )
            if created:
                user.set_password(datos['password'])
                user.save()
                creados += 1

            # Vincular con Personal y asignar perfil
            perfil = perfiles.get(datos['perfil_codigo'])
            try:
                personal = Personal.objects.get(nro_doc=datos['dni_personal'])
                personal.usuario = user
                personal.perfil_acceso = perfil
                personal.save(update_fields=['usuario', 'perfil_acceso'])
            except Personal.DoesNotExist:
                pass

        self.stdout.write(f'  [+] Usuarios demo: {creados} creados')
        self.stdout.write('')
        self.stdout.write('  Credenciales de demo:')
        self.stdout.write('    admin       / Harmoni2026!   [superusuario — acceso total]')
        self.stdout.write('    rrhh.admin  / Demo2026!      [Administrador RRHH]')
        self.stdout.write('    reclutadora / Demo2026!      [Solo Reclutamiento+Personal]')
        self.stdout.write('    planillas   / Demo2026!      [Solo Planillas+Asistencia]')
        self.stdout.write('    bienestar   / Demo2026!      [Solo Encuestas+Capacitaciones]')
        self.stdout.write('    jefe.ops    / Demo2026!      [Modulos operativos de su area]')


# Import necesario para usar el modelo Personal dentro del Command
from personal.models import Personal
