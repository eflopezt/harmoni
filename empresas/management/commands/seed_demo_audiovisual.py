"""
Seed Demo Pixel Motion SAC — agencia diseño y audiovisual (25 trabajadores).

Caso de uso: empresa pequeña (Plan Starter S/149/mes hasta 30 colaboradores).
Contexto: agencia creativa de diseño gráfico + post-producción + motion graphics.

Crea:
- Empresa Pixel Motion SAC (RUC ficticio)
- 4 áreas: Creativo, Audiovisual, Cuentas, Administración
- 25 trabajadores con cargos realistas y sueldos del mercado peruano
- Usuario demo2/demo con acceso a esta empresa
- Asistencia de últimos 30 días
- 2 capacitaciones recientes
- 3 vacaciones aprobadas

Uso:
    python manage.py seed_demo_audiovisual
    python manage.py seed_demo_audiovisual --reset
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


# ── Definición del staff Pixel Motion ──
# Cargo, area_codigo, sueldo_base PEN, sexo (M/F)
ROSTER = [
    # Liderazgo
    ('Carlos Mendoza Vargas',        'CEO / Director General',          'CRE', 12000, 'M'),
    ('Andrea Castillo Reyes',        'Directora de Cuentas',            'CTA',  8500, 'F'),

    # Dirección Creativa
    ('Mauricio Salinas Torres',      'Director Creativo',               'CRE',  7000, 'M'),
    ('Valentina Rojas Pinto',        'Directora de Arte',               'CRE',  6500, 'F'),

    # Diseño
    ('Diego Quispe Bautista',        'Diseñador Senior',                'CRE',  4500, 'M'),
    ('Sofia Pérez Anchante',         'Diseñadora Senior',               'CRE',  4500, 'F'),
    ('Ana Lucía Vega Cordero',       'Diseñadora Senior',               'CRE',  4200, 'F'),
    ('Bruno Cárdenas Aliaga',        'Diseñador Junior',                'CRE',  2200, 'M'),
    ('Karla Espinoza Mamani',        'Diseñadora Junior',               'CRE',  2200, 'F'),
    ('Sebastián Ramos Llanos',       'Diseñador Junior',                'CRE',  2000, 'M'),
    ('Camila Torres Velasquez',      'Diseñadora Junior',               'CRE',  2000, 'F'),

    # Audiovisual
    ('Renzo Vela Chumpitaz',         'Motion Designer',                 'AUD',  3800, 'M'),
    ('Daniela Alva Sandoval',        'Motion Designer',                 'AUD',  3500, 'F'),
    ('José Luis Quiroz Tinoco',      'Editor de Video Senior',          'AUD',  3500, 'M'),
    ('Luis Fernando Pineda Rey',     'Editor de Video',                 'AUD',  2800, 'M'),
    ('Patricia Soto Calderón',       'Editora de Video',                'AUD',  2800, 'F'),
    ('Marcelo Atauje Lazo',          'Animador 3D',                     'AUD',  3600, 'M'),
    ('Fernanda Loyola Bravo',        'Animadora 3D',                    'AUD',  3400, 'F'),
    ('Iván Cabrera Mendoza',         'Camarógrafo / DOP',               'AUD',  3000, 'M'),
    ('Romina Ferrer Pacheco',        'Productora Audiovisual',          'AUD',  3800, 'F'),

    # Cuentas / Comercial
    ('Mateo Aguilar Salas',          'Account Manager',                 'CTA',  3500, 'M'),
    ('Lucía Benavente Olano',        'Account Executive',               'CTA',  2500, 'F'),
    ('Ariana Salazar Vergara',       'Community Manager',               'CTA',  2200, 'F'),

    # Administración
    ('Rocío Huamán Choque',          'Administradora',                  'ADM',  3500, 'F'),

    # Practicantes
    ('Joaquín Maldonado Calle',      'Practicante de Diseño',           'CRE',  1100, 'M'),
]


class Command(BaseCommand):
    help = 'Crea demo Pixel Motion SAC (25 trabajadores diseño/audiovisual).'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
            help='Borrar trabajadores y empresa antes de re-crear (CUIDADO)')

    def handle(self, *args, **options):
        from empresas.models import Empresa
        from personal.models import Area, SubArea, Personal

        random.seed(42)

        if options['reset']:
            self.stdout.write(self.style.WARNING(
                '⚠ Resetting Pixel Motion data...'
            ))
            Empresa.objects.filter(ruc='20612345678').delete()

        # ── 1. Empresa ──
        empresa, created = Empresa.objects.get_or_create(
            ruc='20612345678',
            defaults={
                'razon_social':        'PIXEL MOTION DESIGN S.A.C.',
                'nombre_comercial':    'Pixel Motion',
                'direccion':           'Av. Arequipa 4500 piso 8 — Miraflores',
                'distrito':            'Miraflores',
                'provincia':           'Lima',
                'departamento':        'Lima',
                'ubigeo':              '150122',
                'telefono':            '+51 1 700 8500',
                'email_rrhh':          'rrhh@pixelmotion.pe',
                'web':                 'https://pixelmotion.pe',
                'regimen_laboral':     'PEQUENA' if Empresa.REGIMEN_CHOICES and any(c[0] == 'PEQUENA' for c in Empresa.REGIMEN_CHOICES) else 'GENERAL',
                'sector':              'PRIVADO',
                'actividad_economica': '74100 — Actividades de diseño especializado',
                'activa':              True,
                'subdominio':          'pixel-motion',
            },
        )
        self.stdout.write(
            self.style.SUCCESS(f"{'✓ Creada' if created else '~ Existente'}: {empresa.razon_social}")
        )

        # ── 2. Áreas ──
        areas_data = [
            ('CRE', 'Creativo / Diseño'),
            ('AUD', 'Audiovisual'),
            ('CTA', 'Cuentas / Comercial'),
            ('ADM', 'Administración'),
        ]
        areas = {}
        for codigo, nombre in areas_data:
            area, _ = Area.objects.get_or_create(
                nombre=nombre,
                defaults={'activa': True},
            )
            areas[codigo] = area
            # SubArea por defecto
            SubArea.objects.get_or_create(
                area=area, nombre=nombre,
                defaults={'activa': True},
            )

        # ── 3. Trabajadores ──
        creados = 0
        today = date.today()
        for idx, (nombre, cargo, area_cod, sueldo, sexo) in enumerate(ROSTER, start=1):
            dni = f'4{idx:07d}'  # DNI ficticio 8 dígitos
            area = areas[area_cod]
            subarea = SubArea.objects.filter(area=area).first()

            # Fecha alta aleatoria: entre 6m y 5 años atrás
            dias_antiguedad = random.randint(180, 5 * 365)
            fecha_alta = today - timedelta(days=dias_antiguedad)

            # Email derivado del nombre
            partes = nombre.lower().split()
            email = f'{partes[0]}.{partes[1]}@pixelmotion.pe' if len(partes) >= 2 else f'{partes[0]}@pixelmotion.pe'
            email = email.replace('í', 'i').replace('é', 'e').replace('á', 'a').replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')

            personal, created = Personal.objects.get_or_create(
                nro_doc=dni,
                defaults={
                    'apellidos_nombres':  nombre.upper(),
                    'cargo':              cargo,
                    'subarea':            subarea,
                    'empresa':            empresa,
                    'fecha_alta':         fecha_alta,
                    'estado':             'Activo',
                    'sueldo_base':        Decimal(str(sueldo)),
                    'sexo':               sexo,
                    'grupo_tareo':        'STAFF',
                    'correo_corporativo': email,
                },
            )
            if created:
                creados += 1

        self.stdout.write(self.style.SUCCESS(
            f'✓ Trabajadores: {creados} creados, {len(ROSTER) - creados} existentes'
        ))

        # ── 4. Usuario demo2 ──
        u, created = User.objects.get_or_create(
            username='demo2',
            defaults={
                'email':       'demo2@harmoni.pe',
                'first_name':  'Carlos',
                'last_name':   'Mendoza (Pixel Motion)',
                'is_staff':    True,
                'is_superuser': True,  # Para acceso completo en demo
            },
        )
        if created or not u.check_password('demo'):
            u.set_password('demo')
            u.save()
        self.stdout.write(self.style.SUCCESS(
            f"{'✓ Creado' if created else '~ Actualizado'}: usuario demo2/demo"
        ))

        # ── 5. Asistencia últimos 30 días (papeletas + tardanzas) ──
        try:
            from asistencia.models import RegistroPapeleta
            personal_qs = Personal.objects.filter(empresa=empresa, estado='Activo')
            papeletas_creadas = 0
            for p in random.sample(list(personal_qs), 8):
                fecha_inicio = today - timedelta(days=random.randint(1, 25))
                fecha_fin = fecha_inicio + timedelta(days=random.choice([0, 0, 1]))
                tipo_permiso = random.choice([
                    'PERMISO_MEDICO', 'PERMISO_PERSONAL', 'LIC_FALLECIMIENTO',
                ])
                try:
                    RegistroPapeleta.objects.get_or_create(
                        personal=p,
                        fecha_inicio=fecha_inicio,
                        tipo_permiso=tipo_permiso,
                        defaults={
                            'fecha_fin':     fecha_fin,
                            'dni':           p.nro_doc,
                            'estado':        'APROBADA',
                            'observaciones': f'[Demo Pixel Motion] {tipo_permiso}',
                            'dias':          (fecha_fin - fecha_inicio).days + 1,
                        },
                    )
                    papeletas_creadas += 1
                except Exception:
                    pass
            self.stdout.write(
                f'  · {papeletas_creadas} papeletas demo creadas',
            )
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ~ Asistencia skip: {str(e)[:60]}'))

        # ── 6. Capacitaciones ──
        try:
            from capacitaciones.models import Capacitacion
            cap_data = [
                ('Adobe Creative Suite 2026 — Novedades',
                 'Workshop interno sobre las nuevas funciones de Adobe Suite.',
                 today + timedelta(days=10)),
                ('Storytelling para Brand Videos',
                 'Capacitación con instructor externo sobre narrativa para piezas comerciales.',
                 today - timedelta(days=20)),
            ]
            for titulo, desc, fecha in cap_data:
                Capacitacion.objects.get_or_create(
                    titulo=titulo,
                    defaults={
                        'descripcion': desc,
                        'fecha_inicio': fecha,
                        'estado': 'COMPLETADA' if fecha < today else 'PROGRAMADA',
                    },
                )
            self.stdout.write('  · 2 capacitaciones demo')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ~ Capacitaciones skip: {str(e)[:60]}'))

        # ── 7. Vacaciones aprobadas ──
        try:
            from vacaciones.models import SolicitudVacacion
            personal_qs = Personal.objects.filter(empresa=empresa, estado='Activo')[:3]
            for p in personal_qs:
                fi = today + timedelta(days=random.randint(20, 60))
                ff = fi + timedelta(days=random.choice([7, 14, 15]))
                try:
                    SolicitudVacacion.objects.get_or_create(
                        personal=p,
                        fecha_inicio=fi,
                        defaults={
                            'fecha_fin':         ff,
                            'dias_solicitados':  (ff - fi).days + 1,
                            'estado':            'APROBADA',
                        },
                    )
                except Exception:
                    pass
            self.stdout.write('  · 3 solicitudes vacaciones')
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ~ Vacaciones skip: {str(e)[:60]}'))

        # ── Resumen ──
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('═══════════════════════════════════════════'))
        self.stdout.write(self.style.SUCCESS('  ✓ Demo Pixel Motion SAC listo'))
        self.stdout.write(self.style.SUCCESS('═══════════════════════════════════════════'))
        self.stdout.write('')
        self.stdout.write(f'  Empresa:       {empresa.razon_social}')
        self.stdout.write(f'  RUC:           {empresa.ruc}')
        self.stdout.write(f'  Trabajadores:  {Personal.objects.filter(empresa=empresa).count()}')
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('  Acceso:'))
        self.stdout.write('  URL:           https://demo.harmoni.pe/')
        self.stdout.write('  Usuario:       demo2')
        self.stdout.write('  Password:      demo')
        self.stdout.write('')
