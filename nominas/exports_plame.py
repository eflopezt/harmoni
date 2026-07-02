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
import unicodedata
from decimal import Decimal


from .models import PeriodoNomina


def _nfc(s: str) -> str:
    """Normaliza a NFC para que las tildes (combining/NFD) no se pierdan al
    codificar el archivo a latin-1 para SUNAT. Idempotente para texto ya en NFC."""
    return unicodedata.normalize('NFC', s)


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

# Códigos de concepto PLAME — Tabla 22 SUNAT (Anexo 2, Tablas paramétricas)
# Fuente oficial: https://orientacion.sunat.gob.pe/sites/default/files/inline-files/
#                 Tabla%20N22%20Definici%C3%B3n%20Conceptos%20Plame_181124.pdf
#
# AUDIT 2026-05-26: muchos códigos previos estaban equivocados (ej. 'sueldo':'0100'
# pero 0100 no existe; '0121' lo asignamos a 3 conceptos cuando 0121 es solo "Jornal
# Básico"). Reescrito contra el PDF oficial de Tabla 22 (versión 18/11/2024).
# Mapeos con referencia de página entre paréntesis.
#
# Si el código exacto no es verificable, dejamos `None`: el caller debe filtrar
# y NO exportar esa línea — no inventamos códigos para SUNAT.
#
# IMPORTANTE: el formato actual de `generar_plame_remuneraciones()` NO es el PDT
# PLAME oficial — es un formato resumido posicional. Este dict queda como
# infraestructura para una eventual implementación del archivo plano PDT 601 real,
# que sí requiere registros por concepto con código de Tabla 22.
CONCEPTO_PLAME = {
    # ════════════════════════════════════════════════════════════
    # INGRESOS — Trabajador (rango 01xx)
    # ════════════════════════════════════════════════════════════
    'sueldo':              '0121',   # Remuneración o jornal básico (pág 3)
    'sueldo-basico':       '0121',   # idem
    'comisiones':          '0103',   # Comisiones o destajo — remuneración principal imprecisa (pág 1)
    'comisiones-eventual': '0104',   # Comisiones eventuales (no regulares) (pág 1)
    'he-25':               '0105',   # Trabajo en sobretiempo 25% (pág 1)
    'he-35':               '0106',   # Trabajo en sobretiempo 35% (pág 1)
    'he-100':              '0107',   # Trabajo en día feriado/descanso (pág 1) — 100% es coloquial
    'premio-ventas':       '0111',   # Premios por ventas / cumplimiento objetivos comerciales (pág 1)
    'vacaciones':          '0118',   # Remuneración vacacional (pág 3)
    'vacaciones-truncas':  '0114',   # Vacaciones truncas (pág 2)
    'rem-devengada':       '0119',   # Remuneraciones devengadas de períodos anteriores (pág 3)

    # ════════════════════════════════════════════════════════════
    # ASIGNACIONES — Trabajador (rango 02xx)
    # ════════════════════════════════════════════════════════════
    'asig-familiar':       '0201',   # Asignación familiar Ley 25129 (pág 4)
    'asig-educacion':      '0202',   # Asignación o bonificación por educación (pág 4)
    'asig-cumpleanos':     '0203',   # Asignación por cumpleaños (pág 4)
    'asig-matrimonio':     '0204',   # Asignación por matrimonio (pág 4)
    'asig-nacimiento':     '0205',   # Asignación por nacimiento de hijos (pág 5)
    'asig-fallecimiento':  '0206',   # Asignación por fallecimiento de familiares (pág 5)
    'asig-vacacional':     '0210',   # Asignación vacacional (adicional, por convenio) (pág 5)

    # ════════════════════════════════════════════════════════════
    # BONIFICACIONES — Trabajador (rango 03xx)
    # ════════════════════════════════════════════════════════════
    'bono-produccion':     '0303',   # Bonificación por producción/altura/turno (pág 6)
    'bono-riesgo-caja':    '0304',   # Bonificación por riesgo de caja (pág 6)
    'bono-antiguedad':     '0305',   # Bonificaciones por tiempo de servicios (pág 6)
    'bonificacion':        '0306',   # Bonificaciones regulares — genérico (pág 6)
    'bono-puntualidad':    '0306',   # Bonificación regular → cae en "Bonificaciones regulares"
    'bono-nocturno':       '0309',   # Bonificación por turno nocturno 20% (pág 6)

    # ════════════════════════════════════════════════════════════
    # GRATIFICACIONES (rango 04xx)
    # ════════════════════════════════════════════════════════════
    'gratificacion':       '0408',   # Gratificaciones Fiestas Patrias y Navidad (post 29351) (pág 8)
    'gratif':              '0408',   # alias
    'gratif-truncas':      '0407',   # Gratificaciones proporcionales/truncas Ley 29351 (pág 8)
    'gratif-extraord':     '0403',   # Gratificaciones extraordinarias por liberalidad (pág 8)
    # Bonificación Extraordinaria 9% Ley 29351 NO tiene código aislado en Tabla 22 —
    # se considera parte del concepto 0408 pero exenta de aportes. Marcar None y
    # documentar en el caller.
    'bon-ext-9':           None,     # ← no existe código separado en T22 (ver doc Ley 29351)
    'bonif-extraordinaria': None,    # idem

    # ════════════════════════════════════════════════════════════
    # INDEMNIZACIONES (rango 05xx)
    # ════════════════════════════════════════════════════════════
    'indem-despido':       '0501',   # Indemnización por despido injustificado (pág 9)
    'indem-vac-no-goz':    '0504',   # Indemnización por vacaciones no gozadas (pág 9)

    # ════════════════════════════════════════════════════════════
    # TRIBUTOS Y APORTES — Trabajador (rango 06xx)
    # ════════════════════════════════════════════════════════════
    'ir-5ta':              '0605',   # Renta 5ta categoría — retenciones (pág 27)
    'afp-seguro':          '0606',   # Prima de seguro AFP (pág 28)
    'onp':                 '0607',   # SNP — Sistema Nacional de Pensiones DL 19990 (pág 28)
    'afp-aporte':          '0608',   # SPP — Aportación obligatoria 10% (pág 28)
    'afp-aporte-voluntario': '0609', # SPP aportación voluntaria (pág 28)
    # Comisión por flujo AFP: la T22 no le asigna un código aislado del aporte
    # obligatorio. En el archivo PLAME va en el mismo campo del aporte.
    'afp-comision':        None,     # ← sin código separado (era 0606 incorrecto)

    # ════════════════════════════════════════════════════════════
    # DESCUENTOS — Trabajador (rango 07xx) [pág 26]
    # ════════════════════════════════════════════════════════════
    'descto-adelanto':     '0701',   # Adelantos
    'descto-prestamo':     '0701',   # Préstamo → mismo código que adelanto en T22
    'cuota-sindical':      '0702',   # Cuota sindical autorizada
    'retencion-judicial':  '0703',   # Descuento por mandato judicial
    'embargo-judicial':    '0703',   # idem
    'pension-alimenticia': '0703',   # idem (mandato judicial de alimentos)
    'descuento-interno':   '0706',   # Descuentos internos autorizados (no deducibles)
    'descto-tardanza':     '0704',   # Tardanzas
    'descto-falta':        '0705',   # Inasistencias / licencias sin goce
    'otros-descuentos':    '0706',   # Otros descuentos no deducibles de base imponible
    'descto-deducible':    '0707',   # Otros descuentos deducibles de base imponible

    # ════════════════════════════════════════════════════════════
    # CONCEPTOS VARIOS (rango 09xx) [pág 10-11]
    # ════════════════════════════════════════════════════════════
    'bono-productividad':  '0902',   # Bono de productividad — estímulo por resultados (pág 10)
    'bono-resultados':     '0902',   # idem (resuelve TODO previo — descripción T22 menciona "los resultados")
    'cts':                 '0904',   # Compensación por tiempo de servicios (pág 10)
    'cts-semestral':       '0904',   # idem
    'incentivo-cese':      '0906',   # Incentivo por cese del trabajador (pág 10)
    'utilidades':          '0911',   # Participación en utilidades post-declaración anual IR (pág 11)

    # ════════════════════════════════════════════════════════════
    # NO REMUNERATIVOS — no se exportan en archivo de remuneraciones
    # ════════════════════════════════════════════════════════════
    'movilidad':           None,     # Condición de trabajo (Inc. j Art. 19 D.Leg. 650)
    'refrigerio':          None,     # No alimentación principal (0914 si aplica)
    'viaticos-cdt':        None,     # Viáticos — condición de trabajo
    'otros-ingresos':      None,     # Categoría genérica — depende del caso específico
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
    28    | SCTR Salud empleador (0812)
    29    | SCTR Pension empleador (0813)

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
            str(reg.dias_falta),                                  # 8. Dias no laborados (faltas/subsidios; el descanso semanal es pagado, no se declara aquí)
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
            _monto(reg.aporte_sctr_salud or Decimal('0')),        # 28. SCTR Salud (0812)
            _monto(reg.aporte_sctr_pension or Decimal('0')),      # 29. SCTR Pension (0813)
        ]
        output.write(_nfc('|'.join(row)) + '\r\n')
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
        output.write(_nfc('|'.join(row)) + '\r\n')
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
        output.write(_nfc('|'.join(row)) + '\r\n')
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
