"""
Management command: seed_conceptos
Carga los conceptos remunerativos estándar de planilla Perú.

Uso:
    python manage.py seed_conceptos
    python manage.py seed_conceptos --reset
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from nominas.models import ConceptoRemunerativo


# (codigo, nombre, tipo, subtipo, formula, %, afecto_ess, afecto_renta, afecto_cts, afecto_gratif, orden)
CONCEPTOS = [
    # ── INGRESOS REMUNERATIVOS ──────────────────────────────────────
    ('sueldo-basico',       'Sueldo Básico',                'INGRESO', 'REMUNERATIVO',    'DIAS_TRABAJADOS', 0,    True, True, True, True,  1),
    ('asig-familiar',       'Asignación Familiar',          'INGRESO', 'REMUNERATIVO',    'FIJO',            0,    True, True, True, True,  2),
    ('he-25',               'Horas Extra 25%',              'INGRESO', 'REMUNERATIVO',    'HE_25',           25,   True, True, False,False, 3),
    ('he-35',               'Horas Extra 35%',              'INGRESO', 'REMUNERATIVO',    'HE_35',           35,   True, True, False,False, 4),
    ('he-100',              'Horas Extra 100% (Feriados)',  'INGRESO', 'REMUNERATIVO',    'HE_100',          100,  True, True, False,False, 5),
    ('bono-productividad',  'Bono de Productividad',        'INGRESO', 'REMUNERATIVO',    'MANUAL',          0,    True, True, False,False, 6),
    ('bono-puntualidad',    'Bono de Puntualidad',          'INGRESO', 'REMUNERATIVO',    'MANUAL',          0,    True, True, False,False, 7),
    ('comisiones',          'Comisiones por Ventas',        'INGRESO', 'REMUNERATIVO',    'MANUAL',          0,    True, True, True, True,  8),
    ('bono-resultados',     'Bono por Resultados',          'INGRESO', 'REMUNERATIVO',    'MANUAL',          0,    True, True, False,False, 9),

    # ── INGRESOS NO REMUNERATIVOS ──────────────────────────────────
    ('movilidad',           'Movilidad',                    'INGRESO', 'NO_REMUNERATIVO', 'FIJO',            0,    False,False,False,False, 10),
    ('refrigerio',          'Refrigerio',                   'INGRESO', 'NO_REMUNERATIVO', 'FIJO',            0,    False,False,False,False, 11),
    ('viaticos-cdt',        'Viáticos / CDT',               'INGRESO', 'NO_REMUNERATIVO', 'MANUAL',          0,    False,False,False,False, 12),
    ('otros-ingresos',      'Otros Ingresos',               'INGRESO', 'NO_REMUNERATIVO', 'MANUAL',          0,    False,False,False,False, 19),

    # ── PROVISIONES (informativas en planilla regular) ─────────────
    ('prov-gratificacion',  'Provisión Gratificación',      'INGRESO', 'PROVISION',       'GRATIFICACION',   0,    False,False,False,False, 20),
    ('prov-cts',            'Provisión CTS',                'INGRESO', 'PROVISION',       'CTS',             0,    False,False,False,False, 21),

    # ── CONCEPTOS ESPECIALES — GRATIFICACIÓN (períodos tipo GRATIFICACION) ──
    ('gratificacion',         'Gratificación Semestral',        'INGRESO', 'REMUNERATIVO',   'GRATIFICACION',   0,  False,False,False,False, 22),
    ('bonif-extraordinaria',  'Bonificación Extraordinaria 9%', 'INGRESO', 'NO_REMUNERATIVO','MANUAL',          9,  False,False,False,False, 23),

    # ── CONCEPTOS ESPECIALES — CTS (períodos tipo CTS) ──────────────────
    ('cts-semestral',         'CTS Semestral',                  'APORTE_EMPLEADOR','REMUNERATIVO','CTS',         0,  False,False,False,False, 53),

    # ── DESCUENTOS TRABAJADOR — PENSIONES ─────────────────────────
    ('afp-aporte',          'AFP — Aporte Obligatorio 10%', 'DESCUENTO','REMUNERATIVO',   'AFP_APORTE',      10,   False,False,False,False, 30),
    ('afp-comision',        'AFP — Comisión Flujo',         'DESCUENTO','REMUNERATIVO',   'AFP_COMISION',    0,    False,False,False,False, 31),
    ('afp-seguro',          'AFP — Prima de Seguro',        'DESCUENTO','REMUNERATIVO',   'AFP_SEGURO',      0,    False,False,False,False, 32),
    ('onp',                 'ONP — Sistema Nacional 13%',   'DESCUENTO','REMUNERATIVO',   'ONP',             13,   False,False,False,False, 33),

    # ── DESCUENTOS TRABAJADOR — OTROS ─────────────────────────────
    ('ir-5ta',              'IR 5ta Categoría (Retención)', 'DESCUENTO','REMUNERATIVO',   'IR_5TA',          0,    False,False,False,False, 35),
    ('descto-prestamo',     'Descuento Préstamo',           'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 36),
    ('descto-adelanto',     'Descuento Adelanto',           'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 37),
    ('descto-falta',        'Descuento por Falta',          'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 38),
    ('otros-descuentos',    'Otros Descuentos',             'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 39),
    ('embargo-judicial',    'Embargo Judicial',             'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 40),
    ('retencion-judicial',  'Retención por Mandato Judicial','DESCUENTO','REMUNERATIVO',  'MANUAL',          0,    False,False,False,False, 41),
    ('cuota-sindical',      'Cuota Sindical',               'DESCUENTO','REMUNERATIVO',   'MANUAL',          0,    False,False,False,False, 42),

    # ── APORTES EMPLEADOR ─────────────────────────────────────────
    ('essalud',             'EsSalud 9% (Empleador)',       'APORTE_EMPLEADOR','REMUNERATIVO','ESSALUD',     9,    False,False,False,False, 50),
    ('sctr-pension',        'SCTR Pensión (Empleador)',     'APORTE_EMPLEADOR','REMUNERATIVO','PORCENTAJE',  Decimal('0.73'), False,False,False,False, 51),
    ('sctr-salud',          'SCTR Salud (Empleador)',       'APORTE_EMPLEADOR','REMUNERATIVO','PORCENTAJE',  Decimal('0.80'), False,False,False,False, 52),
    ('vida-ley',            'Seguro Vida Ley (D.Leg. 688)', 'APORTE_EMPLEADOR','REMUNERATIVO','PORCENTAJE',  Decimal('0.71'), False,False,False,False, 54),
]

# Códigos PLAME (SUNAT Tabla 22) para conceptos que los necesitan al exportar.
# Vida Ley no se declara en PLAME (prima de seguro, no aporte a SUNAT).
CODIGO_PLAME = {
    'sctr-salud':   '0812',
    'sctr-pension': '0813',
}


class Command(BaseCommand):
    help = 'Carga conceptos remunerativos estándar de planilla Perú.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Elimina todos los conceptos antes de recrear.')

    def handle(self, *args, **options):
        if options['reset']:
            ConceptoRemunerativo.objects.all().delete()
            self.stdout.write(self.style.WARNING('Conceptos eliminados.'))

        creados = 0
        existentes = 0

        for (codigo, nombre, tipo, subtipo, formula, pct,
             ess, renta, cts, gratif, orden) in CONCEPTOS:
            _, created = ConceptoRemunerativo.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre':          nombre,
                    'tipo':            tipo,
                    'subtipo':         subtipo,
                    'formula':         formula,
                    'porcentaje':      pct,
                    'afecto_essalud':  ess,
                    'afecto_renta':    renta,
                    'afecto_cts':      cts,
                    'afecto_gratif':   gratif,
                    'orden':           orden,
                    'es_sistema':      True,
                    'activo':          True,
                },
            )
            if created:
                creados += 1
            else:
                existentes += 1

        # Asegurar códigos PLAME en los conceptos que los requieren (idempotente,
        # también corrige instalaciones previas donde quedaron en blanco).
        for codigo, cod_plame in CODIGO_PLAME.items():
            ConceptoRemunerativo.objects.filter(
                codigo=codigo,
            ).exclude(codigo_plame=cod_plame).update(codigo_plame=cod_plame)

        self.stdout.write(self.style.SUCCESS(
            f'Seed conceptos: {creados} creados, {existentes} ya existían. '
            f'Total: {ConceptoRemunerativo.objects.count()} conceptos.'
        ))
