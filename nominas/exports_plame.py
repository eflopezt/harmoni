"""
PLAME / PDT 601 -- Exportacion de archivos planos para SUNAT.

Genera los archivos requeridos por el PDT Planilla Mensual de Pagos (PLAME):
- Archivo de Remuneraciones (0601): datos de remuneraciones por trabajador
- Archivo de Retenciones de 5ta Categoria
- Archivo de Prestadores de Servicios 4ta (si aplica)

Formato: campos delimitados por pipe (|), sin encabezado, codificacion ANSI.
Base legal: R.S. 183-2011/SUNAT y modificatorias.

UIT 2026: S/ 5,500  |  RMV 2025: S/ 1,130
"""
import io
from decimal import Decimal

from django.db.models import Sum

from .models import PeriodoNomina, RegistroNomina


# ── Mapeos SUNAT ─────────────────────────────────────────────────────

TIPO_DOC_SUNAT = {
    'DNI': '01',
    'CE': '04',
    'Pasaporte': '07',
}

TIPO_TRAB_SUNAT = {
    'Empleado': '01',
    'Obrero': '02',
}

REGIMEN_PENSION_SUNAT = {
    'AFP': '01',
    'ONP': '02',
    'SIN_PENSION': '00',
}

# Codigos AFP segun SUNAT
AFP_CODIGO_SUNAT = {
    'Habitat': '04',
    'Integra': '01',
    'Prima': '03',
    'Profuturo': '02',
}

MODALIDAD_CONTRATO_SUNAT = {
    'INDEFINIDO': '01',
    'PLAZO_FIJO': '02',
    'INICIO_ACTIVIDAD': '03',
    'NECESIDAD_MERCADO': '04',
    'RECONVERSION_EMPRESARIAL': '05',
    'OBRA_SERVICIO': '06',
    'DISCONTINUO': '07',
    'TEMPORADA': '08',
    'SUPLENCIA': '09',
    'EMERGENCIA': '10',
    'SNP': '20',
    'PRACTICANTE': '30',
    'OTRO': '99',
    '': '01',
}

CATEGORIA_SUNAT = {
    'NORMAL': '01',
    'CONFIANZA': '02',
    'DIRECCION': '03',
}

# Codigos de concepto PLAME (Tabla 22 SUNAT - conceptos remunerativos)
# Mapea codigos internos del sistema a codigos PLAME.
#
# Donde el código exacto no fue verificable, dejamos TODO con la nota
# 'verificar con Tabla 22 SUNAT'. No inventamos códigos: si no estamos
# seguros, no exportamos esa línea (el caller debe filtrar None).
CONCEPTO_PLAME = {
    # ── Alias legados (no remover, los usa generar_plame_remuneraciones) ──
    'sueldo':              '0100',   # Remuneracion basica (alias legado)
    'asig-familiar':       '0201',   # Asignacion familiar
    'he-25':               '0301',   # Horas extra 25%
    'he-35':               '0302',   # Horas extra 35%
    'he-100':              '0303',   # Horas extra 100%
    'bonificacion':        '0400',   # Bonificaciones (genérico)
    'gratif':              '0600',   # Gratificaciones Ley 27735 (alias)
    'bon-ext-9':           '0604',   # Bonificacion extraordinaria 9%
    'vacaciones':          '0800',   # Vacaciones
    'cts':                 '0900',   # CTS (alias)

    # ── Códigos internos seedeados (mapping completo) ──
    'sueldo-basico':       '0100',   # Remuneracion basica
    'bono-productividad':  '0121',   # Bonificación habitual - productividad
    'bono-puntualidad':    '0123',   # Bonificación habitual - puntualidad
    'comisiones':          '0121',   # Comisiones (rem. variable habitual)
    # TODO: verificar código PLAME exacto para 'bono-resultados' con Tabla 22 SUNAT
    'bono-resultados':     None,     # Bono por resultados — pendiente verificar
    'gratificacion':       '0600',   # Gratificación semestral
    'bonif-extraordinaria':'0604',   # Bonificación extraordinaria 9% Ley 29351
    'cts-semestral':       '0904',   # Depósito semestral CTS

    # Conceptos no remunerativos (no van en remuneraciones, pero referenciados)
    'movilidad':           None,     # No remunerativo
    'refrigerio':          None,     # No remunerativo
    'viaticos-cdt':        None,     # No remunerativo
    'otros-ingresos':      None,     # Categoría genérica — depende del caso

    # ── DESCUENTOS — pensión y renta ──
    'afp-aporte':          '0605',   # Aporte obligatorio AFP (en archivo de aportes)
    'afp-comision':        '0606',   # Comisión flujo AFP
    'afp-seguro':          '0607',   # Prima seguro AFP
    'onp':                 '0608',   # Aporte ONP
    'ir-5ta':              '0610',   # Retención IR 5ta categoría

    # ── DESCUENTOS — otros ──
    # Códigos según Tabla 22 SUNAT — sección descuentos.
    'descto-prestamo':     '0802',   # Adelantos y préstamos
    'descto-adelanto':     '0802',   # Adelantos al trabajador (mismo código)
    'descto-falta':        '0810',   # Descuento por faltas e inasistencias
    'cuota-sindical':      '0805',   # Cuota sindical (autorizada)
    'retencion-judicial':  '0807',   # Retenciones por mandato judicial
    'embargo-judicial':    '0809',   # Embargos judiciales / otros descuentos
    'otros-descuentos':    '0809',   # Otros descuentos al trabajador

    # ── APORTES EMPLEADOR ──
    'essalud':             '2001',   # EsSalud 9% empleador
    'sctr-pension':        '2009',   # SCTR pensión (empleador)
    'sctr-salud':          '2010',   # SCTR salud (empleador)
}


# ── Helpers ──────────────────────────────────────────────────────────

def _safe(value, default=''):
    """None -> string vacio."""
    if value is None:
        return default
    return str(value).strip()


def _monto(value, decimales=2):
    """Formatea monto decimal para PLAME (sin simbolo, con punto decimal)."""
    if not value:
        return '0.00'
    try:
        fmt = f'{{:.{decimales}f}}'
        return fmt.format(Decimal(str(value)))
    except Exception:
        return '0.00'


def _fecha_sunat(d):
    """Fecha en formato DD/MM/YYYY para SUNAT."""
    if not d:
        return ''
    if hasattr(d, 'strftime'):
        return d.strftime('%d/%m/%Y')
    return ''


def _separar_nombres(apellidos_nombres):
    """
    Separa 'APELLIDOS, NOMBRES' en (ap_paterno, ap_materno, nombres).
    Si no hay coma, intenta separar por espacios asumiendo
    que los primeros dos tokens son apellidos.
    """
    if ',' in apellidos_nombres:
        partes = apellidos_nombres.split(',', 1)
        apellidos = partes[0].strip()
        nombres = partes[1].strip() if len(partes) > 1 else ''
    else:
        # Asumir: AP_PATERNO AP_MATERNO NOMBRES...
        tokens = apellidos_nombres.strip().split()
        if len(tokens) >= 3:
            apellidos = ' '.join(tokens[:2])
            nombres = ' '.join(tokens[2:])
        elif len(tokens) == 2:
            apellidos = tokens[0]
            nombres = tokens[1]
        else:
            apellidos = apellidos_nombres
            nombres = ''

    # Separar apellidos en paterno y materno
    ap_tokens = apellidos.split(None, 1)
    ap_paterno = ap_tokens[0] if ap_tokens else apellidos
    ap_materno = ap_tokens[1] if len(ap_tokens) > 1 else ''

    return ap_paterno.upper(), ap_materno.upper(), nombres.upper()


# ══════════════════════════════════════════════════════════════════════
# ARCHIVO PRINCIPAL: REMUNERACIONES (0601)
# ══════════════════════════════════════════════════════════════════════

def generar_plame_remuneraciones(periodo: PeriodoNomina) -> tuple[str, int]:
    """
    Genera archivo plano de remuneraciones para PLAME (PDT 601).

    Cada linea contiene los datos de un trabajador con sus conceptos
    remunerativos del periodo. Formato pipe-delimited.

    Estructura por linea (registro tipo 06 - remuneraciones):
    Campo | Descripcion
    ------|---------------------------------------------------
    1     | Tipo de registro ('0601')
    2     | Tipo documento (01=DNI, 04=CE, 07=PAS)
    3     | Numero documento
    4     | Apellido paterno
    5     | Apellido materno
    6     | Nombres
    7     | Dias efectivamente laborados
    8     | Dias no laborados / subsidiados
    9     | Horas ordinarias
    10    | Remuneracion basica (0100)
    11    | Asignacion familiar (0201)
    12    | Horas extra 25% (0301)
    13    | Horas extra 35% (0302)
    14    | Horas extra 100% (0303)
    15    | Total remuneracion computable
    16    | Regimen pensionario (01=AFP, 02=ONP, 00=Sin)
    17    | CUSPP (solo AFP)
    18    | Codigo AFP SUNAT
    19    | Aporte obligatorio AFP / ONP
    20    | Aporte EsSalud empleador
    21    | IR 5ta categoria retenido
    22    | Total descuentos
    23    | Neto a pagar
    24    | Periodo tributario (YYYYMM)
    25    | Indicador de situacion (1=activo, 2=baja en periodo)
    26    | Categoria trabajador (01=normal, 02=confianza, 03=direccion)
    27    | Tipo trabajador (01=empleado, 02=obrero)

    Returns:
        Tuple (contenido_texto, numero_registros)
    """
    output = io.StringIO()
    periodo_str = f'{periodo.anio}{periodo.mes:02d}'

    registros = (
        periodo.registros
        .select_related('personal', 'personal__subarea', 'personal__subarea__area')
        .prefetch_related('lineas__concepto')
        .order_by('personal__apellidos_nombres')
    )

    count = 0
    for reg in registros:
        p = reg.personal

        # Separar nombre
        ap_paterno, ap_materno, nombres = _separar_nombres(p.apellidos_nombres)

        # Obtener montos de las lineas de nomina
        lineas_map = {l.concepto.codigo: l for l in reg.lineas.all()}

        def _linea_monto(codigo):
            l = lineas_map.get(codigo)
            return l.monto if l else Decimal('0')

        sueldo_prop = _linea_monto('sueldo')
        asig_fam = _linea_monto('asig-familiar')
        he_25 = _linea_monto('he-25')
        he_35 = _linea_monto('he-35')
        he_100 = _linea_monto('he-100')

        # Aportes pension
        aporte_afp = _linea_monto('afp-aporte')
        aporte_onp = _linea_monto('onp')
        comision_afp = _linea_monto('afp-comision')
        seguro_afp = _linea_monto('afp-seguro')

        # Totalizar aporte pension
        if reg.regimen_pension == 'AFP':
            total_pension = aporte_afp + comision_afp + seguro_afp
        elif reg.regimen_pension == 'ONP':
            total_pension = aporte_onp
        else:
            total_pension = Decimal('0')

        # IR 5ta
        ir_5ta = abs(_linea_monto('ir-5ta'))

        # EsSalud
        essalud = reg.aporte_essalud or Decimal('0')

        # Situacion: activo o baja en el periodo
        situacion = '1'  # Activo
        if p.fecha_cese and p.fecha_cese <= periodo.fecha_fin:
            if p.fecha_cese >= periodo.fecha_inicio:
                situacion = '2'  # Baja durante el periodo

        row = [
            '0601',                                               # 1. Tipo registro
            TIPO_DOC_SUNAT.get(p.tipo_doc, '01'),                # 2. Tipo doc
            _safe(p.nro_doc),                                     # 3. Nro doc
            ap_paterno[:40],                                      # 4. Ap paterno
            ap_materno[:40],                                      # 5. Ap materno
            nombres[:60],                                         # 6. Nombres
            str(reg.dias_trabajados),                             # 7. Dias laborados
            str(reg.dias_falta + reg.dias_descanso),              # 8. Dias no laborados
            str(int(reg.dias_trabajados * 8)),                    # 9. Horas ordinarias
            _monto(sueldo_prop or reg.sueldo_base),               # 10. Rem basica (0100)
            _monto(asig_fam),                                     # 11. Asig familiar (0201)
            _monto(he_25),                                        # 12. HE 25%
            _monto(he_35),                                        # 13. HE 35%
            _monto(he_100),                                       # 14. HE 100%
            _monto(reg.total_ingresos),                           # 15. Total rem computable
            REGIMEN_PENSION_SUNAT.get(reg.regimen_pension, '00'), # 16. Regimen pension
            _safe(p.cuspp) if reg.regimen_pension == 'AFP' else '',  # 17. CUSPP
            AFP_CODIGO_SUNAT.get(reg.afp, '') if reg.regimen_pension == 'AFP' else '',  # 18. Cod AFP
            _monto(total_pension),                                # 19. Aporte pension
            _monto(essalud),                                      # 20. EsSalud
            _monto(ir_5ta),                                       # 21. IR 5ta
            _monto(reg.total_descuentos),                         # 22. Total descuentos
            _monto(reg.neto_a_pagar),                             # 23. Neto
            periodo_str,                                          # 24. Periodo YYYYMM
            situacion,                                            # 25. Situacion
            CATEGORIA_SUNAT.get(getattr(p, 'categoria', 'NORMAL'), '01'),  # 26. Categoria
            TIPO_TRAB_SUNAT.get(getattr(p, 'tipo_trab', 'Empleado'), '01'),  # 27. Tipo trab
        ]
        output.write('|'.join(row) + '\r\n')
        count += 1

    return output.getvalue(), count


# ══════════════════════════════════════════════════════════════════════
# ARCHIVO DE RETENCIONES DE 5TA CATEGORIA
# ══════════════════════════════════════════════════════════════════════

def generar_plame_retenciones_5ta(periodo: PeriodoNomina) -> tuple[str, int]:
    """
    Genera archivo plano de retenciones de IR 5ta categoria.

    Solo incluye trabajadores con retencion > 0 en el periodo.

    Estructura por linea:
    Campo | Descripcion
    ------|---------------------------------------------------
    1     | Tipo registro ('0605')
    2     | Tipo documento
    3     | Numero documento
    4     | Remuneracion computable del mes
    5     | Monto retencion 5ta del mes
    6     | Periodo tributario (YYYYMM)
    """
    output = io.StringIO()
    periodo_str = f'{periodo.anio}{periodo.mes:02d}'

    registros = (
        periodo.registros
        .select_related('personal')
        .prefetch_related('lineas__concepto')
        .order_by('personal__apellidos_nombres')
    )

    count = 0
    for reg in registros:
        # Buscar linea de IR 5ta
        ir_5ta = Decimal('0')
        for linea in reg.lineas.all():
            if linea.concepto.formula == 'IR_5TA':
                ir_5ta = abs(linea.monto)
                break

        if ir_5ta <= 0:
            continue

        p = reg.personal
        row = [
            '0605',                                    # 1. Tipo registro
            TIPO_DOC_SUNAT.get(p.tipo_doc, '01'),     # 2. Tipo doc
            _safe(p.nro_doc),                          # 3. Nro doc
            _monto(reg.total_ingresos),                # 4. Rem computable
            _monto(ir_5ta),                            # 5. Retencion 5ta
            periodo_str,                               # 6. Periodo
        ]
        output.write('|'.join(row) + '\r\n')
        count += 1

    return output.getvalue(), count


# ══════════════════════════════════════════════════════════════════════
# ARCHIVO JORNADA LABORAL
# ══════════════════════════════════════════════════════════════════════

def generar_plame_jornada(periodo: PeriodoNomina) -> tuple[str, int]:
    """
    Genera archivo de jornada laboral para PLAME.
    Indica dias trabajados, subsidiados y horas por trabajador.

    Estructura por linea:
    Campo | Descripcion
    ------|---------------------------------------------------
    1     | Tipo registro ('0701')
    2     | Tipo documento
    3     | Numero documento
    4     | Dias laborados
    5     | Dias no laborados y no subsidiados
    6     | Dias subsidiados
    7     | Horas ordinarias jornada
    8     | Horas sobretiempo (HE)
    9     | Periodo tributario (YYYYMM)
    """
    output = io.StringIO()
    periodo_str = f'{periodo.anio}{periodo.mes:02d}'

    registros = (
        periodo.registros
        .select_related('personal')
        .order_by('personal__apellidos_nombres')
    )

    count = 0
    for reg in registros:
        p = reg.personal

        horas_he = (
            reg.horas_extra_25 +
            reg.horas_extra_35 +
            reg.horas_extra_100
        )

        row = [
            '0701',                                    # 1. Tipo registro
            TIPO_DOC_SUNAT.get(p.tipo_doc, '01'),     # 2. Tipo doc
            _safe(p.nro_doc),                          # 3. Nro doc
            str(reg.dias_trabajados),                  # 4. Dias laborados
            str(reg.dias_falta),                       # 5. Dias no lab no subsid
            '0',                                       # 6. Dias subsidiados
            str(int(reg.dias_trabajados * 8)),          # 7. Horas ordinarias
            _monto(horas_he),                          # 8. Horas sobretiempo
            periodo_str,                               # 9. Periodo
        ]
        output.write('|'.join(row) + '\r\n')
        count += 1

    return output.getvalue(), count


# ══════════════════════════════════════════════════════════════════════
# RESUMEN -- genera ZIP con todos los archivos PLAME
# ══════════════════════════════════════════════════════════════════════

def generar_plame_completo(periodo: PeriodoNomina) -> dict:
    """
    Genera todos los archivos PLAME del periodo.

    Returns:
        dict con claves:
            'remuneraciones': (contenido, count),
            'retenciones_5ta': (contenido, count),
            'jornada': (contenido, count),
            'periodo_str': 'YYYYMM',
            'total_registros': int,
    """
    rem_content, rem_count = generar_plame_remuneraciones(periodo)
    ret_content, ret_count = generar_plame_retenciones_5ta(periodo)
    jor_content, jor_count = generar_plame_jornada(periodo)

    return {
        'remuneraciones': (rem_content, rem_count),
        'retenciones_5ta': (ret_content, ret_count),
        'jornada': (jor_content, jor_count),
        'periodo_str': f'{periodo.anio}{periodo.mes:02d}',
        'total_registros': rem_count,
    }
