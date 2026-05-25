"""
Importar planilla legacy desde Spring (u otro sistema) a Harmoni ERP.

Cubre escenarios típicos de migración cuando un cliente viene con varios
años de data histórica. Para Sabores del Sur: 16 años de planillas en Spring
que necesitan migrar conservando los totales originales.

USO:
    # Dry-run (no escribe nada, solo valida)
    python manage.py importar_planilla_legacy archivo.xlsx --dry-run

    # Importar con commit a BD
    python manage.py importar_planilla_legacy archivo.xlsx

    # Solo un RUC específico
    python manage.py importar_planilla_legacy archivo.xlsx --empresa 1

    # Forzar columnas si el auto-detect falla
    python manage.py importar_planilla_legacy archivo.xlsx \\
        --col-dni "Documento" --col-anio "Año" --col-mes "Mes" \\
        --col-bruto "Total Bruto" --col-neto "Neto"

    # Tolerancia personalizada para cuadre vs totales originales (default: 1.00)
    python manage.py importar_planilla_legacy archivo.xlsx --tolerancia 5.00

FORMATO ESPERADO del Excel/CSV (auto-detect tolerante a nombres en español):
    DNI / Documento / Nro Documento
    Nombre / Apellidos y Nombres / Trabajador
    Año / Anio / Year
    Mes / Month
    Bruto / Total Ingresos / Total Bruto / Remuneración Bruta
    Neto / Total Neto / Neto a Pagar
    AFP / Aporte AFP (opcional)
    ONP / Aporte ONP (opcional)
    EsSalud / ESSALUD (opcional)
    Empresa / RUC / Razón Social (opcional, si no, usa --empresa o la default)

Cualquier columna extra es ignorada. Las celdas vacías se asumen 0.
"""
from __future__ import annotations

import os
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


# ─── Auto-detect de columnas (case-insensitive, español-friendly) ───────────
COLUMN_ALIASES = {
    "dni": [
        "dni", "documento", "nro_doc", "nro doc", "nro documento",
        "numero documento", "numero doc", "n° doc", "n°documento",
        "cedula", "cédula", "identificacion", "identificación",
    ],
    "nombre": [
        "nombre", "nombres", "apellidos y nombres", "apellido y nombre",
        "trabajador", "empleado", "colaborador", "full name",
    ],
    "anio": [
        "anio", "año", "year", "ano",
    ],
    "mes": [
        "mes", "month", "period_mes",
    ],
    "bruto": [
        "bruto", "total bruto", "total ingresos", "ingresos",
        "remuneracion bruta", "remuneración bruta", "sueldo bruto",
        "gross",
    ],
    "neto": [
        "neto", "total neto", "neto a pagar", "net pay",
        "pago neto",
    ],
    "afp": [
        "afp", "aporte afp", "descuento afp", "afp obligatorio",
    ],
    "onp": [
        "onp", "aporte onp", "descuento onp",
    ],
    "essalud": [
        "essalud", "es salud", "esSalud", "aporte essalud",
    ],
    "empresa": [
        "empresa", "ruc", "razon social", "razón social",
        "company", "company_id",
    ],
}


def _normaliza_columna(col_name: str) -> str:
    """Normaliza un nombre de columna: lowercase, sin tildes, sin espacios extra."""
    import unicodedata
    if not col_name:
        return ""
    s = str(col_name).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = " ".join(s.split())
    return s


def _detectar_columnas(df_columns) -> dict:
    """Devuelve un dict {nombre_canonico: nombre_real_en_df} con auto-detect."""
    mapping = {}
    normalizadas = {col: _normaliza_columna(col) for col in df_columns}
    for canon, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_norm = _normaliza_columna(alias)
            for original, norm in normalizadas.items():
                if norm == alias_norm:
                    mapping[canon] = original
                    break
            if canon in mapping:
                break
    return mapping


def _to_decimal(value) -> Decimal:
    """Convierte cualquier valor a Decimal de forma defensiva.

    Acepta:
      - Decimal, int, float -> directo
      - str con 'S/', 'S/.', 'PEN', comas de miles, espacios -> limpia y convierte
      - None, '', 'nan', 'none', '-' -> 0
      - Cualquier otro string sin numero -> 0 (silencioso)
    """
    if value is None:
        return Decimal("0")
    try:
        if isinstance(value, str):
            s = value.strip()
            # Quitar prefijos de moneda (orden importa: S/. antes que S/)
            for prefix in ("S/.", "S/", "PEN", "$"):
                if s.upper().startswith(prefix):
                    s = s[len(prefix):].strip()
                    break
            # Quitar comas de miles
            s = s.replace(",", "").strip()
            if not s or s.lower() in ("nan", "none", "-"):
                return Decimal("0")
            return Decimal(s)
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


class Command(BaseCommand):
    help = "Importa planillas históricas desde Excel/CSV (Spring u otro) a Harmoni."

    def add_arguments(self, parser):
        parser.add_argument(
            "archivo",
            help="Ruta al archivo Excel (.xlsx) o CSV con la data legacy.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo valida y reporta, sin escribir nada a la BD.",
        )
        parser.add_argument(
            "--empresa",
            type=int,
            default=None,
            help="ID de la Empresa a asociar. Si el archivo trae columna Empresa, "
                 "se prioriza esa por fila.",
        )
        parser.add_argument(
            "--tolerancia",
            type=float,
            default=1.00,
            help="Tolerancia en S/ para validar cuadre vs totales legacy "
                 "(default: 1.00).",
        )
        # Overrides manuales de columnas (si el auto-detect falla)
        for key in COLUMN_ALIASES.keys():
            parser.add_argument(
                f"--col-{key}",
                default=None,
                help=f"Nombre exacto de la columna '{key}' (si auto-detect falla).",
            )

    def handle(self, *args, **options):
        archivo = options["archivo"]
        dry_run = options["dry_run"]
        empresa_default_id = options["empresa"]
        tolerancia = Decimal(str(options["tolerancia"]))

        if not os.path.exists(archivo):
            raise CommandError(f"Archivo no encontrado: {archivo}")

        # Lazy import — pandas/openpyxl no deben ser hard deps del módulo
        try:
            import pandas as pd
        except ImportError:
            raise CommandError("pandas no está instalado. pip install pandas openpyxl")

        self.stdout.write(self.style.SUCCESS(
            f"\n=== Importación planilla legacy {'(DRY-RUN)' if dry_run else ''} ===\n"
        ))
        self.stdout.write(f"Archivo: {archivo}")
        if empresa_default_id:
            self.stdout.write(f"Empresa default: id={empresa_default_id}")
        self.stdout.write(f"Tolerancia cuadre: S/ {tolerancia}\n")

        # 1) Leer archivo
        try:
            if archivo.lower().endswith(".csv"):
                df = pd.read_csv(archivo, dtype=str, keep_default_na=False)
            else:
                df = pd.read_excel(archivo, dtype=str, keep_default_na=False)
        except Exception as exc:
            raise CommandError(f"Error leyendo archivo: {exc}")

        self.stdout.write(f"Filas leídas: {len(df)}")
        self.stdout.write(f"Columnas detectadas: {list(df.columns)}\n")

        # 2) Detectar columnas (con override manual si se especifica)
        col_map = _detectar_columnas(df.columns)
        for key in COLUMN_ALIASES.keys():
            override = options.get(f"col_{key}")
            if override:
                if override in df.columns:
                    col_map[key] = override
                else:
                    self.stderr.write(self.style.WARNING(
                        f"  ! --col-{key} '{override}' no se encontró en el archivo."
                    ))

        # 3) Validar columnas mínimas
        required = ["dni", "anio", "mes", "bruto", "neto"]
        faltantes = [r for r in required if r not in col_map]
        if faltantes:
            self.stderr.write(self.style.ERROR(
                f"\nColumnas obligatorias faltantes: {faltantes}\n"
                f"Detectadas: {col_map}\n"
                f"Usa --col-X para mapear manualmente o renombra las columnas."
            ))
            return

        self.stdout.write(self.style.SUCCESS("Mapeo de columnas:"))
        for k, v in col_map.items():
            self.stdout.write(f"  {k:10s} -> '{v}'")
        self.stdout.write("")

        # 4) Procesar filas
        from personal.models import Personal
        from empresas.models import Empresa
        from nominas.models import PeriodoNomina, RegistroNomina

        # Indexar Personal por DNI para lookup O(1)
        personal_by_dni = {
            (p.nro_doc or "").strip(): p
            for p in Personal.objects.all()
        }

        # Empresa default
        empresa_default = None
        if empresa_default_id:
            try:
                empresa_default = Empresa.objects.get(pk=empresa_default_id)
            except Empresa.DoesNotExist:
                raise CommandError(f"Empresa id={empresa_default_id} no existe.")

        # Indexar empresas por RUC para resolver columna Empresa del archivo
        empresas_by_ruc = {
            (e.ruc or "").strip(): e
            for e in Empresa.objects.filter(activa=True)
        }
        empresas_by_id = {e.pk: e for e in Empresa.objects.filter(activa=True)}

        stats = {
            "filas_procesadas": 0,
            "registros_creados": 0,
            "registros_actualizados": 0,
            "periodos_creados": set(),
            "dni_no_encontrados": [],
            "filas_con_error": [],
            "cuadre_ok": 0,
            "cuadre_warn": 0,
            "total_bruto_archivo": Decimal("0"),
            "total_neto_archivo": Decimal("0"),
            "total_bruto_harmoni": Decimal("0"),
            "total_neto_harmoni": Decimal("0"),
        }

        sid = transaction.savepoint() if not dry_run else None
        try:
            with transaction.atomic():
                for idx, row in df.iterrows():
                    stats["filas_procesadas"] += 1
                    dni = str(row.get(col_map["dni"], "")).strip()
                    if not dni:
                        stats["filas_con_error"].append(f"Fila {idx+2}: DNI vacío.")
                        continue

                    personal = personal_by_dni.get(dni)
                    if not personal:
                        stats["dni_no_encontrados"].append(dni)
                        continue

                    try:
                        anio = int(float(str(row[col_map["anio"]]).strip()))
                        mes  = int(float(str(row[col_map["mes"]]).strip()))
                    except (ValueError, TypeError):
                        stats["filas_con_error"].append(
                            f"Fila {idx+2} ({dni}): año/mes inválidos."
                        )
                        continue

                    if not (2000 <= anio <= 2030) or not (1 <= mes <= 12):
                        stats["filas_con_error"].append(
                            f"Fila {idx+2} ({dni}): año {anio} o mes {mes} fuera de rango."
                        )
                        continue

                    bruto = _to_decimal(row[col_map["bruto"]])
                    neto  = _to_decimal(row[col_map["neto"]])
                    afp   = _to_decimal(row.get(col_map.get("afp"))) if col_map.get("afp") else Decimal("0")
                    onp   = _to_decimal(row.get(col_map.get("onp"))) if col_map.get("onp") else Decimal("0")
                    ess   = _to_decimal(row.get(col_map.get("essalud"))) if col_map.get("essalud") else Decimal("0")

                    stats["total_bruto_archivo"] += bruto
                    stats["total_neto_archivo"]  += neto

                    # Resolver empresa de la fila
                    emp = empresa_default
                    if col_map.get("empresa"):
                        raw_emp = str(row[col_map["empresa"]]).strip()
                        if raw_emp:
                            # Intentar como RUC primero, luego como ID
                            if raw_emp in empresas_by_ruc:
                                emp = empresas_by_ruc[raw_emp]
                            else:
                                try:
                                    emp_id_int = int(raw_emp)
                                    emp = empresas_by_id.get(emp_id_int, emp)
                                except (ValueError, TypeError):
                                    pass

                    # Crear o actualizar el período (BORRADOR para no afectar la planilla activa)
                    descripcion = f"Migración Legacy {anio}-{mes:02d}"
                    if emp:
                        descripcion += f" — {emp.nombre_comercial or emp.razon_social}"

                    periodo, periodo_created = PeriodoNomina.objects.get_or_create(
                        anio=anio,
                        mes=mes,
                        tipo="REGULAR",
                        defaults={
                            "fecha_inicio": date(anio, mes, 1),
                            "fecha_fin": date(anio, mes, 28),  # Conservador para evitar errores feb
                            "descripcion": descripcion,
                            "estado": "CERRADO",  # Histórico, no editable
                        },
                    )
                    if periodo_created:
                        stats["periodos_creados"].add((anio, mes))

                    # Crear o actualizar el RegistroNomina
                    registro, reg_created = RegistroNomina.objects.update_or_create(
                        periodo=periodo,
                        personal=personal,
                        defaults={
                            "sueldo_base": bruto,  # mejor aproximación: bruto histórico
                            "total_ingresos": bruto,
                            "total_descuentos": bruto - neto,
                            "neto_a_pagar": neto,
                            "aporte_essalud": ess,
                            "grupo": personal.grupo_tareo or "",
                            "regimen_pension": personal.regimen_pension or "AFP",
                            "afp": personal.afp or "",
                            "estado": "CERRADO",
                        },
                    )

                    if reg_created:
                        stats["registros_creados"] += 1
                    else:
                        stats["registros_actualizados"] += 1

                    stats["total_bruto_harmoni"] += bruto
                    stats["total_neto_harmoni"]  += neto

                # Validar cuadre
                diff_bruto = abs(stats["total_bruto_archivo"] - stats["total_bruto_harmoni"])
                diff_neto  = abs(stats["total_neto_archivo"]  - stats["total_neto_harmoni"])
                if diff_bruto <= tolerancia and diff_neto <= tolerancia:
                    stats["cuadre_ok"] = 1
                else:
                    stats["cuadre_warn"] = 1

                # Rollback si dry-run
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.WARNING(
                        "\n[DRY-RUN] Rollback ejecutado — no se persistieron cambios.\n"
                    ))

        except Exception as exc:
            if sid:
                transaction.savepoint_rollback(sid)
            raise CommandError(f"Error procesando archivo: {exc}")

        # Reporte final
        self.stdout.write(self.style.SUCCESS("\n=== Resumen ==="))
        self.stdout.write(f"Filas procesadas:           {stats['filas_procesadas']:>6}")
        self.stdout.write(f"Registros creados:          {stats['registros_creados']:>6}")
        self.stdout.write(f"Registros actualizados:     {stats['registros_actualizados']:>6}")
        self.stdout.write(f"Períodos nuevos:            {len(stats['periodos_creados']):>6}")
        self.stdout.write("")
        self.stdout.write(f"Total bruto archivo:    S/ {stats['total_bruto_archivo']:>14,.2f}")
        self.stdout.write(f"Total bruto Harmoni:    S/ {stats['total_bruto_harmoni']:>14,.2f}")
        self.stdout.write(f"Total neto archivo:     S/ {stats['total_neto_archivo']:>14,.2f}")
        self.stdout.write(f"Total neto Harmoni:     S/ {stats['total_neto_harmoni']:>14,.2f}")
        diff_b = stats['total_bruto_archivo'] - stats['total_bruto_harmoni']
        diff_n = stats['total_neto_archivo'] - stats['total_neto_harmoni']
        self.stdout.write(f"Diferencia bruto:       S/ {diff_b:>14,.2f}")
        self.stdout.write(f"Diferencia neto:        S/ {diff_n:>14,.2f}")
        self.stdout.write("")

        if stats["cuadre_ok"]:
            self.stdout.write(self.style.SUCCESS(
                f"[OK] Cuadre OK (diferencias dentro de tolerancia S/ {tolerancia})."
            ))
        elif stats["cuadre_warn"]:
            self.stdout.write(self.style.WARNING(
                f"[!] Diferencia mayor que la tolerancia. Revisar el archivo origen."
            ))

        if stats["dni_no_encontrados"]:
            self.stdout.write(self.style.WARNING(
                f"\nDNIs no encontrados en Personal ({len(stats['dni_no_encontrados'])}):"
            ))
            for d in stats["dni_no_encontrados"][:20]:
                self.stdout.write(f"  - {d}")
            if len(stats["dni_no_encontrados"]) > 20:
                self.stdout.write(f"  ... y {len(stats['dni_no_encontrados']) - 20} más.")

        if stats["filas_con_error"]:
            self.stdout.write(self.style.ERROR(
                f"\nFilas con error ({len(stats['filas_con_error'])}):"
            ))
            for err in stats["filas_con_error"][:10]:
                self.stdout.write(f"  - {err}")
            if len(stats["filas_con_error"]) > 10:
                self.stdout.write(f"  ... y {len(stats['filas_con_error']) - 10} más.")

        self.stdout.write("")
