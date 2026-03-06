"""
seed_demo_data.py — Carga datos demo completos para Harmoni ERP

Importa empleados REALES desde Excel de contratos + genera data realista
para todos los módulos: asistencia, vacaciones, capacitaciones, salarios,
reclutamiento, disciplinaria, evaluaciones, encuestas, préstamos, onboarding.

Uso:
    python manage.py seed_demo_data
    python manage.py seed_demo_data --solo-personal
    python manage.py seed_demo_data --solo-modulos
"""

import random
import traceback
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()

# ── Colores consola ─────────────────────────────────────────────────────────
G = '\033[92m'; Y = '\033[93m'; R = '\033[91m'; B = '\033[94m'; E = '\033[0m'
def ok(m):  print(f"  [OK] {m}")
def warn(m): print(f"  [!!] {m}")
def err(m):  print(f"  [XX] {m}")
def hdr(m):  print(f"\n{'='*60}\n  {m}\n{'='*60}")
def step(m): print(f"\n  -> {m}")

# ── Ruta Excel ───────────────────────────────────────────────────────────────
# 1° Busca en core/fixtures/ (incluido en el repo → funciona en Render)
# 2° Fallback a ruta local Windows (desarrollo)
_CMD_DIR   = Path(__file__).resolve().parent          # commands/
_CORE_DIR  = _CMD_DIR.parent.parent                   # core/
EXCEL_PATH_PROJECT = _CORE_DIR / 'fixtures' / 'matriz_contratos.xlsx'
EXCEL_PATH_LOCAL   = (
    r'C:\Users\EDWIN LOPEZ\RIPCON\Proyectos Perú - Recursos humanos'
    r'\02 Administración de Personal\Control de Contratos'
    r'\MATRIZ CONTRATOS FINAL CSRT.xlsx'
)
EXCEL_PATH = str(EXCEL_PATH_PROJECT)   # alias por compatibilidad
EMPRESA_ID = 4   # Andes Mining

# ── AFP disponibles en Perú ─────────────────────────────────────────────────
AFP_LIST = ['PRIMA', 'INTEGRA', 'PROFUTURO', 'HABITAT']

# ── Cargos considerados RCO (operativos de obra) ───────────────────────────
CARGOS_RCO = {
    'OPERARIO', 'OFICIAL', 'PEON', 'AYUDANTE', 'OPERADOR',
    'MAESTRO DE OBRA', 'CAPATAZ', 'TOPOGRAFO', 'TÉCNICO',
    'ELECTRICISTA', 'GASFITERO', 'ALBAÑIL', 'CARPINTERO',
    'SOLDADOR', 'VIGILANTE', 'AUXILIAR DE SEGURIDAD',
}

# ── Cargos foráneos típicos (régimen acumulativo) ──────────────────────────
CARGOS_FORANEOS = {
    'RESIDENTE', 'JEFE DE OBRA', 'MAESTRO DE OBRA', 'CAPATAZ',
    'SUPERVISOR', 'INGENIERO RESIDENTE', 'TOPOGRAFO',
}


def _es_rco(cargo: str) -> bool:
    cargo_up = cargo.upper()
    return any(r in cargo_up for r in CARGOS_RCO)


def _es_foraneo(cargo: str) -> bool:
    cargo_up = cargo.upper()
    return any(r in cargo_up for r in CARGOS_FORANEOS)


def _sexo_por_nombre(nombre: str) -> str:
    """Heurística simple: termina en 'A' apellido/nombre → F."""
    femeninos = {
        'JULIE', 'MARIA', 'PATRICIA', 'ROSA', 'ANA', 'CARMEN',
        'LUCIA', 'SANDRA', 'CLAUDIA', 'DIANA', 'GLORIA', 'ELENA',
        'VERONICA', 'JESSICA', 'GABRIELA', 'ANDREA', 'NATALIA',
        'ISABEL', 'TERESA', 'NANCY', 'JENNIFER', 'MILAGROS',
        'EVELYN', 'KARINA', 'MELISSA', 'YESSENIA', 'FIORELLA',
        'CYNTHIA', 'WENDY', 'BRENDA', 'VANESSA', 'LOURDES',
    }
    partes = nombre.upper().split()
    for p in partes[2:]:   # nombres (después de apellidos)
        if p in femeninos:
            return 'F'
    return 'M'


def _safe_decimal(val, default=Decimal('0.00')) -> Decimal:
    try:
        if val is None or (isinstance(val, float) and str(val) == 'nan'):
            return default
        return Decimal(str(val)).quantize(Decimal('0.01'))
    except Exception:
        return default


def _safe_date(val):
    """Convierte varios formatos a date o None."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    if hasattr(val, 'date'):
        return val.date()
    try:
        import pandas as pd
        if pd.isnull(val):
            return None
    except Exception:
        pass
    return None


class Command(BaseCommand):
    help = 'Carga datos demo completos: empleados reales + data generada para todos los módulos'

    def add_arguments(self, parser):
        parser.add_argument('--solo-personal', action='store_true',
                            help='Solo importa empleados del Excel')
        parser.add_argument('--solo-modulos', action='store_true',
                            help='Solo genera data de módulos (empleados ya cargados)')
        parser.add_argument('--no-input', action='store_true')

    def handle(self, *args, **options):
        hdr('HARMONI ERP — SEED DEMO DATA')

        solo_personal = options.get('solo_personal')
        solo_modulos  = options.get('solo_modulos')

        if not solo_modulos:
            self._importar_personal_excel()

        if not solo_personal:
            self._seed_categorias_capacitacion()
            self._seed_bandas_salariales()
            self._seed_historial_salarial()
            self._seed_saldos_vacaciones()
            self._seed_capacitaciones()
            self._seed_prestamos()
            self._seed_disciplinaria()
            self._seed_vacantes()
            self._seed_encuesta()
            self._seed_evaluaciones()

        hdr('SEED DEMO COMPLETADO - OK')

    # ═══════════════════════════════════════════════════════════════════════
    # 1 — PERSONAL DESDE EXCEL
    # ═══════════════════════════════════════════════════════════════════════
    def _importar_personal_excel(self):
        hdr('1 — Importando Personal desde Excel')
        try:
            import pandas as pd
        except ImportError:
            err('pandas no instalado. Ejecuta: pip install pandas openpyxl')
            return

        # Busca primero en core/fixtures/ (repo), luego en ruta local Windows
        xl_path = EXCEL_PATH_PROJECT
        if not xl_path.exists():
            xl_path = Path(EXCEL_PATH_LOCAL)
        if not xl_path.exists():
            warn('Excel no encontrado ni en fixtures/ ni en ruta local.')
            warn('Generando empleados demo sintéticos...')
            self._seed_personal_sintetico()
            return
        ok(f'Excel encontrado: {xl_path}')

        from personal.models import Area, SubArea, Personal

        try:
            empresa = self._get_empresa()
        except Exception as e:
            err(f'Error obteniendo empresa: {e}')
            return

        total_ok = total_skip = total_err = 0

        # ── Hoja Activos ────────────────────────────────────────────────
        step('Leyendo hoja "Matriz contrato Activos"...')
        try:
            df_activos = pd.read_excel(xl_path, sheet_name='Matriz contrato Activos')
            df_activos = df_activos.dropna(subset=['DNI O CE'])
            ok(f'{len(df_activos)} filas encontradas')
        except Exception as e:
            err(f'Error leyendo Excel: {e}')
            df_activos = pd.DataFrame()

        for _, row in df_activos.iterrows():
            try:
                r = self._procesar_fila_excel(row, empresa, estado='Activo')
                if r == 'ok':   total_ok += 1
                elif r == 'skip': total_skip += 1
            except Exception as e:
                total_err += 1
                err(f"  Error fila {row.get('DNI O CE', '?')}: {e}")

        # ── Hoja Liquidados ─────────────────────────────────────────────
        step('Leyendo hoja "Liquidados"...')
        try:
            df_liq = pd.read_excel(xl_path, sheet_name='Liquidados', header=1)
            df_liq = df_liq.dropna(subset=['DNI O CE'])
            ok(f'{len(df_liq)} filas encontradas')
        except Exception as e:
            warn(f'No se pudo leer hoja Liquidados: {e}')
            df_liq = pd.DataFrame()

        for _, row in df_liq.iterrows():
            try:
                r = self._procesar_fila_excel(row, empresa, estado='Inactivo')
                if r == 'ok':   total_ok += 1
                elif r == 'skip': total_skip += 1
            except Exception as e:
                total_err += 1

        ok(f'Personal: {total_ok} creados/actualizados, {total_skip} sin cambios, {total_err} errores')

    def _procesar_fila_excel(self, row, empresa, estado='Activo'):
        from personal.models import Area, SubArea, Personal

        nro_doc = str(row.get('DNI O CE', '')).strip().split('.')[0]
        if not nro_doc or len(nro_doc) < 6:
            return 'skip'

        apellidos_nombres = str(row.get('APELLIDOS Y NOMBRES', '')).strip()
        if not apellidos_nombres:
            return 'skip'

        cargo   = str(row.get('CARGO', 'SIN CARGO')).strip().upper()
        area_nm = str(row.get('AREA', 'ADMINISTRACION')).strip().upper()
        correo  = str(row.get('CORREO', '')).strip().lower()
        if correo in ('nan', 'none', ''):
            correo = ''

        tipo_raw = str(row.get('TIPO DE CONTRATO', 'FISCALIZABLE')).strip().upper()
        categoria = 'CONFIANZA' if 'CONFIANZA' in tipo_raw else ''

        sueldo  = _safe_decimal(row.get('BASICO'), Decimal('1025.00'))
        aliment = _safe_decimal(row.get('ALIMENTACION'), Decimal('0.00'))
        hospedj = _safe_decimal(row.get('HOSPEDAJE'), Decimal('0.00'))

        f_ingreso = _safe_date(row.get('FECHA DE INGRESO A NOMINA'))
        # Última prórroga como fecha fin de contrato
        f_fin = None
        for col in ['ULTIMA PRORROGA', 'TERMINO DE CONTRATO']:
            f_fin = _safe_date(row.get(col))
            if f_fin:
                break
        if not f_fin:
            f_fin = date.today() + timedelta(days=90)

        # Área y SubÁrea
        area_obj, _ = Area.objects.get_or_create(nombre=area_nm)
        subarea_obj, _ = SubArea.objects.get_or_create(
            nombre=area_nm, area=area_obj
        )

        grupo  = 'RCO' if _es_rco(cargo) else 'STAFF'
        cond   = 'FORANEO' if _es_foraneo(cargo) else 'LOCAL'
        sexo   = _sexo_por_nombre(apellidos_nombres)
        reg_p  = random.choice(['AFP', 'AFP', 'AFP', 'ONP'])
        afp    = random.choice(AFP_LIST) if reg_p == 'AFP' else ''
        tipo_t = 'Empleado' if grupo == 'STAFF' else 'Obrero'

        defaults = dict(
            apellidos_nombres   = apellidos_nombres,
            cargo               = cargo,
            subarea             = subarea_obj,
            empresa             = empresa,
            tipo_trab           = tipo_t,
            sexo                = sexo,
            sueldo_base         = sueldo,
            alimentacion_mensual= aliment,
            cond_trabajo_mensual= hospedj,
            grupo_tareo         = grupo,
            condicion           = cond,
            categoria           = categoria,
            tipo_contrato       = 'PLAZO_FIJO',
            regimen_pension     = reg_p,
            afp                 = afp,
            estado              = estado,
            correo_corporativo  = correo if correo else '',
        )
        if f_ingreso:
            defaults['fecha_inicio_contrato'] = f_ingreso
        if f_fin:
            defaults['fecha_fin_contrato'] = f_fin

        _, created = Personal.objects.update_or_create(
            nro_doc=nro_doc, defaults=defaults
        )
        return 'ok'

    def _seed_personal_sintetico(self):
        """Fallback: 30 empleados demo si no hay Excel."""
        from personal.models import Area, SubArea, Personal
        empresa = self._get_empresa()

        DEMO = [
            ('12345678', 'GARCIA LOPEZ CARLOS ALBERTO',   'GERENTE GENERAL',           'GERENCIA',           'STAFF', 'CONFIANZA', 15000),
            ('23456789', 'MENDOZA RIOS MARIA ELENA',      'JEFE DE RECURSOS HUMANOS',  'RRHH',               'STAFF', '',          7500),
            ('34567890', 'TORRES VEGA JUAN CARLOS',       'INGENIERO RESIDENTE',       'PRODUCCION',         'STAFF', '',          9000),
            ('45678901', 'RAMIREZ SILVA PATRICIA ANA',    'CONTADORA',                 'CONTABILIDAD',       'STAFF', '',          6000),
            ('56789012', 'FLORES HUANCA ROBERTO JESUS',   'ARQUITECTO',                'ARQUITECTURA',       'STAFF', '',          7000),
            ('67890123', 'CASTRO PINTO DIANA LUCIA',      'ASISTENTE RRHH',            'RRHH',               'STAFF', '',          3200),
            ('78901234', 'VARGAS MORENO LUIS ENRIQUE',    'RESIDENTE DE OBRA',         'PRODUCCION',         'STAFF', '',          8500),
            ('89012345', 'QUISPE MAMANI ROSA CARMEN',     'ASISTENTE CONTABLE',        'CONTABILIDAD',       'STAFF', '',          2800),
            ('90123456', 'HUAMAN CCOPA JORGE MARIO',      'OPERARIO',                  'PRODUCCION',         'RCO',   '',          2000),
            ('01234567', 'LEON PAREDES ANA MARIA',        'COORDINADORA LEGAL',        'LEGAL',              'STAFF', '',          6500),
            ('11223344', 'RIVAS GOMEZ PEDRO ANTONIO',     'SUPERVISOR DE OBRA',        'PRODUCCION',         'RCO',   '',          4500),
            ('22334455', 'SANTOS DIAZ CARMEN ROSA',       'ASISTENTE ADMINISTRATIVO',  'ADMINISTRACION',     'STAFF', '',          2400),
            ('33445566', 'MEDINA RIOS VICTOR HUGO',       'JEFE BIM',                  'BIM',                'STAFF', '',          8000),
            ('44556677', 'PAREDES LARA JESSICA PAOLA',    'ESPECIALISTA SSOMA',        'SSOMA',              'STAFF', '',          5500),
            ('55667788', 'AGUILAR VEGA MARCOS ANTONIO',   'JEFE DE COSTOS',            'COSTOS',             'STAFF', '',          7000),
            ('66778899', 'NAVARRO PAZ LOURDES ISABEL',    'ESPECIALISTA FINANZAS',     'FINANZAS',           'STAFF', '',          5000),
            ('77889900', 'ROJAS CAMPOS MICHAEL JOSE',     'PLANIFICADOR',              'PLANEAMIENTO',       'STAFF', '',          6000),
            ('88990011', 'CABRERA VIDAL GLORIA TERESA',   'RECEPCIONISTA',             'ADMINISTRACION',     'STAFF', '',          2000),
            ('99001122', 'FUENTES MORA OSCAR DANIEL',     'OPERARIO ELECTRICISTA',     'ESPECIALIDADES',     'RCO',   '',          2500),
            ('10203040', 'ESPINOZA LUNA EVELYN GRACE',    'COORDINADORA DE OFICINA',   'OFICINA TECNICA',    'STAFF', '',          4500),
            ('20304050', 'ORTIZ PEREZ ALBERTO RAUL',      'MAESTRO DE OBRA',           'PRODUCCION',         'RCO',   '',          3000),
            ('30405060', 'MIRANDA SOTO FIORELLA BELEN',   'DISEÑADORA CAD',            'ARQUITECTURA',       'STAFF', '',          3800),
            ('40506070', 'ALVAREZ ROMERO DIEGO ARTURO',   'PROCURADOR',                'PROCURA',            'STAFF', '',          4200),
            ('50607080', 'PIZARRO CANO KARINA JANET',     'ADMINISTRADORA CONTRATOS',  'ADMINISTRACION',     'STAFF', '',          4000),
            ('60708090', 'REYES SALINAS FRANKLIN JESUS',  'CAPATAZ',                   'PRODUCCION',         'RCO',   '',          2800),
            ('70809010', 'GUILLEN TELLO VANESSA PILAR',   'ANALISTA DE CALIDAD',       'CALIDAD',            'STAFF', '',          4500),
            ('80901020', 'ACOSTA NEYRA HENRY PAUL',       'MODELADOR BIM',             'BIM',                'STAFF', '',          5000),
            ('90102030', 'DELGADO VELA MILAGROS RUTH',    'ASISTENTE DE PROCURA',      'PROCURA',            'STAFF', '',          3000),
            ('01020304', 'CHAVARRI POLO ENRIQUE JOSE',    'JEFE DE PLANEAMIENTO',      'PLANEAMIENTO',       'STAFF', '',          8000),
            ('12302345', 'NUÑEZ BARDALES WENDY STEFANI',  'ASISTENTE DE CALIDAD',      'CALIDAD',            'STAFF', '',          3200),
        ]
        creados = 0
        for (dni, nombre, cargo, area_nm, grupo, categ, sueldo) in DEMO:
            area_obj, _ = Area.objects.get_or_create(nombre=area_nm)
            sub_obj,  _ = SubArea.objects.get_or_create(nombre=area_nm, area=area_obj)
            reg_p = random.choice(['AFP', 'AFP', 'ONP'])
            _, created = Personal.objects.update_or_create(
                nro_doc=dni,
                defaults=dict(
                    apellidos_nombres   = nombre,
                    cargo               = cargo,
                    subarea             = sub_obj,
                    empresa             = empresa,
                    tipo_trabajador     = 'Empleado' if grupo == 'STAFF' else 'Obrero',
                    sexo                = _sexo_por_nombre(nombre),
                    sueldo_base         = Decimal(str(sueldo)),
                    grupo_tareo         = grupo,
                    condicion           = 'FORANEO' if grupo == 'RCO' else 'LOCAL',
                    categoria           = categ,
                    tipo_contrato       = 'PLAZO_FIJO',
                    regimen_pension     = reg_p,
                    afp                 = random.choice(AFP_LIST) if reg_p == 'AFP' else '',
                    estado              = 'Activo',
                    fecha_inicio_contrato = date.today() - timedelta(days=random.randint(180, 900)),
                    fecha_fin_contrato    = date.today() + timedelta(days=random.randint(30, 365)),
                )
            )
            if created:
                creados += 1
        ok(f'{creados} empleados demo creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 2 — CATEGORÍAS CAPACITACIÓN
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_categorias_capacitacion(self):
        hdr('2 — Categorías de Capacitación')
        try:
            from capacitaciones.models import CategoriaCapacitacion
        except ImportError:
            warn('Módulo capacitaciones no disponible'); return

        CATS = [
            ('SEG',  'Seguridad y Salud en el Trabajo', '🦺', '#ef4444', 1),
            ('TEC',  'Técnica y Especialidades',         '⚙️',  '#3b82f6', 2),
            ('GES',  'Gestión y Liderazgo',              '📊', '#8b5cf6', 3),
            ('IND',  'Inducción y Onboarding',           '🎓', '#10b981', 4),
            ('DIG',  'Transformación Digital',           '💻', '#f59e0b', 5),
            ('SOF',  'Habilidades Blandas',              '🤝', '#06b6d4', 6),
        ]
        creadas = 0
        for codigo, nombre, icono, color, orden in CATS:
            _, c = CategoriaCapacitacion.objects.get_or_create(
                codigo=codigo,
                defaults=dict(nombre=nombre, icono=icono, color=color, orden=orden, activa=True)
            )
            if c: creadas += 1
        ok(f'{creadas} categorías creadas')

    # ═══════════════════════════════════════════════════════════════════════
    # 3 — BANDAS SALARIALES
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_bandas_salariales(self):
        hdr('3 — Bandas Salariales')
        try:
            from salarios.models import BandaSalarial
            from personal.models import Personal
        except ImportError:
            warn('Módulo salarios no disponible'); return

        # Agrupar sueldos por cargo para definir bandas reales
        from django.db.models import Avg, Max, Min
        cargos_stats = (
            Personal.objects.filter(estado='Activo', sueldo_base__gt=0)
            .values('cargo')
            .annotate(avg=Avg('sueldo_base'), mn=Min('sueldo_base'), mx=Max('sueldo_base'))
            .order_by('cargo')
        )

        creadas = 0
        for cs in cargos_stats:
            cargo = cs['cargo']
            avg   = cs['avg'] or Decimal('2000')
            mn    = cs['mn']  or avg * Decimal('0.8')
            mx    = cs['mx']  or avg * Decimal('1.3')

            # Nivel según sueldo promedio
            if avg >= 10000:   nivel = 'GERENTE'
            elif avg >= 7000:  nivel = 'LEAD'
            elif avg >= 5000:  nivel = 'SENIOR'
            elif avg >= 3000:  nivel = 'SEMI_SENIOR'
            else:              nivel = 'JUNIOR'

            medio  = Decimal(str(avg)).quantize(Decimal('0.01'))
            minimo = max(Decimal(str(mn)).quantize(Decimal('0.01')), medio * Decimal('0.75'))
            maximo = max(Decimal(str(mx)).quantize(Decimal('0.01')), medio * Decimal('1.30'))

            _, c = BandaSalarial.objects.get_or_create(
                cargo=cargo, nivel=nivel,
                defaults=dict(minimo=minimo, medio=medio, maximo=maximo,
                              moneda='PEN', activa=True)
            )
            if c: creadas += 1

        ok(f'{creadas} bandas salariales creadas')

    # ═══════════════════════════════════════════════════════════════════════
    # 4 — HISTORIAL SALARIAL
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_historial_salarial(self):
        hdr('4 — Historial Salarial')
        try:
            from salarios.models import HistorialSalarial
            from personal.models import Personal
        except ImportError:
            warn('Módulo salarios no disponible'); return

        empleados = list(Personal.objects.filter(estado='Activo')[:80])
        creados = 0
        for emp in empleados:
            sueldo_actual = emp.sueldo_base or Decimal('1025')
            # Simula 1-3 incrementos históricos
            n_cambios = random.randint(1, 3)
            sueldo_hist = sueldo_actual * Decimal('0.85')
            for i in range(n_cambios):
                dias_atras = (n_cambios - i) * random.randint(120, 365)
                fecha_cambio = date.today() - timedelta(days=dias_atras)
                sueldo_nuevo = sueldo_hist * Decimal(str(1 + random.uniform(0.03, 0.12)))
                motivos = ['INCREMENTO_ANUAL', 'PROMOCION', 'MERITO', 'AJUSTE_MERCADO']
                _, c = HistorialSalarial.objects.get_or_create(
                    personal=emp,
                    fecha_efectiva=fecha_cambio,
                    defaults=dict(
                        remuneracion_anterior = sueldo_hist.quantize(Decimal('0.01')),
                        remuneracion_nueva    = sueldo_nuevo.quantize(Decimal('0.01')),
                        motivo                = random.choice(motivos),
                        aprobado_por          = self._get_admin_user(),
                        observaciones         = 'Registro historico demo',
                    )
                )
                if c: creados += 1
                sueldo_hist = sueldo_nuevo

        ok(f'{creados} registros historial salarial creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 5 — SALDOS VACACIONALES
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_saldos_vacaciones(self):
        hdr('5 — Saldos Vacacionales')
        try:
            from vacaciones.models import SaldoVacacional
            from personal.models import Personal
        except ImportError:
            warn('Módulo vacaciones no disponible'); return

        empleados = list(Personal.objects.filter(estado='Activo'))
        creados = 0
        for emp in empleados:
            # Periodo actual: ingreso → un año después
            fi = emp.fecha_inicio_contrato or (date.today() - timedelta(days=400))
            periodo_inicio = fi
            periodo_fin    = fi + timedelta(days=364)

            gozados  = random.randint(0, 20)
            vendidos = random.randint(0, 5) if random.random() < 0.15 else 0
            derecho  = 30

            try:
                _, c = SaldoVacacional.objects.get_or_create(
                    personal=emp,
                    periodo_inicio=periodo_inicio,
                    defaults=dict(
                        periodo_fin   = periodo_fin,
                        dias_derecho  = derecho,
                        dias_gozados  = min(gozados, derecho),
                        dias_vendidos = min(vendidos, derecho - gozados),
                        dias_pendientes = max(0, derecho - gozados - vendidos),
                        dias_truncos  = Decimal('0.00'),
                    )
                )
                if c: creados += 1
            except Exception:
                pass

        ok(f'{creados} saldos vacacionales creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 6 — CAPACITACIONES
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_capacitaciones(self):
        hdr('6 — Capacitaciones')
        try:
            from capacitaciones.models import CategoriaCapacitacion, Capacitacion, AsistenciaCapacitacion
            from personal.models import Personal
        except ImportError:
            warn('Módulo capacitaciones no disponible'); return

        admin = self._get_admin_user()
        cat_map = {c.codigo: c for c in CategoriaCapacitacion.objects.all()}
        if not cat_map:
            warn('Sin categorías — ejecuta seed completo')
            return

        CAPS = [
            ('Inducción General Harmoni 2025',      'IND', 'INDUCCION',  8,   0,    'COMPLETADA'),
            ('Seguridad en Obra — D.S. 011-2019',   'SEG', 'SSOMA',      16,  500,  'COMPLETADA'),
            ('AutoCAD 2025 Avanzado',               'TEC', 'EXTERNA',    24,  1200, 'COMPLETADA'),
            ('Liderazgo y Gestión de Equipos',      'GES', 'EXTERNA',    16,  2500, 'COMPLETADA'),
            ('BIM — Revit Structure',               'TEC', 'EXTERNA',    40,  3500, 'COMPLETADA'),
            ('Excel Avanzado para Gestión',         'DIG', 'INTERNA',    8,   0,    'COMPLETADA'),
            ('Primeros Auxilios y RCP',             'SEG', 'INTERNA',    8,   0,    'COMPLETADA'),
            ('Negociación y Comunicación Efectiva', 'SOF', 'EXTERNA',    12,  1800, 'EN_CURSO'),
            ('Power BI para RR.HH.',                'DIG', 'ELEARNING',  20,  800,  'EN_CURSO'),
            ('Gestión de Contratos — FIDIC',        'GES', 'EXTERNA',    24,  4500, 'PROGRAMADA'),
            ('Inducción Nuevos Ingresos Q1-2026',   'IND', 'INDUCCION',  8,   0,    'PROGRAMADA'),
            ('SSOMA — Riesgos Críticos',            'SEG', 'SSOMA',      24,  0,    'PROGRAMADA'),
        ]

        empleados = list(Personal.objects.filter(estado='Activo'))
        creadas = 0
        inscripciones = 0

        for titulo, cat_cod, tipo, horas, costo, estado in CAPS:
            cat = cat_map.get(cat_cod)
            if not cat: continue

            dias_atras = random.randint(-30, 180)
            f_inicio   = date.today() - timedelta(days=dias_atras)
            f_fin      = f_inicio + timedelta(days=max(1, horas // 8))

            cap, c = Capacitacion.objects.get_or_create(
                titulo=titulo,
                defaults=dict(
                    categoria    = cat,
                    tipo         = tipo,
                    fecha_inicio = f_inicio,
                    fecha_fin    = f_fin,
                    horas        = horas,
                    costo        = Decimal(str(costo)),
                    estado       = estado,
                    obligatoria  = tipo in ('SSOMA', 'INDUCCION'),
                    instructor   = 'Instructor Externo' if costo > 0 else 'Capacitador Interno',
                    lugar        = 'Sala de Capacitación — Sede Lima' if costo == 0 else 'Centro de Convenciones',
                    creado_por   = admin,
                )
            )
            if c: creadas += 1

            # Asignar 40-90% de empleados
            if estado != 'PROGRAMADA':
                muestra = random.sample(empleados, min(len(empleados), random.randint(
                    max(5, len(empleados)//3), min(len(empleados), len(empleados)*9//10)
                )))
                for emp in muestra:
                    est_asis = 'ASISTIO' if estado == 'COMPLETADA' else 'INSCRITO'
                    if est_asis == 'ASISTIO' and random.random() < 0.1:
                        est_asis = 'NO_ASISTIO'
                    _, ci = AsistenciaCapacitacion.objects.get_or_create(
                        capacitacion=cap, personal=emp,
                        defaults=dict(
                            estado=est_asis,
                            nota=Decimal(str(round(random.uniform(14, 20), 1))) if est_asis == 'ASISTIO' else None,
                            fecha_certificado=f_fin if est_asis == 'ASISTIO' else None,
                        )
                    )
                    if ci: inscripciones += 1

        ok(f'{creadas} capacitaciones, {inscripciones} inscripciones creadas')

    # ═══════════════════════════════════════════════════════════════════════
    # 7 — PRÉSTAMOS
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_prestamos(self):
        hdr('7 — Préstamos y Adelantos')
        try:
            from prestamos.models import TipoPrestamo, Prestamo, CuotaPrestamo
            from personal.models import Personal
        except ImportError:
            warn('Módulo préstamos no disponible'); return

        tipos = list(TipoPrestamo.objects.filter(activo=True))
        if not tipos:
            warn('Sin tipos de préstamo'); return

        empleados = list(Personal.objects.filter(estado='Activo'))
        muestra   = random.sample(empleados, min(25, len(empleados)))
        admin     = self._get_admin_user()
        creados   = 0

        ESTADOS_DIST = ['APROBADO', 'APROBADO', 'EN_CURSO', 'EN_CURSO', 'PAGADO', 'PENDIENTE']

        for emp in muestra:
            tipo  = random.choice(tipos)
            monto = Decimal(str(random.randint(1, 6) * 500))
            cuotas_n = random.randint(1, min(tipo.max_cuotas or 12, 12))
            est   = random.choice(ESTADOS_DIST)
            dias  = random.randint(30, 300)

            try:
                p, c = Prestamo.objects.get_or_create(
                    personal=emp, tipo=tipo,
                    defaults=dict(
                        monto_solicitado = monto,
                        monto_aprobado   = monto if est != 'PENDIENTE' else Decimal('0'),
                        num_cuotas       = cuotas_n,
                        estado           = est,
                        fecha_solicitud  = date.today() - timedelta(days=dias),
                        fecha_aprobacion = (date.today() - timedelta(days=dias-3)) if est not in ('PENDIENTE', 'BORRADOR') else None,
                        aprobado_por     = admin if est not in ('PENDIENTE', 'BORRADOR') else None,
                        motivo           = 'Necesidad personal',
                    )
                )
                if c: creados += 1
            except Exception:
                pass

        ok(f'{creados} préstamos creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 8 — DISCIPLINARIA
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_disciplinaria(self):
        hdr('8 — Procesos Disciplinarios')
        try:
            from disciplinaria.models import TipoFalta, MedidaDisciplinaria
            from personal.models import Personal
        except ImportError:
            warn('Módulo disciplinaria no disponible'); return

        tipos_falta = list(TipoFalta.objects.filter(activo=True))
        if not tipos_falta:
            warn('Sin tipos de falta configurados'); return

        empleados = list(Personal.objects.filter(estado='Activo'))
        muestra   = random.sample(empleados, min(8, len(empleados)))
        admin     = self._get_admin_user()
        creados   = 0

        MEDIDAS = ['VERBAL', 'ESCRITA', 'SUSPENSION']
        ESTADOS = ['RESUELTA', 'RESUELTA', 'EN_DESCARGO', 'NOTIFICADA']

        for emp in muestra:
            tipo_f = random.choice(tipos_falta)
            dias   = random.randint(15, 200)
            tipo_m = 'SUSPENSION' if tipo_f.gravedad == 'MUY_GRAVE' else random.choice(MEDIDAS[:2])
            est    = random.choice(ESTADOS)
            try:
                _, c = MedidaDisciplinaria.objects.get_or_create(
                    personal=emp,
                    fecha_hechos=date.today() - timedelta(days=dias),
                    defaults=dict(
                        tipo_falta           = tipo_f,
                        tipo_medida          = tipo_m,
                        descripcion_hechos   = f'Incumplimiento: {tipo_f.nombre}.',
                        estado               = est,
                        registrado_por       = admin,
                    )
                )
                if c: creados += 1
            except Exception:
                pass

        ok(f'{creados} procesos disciplinarios creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 9 — VACANTES (RECLUTAMIENTO)
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_vacantes(self):
        hdr('9 — Vacantes de Reclutamiento')
        try:
            from reclutamiento.models import Vacante, Postulacion, EtapaPipeline
            from personal.models import Area
        except ImportError:
            warn('Módulo reclutamiento no disponible'); return

        admin = self._get_admin_user()
        areas = {a.nombre: a for a in Area.objects.all()}

        VACANTES = [
            ('Ingeniero Civil Senior',           'PRODUCCION',     9000,  14000, 'PUBLICADA',   'ALTA'),
            ('Coordinador BIM',                  'BIM',            7000,  10000, 'PUBLICADA',   'MEDIA'),
            ('Especialista SSOMA',               'SSOMA',          5000,   8000, 'PUBLICADA',   'ALTA'),
            ('Asistente de Recursos Humanos',    'RRHH',           2500,   3500, 'PUBLICADA',   'NORMAL'),
            ('Jefe de Costos y Presupuestos',    'COSTOS',         8000,  12000, 'EN_PROCESO',  'ALTA'),
            ('Arquitecto de Proyectos',          'ARQUITECTURA',   6000,   9000, 'EN_PROCESO',  'MEDIA'),
            ('Analista de Planificación',        'PLANEAMIENTO',   4500,   7000, 'CERRADA',     'NORMAL'),
        ]

        area_default = next(iter(areas.values())) if areas else None
        creadas = 0
        for titulo, area_nm, sal_min, sal_max, estado, prioridad in VACANTES:
            area_obj = areas.get(area_nm) or areas.get(area_nm.upper()) or area_default
            if not area_obj: continue
            try:
                _, c = Vacante.objects.get_or_create(
                    titulo=titulo,
                    defaults=dict(
                        area              = area_obj,
                        estado            = estado,
                        prioridad         = prioridad,
                        descripcion       = f'Buscamos un/a {titulo} con experiencia en proyectos de construcción.',
                        requisitos        = '- Titulado en carrera afín\n- Mínimo 3 años de experiencia\n- Disponibilidad inmediata',
                        experiencia_minima= 3,
                        educacion_minima  = 'UNIVERSITARIA',
                        tipo_contrato     = 'PLAZO_FIJO',
                        salario_min       = Decimal(str(sal_min)),
                        salario_max       = Decimal(str(sal_max)),
                        moneda            = 'PEN',
                        fecha_publicacion = date.today() - timedelta(days=random.randint(5, 45)),
                        fecha_limite      = date.today() + timedelta(days=random.randint(15, 60)),
                        creado_por        = admin,
                    )
                )
                if c: creadas += 1
            except Exception as e:
                warn(f'Error vacante {titulo}: {e}')

        ok(f'{creadas} vacantes creadas')

        # Postulantes demo
        self._seed_postulantes()

    def _seed_postulantes(self):
        try:
            from reclutamiento.models import Vacante, Postulacion, EtapaPipeline
        except ImportError:
            return

        NOMBRES = [
            ('78234561', 'PALOMINO VERA CESAR AUGUSTO',      'cesarpalomino@gmail.com'),
            ('67891234', 'ESPEJO HUANCA MIRIAM CECILIA',      'miriam.espejo@outlook.com'),
            ('56012345', 'ZAPATA RIOS JONATHAN DAVID',        'jzapata@gmail.com'),
            ('45901234', 'ASTO MAMANI YOLANDA VICTORIA',      'yolanda.asto@gmail.com'),
            ('34890123', 'VILCHEZ PAREDES ROBERTO CARLOS',    'rvilchez@hotmail.com'),
            ('23789012', 'CONDORI FLORES SILVIA PATRICIA',    'scondori@gmail.com'),
            ('12678901', 'HERRERA SALINAS FELIX AUGUSTO',     'fherrera@gmail.com'),
            ('11567890', 'CHAUCA LUNA STEPHANY MILUSKA',      'schauca@gmail.com'),
            ('99456789', 'PORTAL ROCA DIEGO ARMANDO',         'dportal@outlook.com'),
            ('88345678', 'DIAZ TORRES KAREN MELISSA',         'kdiaz@gmail.com'),
        ]
        vacantes = list(Vacante.objects.filter(estado__in=['PUBLICADA', 'EN_PROCESO'])[:5])
        creados = 0
        ETAPAS = ['POSTULACION', 'CV_REVIEW', 'ENTREVISTA_HR', 'ENTREVISTA_TECNICA', 'OFERTA']
        for dni, nombre, email in NOMBRES:
            vac = random.choice(vacantes) if vacantes else None
            if not vac: continue
            try:
                _, c = Postulacion.objects.get_or_create(
                    email=email,
                    vacante=vac,
                    defaults=dict(
                        nombre_completo   = nombre,
                        etapa             = random.choice(ETAPAS),
                        estado            = 'ACTIVA',
                        experiencia_anos  = random.randint(1, 10),
                        fuente            = random.choice(['LINKEDIN', 'REFERIDO', 'PORTAL_WEB', 'BOLSA_TRABAJO']),
                    )
                )
                if c: creados += 1
            except Exception:
                pass
        ok(f'{creados} postulantes creados')

    # ═══════════════════════════════════════════════════════════════════════
    # 10 — ENCUESTA CLIMA LABORAL
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_encuesta(self):
        hdr('10 — Encuesta de Clima Laboral')
        try:
            from encuestas.models import Encuesta, PreguntaEncuesta, RespuestaEncuesta, ResultadoEncuesta
            from personal.models import Personal
        except ImportError:
            warn('Módulo encuestas no disponible'); return

        admin = self._get_admin_user()

        enc, c = Encuesta.objects.get_or_create(
            titulo='Clima Laboral 2025 — Harmoni',
            defaults=dict(
                descripcion  = 'Encuesta anual de clima laboral. Tus respuestas son anónimas.',
                tipo         = 'CLIMA',
                estado       = 'CERRADA',
                anonima      = True,
                fecha_inicio = date.today() - timedelta(days=60),
                fecha_fin    = date.today() - timedelta(days=30),
                creado_por   = admin,
            )
        )

        PREGUNTAS = [
            ('¿Estás satisfecho con tu ambiente de trabajo?',      'ESCALA', True),
            ('¿Tu jefe directo te brinda retroalimentación?',       'ESCALA', True),
            ('¿Las herramientas y equipos son adecuados?',          'ESCALA', True),
            ('¿Sientes que tu trabajo es reconocido?',              'ESCALA', True),
            ('¿Recomendarías Harmoni como lugar de trabajo?',       'ESCALA', True),
            ('¿Cuál es tu principal motivación en el trabajo?',     'TEXTO',  False),
            ('¿Qué mejorarías de la empresa?',                      'TEXTO',  False),
        ]

        for i, (texto, tipo_p, obligatoria) in enumerate(PREGUNTAS, 1):
            PreguntaEncuesta.objects.get_or_create(
                encuesta=enc, orden=i,
                defaults=dict(texto=texto, tipo=tipo_p, obligatoria=obligatoria)
            )

        # Respuestas de empleados (60% participación)
        empleados = list(Personal.objects.filter(estado='Activo'))
        muestra   = random.sample(empleados, int(len(empleados) * 0.60))
        respuestas = 0
        preguntas  = list(enc.preguntas.all()) if hasattr(enc, 'preguntas') else []

        for emp in muestra:
            try:
                re, cr = RespuestaEncuesta.objects.get_or_create(
                    encuesta=enc,
                    personal=emp if not enc.anonima else None,
                    defaults=dict(completada=True, fecha_respuesta=enc.fecha_fin - timedelta(days=random.randint(0, 20)))
                )
                if cr:
                    for preg in preguntas:
                        pass  # respuestas por pregunta no implementadas en este modelo
                    respuestas += 1
            except Exception:
                pass

        ok(f'Encuesta clima laboral + {respuestas} respuestas creadas')

        # eNPS
        self._seed_enps(admin)

    def _seed_enps(self, admin):
        try:
            from encuestas.models import Encuesta, PreguntaEncuesta
        except ImportError:
            return
        enc2, c = Encuesta.objects.get_or_create(
            titulo='eNPS Q4-2025',
            defaults=dict(
                descripcion  = '¿Recomendarías trabajar en Harmoni? Escala 0-10.',
                tipo         = 'ENPS',
                estado       = 'CERRADA',
                anonima      = True,
                fecha_inicio = date.today() - timedelta(days=90),
                fecha_fin    = date.today() - timedelta(days=75),
                creado_por   = admin,
            )
        )
        if c:
            PreguntaEncuesta.objects.get_or_create(
                encuesta=enc2, orden=1,
                defaults=dict(
                    texto='En una escala de 0 a 10, ¿qué tan probable es que recomiendes esta empresa como lugar de trabajo?',
                    tipo='ESCALA', obligatoria=True
                )
            )
            ok('Encuesta eNPS Q4-2025 creada')

    # ═══════════════════════════════════════════════════════════════════════
    # 11 — EVALUACIONES DE DESEMPEÑO
    # ═══════════════════════════════════════════════════════════════════════
    def _seed_evaluaciones(self):
        hdr('11 — Evaluaciones de Desempeño')
        try:
            from evaluaciones.models import CicloEvaluacion, Evaluacion
            from personal.models import Personal
        except ImportError:
            warn('Módulo evaluaciones no disponible'); return

        admin = self._get_admin_user()

        ciclo, c = CicloEvaluacion.objects.get_or_create(
            nombre='Evaluación Anual 2025',
            defaults=dict(
                descripcion  = 'Evaluación de desempeño anual — período enero a diciembre 2025.',
                fecha_inicio = date(2025, 1, 1),
                fecha_fin    = date(2025, 12, 31),
                estado       = 'CERRADO',
                tipo         = '360' if hasattr(CicloEvaluacion, 'tipo') else None,
            )
        )
        if not c:
            ok('Ciclo evaluación 2025 ya existe')

        # Ciclo en curso
        ciclo2, c2 = CicloEvaluacion.objects.get_or_create(
            nombre='Evaluación Semestral S1-2026',
            defaults=dict(
                descripcion  = 'Evaluación de desempeño primer semestre 2026.',
                fecha_inicio = date(2026, 1, 1),
                fecha_fin    = date(2026, 6, 30),
                estado       = 'EN_CURSO',
            )
        )

        # Asignar evaluaciones a empleados
        empleados = list(Personal.objects.filter(estado='Activo'))
        jefes     = [e for e in empleados if any(k in e.cargo.upper() for k in ['JEFE', 'GERENTE', 'COORDINADOR', 'SUPERVISOR'])]
        if not jefes:
            jefes = empleados[:5]

        creadas = 0
        muestra = random.sample(empleados, min(40, len(empleados)))

        for emp in muestra:
            evaluador = random.choice(jefes) if jefes else emp
            try:
                _, c = Evaluacion.objects.get_or_create(
                    ciclo    = ciclo,
                    evaluado = emp,
                    defaults=dict(
                        evaluador    = evaluador,
                        estado       = 'COMPLETADA',
                        comentario_general = 'Evaluacion anual completada satisfactoriamente.',
                        comentarios  = 'Evaluación anual completada satisfactoriamente.',
                        fecha_completada = date(2025, 12, 20),
                    )
                )
                if c: creadas += 1
            except Exception:
                pass

        ok(f'{creadas} evaluaciones de desempeño creadas')

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════
    def _get_empresa(self):
        from empresas.models import Empresa
        return Empresa.objects.get(id=EMPRESA_ID)

    def _get_admin_user(self):
        u = User.objects.filter(is_superuser=True).first()
        if not u:
            u = User.objects.filter(is_staff=True).first()
        if not u:
            u, _ = User.objects.get_or_create(
                username='admin_demo',
                defaults=dict(email='admin@harmoni.pe', is_staff=True, is_superuser=True)
            )
            u.set_password('Harmoni2026!')
            u.save()
        return u
