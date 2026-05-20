"""
Procesador central de Tareo.

Recibe los datos crudos del parser (Synkro Reloj + Papeletas)
y los consolida en registros RegistroTareo con:
  - Código final según prioridad: Papeleta > Feriado > Reloj > Falta automática
  - Horas efectivas, HE 25/35/100
  - Banco de horas para STAFF
  - Cálculo de regularizaciones (descuentos fin de mes → mes siguiente)

Regla SS (Sin Salida):
  - La persona se presentó pero no marcó salida en el biométrico
  - Se le paga el día completo (cuenta como asistencia)
  - NO genera horas extras ni se acumula nada en el banco
  - horas_efectivas = jornada base, he_25 = he_35 = he_100 = 0
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger('personal.business')

CERO = Decimal('0')
MEDIA = Decimal('0.5')


def redondear_media_hora(valor: Decimal | float | int | None) -> Decimal:
    """Redondea al múltiplo más cercano de 0.5.

    Regla: x → round(x*2)/2 con ROUND_HALF_UP.
    Ej: 0.24→0.0, 0.25→0.5, 0.42→0.5, 0.78→1.0, 1.62→1.5, 2.08→2.0.
    """
    if valor is None:
        return CERO
    d = valor if isinstance(valor, Decimal) else Decimal(str(valor))
    # Multiplica por 2, redondea a entero, divide entre 2.
    pasos = (d * 2).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
    return (pasos / 2).quantize(Decimal('0.1'))

# ──────────────────────────────────────────────────────────────
# MAPEO DE TIPO PERMISO (texto → choice interno)
# ──────────────────────────────────────────────────────────────
TIPO_PERMISO_MAP = {
    'BAJADA': 'BAJADAS',
    'BAJADAS': 'BAJADAS',
    'BAJA': 'BAJADAS',
    'BAJADA ACUMULADA': 'BAJADAS_ACUMULADAS',
    'BAJADAS ACUMULADAS': 'BAJADAS_ACUMULADAS',
    'VACACIONES': 'VACACIONES',
    'VAC': 'VACACIONES',
    'DESCANSO MEDICO': 'DESCANSO_MEDICO',
    'DM': 'DESCANSO_MEDICO',
    'COMPENSACION HE': 'COMPENSACION_HE',
    'COMPENSACION POR HORARIO EXTENDIDO': 'COMPENSACION_HE',
    'CHE': 'COMPENSACION_HE',
    'LICENCIA CON GOCE': 'LICENCIA_CON_GOCE',
    'LCG': 'LICENCIA_CON_GOCE',
    'LICENCIA SIN GOCE': 'LICENCIA_SIN_GOCE',
    'LSG': 'LICENCIA_SIN_GOCE',
    'LICENCIA FALLECIMIENTO': 'LICENCIA_FALLECIMIENTO',
    'LICENCIA POR FALLECIMIENTO': 'LICENCIA_FALLECIMIENTO',
    'LF': 'LICENCIA_FALLECIMIENTO',
    'LICENCIA PATERNIDAD': 'LICENCIA_PATERNIDAD',
    'LICENCIA POR PATERNIDAD': 'LICENCIA_PATERNIDAD',
    'LP': 'LICENCIA_PATERNIDAD',
    'COMISION DE TRABAJO': 'COMISION_TRABAJO',
    'CT': 'COMISION_TRABAJO',
    'COMPENSACION DIA TRABAJO': 'COMP_DIA_TRABAJO',
    'CDT': 'COMP_DIA_TRABAJO',
    'SUSPENSION': 'SUSPENSION',
    'SUSPENSION ACTO INSEGURO': 'SUSPENSION_ACTO_INSEGURO',
    'SUSPENSION POR ACTO INSEGURO': 'SUSPENSION_ACTO_INSEGURO',
    'SAI': 'SUSPENSION_ACTO_INSEGURO',
    'ATENCION MEDICA': 'LICENCIA_CON_GOCE',   # ATM → cuenta como LCG (asistencia)
    'ATM': 'LICENCIA_CON_GOCE',
    'TRABAJO REMOTO': 'COMISION_TRABAJO',
    'TR': 'COMISION_TRABAJO',
}

# Iniciales → código tareo (homologación directa)
INICIALES_A_CODIGO = {
    'B':   'DL',   # Bajada / día libre ganado
    'BA':  'DLA',  # Bajada acumulada (corte 2025)
    'VAC': 'VAC',  # Vacaciones
    'DM':  'DM',   # Descanso médico
    'CHE': 'CHE',  # Compensación por HE (usa día del banco)
    'LCG': 'LCG',  # Licencia con goce
    'ATM': 'LCG',  # Atención médica → mismo tratamiento que LCG
    'LSG': 'LSG',  # Licencia sin goce (descuenta)
    'LF':  'LF',   # Licencia por fallecimiento
    'LP':  'LP',   # Licencia por paternidad
    'CT':  'CT',   # Comisión de trabajo
    'TR':  'TR',   # Trabajo remoto
    'CDT': 'CDT',  # Compensación día trabajado
    'CPF': 'CPF',  # Compensación por feriado
    'SAI': 'SAI',  # Suspensión por acto inseguro
    'F':   'FA',   # Falta
    'FA':  'FA',   # Falta
    'NOR': 'T',    # Día normal trabajado
    'T':   'T',    # Trabajo
    # SS se maneja aparte — NO se mapea a un código de HE
}

# Códigos que descuentan remuneración
CODIGOS_DESCUENTO = {'FA', 'LSG', 'SAI'}

# Códigos que NO generan HE (el día se paga pero no suma horas al banco/pago)
CODIGOS_SIN_HE = {'SS', 'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF',
                  'LP', 'LSG', 'FA', 'TR', 'CDT', 'CPF', 'ATM', 'SAI',
                  'DS', 'FER'}
# DS/FER → no laborado (0 horas, fuerza limpia).
# Para "trabajado en descanso/feriado" usar DSL/FL → 100% por D.Leg. 713
# Art. 3-4 (descanso semanal) y Art. 9 (feriados).

# Códigos que SÍ cuentan como día trabajado para el resumen mensual
CODIGOS_ASISTENCIA = {'T', 'TR', 'LCG', 'ATM', 'CPF', 'CDT', 'SS', 'DSL', 'FL'}


class TareoProcessor:
    """
    Consolida datos de Reloj y Papeletas en RegistroTareo.

    Uso:
        proc = TareoProcessor(importacion)
        resultado = proc.procesar(registros_reloj, papeletas)
    """

    def __init__(self, importacion, config=None):
        from asistencia.models import ConfiguracionSistema, FeriadoCalendario, HomologacionCodigo
        self.importacion = importacion
        self.config = config or ConfiguracionSistema.get()

        # Cargar feriados del período
        self._feriados: set[date] = set(
            FeriadoCalendario.objects
            .filter(activo=True)
            .values_list('fecha', flat=True)
        )

        # Cargar homologaciones (código_origen → HomologacionCodigo)
        self._homologaciones = {
            h.codigo_origen.upper(): h
            for h in HomologacionCodigo.objects.filter(activo=True)
        }

        # Cargar papeletas de compensación activas (personal_id, fecha_referencia)
        # Unificado: RegistroPapeleta con tipo CPF/CDT reemplaza PapeletaCompensacion
        from asistencia.models import RegistroPapeleta, SolicitudHE
        self._papeletas_comp: set[tuple] = set(
            RegistroPapeleta.objects
            .filter(
                tipo_permiso__in=['COMPENSACION_FERIADO', 'COMP_DIA_TRABAJO'],
                estado__in=['APROBADA', 'EJECUTADA'],
                fecha_referencia__isnull=False,
            )
            .values_list('personal_id', 'fecha_referencia')
        )

        # Control HE: si he_requiere_solicitud=True, cargar solicitudes aprobadas
        self._he_requiere_solicitud: bool = self.config.he_requiere_solicitud
        self._solicitudes_he: set[tuple] = set()
        if self._he_requiere_solicitud:
            self._solicitudes_he = set(
                SolicitudHE.objects
                .filter(estado='APROBADA')
                .values_list('personal_id', 'fecha')
            )

        # Cargar reglas especiales por empleado (activas, ordenadas por prioridad)
        from asistencia.models import ReglaEspecialPersonal
        self._reglas: dict[int, list] = {}
        for regla in ReglaEspecialPersonal.objects.filter(activa=True).order_by('prioridad'):
            self._reglas.setdefault(regla.personal_id, []).append(regla)

    @transaction.atomic
    def procesar(self, registros_reloj: list[dict], papeletas: list[dict],
                 grupo_default: str = 'STAFF') -> dict:
        """
        Procesa y guarda los RegistroTareo y RegistroPapeleta.

        registros_reloj: lista de dicts de SynkroParser.parse_reloj()
        papeletas: lista de dicts de SynkroParser.parse_papeletas()
        grupo_default: 'STAFF' o 'RCO' si no se puede determinar por DB

        Retorna dict con contadores y listas de errores/advertencias.
        """
        from asistencia.models import RegistroPapeleta, RegistroTareo

        creados = 0
        actualizados = 0
        sin_match = 0
        errores = []
        advertencias = []

        # ── 1. Guardar papeletas ───────────────────────────────
        papeletas_por_dni: dict[str, list[dict]] = {}
        for p in papeletas:
            dni = p['dni']
            papeletas_por_dni.setdefault(dni, []).append(p)

        personal_map = self._cargar_personal_map(
            {r['dni'] for r in registros_reloj} | set(papeletas_por_dni.keys())
        )

        for p in papeletas:
            dni = p['dni']
            personal_obj = personal_map.get(dni)
            tipo_choice = self._mapear_tipo_permiso(
                p['tipo_permiso_raw'], p['iniciales'])

            RegistroPapeleta.objects.get_or_create(
                importacion=self.importacion,
                dni=dni,
                fecha_inicio=p['fecha_inicio'],
                fecha_fin=p['fecha_fin'],
                defaults={
                    'personal': personal_obj,
                    'nombre_archivo': p.get('nombre', ''),
                    'tipo_permiso': tipo_choice,
                    'tipo_permiso_raw': p['tipo_permiso_raw'],
                    'iniciales': p['iniciales'],
                    'detalle': p['detalle'],
                    'area_trabajo': p.get('area', ''),
                    'cargo': p.get('cargo', ''),
                }
            )

        # Índice de papeletas por (dni, fecha)
        papeletas_idx = self._indexar_papeletas(papeletas)

        # Pre-cargar overrides de almuerzo_manual (ediciones manuales previas a re-importación)
        almuerzo_overrides: dict[tuple, Decimal] = {
            (r['dni'], r['fecha']): r['almuerzo_manual']
            for r in RegistroTareo.objects.filter(
                importacion=self.importacion,
                almuerzo_manual__isnull=False,
            ).values('dni', 'fecha', 'almuerzo_manual')
        }

        # ── 2. Procesar registros del Reloj ────────────────────
        for reg in registros_reloj:
            dni = reg['dni']
            fecha = reg['fecha']
            personal_obj = personal_map.get(dni)

            if not personal_obj:
                sin_match += 1
                advertencias.append(
                    f'DNI {dni} ({reg.get("nombre","")}) no encontrado en BD.')

            # Determinar grupo y condición
            grupo = (personal_obj.grupo_tareo if personal_obj else grupo_default)
            condicion = (personal_obj.condicion if personal_obj and personal_obj.condicion
                         else reg.get('condicion', 'LOCAL'))

            # Jornada diaria según condición y día de semana
            jornada_h = self._obtener_jornada(personal_obj, condicion,
                                               dia_semana=fecha.weekday())

            # ── Determinar código y fuente ────────────────────
            codigo_dia, fuente, horas_marcadas, es_ss = self._determinar_codigo(
                reg, fecha, papeletas_idx.get((dni, fecha)), condicion,
                personal_id=personal_obj.pk if personal_obj else None)

            # ── Calcular horas ────────────────────────────────
            personal_id = personal_obj.pk if personal_obj else None

            # Papeleta de compensación aprobada → feriado/DSO se trata como día normal
            tiene_papeleta = (personal_id, fecha) in self._papeletas_comp

            # Control HE: sin solicitud aprobada → no se registran HE
            he_bloqueado = (
                self._he_requiere_solicitud
                and personal_id is not None
                and (personal_id, fecha) not in self._solicitudes_he
            )

            # Override de almuerzo manual (editado previamente en calendario)
            almuerzo_manual = almuerzo_overrides.get((dni, fecha))

            horas_ef, h_norm, he25, he35, he100 = self._calcular_horas(
                codigo_dia, horas_marcadas, jornada_h,
                fecha in self._feriados, grupo, es_ss,
                dia_semana=fecha.weekday(),
                tiene_papeleta_comp=tiene_papeleta,
                he_bloqueado=he_bloqueado,
                almuerzo_manual=almuerzo_manual,
                fuente_codigo=fuente,
            )

            he_al_banco = (grupo == 'STAFF')

            # ── Guardar ───────────────────────────────────────
            obj, created = RegistroTareo.objects.update_or_create(
                importacion=self.importacion,
                dni=dni,
                fecha=fecha,
                defaults={
                    'personal': personal_obj,
                    'nombre_archivo': reg.get('nombre', ''),
                    'grupo': grupo,
                    'condicion': condicion,
                    'valor_reloj_raw': reg.get('valor_raw', ''),
                    'horas_marcadas': horas_marcadas,
                    'codigo_dia': codigo_dia,
                    'fuente_codigo': fuente,
                    'horas_efectivas': horas_ef,
                    'horas_normales': h_norm,
                    'he_25': he25,
                    'he_35': he35,
                    'he_100': he100,
                    'he_al_banco': he_al_banco,
                    'es_feriado': fecha in self._feriados,
                    'dia_semana': fecha.weekday(),
                }
            )
            if created:
                creados += 1
            else:
                actualizados += 1

        # ── 3. Actualizar banco de horas STAFF ─────────────────
        banco_stats = self._actualizar_banco_horas(personal_map)

        # ── 4. Actualizar importación ──────────────────────────
        self.importacion.registros_ok = creados + actualizados
        self.importacion.registros_error = len(errores)
        self.importacion.registros_sin_match = sin_match
        self.importacion.estado = (
            'COMPLETADO_CON_ERRORES' if errores else 'COMPLETADO')
        self.importacion.procesado_en = timezone.now()
        self.importacion.errores = errores
        self.importacion.advertencias = advertencias
        self.importacion.save()

        logger.info(
            f'Tareo procesado: {creados} creados, {actualizados} actualizados, '
            f'{sin_match} sin match. Importación #{self.importacion.pk}')

        return {
            'creados': creados,
            'actualizados': actualizados,
            'sin_match': sin_match,
            'errores': errores,
            'advertencias': advertencias,
            'banco': banco_stats,
        }

    # ── Helpers ────────────────────────────────────────────────

    def _cargar_personal_map(self, dnis: set) -> dict:
        """
        Carga el mapa DNI → Personal desde la BD.
        Maneja zero-padding: Excel puede guardar '01234567' como '1234567'
        (pierde el cero inicial al tratar el DNI como número).
        Se buscan ambas versiones y el resultado se indexa por la versión
        que llegó en el archivo para que el lookup posterior funcione.
        """
        from personal.models import Personal
        # Expandir: agregar versión zero-padded (7 → 8 dígitos) y sin padding (8 → 7 si hay cero)
        dnis_expanded = set(dnis)
        for d in dnis:
            if d.isdigit():
                if len(d) == 7:
                    dnis_expanded.add(d.zfill(8))   # 1234567 → 01234567
                elif len(d) == 8 and d.startswith('0'):
                    dnis_expanded.add(d.lstrip('0')) # 01234567 → 1234567

        personas = list(
            Personal.objects.filter(nro_doc__in=dnis_expanded)
            .select_related('subarea', 'subarea__area')
        )

        result: dict[str, object] = {}
        for p in personas:
            result[p.nro_doc] = p
            # Mapear también la versión sin/con cero para que el lookup funcione
            # con el DNI tal como vino en el archivo
            nd = p.nro_doc
            if nd.isdigit():
                alt = nd.lstrip('0') or nd   # sin ceros iniciales
                padded = nd.zfill(8)         # con cero inicial
                if alt in dnis and alt not in result:
                    result[alt] = p
                if padded in dnis and padded not in result:
                    result[padded] = p
        return result

    def _indexar_papeletas(self, papeletas: list[dict]) -> dict:
        """
        Índice (dni, fecha) → papeleta para lookup O(1).
        Si hay varias papeletas en la misma fecha, prevalece la primera
        (el parser ya las ordena por prioridad del tipo).
        """
        idx: dict[tuple, dict] = {}
        for p in papeletas:
            fecha_cur = p['fecha_inicio']
            while fecha_cur <= p['fecha_fin']:
                key = (p['dni'], fecha_cur)
                if key not in idx:
                    idx[key] = p
                fecha_cur += timedelta(days=1)
        return idx

    def _obtener_jornada(self, personal_obj, condicion: str,
                         dia_semana: int | None = None) -> Decimal:
        """
        Jornada diaria en horas según condición y día de semana.
          LOCAL / LIMA  lun–vie (0–4) → config.jornada_local_horas   (def 8.5h)
          LOCAL / LIMA  sábado  (5)   → config.jornada_sabado_horas  (def 5.5h)
          FORÁNEO                     → config.jornada_foraneo_horas (def 11.0h)

        Override explícito en Personal.jornada_horas solo se aplica si el valor
        difiere del default 8 (evita que el default del campo anule la config).
        """
        # Override manual en ficha del trabajador (distinto al default 8)
        if (personal_obj and personal_obj.jornada_horas
                and Decimal(str(personal_obj.jornada_horas)) != Decimal('8')):
            return Decimal(str(personal_obj.jornada_horas))

        # Domingo
        if dia_semana == 6:
            if condicion.upper().replace('Á', 'A') == 'FORANEO':
                # FORÁNEO: domingo es parte del ciclo 21×7, jornada reducida 4h
                return Decimal(str(self.config.jornada_domingo_horas))
            # LOCAL/LIMA: domingo es descanso semanal, si labora todo al 100%
            return CERO

        if condicion in ('FORANEO', 'FORÁNEO'):
            return Decimal(str(self.config.jornada_foraneo_horas))

        # LOCAL / LIMA: distinguir sábado de lun–vie
        if dia_semana == 5:          # sábado
            return Decimal(str(self.config.jornada_sabado_horas))
        return Decimal(str(self.config.jornada_local_horas))

    def _determinar_codigo(self, reg: dict, fecha: date,
                            papeleta: dict | None,
                            condicion: str,
                            personal_id: int | None = None,
                            ) -> tuple[str, str, Decimal | None, bool]:
        """
        Aplica reglas de prioridad:
          1. Papeleta (prioridad 1)
          2. Feriado del calendario (prioridad 5)
          3. Dato del Reloj (prioridad 10)
          4. Falta automática (prioridad 99)

        Retorna: (codigo_dia, fuente, horas_marcadas, es_ss)
          es_ss=True indica que el día tiene SS (sin salida) en el reloj.
        """
        codigo, fuente, horas, es_ss = self._determinar_codigo_raw(
            reg, fecha, papeleta, condicion, personal_id,
        )

        # #8 fix: FORÁNEO domingo NUNCA debe ser DS (su domingo es jornada 4h
        # del ciclo 21×7, no descanso). Si el reloj envió DS, normalizar.
        cond_norm = (condicion or '').upper().replace('Á', 'A')
        if (codigo == 'DS' and cond_norm == 'FORANEO'
                and fecha.weekday() == 6):
            horas_reloj = reg.get('horas')
            codigo_reloj_raw = (reg.get('codigo') or '').upper().strip()
            if (horas_reloj and horas_reloj > 0) or codigo_reloj_raw == 'SS':
                # Marcó horas → asistencia normal
                return ('A', 'RELOJ', horas_reloj if horas_reloj else None,
                        codigo_reloj_raw == 'SS')
            # Sin marca → falta (no DS porque domingo es laborable para FORÁNEO)
            return 'FA', 'FALTA_AUTO', None, False

        return codigo, fuente, horas, es_ss

    def _determinar_codigo_raw(self, reg: dict, fecha: date,
                                papeleta: dict | None,
                                condicion: str,
                                personal_id: int | None = None,
                                ) -> tuple[str, str, Decimal | None, bool]:
        """Implementación interna sin validaciones de coherencia."""
        # Prioridad 1: Papeleta (anula el reloj)
        if papeleta:
            ini = papeleta['iniciales'].upper().strip()
            codigo = INICIALES_A_CODIGO.get(ini, ini)
            return codigo, 'PAPELETA', None, False

        # Prioridad 1.5: Regla especial del personal
        if personal_id and personal_id in self._reglas:
            codigo_reloj = (reg.get('codigo') or '').upper().strip()
            for regla in self._reglas[personal_id]:
                if regla.aplica_a(fecha, fecha.weekday(), condicion,
                                  codigo_reloj, fecha in self._feriados):
                    return regla.codigo_resultado, 'REGLA_ESPECIAL', regla.horas_override, False

        # Prioridad 2: Feriado (solo si no hay marcación de trabajo real)
        if fecha in self._feriados and reg.get('codigo') in (None, 'FA', ''):
            return 'FER', 'FERIADO', None, False

        # Prioridad 3: Dato del Reloj
        codigo_reloj = reg.get('codigo', '').upper().strip() if reg.get('codigo') else ''
        horas_reloj = reg.get('horas')

        # SS = Sin Salida: persona presente pero sin marca de salida
        # → paga el día, NO genera HE, NO va al banco
        if codigo_reloj == 'SS':
            return 'SS', 'RELOJ', None, True

        if horas_reloj and horas_reloj > 0:
            # Número de horas → asistencia normal
            # Validar rango razonable (máx 16h para foráneos con extensión)
            if horas_reloj > 16:
                logger.warning(
                    f'Horas sospechosas ({horas_reloj}h) para DNI {reg.get("dni")} '
                    f'en {fecha}. Se usará máximo 16h.')
                horas_reloj = Decimal('16')
            # Homologar si hay regla DB, sino usar código 'T'
            h = self._homologaciones.get('NUMERICO') or self._homologaciones.get('>0')
            codigo = h.codigo_tareo if h else 'T'
            return codigo, 'RELOJ', horas_reloj, False

        if codigo_reloj and codigo_reloj not in ('FA', '', '-'):
            # Código string (DL, VAC, DM, CHE, etc.)
            h = self._homologaciones.get(codigo_reloj)
            codigo = h.codigo_tareo if h else INICIALES_A_CODIGO.get(codigo_reloj, codigo_reloj)
            return codigo, 'RELOJ', None, False

        # Prioridad 4: Domingo LOCAL/LIMA = Descanso Semanal (no falta)
        if fecha.weekday() == 6 and condicion.upper() in ('LOCAL', 'LIMA', ''):
            return 'DS', 'DESCANSO_SEMANAL', None, False

        # Prioridad 5: Falta automática
        return 'FA', 'FALTA_AUTO', None, False

    def _calcular_horas(self, *args, **kwargs
                        ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        """Wrapper que redondea cada componente al múltiplo más cercano de 0.5.

        La regla de negocio exige que horas_efectivas, horas_normales y las
        tres variantes de HE se almacenen siempre como X.0 o X.5. Para mantener
        la invariante ef = norm + he25 + he35 + he100 redondeamos cada campo
        de forma independiente (verificado contra el dataset abril 2026).
        """
        he, hn, h25, h35, h100 = self._calcular_horas_raw(*args, **kwargs)
        return (redondear_media_hora(he),
                redondear_media_hora(hn),
                redondear_media_hora(h25),
                redondear_media_hora(h35),
                redondear_media_hora(h100))

    def _calcular_horas_raw(self, codigo: str, horas_marcadas: Decimal | None,
                        jornada_h: Decimal, es_feriado: bool,
                        grupo: str, es_ss: bool = False,
                        dia_semana: int | None = None,
                        tiene_papeleta_comp: bool = False,
                        he_bloqueado: bool = False,
                        almuerzo_manual: Decimal | None = None,
                        fuente_codigo: str = '',
                        ) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
        """
        Retorna (horas_efectivas, horas_normales, he_25, he_35, he_100).

        Reglas HE (D.S. 007-2002-TR, art. 10):
          - 1ra y 2da HE → tasa 25%
          - 3ra HE en adelante → tasa 35%
          - Feriado laborado → tasa 100% (D.Leg. 713, Art. 9)
          - Descanso semanal trabajado → tasa 100% (D.Leg. 713, Art. 3-4)
            Incluye: domingos y cualquier día de descanso según régimen

        Regla SS:
          - El día SS se paga como jornada completa (horas_efectivas = jornada)
          - NO genera HE de ningún tipo
          - NO va al banco de horas

        Regla STAFF vs RCO:
          - STAFF: HE van al banco (he_al_banco=True, se guardan igual)
          - RCO: HE se pagan en nómina (se exportan a CargaS10)
          - El cálculo de HE es idéntico; solo difiere el destino.
        """
        # ── SS (Sin Salida): paga jornada, sin HE adicional ──
        if es_ss:
            j = jornada_h if jornada_h > CERO else Decimal('8.5')
            # LOCAL domingo o feriado: SS también se paga al 100%
            # D.Leg. 713: trabajar en descanso semanal o feriado → 100%
            es_descanso = (dia_semana == 6) if dia_semana is not None else False
            if (es_feriado or es_descanso) and (es_feriado or jornada_h == CERO):
                return j, CERO, CERO, CERO, j
            return j, j, CERO, CERO, CERO

        # ── Marcación incompleta: horas < mitad de jornada → SS implícito
        # Si marcó entrada pero no salida (o solo salida a refrigerio),
        # el biométrico calcula pocas horas. Se reconoce jornada completa, sin HE.
        if (horas_marcadas and horas_marcadas > CERO
                and horas_marcadas < jornada_h / 2
                and codigo not in CODIGOS_SIN_HE):
            return jornada_h, jornada_h, CERO, CERO, CERO

        # ── Códigos sin horas ni HE ────────────────────────────
        if codigo in CODIGOS_SIN_HE or not horas_marcadas or horas_marcadas <= CERO:
            return CERO, CERO, CERO, CERO, CERO

        # ── Descontar almuerzo ─────────────────────────────────
        # Lógica unificada con _recalcular_horas (UI) via helper compartido.
        from asistencia.services._helpers import calcular_almuerzo_h
        almuerzo_h = calcular_almuerzo_h(horas_marcadas, jornada_h, almuerzo_manual)
        horas_ef = max(CERO, horas_marcadas - almuerzo_h)

        # ── Feriado laborado o Descanso Semanal trabajado: todo al 100%
        # D.Leg. 713, Art. 3-4: Descanso semanal obligatorio (domingo por defecto)
        # D.Leg. 713, Art. 9: Feriados no laborables
        # Si el trabajador asiste en estos días, TODAS las horas son al 100%
        # Excepción: si hay papeleta de compensación APROBADA, se trata como día normal
        # (D.Leg. 713 Art. 6 — compensación en lugar de pago HE 100%)
        # Códigos LABORADOS (DSL/FL) indican descanso/feriado trabajado aunque
        # el día calendario no lo sea (descanso rotativo en miércoles).
        es_descanso_semanal = (
            ((dia_semana == 6) if dia_semana is not None else False)
            or codigo == 'DSL'
        )
        codigo_es_feriado = codigo == 'FL'
        # Si el CÓDIGO dice laborado en descanso/feriado, todas las horas al 100%
        # (no aplica la jornada reducida de FORÁNEO domingo).
        codigo_fuerza_100 = codigo in ('DSL', 'FL')
        # #4 fix: si el admin cambió manualmente a NOR/T/A, calcular como día normal
        # (el trabajador tiene descanso semanal en otro día, no el domingo)
        codigo_fuerza_normal = (
            codigo in ('NOR', 'T', 'A') and fuente_codigo == 'MANUAL'
        )
        if ((es_feriado or codigo_es_feriado or es_descanso_semanal)
                and not tiene_papeleta_comp and not codigo_fuerza_normal):
            jornada = Decimal(str(jornada_h))
            if es_feriado or codigo_fuerza_100 or jornada == CERO:
                # Feriado (toda condición) o LOCAL domingo: TODAS las horas al 100%
                # D.Leg. 713, Art. 3-4 (descanso semanal) y Art. 9 (feriados)
                return horas_ef, CERO, CERO, CERO, horas_ef
            else:
                # FORÁNEO domingo (4h jornada): normal hasta jornada, exceso HE 100%
                h_norm = min(horas_ef, jornada)
                he100 = max(CERO, horas_ef - jornada)
                return horas_ef, h_norm, CERO, CERO, he100

        # ── Día normal ─────────────────────────────────────────
        jornada = Decimal(str(jornada_h))
        if horas_ef <= jornada:
            return horas_ef, horas_ef, CERO, CERO, CERO

        # ── Control HE: sin solicitud aprobada → se capan en jornada ──
        # DL 728: HE son voluntarias; el empleador puede exigir autorización previa.
        # Si he_bloqueado=True, el exceso no se registra como HE.
        if he_bloqueado:
            return jornada, jornada, CERO, CERO, CERO

        # Exceso sobre la jornada normal → HE
        exceso = horas_ef - jornada
        he25 = min(exceso, Decimal('2'))            # primeras 2 HE al 25%
        he35 = max(CERO, exceso - Decimal('2'))     # 3ra HE en adelante al 35%

        return horas_ef, jornada, he25, he35, CERO

    @transaction.atomic
    def _actualizar_banco_horas(self, personal_map: dict) -> dict:
        """
        Acumula HE en BancoHoras para personal STAFF.
        Solo procesa registros de la importación actual.

        El ciclo HE va del día 21 del mes anterior al 20 del mes actual.
        El banco se asocia al mes de la planilla (periodo_inicio.month del
        ImportacionTareo, que corresponde al mes de pago).

        Además descuenta las papeletas CHE (días compensados) que caigan
        dentro del mismo ciclo, actualizando he_compensadas y saldo_horas.
        """
        from django.db.models import Sum
        from asistencia.models import (BancoHoras, MovimientoBancoHoras,
                                   RegistroPapeleta, RegistroTareo)

        if not self.importacion.periodo_fin:
            return {}

        # El banco se registra en el MES DE PAGO = periodo_fin del ciclo HE.
        # El ciclo HE va del día 21 del mes anterior al 20 (o 25) del mes actual.
        # periodo_fin cae dentro del mes que se paga, no del mes anterior.
        # Ej: ciclo 21-ene→25-feb → pago febrero → anio=2026, mes=2
        anio = self.importacion.periodo_fin.year
        mes = self.importacion.periodo_fin.month

        # Sumar HE generadas en esta importación (STAFF, con match en BD)
        resumen_he = (
            RegistroTareo.objects
            .filter(importacion=self.importacion, grupo='STAFF',
                    personal__isnull=False)
            .values('personal_id')
            .annotate(
                sum_25=Sum('he_25'),
                sum_35=Sum('he_35'),
                sum_100=Sum('he_100'),
            )
        )

        # Contar días CHE (compensación usada) en papeletas de esta importación
        che_por_personal: dict[int, int] = {}
        for pap in (RegistroPapeleta.objects
                    .filter(importacion=self.importacion,
                            tipo_permiso='COMPENSACION_HE',
                            personal__isnull=False)
                    .values('personal_id', 'fecha_inicio', 'fecha_fin')):
            pid = pap['personal_id']
            dias = (pap['fecha_fin'] - pap['fecha_inicio']).days + 1
            che_por_personal[pid] = che_por_personal.get(pid, 0) + dias

        stats = {'actualizados': 0, 'creados': 0}
        for r in resumen_he:
            pid = r['personal_id']
            sum_25 = r['sum_25'] or Decimal('0')
            sum_35 = r['sum_35'] or Decimal('0')
            sum_100 = r['sum_100'] or Decimal('0')
            total_acumulado = sum_25 + sum_35 + sum_100

            # Días CHE → 1 día CHE = jornada_h horas descontadas del banco
            dias_che = che_por_personal.get(pid, 0)
            personal_obj = None
            for p in personal_map.values():
                if p and p.pk == pid:
                    personal_obj = p
                    break
            jornada_h = self._obtener_jornada(personal_obj, 'LOCAL')
            horas_compensadas = Decimal(str(dias_che)) * jornada_h

            banco, created = BancoHoras.objects.get_or_create(
                personal_id=pid,
                periodo_anio=anio,
                periodo_mes=mes,
                defaults={
                    'he_25_acumuladas': sum_25,
                    'he_35_acumuladas': sum_35,
                    'he_100_acumuladas': sum_100,
                    'he_compensadas': horas_compensadas,
                    'saldo_horas': total_acumulado - horas_compensadas,
                }
            )
            if not created:
                banco.he_25_acumuladas = sum_25
                banco.he_35_acumuladas = sum_35
                banco.he_100_acumuladas = sum_100
                banco.he_compensadas = horas_compensadas
                banco.saldo_horas = total_acumulado - horas_compensadas
                banco.save()
                stats['actualizados'] += 1
            else:
                stats['creados'] += 1

            # Movimiento de acumulación (idempotente)
            if total_acumulado > 0:
                MovimientoBancoHoras.objects.get_or_create(
                    banco=banco,
                    tipo='ACUMULACION',
                    fecha=self.importacion.periodo_fin or date.today(),
                    defaults={
                        'horas': total_acumulado,
                        'descripcion': f'Importación #{self.importacion.pk}',
                    }
                )

            # Movimiento de compensación (si aplica)
            if horas_compensadas > 0:
                MovimientoBancoHoras.objects.get_or_create(
                    banco=banco,
                    tipo='COMPENSACION',
                    fecha=self.importacion.periodo_fin or date.today(),
                    defaults={
                        'horas': -horas_compensadas,
                        'descripcion': (f'{dias_che} día(s) CHE × {jornada_h}h — '
                                        f'Importación #{self.importacion.pk}'),
                    }
                )

        return stats

    @staticmethod
    def _mapear_tipo_permiso(tipo_raw: str, iniciales: str) -> str:
        tipo_upper = tipo_raw.upper().strip()
        for k, v in TIPO_PERMISO_MAP.items():
            if k in tipo_upper:
                return v
        ini_upper = iniciales.upper().strip()
        for k, v in TIPO_PERMISO_MAP.items():
            if k == ini_upper:
                return v
        return 'OTRO'
