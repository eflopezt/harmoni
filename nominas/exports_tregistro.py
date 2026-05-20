"""
T-Registro -- Exportacion de datos de trabajadores para SUNAT.

Genera archivos planos para el registro de trabajadores en el
T-Registro (Registro de Informacion Laboral) de SUNAT.

Formatos:
- Alta de trabajadores (nuevos ingresos)
- Baja de trabajadores (ceses)
- Datos completos del trabajador (actualizacion)

Base legal: R.S. 210-2004/SUNAT y modificatorias.
"""
import io
from datetime import date
from decimal import Decimal

from personal.models import Personal


# ── Mapeos SUNAT T-Registro ──────────────────────────────────────────

TIPO_DOC_TREG = {
    'DNI': '01',
    'CE': '04',
    'Pasaporte': '07',
}

TIPO_TRAB_TREG = {
    'Empleado': '01',
    'Obrero': '02',
}

REGIMEN_PENSION_TREG = {
    'AFP': '01',
    'ONP': '02',
    'SIN_PENSION': '00',
}

AFP_CODIGO_TREG = {
    'Habitat': '04',
    'Integra': '01',
    'Prima': '03',
    'Profuturo': '02',
}

MODALIDAD_CONTRATO_TREG = {
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

SEXO_TREG = {
    'M': '1',
    'F': '2',
    '': '1',
}

CATEGORIA_TREG = {
    'NORMAL': '01',
    'CONFIANZA': '02',
    'DIRECCION': '03',
}

# Regimen laboral general
REGIMEN_LABORAL_TREG = '01'  # D.Leg. 728 Regimen General

# Nivel educativo por defecto
NIVEL_EDUCATIVO_TREG = '11'  # Superior completa (default)

# Ocupacion CIIU por defecto
OCUPACION_TREG = '9999'  # No especificada

SITUACION_ESPECIAL = '00'  # Ninguna


# ── Helpers ──────────────────────────────────────────────────────────

def _safe(value, default=''):
    if value is None:
        return default
    return str(value).strip()


def _monto(value):
    if not value:
        return '0.00'
    try:
        return f'{Decimal(str(value)):.2f}'
    except Exception:
        return '0.00'


def _fecha(d, fmt='%d/%m/%Y'):
    if not d or not hasattr(d, 'strftime'):
        return ''
    return d.strftime(fmt)


def _separar_nombres(apellidos_nombres):
    """
    Separa 'APELLIDOS, NOMBRES' en (ap_paterno, ap_materno, nombres).
    """
    if ',' in apellidos_nombres:
        partes = apellidos_nombres.split(',', 1)
        apellidos = partes[0].strip()
        nombres = partes[1].strip() if len(partes) > 1 else ''
    else:
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

    ap_tokens = apellidos.split(None, 1)
    ap_paterno = ap_tokens[0] if ap_tokens else apellidos
    ap_materno = ap_tokens[1] if len(ap_tokens) > 1 else ''

    return ap_paterno.upper(), ap_materno.upper(), nombres.upper()


# ══════════════════════════════════════════════════════════════════════
# T-REGISTRO ALTAS
# ══════════════════════════════════════════════════════════════════════

def generar_tregistro_altas(queryset=None, fecha_desde=None, fecha_hasta=None) -> tuple[str, int]:
    """
    Genera archivo T-Registro de altas de trabajadores.
    Formato pipe-delimitado para carga masiva en SUNAT.

    Args:
        queryset: QuerySet de Personal. Si es None, usa personal activo.
        fecha_desde: filtrar por fecha_alta >= fecha_desde
        fecha_hasta: filtrar por fecha_alta <= fecha_hasta

    Estructura por linea:
    Campo | Descripcion
    ------|---------------------------------------------------
    1     | Tipo registro ('TA')
    2     | Tipo documento empleador ('06' = RUC)
    3     | RUC empleador
    4     | Tipo documento trabajador
    5     | Numero documento trabajador
    6     | Apellido paterno
    7     | Apellido materno
    8     | Nombres
    9     | Sexo (1=M, 2=F)
    10    | Fecha nacimiento (DD/MM/YYYY)
    11    | Nacionalidad (604=Peruana por defecto)
    12    | Direccion domicilio
    13    | Telefono / Celular
    14    | Correo electronico
    15    | Tipo trabajador (01=Empleado, 02=Obrero)
    16    | Regimen laboral (01=General)
    17    | Categoria ocupacional
    18    | Modalidad contrato
    19    | Fecha inicio contrato (DD/MM/YYYY)
    20    | Fecha fin contrato (DD/MM/YYYY) - vacio si indefinido
    21    | Regimen pensionario
    22    | CUSPP (solo AFP)
    23    | Codigo AFP SUNAT
    24    | EPS (S/N)
    25    | Remuneracion mensual
    26    | Situacion especial (00=ninguna)
    27    | Asignacion familiar (S/N)
    28    | Periodo registro (YYYYMM)
    29    | Cargo

    Returns:
        Tuple (contenido_texto, numero_registros)
    """
    if queryset is None:
        queryset = Personal.objects.filter(estado='Activo')

    if fecha_desde:
        queryset = queryset.filter(fecha_alta__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha_alta__lte=fecha_hasta)

    queryset = queryset.select_related('subarea', 'subarea__area', 'empresa')
    queryset = queryset.order_by('apellidos_nombres')

    output = io.StringIO()
    periodo_str = date.today().strftime('%Y%m')

    # Intentar obtener RUC de la empresa
    ruc_empresa = ''

    count = 0
    for p in queryset:
        ap_paterno, ap_materno, nombres = _separar_nombres(p.apellidos_nombres)

        # RUC de empresa del trabajador
        ruc = ''
        if hasattr(p, 'empresa') and p.empresa:
            ruc = _safe(getattr(p.empresa, 'ruc', ''))
        if not ruc:
            ruc = ruc_empresa

        row = [
            'TA',                                                   # 1. Tipo registro
            '06',                                                   # 2. Tipo doc empleador (RUC)
            ruc,                                                    # 3. RUC empleador
            TIPO_DOC_TREG.get(p.tipo_doc, '01'),                   # 4. Tipo doc trabajador
            _safe(p.nro_doc),                                       # 5. Nro doc
            ap_paterno[:40],                                        # 6. Ap paterno
            ap_materno[:40],                                        # 7. Ap materno
            nombres[:60],                                           # 8. Nombres
            SEXO_TREG.get(p.sexo, '1'),                             # 9. Sexo
            _fecha(p.fecha_nacimiento),                             # 10. Fecha nacimiento
            '604',                                                  # 11. Nacionalidad (Peru)
            _safe(p.direccion)[:100] if p.direccion else '',        # 12. Direccion
            _safe(p.celular),                                       # 13. Telefono
            _safe(p.correo_corporativo or p.correo_personal),       # 14. Email
            TIPO_TRAB_TREG.get(p.tipo_trab, '01'),                 # 15. Tipo trabajador
            REGIMEN_LABORAL_TREG,                                   # 16. Regimen laboral
            CATEGORIA_TREG.get(getattr(p, 'categoria', 'NORMAL'), '01'),  # 17. Categoria
            MODALIDAD_CONTRATO_TREG.get(p.tipo_contrato or '', '01'),  # 18. Modalidad contrato
            _fecha(p.fecha_alta or p.fecha_inicio_contrato),        # 19. Fecha inicio
            _fecha(p.fecha_fin_contrato),                           # 20. Fecha fin contrato
            REGIMEN_PENSION_TREG.get(p.regimen_pension, '00'),      # 21. Regimen pension
            _safe(p.cuspp) if p.regimen_pension == 'AFP' else '',   # 22. CUSPP
            AFP_CODIGO_TREG.get(p.afp, '') if p.regimen_pension == 'AFP' else '',  # 23. Cod AFP
            'S' if getattr(p, 'tiene_eps', False) else 'N',        # 24. EPS
            _monto(p.sueldo_base),                                  # 25. Remuneracion
            SITUACION_ESPECIAL,                                     # 26. Situacion especial
            'S' if p.asignacion_familiar else 'N',                  # 27. Asig familiar
            periodo_str,                                            # 28. Periodo
            _safe(p.cargo)[:60],                                    # 29. Cargo
        ]
        output.write('|'.join(row) + '\r\n')
        count += 1

    return output.getvalue(), count


# ══════════════════════════════════════════════════════════════════════
# T-REGISTRO BAJAS
# ══════════════════════════════════════════════════════════════════════

# Mapeo motivo de cese Harmoni -> codigo SUNAT T-Registro
MOTIVO_BAJA_TREG = {
    'RENUNCIA': '01',
    'MUTUO_ACUERDO': '02',
    'JUBILACION': '03',
    'VENCIMIENTO': '04',
    'NO_RENOVACION': '04',
    'DESPIDO_CAUSA': '05',
    'CESE_COLECTIVO': '06',
    'LIQUIDACION': '07',
    'FALLECIMIENTO': '08',
    'INVALIDEZ': '09',
    'ABANDONO': '10',
    'OTRO': '99',
    '': '99',
}


def generar_tregistro_bajas(queryset=None, fecha_desde=None, fecha_hasta=None) -> tuple[str, int]:
    """
    Genera archivo T-Registro de bajas (ceses) de trabajadores.

    Args:
        queryset: QuerySet de Personal cesados.
        fecha_desde: filtrar por fecha_cese >= fecha_desde
        fecha_hasta: filtrar por fecha_cese <= fecha_hasta

    Estructura por linea:
    Campo | Descripcion
    ------|---------------------------------------------------
    1     | Tipo registro ('TB')
    2     | Tipo documento empleador ('06' = RUC)
    3     | RUC empleador
    4     | Tipo documento trabajador
    5     | Numero documento trabajador
    6     | Fecha de cese (DD/MM/YYYY)
    7     | Motivo de baja (codigo SUNAT)
    8     | Periodo registro (YYYYMM)

    Returns:
        Tuple (contenido_texto, numero_registros)
    """
    if queryset is None:
        queryset = Personal.objects.filter(estado='Cesado')

    if fecha_desde:
        queryset = queryset.filter(fecha_cese__gte=fecha_desde)
    if fecha_hasta:
        queryset = queryset.filter(fecha_cese__lte=fecha_hasta)

    queryset = queryset.select_related('empresa').order_by('apellidos_nombres')

    output = io.StringIO()
    periodo_str = date.today().strftime('%Y%m')

    count = 0
    for p in queryset:
        if not p.fecha_cese:
            continue

        ruc = ''
        if hasattr(p, 'empresa') and p.empresa:
            ruc = _safe(getattr(p.empresa, 'ruc', ''))

        row = [
            'TB',                                               # 1. Tipo registro
            '06',                                               # 2. Tipo doc empleador
            ruc,                                                # 3. RUC empleador
            TIPO_DOC_TREG.get(p.tipo_doc, '01'),               # 4. Tipo doc trabajador
            _safe(p.nro_doc),                                   # 5. Nro doc
            _fecha(p.fecha_cese),                               # 6. Fecha cese
            MOTIVO_BAJA_TREG.get(p.motivo_cese or '', '99'),   # 7. Motivo baja
            periodo_str,                                        # 8. Periodo
        ]
        output.write('|'.join(row) + '\r\n')
        count += 1

    return output.getvalue(), count


# ══════════════════════════════════════════════════════════════════════
# T-REGISTRO COMPLETO (para exportar desde periodo de nomina)
# ══════════════════════════════════════════════════════════════════════

def generar_tregistro_desde_periodo(periodo) -> tuple[str, int]:
    """
    Genera T-Registro de altas para todos los trabajadores
    incluidos en un periodo de nomina especifico.

    Util para generar el T-Registro alineado con la planilla del periodo.
    """

    personal_ids = (
        periodo.registros
        .values_list('personal_id', flat=True)
    )

    queryset = Personal.objects.filter(
        pk__in=personal_ids,
        estado='Activo',
    )

    return generar_tregistro_altas(queryset=queryset)
