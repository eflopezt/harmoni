"""
seed_demo_historico.py
======================

Pobla 17 meses de historia (Ene 2025 → May 2026) sobre los trabajadores ya
creados por `seed_demo_gastronomia` para que el demo de Sabores del Sur muestre
KPIs con tendencia real (Centro de Comando, Asistencia matricial, Analytics,
Nóminas históricas, Pulse semanal).

Qué genera (idempotente — la 2da corrida no duplica):

  1. Periodos REGULAR (17): Ene 2025 → May 2026, todos CERRADO excepto
     el último que queda CALCULADO (espejo del estado real de la demo).
  2. Periodos GRATIFICACION (2): Jul 2025 y Dic 2025.
  3. Periodos CTS (2): May 2025 y Nov 2025.
  4. RegistroNomina + LineaNomina por trabajador-mes via
     `nominas.engine.calcular_registro` (cálculo real con AFP/ONP/IR 5ta).
     Incremento gradual del sueldo: el 1er mes = sueldo×0.85, último mes =
     sueldo actual; 5-10% recibe un aumento puntual extra en algún mes
     intermedio (mostrar "variación de sueldos").
  5. Rotación trimestral ~3-5%: marca algunos trabajadores como Cesado con
     fecha_cese histórica, y backdatea fecha_alta de otros para simular
     contrataciones a lo largo del año.
  6. Banco de horas: movimientos mensuales de HE 25/35 acumuladas para
     trabajadores STAFF (administración) — datos agregados, NO tareo diario.
  7. Pulse semanal: respuestas con tendencia ligeramente bajista en 1-2
     locales para que el Centro de Comando muestre una alerta.

Restricciones:
  - NO crea migraciones nuevas
  - NO modifica modelos
  - NO genera asistencia diaria (sería 800 trab × 17 meses × 30 días =
    ~408K filas — innecesario para los KPIs agregados)

Uso:
    python manage.py seed_demo_historico --dry-run
    python manage.py seed_demo_historico
    python manage.py seed_demo_historico --reset    # borra histórico previo

Para el reset_demo.sh del VPS — agregar DESPUÉS de seed_demo_gastronomia:

    docker exec $EXEC_ENV harmoni-demo-web python manage.py seed_demo_historico \\
      >> $LOG 2>&1 || echo "  ! seed_demo_historico fallo (no critico)" >> $LOG
"""
import calendar
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction


# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────────────────────────────────────

# Horizonte: 17 meses (Ene 2025 → May 2026)
MES_INICIO = (2025, 1)
MES_FIN    = (2026, 5)

# Periodos especiales (siempre dentro del horizonte)
PERIODOS_GRATIFICACION = [(2025, 7), (2025, 12)]
PERIODOS_CTS           = [(2025, 5), (2025, 11)]

# Incremento gradual de sueldo: 1er mes 85% del actual, último mes 100%.
SUELDO_FACTOR_INICIAL = Decimal('0.85')
SUELDO_FACTOR_FINAL   = Decimal('1.00')

# Aumento puntual intermedio para 5-10% de los trabajadores
PCT_AUMENTO_PUNTUAL = 0.08          # 8% de la plantilla recibe un bump extra
AUMENTO_PUNTUAL_RANGO = (0.05, 0.12) # +5%–12% sobre el sueldo escalado

# Rotación trimestral (3-5%)
PCT_CESES_POR_TRIMESTRE = 0.03
PCT_ALTAS_POR_TRIMESTRE = 0.04

# Banco de horas: solo STAFF (administración). HE/mes promedio.
HE_25_RANGO_STAFF = (4, 16)
HE_35_RANGO_STAFF = (0, 6)

# Pulse semanal
PCT_RESPUESTAS_PULSE = 0.55   # ~55% de la plantilla responde cada semana
LOCALES_BAJISTAS = 1          # cuántas empresas (locales) tienen tendencia
                              # bajista en pulse — alimenta alertas Centro Comando

SEMILLA = 42  # reproducibilidad


# ─────────────────────────────────────────────────────────────────────────────
# Helpers de fechas
# ─────────────────────────────────────────────────────────────────────────────

def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _iter_meses(inicio, fin):
    """Yield (anio, mes) desde inicio hasta fin inclusive."""
    a, m = inicio
    af, mf = fin
    while (a, m) <= (af, mf):
        yield (a, m)
        m += 1
        if m > 12:
            m = 1
            a += 1


def _meses_entre(inicio, fin):
    """Cantidad de meses inclusive entre inicio y fin."""
    return (fin[0] - inicio[0]) * 12 + (fin[1] - inicio[1]) + 1


# ─────────────────────────────────────────────────────────────────────────────
# Command
# ─────────────────────────────────────────────────────────────────────────────

class _DryRunRollback(Exception):
    """Marker para abortar la transacción en --dry-run."""


class Command(BaseCommand):
    help = (
        'Genera 17 meses de historia (2025-01 a 2026-05) para la demo de '
        'Sabores del Sur. Idempotente. Correr DESPUÉS de seed_demo_gastronomia.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe nada — solo muestra qué generaría.',
        )
        parser.add_argument(
            '--reset', action='store_true',
            help=(
                'Limpia PeriodoNomina/RegistroNomina/MovimientoBancoHoras/'
                'PulseSemanal del histórico antes de regenerar. Útil si el '
                'esquema cambió o quieres rehacer de cero.'
            ),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Entry point
    # ──────────────────────────────────────────────────────────────────────

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.reset   = options['reset']
        random.seed(SEMILLA)

        marker = ' [DRY-RUN]' if self.dry_run else ''
        self.stdout.write(
            f'\n=== Harmoni Demo — Seed Histórico 17 meses{marker} ===\n'
        )

        self.resumen = {
            'periodos_regular': 0,
            'periodos_gratif':  0,
            'periodos_cts':     0,
            'registros_nomina': 0,
            'ceses':            0,
            'altas_retro':      0,
            'mov_banco_horas':  0,
            'pulses':           0,
            'aumentos_puntuales': 0,
            'avisos':           [],
        }

        if self.dry_run:
            try:
                with transaction.atomic():
                    self._run()
                    raise _DryRunRollback()
            except _DryRunRollback:
                self.stdout.write(self.style.WARNING(
                    '\n  [DRY-RUN] Rollback — no se persistieron cambios.\n'
                ))
        else:
            # NO usamos un atomic global — los 17 meses se procesan uno por uno
            # con su propio atomic. Si un mes falla, no perdemos los anteriores.
            self._run()

        self._reporte_final()

    # ──────────────────────────────────────────────────────────────────────
    # Pipeline
    # ──────────────────────────────────────────────────────────────────────

    def _run(self):
        if self.reset:
            self._reset()

        # Pre-cargar los trabajadores del demo gastronomía
        trabajadores = self._cargar_trabajadores()
        if not trabajadores:
            self.stdout.write(self.style.ERROR(
                '  [!] No hay trabajadores en BD. Corre primero '
                '`seed_demo_gastronomia` (y/o `seed_demo_presentacion`).'
            ))
            return

        self.stdout.write(
            f'  [i] Trabajadores base: {len(trabajadores)} (DNIs '
            f'{trabajadores[0].nro_doc} -> {trabajadores[-1].nro_doc})'
        )

        # 1) Asignar fechas históricas de alta + ceses por trimestre
        self._distribuir_altas_retroactivas(trabajadores)
        self._distribuir_ceses_trimestrales(trabajadores)

        # 2) Aumentos puntuales en mes random
        aumentos_idx = self._planificar_aumentos_puntuales(trabajadores)

        # 3) Recorrer mes a mes y generar periodos + registros
        meses = list(_iter_meses(MES_INICIO, MES_FIN))
        total_meses = len(meses)
        for i, (anio, mes) in enumerate(meses):
            es_ultimo = (i == total_meses - 1)
            self._procesar_mes(
                anio, mes,
                trabajadores=trabajadores,
                aumentos_idx=aumentos_idx,
                idx_mes=i,
                total_meses=total_meses,
                es_ultimo=es_ultimo,
            )

        # 4) Banco de horas (agregado mensual para STAFF)
        self._generar_banco_horas(trabajadores)

        # 5) Pulse semanal con tendencia
        self._generar_pulses(trabajadores)

    # ──────────────────────────────────────────────────────────────────────
    # Carga de trabajadores
    # ──────────────────────────────────────────────────────────────────────

    def _cargar_trabajadores(self):
        from personal.models import Personal
        # Tomamos a todos los activos o cesados que existen — el histórico
        # los va a "reanimar" cambiando fecha_alta/fecha_cese según el mes.
        return list(
            Personal.objects
            .all()
            .order_by('nro_doc')
        )

    # ──────────────────────────────────────────────────────────────────────
    # Reset opcional
    # ──────────────────────────────────────────────────────────────────────

    def _reset(self):
        from nominas.models import PeriodoNomina, RegistroNomina, LineaNomina
        from asistencia.models import MovimientoBancoHoras, BancoHoras

        # Borrar periodos del horizonte (RegistroNomina/LineaNomina caen por CASCADE)
        for (a, m) in _iter_meses(MES_INICIO, MES_FIN):
            PeriodoNomina.objects.filter(anio=a, mes=m).delete()
        # Borrar BH del horizonte
        MovimientoBancoHoras.objects.filter(
            banco__periodo_anio__gte=MES_INICIO[0],
        ).delete()
        BancoHoras.objects.filter(
            periodo_anio__gte=MES_INICIO[0],
        ).delete()

        # Borrar pulses del horizonte
        try:
            from encuestas.models import PulseSemanal
            PulseSemanal.objects.filter(
                anio__gte=MES_INICIO[0],
                anio__lte=MES_FIN[0],
            ).delete()
        except Exception:
            pass

        self.stdout.write(self.style.WARNING(
            '  [reset] Histórico borrado (periodos, registros, banco horas, pulses).'
        ))

    # ──────────────────────────────────────────────────────────────────────
    # Altas retroactivas
    # ──────────────────────────────────────────────────────────────────────

    def _distribuir_altas_retroactivas(self, trabajadores):
        """
        Para que el dashboard muestre 'altas' a lo largo del 2025, backdateamos
        la fecha_alta de un subconjunto a una fecha dentro del horizonte. La
        2da corrida es no-op porque ya quedó dentro del rango.
        """
        meses = list(_iter_meses(MES_INICIO, MES_FIN))
        # ~PCT_ALTAS_POR_TRIMESTRE × 4 trimestres × 1.25 (margen)
        cuota = int(len(trabajadores) * PCT_ALTAS_POR_TRIMESTRE * 4 * 1.25)
        cuota = min(cuota, len(trabajadores) // 3)

        candidatos = [t for t in trabajadores if t.fecha_alta]
        random.shuffle(candidatos)
        elegidos = candidatos[:cuota]

        altas = 0
        for t in elegidos:
            # Solo si su fecha_alta es anterior al horizonte (lo movemos hacia
            # adentro). Si ya está dentro, lo dejamos como está.
            if t.fecha_alta and t.fecha_alta < date(*MES_INICIO, 1):
                anio, mes = random.choice(meses[:14])  # cualquier mes salvo
                                                       # los 3 últimos
                dia = random.randint(1, min(28, _last_day(anio, mes)))
                t.fecha_alta = date(anio, mes, dia)
                if not self.dry_run:
                    t.save(update_fields=['fecha_alta'])
                altas += 1
        self.resumen['altas_retro'] = altas
        if altas:
            self.stdout.write(f'  [+] Altas retroactivas distribuidas: {altas}')

    # ──────────────────────────────────────────────────────────────────────
    # Ceses trimestrales
    # ──────────────────────────────────────────────────────────────────────

    def _distribuir_ceses_trimestrales(self, trabajadores):
        """
        Selecciona ~3% por trimestre (max 5%) y marca fecha_cese + estado=Cesado.
        Idempotente: si ya tiene cese dentro del horizonte, lo respeta.
        """
        # Trimestres dentro del horizonte
        trimestres = [
            (2025, 3), (2025, 6), (2025, 9), (2025, 12),
            (2026, 3),
        ]
        cuota_trim = max(1, int(len(trabajadores) * PCT_CESES_POR_TRIMESTRE))

        # Trabajadores ya cesados (de cualquier seed previo) cuentan como dotación
        ya_cesados = {t.pk for t in trabajadores if t.estado == 'Cesado'}
        elegibles = [t for t in trabajadores if t.pk not in ya_cesados]
        random.shuffle(elegibles)

        ceses = 0
        idx = 0
        for (anio, mes) in trimestres:
            if idx >= len(elegibles):
                break
            for _ in range(cuota_trim):
                if idx >= len(elegibles):
                    break
                t = elegibles[idx]
                idx += 1
                dia = random.randint(1, min(28, _last_day(anio, mes)))
                fecha_cese = date(anio, mes, dia)
                # Si su fecha_alta es posterior, ajustamos: no puede cesarse
                # antes de ingresar. Saltamos.
                if t.fecha_alta and t.fecha_alta >= fecha_cese:
                    continue
                t.fecha_cese = fecha_cese
                t.estado = 'Cesado'
                if not t.motivo_cese:
                    t.motivo_cese = random.choice([
                        'RENUNCIA', 'VENCIMIENTO', 'MUTUO_ACUERDO',
                        'TERMINO_CONTRATO',
                    ])
                if not self.dry_run:
                    t.save(update_fields=['fecha_cese', 'estado', 'motivo_cese'])
                ceses += 1
        self.resumen['ceses'] = ceses
        if ceses:
            self.stdout.write(f'  [+] Ceses trimestrales: {ceses}')

    # ──────────────────────────────────────────────────────────────────────
    # Aumentos puntuales (variación de sueldos)
    # ──────────────────────────────────────────────────────────────────────

    def _planificar_aumentos_puntuales(self, trabajadores):
        """
        Devuelve dict {trabajador.pk: (mes_idx, factor)} — para algunos % de la
        plantilla, en algún mes intermedio aplicamos un bump extra al sueldo
        escalado de ese mes (y todos los siguientes).
        """
        total_meses = _meses_entre(MES_INICIO, MES_FIN)
        n = max(1, int(len(trabajadores) * PCT_AUMENTO_PUNTUAL))
        pool = list(trabajadores)
        random.shuffle(pool)
        elegidos = pool[:n]

        result = {}
        for t in elegidos:
            mes_idx = random.randint(2, max(2, total_meses - 3))
            f_min, f_max = AUMENTO_PUNTUAL_RANGO
            factor_extra = Decimal(str(round(random.uniform(f_min, f_max), 4)))
            result[t.pk] = (mes_idx, factor_extra)

        self.resumen['aumentos_puntuales'] = len(result)
        return result

    # ──────────────────────────────────────────────────────────────────────
    # Procesar un mes
    # ──────────────────────────────────────────────────────────────────────

    def _procesar_mes(self, anio, mes, *, trabajadores, aumentos_idx,
                       idx_mes, total_meses, es_ultimo):
        from nominas.models import PeriodoNomina, RegistroNomina, LineaNomina
        from nominas.models import ConceptoRemunerativo
        from nominas.engine import calcular_registro, calcular_gratificacion, calcular_cts

        # Factor de escala lineal entre 0.85 → 1.00
        if total_meses == 1:
            factor_base = SUELDO_FACTOR_FINAL
        else:
            rango = SUELDO_FACTOR_FINAL - SUELDO_FACTOR_INICIAL
            factor_base = SUELDO_FACTOR_INICIAL + (rango * Decimal(idx_mes) / Decimal(total_meses - 1))

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, _last_day(anio, mes))
        fecha_pago = fecha_fin  # día último del mes (planilla cerrada)

        # ── REGULAR ──────────────────────────────────────────────────────
        estado_periodo = 'CALCULADO' if es_ultimo else 'CERRADO'
        with transaction.atomic():
            periodo_reg, created = PeriodoNomina.objects.get_or_create(
                tipo='REGULAR', anio=anio, mes=mes,
                defaults={
                    'descripcion': f'Planilla {self._mes_nombre(mes)} {anio}',
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                    'fecha_pago': fecha_pago,
                    'estado': estado_periodo,
                },
            )
            if not created:
                # Refrescamos estado y fechas por si cambió la lógica
                periodo_reg.estado = estado_periodo
                periodo_reg.fecha_inicio = fecha_inicio
                periodo_reg.fecha_fin = fecha_fin
                periodo_reg.fecha_pago = fecha_pago
                periodo_reg.save(update_fields=['estado', 'fecha_inicio',
                                                'fecha_fin', 'fecha_pago'])
            self.resumen['periodos_regular'] += 1

            # Activos en este mes específico
            activos = self._activos_en_mes(trabajadores, anio, mes)
            if not activos:
                return

            # IMPORTANTE: el engine usa `conceptos_activos.get(codigo=...)`
            # internamente → tiene que ser un queryset, no una lista.
            conceptos = (
                ConceptoRemunerativo.objects.filter(activo=True)
                .order_by('tipo', 'orden')
            )

            registros_mes = 0
            total_bruto = Decimal('0')
            total_desc  = Decimal('0')
            total_neto  = Decimal('0')
            total_costo = Decimal('0')

            for t in activos:
                sueldo_efectivo = self._sueldo_en_mes(
                    t, factor_base, idx_mes, aumentos_idx
                )
                # Crear/actualizar registro
                registro, _ = RegistroNomina.objects.update_or_create(
                    periodo=periodo_reg, personal=t,
                    defaults={
                        'sueldo_base':         sueldo_efectivo,
                        'regimen_pension':     t.regimen_pension or 'AFP',
                        'afp':                 t.afp or '',
                        'grupo':               t.grupo_tareo or '',
                        'asignacion_familiar': bool(getattr(t, 'asignacion_familiar', False)),
                        'dias_trabajados':     30,
                    },
                )
                try:
                    resultado = calcular_registro(registro, conceptos)
                except Exception as exc:
                    self.resumen['avisos'].append(
                        f'  - {t.nro_doc} {anio}-{mes:02d}: {exc.__class__.__name__}'
                    )
                    continue

                # Reemplazar líneas (bulk para velocidad)
                registro.lineas.all().delete()
                LineaNomina.objects.bulk_create([
                    LineaNomina(
                        registro=registro,
                        concepto=l['concepto'],
                        base_calculo=l['base_calculo'],
                        porcentaje_aplicado=l['porcentaje_aplicado'],
                        monto=l['monto'],
                        observacion=l['observacion'],
                    )
                    for l in resultado['lineas']
                ])

                registro.total_ingresos      = resultado['total_ingresos']
                registro.total_descuentos    = resultado['total_descuentos']
                registro.neto_a_pagar        = resultado['neto_a_pagar']
                registro.aporte_essalud      = resultado['aporte_essalud']
                registro.costo_total_empresa = resultado['costo_total_empresa']
                registro.estado = 'APROBADO' if not es_ultimo else 'CALCULADO'
                registro.save()

                total_bruto += resultado['total_ingresos']
                total_desc  += resultado['total_descuentos']
                total_neto  += resultado['neto_a_pagar']
                total_costo += resultado['costo_total_empresa']
                registros_mes += 1

            periodo_reg.total_trabajadores  = registros_mes
            periodo_reg.total_bruto         = total_bruto
            periodo_reg.total_descuentos    = total_desc
            periodo_reg.total_neto          = total_neto
            periodo_reg.total_costo_empresa = total_costo
            periodo_reg.save()
            self.resumen['registros_nomina'] += registros_mes

        # ── GRATIFICACION ────────────────────────────────────────────────
        if (anio, mes) in PERIODOS_GRATIFICACION:
            with transaction.atomic():
                self._generar_periodo_especial(
                    tipo='GRATIFICACION', anio=anio, mes=mes,
                    trabajadores=trabajadores,
                    factor_base=factor_base,
                    idx_mes=idx_mes,
                    aumentos_idx=aumentos_idx,
                    desc_prefix='Gratificación',
                    estado='CERRADO',
                )

        # ── CTS ──────────────────────────────────────────────────────────
        if (anio, mes) in PERIODOS_CTS:
            with transaction.atomic():
                self._generar_periodo_especial(
                    tipo='CTS', anio=anio, mes=mes,
                    trabajadores=trabajadores,
                    factor_base=factor_base,
                    idx_mes=idx_mes,
                    aumentos_idx=aumentos_idx,
                    desc_prefix='CTS',
                    estado='CERRADO',
                )

        self.stdout.write(
            f'  [{anio}-{mes:02d}] REG · {self.resumen["registros_nomina"]:>5} reg acum · '
            f'factor sueldo {factor_base:.3f}'
        )

    def _generar_periodo_especial(self, *, tipo, anio, mes, trabajadores,
                                   factor_base, idx_mes, aumentos_idx,
                                   desc_prefix, estado):
        from nominas.models import PeriodoNomina, RegistroNomina, LineaNomina
        from nominas.models import ConceptoRemunerativo
        from nominas.engine import calcular_gratificacion, calcular_cts

        fecha_inicio = date(anio, mes, 1)
        fecha_fin = date(anio, mes, _last_day(anio, mes))

        periodo, created = PeriodoNomina.objects.get_or_create(
            tipo=tipo, anio=anio, mes=mes,
            defaults={
                'descripcion': f'{desc_prefix} {self._mes_nombre(mes)} {anio}',
                'fecha_inicio': fecha_inicio,
                'fecha_fin': fecha_fin,
                'fecha_pago': fecha_fin,
                'estado': estado,
            },
        )
        if tipo == 'GRATIFICACION':
            self.resumen['periodos_gratif'] += 1
        else:
            self.resumen['periodos_cts'] += 1

        activos = self._activos_en_mes(trabajadores, anio, mes)
        if not activos:
            return

        # IMPORTANTE: el engine usa `.get(codigo=...)` → queryset, no lista
        conceptos = (
            ConceptoRemunerativo.objects.filter(activo=True)
            .order_by('tipo', 'orden')
        )
        calculador = calcular_gratificacion if tipo == 'GRATIFICACION' else calcular_cts

        total_bruto = Decimal('0')
        total_desc  = Decimal('0')
        total_neto  = Decimal('0')
        total_costo = Decimal('0')
        registros_mes = 0

        for t in activos:
            sueldo_efectivo = self._sueldo_en_mes(
                t, factor_base, idx_mes, aumentos_idx
            )
            registro, _ = RegistroNomina.objects.update_or_create(
                periodo=periodo, personal=t,
                defaults={
                    'sueldo_base':         sueldo_efectivo,
                    'regimen_pension':     t.regimen_pension or 'AFP',
                    'afp':                 t.afp or '',
                    'grupo':               t.grupo_tareo or '',
                    'asignacion_familiar': bool(getattr(t, 'asignacion_familiar', False)),
                    'dias_trabajados':     6,  # semestre completo (proxy de meses)
                },
            )
            try:
                resultado = calculador(registro, conceptos)
            except Exception as exc:
                self.resumen['avisos'].append(
                    f'  - {tipo} {t.nro_doc} {anio}-{mes:02d}: {exc.__class__.__name__}'
                )
                continue

            registro.lineas.all().delete()
            LineaNomina.objects.bulk_create([
                LineaNomina(
                    registro=registro,
                    concepto=l['concepto'],
                    base_calculo=l['base_calculo'],
                    porcentaje_aplicado=l['porcentaje_aplicado'],
                    monto=l['monto'],
                    observacion=l['observacion'],
                )
                for l in resultado['lineas']
            ])
            registro.total_ingresos      = resultado['total_ingresos']
            registro.total_descuentos    = resultado['total_descuentos']
            registro.neto_a_pagar        = resultado['neto_a_pagar']
            registro.aporte_essalud      = resultado['aporte_essalud']
            registro.costo_total_empresa = resultado['costo_total_empresa']
            registro.estado = 'APROBADO'
            registro.save()

            total_bruto += resultado['total_ingresos']
            total_desc  += resultado['total_descuentos']
            total_neto  += resultado['neto_a_pagar']
            total_costo += resultado['costo_total_empresa']
            registros_mes += 1

        periodo.total_trabajadores  = registros_mes
        periodo.total_bruto         = total_bruto
        periodo.total_descuentos    = total_desc
        periodo.total_neto          = total_neto
        periodo.total_costo_empresa = total_costo
        periodo.save()
        self.resumen['registros_nomina'] += registros_mes

    # ──────────────────────────────────────────────────────────────────────
    # Helpers cálculo
    # ──────────────────────────────────────────────────────────────────────

    def _activos_en_mes(self, trabajadores, anio, mes):
        """Trabajadores que están dentro de [fecha_alta, fecha_cese] del mes."""
        primer_dia = date(anio, mes, 1)
        ultimo_dia = date(anio, mes, _last_day(anio, mes))
        out = []
        for t in trabajadores:
            if t.fecha_alta and t.fecha_alta > ultimo_dia:
                continue  # aún no ingresa
            if t.fecha_cese and t.fecha_cese < primer_dia:
                continue  # ya se fue antes
            out.append(t)
        return out

    def _sueldo_en_mes(self, trabajador, factor_base, idx_mes, aumentos_idx):
        sueldo_actual = Decimal(trabajador.sueldo_base or 0)
        if sueldo_actual <= 0:
            return Decimal('1130.00')  # RMV fallback
        sueldo = (sueldo_actual * factor_base).quantize(Decimal('0.01'))

        # Aumento puntual a partir del mes elegido
        aumento = aumentos_idx.get(trabajador.pk)
        if aumento:
            mes_bump, factor_extra = aumento
            if idx_mes >= mes_bump:
                sueldo = (sueldo * (Decimal('1') + factor_extra)).quantize(Decimal('0.01'))
        return sueldo

    def _mes_nombre(self, mes):
        MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        return MESES[mes] if 1 <= mes <= 12 else str(mes)

    # ──────────────────────────────────────────────────────────────────────
    # Banco de Horas (STAFF, agregado mensual)
    # ──────────────────────────────────────────────────────────────────────

    def _generar_banco_horas(self, trabajadores):
        try:
            from asistencia.models import BancoHoras, MovimientoBancoHoras
        except ImportError:
            self.resumen['avisos'].append('  - BancoHoras no disponible')
            return

        staff = [t for t in trabajadores if (t.grupo_tareo or '') == 'STAFF']
        if not staff:
            return

        movs_creados = 0
        for t in staff:
            for (anio, mes) in _iter_meses(MES_INICIO, MES_FIN):
                # Solo si estaba activo en el mes
                if t.fecha_alta and t.fecha_alta > date(anio, mes, _last_day(anio, mes)):
                    continue
                if t.fecha_cese and t.fecha_cese < date(anio, mes, 1):
                    continue

                he25 = Decimal(str(random.randint(*HE_25_RANGO_STAFF)))
                he35 = Decimal(str(random.randint(*HE_35_RANGO_STAFF)))
                if he25 == 0 and he35 == 0:
                    continue

                banco, _ = BancoHoras.objects.get_or_create(
                    personal=t, periodo_anio=anio, periodo_mes=mes,
                    defaults={
                        'he_25_acumuladas': he25,
                        'he_35_acumuladas': he35,
                        'saldo_horas':      he25 + he35,
                    },
                )
                # Asegurar valores aún si ya existía
                banco.he_25_acumuladas = he25
                banco.he_35_acumuladas = he35
                banco.saldo_horas = (
                    banco.he_25_acumuladas + banco.he_35_acumuladas + banco.he_100_acumuladas
                    - banco.he_compensadas
                )
                banco.save(update_fields=[
                    'he_25_acumuladas', 'he_35_acumuladas', 'saldo_horas'
                ])

                fecha_mov = date(anio, mes, min(15, _last_day(anio, mes)))

                # Crear movimientos solo si no existen aún (idempotente por
                # combinación banco+fecha+tipo+tasa)
                if he25 > 0 and not MovimientoBancoHoras.objects.filter(
                    banco=banco, fecha=fecha_mov, tipo='ACUMULACION', tasa='25'
                ).exists():
                    MovimientoBancoHoras.objects.create(
                        banco=banco, tipo='ACUMULACION', tasa='25',
                        fecha=fecha_mov, horas=he25,
                        descripcion='HE 25% acumuladas (carga histórica demo)',
                    )
                    movs_creados += 1
                if he35 > 0 and not MovimientoBancoHoras.objects.filter(
                    banco=banco, fecha=fecha_mov, tipo='ACUMULACION', tasa='35'
                ).exists():
                    MovimientoBancoHoras.objects.create(
                        banco=banco, tipo='ACUMULACION', tasa='35',
                        fecha=fecha_mov, horas=he35,
                        descripcion='HE 35% acumuladas (carga histórica demo)',
                    )
                    movs_creados += 1

        self.resumen['mov_banco_horas'] = movs_creados
        if movs_creados:
            self.stdout.write(f'  [+] Movimientos banco horas: {movs_creados}')

    # ──────────────────────────────────────────────────────────────────────
    # Pulse semanal
    # ──────────────────────────────────────────────────────────────────────

    def _generar_pulses(self, trabajadores):
        try:
            from encuestas.models import PulseSemanal
        except ImportError:
            self.resumen['avisos'].append('  - PulseSemanal no disponible')
            return

        # Empresas distintas presentes en la plantilla → escogemos las
        # "bajistas" determinísticamente
        empresas = sorted({t.empresa_id for t in trabajadores if t.empresa_id})
        if empresas:
            bajistas = set(empresas[:LOCALES_BAJISTAS])
        else:
            bajistas = set()

        # 17 meses × 4 semanas aprox = ~70 semanas. Cubrimos cada lunes ISO.
        fecha_inicio = date(*MES_INICIO, 1)
        fecha_fin = date(MES_FIN[0], MES_FIN[1], _last_day(*MES_FIN))

        # Lista de (anio_iso, semana_iso) únicas
        semanas = []
        cur = fecha_inicio
        vistas = set()
        while cur <= fecha_fin:
            y, w, _ = cur.isocalendar()
            if (y, w) not in vistas:
                vistas.add((y, w))
                semanas.append((y, w, cur))
            cur += timedelta(days=7)

        pulses_creados = 0
        for (anio_iso, sem_iso, fecha_ref) in semanas:
            # Tendencia: semanas más recientes → cae 0.5 puntos en bajistas
            progreso = semanas.index((anio_iso, sem_iso, fecha_ref)) / max(1, len(semanas) - 1)
            for t in trabajadores:
                if random.random() > PCT_RESPUESTAS_PULSE:
                    continue
                # Solo trabajadores activos en esa semana
                if t.fecha_alta and t.fecha_alta > fecha_ref:
                    continue
                if t.fecha_cese and t.fecha_cese < fecha_ref:
                    continue

                base = 4.1  # promedio "bien"
                if t.empresa_id in bajistas:
                    # Cae linealmente de 4.0 → 2.8
                    base = 4.0 - (1.2 * progreso)
                # Ruido aleatorio leve
                puntaje = max(1, min(5, int(round(base + random.uniform(-0.6, 0.6)))))

                _, created = PulseSemanal.objects.get_or_create(
                    personal=t, semana=sem_iso, anio=anio_iso,
                    defaults={
                        'empresa_id': t.empresa_id,
                        'animo': puntaje,
                        'que_falta': '',
                        'propuestas': '',
                        'nps': max(0, min(10, puntaje * 2)),
                    },
                )
                if created:
                    pulses_creados += 1

        self.resumen['pulses'] = pulses_creados
        if pulses_creados:
            self.stdout.write(f'  [+] Pulses semanales generados: {pulses_creados}')

    # ──────────────────────────────────────────────────────────────────────
    # Reporte
    # ──────────────────────────────────────────────────────────────────────

    def _reporte_final(self):
        r = self.resumen
        self.stdout.write(self.style.SUCCESS(
            '\n-------- Resumen seed_demo_historico --------'
        ))
        self.stdout.write(
            f'  [OK] {r["periodos_regular"]} periodos REGULAR creados/actualizados '
            f'({MES_INICIO[0]}-{MES_INICIO[1]:02d} -> {MES_FIN[0]}-{MES_FIN[1]:02d})'
        )
        self.stdout.write(
            f'  [OK] {r["periodos_gratif"]} periodos GRATIFICACION '
            f'({", ".join(f"{m:02d}/{a}" for a, m in PERIODOS_GRATIFICACION)})'
        )
        self.stdout.write(
            f'  [OK] {r["periodos_cts"]} periodos CTS '
            f'({", ".join(f"{m:02d}/{a}" for a, m in PERIODOS_CTS)})'
        )
        self.stdout.write(f'  [OK] ~{r["registros_nomina"]} RegistroNomina generados')
        self.stdout.write(
            f'  [OK] {r["ceses"]} ceses + {r["altas_retro"]} altas retroactivas '
            f'({r["aumentos_puntuales"]} aumentos puntuales)'
        )
        self.stdout.write(f'  [OK] {r["mov_banco_horas"]} movimientos banco de horas')
        self.stdout.write(f'  [OK] {r["pulses"]} pulses semanales')
        if r['avisos']:
            self.stdout.write(self.style.WARNING(f'\n  Avisos ({len(r["avisos"])}):'))
            for a in r['avisos'][:10]:
                self.stdout.write(a)
            if len(r['avisos']) > 10:
                self.stdout.write(f'    ... y {len(r["avisos"]) - 10} más')
        self.stdout.write('')
