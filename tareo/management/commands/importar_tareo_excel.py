"""
Comando de management: importar_tareo_excel

Procesa el archivo Tareo.xlsx (o cualquier archivo con el mismo formato)
y genera registros en los modelos del módulo Tareo.

Hojas soportadas:
  --reloj      → hoja "Reloj"      (marcación diaria del sistema biométrico)
  --papeletas  → hoja "Papeletas"  (justificaciones y permisos)
  --staff      → hoja "CSRT STAFF" (solo lectura para determinar grupo STAFF)
  --rco        → hoja "CSRT RCO"   (solo lectura para determinar grupo RCO)
  --s10        → hoja "S10"        (importar RegistroS10 para cruce)
  --sunat      → hoja externa SUNAT/PLAME (RegistroSUNAT)

Uso básico:
    python manage.py importar_tareo_excel Tareo.xlsx
    python manage.py importar_tareo_excel Tareo.xlsx --reloj --papeletas --s10
    python manage.py importar_tareo_excel Tareo.xlsx --dry-run
    python manage.py importar_tareo_excel Tareo.xlsx --periodo-inicio 2026-01-21 --periodo-fin 2026-02-20
"""

import re
import datetime
import logging
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('tareo.importacion')


# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

# Meses abreviados en español (Reloj usa "Ene-21", "Feb-1", etc.)
MES_MAP = {
    'ene': 1, 'feb': 2, 'mar': 3, 'abr': 4,
    'may': 5, 'jun': 6, 'jul': 7, 'ago': 8,
    'sep': 9, 'oct': 10, 'nov': 11, 'dic': 12,
}

# Columnas fijas del Reloj (antes de los días)
RELOJ_COLS_FIJAS = {
    'DNI': 'dni',
    'Nombre Completo': 'nombre',
    'Celular': 'celular',
    'Fecha Ingreso': 'fecha_ingreso',
    'Partida': 'partida',
    'Condicion': 'condicion',
    'Tipo Trabajador': 'tipo_trab',
    'Area': 'area',
    'Cargo': 'cargo',
}

# Columnas fijas de Papeletas
PAPELETA_COLS = {
    'TipoPermiso': 'tipo_permiso_raw',
    'DNI': 'dni',
    'Personal': 'nombre',
    'Area Trabajo': 'area_trabajo',
    'Cargo': 'cargo',
    'Iniciales': 'iniciales',
    'FechaInicio': 'fecha_inicio',
    'FechaFin': 'fecha_fin',
    'Detalle': 'detalle',
}

# Normalización de condicion texto → elección del sistema
CONDICION_MAP = {
    'local': 'LOCAL',
    'foráneo': 'FORANEO',
    'foraneo': 'FORANEO',
    'lima': 'LIMA',
}

# Mapeo de iniciales de papeleta → tipo_permiso
INICIALES_TIPO = {
    'CHE':  'COMPENSACION_HE',
    'C':    'COMPENSACION_HE',
    'B':    'BAJADAS',
    'BA':   'BAJADAS_ACUMULADAS',
    'V':    'VACACIONES',
    'DM':   'DESCANSO_MEDICO',
    'LF':   'LICENCIA_FALLECIMIENTO',
    'LP':   'LICENCIA_PATERNIDAD',
    'LCG':  'LICENCIA_CON_GOCE',
    'LSG':  'LICENCIA_SIN_GOCE',
    'CT':   'COMISION_TRABAJO',
    'CPF':  'COMPENSACION_FERIADO',
    'CDT':  'COMP_DIA_TRABAJO',
    'AS':   'SUSPENSION',
    'SAI':  'SUSPENSION',
}

# Columnas fijas S10 (hoja DatosPorPeriodo / S10 del Excel)
S10_COLS = {
    'Código': 'codigo_s10',
    'DNI': 'nro_doc',
    'Nombre': 'apellidos_nombres',
    'Categoría': 'categoria',
    'Recurso equivalente': 'ocupacion',
    'Ocupación': 'ocupacion',
    'Fecha Ingreso': 'fecha_ingreso',
    'Fecha Cese': 'fecha_cese',
    'Condición': 'condicion',
    'EnTareo': 'en_tareo',
    'Régimen Pensión': 'regimen_pension',
    'Código Proyecto Destino (Tareo autom.)': 'codigo_proyecto',
}


# ─────────────────────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────────────────────

def limpiar_dni(valor) -> str:
    """Normaliza un DNI: quita .0, espacios; retorna string."""
    if pd.isna(valor):
        return ''
    s = str(valor).strip().replace('.0', '')
    return s


def es_dni_valido(dni: str) -> bool:
    return bool(re.fullmatch(r'\d{8}', dni))


def parse_horas(valor) -> Decimal | None:
    """
    Convierte el valor de una celda del Reloj a Decimal de horas.
    Retorna None si el valor no es numérico (es un código: 'B', 'V', etc.)
    """
    if pd.isna(valor):
        return None
    try:
        h = Decimal(str(float(valor)))
        if h >= 0:
            return h
    except (InvalidOperation, ValueError, TypeError):
        pass
    return None


def parse_columna_fecha(col_name: str, anio_base: int = None) -> datetime.date | None:
    """
    Convierte el nombre de columna del Reloj a fecha.
    Formatos soportados:
      "Ene-21"  → 21 de enero del año deducido
      "Feb-1"   → 1 de febrero del año deducido
      datetime  → ya es fecha
    """
    if isinstance(col_name, (datetime.datetime, datetime.date)):
        return col_name.date() if hasattr(col_name, 'date') else col_name

    s = str(col_name).strip().lower()
    match = re.match(r'([a-záéíóú]+)-(\d{1,2})$', s)
    if not match:
        return None

    mes_str, dia_str = match.group(1), match.group(2)
    mes = MES_MAP.get(mes_str[:3])
    if not mes:
        return None

    dia = int(dia_str)
    anio = anio_base or datetime.date.today().year

    # Heurística: si mes < mes actual y no hay año_base, probablemente es año siguiente
    try:
        return datetime.date(anio, mes, dia)
    except ValueError:
        return None


def detectar_periodo(fechas: list[datetime.date]) -> tuple[datetime.date, datetime.date]:
    """Retorna (min_fecha, max_fecha) de la lista."""
    validas = [f for f in fechas if f is not None]
    if not validas:
        raise ValueError("No se pudieron detectar fechas en las columnas del Reloj.")
    return min(validas), max(validas)


def normalizar_condicion(valor) -> str:
    """Convierte texto de condición a código interno."""
    if pd.isna(valor):
        return 'LOCAL'
    return CONDICION_MAP.get(str(valor).strip().lower(), 'LOCAL')


def calcular_horas_efectivas(horas_brutas: Decimal, minutos_almuerzo: int) -> Decimal:
    almuerzo = Decimal(str(minutos_almuerzo / 60))
    return max(Decimal('0'), horas_brutas - almuerzo)


def calcular_he_dia(horas_efectivas: Decimal, jornada_normal: Decimal) -> dict:
    """
    Calcula horas extras del día según normativa:
      1ra y 2da hora → 25%
      3ra en adelante → 35%
    Retorna dict con he_total, he_25, he_35, horas_normales
    """
    exceso = max(Decimal('0'), horas_efectivas - jornada_normal)
    he_25 = min(exceso, Decimal('2'))
    he_35 = max(Decimal('0'), exceso - Decimal('2'))
    return {
        'horas_normales': min(horas_efectivas, jornada_normal),
        'he_25': he_25,
        'he_35': he_35,
        'he_total': exceso,
    }


def mapear_tipo_permiso(tipo_raw: str, iniciales: str) -> str:
    """Determina el tipo_permiso interno a partir del texto o las iniciales."""
    # Primero intentar por iniciales (más preciso)
    ini = str(iniciales).strip().upper() if iniciales and not pd.isna(iniciales) else ''
    if ini and ini in INICIALES_TIPO:
        return INICIALES_TIPO[ini]

    # Luego por texto parcial
    t = str(tipo_raw).strip().upper() if tipo_raw and not pd.isna(tipo_raw) else ''
    mapping = {
        'COMPENSACION POR HORARIO': 'COMPENSACION_HE',
        'BAJADAS ACUMULADAS': 'BAJADAS_ACUMULADAS',
        'BAJADAS': 'BAJADAS',
        'VACACIONES': 'VACACIONES',
        'DESCANSO MEDICO': 'DESCANSO_MEDICO',
        'FALLECIMIENTO': 'LICENCIA_FALLECIMIENTO',
        'PATERNIDAD': 'LICENCIA_PATERNIDAD',
        'LICENCIA CON GOCE': 'LICENCIA_CON_GOCE',
        'LICENCIA SIN GOCE': 'LICENCIA_SIN_GOCE',
        'COMISION DE TRABAJO': 'COMISION_TRABAJO',
        'COMPENSACION POR FERIADO': 'COMPENSACION_FERIADO',
        'SUSPENSION': 'SUSPENSION',
    }
    for key, val in mapping.items():
        if key in t:
            return val

    return 'OTRO'


# ─────────────────────────────────────────────────────────────
# COMANDO PRINCIPAL
# ─────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = "Importa Tareo.xlsx al módulo Tareo (Reloj, Papeletas, S10, SUNAT)"

    def add_arguments(self, parser):
        parser.add_argument('archivo', type=str, help="Ruta al archivo .xlsx")
        parser.add_argument(
            '--reloj', action='store_true', default=False,
            help="Procesar hoja Reloj")
        parser.add_argument(
            '--papeletas', action='store_true', default=False,
            help="Procesar hoja Papeletas")
        parser.add_argument(
            '--s10', action='store_true', default=False,
            help="Procesar hoja S10 (DatosPorPeriodo o S10)")
        parser.add_argument(
            '--todo', action='store_true', default=False,
            help="Procesar todas las fuentes disponibles")
        parser.add_argument(
            '--hoja-reloj', type=str, default='Reloj',
            help="Nombre de la hoja Reloj (default: 'Reloj')")
        parser.add_argument(
            '--hoja-papeletas', type=str, default='Papeletas',
            help="Nombre de la hoja Papeletas (default: 'Papeletas')")
        parser.add_argument(
            '--hoja-staff', type=str, default='CSRT STAFF',
            help="Nombre de la hoja STAFF para detectar grupo")
        parser.add_argument(
            '--hoja-rco', type=str, default='CSRT RCO',
            help="Nombre de la hoja RCO para detectar grupo")
        parser.add_argument(
            '--hoja-s10', type=str, default='S10',
            help="Nombre de la hoja S10 (default: 'S10')")
        parser.add_argument(
            '--periodo-inicio', type=str, default=None,
            help="Inicio del período YYYY-MM-DD (si no se detecta del archivo)")
        parser.add_argument(
            '--periodo-fin', type=str, default=None,
            help="Fin del período YYYY-MM-DD (si no se detecta del archivo)")
        parser.add_argument(
            '--anio', type=int, default=None,
            help="Año base para interpretar columnas de fechas (default: año actual)")
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help="Simular la importación sin guardar en BD")
        parser.add_argument(
            '--force', action='store_true', default=False,
            help="Sobreescribir registros existentes de la misma importación")
        parser.add_argument(
            '--regimen-default', type=str, default='5X2',
            help="Código de régimen por defecto para LOCAL (default: 5X2)")
        parser.add_argument(
            '--regimen-foraneo', type=str, default='21X7',
            help="Código de régimen para FORÁNEO (default: 21X7)")

    # ── handle ─────────────────────────────────────────────────

    def handle(self, *args, **options):
        archivo = Path(options['archivo'])
        if not archivo.exists():
            raise CommandError(f"Archivo no encontrado: {archivo}")
        if archivo.suffix.lower() not in ('.xlsx', '.xls'):
            raise CommandError("Solo se aceptan archivos .xlsx o .xls")

        dry_run = options['dry_run']
        todo = options['todo']

        procesar_reloj = todo or options['reloj']
        procesar_papeletas = todo or options['papeletas']
        procesar_s10 = todo or options['s10']

        if not any([procesar_reloj, procesar_papeletas, procesar_s10]):
            # Por defecto procesar reloj + papeletas
            procesar_reloj = True
            procesar_papeletas = True

        anio_base = options['anio'] or datetime.date.today().year

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\n{'[DRY-RUN] ' if dry_run else ''}═══ Importar Tareo Excel ═══"
        ))
        self.stdout.write(f"Archivo : {archivo.name}")
        self.stdout.write(f"Año base: {anio_base}")
        self.stdout.write(f"Fuentes : "
                          f"{'[RELOJ] ' if procesar_reloj else ''}"
                          f"{'[PAPELETAS] ' if procesar_papeletas else ''}"
                          f"{'[S10] ' if procesar_s10 else ''}\n")

        # Cargar tablas de apoyo en memoria
        ctx = self._cargar_contexto(options)

        # Determinar DNIs de STAFF y RCO leyendo las hojas de resumen
        xls = pd.ExcelFile(archivo)
        staff_dnis, rco_dnis = self._detectar_grupos(xls, options)
        ctx['staff_dnis'] = staff_dnis
        ctx['rco_dnis'] = rco_dnis
        self.stdout.write(
            f"Grupos detectados → STAFF: {len(staff_dnis)} DNIs | RCO: {len(rco_dnis)} DNIs"
        )

        resultados = {}

        with transaction.atomic():
            if procesar_reloj:
                resultados['reloj'] = self._importar_reloj(
                    xls, options, ctx, dry_run)

            if procesar_papeletas and resultados.get('reloj'):
                imp = resultados['reloj']['importacion']  # reusar importación
                resultados['papeletas'] = self._importar_papeletas(
                    xls, options, ctx, imp, dry_run)
            elif procesar_papeletas:
                resultados['papeletas'] = self._importar_papeletas(
                    xls, options, ctx, None, dry_run)

            if procesar_s10:
                resultados['s10'] = self._importar_s10(
                    xls, options, ctx, dry_run)

            if dry_run:
                self.stdout.write(self.style.WARNING(
                    "\n[DRY-RUN] Rolled back — ningún cambio guardado."))
                transaction.set_rollback(True)

        self._imprimir_resumen(resultados)

    # ── Carga de tablas de apoyo ────────────────────────────────

    def _cargar_contexto(self, options) -> dict:
        """Carga en memoria: homologaciones, feriados, regímenes."""
        from tareo.models import HomologacionCodigo, FeriadoCalendario, RegimenTurno

        homo = {
            h.codigo_origen: h
            for h in HomologacionCodigo.objects.filter(activo=True)
        }
        feriados = set(
            FeriadoCalendario.objects.filter(activo=True).values_list('fecha', flat=True)
        )
        regimenes = {
            r.codigo: r for r in RegimenTurno.objects.filter(activo=True).prefetch_related('horarios')
        }

        # Precargar personal (DNI → instancia)
        from personal.models import Personal
        personal_map = {
            p.nro_doc: p
            for p in Personal.objects.all().only('id', 'nro_doc', 'apellidos_nombres')
        }

        cod_local = options.get('regimen_default', '5X2')
        cod_foraneo = options.get('regimen_foraneo', '21X7')

        ctx = {
            'homo': homo,
            'feriados': feriados,
            'regimenes': regimenes,
            'personal_map': personal_map,
            'cod_local': cod_local,
            'cod_foraneo': cod_foraneo,
        }

        if not homo:
            self.stdout.write(self.style.WARNING(
                "  ⚠ No hay homologaciones cargadas. "
                "Ejecuta: python manage.py seed_tareo_inicial"
            ))
        return ctx

    # ── Detección de grupos STAFF / RCO ────────────────────────

    def _detectar_grupos(self, xls: pd.ExcelFile, options) -> tuple[set, set]:
        """
        Lee las hojas CSRT STAFF y CSRT RCO (header en fila 6)
        y retorna sets de DNIs para cada grupo.
        """
        staff_dnis: set = set()
        rco_dnis: set = set()

        for hoja, target_set in [
            (options['hoja_staff'], staff_dnis),
            (options['hoja_rco'], rco_dnis),
        ]:
            if hoja not in xls.sheet_names:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠ Hoja '{hoja}' no encontrada — se omite."))
                continue
            try:
                df = pd.read_excel(xls, sheet_name=hoja, header=6)
                if 'DNI' in df.columns:
                    for v in df['DNI'].dropna():
                        d = limpiar_dni(v)
                        if d:
                            target_set.add(d)
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠ Error leyendo '{hoja}': {e}"))

        return staff_dnis, rco_dnis

    # ── Importar Reloj ──────────────────────────────────────────

    def _importar_reloj(self, xls: pd.ExcelFile, options, ctx, dry_run) -> dict:
        from tareo.models import (TareoImportacion, RegistroTareo,
                                   BancoHoras, MovimientoBancoHoras)

        hoja = options['hoja_reloj']
        if hoja not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(f"  ⚠ Hoja '{hoja}' no encontrada."))
            return {}

        self.stdout.write(f"\n▸ Procesando hoja '{hoja}'...")

        anio_base = options['anio'] or datetime.date.today().year
        df = pd.read_excel(xls, sheet_name=hoja, header=1)  # fila 1 = encabezado

        # Identificar columnas de días vs columnas fijas
        col_fijas = set(RELOJ_COLS_FIJAS.keys())
        col_dias: list[tuple[str, datetime.date]] = []  # (nombre_col, fecha)
        for col in df.columns:
            if str(col) in col_fijas:
                continue
            # intentar parsear como fecha
            fecha = parse_columna_fecha(col, anio_base)
            if fecha:
                col_dias.append((col, fecha))

        if not col_dias:
            self.stdout.write(self.style.ERROR("  ✗ No se encontraron columnas de fechas en el Reloj."))
            return {}

        fechas = [f for _, f in col_dias]
        periodo_inicio, periodo_fin = detectar_periodo(fechas)

        # Sobrescribir si se pasaron como argumento
        if options.get('periodo_inicio'):
            periodo_inicio = datetime.date.fromisoformat(options['periodo_inicio'])
        if options.get('periodo_fin'):
            periodo_fin = datetime.date.fromisoformat(options['periodo_fin'])

        self.stdout.write(
            f"  Período detectado : {periodo_inicio} → {periodo_fin} "
            f"({len(col_dias)} días)"
        )

        # Crear importación
        importacion = TareoImportacion(
            tipo='RELOJ',
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            archivo_nombre=options['archivo'],
            estado='PROCESANDO',
            metadata={
                'hoja': hoja,
                'columnas_dia': len(col_dias),
                'anio_base': anio_base,
            }
        )
        if not dry_run:
            importacion.save()

        # Prefetch feriados como set
        feriados: set = ctx['feriados']
        homo: dict = ctx['homo']
        personal_map: dict = ctx['personal_map']
        staff_dnis: set = ctx['staff_dnis']
        rco_dnis: set = ctx['rco_dnis']
        regimenes: dict = ctx['regimenes']
        cod_local: str = ctx['cod_local']
        cod_foraneo: str = ctx['cod_foraneo']

        ok = errores = sin_match = 0
        err_list = []
        advertencias = []

        # Registros para banco de horas (STAFF) agrupados por dnin y mes
        banco_acumulado: dict = {}  # (dni, anio, mes) → {he_25, he_35, he_100}

        # Filtrar el DataFrame ANTES de iterar: solo STAFF y RCO
        todos_validos = staff_dnis | rco_dnis
        df['_dni_limpio'] = df['DNI'].apply(limpiar_dni)
        df_filtrado = df[df['_dni_limpio'].isin(todos_validos)].copy()
        personas_fuera = df.shape[0] - df_filtrado.shape[0]
        if personas_fuera > 0:
            self.stdout.write(
                f"  Filtrando {personas_fuera} personas históricas (no STAFF ni RCO) "
                f"→ procesando {df_filtrado.shape[0]} de {df.shape[0]} filas."
            )

        for idx, row in df_filtrado.iterrows():
            # ── Leer datos fijos ──────────────────────────────
            dni = row['_dni_limpio']
            if not dni:
                continue

            if not es_dni_valido(dni):
                advertencias.append({
                    'fila': idx + 3,
                    'dni': dni,
                    'mensaje': f"DNI no tiene 8 dígitos: '{dni}' — se procesa igual."
                })

            nombre = str(row.get('Nombre Completo', '')).strip()
            condicion_raw = row.get('Condicion', '')
            condicion = normalizar_condicion(condicion_raw)

            # LIMA hereda LOCAL
            if condicion == 'LIMA':
                condicion_efectiva = 'LOCAL'
            else:
                condicion_efectiva = condicion

            # Determinar grupo
            if dni in staff_dnis:
                grupo = 'STAFF'
            else:
                grupo = 'RCO'

            # Determinar régimen
            if condicion_efectiva == 'FORANEO':
                regimen = regimenes.get(cod_foraneo)
            else:
                regimen = regimenes.get(cod_local)

            jornada_normal = (
                regimen.horarios.filter(
                    tipo_dia__in=['LUNES_VIERNES', 'LUNES_SABADO', 'TODOS', 'TURNO_A']
                ).first().horas_efectivas
                if regimen and regimen.horarios.exists()
                else Decimal('8.5')
            )

            personal_obj = personal_map.get(dni)
            if not personal_obj:
                sin_match += 1

            # ── Iterar sobre columnas de días ─────────────────
            for col_name, fecha in col_dias:
                valor_raw = row.get(col_name)
                if pd.isna(valor_raw) and col_name not in df.columns:
                    continue

                valor_str = '' if pd.isna(valor_raw) else str(valor_raw).strip()
                horas_num = parse_horas(valor_raw)
                es_feriado_dia = fecha in feriados

                # ── Determinar código y fuente ────────────────
                codigo_dia = ''
                fuente = 'RELOJ'
                horas_marcadas = None
                horas_efectivas = Decimal('0')
                horas_normales = Decimal('0')
                he_25 = Decimal('0')
                he_35 = Decimal('0')
                he_100 = Decimal('0')

                if valor_str == '' or pd.isna(valor_raw):
                    # En blanco → Falta
                    codigo_dia = 'F'
                    fuente = 'FALTA_AUTO'
                    homo_key = 'BLANK'

                elif horas_num is not None:
                    # Valor numérico → asistencia con horas
                    horas_marcadas = horas_num
                    homo_key = '>0'
                    minutos_almuerzo = regimen.minutos_almuerzo if regimen else 60
                    horas_efectivas = calcular_horas_efectivas(
                        horas_marcadas, minutos_almuerzo)

                    if es_feriado_dia:
                        # Feriado laborado → HE 100%
                        codigo_dia = 'FL'
                        fuente = 'FERIADO'
                        he_100 = horas_efectivas
                        horas_normales = Decimal('0')
                    else:
                        codigo_dia = 'A'
                        resultado_he = calcular_he_dia(horas_efectivas, jornada_normal)
                        horas_normales = resultado_he['horas_normales']
                        he_25 = resultado_he['he_25']
                        he_35 = resultado_he['he_35']

                else:
                    # Código de texto → aplicar homologación
                    val_upper = valor_str.upper()
                    homo_obj = homo.get(val_upper)
                    if homo_obj:
                        codigo_dia = homo_obj.codigo_tareo
                        homo_key = val_upper
                        if homo_obj.tipo_evento == 'FERIADO_LABORADO':
                            fuente = 'FERIADO'
                        elif homo_obj.tipo_evento in ('AUSENCIA', 'SUSPENSION'):
                            fuente = 'RELOJ'
                        else:
                            fuente = 'RELOJ'
                    else:
                        # Código no mapeado → conservar tal cual con advertencia
                        codigo_dia = val_upper
                        homo_key = val_upper
                        advertencias.append({
                            'fila': idx + 3,
                            'dni': dni,
                            'fecha': str(fecha),
                            'mensaje': f"Código '{val_upper}' no está en homologación."
                        })

                # Si el código final es NOR (del STAFF), mapear a 'A'
                if codigo_dia == 'NOR':
                    codigo_dia = 'A'

                # Las HE del STAFF van al banco (no se pagan)
                he_al_banco = (grupo == 'STAFF')

                # ── Guardar RegistroTareo ──────────────────────
                registro_data = dict(
                    importacion=importacion if not dry_run else None,
                    personal=personal_obj,
                    dni=dni,
                    nombre_archivo=nombre,
                    grupo=grupo,
                    condicion=condicion,
                    regimen=regimen,
                    fecha=fecha,
                    dia_semana=fecha.weekday(),
                    es_feriado=es_feriado_dia,
                    valor_reloj_raw=valor_str,
                    horas_marcadas=horas_marcadas,
                    codigo_dia=codigo_dia,
                    fuente_codigo=fuente,
                    horas_efectivas=horas_efectivas,
                    horas_normales=horas_normales,
                    he_25=he_25,
                    he_35=he_35,
                    he_100=he_100,
                    he_al_banco=he_al_banco,
                )

                if not dry_run:
                    try:
                        obj, created = RegistroTareo.objects.update_or_create(
                            importacion=importacion,
                            dni=dni,
                            fecha=fecha,
                            defaults={k: v for k, v in registro_data.items()
                                       if k not in ('importacion', 'dni', 'fecha')}
                        )

                        # Acumular banco de horas para STAFF
                        if grupo == 'STAFF' and personal_obj and (he_25 + he_35 + he_100) > 0:
                            key = (personal_obj.pk, fecha.year, fecha.month)
                            if key not in banco_acumulado:
                                banco_acumulado[key] = {
                                    'he_25': Decimal('0'),
                                    'he_35': Decimal('0'),
                                    'he_100': Decimal('0'),
                                    'registros': [],
                                }
                            banco_acumulado[key]['he_25'] += he_25
                            banco_acumulado[key]['he_35'] += he_35
                            banco_acumulado[key]['he_100'] += he_100
                            banco_acumulado[key]['registros'].append((obj, he_25, he_35, he_100))

                        if created:
                            ok += 1
                        else:
                            ok += 1
                    except Exception as e:
                        errores += 1
                        err_list.append({
                            'fila': idx + 3,
                            'dni': dni,
                            'fecha': str(fecha),
                            'mensaje': str(e),
                        })
                else:
                    ok += 1  # dry-run: contar como OK

        # ── Actualizar BancoHoras STAFF ───────────────────────
        if not dry_run and banco_acumulado:
            self._actualizar_banco_horas(banco_acumulado, importacion)

        # ── Finalizar importación ─────────────────────────────
        if not dry_run:
            estado = 'COMPLETADO' if not err_list else 'COMPLETADO_CON_ERRORES'
            importacion.total_registros = ok + errores
            importacion.registros_ok = ok
            importacion.registros_error = errores
            importacion.registros_sin_match = sin_match
            importacion.estado = estado
            importacion.advertencias = advertencias[:200]  # limitar
            importacion.errores = err_list[:200]
            importacion.procesado_en = timezone.now()
            importacion.save()

        self.stdout.write(
            f"  ✓ Registros OK: {ok} | Errores: {errores} | Sin match BD: {sin_match} | "
            f"Advertencias: {len(advertencias)}"
        )

        return {
            'ok': ok,
            'errores': errores,
            'sin_match': sin_match,
            'advertencias': len(advertencias),
            'importacion': importacion if not dry_run else None,
        }

    # ── Banco de Horas STAFF ────────────────────────────────────

    def _actualizar_banco_horas(self, banco_acumulado: dict, importacion) -> None:
        from tareo.models import BancoHoras, MovimientoBancoHoras
        from personal.models import Personal

        for (personal_pk, anio, mes), datos in banco_acumulado.items():
            try:
                personal = Personal.objects.get(pk=personal_pk)
            except Personal.DoesNotExist:
                continue

            banco, _ = BancoHoras.objects.get_or_create(
                personal=personal,
                periodo_anio=anio,
                periodo_mes=mes,
                defaults={'saldo_horas': Decimal('0')}
            )

            total_he = datos['he_25'] + datos['he_35'] + datos['he_100']
            banco.he_25_acumuladas += datos['he_25']
            banco.he_35_acumuladas += datos['he_35']
            banco.he_100_acumuladas += datos['he_100']
            banco.saldo_horas = banco.total_acumulado - banco.he_compensadas
            banco.save()

            # Movimiento de acumulación por tasa
            for tasa, horas in [
                ('25', datos['he_25']),
                ('35', datos['he_35']),
                ('100', datos['he_100']),
            ]:
                if horas > 0:
                    MovimientoBancoHoras.objects.create(
                        banco=banco,
                        tipo='ACUMULACION',
                        tasa=tasa,
                        fecha=importacion.periodo_fin,
                        horas=horas,
                        descripcion=(
                            f"Importación tareo {importacion.periodo_inicio} "
                            f"→ {importacion.periodo_fin}"
                        ),
                    )

    # ── Importar Papeletas ──────────────────────────────────────

    def _importar_papeletas(self, xls: pd.ExcelFile, options, ctx,
                             importacion_reloj, dry_run) -> dict:
        from tareo.models import (TareoImportacion, RegistroPapeleta,
                                   RegistroTareo)

        hoja = options['hoja_papeletas']
        if hoja not in xls.sheet_names:
            self.stdout.write(self.style.WARNING(f"  ⚠ Hoja '{hoja}' no encontrada."))
            return {}

        self.stdout.write(f"\n▸ Procesando hoja '{hoja}'...")

        df = pd.read_excel(xls, sheet_name=hoja)

        # Verificar columnas mínimas
        for col in ['DNI', 'FechaInicio', 'FechaFin']:
            if col not in df.columns:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ Columna '{col}' no encontrada en {hoja}."))
                return {}

        # Si hay importación de Reloj la reutilizamos; si no, creamos una propia
        if importacion_reloj:
            imp = importacion_reloj
        else:
            # Detectar período desde las fechas de las papeletas
            fechas_validas = []
            for v in df['FechaInicio'].dropna():
                try:
                    fechas_validas.append(pd.to_datetime(v).date())
                except Exception:
                    pass
            p_ini = min(fechas_validas) if fechas_validas else datetime.date.today()
            p_fin = max(
                [pd.to_datetime(v).date() for v in df['FechaFin'].dropna()
                 if not pd.isna(v)],
                default=p_ini
            )
            imp = TareoImportacion(
                tipo='PAPELETAS',
                periodo_inicio=p_ini,
                periodo_fin=p_fin,
                archivo_nombre=options['archivo'],
                estado='PROCESANDO',
            )
            if not dry_run:
                imp.save()

        personal_map = ctx['personal_map']
        ok = errores = 0
        err_list = []

        for idx, row in df.iterrows():
            dni = limpiar_dni(row.get('DNI', ''))
            if not dni:
                continue

            try:
                f_ini = pd.to_datetime(row.get('FechaInicio')).date()
                f_fin = pd.to_datetime(row.get('FechaFin')).date()
            except Exception:
                err_list.append({
                    'fila': idx + 2,
                    'dni': dni,
                    'mensaje': "Fechas inválidas en papeleta."
                })
                errores += 1
                continue

            tipo_raw = str(row.get('TipoPermiso', '')).strip()
            iniciales = str(row.get('Iniciales', '')).strip()
            tipo = mapear_tipo_permiso(tipo_raw, iniciales)

            personal_obj = personal_map.get(dni)
            dias_habiles = max(1, (f_fin - f_ini).days + 1)

            pap_data = dict(
                importacion=imp if not dry_run else None,
                personal=personal_obj,
                dni=dni,
                nombre_archivo=str(row.get('Personal', '')).strip(),
                tipo_permiso=tipo,
                tipo_permiso_raw=tipo_raw,
                iniciales=iniciales,
                fecha_inicio=f_ini,
                fecha_fin=f_fin,
                detalle=str(row.get('Detalle', '')).strip() if not pd.isna(row.get('Detalle', '')) else '',
                dias_habiles=dias_habiles,
                area_trabajo=str(row.get('Area Trabajo', '')).strip(),
                cargo=str(row.get('Cargo', '')).strip(),
            )

            if not dry_run:
                try:
                    RegistroPapeleta.objects.create(**pap_data)
                    ok += 1

                    # Override en RegistroTareo, si existen registros del Reloj
                    if importacion_reloj:
                        self._aplicar_override_papeleta(
                            dni, f_ini, f_fin, tipo, importacion_reloj)

                except Exception as e:
                    errores += 1
                    err_list.append({
                        'fila': idx + 2,
                        'dni': dni,
                        'mensaje': str(e),
                    })
            else:
                ok += 1

        if not dry_run:
            if not importacion_reloj:
                imp.total_registros = ok + errores
                imp.registros_ok = ok
                imp.registros_error = errores
                imp.estado = 'COMPLETADO' if not err_list else 'COMPLETADO_CON_ERRORES'
                imp.errores = err_list[:100]
                imp.procesado_en = timezone.now()
                imp.save()

        self.stdout.write(
            f"  ✓ Papeletas OK: {ok} | Errores: {errores}")
        return {'ok': ok, 'errores': errores}

    def _aplicar_override_papeleta(self, dni: str, f_ini: datetime.date,
                                    f_fin: datetime.date, tipo_permiso: str,
                                    importacion) -> None:
        """
        Actualiza los RegistroTareo del rango con el código de la papeleta.
        La papeleta tiene mayor prioridad que la marcación del Reloj.
        """
        from tareo.models import RegistroTareo

        # Mapa de tipo_permiso_choice → codigo_dia
        codigo_map = {
            'COMPENSACION_HE':      'CHE',
            'BAJADAS':              'DL',
            'BAJADAS_ACUMULADAS':   'DLA',
            'VACACIONES':           'VAC',
            'DESCANSO_MEDICO':      'DM',
            'LICENCIA_FALLECIMIENTO':'LF',
            'LICENCIA_PATERNIDAD':  'LP',
            'LICENCIA_CON_GOCE':    'LCG',
            'LICENCIA_SIN_GOCE':    'LSG',
            'COMISION_TRABAJO':     'A',
            'COMPENSACION_FERIADO': 'CPF',
            'COMP_DIA_TRABAJO':     'CDT',
            'SUSPENSION':           'F',
            'OTRO':                 '',
        }
        codigo_papeleta = codigo_map.get(tipo_permiso, '')
        if not codigo_papeleta:
            return

        RegistroTareo.objects.filter(
            importacion=importacion,
            dni=dni,
            fecha__gte=f_ini,
            fecha__lte=f_fin,
        ).update(
            codigo_dia=codigo_papeleta,
            fuente_codigo='PAPELETA',
            # Override limpia HE (papeletas de permiso/DL no generan HE)
            he_25=Decimal('0'),
            he_35=Decimal('0'),
            he_100=Decimal('0'),
        )

    # ── Importar S10 ────────────────────────────────────────────

    def _importar_s10(self, xls: pd.ExcelFile, options, ctx, dry_run) -> dict:
        from tareo.models import TareoImportacion, RegistroS10

        hoja = options['hoja_s10']
        # Intentar también con 'DatosPorPeriodo'
        if hoja not in xls.sheet_names:
            if 'DatosPorPeriodo' in xls.sheet_names:
                hoja = 'DatosPorPeriodo'
            else:
                self.stdout.write(self.style.WARNING(f"  ⚠ Hoja S10 no encontrada."))
                return {}

        self.stdout.write(f"\n▸ Procesando hoja '{hoja}' (S10)...")

        df = pd.read_excel(xls, sheet_name=hoja)
        if 'DNI' not in df.columns:
            self.stdout.write(self.style.ERROR("  ✗ Columna 'DNI' no encontrada."))
            return {}

        # Detectar período desde fechas disponibles
        periodo = datetime.date.today().strftime('%m/%Y')

        imp = TareoImportacion(
            tipo='S10',
            periodo_inicio=datetime.date.today().replace(day=1),
            periodo_fin=datetime.date.today(),
            archivo_nombre=options['archivo'],
            estado='PROCESANDO',
            metadata={'hoja': hoja},
        )
        if not dry_run:
            imp.save()

        personal_map = ctx['personal_map']
        ok = errores = sin_match = 0

        for idx, row in df.iterrows():
            dni = limpiar_dni(row.get('DNI', ''))
            if not dni:
                continue

            personal_obj = personal_map.get(dni)
            if not personal_obj:
                sin_match += 1

            def safe(col):
                v = row.get(col)
                return v if not pd.isna(v) else None

            def safe_date(col):
                v = row.get(col)
                if pd.isna(v):
                    return None
                try:
                    return pd.to_datetime(v, dayfirst=True).date()
                except Exception:
                    return None

            def safe_str(col, default=''):
                v = row.get(col, default)
                return str(v).strip() if not pd.isna(v) else default

            data = dict(
                importacion=imp if not dry_run else None,
                personal=personal_obj,
                nro_doc=dni,
                codigo_s10=safe_str('Código'),
                apellidos_nombres=safe_str('Nombre'),
                categoria=safe_str('Categoría'),
                ocupacion=safe_str('Recurso equivalente') or safe_str('Ocupación'),
                condicion=safe_str('Condición'),
                periodo=periodo,
                fecha_ingreso=safe_date('Fecha Ingreso'),
                fecha_cese=safe_date('Fecha Cese'),
                en_tareo=bool(safe('EnTareo')),
                regimen_pension=safe_str('Régimen Pensión'),
                codigo_proyecto=safe_str('Código Proyecto Destino (Tareo autom.)'),
                datos_extra={},
            )

            if not dry_run:
                try:
                    RegistroS10.objects.create(**data)
                    ok += 1
                except Exception as e:
                    errores += 1

        if not dry_run:
            imp.total_registros = ok + errores
            imp.registros_ok = ok
            imp.registros_error = errores
            imp.registros_sin_match = sin_match
            imp.estado = 'COMPLETADO' if not errores else 'COMPLETADO_CON_ERRORES'
            imp.procesado_en = timezone.now()
            imp.save()

        self.stdout.write(
            f"  ✓ Registros S10 OK: {ok} | Errores: {errores} | Sin match: {sin_match}")
        return {'ok': ok, 'errores': errores, 'sin_match': sin_match}

    # ── Resumen final ───────────────────────────────────────────

    def _imprimir_resumen(self, resultados: dict) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("\n═══ Resumen Final ═══"))
        if 'reloj' in resultados and resultados['reloj']:
            r = resultados['reloj']
            self.stdout.write(
                f"  RELOJ     → OK: {r.get('ok', 0):>6} | "
                f"Errores: {r.get('errores', 0):>4} | "
                f"Sin match: {r.get('sin_match', 0):>4} | "
                f"Advertencias: {r.get('advertencias', 0):>4}"
            )
        if 'papeletas' in resultados and resultados['papeletas']:
            r = resultados['papeletas']
            self.stdout.write(
                f"  PAPELETAS → OK: {r.get('ok', 0):>6} | "
                f"Errores: {r.get('errores', 0):>4}"
            )
        if 's10' in resultados and resultados['s10']:
            r = resultados['s10']
            self.stdout.write(
                f"  S10       → OK: {r.get('ok', 0):>6} | "
                f"Errores: {r.get('errores', 0):>4} | "
                f"Sin match: {r.get('sin_match', 0):>4}"
            )
        self.stdout.write("")
