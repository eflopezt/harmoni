"""
Importador de personal en 2 pasos: subir → PREVIEW con errores por fila → confirmar.

Patrón estándar de los HRIS líderes: nada se escribe en BD hasta que el
admin ve qué se va a crear/actualizar y qué filas tienen problemas.

El archivo subido se guarda en MEDIA_ROOT/imports_tmp/<token>.xlsx; el
preview y la confirmación re-parsean el MISMO archivo (consistencia).

Columnas soportadas (además de las históricas): SueldoBase, RegimenPension,
AFP, Banco, CuentaCCI — lo mínimo para que la primera planilla salga bien.
"""
import logging
import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

import pandas as pd
from django.conf import settings

logger = logging.getLogger(__name__)

TMP_DIR = 'imports_tmp'
TOKEN_RE = re.compile(r'^[0-9a-f]{32}$')

REGIMENES_PENSION = {'AFP', 'ONP', 'SIN_PENSION'}
AFPS = {'Habitat', 'Integra', 'Prima', 'Profuturo'}


def guardar_archivo_tmp(archivo) -> str:
    """Guarda el upload en MEDIA_ROOT/imports_tmp/<token>.xlsx → token."""
    token = uuid.uuid4().hex
    destino = Path(settings.MEDIA_ROOT) / TMP_DIR
    destino.mkdir(parents=True, exist_ok=True)
    with open(destino / f'{token}.xlsx', 'wb') as fh:
        for chunk in archivo.chunks():
            fh.write(chunk)
    return token


def ruta_tmp(token: str):
    """Path del archivo temporal si el token es válido y existe; si no, None."""
    if not TOKEN_RE.match(token or ''):
        return None
    p = Path(settings.MEDIA_ROOT) / TMP_DIR / f'{token}.xlsx'
    return p if p.exists() else None


def borrar_tmp(token: str):
    p = ruta_tmp(token)
    if p:
        try:
            p.unlink()
        except OSError:
            pass


def _celda(row, col, default=''):
    if col in row and pd.notna(row[col]):
        return str(row[col]).strip()
    return default


def parsear_excel_personal(path) -> dict:
    """
    Parsea y valida el Excel SIN tocar la BD.

    Returns: {'filas': [...], 'a_crear': n, 'a_actualizar': n,
              'con_error': n, 'con_warning': n, 'error_global': str|None}
    Cada fila: {'n', 'nro_doc', 'nombre', 'accion', 'datos', 'errores', 'warnings'}
    """
    from .models import Personal, SubArea

    try:
        df = pd.read_excel(
            path, sheet_name='Personal',
            dtype={'NroDoc': str, 'CodigoFotocheck': str, 'Celular': str,
                   'CuentaCCI': str, 'Ubigeo': str},
        )
    except ValueError:
        return {'filas': [], 'a_crear': 0, 'a_actualizar': 0, 'con_error': 0,
                'con_warning': 0,
                'error_global': 'El archivo no tiene una hoja llamada "Personal". '
                                'Descarga la plantilla y úsala como base.'}
    except Exception as e:
        return {'filas': [], 'a_crear': 0, 'a_actualizar': 0, 'con_error': 0,
                'con_warning': 0, 'error_global': f'No se pudo leer el Excel: {e}'}

    if not all(c in df.columns for c in ('NroDoc', 'ApellidosNombres')):
        return {'filas': [], 'a_crear': 0, 'a_actualizar': 0, 'con_error': 0,
                'con_warning': 0,
                'error_global': 'Faltan las columnas obligatorias NroDoc y ApellidosNombres.'}

    subareas = {s.nombre.strip().lower(): s for s in SubArea.objects.select_related('area')}
    existentes = set(Personal.objects.values_list('nro_doc', flat=True))

    filas = []
    vistos = {}
    for idx, row in df.iterrows():
        n_excel = idx + 2  # fila 1 = encabezado

        raw = row.get('NroDoc')
        if pd.isna(raw):
            continue
        if isinstance(raw, (int, float)):
            nro_doc = str(int(raw)).strip()
        else:
            nro_doc = str(raw).strip()
        if not nro_doc or nro_doc.lower() == 'nan':
            continue

        errores, warnings = [], []
        tipo_doc = _celda(row, 'TipoDoc', 'DNI') or 'DNI'
        nombre = _celda(row, 'ApellidosNombres')

        if not nombre:
            errores.append('ApellidosNombres vacío.')
        if tipo_doc.upper() == 'DNI' and not (nro_doc.isdigit() and len(nro_doc) == 8):
            errores.append(f'DNI inválido ("{nro_doc}") — deben ser 8 dígitos.')
        if nro_doc in vistos:
            errores.append(f'DNI repetido en el archivo (también en la fila {vistos[nro_doc]}).')
        vistos.setdefault(nro_doc, n_excel)

        datos = {
            'apellidos_nombres': nombre,
            'tipo_doc': tipo_doc,
            'codigo_fotocheck': _celda(row, 'CodigoFotocheck'),
            'cargo': _celda(row, 'Cargo'),
            'tipo_trab': _celda(row, 'TipoTrabajador', 'Empleado') or 'Empleado',
            'estado': _celda(row, 'Estado', 'Activo') or 'Activo',
            'sexo': _celda(row, 'Sexo'),
            'celular': _celda(row, 'Celular'),
            'correo_personal': _celda(row, 'CorreoPersonal'),
            'correo_corporativo': _celda(row, 'CorreoCorporativo'),
            'direccion': _celda(row, 'Direccion'),
            'ubigeo': _celda(row, 'Ubigeo'),
            'regimen_laboral': _celda(row, 'RegimenLaboral'),
            'regimen_turno': _celda(row, 'RegimenTurno'),
            'observaciones': _celda(row, 'Observaciones'),
        }

        # SubArea por nombre (warning si no existe — no bloquea)
        sub_nombre = _celda(row, 'SubArea')
        if sub_nombre:
            sub = subareas.get(sub_nombre.lower())
            if sub:
                datos['subarea'] = sub
            else:
                warnings.append(f'SubÁrea "{sub_nombre}" no existe — quedará sin asignar.')

        # Fechas
        for col, campo in (('FechaAlta', 'fecha_alta'), ('FechaCese', 'fecha_cese'),
                           ('FechaNacimiento', 'fecha_nacimiento')):
            if col in row and pd.notna(row[col]):
                try:
                    datos[campo] = pd.to_datetime(row[col]).date()
                except (ValueError, TypeError):
                    warnings.append(f'{col} inválida ("{row[col]}") — se ignora.')

        # ── Datos de planilla (nuevos) ──
        sueldo_raw = _celda(row, 'SueldoBase')
        if sueldo_raw:
            try:
                sueldo = Decimal(sueldo_raw.replace(',', ''))
                if sueldo < 0:
                    raise InvalidOperation
                datos['sueldo_base'] = sueldo
            except (InvalidOperation, ValueError):
                errores.append(f'SueldoBase inválido ("{sueldo_raw}").')

        regimen = _celda(row, 'RegimenPension').upper().replace(' ', '_')
        if regimen:
            if regimen in REGIMENES_PENSION:
                datos['regimen_pension'] = regimen
            else:
                errores.append(
                    f'RegimenPension "{regimen}" inválido (AFP / ONP / SIN_PENSION).')
        afp = _celda(row, 'AFP')
        if afp:
            match = next((a for a in AFPS if a.lower() == afp.lower()), None)
            if match:
                datos['afp'] = match
            else:
                warnings.append(f'AFP "{afp}" no reconocida (Habitat/Integra/Prima/Profuturo).')

        banco = _celda(row, 'Banco')
        if banco:
            datos['banco'] = banco
        cci = _celda(row, 'CuentaCCI').replace(' ', '').replace('-', '')
        if cci:
            if cci.isdigit() and len(cci) == 20:
                datos['cuenta_cci'] = cci
            else:
                errores.append(f'CuentaCCI inválida ("{cci}") — deben ser 20 dígitos.')

        if 'DiasLibresCorte2025' in row and pd.notna(row['DiasLibresCorte2025']):
            try:
                datos['dias_libres_corte_2025'] = Decimal(str(row['DiasLibresCorte2025']))
            except (InvalidOperation, ValueError):
                warnings.append('DiasLibresCorte2025 inválido — se ignora.')

        filas.append({
            'n': n_excel,
            'nro_doc': nro_doc,
            'nombre': nombre,
            'accion': 'ACTUALIZAR' if nro_doc in existentes else 'CREAR',
            'datos': datos,
            'errores': errores,
            'warnings': warnings,
        })

    return {
        'filas': filas,
        'a_crear': sum(1 for f in filas if not f['errores'] and f['accion'] == 'CREAR'),
        'a_actualizar': sum(1 for f in filas if not f['errores'] and f['accion'] == 'ACTUALIZAR'),
        'con_error': sum(1 for f in filas if f['errores']),
        'con_warning': sum(1 for f in filas if f['warnings'] and not f['errores']),
        'error_global': None,
    }


def aplicar_importacion(parse) -> dict:
    """Aplica las filas SIN errores (update_or_create por DNI)."""
    from .models import Personal

    creados = actualizados = 0
    for f in parse['filas']:
        if f['errores']:
            continue
        _, created = Personal.objects.update_or_create(
            nro_doc=f['nro_doc'], defaults=f['datos'],
        )
        if created:
            creados += 1
        else:
            actualizados += 1
    return {'creados': creados, 'actualizados': actualizados,
            'omitidos': parse['con_error']}
