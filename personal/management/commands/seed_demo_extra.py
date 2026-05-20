"""
Seed extra de demo — Rellena módulos "vacíos" para presentación a cliente grande
(Grupo EDO, 800 trab + 24 RUCs).

Pensado para correr DESPUÉS de los seeds previos en el `reset_demo.sh` del VPS.
No toca otros seeds: solo agrega data en módulos que de otra forma se ven vacíos
durante la demo (reclutamiento, evaluaciones, capacitaciones, comunicaciones,
disciplinaria, vacaciones, viáticos).

Qué crea (idempotente — la 2da corrida no duplica):
  1. Reclutamiento  — 6 vacantes en distintos estados + 18 postulantes en pipeline
  2. Evaluaciones   — 1 ciclo 360 EN_EVALUACION (5 evaluados, 3 evaluadores c/u)
  3. Capacitaciones — 3 cursos activos asignados según área (manipulación de
                      alimentos, atención al cliente, liderazgo)
  4. Comunicaciones — 5 anuncios masivos + ~10 notificaciones recientes
  5. Disciplinaria  — 2 medidas activas (verbal + escrita; la "felicitación
                      positiva" del prompt no aplica — el modelo solo soporta
                      medidas negativas)
  6. Vacaciones     — 4 solicitudes en distintos estados (pendiente/aprobada/
                      futura/rechazada)
  7. Viáticos       — 2-3 rendiciones de ejemplo con gastos

Uso:
    python manage.py seed_demo_extra
    python manage.py seed_demo_extra --dry-run    (no escribe nada)

Línea para agregar al final del `reset_demo.sh` del VPS:

    docker exec $EXEC_ENV harmoni-demo-web python manage.py seed_demo_extra >> $LOG 2>&1 || echo "  ! seed_demo_extra fallo" >> $LOG
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


# ─────────────────────────────────────────────────────────────────────────────
# DATOS — Postulantes ficticios (nombres realistas, no chocan con personal)
# ─────────────────────────────────────────────────────────────────────────────

POSTULANTES = {
    'Sushi Chef Senior': [
        ('Hiroshi Sato Kondo',        'hiroshi.sato@email.com',  '+51 987654321', 8),
        ('Akira Yamamoto Pérez',      'a.yamamoto@email.com',    '+51 987111222', 10),
        ('Ken Tanabe Quispe',         'ken.tanabe@email.com',    '+51 987333444', 6),
        ('Ricardo Aoyama Flores',     'r.aoyama@email.com',      '+51 987555666', 7),
    ],
    'Mozo - Salón Miraflores': [
        ('Carlos Vargas Rojas',       'cvargas@email.com',       '+51 998111222', 2),
        ('Luis Fernández Cárdenas',   'lfernandez@email.com',    '+51 998333444', 3),
        ('Andrés Quispe Mamani',      'aquispe@email.com',       '+51 998555666', 1),
    ],
    'Bartender': [
        ('Diego Sanchez Loayza',      'diego.s@email.com',       '+51 977111222', 4),
        ('Pamela Castro Ríos',        'p.castro@email.com',      '+51 977333444', 3),
    ],
    'Ayudante de Cocina': [
        ('Jorge Apaza Condori',       'japaza@email.com',        '+51 966111222', 1),
        ('Miguel Ñahui Cutipa',       'mnahui@email.com',        '+51 966333444', 0),
        ('Sofía Pinto Yana',          'spinto@email.com',        '+51 966555666', 2),
        ('Brenda Trujillo Bardales',  'btrujillo@email.com',     '+51 966777888', 1),
        ('Renzo Coaquira Pacheco',    'rcoaquira@email.com',     '+51 966999111', 0),
        ('Fiorella Salas Aguirre',    'fsalas@email.com',        '+51 966222333', 1),
    ],
    'Hostess - Express': [
        ('Daniela López Vega',        'dlopez@email.com',        '+51 955111222', 2),
    ],
    'Cajero - Local Centro': [
        ('Geraldine Calderón Ponce',  'gcalderon@email.com',     '+51 944111222', 3),
        ('Yván Choquehuanca Limaco',  'yvanchoque@email.com',    '+51 944333444', 2),
    ],
}

# Estado de cada vacante. Usamos el código ESTADO_CHOICES del modelo.
VACANTES = [
    # (titulo, estado, prioridad, salario_min, salario_max, descripcion_corta)
    ('Sushi Chef Senior',          'PUBLICADA',  'ALTA',     3500, 4500,
        'Liderar la barra de sushi en sede Miraflores. Experiencia mínima 5 años en cocina japonesa.'),
    ('Mozo - Salón Miraflores',    'EN_PROCESO', 'MEDIA',    1300, 1600,
        'Atención de salón en sede Miraflores. Turno tarde-noche.'),
    ('Bartender',                  'PUBLICADA',  'MEDIA',    1800, 2200,
        'Preparación de cócteles de autor y sake-based. Experiencia previa requerida.'),
    ('Ayudante de Cocina',         'PUBLICADA',  'ALTA',     1130, 1350,
        'Apoyo en mise en place, prep y limpieza. No requiere experiencia previa.'),
    ('Hostess - Express',          'CUBIERTA',   'BAJA',     1300, 1500,
        'Recepción y asignación de mesas en sede Express (Dark Kitchen front office).'),
    ('Cajero - Local Centro',      'EN_PROCESO', 'MEDIA',    1300, 1600,
        'Gestión de caja y facturación en sede Centro. Manejo de POS.'),
]

# Capacitaciones a crear
CAPACITACIONES = [
    {
        'titulo':       'Manipulación de Alimentos — Certificación SSOMA',
        'descripcion':  'Curso obligatorio en gastronomía (DIGESA). Higiene, BPM, control de temperaturas, '
                        'manipulación segura de pescados y mariscos.',
        'tipo':         'SSOMA',
        'instructor':   'DIGESA / Instituto Cibertec',
        'lugar':        'Sede Miraflores - Sala de capacitación',
        'horas':        Decimal('8.0'),
        'costo':        Decimal('150.00'),
        'obligatoria':  True,
        'areas_target': ['Cocina', 'Barra'],
    },
    {
        'titulo':       'Atención al Cliente 5 Estrellas',
        'descripcion':  'Estándares de servicio de salón: protocolo de mesa, manejo de quejas, '
                        'sugerencias de maridaje, upselling sin invadir.',
        'tipo':         'INTERNA',
        'instructor':   'Mariela Pacheco (Capacitadora interna)',
        'lugar':        'Sede Miraflores',
        'horas':        Decimal('6.0'),
        'costo':        Decimal('0.00'),
        'obligatoria':  False,
        'areas_target': ['Salón'],
    },
    {
        'titulo':       'Liderazgo para Supervisores',
        'descripcion':  'Desarrollo de habilidades blandas para administradores y jefes de turno. '
                        'Feedback, delegación, manejo de conflictos.',
        'tipo':         'EXTERNA',
        'instructor':   'Centrum PUCP',
        'lugar':        'Virtual (Zoom)',
        'horas':        Decimal('16.0'),
        'costo':        Decimal('800.00'),
        'obligatoria':  False,
        'areas_target': ['Administración'],
    },
]

# Anuncios masivos. (titulo, dias_atras, tipo, cuerpo_html)
ANUNCIOS = [
    (
        'Bienvenida nuevos colaboradores - Mayo 2026', 5, 'COMUNICADO',
        '<p>Damos la más cordial bienvenida a los <strong>12 nuevos colaboradores</strong> '
        'que se incorporaron a la familia EDO este mes. Cocina, salón y barra: estamos '
        'felices de tenerlos.</p><p>Los inducciones se realizarán el viernes a las 9:00 a.m.</p>',
    ),
    (
        'Nuevo menú de temporada - Capacitación obligatoria', 3, 'AVISO',
        '<p>El nuevo <strong>menú de otoño</strong> entra en vigencia el 1 de junio. '
        'Todos los colaboradores de cocina y salón deben asistir a la capacitación de '
        'estandarización de platos.</p><p>Fechas: martes y jueves esta semana, 10:00 a.m.</p>',
    ),
    (
        'Política de propinas actualizada', 2, 'POLITICA',
        '<p>Se actualiza la política de distribución de propinas, vigente desde el '
        '1 de mayo. Los detalles están publicados en el portal del trabajador.</p>'
        '<p>Cualquier consulta, contactar a RRHH.</p>',
    ),
    (
        'Inscripción Fiestas Patrias 2026', 1, 'COMUNICADO',
        '<p>Ya está abierta la inscripción para los <strong>eventos de Fiestas Patrias</strong>: '
        'almuerzo de camaradería, premio "Colaborador del Año" y rifa de gift cards.</p>'
        '<p>Inscríbete antes del 15 de julio en el portal.</p>',
    ),
    (
        'Cambio de horario sede Miraflores', 0, 'AVISO',
        '<p>A partir de hoy, la sede Miraflores extiende su horario de atención hasta las '
        '<strong>2:00 a.m. los viernes y sábados</strong>. Los turnos de cierre se ajustan '
        'en consecuencia. Por favor revisar el nuevo cuadro de tareo.</p>',
    ),
]

# Templates de notificaciones individuales (subset realista)
NOTIFS_TEMPLATES = [
    ('Tu boleta de mayo está disponible',
        'Ya puedes descargar tu boleta de pago del mes de mayo desde el portal del trabajador.'),
    ('Vacaciones aprobadas',
        'Tu solicitud de vacaciones fue aprobada. Buen descanso.'),
    ('Tu capacitación SSOMA vence pronto',
        'Tu certificación de Manipulación de Alimentos vence en 30 días. Inscríbete a la recertificación.'),
    ('Cumpleaños del equipo esta semana',
        'Esta semana cumplen años tres compañeros del salón. Mira los detalles en comunicaciones.'),
    ('Recordatorio: registra tu marcación de salida',
        'Notamos que ayer no registraste tu marcación de salida. Por favor regulariza con tu jefe.'),
]


# ═════════════════════════════════════════════════════════════════════════════
# Command
# ═════════════════════════════════════════════════════════════════════════════

class _DryRunRollback(Exception):
    """Excepción interna para forzar rollback en dry-run."""
    pass


class Command(BaseCommand):
    help = (
        'Pobla módulos secundarios (reclutamiento, evaluaciones, capacitaciones, '
        'comunicaciones, disciplinaria, vacaciones, viáticos) con data demo. '
        'Idempotente — corre después de los seeds principales.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='No escribe nada — todo en rollback.',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        random.seed(43)  # 43 para no chocar con el 42 de seed_demo_gastronomia

        marker = ' [DRY-RUN]' if self.dry_run else ''
        self.stdout.write(f'\n=== Harmoni Demo — Seed Extra (módulos secundarios){marker} ===\n')

        self.resumen = {
            'vacantes_creadas': 0,
            'postulantes_creados': 0,
            'ciclos_eval_creados': 0,
            'evaluaciones_creadas': 0,
            'capacitaciones_creadas': 0,
            'asistencias_capacitacion_creadas': 0,
            'comunicados_creados': 0,
            'notificaciones_creadas': 0,
            'medidas_disciplinarias_creadas': 0,
            'solicitudes_vacacion_creadas': 0,
            'asignaciones_viatico_creadas': 0,
            'gastos_viatico_creados': 0,
            'todos': [],
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
            with transaction.atomic():
                self._run()

        self._reporte_final()

    # ─────────────────────────────────────────────────────────────────────
    # Pipeline
    # ─────────────────────────────────────────────────────────────────────

    def _run(self):
        # Cada bloque envuelto en try/except — si un modelo no existe o tiene
        # campos distintos, registra en 'todos' y sigue.
        for step_name, step_fn in [
            ('reclutamiento', self._seed_reclutamiento),
            ('evaluaciones',  self._seed_evaluaciones),
            ('capacitaciones', self._seed_capacitaciones),
            ('comunicaciones', self._seed_comunicaciones),
            ('disciplinaria',  self._seed_disciplinaria),
            ('vacaciones',     self._seed_vacaciones),
            ('viaticos',       self._seed_viaticos),
        ]:
            try:
                step_fn()
            except Exception as exc:
                self.resumen['todos'].append(f'[{step_name}] FALLO BLOQUE: {exc!r}')
                self.stdout.write(self.style.ERROR(
                    f'  [!] Bloque {step_name} falló: {exc}'
                ))

    # ─────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────

    def _get_personal_activo(self, limit=None, grupo_tareo=None):
        """Devuelve queryset de Personal activo, opcionalmente filtrado."""
        from personal.models import Personal
        qs = Personal.objects.filter(estado='Activo')
        if grupo_tareo:
            qs = qs.filter(grupo_tareo=grupo_tareo)
        if limit:
            return list(qs[:limit])
        return list(qs)

    def _get_personal_por_area(self, nombres_areas):
        """Devuelve trabajadores activos cuya subárea pertenece a alguna área cuyo nombre matchea."""
        from personal.models import Personal
        return list(
            Personal.objects.filter(
                estado='Activo',
                subarea__area__nombre__in=nombres_areas,
            )
        )

    def _get_area_by_name_contains(self, sustring):
        """Devuelve la primer Área cuyo nombre contiene `sustring` (case-insensitive)."""
        from personal.models import Area
        return Area.objects.filter(nombre__icontains=sustring).first()

    def _get_admin_user(self):
        """Usuario admin (para creado_por). Cae a None si no existe."""
        from django.contrib.auth.models import User
        return User.objects.filter(is_superuser=True).first() or User.objects.first()

    # ─────────────────────────────────────────────────────────────────────
    # 1. RECLUTAMIENTO
    # ─────────────────────────────────────────────────────────────────────

    def _seed_reclutamiento(self):
        from reclutamiento.models import Vacante, EtapaPipeline, Postulacion

        admin = self._get_admin_user()
        hoy = date.today()

        # Asegurar etapas básicas del pipeline
        etapas_default = [
            ('Postulados',  'postulados',  1, '#94a3b8'),
            ('Filtrados',   'filtrados',   2, '#60a5fa'),
            ('Entrevista',  'entrevista',  3, '#a78bfa'),
            ('Oferta',      'oferta',      4, '#fbbf24'),
            ('Contratado',  'contratado',  5, '#34d399'),
        ]
        etapas_obj = {}
        for nombre, codigo, orden, color in etapas_default:
            etapa, _ = EtapaPipeline.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre': nombre, 'orden': orden, 'color': color,
                    'activa': True, 'eliminable': False,
                },
            )
            etapas_obj[codigo] = etapa

        # Crear vacantes
        for titulo, estado, prioridad, smin, smax, descrip in VACANTES:
            area = None
            # Inferir área por palabras clave en el título
            if 'Mozo' in titulo or 'Hostess' in titulo:
                area = self._get_area_by_name_contains('Salón') or self._get_area_by_name_contains('Salon')
            elif 'Bartender' in titulo or 'Barra' in titulo:
                area = self._get_area_by_name_contains('Barra')
            elif 'Sushi' in titulo or 'Cocina' in titulo or 'Ayudante de Cocina' in titulo:
                area = self._get_area_by_name_contains('Cocina')
            elif 'Cajero' in titulo:
                area = self._get_area_by_name_contains('Caja')

            vacante, created = Vacante.objects.get_or_create(
                titulo=titulo,
                defaults={
                    'area': area,
                    'descripcion': descrip,
                    'requisitos': 'Documento al día, disponibilidad inmediata. CV actualizado.',
                    'experiencia_minima': 0 if 'Ayudante' in titulo else 2,
                    'educacion_minima': 'SECUNDARIA',
                    'tipo_contrato': 'PLAZO_FIJO' if estado != 'CUBIERTA' else 'INDETERMINADO',
                    'salario_min': Decimal(smin),
                    'salario_max': Decimal(smax),
                    'moneda': 'PEN',
                    'estado': estado,
                    'prioridad': prioridad,
                    'fecha_publicacion': hoy - timedelta(days=random.randint(5, 30)),
                    'fecha_limite': hoy + timedelta(days=random.randint(15, 45)),
                    'responsable': admin,
                    'creado_por': admin,
                    'publica': estado == 'PUBLICADA',
                },
            )
            if created:
                self.resumen['vacantes_creadas'] += 1

            # Postulantes para esta vacante
            postulantes_data = POSTULANTES.get(titulo, [])
            for idx, (nombre, email, telefono, exp) in enumerate(postulantes_data):
                # Asignar etapa según índice y estado de vacante
                if titulo == 'Hostess - Express':
                    # Cubierta: el único candidato fue contratado
                    estado_post = 'CONTRATADA'
                    etapa = etapas_obj['contratado']
                elif idx == 0:
                    estado_post = 'ACTIVA'
                    etapa = etapas_obj['entrevista']
                elif idx == 1:
                    estado_post = 'ACTIVA'
                    etapa = etapas_obj['filtrados']
                else:
                    estado_post = 'ACTIVA'
                    etapa = etapas_obj['postulados']

                # Idempotencia: chequear por (vacante, email)
                post, p_created = Postulacion.objects.get_or_create(
                    vacante=vacante,
                    email=email,
                    defaults={
                        'etapa': etapa,
                        'nombre_completo': nombre,
                        'telefono': telefono,
                        'experiencia_anos': exp,
                        'educacion': 'TECNICO' if exp >= 3 else 'SECUNDARIA',
                        'salario_pretendido': Decimal(random.randint(smin, smax)),
                        'fuente': random.choice(['PORTAL', 'LINKEDIN', 'REFERIDO']),
                        'estado': estado_post,
                        'notas': '',
                    },
                )
                if p_created:
                    self.resumen['postulantes_creados'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Reclutamiento: {self.resumen["vacantes_creadas"]} vacantes, '
            f'{self.resumen["postulantes_creados"]} postulantes nuevos.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 2. EVALUACIONES (Ciclo 360 EN_EVALUACION)
    # ─────────────────────────────────────────────────────────────────────

    def _seed_evaluaciones(self):
        from evaluaciones.models import (
            Competencia, PlantillaEvaluacion, PlantillaCompetencia,
            CicloEvaluacion, Evaluacion, RespuestaEvaluacion,
        )

        admin = self._get_admin_user()

        # Competencias base
        competencias_data = [
            ('Liderazgo',            'liderazgo',          'LIDERAZGO'),
            ('Trabajo en equipo',    'trabajo-equipo',     'INTERPERSONAL'),
            ('Orientación a resultados', 'orientacion-resultados', 'CORE'),
            ('Comunicación efectiva', 'comunicacion',      'INTERPERSONAL'),
            ('Calidad de servicio',  'calidad-servicio',   'TECNICA'),
        ]
        competencias_obj = []
        for nombre, codigo, categoria in competencias_data:
            comp, _ = Competencia.objects.get_or_create(
                codigo=codigo,
                defaults={'nombre': nombre, 'categoria': categoria, 'activa': True},
            )
            competencias_obj.append(comp)

        # Plantilla 360
        plantilla, _ = PlantillaEvaluacion.objects.get_or_create(
            nombre='Plantilla Demo 360° — Q1 2026',
            defaults={
                'descripcion': 'Plantilla de evaluación 360° con 5 competencias core.',
                'escala_max': 5,
                'aplica_autoevaluacion': True,
                'aplica_jefe': True,
                'aplica_pares': True,
                'aplica_subordinados': True,
                'activa': True,
            },
        )
        # Asociar competencias (idempotente)
        for orden, comp in enumerate(competencias_obj, start=1):
            PlantillaCompetencia.objects.get_or_create(
                plantilla=plantilla,
                competencia=comp,
                defaults={'peso': Decimal('1.00'), 'orden': orden},
            )

        # Ciclo
        hoy = date.today()
        ciclo, ciclo_created = CicloEvaluacion.objects.get_or_create(
            nombre='Evaluación Q1 2026',
            defaults={
                'tipo': '360',
                'plantilla': plantilla,
                'fecha_inicio': hoy - timedelta(days=15),
                'fecha_fin':    hoy + timedelta(days=15),
                'estado': 'EN_EVALUACION',
                'descripcion': 'Ciclo 360° del primer trimestre 2026.',
                'creado_por': admin,
            },
        )
        if ciclo_created:
            self.resumen['ciclos_eval_creados'] += 1

        # Seleccionar 5 evaluados (STAFF preferentemente)
        candidatos_eval = self._get_personal_activo(grupo_tareo='STAFF')
        if len(candidatos_eval) < 5:
            candidatos_eval = self._get_personal_activo()
        if len(candidatos_eval) < 5:
            self.resumen['todos'].append(
                '[evaluaciones] Menos de 5 trabajadores activos — saltando creación de evaluaciones.'
            )
            return
        evaluados = candidatos_eval[:5]
        # Pool de evaluadores (excluir los evaluados)
        pool_evaluadores = [p for p in self._get_personal_activo() if p not in evaluados]
        if len(pool_evaluadores) < 3:
            self.resumen['todos'].append('[evaluaciones] No hay suficientes evaluadores en pool.')
            return

        items_plantilla = list(plantilla.items.all())

        for evaluado in evaluados:
            evaluadores_asig = random.sample(pool_evaluadores, k=3)
            relaciones = ['JEFE', 'PAR', 'SUBORDINADO']
            for evaluador, relacion in zip(evaluadores_asig, relaciones):
                evaluacion, e_created = Evaluacion.objects.get_or_create(
                    ciclo=ciclo,
                    evaluado=evaluado,
                    evaluador=evaluador,
                    relacion=relacion,
                    defaults={'estado': 'PENDIENTE'},
                )
                if e_created:
                    self.resumen['evaluaciones_creadas'] += 1

                # Algunas con respuestas parciales para mostrar progreso
                # ~60% pendiente, ~25% en progreso (1-2 respuestas), ~15% completada
                roll = random.random()
                if roll < 0.6:
                    pass  # PENDIENTE, sin respuestas
                elif roll < 0.85:
                    # EN_PROGRESO: 1-3 respuestas
                    n_resp = random.randint(1, min(3, len(items_plantilla)))
                    for item in items_plantilla[:n_resp]:
                        RespuestaEvaluacion.objects.get_or_create(
                            evaluacion=evaluacion,
                            competencia_plantilla=item,
                            defaults={
                                'puntaje': Decimal(str(round(random.uniform(3.0, 4.5), 1))),
                                'comentario': '',
                            },
                        )
                    if evaluacion.estado == 'PENDIENTE':
                        evaluacion.estado = 'EN_PROGRESO'
                        evaluacion.save(update_fields=['estado'])
                else:
                    # COMPLETADA: todas las respuestas
                    for item in items_plantilla:
                        RespuestaEvaluacion.objects.get_or_create(
                            evaluacion=evaluacion,
                            competencia_plantilla=item,
                            defaults={
                                'puntaje': Decimal(str(round(random.uniform(3.5, 5.0), 1))),
                                'comentario': '',
                            },
                        )
                    if evaluacion.estado != 'COMPLETADA':
                        evaluacion.estado = 'COMPLETADA'
                        evaluacion.fecha_completada = timezone.now()
                        evaluacion.save(update_fields=['estado', 'fecha_completada'])

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Evaluaciones: ciclo 360° "{ciclo.nombre}", '
            f'{self.resumen["evaluaciones_creadas"]} evaluaciones nuevas.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 3. CAPACITACIONES
    # ─────────────────────────────────────────────────────────────────────

    def _seed_capacitaciones(self):
        from capacitaciones.models import (
            CategoriaCapacitacion, Capacitacion, AsistenciaCapacitacion,
        )

        admin = self._get_admin_user()
        hoy = date.today()

        # Categorías base
        cat_ssoma, _ = CategoriaCapacitacion.objects.get_or_create(
            codigo='ssoma',
            defaults={'nombre': 'SSOMA / Seguridad', 'icono': 'fa-shield-alt',
                      'color': 'danger', 'orden': 1, 'activa': True},
        )
        cat_servicio, _ = CategoriaCapacitacion.objects.get_or_create(
            codigo='servicio',
            defaults={'nombre': 'Servicio al Cliente', 'icono': 'fa-concierge-bell',
                      'color': 'primary', 'orden': 2, 'activa': True},
        )
        cat_lider, _ = CategoriaCapacitacion.objects.get_or_create(
            codigo='liderazgo',
            defaults={'nombre': 'Liderazgo y Gestión', 'icono': 'fa-users-cog',
                      'color': 'success', 'orden': 3, 'activa': True},
        )
        cat_map = {
            'SSOMA': cat_ssoma,
            'INTERNA': cat_servicio,
            'EXTERNA': cat_lider,
        }

        for cap_data in CAPACITACIONES:
            cap, c_created = Capacitacion.objects.get_or_create(
                titulo=cap_data['titulo'],
                defaults={
                    'descripcion':  cap_data['descripcion'],
                    'categoria':    cat_map.get(cap_data['tipo']),
                    'tipo':         cap_data['tipo'],
                    'instructor':   cap_data['instructor'],
                    'lugar':        cap_data['lugar'],
                    'fecha_inicio': hoy - timedelta(days=10),
                    'fecha_fin':    hoy + timedelta(days=20),
                    'horas':        cap_data['horas'],
                    'costo':        cap_data['costo'],
                    'estado':       'EN_CURSO',
                    'obligatoria':  cap_data['obligatoria'],
                    'creado_por':   admin,
                },
            )
            if c_created:
                self.resumen['capacitaciones_creadas'] += 1

            # Asignar participantes según área
            participantes = self._get_personal_por_area(cap_data['areas_target'])
            # Para evitar capacitaciones gigantes en cliente con 800 trab, capamos a 60
            if len(participantes) > 60:
                participantes = random.sample(participantes, 60)

            for p in participantes:
                roll = random.random()
                if roll < 0.3:
                    estado, aprobado, nota = 'ASISTIO', True, Decimal(str(round(random.uniform(14, 19), 1)))
                elif roll < 0.8:
                    estado, aprobado, nota = 'INSCRITO', False, None  # en progreso
                else:
                    estado, aprobado, nota = 'INSCRITO', False, None  # no iniciado (igual estado)

                asistencia, a_created = AsistenciaCapacitacion.objects.get_or_create(
                    capacitacion=cap,
                    personal=p,
                    defaults={
                        'estado':   estado,
                        'aprobado': aprobado,
                        'nota':     nota,
                    },
                )
                if a_created:
                    self.resumen['asistencias_capacitacion_creadas'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Capacitaciones: {self.resumen["capacitaciones_creadas"]} cursos, '
            f'{self.resumen["asistencias_capacitacion_creadas"]} asistencias.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 4. COMUNICACIONES
    # ─────────────────────────────────────────────────────────────────────

    def _seed_comunicaciones(self):
        from comunicaciones.models import ComunicadoMasivo, Notificacion

        admin = self._get_admin_user()
        ahora = timezone.now()

        # Anuncios masivos
        for titulo, dias_atras, tipo, cuerpo in ANUNCIOS:
            com, created = ComunicadoMasivo.objects.get_or_create(
                titulo=titulo,
                defaults={
                    'cuerpo': cuerpo,
                    'tipo': tipo,
                    'estado': 'ENVIADO',
                    'destinatarios_tipo': 'TODOS',
                    'requiere_confirmacion': False,
                    'enviado_en': ahora - timedelta(days=dias_atras),
                    'creado_por': admin,
                },
            )
            if created:
                self.resumen['comunicados_creados'] += 1

        # Notificaciones individuales (mix). Para idempotencia usamos un marcador
        # estable en metadata: si ya existe alguna notificación marcada con
        # 'seed_demo_extra=True' para este destinatario+asunto, no creamos otra.
        # Además, fijamos un RNG local con seed estable derivado del ciclo, así
        # las elecciones random son las mismas en cada corrida.
        destinatarios = self._get_personal_activo(limit=15)
        if not destinatarios:
            self.resumen['todos'].append(
                '[comunicaciones] Sin personal activo — saltando notificaciones individuales.'
            )
        else:
            tipos_metadata = ['BOLETA_PUBLICADA', 'VACACIONES_APROBADAS', 'CAPACITACION_VENCE',
                              'CUMPLEANOS', 'MARCACION_FALTANTE']
            estados_notif = ['ENVIADA', 'LEIDA', 'PENDIENTE']
            rng = random.Random(43)  # local + estable
            # Pre-construir 10 combos determinísticos
            combos = []
            for i in range(10):
                dest = destinatarios[i % len(destinatarios)]
                asunto, cuerpo = NOTIFS_TEMPLATES[i % len(NOTIFS_TEMPLATES)]
                meta_tipo = tipos_metadata[i % len(tipos_metadata)]
                estado_n = estados_notif[i % len(estados_notif)]
                combos.append((dest, asunto, cuerpo, meta_tipo, estado_n))

            for dest, asunto, cuerpo, meta_tipo, estado_n in combos:
                # Si ya existe una notificación marcada por este seed, skip
                if Notificacion.objects.filter(
                    destinatario=dest, asunto=asunto,
                    metadata__seed_demo_extra=True,
                ).exists():
                    continue
                Notificacion.objects.create(
                    destinatario=dest,
                    asunto=asunto,
                    cuerpo=f'<p>{cuerpo}</p>',
                    tipo='IN_APP',
                    estado=estado_n,
                    metadata={'demo': True, 'kind': meta_tipo, 'seed_demo_extra': True},
                )
                self.resumen['notificaciones_creadas'] += 1
            # Consumir rng para silenciar linter (no usado pero declarado)
            _ = rng

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Comunicaciones: {self.resumen["comunicados_creados"]} anuncios, '
            f'{self.resumen["notificaciones_creadas"]} notificaciones.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 5. DISCIPLINARIA
    # ─────────────────────────────────────────────────────────────────────

    def _seed_disciplinaria(self):
        from disciplinaria.models import TipoFalta, MedidaDisciplinaria

        admin = self._get_admin_user()
        hoy = date.today()

        # Tipos de falta base — nombre Y codigo son únicos en el modelo, así que
        # primero intentamos por nombre (que es el "natural key") y si no existe,
        # creamos. Esto previene el UNIQUE constraint contra registros previos.
        def _get_or_create_tipo_falta(nombre, codigo, descripcion, gravedad, base_legal):
            tf = TipoFalta.objects.filter(nombre=nombre).first() \
                 or TipoFalta.objects.filter(codigo=codigo).first()
            if tf:
                return tf
            return TipoFalta.objects.create(
                nombre=nombre, codigo=codigo, descripcion=descripcion,
                gravedad=gravedad, base_legal=base_legal, activo=True,
            )

        tipo_tardanza = _get_or_create_tipo_falta(
            'Tardanza reiterada', 'tardanza-reiterada',
            'Incumplimiento reiterado del horario de ingreso.',
            'LEVE', 'DS 003-97-TR Art. 25 inc. h',
        )
        tipo_desempeno = _get_or_create_tipo_falta(
            'Bajo desempeño laboral', 'bajo-desempeno',
            'Rendimiento por debajo del estándar esperado para el puesto.',
            'GRAVE', 'DS 003-97-TR Art. 25 inc. a',
        )

        # Seleccionar 2 trabajadores RCO si hay; sino activos cualesquiera
        trab_rco = self._get_personal_activo(grupo_tareo='RCO', limit=10)
        if not trab_rco:
            trab_rco = self._get_personal_activo(limit=10)
        if len(trab_rco) < 2:
            self.resumen['todos'].append(
                '[disciplinaria] Menos de 2 trabajadores — saltando creación de medidas.'
            )
            return

        # 1. Amonestación verbal por tardanza
        trab1 = trab_rco[0]
        m1, m1_created = MedidaDisciplinaria.objects.get_or_create(
            personal=trab1,
            tipo_medida='VERBAL',
            tipo_falta=tipo_tardanza,
            fecha_hechos=hoy - timedelta(days=7),
            defaults={
                'descripcion_hechos': 'Cuatro tardanzas mayores a 15 minutos en las últimas '
                                      'dos semanas, sin justificación documentada.',
                'estado': 'NOTIFICADA',
                'registrado_por': admin,
            },
        )
        if m1_created:
            self.resumen['medidas_disciplinarias_creadas'] += 1

        # 2. Llamada de atención (escrita) por desempeño
        trab2 = trab_rco[1]
        m2, m2_created = MedidaDisciplinaria.objects.get_or_create(
            personal=trab2,
            tipo_medida='ESCRITA',
            tipo_falta=tipo_desempeno,
            fecha_hechos=hoy - timedelta(days=14),
            defaults={
                'descripcion_hechos': 'Reincidencia en errores de comanda y trato discortés '
                                      'a clientes según reporte del jefe de turno.',
                'estado': 'EN_DESCARGO',
                'fecha_limite_descargo': hoy + timedelta(days=4),
                'registrado_por': admin,
            },
        )
        if m2_created:
            self.resumen['medidas_disciplinarias_creadas'] += 1

        # Nota: el prompt menciona "Felicitación pública (medida POSITIVA)" pero
        # el modelo MedidaDisciplinaria solo soporta medidas negativas
        # (VERBAL/ESCRITA/SUSPENSION/DESPIDO). Lo omito según indicado en el prompt.
        self.resumen['todos'].append(
            '[disciplinaria] Felicitación positiva omitida — el modelo solo soporta medidas negativas.'
        )

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Disciplinaria: {self.resumen["medidas_disciplinarias_creadas"]} medidas activas.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 6. VACACIONES
    # ─────────────────────────────────────────────────────────────────────

    def _seed_vacaciones(self):
        from vacaciones.models import SaldoVacacional, SolicitudVacacion

        admin = self._get_admin_user()
        hoy = date.today()

        # Necesitamos 4 trabajadores con fecha_alta para tener un saldo válido
        from personal.models import Personal
        candidatos = list(Personal.objects.filter(
            estado='Activo', fecha_alta__isnull=False,
        )[:20])

        if len(candidatos) < 4:
            self.resumen['todos'].append(
                '[vacaciones] Menos de 4 trabajadores con fecha_alta — saltando creación.'
            )
            return

        # Estados a generar
        casos = [
            # (trabajador_idx, estado, fecha_inicio_offset_dias, dias_calendario, motivo, motivo_rechazo)
            (0, 'PENDIENTE',  20,   7,  'Solicitud de vacaciones de 7 días, viaje familiar.',                  ''),
            (1, 'APROBADA',   -3,   7,  'Vacaciones en curso — período aprobado.',                              ''),
            (2, 'APROBADA',   35,  15,  'Vacaciones aprobadas para el próximo mes.',                            ''),
            (3, 'RECHAZADA',  10,  10,  'Solicitud rechazada por coincidencia con cierre contable mensual.',
             'Periodo coincide con cierre mensual de planilla — favor reprogramar para luego del día 15.'),
        ]

        for idx, estado, offset_inicio, dias_cal, motivo, motivo_rechazo in casos:
            trab = candidatos[idx]

            # Asegurar saldo (período actual del trabajador)
            periodo_inicio = trab.fecha_alta or (hoy - timedelta(days=365))
            # Tomar último período: si tiene varios años de servicio, último año
            anios_servicio = (hoy - periodo_inicio).days // 365
            if anios_servicio > 0:
                periodo_inicio = periodo_inicio + timedelta(days=365 * anios_servicio)
            periodo_fin = periodo_inicio + timedelta(days=365)

            saldo, _ = SaldoVacacional.objects.get_or_create(
                personal=trab,
                periodo_inicio=periodo_inicio,
                defaults={
                    'periodo_fin':     periodo_fin,
                    'dias_derecho':    30,
                    'dias_gozados':    0,
                    'dias_vendidos':   0,
                    'dias_pendientes': 30,
                    'estado': 'PENDIENTE',
                },
            )

            fecha_inicio = hoy + timedelta(days=offset_inicio)
            fecha_fin    = fecha_inicio + timedelta(days=dias_cal - 1)

            # Idempotencia: chequear si ya existe solicitud para este trab+fecha_inicio
            if SolicitudVacacion.objects.filter(
                personal=trab, fecha_inicio=fecha_inicio,
            ).exists():
                continue

            sv = SolicitudVacacion(
                personal=trab,
                saldo=saldo,
                fecha_inicio=fecha_inicio,
                fecha_fin=fecha_fin,
                motivo=motivo,
                estado=estado,
                solicitado_por=admin,
            )
            if estado == 'APROBADA':
                sv.aprobado_por = admin
                sv.fecha_aprobacion = hoy - timedelta(days=2)
            elif estado == 'RECHAZADA':
                sv.aprobado_por = admin
                sv.fecha_aprobacion = hoy - timedelta(days=1)
                sv.motivo_rechazo = motivo_rechazo
            sv.save()  # save() recalcula dias_calendario/habiles
            self.resumen['solicitudes_vacacion_creadas'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Vacaciones: {self.resumen["solicitudes_vacacion_creadas"]} solicitudes nuevas.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # 7. VIATICOS
    # ─────────────────────────────────────────────────────────────────────

    def _seed_viaticos(self):
        from viaticos.models import ConceptoViatico, AsignacionViatico, GastoViatico

        admin = self._get_admin_user()
        hoy = date.today()
        primer_dia_mes = hoy.replace(day=1)

        # Conceptos
        c_alim, _ = ConceptoViatico.objects.get_or_create(
            codigo='alimentacion',
            defaults={'nombre': 'Alimentación', 'tope_diario': Decimal('60.00'),
                      'requiere_comprobante': True, 'activo': True, 'orden': 1},
        )
        c_hosp, _ = ConceptoViatico.objects.get_or_create(
            codigo='hospedaje',
            defaults={'nombre': 'Hospedaje', 'tope_diario': Decimal('150.00'),
                      'requiere_comprobante': True, 'activo': True, 'orden': 2},
        )
        c_mov, _ = ConceptoViatico.objects.get_or_create(
            codigo='movilidad',
            defaults={'nombre': 'Movilidad', 'tope_diario': Decimal('50.00'),
                      'requiere_comprobante': True, 'activo': True, 'orden': 3},
        )

        # Buscar trabajadores admin/supervisión (con foco en quienes podrían viajar)
        from personal.models import Personal
        candidatos = list(Personal.objects.filter(
            estado='Activo', fecha_alta__isnull=False,
        )[:30])
        if len(candidatos) < 3:
            self.resumen['todos'].append('[viaticos] Menos de 3 trabajadores — saltando.')
            return

        casos = [
            # (idx, ubicacion, monto_asignado, estado, dias_campo, gastos)
            (0, 'Arequipa - Apertura local', Decimal('800.00'), 'EN_RENDICION', 5,
                [(c_alim, Decimal('55.00'), 'APROBADO', 'Almuerzo equipo'),
                 (c_hosp, Decimal('140.00'), 'APROBADO', 'Hotel - 1 noche'),
                 (c_mov,  Decimal('45.00'),  'APROBADO', 'Taxi aeropuerto')]),
            (1, 'Cusco - Capacitación regional', Decimal('1200.00'), 'CONCILIADO', 7,
                [(c_alim, Decimal('58.00'), 'APROBADO', 'Cena de cierre'),
                 (c_hosp, Decimal('145.00'), 'APROBADO', 'Hotel 2 noches'),
                 (c_mov,  Decimal('48.00'),  'PENDIENTE', 'Combi al aeropuerto')]),
            (2, 'Trujillo - Visita proveedor', Decimal('600.00'), 'APROBADO', 3,
                []),
        ]

        for idx, ubic, monto, estado, dias_campo, gastos in casos:
            trab = candidatos[idx]
            asig, a_created = AsignacionViatico.objects.get_or_create(
                personal=trab,
                periodo=primer_dia_mes,
                defaults={
                    'monto_asignado': monto,
                    'ubicacion':      ubic,
                    'dias_campo':     dias_campo,
                    'estado':         estado,
                    'fecha_entrega':  hoy - timedelta(days=10) if estado != 'BORRADOR' else None,
                    'creado_por':     admin,
                    'aprobado_por':   admin if estado != 'BORRADOR' else None,
                },
            )
            if a_created:
                self.resumen['asignaciones_viatico_creadas'] += 1

            for concepto, monto_g, estado_g, descrip in gastos:
                # Idempotencia: por (asignacion, concepto, monto, descripcion)
                if GastoViatico.objects.filter(
                    asignacion=asig, concepto=concepto,
                    monto=monto_g, descripcion=descrip,
                ).exists():
                    continue
                GastoViatico.objects.create(
                    asignacion=asig,
                    concepto=concepto,
                    fecha_gasto=hoy - timedelta(days=random.randint(5, 12)),
                    monto=monto_g,
                    descripcion=descrip,
                    tipo_comprobante='BOLETA',
                    numero_comprobante=f'B001-{random.randint(10000, 99999)}',
                    estado=estado_g,
                )
                self.resumen['gastos_viatico_creados'] += 1

        self.stdout.write(self.style.SUCCESS(
            f'  [+] Viáticos: {self.resumen["asignaciones_viatico_creadas"]} asignaciones, '
            f'{self.resumen["gastos_viatico_creados"]} gastos.'
        ))

    # ─────────────────────────────────────────────────────────────────────
    # Reporte final
    # ─────────────────────────────────────────────────────────────────────

    def _reporte_final(self):
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('Seed Extra — Resumen'))
        self.stdout.write('=' * 60)
        for key, val in self.resumen.items():
            if key == 'todos':
                continue
            self.stdout.write(f'  {key:42s} {val}')
        if self.resumen['todos']:
            self.stdout.write('\n  TODOs / avisos:')
            for t in self.resumen['todos']:
                self.stdout.write(f'   - {t}')
        self.stdout.write('=' * 60 + '\n')
