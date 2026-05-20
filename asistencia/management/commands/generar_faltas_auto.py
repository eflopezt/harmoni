"""
Genera RegistroTareo con FA/DS automáticos para días sin marca.

Tras importar asistencia, los días sin marcación quedan "invisibles" en BD.
La vista matricial los muestra como FA/DS on-the-fly, pero el reporte Excel
de Faltas solo lee los registros físicos. Este comando los persiste.

Reglas (coinciden con calendario.py fallback):
  - Si tiene papeleta APROBADA cubriendo ese día → NO crear (papeleta gana).
  - Si es domingo y condición LOCAL/LIMA → crear DS (descanso semanal).
  - Si condición LIMA y día L-S → crear A (auto-presente, no marca biométrico).
  - Resto (FORANEO L-D, LOCAL L-S, LIMA fuera de rango) → crear FA.

No modifica registros existentes. Solo crea los faltantes.

Uso:
    python manage.py generar_faltas_auto --fecha-ini 2026-03-22 --fecha-fin 2026-04-21
    python manage.py generar_faltas_auto --fecha-ini 2026-03-22 --fecha-fin 2026-04-21 --dry-run
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from asistencia.models import (
    FeriadoCalendario, RegistroPapeleta,
    RegistroTareo, TareoImportacion,
)
from asistencia.services.papeletas_sync import _codigo_default
from personal.models import Personal


CERO = Decimal('0')


def _cond_norm(c):
    return (c or 'LOCAL').upper().replace('Á', 'A').replace('Ñ', 'N')


class Command(BaseCommand):
    help = 'Genera RegistroTareo FA/DS automáticos para días sin marca en un período.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha-ini', required=True)
        parser.add_argument('--fecha-fin', required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        fecha_ini = date.fromisoformat(opts['fecha_ini'])
        fecha_fin = date.fromisoformat(opts['fecha_fin'])
        dry = opts['dry_run']

        # Feriados del período
        feriados = set(
            FeriadoCalendario.objects.filter(
                fecha__gte=fecha_ini, fecha__lte=fecha_fin, activo=True
            ).values_list('fecha', flat=True)
        )

        # Personal que estuvo activo en el período (fecha_alta <= fin Y (fecha_cese >= ini OR null))
        personal_qs = Personal.objects.filter(
            fecha_alta__lte=fecha_fin,
        ).filter(
            # Sin fecha_cese o cese posterior al inicio
            **{}
        )
        from django.db.models import Q
        personal_qs = personal_qs.filter(
            Q(fecha_cese__isnull=True) | Q(fecha_cese__gte=fecha_ini)
        )
        self.stdout.write(f'Personal en período: {personal_qs.count()}')

        # Registros existentes por (personal_id, fecha)
        existentes = set(
            RegistroTareo.objects.filter(
                fecha__gte=fecha_ini, fecha__lte=fecha_fin,
            ).values_list('personal_id', 'fecha')
        )

        # Papeletas aprobadas del período indexadas por (personal_id, fecha)
        pap_days = set()
        paps = RegistroPapeleta.objects.filter(
            estado__in=['APROBADA', 'EJECUTADA'],
            fecha_fin__gte=fecha_ini, fecha_inicio__lte=fecha_fin,
        )
        for pa in paps:
            d = max(pa.fecha_inicio, fecha_ini)
            f = min(pa.fecha_fin, fecha_fin)
            while d <= f:
                pap_days.add((pa.personal_id, d))
                d += timedelta(days=1)

        # TareoImportacion para trazabilidad
        imp = None
        if not dry:
            imp = TareoImportacion.objects.create(
                archivo_nombre='generar_faltas_auto',
                tipo='RELOJ',
                periodo_inicio=fecha_ini,
                periodo_fin=fecha_fin,
                estado='PROCESANDO',
            )

        # Iterar
        a_crear = []
        stats = {'FA': 0, 'DS': 0, 'A_LIMA': 0, 'skip_papeleta': 0,
                 'skip_existente': 0, 'skip_fuera_rango': 0}

        total_dias = (fecha_fin - fecha_ini).days + 1
        for p in personal_qs.iterator():
            cond = _cond_norm(p.condicion)
            grupo = p.grupo_tareo or ('STAFF' if cond != 'FORANEO' else 'RCO')

            f = fecha_ini
            while f <= fecha_fin:
                # Fuera de rango del empleado (post-cese o pre-alta)
                if p.fecha_alta and f < p.fecha_alta:
                    stats['skip_fuera_rango'] += 1
                    f += timedelta(days=1)
                    continue
                if p.fecha_cese and f > p.fecha_cese:
                    stats['skip_fuera_rango'] += 1
                    f += timedelta(days=1)
                    continue

                if (p.id, f) in existentes:
                    stats['skip_existente'] += 1
                    f += timedelta(days=1)
                    continue

                if (p.id, f) in pap_days:
                    stats['skip_papeleta'] += 1
                    f += timedelta(days=1)
                    continue

                # Determinar código (aplica ReglaEspecialPersonal si hay)
                dow = f.weekday()  # 0=Lun ... 6=Dom
                es_fer = f in feriados
                codigo, fuente = _codigo_default(p, f, es_fer)
                stats[codigo] = stats.get(codigo, 0) + 1

                a_crear.append(RegistroTareo(
                    importacion=imp,
                    personal=p,
                    dni=p.nro_doc,
                    nombre_archivo=p.apellidos_nombres,
                    grupo=grupo,
                    condicion=p.condicion or 'LOCAL',
                    fecha=f,
                    dia_semana=dow,
                    es_feriado=es_fer,
                    codigo_dia=codigo,
                    fuente_codigo=fuente,
                    horas_marcadas=None,
                    horas_efectivas=CERO,
                    horas_normales=CERO,
                    he_25=CERO,
                    he_35=CERO,
                    he_100=CERO,
                    he_al_banco=(grupo == 'STAFF'),
                ))
                f += timedelta(days=1)

        # Resumen
        self.stdout.write(f'\n=== RESUMEN ===')
        for k, v in stats.items():
            self.stdout.write(f'  {k}: {v}')
        self.stdout.write(f'Total a crear: {len(a_crear)}')

        if dry:
            self.stdout.write(self.style.WARNING('DRY RUN - no se guardó.'))
            return

        with transaction.atomic():
            RegistroTareo.objects.bulk_create(a_crear, batch_size=500)
            if imp:
                imp.estado = 'COMPLETADO'
                imp.registros_ok = len(a_crear)
                imp.save()

        self.stdout.write(self.style.SUCCESS(f'\n✓ Creados {len(a_crear)} registros.'))
