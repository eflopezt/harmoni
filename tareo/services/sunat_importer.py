"""
Importador del reporte SUNAT T-Registro (TR5).

El archivo TR5 es un TXT con campos separados por '|' (pipe),
generado desde el portal SUNAT T-Registro.

Formato detectado en 20608830392_TRA_26022026_120939.txt:
  Columnas (27): NroDoc|Tipo|Número|ApePaterno|ApeMaterno|Nombres|
                 FecInicio|TipoTrabajador|RegimenLaboral|CatOcupacional|
                 Ocupacion|NivelEducativo|Discapacidad|Sindicalizado|
                 RegAcumulativo|Maxima|HorarioNocturno|SituacionEspecial|
                 Establecimiento|TipoContrato|TipoPago|Periodicidad|
                 EntidadFinanciera|NroCuenta|RemunBasica|Situacion|EnTareo

Importa a RegistroSUNAT y actualiza Personal si hay match por DNI.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

import pandas as pd

logger = logging.getLogger('personal.business')

# Columnas del TR5 (orden fijo del archivo SUNAT)
TR5_COLS = [
    'nro_doc_raw', 'tipo_doc', 'numero', 'apellido_paterno', 'apellido_materno',
    'nombres', 'fecha_ingreso', 'tipo_trabajador', 'regimen_laboral',
    'cat_ocupacional', 'ocupacion', 'nivel_educativo', 'discapacidad',
    'sindicalizado', 'reg_acumulativo', 'maxima', 'horario_nocturno',
    'situacion_especial', 'establecimiento', 'tipo_contrato', 'tipo_pago',
    'periodicidad', 'entidad_financiera', 'nro_cuenta', 'remun_basica',
    'situacion', 'en_tareo',
]


def importar_tr5(ruta_o_buffer, importacion, actualizar_personal: bool = False) -> dict:
    """
    Importa el archivo TR5 de SUNAT.

    ruta_o_buffer: path string o BytesIO del archivo TXT
    importacion: instancia de TareoImportacion
    actualizar_personal: si True, actualiza datos del Personal (código SAP, cargo, etc.)

    Retorna dict con contadores.
    """
    from personal.models import Personal
    from tareo.models import RegistroSUNAT

    errores = []
    advertencias = []
    creados = 0
    sin_match = 0

    # ── Leer archivo ──────────────────────────────────────────
    lineas = _leer_archivo(ruta_o_buffer, errores)
    if not lineas:
        importacion.estado = 'FALLIDO'
        importacion.errores = errores
        importacion.save()
        return {'creados': 0, 'errores': errores}

    # Detectar separador y estructura
    separador = _detectar_separador(lineas[0] if lineas else '')

    # Detectar si tiene encabezado
    primera_linea = lineas[0] if lineas else ''
    tiene_header = _es_encabezado(primera_linea)
    datos = lineas[1:] if tiene_header else lineas

    personal_map = {p.nro_doc: p for p in Personal.objects.all()}
    periodo = (f"{importacion.periodo_inicio.month:02d}/"
               f"{importacion.periodo_inicio.year}"
               if importacion.periodo_inicio else '')

    for i, linea in enumerate(datos):
        linea = linea.strip()
        if not linea:
            continue
        partes = linea.split(separador)

        # Rellenar con vacíos si faltan columnas
        while len(partes) < len(TR5_COLS):
            partes.append('')

        row = dict(zip(TR5_COLS, partes[:len(TR5_COLS)]))

        # Limpiar DNI
        nro_doc = _limpiar_dni(row.get('nro_doc_raw', '') or row.get('numero', ''))
        if not nro_doc:
            advertencias.append(f'Línea {i+2}: DNI vacío, se omite.')
            continue

        apellidos_nombres = (
            f"{row.get('apellido_paterno', '').strip()}, "
            f"{row.get('apellido_materno', '').strip()} "
            f"{row.get('nombres', '').strip()}"
        ).strip().strip(',').strip()

        fecha_ingreso = _parse_fecha(row.get('fecha_ingreso', ''))
        remun = _parse_decimal(row.get('remun_basica', ''))

        personal_obj = personal_map.get(nro_doc)
        if not personal_obj:
            sin_match += 1

        # Datos extra (todos los campos que no mapean 1:1)
        datos_extra = {
            'tipo_contrato': row.get('tipo_contrato', ''),
            'periodicidad': row.get('periodicidad', ''),
            'entidad_financiera': row.get('entidad_financiera', ''),
            'nivel_educativo': row.get('nivel_educativo', ''),
            'cat_ocupacional': row.get('cat_ocupacional', ''),
            'establecimiento': row.get('establecimiento', ''),
            'horario_nocturno': row.get('horario_nocturno', ''),
            'reg_acumulativo': row.get('reg_acumulativo', ''),
            'sindicalizado': row.get('sindicalizado', ''),
        }

        reg, created = RegistroSUNAT.objects.update_or_create(
            importacion=importacion,
            nro_doc=nro_doc,
            defaults={
                'personal': personal_obj,
                'tipo_doc': row.get('tipo_doc', ''),
                'apellidos_nombres': apellidos_nombres,
                'periodo': periodo,
                'fecha_ingreso': fecha_ingreso,
                'remuneracion_basica': remun,
                'tipo_trabajador_sunat': row.get('tipo_trabajador', ''),
                'datos_extra': datos_extra,
            }
        )
        if created:
            creados += 1

        # Actualizar Personal con datos del TR5
        if actualizar_personal and personal_obj:
            _actualizar_personal_desde_tr5(personal_obj, row, remun)

    importacion.total_registros = len(datos)
    importacion.registros_ok = creados
    importacion.registros_sin_match = sin_match
    importacion.estado = 'COMPLETADO_CON_ERRORES' if errores else 'COMPLETADO'
    importacion.errores = errores
    importacion.advertencias = advertencias
    importacion.save()

    logger.info(f'TR5 importado: {creados} registros, {sin_match} sin match.')
    return {'creados': creados, 'sin_match': sin_match,
            'errores': errores, 'advertencias': advertencias}


def _leer_archivo(ruta_o_buffer, errores: list) -> list[str]:
    encodings = ['utf-8', 'latin-1', 'cp1252', 'utf-8-sig']
    for enc in encodings:
        try:
            if hasattr(ruta_o_buffer, 'read'):
                ruta_o_buffer.seek(0)
                content = ruta_o_buffer.read().decode(enc)
            else:
                with open(ruta_o_buffer, 'r', encoding=enc) as f:
                    content = f.read()
            return content.splitlines()
        except (UnicodeDecodeError, Exception):
            continue
    errores.append('No se pudo leer el archivo: encoding desconocido.')
    return []


def _detectar_separador(linea: str) -> str:
    for sep in ['|', '\t', ';', ',']:
        if linea.count(sep) >= 5:
            return sep
    return '|'


def _es_encabezado(linea: str) -> bool:
    linea_lower = linea.lower()
    return any(k in linea_lower for k in ['nrodoc', 'dni', 'apellido', 'nombre', 'tipo doc'])


def _limpiar_dni(val: str) -> str:
    s = str(val).strip()
    s = re.sub(r'\.0$', '', s)
    s = re.sub(r'[^0-9A-Za-z]', '', s)
    return s if len(s) >= 7 else ''


def _parse_fecha(val: str):
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y'):
        try:
            return datetime.strptime(str(val).strip(), fmt).date()
        except (ValueError, TypeError):
            pass
    return None


def _parse_decimal(val: str) -> Decimal | None:
    try:
        return Decimal(str(val).strip().replace(',', '.'))
    except InvalidOperation:
        return None


def _actualizar_personal_desde_tr5(personal_obj, row: dict, remun) -> None:
    """Actualiza campos del Personal con info del TR5 (solo si están vacíos)."""
    changed = False
    if not personal_obj.regimen_laboral and row.get('regimen_laboral'):
        personal_obj.regimen_laboral = row['regimen_laboral']
        changed = True
    if remun and not personal_obj.sueldo_base:
        personal_obj.sueldo_base = remun
        changed = True
    if changed:
        personal_obj.save(update_fields=[
            f for f in ['regimen_laboral', 'sueldo_base'] if changed
        ])
