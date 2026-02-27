"""
Comando de management: seed_tareo_inicial

Carga en la BD la configuración inicial del módulo Tareo:
  - Regímenes de turno (Local 5×2, Foráneo 21×7)
  - Horarios por tipo de día (según hoja Parametros del Excel)
  - Feriados 2026 (según hoja Parametros)
  - Tabla de homologación de códigos (Reloj → Tareo → Roster)

Idempotente: puede ejecutarse varias veces sin duplicar registros.

Uso:
    python manage.py seed_tareo_inicial
    python manage.py seed_tareo_inicial --force  # sobreescribe si existe
"""
import datetime
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Carga configuración inicial del módulo Tareo (regímenes, horarios, feriados, homologaciones)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Sobreescribir registros existentes',
        )

    def handle(self, *args, **options):
        force = options['force']
        self.stdout.write(self.style.MIGRATE_HEADING(
            "═══ Seed inicial del módulo Tareo ═══"
        ))

        with transaction.atomic():
            self._seed_regimenes(force)
            self._seed_feriados(force)
            self._seed_homologaciones(force)

        self.stdout.write(self.style.SUCCESS("\n✓ Seed completado exitosamente.\n"))

    # ─────────────────────────────────────────────────────────
    # REGÍMENES Y HORARIOS
    # ─────────────────────────────────────────────────────────

    def _seed_regimenes(self, force):
        from tareo.models import RegimenTurno, TipoHorario

        self.stdout.write("\n▸ Regímenes de turno y horarios...")

        regimenes_data = [
            {
                'nombre': 'Local 5×2',
                'codigo': '5X2',
                'jornada_tipo': 'SEMANAL',
                'dias_trabajo_ciclo': 5,
                'dias_descanso_ciclo': 2,
                'minutos_almuerzo': 60,
                'es_nocturno': False,
                'descripcion': (
                    'Jornada local sede. L-V: 07:30-17:00 (8.5h efectivas), '
                    'Sáb: 07:30-13:00 (5.5h). Total semana: 48h. '
                    'Cumple normativa DS 007-2002-TR.'
                ),
                'horarios': [
                    {
                        'nombre': 'Local L-V',
                        'tipo_dia': 'LUNES_VIERNES',
                        'hora_entrada': datetime.time(7, 30),
                        'hora_salida': datetime.time(17, 0),
                        'salida_dia_siguiente': False,
                    },
                    {
                        'nombre': 'Local Sábado',
                        'tipo_dia': 'SABADO',
                        'hora_entrada': datetime.time(7, 30),
                        'hora_salida': datetime.time(13, 0),
                        'salida_dia_siguiente': False,
                    },
                ],
            },
            {
                'nombre': 'Foráneo 21×7',
                'codigo': '21X7',
                'jornada_tipo': 'ACUMULATIVA',
                'dias_trabajo_ciclo': 21,
                'dias_descanso_ciclo': 7,
                'minutos_almuerzo': 60,
                'es_nocturno': False,
                'descripcion': (
                    'Régimen acumulativo Art. 9 DS 007-2002-TR. '
                    'L-Sáb: 07:30-18:30 (10h efectivas), Dom: 08:00-12:00 (4h). '
                    'Ciclo 28 días = 4 semanas × 48h = 192h máximas. '
                    'Verificación: 21 días × 10h (aprox.) = 210h → HE desde h193.'
                ),
                'horarios': [
                    {
                        'nombre': 'Foráneo L-Sáb',
                        'tipo_dia': 'LUNES_SABADO',
                        'hora_entrada': datetime.time(7, 30),
                        'hora_salida': datetime.time(18, 30),
                        'salida_dia_siguiente': False,
                    },
                    {
                        'nombre': 'Foráneo Domingo',
                        'tipo_dia': 'DOMINGO',
                        'hora_entrada': datetime.time(8, 0),
                        'hora_salida': datetime.time(12, 0),
                        'salida_dia_siguiente': False,
                    },
                ],
            },
            {
                'nombre': 'Foráneo Turno Noche',
                'codigo': 'TN',
                'jornada_tipo': 'NOCTURNA',
                'dias_trabajo_ciclo': 5,
                'dias_descanso_ciclo': 2,
                'minutos_almuerzo': 0,  # Sin almuerzo en noche
                'es_nocturno': True,
                'recargo_nocturno_pct': 35,
                'descripcion': (
                    'Turno nocturno (22:00-06:00). '
                    'Recargo mínimo legal 35% sobre RMV vigente. '
                    'Ajustar hora_entrada/salida según operación.'
                ),
                'horarios': [
                    {
                        'nombre': 'Noche L-V',
                        'tipo_dia': 'LUNES_VIERNES',
                        'hora_entrada': datetime.time(22, 0),
                        'hora_salida': datetime.time(6, 0),
                        'salida_dia_siguiente': True,
                    },
                ],
            },
            {
                'nombre': 'Semanal Rotativo',
                'codigo': 'ROT',
                'jornada_tipo': 'ROTATIVA',
                'dias_trabajo_ciclo': 5,
                'dias_descanso_ciclo': 2,
                'minutos_almuerzo': 60,
                'es_nocturno': False,
                'descripcion': (
                    'Jornada con día de descanso rotativo (no necesariamente domingo). '
                    'La persona puede trabajar cualquier día de la semana; '
                    'el descanso se asigna individualmente.'
                ),
                'horarios': [
                    {
                        'nombre': 'Rotativo Turno A',
                        'tipo_dia': 'TURNO_A',
                        'hora_entrada': datetime.time(7, 30),
                        'hora_salida': datetime.time(17, 0),
                        'salida_dia_siguiente': False,
                    },
                    {
                        'nombre': 'Rotativo Turno B',
                        'tipo_dia': 'TURNO_B',
                        'hora_entrada': datetime.time(14, 0),
                        'hora_salida': datetime.time(22, 0),
                        'salida_dia_siguiente': False,
                    },
                ],
            },
        ]

        created_r = updated_r = created_h = 0

        for rd in regimenes_data:
            horarios = rd.pop('horarios', [])
            recargo = rd.pop('recargo_nocturno_pct', None)

            defaults = {k: v for k, v in rd.items() if k != 'nombre'}
            if recargo is not None:
                defaults['recargo_nocturno_pct'] = recargo

            regimen, created = RegimenTurno.objects.get_or_create(
                codigo=rd['codigo'],
                defaults={**defaults, 'nombre': rd['nombre']},
            )

            if not created and force:
                for k, v in defaults.items():
                    setattr(regimen, k, v)
                regimen.save()
                updated_r += 1
            elif created:
                created_r += 1

            for hd in horarios:
                _, h_created = TipoHorario.objects.get_or_create(
                    regimen=regimen,
                    tipo_dia=hd['tipo_dia'],
                    defaults=hd,
                )
                if h_created:
                    created_h += 1

        self.stdout.write(
            f"  Regímenes: {created_r} creados, {updated_r} actualizados. "
            f"Horarios: {created_h} creados."
        )

    # ─────────────────────────────────────────────────────────
    # FERIADOS 2026 (desde hoja Parametros del Excel)
    # ─────────────────────────────────────────────────────────

    def _seed_feriados(self, force):
        from tareo.models import FeriadoCalendario

        self.stdout.write("\n▸ Feriados 2026...")

        feriados = [
            (datetime.date(2026, 1, 1),  'Año Nuevo',                                   'NO_RECUPERABLE'),
            (datetime.date(2026, 4, 2),  'Jueves Santo',                                'NO_RECUPERABLE'),
            (datetime.date(2026, 4, 3),  'Viernes Santo',                               'NO_RECUPERABLE'),
            (datetime.date(2026, 5, 1),  'Día del Trabajo',                             'NO_RECUPERABLE'),
            (datetime.date(2026, 6, 7),  'Batalla de Arica y Día de la Bandera',        'NO_RECUPERABLE'),
            (datetime.date(2026, 6, 29), 'San Pedro y San Pablo',                       'NO_RECUPERABLE'),
            (datetime.date(2026, 7, 23), 'Día de la Fuerza Aérea del Perú',             'NO_RECUPERABLE'),
            (datetime.date(2026, 7, 28), 'Fiestas Patrias',                             'NO_RECUPERABLE'),
            (datetime.date(2026, 7, 29), 'Fiestas Patrias',                             'NO_RECUPERABLE'),
            (datetime.date(2026, 8, 6),  'Batalla de Junín',                            'NO_RECUPERABLE'),
            (datetime.date(2026, 8, 30), 'Santa Rosa de Lima',                          'NO_RECUPERABLE'),
            (datetime.date(2026, 10, 8), 'Combate de Angamos',                          'NO_RECUPERABLE'),
            (datetime.date(2026, 11, 1), 'Día de Todos los Santos',                     'NO_RECUPERABLE'),
            (datetime.date(2026, 12, 8), 'Inmaculada Concepción',                       'NO_RECUPERABLE'),
            (datetime.date(2026, 12, 9), 'Batalla de Ayacucho',                         'NO_RECUPERABLE'),
            (datetime.date(2025, 12, 25),'Navidad 2025',                                'NO_RECUPERABLE'),
        ]

        created = 0
        for fecha, nombre, tipo in feriados:
            _, c = FeriadoCalendario.objects.get_or_create(
                fecha=fecha,
                defaults={'nombre': nombre, 'tipo': tipo}
            )
            if c:
                created += 1
            elif force:
                FeriadoCalendario.objects.filter(fecha=fecha).update(nombre=nombre, tipo=tipo)

        self.stdout.write(f"  Feriados: {created} nuevos insertados.")

    # ─────────────────────────────────────────────────────────
    # HOMOLOGACIÓN DE CÓDIGOS (Reloj → Tareo → Roster)
    # ─────────────────────────────────────────────────────────

    def _seed_homologaciones(self, force):
        from tareo.models import HomologacionCodigo

        self.stdout.write("\n▸ Tabla de homologación de códigos...")

        # Formato: (codigo_origen, codigo_tareo, codigo_roster, descripcion,
        #           tipo_evento, signo, cuenta_asist, genera_he, es_numerico, prioridad)
        homologaciones = [
            # ── Papeletas (prioridad 1) ─────────────────────────────────────
            ('CHE',  'CHE',  '',   'Compensación por Horario Extendido',    'COMPENSACION',     '+', True,  False, False,  1),
            ('CPF',  'CPF',  '',   'Compensación por Feriado',              'COMPENSACION',     '+', True,  False, False,  1),
            ('CDT',  'CDT',  '',   'Compensación de Día por Trabajo',       'COMPENSACION',     '+', True,  False, False,  1),
            # ── Descansos / DL ──────────────────────────────────────────────
            ('B',    'DL',   'DL', 'Bajadas (día libre)',                   'DESCANSO',         '+', True,  False, False,  3),
            ('BA',   'DLA',  'DL', 'Bajadas Acumuladas',                    'DESCANSO',         '+', True,  False, False,  3),
            # ── Vacaciones ──────────────────────────────────────────────────
            ('V',    'VAC',  'V',  'Vacaciones',                            'VACACIONES',       '+', True,  False, False,  3),
            # ── Licencias ───────────────────────────────────────────────────
            ('LF',   'LF',   '',   'Licencia por Fallecimiento',            'PERMISO',          '+', True,  False, False,  2),
            ('LP',   'LP',   '',   'Licencia por Paternidad',               'PERMISO',          '+', True,  False, False,  2),
            ('LCG',  'LCG',  '',   'Licencia con Goce',                     'PERMISO',          '+', True,  False, False,  2),
            ('LSG',  'LSG',  '',   'Licencia sin Goce (descuenta sueldo)',  'PERMISO',          '-', False, False, False,  2),
            ('CT',   'A',    'T',  'Comisión de Trabajo (cuenta asistencia)','ASISTENCIA',      '+', True,  False, False,  2),
            ('ATM',  'A',    '',   'Atención Médica',                       'PERMISO',          '+', True,  False, False,  2),
            # ── Descanso médico ─────────────────────────────────────────────
            ('DM',   'DM',   '',   'Descanso Médico',                       'DESCANSO_MEDICO',  '+', True,  False, False,  2),
            # ── Feriados ────────────────────────────────────────────────────
            ('FR',   'FR',   '',   'Feriado No Recuperable (no trabajó)',   'FERIADO',          '+', True,  False, False,  5),
            ('FL',   'FL',   '',   'Feriado Laborado (HE 100%)',            'FERIADO_LABORADO', '+', True,  True,  False,  5),
            # ── Suspensiones ────────────────────────────────────────────────
            ('AS',   'F',    '',   'Amonestación por Suspensión',          'SUSPENSION',       '-', False, False, False,  2),
            ('SAI',  'F',    '',   'Suspensión por Acto Inseguro',          'SUSPENSION',       '-', False, False, False,  2),
            # ── Teletrabajo ─────────────────────────────────────────────────
            ('TR',   'TR',   'TR', 'Trabajo Remoto',                        'TELETRABAJO',      '+', True,  True,  False, 10),
            # ── Asistencia con marcación ────────────────────────────────────
            ('>0',   'A',    'T',  'Asistencia — valor numérico de horas',  'ASISTENCIA',       '+', True,  True,  True,  10),
            ('SS',   'A',    'T',  'Sin marca (entrada o salida) = presente','ASISTENCIA',      '+', True,  True,  False, 10),
            # ── Sin registro ────────────────────────────────────────────────
            ('0',    'FALTA','',   'Cero horas = no asistió',               'AUSENCIA',         '-', False, False, True,  99),
            ('BLANK','F',    '',   'En blanco (sin dato) = falta',          'AUSENCIA',         '-', False, False, False, 99),
        ]

        created = updated = 0
        for row in homologaciones:
            (cod_origen, cod_tareo, cod_roster, desc,
             tipo, signo, cuenta, genera_he, es_num, prio) = row

            defaults = {
                'codigo_tareo': cod_tareo,
                'codigo_roster': cod_roster,
                'descripcion': desc,
                'tipo_evento': tipo,
                'signo': signo,
                'cuenta_asistencia': cuenta,
                'genera_he': genera_he,
                'es_numerico': es_num,
                'prioridad': prio,
            }
            obj, c = HomologacionCodigo.objects.get_or_create(
                codigo_origen=cod_origen,
                defaults=defaults,
            )
            if c:
                created += 1
            elif force:
                for k, v in defaults.items():
                    setattr(obj, k, v)
                obj.save()
                updated += 1

        self.stdout.write(f"  Homologaciones: {created} creadas, {updated} actualizadas.")
