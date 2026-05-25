"""
Seed de demo gastronómico — Cadena de restaurantes peruanos (perfilado para Grupo Sabores).

Pensado para correr DESPUÉS de `seed_demo_presentacion` + `seed_demo_completar`,
en el ciclo nocturno del reset_demo.sh del VPS. Suma sobre lo que ya existe — NO
borra trabajadores ni áreas previos.

Qué crea (idempotente — la 2da corrida no duplica):
  1. 3 empresas multi-RUC ("Sabores del Sur SAC", "Sabores del Sur Premium SAC", "Sabores del Sur Express SAC")
     - Si la empresa demo principal ya existe, la actualiza a "Sabores del Sur SAC"
  2. Áreas + SubÁreas típicas de restaurante (Cocina, Salón, Barra, Caja, Limpieza, Admin)
  3. Cargos normalizados (Chef Ejecutivo, Mozo, Bartender, Cajero, etc.)
  4. ~50 trabajadores nuevos (DNI 73000001 en adelante, sin chocar con seeds previos)
     - Nombres peruanos realistas, sueldos coherentes con mercado gastronomía Perú
     - AFP/ONP, asignación familiar, fechas de ingreso distribuidas
     - Distribuidos entre las 3 RUCs (40/35/25)
  5. Régimenes de turno rotativo (Mañana 11-19, Tarde-Noche 16-00, Cierre 18-02)
  6. Conceptos remunerativos especiales — Propinas, Recargo por consumo
  7. Líneas de propinas (S/.200–800) en la última planilla regular (mes-1) a ~20 mozos
     — si no hay planilla previa, lo registra como TODO en el output.

Uso:
    python manage.py seed_demo_gastronomia
    python manage.py seed_demo_gastronomia --dry-run    (no escribe nada)

Línea para agregar al final del `reset_demo.sh` del VPS (después de los seeds previos):

    docker exec $EXEC_ENV harmoni-demo-web python manage.py seed_demo_gastronomia >> $LOG 2>&1 || echo "  ! seed_demo_gastronomia fallo (no critico)" >> $LOG
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


# ─────────────────────────────────────────────────────────────────────────────
# DATOS — Listas hardcoded para reproducibilidad
# ─────────────────────────────────────────────────────────────────────────────

NOMBRES_M = [
    'Carlos', 'Luis', 'Jorge', 'Miguel', 'Diego', 'Juan', 'Pedro', 'José', 'Ricardo',
    'Daniel', 'Andrés', 'Fernando', 'Alberto', 'Eduardo', 'Manuel', 'Roberto', 'Hugo',
    'Renzo', 'Sergio', 'Cristian', 'Marco', 'Pablo', 'Iván', 'Raúl', 'Bruno', 'Álvaro',
    'Frank', 'Wilmer', 'Yván', 'Kevin',
]
NOMBRES_F = [
    'María', 'Ana', 'Rosa', 'Lucía', 'Carmen', 'Patricia', 'Sandra', 'Karla', 'Yessica',
    'Verónica', 'Milagros', 'Pamela', 'Andrea', 'Daniela', 'Stefany', 'Vanessa', 'Karen',
    'Yenny', 'Mariela', 'Cinthia', 'Gisela', 'Jenny', 'Lourdes', 'Brenda', 'Diana',
    'Fiorella', 'Estefani', 'Magaly', 'Lizbeth', 'Geraldine',
]
APELLIDOS = [
    'Quispe', 'Mamani', 'Huamán', 'Flores', 'Torres', 'Vargas', 'Rojas', 'Castro',
    'Ramos', 'Pérez', 'Sánchez', 'García', 'Gómez', 'Díaz', 'López', 'Cruz',
    'Ríos', 'Vega', 'Salazar', 'Espinoza', 'Cárdenas', 'Mendoza', 'Chávez', 'Huanca',
    'Condori', 'Apaza', 'Sucari', 'Cutipa', 'Ccama', 'Coaquira', 'Pacheco', 'Salas',
    'Pinto', 'Yana', 'Calderón', 'Aguirre', 'Ponce', 'Loayza', 'Bardales', 'Trujillo',
    'Camacho', 'Ñahui', 'Choquehuanca', 'Limaco', 'Pumacahua', 'Suca',
]

# Catálogo de cargos por área. Tupla: (cargo, nivel_cargo, sueldo_min, sueldo_max, es_confianza)
CARGOS_POR_AREA = {
    'COC': [
        ('Chef Ejecutivo',       3, 3500, 4000, False),
        ('Cocinero Senior',      4, 2500, 3200, False),
        ('Cocinero',             5, 1600, 2000, False),
        ('Cocinero Junior',      6, 1200, 1400, False),
        ('Ayudante de Cocina',   6, 1130, 1300, False),
    ],
    'SAL': [
        ('Mozo',                 6, 1200, 1500, False),
        ('Mozo Senior',          5, 1500, 1800, False),
        ('Hostess',              5, 1300, 1500, False),
        ('Anfitrión',            5, 1300, 1500, False),
    ],
    'BAR': [
        ('Bartender',            5, 1800, 2200, False),
        ('Ayudante de Barra',    6, 1200, 1400, False),
    ],
    'CAJ': [
        ('Cajero',               5, 1300, 1600, False),
    ],
    'LIM': [
        ('Auxiliar de Limpieza', 6, 1130, 1200, False),
    ],
    'ADM': [
        ('Administrador de Local', 3, 3500, 4500, True),
        ('Asistente Contable',     5, 2200, 2800, False),
        ('Asistente RRHH',         5, 2500, 3000, False),
    ],
}

# SubÁreas por área. Mapeo nombre del área → lista de subáreas + código de área
AREAS_RESTAURANTE = [
    ('Cocina',          'COC', ['Cocina Especialidad', 'Cocina Caliente', 'Cocina Fría']),
    ('Salón',           'SAL', ['Salón Principal', 'Terraza']),
    ('Barra',           'BAR', ['Barra']),
    ('Caja',            'CAJ', ['Caja']),
    ('Limpieza',        'LIM', ['Limpieza General']),
    ('Administración',  'ADM', ['Administración', 'Contabilidad', 'RRHH']),
]

# Distribución de cargos en la plantilla (cuántos de cada uno aprox. en 50 nuevos)
DISTRIBUCION_NUEVOS = [
    # (area, cargo, cantidad)
    ('SAL', 'Mozo',                  12),
    ('SAL', 'Mozo Senior',            3),
    ('SAL', 'Hostess',                2),
    ('SAL', 'Anfitrión',              1),
    ('COC', 'Cocinero',               6),
    ('COC', 'Cocinero Junior',        4),
    ('COC', 'Cocinero Senior',        3),
    ('COC', 'Chef Ejecutivo',         2),
    ('COC', 'Ayudante de Cocina',     4),
    ('BAR', 'Bartender',              2),
    ('BAR', 'Ayudante de Barra',      1),
    ('CAJ', 'Cajero',                 3),
    ('LIM', 'Auxiliar de Limpieza',   3),
    ('ADM', 'Administrador de Local', 2),
    ('ADM', 'Asistente Contable',     1),
    ('ADM', 'Asistente RRHH',         1),
]  # total = 50

# Empresas (3 RUCs) — RUCs ficticios pero estructura SUNAT-válida
EMPRESAS_EDO = [
    {
        'ruc': '20100100100',
        'razon_social': 'Sabores del Sur SAC',
        'nombre_comercial': 'Sabores del Sur (Criollo)',
        'subdominio': 'demo',
        'es_principal': True,
        'direccion': 'Av. José Pardo 813, Miraflores',
        'distrito': 'Miraflores', 'provincia': 'Lima', 'departamento': 'Lima',
        'ubigeo': '150122',
        'email_rrhh': 'rrhh@saboresdelsur.pe',
        'telefono': '(01) 446-5555',
        'actividad_economica': '5610 - Restaurantes',
        'representante_legal': 'Manuel Salazar Aguirre',
        'cargo_representante': 'Gerente General',
        'nro_doc_representante': '09876543',
        'porcentaje_personal': 40,  # % de los 50 nuevos
    },
    {
        'ruc': '20100100200',
        'razon_social': 'Sabores del Sur Marino SAC',
        'nombre_comercial': 'Sabores del Sur Marino (Cevichería)',
        'subdominio': None,
        'es_principal': False,
        'direccion': 'Av. La Encalada 1257, Surco',
        'distrito': 'Santiago de Surco', 'provincia': 'Lima', 'departamento': 'Lima',
        'ubigeo': '150141',
        'email_rrhh': 'rrhh@saboresdelsur.pe',
        'telefono': '(01) 437-8888',
        'actividad_economica': '5610 - Restaurantes',
        'representante_legal': 'Manuel Salazar Aguirre',
        'cargo_representante': 'Gerente General',
        'nro_doc_representante': '09876543',
        'porcentaje_personal': 35,
    },
    {
        'ruc': '20100100300',
        'razon_social': 'Sabores del Sur Express SAC',
        'nombre_comercial': 'Sabores del Sur Express (Dark Kitchen)',
        'subdominio': None,
        'es_principal': False,
        'direccion': 'Calle Las Begonias 415, San Isidro',
        'distrito': 'San Isidro', 'provincia': 'Lima', 'departamento': 'Lima',
        'ubigeo': '150131',
        'email_rrhh': 'rrhh@saboresdelsur.pe',
        'telefono': '(01) 222-3333',
        'actividad_economica': '5621 - Servicio de comidas (catering/delivery)',
        'representante_legal': 'Manuel Salazar Aguirre',
        'cargo_representante': 'Gerente General',
        'nro_doc_representante': '09876543',
        'porcentaje_personal': 25,
    },
]

# Regímenes de turno gastronomía
REGIMENES_GASTRO = [
    {
        'codigo': 'GASTRO_M', 'nombre': 'Gastronomía Mañana 11-19',
        'jornada_tipo': 'SEMANAL',
        'dias_trabajo_ciclo': 6, 'dias_descanso_ciclo': 1,
        'es_nocturno': False,
        'hora_entrada': '11:00', 'hora_salida': '19:00',
        'salida_dia_siguiente': False,
        'descripcion': 'Turno de mañana — atención de almuerzo. 8h efectivas con 60min refrigerio.',
    },
    {
        'codigo': 'GASTRO_TN', 'nombre': 'Gastronomía Tarde-Noche 16-00',
        'jornada_tipo': 'NOCTURNA',
        'dias_trabajo_ciclo': 6, 'dias_descanso_ciclo': 1,
        'es_nocturno': True,
        'hora_entrada': '16:00', 'hora_salida': '00:00',
        'salida_dia_siguiente': True,
        'descripcion': 'Turno tarde-noche — cena. Tramo nocturno 22:00–00:00 (+35% recargo).',
    },
    {
        'codigo': 'GASTRO_C', 'nombre': 'Gastronomía Cierre 18-02',
        'jornada_tipo': 'NOCTURNA',
        'dias_trabajo_ciclo': 6, 'dias_descanso_ciclo': 1,
        'es_nocturno': True,
        'hora_entrada': '18:00', 'hora_salida': '02:00',
        'salida_dia_siguiente': True,
        'descripcion': 'Turno cierre — cena + cierre de local. Mayoritariamente nocturno.',
    },
]

# Conceptos remunerativos gastronómicos
CONCEPTOS_GASTRO = [
    {
        'codigo': 'propinas',
        'nombre': 'Propinas',
        'tipo': 'INGRESO',
        'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': False, 'afecto_renta': False,
        'afecto_cts': False, 'afecto_gratif': False,
        'orden': 60,
    },
    {
        'codigo': 'recargo-consumo',
        'nombre': 'Recargo por Consumo',
        'tipo': 'INGRESO',
        'subtipo': 'NO_REMUNERATIVO',
        'formula': 'MANUAL',
        'afecto_essalud': False, 'afecto_renta': False,
        'afecto_cts': False, 'afecto_gratif': False,
        'orden': 61,
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Pobla la demo con datos de cadena de restaurantes peruanos (Grupo Sabores). '
        'Idempotente — corre después de seed_demo_presentacion/completar.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe nada — solo muestra qué crearía.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        random.seed(42)  # reproducibilidad

        marker = ' [DRY-RUN]' if self.dry_run else ''
        self.stdout.write(f'\n=== Harmoni Demo — Seed Gastronomía (Grupo Sabores){marker} ===\n')

        # Resumen para reporte final
        self.resumen = {
            'empresas_creadas': 0, 'empresas_actualizadas': 0,
            'areas_creadas': 0, 'subareas_creadas': 0,
            'cargos_creados': 0,
            'trabajadores_creados': 0, 'trabajadores_existentes': 0,
            'regimenes_turno': 0, 'horarios_turno': 0,
            'conceptos_creados': 0,
            'propinas_aplicadas': 0,
            'todos': [],
        }

        if self.dry_run:
            # En dry-run igual entramos al atomic pero hacemos rollback al final
            try:
                with transaction.atomic():
                    self._run()
                    raise _DryRunRollback()
            except _DryRunRollback:
                self.stdout.write(self.style.WARNING('\n  [DRY-RUN] Rollback — no se persistieron cambios.\n'))
        else:
            with transaction.atomic():
                self._run()

        self._reporte_final()

    # ─────────────────────────────────────────────────────────────────────
    # Pipeline principal
    # ─────────────────────────────────────────────────────────────────────

    def _run(self):
        empresas = self._crear_empresas()
        areas_por_empresa = self._crear_areas_por_empresa(empresas)
        cargos = self._crear_cargos()
        self._crear_trabajadores(empresas, areas_por_empresa, cargos)
        self._crear_regimenes_turno()
        self._crear_conceptos_gastro()
        self._aplicar_propinas_ultima_planilla()
        self._regenerar_planillas_existentes()

    def _regenerar_planillas_existentes(self):
        """Regenera todos los periodos REGULAR existentes para incluir los
        nuevos trabajadores de gastronomía en la planilla. Idempotente: si
        un periodo no existe (BD recién creada), simplemente se salta."""
        from nominas.models import PeriodoNomina
        from nominas.engine import generar_periodo
        from datetime import date

        # Garantizar que existe un período Mayo 2026 para que la demo tenga
        # data en "este mes". Si los seeds previos no lo crearon, lo creamos.
        try:
            from nominas.models import PeriodoNomina as PN
            PN.objects.get_or_create(
                anio=2026, mes=5, tipo='REGULAR',
                defaults={
                    'fecha_inicio': date(2026, 5, 1),
                    'fecha_fin': date(2026, 5, 31),
                    'descripcion': 'Planilla Mayo 2026',
                    'estado': 'CALCULADO',
                },
            )
        except Exception as exc:
            self.resumen['todos'].append(f'No se pudo crear/asegurar período Mayo 2026: {exc}')

        regenerados = 0
        for p in PeriodoNomina.objects.filter(tipo='REGULAR').order_by('-fecha_fin'):
            estado_orig = p.estado
            try:
                # Si está APROBADO/CERRADO, bajar a CALCULADO para permitir regen
                if estado_orig in ('APROBADO', 'CERRADO'):
                    p.estado = 'CALCULADO'
                    p.save(update_fields=['estado'])
                generar_periodo(p)
                # Restaurar estado original (mantiene el "look and feel" del demo)
                if p.estado != estado_orig:
                    p.estado = estado_orig
                    p.save(update_fields=['estado'])
                regenerados += 1
            except Exception as exc:
                self.resumen['todos'].append(
                    f'No se pudo regenerar período {p.descripcion or p.pk}: {exc}'
                )
        if regenerados:
            self.stdout.write(
                self.style.SUCCESS(
                    f'  [+] Planillas regeneradas con todos los workers: {regenerados} períodos'
                )
            )

    # ─────────────────────────────────────────────────────────────────────
    # 1. Empresas multi-RUC
    # ─────────────────────────────────────────────────────────────────────

    def _crear_empresas(self):
        from empresas.models import Empresa

        empresas_creadas = []

        for e_data in EMPRESAS_EDO:
            # Buscamos por RUC primero; si no existe pero hay subdominio='demo' previo,
            # actualizamos esa empresa para que pase a ser "Sabores del Sur SAC".
            empresa = None
            if e_data['subdominio']:
                empresa = Empresa.objects.filter(subdominio=e_data['subdominio']).first()

            defaults = {
                'razon_social': e_data['razon_social'],
                'nombre_comercial': e_data['nombre_comercial'],
                'direccion': e_data['direccion'],
                'distrito': e_data['distrito'],
                'provincia': e_data['provincia'],
                'departamento': e_data['departamento'],
                'ubigeo': e_data['ubigeo'],
                'email_rrhh': e_data['email_rrhh'],
                'telefono': e_data['telefono'],
                'actividad_economica': e_data['actividad_economica'],
                'representante_legal': e_data['representante_legal'],
                'cargo_representante': e_data['cargo_representante'],
                'nro_doc_representante': e_data['nro_doc_representante'],
                'regimen_laboral': 'GENERAL',
                'sector': 'PRIVADO',
                'es_principal': e_data['es_principal'],
                'activa': True,
            }

            if empresa is None:
                # No hay empresa por subdominio — buscar/crear por RUC
                empresa, created = Empresa.objects.get_or_create(
                    ruc=e_data['ruc'],
                    defaults={**defaults, 'subdominio': e_data['subdominio']},
                )
                if created:
                    self.resumen['empresas_creadas'] += 1
                    self.stdout.write(f'  [+] Empresa creada: {empresa.razon_social} (RUC {empresa.ruc})')
                else:
                    self._actualizar_empresa(empresa, defaults)
                    self.resumen['empresas_actualizadas'] += 1
                    self.stdout.write(f'  [~] Empresa actualizada: {empresa.razon_social} (RUC {empresa.ruc})')
            else:
                # Existe la empresa por subdominio=demo → actualizamos a Sabores del Sur
                empresa.ruc = e_data['ruc']  # puede cambiar el RUC ficticio previo
                self._actualizar_empresa(empresa, defaults)
                self.resumen['empresas_actualizadas'] += 1
                self.stdout.write(
                    f'  [~] Empresa demo principal actualizada -> {empresa.razon_social} (RUC {empresa.ruc})'
                )

            empresa._porcentaje_personal = e_data['porcentaje_personal']
            empresas_creadas.append(empresa)

        return empresas_creadas

    def _actualizar_empresa(self, empresa, defaults):
        for k, v in defaults.items():
            setattr(empresa, k, v)
        empresa.save()

    # ─────────────────────────────────────────────────────────────────────
    # 2. Áreas y SubÁreas (compartidas entre empresas — Area no tiene FK empresa)
    # ─────────────────────────────────────────────────────────────────────

    def _crear_areas_por_empresa(self, empresas):
        """
        El modelo Area no tiene FK a Empresa — son globales. Creamos las áreas
        gastronomía una sola vez y todas las empresas las comparten.
        """
        from personal.models import Area, SubArea

        areas_map = {}  # codigo → {subarea_nombre: SubArea}

        for nombre_area, codigo, subareas in AREAS_RESTAURANTE:
            area, created = Area.objects.get_or_create(
                nombre=nombre_area,
                defaults={'codigo': codigo, 'activa': True, 'descripcion': f'Área gastronómica — {nombre_area}'},
            )
            if created:
                self.resumen['areas_creadas'] += 1
                self.stdout.write(f'  [+] Área: {nombre_area} ({codigo})')
            else:
                # Si el código está vacío, completarlo
                if not area.codigo:
                    area.codigo = codigo
                    area.save(update_fields=['codigo'])

            areas_map[codigo] = {}
            for sa_nombre in subareas:
                sa, sa_created = SubArea.objects.get_or_create(
                    nombre=sa_nombre, area=area,
                    defaults={'activa': True},
                )
                areas_map[codigo][sa_nombre] = sa
                if sa_created:
                    self.resumen['subareas_creadas'] += 1

        return areas_map

    # ─────────────────────────────────────────────────────────────────────
    # 3. Cargos normalizados
    # ─────────────────────────────────────────────────────────────────────

    def _crear_cargos(self):
        from personal.models import Cargo

        cargos_map = {}  # nombre → Cargo
        for codigo_area, lista in CARGOS_POR_AREA.items():
            for nombre, nivel, smin, smax, confianza in lista:
                cargo, created = Cargo.objects.get_or_create(
                    nombre=nombre,
                    defaults={
                        'nivel': nivel,
                        'es_confianza': confianza,
                        'es_fiscalizable': not confianza,
                        'activo': True,
                        'descripcion': f'Cargo gastronomía — área {codigo_area}',
                    },
                )
                cargos_map[nombre] = cargo
                if created:
                    self.resumen['cargos_creados'] += 1

        return cargos_map

    # ─────────────────────────────────────────────────────────────────────
    # 4. Trabajadores (~50 nuevos)
    # ─────────────────────────────────────────────────────────────────────

    def _crear_trabajadores(self, empresas, areas_map, cargos_map):
        from personal.models import Personal

        # Generamos la lista plana de cargos a poblar
        plantilla = []
        for codigo_area, nombre_cargo, cantidad in DISTRIBUCION_NUEVOS:
            for _ in range(cantidad):
                plantilla.append((codigo_area, nombre_cargo))
        # Mezclar para distribuir aleatoriamente entre empresas
        random.shuffle(plantilla)

        # Construir ranking de empresas según %
        empresa_buckets = []  # lista de empresas repetida según peso
        for emp in empresas:
            empresa_buckets.extend([emp] * emp._porcentaje_personal)

        # DNI determinista por slot — 73000001, 73000002, ... — para que la
        # 2da corrida encuentre cada DNI ya existente y haga skip (idempotente).
        dni_inicial = 73000001
        creados = 0
        existentes = 0

        for idx, (codigo_area, nombre_cargo) in enumerate(plantilla):
            dni = f'{dni_inicial + idx:08d}'

            # Subárea aleatoria del área
            subareas_disp = list(areas_map.get(codigo_area, {}).values())
            subarea = random.choice(subareas_disp) if subareas_disp else None

            # Datos del cargo
            cargo_obj = cargos_map.get(nombre_cargo)
            cargo_meta = next(
                (c for c in CARGOS_POR_AREA[codigo_area] if c[0] == nombre_cargo),
                (nombre_cargo, 5, 1500, 2000, False),
            )
            _, _, smin, smax, es_confianza = cargo_meta
            sueldo = Decimal(str(random.randint(smin, smax)))

            # Sexo random — bias por cargo
            if nombre_cargo in ('Hostess',):
                sexo = 'F'
            elif nombre_cargo in ('Chef Ejecutivo', 'Cocinero Senior'):
                sexo = random.choices(['M', 'F'], weights=[8, 2])[0]
            else:
                sexo = random.choice(['M', 'F'])

            nombre_pila = random.choice(NOMBRES_F if sexo == 'F' else NOMBRES_M)
            apellido_1 = random.choice(APELLIDOS)
            apellido_2 = random.choice(APELLIDOS)
            apellidos_nombres = f'{apellido_1.upper()} {apellido_2.upper()}, {nombre_pila}'

            # AFP/ONP
            if random.random() < 0.60:
                regimen_pension = 'AFP'
                afp = random.choices(
                    ['Habitat', 'Integra', 'Prima', 'Profuturo'],
                    weights=[25, 30, 25, 20],
                )[0]
            else:
                regimen_pension = 'ONP'
                afp = ''

            asignacion = random.random() < 0.60

            # Empresa según pesos
            empresa = random.choice(empresa_buckets)

            # Fecha ingreso 2024-01-01 a 2025-06-01
            inicio = date(2024, 1, 1)
            fin = date(2025, 6, 1)
            delta_dias = (fin - inicio).days
            fecha_alta = inicio + timedelta(days=random.randint(0, delta_dias))

            # Categoría
            categoria = 'CONFIANZA' if es_confianza else 'NORMAL'

            # Régimen de turno (visual — el campo regimen_turno es texto libre)
            if codigo_area in ('SAL', 'BAR', 'CAJ'):
                # mozos/bartender/cajero rotan
                regimen_turno = random.choice(['GASTRO_M', 'GASTRO_TN', 'GASTRO_C'])
            elif codigo_area == 'COC':
                regimen_turno = random.choice(['GASTRO_M', 'GASTRO_TN'])
            elif codigo_area == 'LIM':
                regimen_turno = 'GASTRO_M'
            else:
                regimen_turno = '5x2'

            # Día de descanso semanal (rotativo en gastronomía).
            # Admin (5x2) descansa sábado+domingo → guardamos domingo por
            # convención (sábado se gestiona como FA salvo edición manual).
            # Operativo gastronomía rota cualquier día de la semana.
            if codigo_area == 'ADM':
                dia_descanso_semanal = ''  # default domingo
            else:
                dia_descanso_semanal = random.choice(['0', '1', '2', '3', '4', '5', '6'])

            defaults = {
                'apellidos_nombres': apellidos_nombres,
                'tipo_doc': 'DNI',
                'cargo': nombre_cargo,
                'cargo_obj': cargo_obj,
                'tipo_trab': 'Obrero' if codigo_area in ('COC', 'LIM') else 'Empleado',
                'subarea': subarea,
                'empresa': empresa,
                'estado': 'Activo',
                'sexo': sexo,
                'sueldo_base': sueldo,
                'regimen_pension': regimen_pension,
                'afp': afp,
                'asignacion_familiar': asignacion,
                'categoria': categoria,
                'fecha_alta': fecha_alta,
                'fecha_inicio_contrato': fecha_alta,
                'grupo_tareo': 'STAFF' if codigo_area == 'ADM' else 'RCO',
                'condicion': 'LOCAL',
                'regimen_turno': regimen_turno,
                'dia_descanso_semanal': dia_descanso_semanal,
                'regimen_laboral': 'D.Leg. 728 — Régimen General',
                'tipo_contrato': 'PLAZO_FIJO' if (date.today() - fecha_alta).days < 365 else 'INDEFINIDO',
                'jornada_horas': Decimal('8.0'),
            }

            obj, created = Personal.objects.get_or_create(
                nro_doc=dni,
                defaults=defaults,
            )
            if created:
                creados += 1
            else:
                existentes += 1

        self.resumen['trabajadores_creados'] = creados
        self.resumen['trabajadores_existentes'] = existentes
        self.stdout.write(f'  [+] Trabajadores: {creados} creados, {existentes} ya existían')

    # ─────────────────────────────────────────────────────────────────────
    # 5. Regímenes de turno
    # ─────────────────────────────────────────────────────────────────────

    def _crear_regimenes_turno(self):
        try:
            from asistencia.models import RegimenTurno, TipoHorario
        except ImportError:
            self.resumen['todos'].append('RegimenTurno/TipoHorario no encontrados — saltado.')
            return

        from datetime import time

        creados = 0
        horarios_creados = 0
        for r in REGIMENES_GASTRO:
            regimen, created = RegimenTurno.objects.get_or_create(
                codigo=r['codigo'],
                defaults={
                    'nombre': r['nombre'],
                    'jornada_tipo': r['jornada_tipo'],
                    'dias_trabajo_ciclo': r['dias_trabajo_ciclo'],
                    'dias_descanso_ciclo': r['dias_descanso_ciclo'],
                    'minutos_almuerzo': 60,
                    'es_nocturno': r['es_nocturno'],
                    'recargo_nocturno_pct': Decimal('35.00'),
                    'descripcion': r['descripcion'],
                    'activo': True,
                },
            )
            if created:
                creados += 1

            # Horario L-S (todos los días del ciclo en realidad — gastronomía trabaja 6x1)
            h_ent = time(*[int(x) for x in r['hora_entrada'].split(':')])
            h_sal_str = r['hora_salida']
            # '00:00' → time(0,0)
            h_sal = time(*[int(x) for x in h_sal_str.split(':')]) if h_sal_str != '24:00' else time(0, 0)

            _, h_created = TipoHorario.objects.get_or_create(
                regimen=regimen,
                tipo_dia='TODOS',
                defaults={
                    'nombre': f'{r["nombre"]} (L-S)',
                    'hora_entrada': h_ent,
                    'hora_salida': h_sal,
                    'salida_dia_siguiente': r['salida_dia_siguiente'],
                    'activo': True,
                },
            )
            if h_created:
                horarios_creados += 1

        self.resumen['regimenes_turno'] = creados
        self.resumen['horarios_turno'] = horarios_creados
        self.stdout.write(
            f'  [+] Regímenes turno: {creados} creados, '
            f'{horarios_creados} horarios creados'
        )

    # ─────────────────────────────────────────────────────────────────────
    # 6. Conceptos remunerativos (Propinas, Recargo por consumo)
    # ─────────────────────────────────────────────────────────────────────

    def _crear_conceptos_gastro(self):
        try:
            from nominas.models import ConceptoRemunerativo
        except ImportError:
            self.resumen['todos'].append('ConceptoRemunerativo no encontrado — saltado.')
            return

        creados = 0
        for c in CONCEPTOS_GASTRO:
            _, created = ConceptoRemunerativo.objects.get_or_create(
                codigo=c['codigo'],
                defaults={
                    'nombre': c['nombre'],
                    'tipo': c['tipo'],
                    'subtipo': c['subtipo'],
                    'formula': c['formula'],
                    'afecto_essalud': c['afecto_essalud'],
                    'afecto_renta': c['afecto_renta'],
                    'afecto_cts': c['afecto_cts'],
                    'afecto_gratif': c['afecto_gratif'],
                    'orden': c['orden'],
                    'es_sistema': True,
                    'activo': True,
                },
            )
            if created:
                creados += 1

        self.resumen['conceptos_creados'] = creados
        self.stdout.write(f'  [+] Conceptos gastronomía: {creados} creados')

    # ─────────────────────────────────────────────────────────────────────
    # 7. Aplicar propinas a ~20 mozos en la última planilla
    # ─────────────────────────────────────────────────────────────────────

    def _aplicar_propinas_ultima_planilla(self):
        try:
            from nominas.models import (
                PeriodoNomina, RegistroNomina, LineaNomina, ConceptoRemunerativo
            )
        except ImportError:
            self.resumen['todos'].append('Modelos de nómina no encontrados — propinas saltadas.')
            return
        from personal.models import Personal

        try:
            concepto = ConceptoRemunerativo.objects.get(codigo='propinas')
        except ConceptoRemunerativo.DoesNotExist:
            self.resumen['todos'].append('Concepto "propinas" no encontrado — propinas saltadas.')
            return

        # Última planilla regular (envuelto: si la BD no tiene la migración más
        # reciente, no crashea el seed completo)
        try:
            periodo = (
                PeriodoNomina.objects
                .filter(tipo='REGULAR')
                .order_by('-anio', '-mes')
                .first()
            )
        except Exception as exc:
            self.resumen['todos'].append(
                f'Error consultando PeriodoNomina ({exc.__class__.__name__}) — '
                'propinas saltadas. Verificar migraciones de nominas.'
            )
            self.stdout.write(self.style.WARNING(
                f'  [!] PeriodoNomina inaccesible ({exc.__class__.__name__}) — propinas saltadas'
            ))
            return
        if periodo is None:
            self.resumen['todos'].append(
                'No hay PeriodoNomina REGULAR previa — propinas saltadas. '
                'Correr `seed_demo_nominas` antes para generar planillas.'
            )
            self.stdout.write('  [!] No hay planilla regular previa — propinas no aplicadas')
            return

        # Mozos disponibles (cargo contiene "Mozo")
        mozos = list(
            Personal.objects
            .filter(cargo__icontains='Mozo', estado='Activo')
            .order_by('nro_doc')
        )
        if not mozos:
            self.stdout.write('  [!] Sin mozos para aplicar propinas')
            return

        random.shuffle(mozos)
        mozos = mozos[:20]

        aplicadas = 0
        for mozo in mozos:
            registro = RegistroNomina.objects.filter(periodo=periodo, personal=mozo).first()
            if registro is None:
                continue
            # Evitar duplicar la línea de propinas
            if LineaNomina.objects.filter(registro=registro, concepto=concepto).exists():
                continue
            monto = Decimal(random.randint(200, 800))
            LineaNomina.objects.create(
                registro=registro,
                concepto=concepto,
                base_calculo=Decimal('0'),
                porcentaje_aplicado=Decimal('0'),
                monto=monto,
                observacion='Propinas de servicio — distribución mensual',
            )
            aplicadas += 1

        self.resumen['propinas_aplicadas'] = aplicadas
        if aplicadas:
            self.stdout.write(
                f'  [+] Propinas aplicadas: {aplicadas} líneas en planilla '
                f'{periodo.mes:02d}/{periodo.anio}'
            )
        else:
            self.stdout.write(
                f'  [!] Mozos sin RegistroNomina en {periodo.mes:02d}/{periodo.anio} '
                '— propinas no aplicadas'
            )

    # ─────────────────────────────────────────────────────────────────────
    # Reporte final
    # ─────────────────────────────────────────────────────────────────────

    def _reporte_final(self):
        r = self.resumen
        self.stdout.write(self.style.SUCCESS('\n-------- Resumen seed_demo_gastronomia --------'))
        self.stdout.write(
            f'  Empresas:        {r["empresas_creadas"]} creadas, {r["empresas_actualizadas"]} actualizadas'
        )
        self.stdout.write(
            f'  Áreas/SubÁreas:  {r["areas_creadas"]} áreas, {r["subareas_creadas"]} subáreas'
        )
        self.stdout.write(f'  Cargos:          {r["cargos_creados"]} cargos')
        self.stdout.write(
            f'  Trabajadores:    {r["trabajadores_creados"]} nuevos '
            f'({r["trabajadores_existentes"]} ya existían)'
        )
        self.stdout.write(
            f'  Turnos:          {r["regimenes_turno"]} regímenes, {r["horarios_turno"]} horarios'
        )
        self.stdout.write(f'  Conceptos:       {r["conceptos_creados"]} (Propinas, Recargo consumo)')
        self.stdout.write(f'  Propinas:        {r["propinas_aplicadas"]} líneas aplicadas a mozos')
        if r['todos']:
            self.stdout.write(self.style.WARNING('\n  TODOs / saltados:'))
            for t in r['todos']:
                self.stdout.write(f'    - {t}')
        self.stdout.write('')


class _DryRunRollback(Exception):
    """Excepción interna para rollback de transacción en --dry-run."""
    pass
