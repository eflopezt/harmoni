"""
Organiza los datos de la demo en 3 escenarios COHERENTES por rubro:

  1. GRUPO GASTRONÓMICO — multiempresa, un solo rubro (GASTRONOMIA):
     el grupo "Sabores del Sur" (varias razones sociales) → vista consolidada.
  2. MINERA — empresa ÚNICA (MINERIA), régimen 14x7, cuadrilla foránea.
  3. CONSTRUCTORA — empresa ÚNICA (CONSTRUCCION), operario/oficial/peón.

Además:
  - Retag del grupo Sabores (estaba GENERAL) → GASTRONOMIA + fija la principal.
  - Puebla minería y construcción con una cuadrilla realista (antes ralas).
  - Desactiva empresas placeholder vacías y duplicados (limpieza).

Idempotente. Uso:
    python manage.py seed_demo_escenarios
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


# RUCs canónicos de cada escenario
GASTRO_GRUPO = [
    '20100100100',  # Sabores del Sur SAC (matriz del grupo)
    '20100000666',  # Central
    '20100000555',  # Express
    '20100000444',  # Café
    '20100000333',  # Asado
    '20100000222',  # Marino
    '20100000111',  # Premium
]
GASTRO_PRINCIPAL = '20100100100'
MINERA_RUC = '20600000029'
CONSTRUCTORA_RUC = '20600000011'
AGENCIA_RUC = '20612345678'   # Pixel Motion (agencia real, 25 trab)

# Empresas placeholder/duplicadas a desactivar (0 trabajadores, ruido en demo)
CLUTTER_RUCS = [
    '20600000037',  # RESTAURANTE GENÉRICO (placeholder gastronomía)
    '20600000053',  # EMPRESA GENÉRICA
    '20600000045',  # AGENCIA CREATIVA GENÉRICA (placeholder audiovisual vacío)
    '20100100300',  # Sabores del Sur Express SAC (duplicado)
    '20100100200',  # Sabores del Sur Marino SAC (duplicado)
]

# Cuadrilla minera (14x7, foránea). DNIs 91xxxxxx (rango propio).
TRAB_MINERIA = [
    ('CONDORI APAZA, MARIO',          'Operador de Scoop',      '3800'),
    ('CHOQUE VILCA, JOSÉ LUIS',       'Perforista',             '3500'),
    ('QUISPE MAMANI, RAÚL',           'Ayudante de Perforista', '2900'),
    ('HUANCA TICONA, PEDRO',          'Operador de Jumbo',      '4200'),
    ('MAMANI CALLE, ROBERTO',         'Bombero de Mina',        '2700'),
    ('APAZA CRUZ, WILBER',            'Winchero',               '3100'),
    ('CCAPA HANCCO, ELÍAS',           'Capataz de Guardia',     '5200'),
    ('SUCASACA LIPA, FÉLIX',          'Mecánico de Mina',       '3600'),
    ('YUCRA COAQUIRA, DAVID',         'Electricista de Mina',   '3700'),
    ('CUTIPA CHURA, ABEL',           'Supervisor de Seguridad', '6000'),
]

# Cuadrilla construcción (jornal diario por categoría). DNIs 92xxxxxx.
TRAB_CONSTRUCCION = [
    ('PÉREZ QUISPE, JUAN CARLOS',     'Operario Albañil',   '89.30', 'OPERARIO'),
    ('ROJAS DÍAZ, MIGUEL',            'Operario Fierrero',  '89.30', 'OPERARIO'),
    ('MAMANI FLORES, LUIS ALBERTO',   'Oficial',            '69.75', 'OFICIAL'),
    ('HUAMÁN ROJAS, PEDRO',           'Peón',               '62.80', 'PEON'),
    ('VÁSQUEZ TORRES, SANTIAGO',      'Operario Encofrador','89.30', 'OPERARIO'),
    ('QUISPE HANCCO, JULIO',          'Oficial',            '69.75', 'OFICIAL'),
    ('FLORES MAMANI, RICARDO',        'Peón',               '62.80', 'PEON'),
    ('CONDORI VILCA, MARCOS',         'Peón',               '62.80', 'PEON'),
    ('TORRES CRUZ, ANDRÉS',           'Operario Gasfitero', '89.30', 'OPERARIO'),
    ('CCASA APAZA, WALTER',           'Maestro de Obra',    '95.00', 'OPERARIO'),
]


class Command(BaseCommand):
    help = 'Organiza la demo en 3 escenarios por rubro (gastronomía grupo, minera, constructora).'

    @transaction.atomic
    def handle(self, *args, **opts):
        from empresas.models import Empresa

        # ── 1. Grupo gastronómico: retag → GASTRONOMIA + principal ──
        grupo = Empresa.objects.filter(ruc__in=GASTRO_GRUPO)
        n_gastro = grupo.update(rubro='GASTRONOMIA', activa=True)
        Empresa.objects.filter(ruc=GASTRO_PRINCIPAL).update(es_principal=True)
        Empresa.objects.exclude(ruc=GASTRO_PRINCIPAL).filter(es_principal=True)\
            .update(es_principal=False)
        self.stdout.write(f'[GASTRONOMIA] grupo Sabores: {n_gastro} empresas re-etiquetadas, '
                          f'principal={GASTRO_PRINCIPAL}')

        # ── 2. Minera (única): cuadrilla 14x7 ──
        minera = Empresa.objects.filter(ruc=MINERA_RUC).first()
        if minera:
            minera.rubro = 'MINERIA'
            minera.es_principal = False
            minera.activa = True
            minera.save(update_fields=['rubro', 'es_principal', 'activa'])
            n = self._poblar(minera, TRAB_MINERIA, base_dni=91000000, minera=True)
            self.stdout.write(f'[MINERIA] {minera.razon_social}: +{n} trabajadores (14x7)')
        else:
            self.stdout.write(self.style.WARNING(f'[MINERIA] empresa {MINERA_RUC} no existe'))

        # ── 3. Constructora (única): operario/oficial/peón ──
        constru = Empresa.objects.filter(ruc=CONSTRUCTORA_RUC).first()
        if constru:
            constru.rubro = 'CONSTRUCCION'
            constru.es_principal = False
            constru.activa = True
            constru.save(update_fields=['rubro', 'es_principal', 'activa'])
            n = self._poblar(constru, TRAB_CONSTRUCCION, base_dni=92000000, construccion=True)
            self.stdout.write(f'[CONSTRUCCION] {constru.razon_social}: +{n} trabajadores')
        else:
            self.stdout.write(self.style.WARNING(f'[CONSTRUCCION] empresa {CONSTRUCTORA_RUC} no existe'))

        # ── 3b. Agencia (única): Pixel Motion → AUDIOVISUAL ──
        agencia = Empresa.objects.filter(ruc=AGENCIA_RUC).first()
        if agencia:
            agencia.rubro = 'AUDIOVISUAL'
            agencia.es_principal = False
            agencia.activa = True
            agencia.save(update_fields=['rubro', 'es_principal', 'activa'])
            self.stdout.write(f'[AUDIOVISUAL] {agencia.razon_social}: rubro alineado')

        # ── 4. Limpieza: desactivar placeholders/duplicados vacíos ──
        from personal.models import Personal
        desactivadas = 0
        for ruc in CLUTTER_RUCS:
            emp = Empresa.objects.filter(ruc=ruc).first()
            if emp and not Personal.objects.filter(empresa=emp, estado='Activo').exists():
                emp.activa = False
                emp.save(update_fields=['activa'])
                desactivadas += 1
        self.stdout.write(f'[LIMPIEZA] {desactivadas} empresas vacías/duplicadas desactivadas')

        self.stdout.write(self.style.SUCCESS('\nEscenarios demo organizados: '
                                             'Grupo Gastronómico · Minera · Constructora'))

    def _poblar(self, empresa, trabajadores, base_dni, minera=False, construccion=False):
        from personal.models import Personal, Area, SubArea

        # Area/SubArea propias del escenario (Area.nombre es único global).
        area_nombre = 'Operaciones Mina' if minera else 'Operaciones Obra'
        sub_nombre = 'Cuadrilla Mina' if minera else 'Cuadrilla Obra'
        area, _ = Area.objects.get_or_create(nombre=area_nombre)
        subarea, _ = SubArea.objects.get_or_create(nombre=sub_nombre, area=area)

        creados = 0
        for wi, fila in enumerate(trabajadores):
            dni = f'{base_dni + wi + 1:08d}'
            if minera:
                nombre, cargo, sueldo = fila
                extra = dict(regimen_laboral='MINERIA', regimen_turno='14x7',
                             condicion='FORANEO', afecto_sctr=True)
                tipo, base = 'Obrero', Decimal(sueldo)
            else:  # construcción
                nombre, cargo, sueldo, cat = fila
                extra = dict(regimen_laboral='CONSTRUCCION',
                             categoria_construccion=cat, condicion='FORANEO',
                             afecto_sctr=True)
                tipo, base = 'Obrero', Decimal(sueldo)

            defaults = dict(
                apellidos_nombres=nombre, cargo=cargo, tipo_trab=tipo,
                subarea=subarea, empresa=empresa, estado='Activo',
                fecha_alta=date(2025, 1, 1), sueldo_base=base,
                grupo_tareo='RCO', **extra,
            )
            _, created = Personal.objects.get_or_create(nro_doc=dni, defaults=defaults)
            if created:
                creados += 1
        return creados
