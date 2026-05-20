"""
Fix integral de horas para personal LOCAL/LIMA — ciclo 21-Feb → 21-Mar 2026.

PROBLEMA:
  _obtener_jornada() usaba Personal.jornada_horas (default=8) en vez de
  config.jornada_local_horas (8.5 lun-vie) / config.jornada_sabado_horas (5.5 sáb).
  Resultado: horas_normales cortas, HE infladas artificialmente, BancoHoras incorrecto.

EFECTOS DEL BUG:
  LOCAL Lun-Vie, marcó 8.5h  → n=8.0 he25=0.5   ← INCORRECTO
                               → n=8.5 he25=0.0   ← CORRECTO
  LOCAL Sábado,  marcó 5.5h  → n=5.0 he25=0.0   ← INCORRECTO (almuerzo mal descontado)
                               → n=5.5 he25=0.0   ← CORRECTO
  LOCAL Sábado,  marcó 6.5h  → n=5.0 he25=1.5   ← INCORRECTO
                               → n=5.5 he25=1.0   ← CORRECTO

USO:
  python manage.py fix_jornada_local_mar2026
  python manage.py fix_jornada_local_mar2026 --dry-run
  python manage.py fix_jornada_local_mar2026 --solo-banco   # solo recalcula BancoHoras
  python manage.py fix_jornada_local_mar2026 --fecha-ini 2026-02-21 --fecha-fin 2026-03-21
  python manage.py fix_jornada_local_mar2026 --condicion LOCAL   # solo LOCAL (no LIMA)
  python manage.py fix_jornada_local_mar2026 -v 2               # verbose: muestra cada fila
"""
import logging
from datetime import date
from decimal import Decimal
from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Sum

from asistencia.models import (
    RegistroTareo,
    TareoImportacion,
    BancoHoras,
    ConfiguracionSistema,
)

logger = logging.getLogger(__name__)

CERO = Decimal('0')
DOS  = Decimal('2')

# Jornada sábado LOCAL/LIMA hardcodeada (no existe jornada_sabado_horas en ConfiguracionSistema)
JORNADA_SABADO_LOCAL = Decimal('5.5')

CODIGOS_SIN_HE = {
    'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF',
    'LP', 'LSG', 'FA', 'TR', 'CDT', 'CPF', 'FER', 'ATM', 'SAI',
}

DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


# ─────────────────────────────────────────────────────────────────────────────
# Lógica de recálculo (replica processor._calcular_horas con jornada correcta)
# ─────────────────────────────────────────────────────────────────────────────

def _jornada_correcta(config, condicion: str, dia_semana: int) -> Decimal:
    """
    Jornada diaria correcta según condición y día de semana.
    Nota: ConfiguracionSistema solo tiene jornada_local_horas y jornada_foraneo_horas.
    El sábado LOCAL/LIMA = 5.5h está hardcodeado (media jornada, sin almuerzo).
    """
    cond_norm = (condicion or '').upper().replace('Á', 'A')
    if dia_semana == 6:                          # domingo
        if cond_norm == 'FORANEO':
            return Decimal(str(config.jornada_domingo_horas))  # 4h ciclo 21×7
        return CERO                              # LOCAL: descanso, todo al 100%
    if cond_norm == 'FORANEO':
        return Decimal(str(config.jornada_foraneo_horas))
    if dia_semana == 5:                          # sábado
        return JORNADA_SABADO_LOCAL              # 5.5h — sin descuento almuerzo
    return Decimal(str(config.jornada_local_horas))


def _recalcular_horas(
    codigo: str,
    horas_marcadas,
    jornada_h: Decimal,
    es_feriado: bool,
    dia_semana: int,
    he_bloqueado: bool = False,
) -> tuple:
    """
    Replica processor._calcular_horas() con los valores correctos de jornada.
    Devuelve (horas_efectivas, horas_normales, he_25, he_35, he_100).

    Caso especial — horas_marcadas=None (EXCEL/papeleta sin biométrico):
      - Código productivo (NOR, A, T…): jornada completa, sin HE
      - Código en CODIGOS_SIN_HE: cero (ausencia, permiso, etc.)
    """
    # SS (sin salida): presente sin marca de salida → paga jornada completa
    # En domingo LOCAL o feriado: SS también va al 100%
    if codigo == 'SS':
        j = jornada_h if jornada_h > CERO else Decimal('8.5')
        es_descanso = (dia_semana == 6)
        if (es_feriado or es_descanso) and (es_feriado or jornada_h == CERO):
            return j, CERO, CERO, CERO, j
        return j, j, CERO, CERO, CERO

    # Códigos que no generan horas
    if codigo in CODIGOS_SIN_HE:
        return CERO, CERO, CERO, CERO, CERO

    # Sin biométrico pero código productivo (fuente EXCEL/papeleta) → jornada completa
    if not horas_marcadas or horas_marcadas <= CERO:
        return jornada_h, jornada_h, CERO, CERO, CERO

    horas_m = Decimal(str(horas_marcadas))

    # Descuento almuerzo
    if jornada_h > Decimal('9'):
        # Foráneo: almuerzo incluido en jornada → sin descuento adicional
        horas_ef = horas_m
    elif jornada_h <= Decimal('6') or dia_semana == 5:
        # Jornada corta (sábado 5.5h, turno especial): sin break de almuerzo
        horas_ef = horas_m
    else:
        # LOCAL/LIMA lun-vie: descuenta 0.5h si marcó más de 5h
        almuerzo = Decimal('0.5') if horas_m > 5 else CERO
        horas_ef = max(CERO, horas_m - almuerzo)

    if horas_ef <= CERO:
        return CERO, CERO, CERO, CERO, CERO

    # Feriado laborado o descanso semanal
    if es_feriado or dia_semana == 6:
        if es_feriado or jornada_h == CERO:
            # Feriado (toda condición) o LOCAL domingo: TODAS al 100%
            return horas_ef, CERO, CERO, CERO, horas_ef
        else:
            # FORÁNEO domingo (4h jornada): normal hasta jornada, exceso HE 100%
            h_norm = min(horas_ef, jornada_h)
            he100 = max(CERO, horas_ef - jornada_h)
            return horas_ef, h_norm, CERO, CERO, he100

    # Día normal
    if horas_ef <= jornada_h:
        return horas_ef, horas_ef, CERO, CERO, CERO

    # Con horas extra
    if he_bloqueado:
        return jornada_h, jornada_h, CERO, CERO, CERO

    exceso = horas_ef - jornada_h
    he25   = min(exceso, DOS)
    he35   = max(CERO, exceso - DOS)
    return horas_ef, jornada_h, he25, he35, CERO


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Corrección integral de horas para personal LOCAL/LIMA '
        '(ciclo 21-Feb → 21-Mar 2026). '
        'Aplica jornada correcta: 8.5h lun-vie, 5.5h sábado. '
        'Recalcula RegistroTareo y BancoHoras.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra cambios sin escribir en BD.')
        parser.add_argument(
            '--fecha-ini', default='2026-02-21', metavar='YYYY-MM-DD',
            help='Inicio del ciclo (default: 2026-02-21).')
        parser.add_argument(
            '--fecha-fin', default='2026-03-21', metavar='YYYY-MM-DD',
            help='Fin del ciclo (default: 2026-03-21).')
        parser.add_argument(
            '--condicion', default='LOCAL,LIMA', metavar='LOCAL|LIMA|FORANEO',
            help='Condiciones separadas por coma (default: LOCAL,LIMA).')
        parser.add_argument(
            '--solo-banco', action='store_true',
            help='Omite la corrección de RegistroTareo; solo recalcula BancoHoras.')
        parser.add_argument(
            '--solo-tareo', action='store_true',
            help='Solo corrige RegistroTareo; no recalcula BancoHoras.')

    # ── helpers ──────────────────────────────────────────────────────────────

    def _header(self, texto):
        self.stdout.write(self.style.MIGRATE_HEADING(texto))

    def _ok(self, texto):
        self.stdout.write(self.style.SUCCESS(texto))

    def _warn(self, texto):
        self.stdout.write(self.style.WARNING(texto))

    def _err(self, texto):
        self.stderr.write(self.style.ERROR(texto))

    def _sep(self, char='─', n=72):
        self.stdout.write(char * n)

    # ── paso 1: corregir RegistroTareo ───────────────────────────────────────

    def _fix_registros(self, qs, config, dry_run, verbosity):
        """
        Recalcula horas para cada registro del queryset.
        Devuelve (actualizados, sin_cambio, errores, personal_ids_afectados).
        """
        actualizados = 0
        sin_cambio   = 0
        errores      = 0
        a_guardar    = []
        personal_afectados = set()

        for reg in qs.iterator(chunk_size=500):
            try:
                jornada_h = _jornada_correcta(config, reg.condicion, reg.dia_semana)

                h_ef, h_norm, he25, he35, he100 = _recalcular_horas(
                    codigo       = reg.codigo_dia or '',
                    horas_marcadas = reg.horas_marcadas,
                    jornada_h    = jornada_h,
                    es_feriado   = reg.es_feriado,
                    dia_semana   = reg.dia_semana,
                )

                changed = (
                    reg.horas_efectivas != h_ef   or
                    reg.horas_normales  != h_norm  or
                    reg.he_25           != he25    or
                    reg.he_35           != he35    or
                    reg.he_100          != he100
                )

                if not changed:
                    sin_cambio += 1
                    continue

                if verbosity >= 2:
                    nombre = (
                        reg.personal.apellidos_nombres if reg.personal
                        else reg.nombre_archivo or reg.dni
                    )
                    ds = DIAS[reg.dia_semana] if 0 <= reg.dia_semana <= 6 else '?'
                    self.stdout.write(
                        f'  {reg.fecha} {ds:<3} | {reg.codigo_dia or "---":<6} | '
                        f'{nombre[:32]:<32} | '
                        f'n {float(reg.horas_normales or 0):4.1f}→{float(h_norm):4.1f}  '
                        f'25% {float(reg.he_25 or 0):4.1f}→{float(he25):4.1f}  '
                        f'35% {float(reg.he_35 or 0):4.1f}→{float(he35):4.1f}  '
                        f'[j={float(jornada_h):.1f}h]'
                    )

                if not dry_run:
                    reg.horas_efectivas = h_ef
                    reg.horas_normales  = h_norm
                    reg.he_25           = he25
                    reg.he_35           = he35
                    reg.he_100          = he100
                    a_guardar.append(reg)

                actualizados += 1
                if reg.personal_id:
                    personal_afectados.add(reg.personal_id)

            except Exception as exc:
                errores += 1
                self._err(f'  ERROR reg={reg.pk} ({reg.fecha} {reg.dni}): {exc}')

        if not dry_run and a_guardar:
            with transaction.atomic():
                RegistroTareo.objects.bulk_update(
                    a_guardar,
                    ['horas_efectivas', 'horas_normales', 'he_25', 'he_35', 'he_100'],
                    batch_size=300,
                )

        return actualizados, sin_cambio, errores, personal_afectados

    # ── paso 2: recalcular BancoHoras ────────────────────────────────────────

    def _fix_banco_horas(self, fecha_ini, fecha_fin, condiciones, dry_run, verbosity):
        """
        Recalcula BancoHoras para las importaciones que abarcan el ciclo.
        Agrega HE desde RegistroTareo directamente, por importacion → (personal, mes).
        """
        # Importaciones que tienen registros en el rango de fechas
        importaciones = TareoImportacion.objects.filter(
            registros__fecha__gte=fecha_ini,
            registros__fecha__lte=fecha_fin,
            registros__condicion__in=condiciones,
            registros__grupo='STAFF',
        ).distinct().order_by('periodo_fin')

        if not importaciones.exists():
            self._warn('  No se encontraron importaciones con registros STAFF en el rango.')
            return 0, 0

        banco_creados    = 0
        banco_actualizados = 0

        for imp in importaciones:
            periodo_anio = imp.periodo_fin.year
            periodo_mes  = imp.periodo_fin.month

            if verbosity >= 1:
                self.stdout.write(
                    f'  Importación #{imp.pk} | periodo {imp.periodo_inicio} → '
                    f'{imp.periodo_fin} → BancoHoras {periodo_anio}/{periodo_mes:02d}'
                )

            # Sumar HE por persona desde RegistroTareo (ya corregido)
            resumen = (
                RegistroTareo.objects
                .filter(importacion=imp, grupo='STAFF', personal__isnull=False)
                .values('personal_id')
                .annotate(
                    sum_25=Sum('he_25'),
                    sum_35=Sum('he_35'),
                    sum_100=Sum('he_100'),
                )
            )

            # Compensaciones (papeletas CHE) — idéntico a processor
            try:
                from asistencia.models import PapeletaPermiso
                che_map = defaultdict(Decimal)
                paps = PapeletaPermiso.objects.filter(
                    importacion=imp,
                    tipo_permiso='COMPENSACION_HE',
                    estado='APROBADA',
                    personal__isnull=False,
                ).values('personal_id', 'dias_solicitados')
                for p in paps:
                    che_map[p['personal_id']] += Decimal(str(p['dias_solicitados'] or 0))
            except Exception:
                che_map = defaultdict(Decimal)

            filas = list(resumen)
            if not filas and verbosity >= 2:
                self.stdout.write('    Sin STAFF en esta importación — saltando.')
                continue

            to_update = []
            to_create = []

            for row in filas:
                pid     = row['personal_id']
                s25     = row['sum_25']  or CERO
                s35     = row['sum_35']  or CERO
                s100    = row['sum_100'] or CERO
                total   = s25 + s35 + s100
                comp    = che_map.get(pid, CERO)
                saldo   = total - comp

                try:
                    banco = BancoHoras.objects.get(
                        personal_id=pid,
                        periodo_anio=periodo_anio,
                        periodo_mes=periodo_mes,
                    )

                    old = (
                        banco.he_25_acumuladas, banco.he_35_acumuladas,
                        banco.he_100_acumuladas, banco.saldo_horas,
                    )
                    new = (s25, s35, s100, saldo)

                    if old != new:
                        if verbosity >= 2:
                            self.stdout.write(
                                f'    PID={pid} | '
                                f'25%: {float(old[0]):.2f}→{float(s25):.2f}  '
                                f'35%: {float(old[1]):.2f}→{float(s35):.2f}  '
                                f'100%: {float(old[2]):.2f}→{float(s100):.2f}  '
                                f'saldo: {float(old[3]):.2f}→{float(saldo):.2f}'
                            )
                        if not dry_run:
                            banco.he_25_acumuladas  = s25
                            banco.he_35_acumuladas  = s35
                            banco.he_100_acumuladas = s100
                            banco.he_compensadas    = comp
                            banco.saldo_horas       = saldo
                            to_update.append(banco)
                        banco_actualizados += 1

                except BancoHoras.DoesNotExist:
                    if verbosity >= 2:
                        self.stdout.write(
                            f'    PID={pid} | NUEVO | saldo={float(saldo):.2f}h')
                    if not dry_run:
                        to_create.append(BancoHoras(
                            personal_id=pid,
                            periodo_anio=periodo_anio,
                            periodo_mes=periodo_mes,
                            he_25_acumuladas=s25,
                            he_35_acumuladas=s35,
                            he_100_acumuladas=s100,
                            he_compensadas=comp,
                            saldo_horas=saldo,
                        ))
                    banco_creados += 1

            if not dry_run:
                with transaction.atomic():
                    if to_update:
                        BancoHoras.objects.bulk_update(
                            to_update,
                            ['he_25_acumuladas', 'he_35_acumuladas',
                             'he_100_acumuladas', 'he_compensadas', 'saldo_horas'],
                            batch_size=200,
                        )
                    if to_create:
                        BancoHoras.objects.bulk_create(to_create, batch_size=200)

        return banco_actualizados, banco_creados

    # ── main ─────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        dry_run    = options['dry_run']
        solo_banco = options['solo_banco']
        solo_tareo = options['solo_tareo']
        verbosity  = options['verbosity']

        try:
            fecha_ini = date.fromisoformat(options['fecha_ini'])
            fecha_fin = date.fromisoformat(options['fecha_fin'])
        except ValueError as e:
            raise CommandError(f'Fecha inválida: {e}')

        if fecha_ini > fecha_fin:
            raise CommandError('fecha-ini debe ser anterior a fecha-fin.')

        condiciones = [c.strip().upper() for c in options['condicion'].split(',')]
        validas = {'LOCAL', 'LIMA', 'FORANEO'}
        inv = set(condiciones) - validas
        if inv:
            raise CommandError(f'Condiciones inválidas: {inv}. Usar: {validas}')

        config = ConfiguracionSistema.get()
        prefix = '[DRY-RUN] ' if dry_run else ''

        self._header(f'\n{prefix}FIX JORNADA LOCAL — {fecha_ini} → {fecha_fin}')
        self.stdout.write(
            f'  Condiciones     : {", ".join(condiciones)}\n'
            f'  Jornada Lun-Vie : {config.jornada_local_horas}h\n'
            f'  Jornada Sábado  : {JORNADA_SABADO_LOCAL}h (hardcoded)\n'
            f'  Modo            : '
            f'{"SOLO BANCO" if solo_banco else "SOLO TAREO" if solo_tareo else "COMPLETO"}\n'
        )

        # ── Paso 1: RegistroTareo ─────────────────────────────────────────────
        t_act = t_sin = t_err = 0
        personal_afectados = set()

        if not solo_banco:
            self._sep()
            self._header('PASO 1 — Corregir RegistroTareo')

            qs = (
                RegistroTareo.objects
                .filter(
                    fecha__gte=fecha_ini,
                    fecha__lte=fecha_fin,
                    condicion__in=condiciones,
                )
                .select_related('personal')
                .order_by('fecha', 'condicion', 'dni')
            )

            total_qs = qs.count()
            self.stdout.write(f'  Registros a revisar: {total_qs:,}')

            if total_qs == 0:
                self._warn('  ⚠ Sin registros. Verificar fechas/condición.')
            else:
                t_act, t_sin, t_err, personal_afectados = self._fix_registros(
                    qs, config, dry_run, verbosity)

                simbolo = '✓' if not dry_run else '→'
                if t_act:
                    self._ok(f'  {simbolo} Con cambios    : {t_act:,}')
                else:
                    self.stdout.write(f'  {simbolo} Con cambios    : {t_act:,}')
                self.stdout.write(f'    Sin cambio     : {t_sin:,}')
                if t_err:
                    self._err(f'    Errores        : {t_err}')

        # ── Paso 2: BancoHoras ────────────────────────────────────────────────
        b_act = b_new = 0

        if not solo_tareo:
            self._sep()
            self._header('PASO 2 — Recalcular BancoHoras')

            b_act, b_new = self._fix_banco_horas(
                fecha_ini, fecha_fin, condiciones, dry_run, verbosity)

            simbolo = '✓' if not dry_run else '→'
            if b_act or b_new:
                self._ok(f'  {simbolo} Actualizados : {b_act:,}')
                if b_new:
                    self._ok(f'  {simbolo} Creados      : {b_new:,}')
            else:
                self.stdout.write('  Sin cambios en BancoHoras.')

        # ── Resumen final ─────────────────────────────────────────────────────
        self._sep('═')
        self._header(f'{prefix}RESUMEN FINAL')
        self.stdout.write(
            f'  RegistroTareo modificados : {t_act:,}\n'
            f'  RegistroTareo sin cambio  : {t_sin:,}\n'
            f'  Errores                   : {t_err}\n'
            f'  Personal únicos afectados : {len(personal_afectados):,}\n'
            f'  BancoHoras actualizados   : {b_act:,}\n'
            f'  BancoHoras creados        : {b_new:,}'
        )

        if dry_run:
            self._warn(
                '\n  ⚠ DRY-RUN activo — ningún dato fue modificado.\n'
                '  Ejecutar sin --dry-run para aplicar los cambios.')
        elif t_act or b_act or b_new:
            self._ok('\n  ✓ Corrección completada exitosamente.')
        else:
            self.stdout.write('\n  No hubo cambios que aplicar.')
