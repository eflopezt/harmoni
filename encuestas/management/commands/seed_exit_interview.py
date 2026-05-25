"""
Seed idempotente — Encuesta "Exit Interview" estándar para offboarding.

Crea (o reutiliza) una `Encuesta` tipo SALIDA con ~10 preguntas que cubren
los temas estándar de una entrevista de salida: motivo de salida,
satisfacción general, eNPS, jefe directo, compensación, reconocimiento,
sugerencias de mejora.

Match por (titulo, tipo='SALIDA') para idempotencia. Si la encuesta ya
existe y tiene exactamente las 10 preguntas, no se toca; si faltan, se
agregan las que falten.

Uso:
    python manage.py seed_exit_interview
    python manage.py seed_exit_interview --dry-run

La encuesta queda en estado ACTIVA por defecto, no anónima (para que
RRHH pueda ligar la respuesta al trabajador cesado vía el portal).

Documentación: docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md (Sprint 3).
"""
from __future__ import annotations

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction


ENCUESTA_TITULO = 'Exit Interview — Entrevista de Salida'
ENCUESTA_TIPO = 'SALIDA'


# 10 preguntas estándar — coinciden con la lista del spec Sprint 3.
PREGUNTAS_EXIT = [
    {
        'orden':       10,
        'texto':       '¿Cuál fue la razón principal de tu salida?',
        'tipo':        'TEXTO',
        'obligatoria': True,
        'categoria':   'Motivo',
    },
    {
        'orden':       20,
        'texto':       '¿Cómo evalúas tu experiencia general en la empresa? (1 = pésima, 10 = excelente)',
        'tipo':        'ESCALA_10',
        'obligatoria': True,
        'categoria':   'Satisfacción',
    },
    {
        'orden':       30,
        'texto':       '¿Recomendarías la empresa a un amigo o familiar como lugar para trabajar?',
        'tipo':        'OPCION',
        'obligatoria': True,
        'categoria':   'eNPS',
        'opciones':    ['Sí', 'No', 'Tal vez'],
    },
    {
        'orden':       40,
        'texto':       '¿Qué fue lo mejor de trabajar aquí?',
        'tipo':        'TEXTO',
        'obligatoria': False,
        'categoria':   'Positivo',
    },
    {
        'orden':       50,
        'texto':       '¿Qué mejorarías de la empresa o de tu experiencia?',
        'tipo':        'TEXTO',
        'obligatoria': False,
        'categoria':   'Mejora',
    },
    {
        'orden':       60,
        'texto':       '¿Cómo evalúas a tu jefe directo? (0 = muy malo, 10 = excelente)',
        'tipo':        'ESCALA_10',
        'obligatoria': True,
        'categoria':   'Liderazgo',
    },
    {
        'orden':       70,
        'texto':       '¿Cómo evalúas tu compensación (sueldo y beneficios)? (0 = injusta, 10 = muy justa)',
        'tipo':        'ESCALA_10',
        'obligatoria': True,
        'categoria':   'Compensación',
    },
    {
        'orden':       80,
        'texto':       '¿Te sentiste valorado(a) por la empresa? (1 = nada, 5 = mucho)',
        'tipo':        'ESCALA_5',
        'obligatoria': True,
        'categoria':   'Reconocimiento',
    },
    {
        'orden':       90,
        'texto':       '¿Recibiste el reconocimiento adecuado por tu trabajo?',
        'tipo':        'OPCION',
        'obligatoria': True,
        'categoria':   'Reconocimiento',
        'opciones':    ['Sí', 'No', 'A veces'],
    },
    {
        'orden':       100,
        'texto':       'Comentarios adicionales (cualquier cosa que quieras agregar)',
        'tipo':        'TEXTO',
        'obligatoria': False,
        'categoria':   'Otros',
    },
]


def get_or_create_exit_encuesta(dry_run=False):
    """
    Idempotente: devuelve la `Encuesta` "Exit Interview" (creada o existente)
    y la lista de preguntas presentes. Si dry_run=True no toca la BD.

    Returns: tuple (encuesta_or_none, created_bool, n_preguntas_creadas).
    """
    from encuestas.models import Encuesta, PreguntaEncuesta

    qs = Encuesta.objects.filter(titulo=ENCUESTA_TITULO, tipo=ENCUESTA_TIPO)
    encuesta = qs.first()
    created = False
    preguntas_creadas = 0

    if dry_run:
        if encuesta is None:
            return None, False, len(PREGUNTAS_EXIT)
        existentes = set(encuesta.preguntas.values_list('orden', flat=True))
        faltantes = [p for p in PREGUNTAS_EXIT if p['orden'] not in existentes]
        return encuesta, False, len(faltantes)

    if encuesta is None:
        hoy = date.today()
        encuesta = Encuesta.objects.create(
            titulo=ENCUESTA_TITULO,
            tipo=ENCUESTA_TIPO,
            descripcion=(
                'Entrevista de salida que se envía automáticamente al '
                'trabajador en el portal cuando se inicia el flujo de '
                'offboarding. Permite a RRHH detectar patrones de salida '
                'y oportunidades de mejora.'
            ),
            estado='ACTIVA',
            anonima=False,
            fecha_inicio=hoy,
            fecha_fin=hoy + timedelta(days=365 * 5),  # encuesta perenne
            recordatorio_dias=3,
        )
        created = True

    # Agregar preguntas que falten (idempotente por orden)
    existentes_orden = set(encuesta.preguntas.values_list('orden', flat=True))
    for cfg in PREGUNTAS_EXIT:
        if cfg['orden'] in existentes_orden:
            continue
        PreguntaEncuesta.objects.create(
            encuesta=encuesta,
            orden=cfg['orden'],
            texto=cfg['texto'],
            tipo=cfg['tipo'],
            obligatoria=cfg.get('obligatoria', True),
            categoria=cfg.get('categoria', ''),
            opciones=cfg.get('opciones', []),
        )
        preguntas_creadas += 1

    return encuesta, created, preguntas_creadas


class Command(BaseCommand):
    help = (
        'Crea (o reutiliza) la encuesta "Exit Interview" con 10 preguntas '
        'estándar para offboarding. Idempotente.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué crearía sin tocar la BD.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        prefix = '[DRY-RUN] ' if dry_run else ''

        encuesta, created, preguntas_creadas = get_or_create_exit_encuesta(
            dry_run=dry_run,
        )

        if encuesta is None:
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}Encuesta "{ENCUESTA_TITULO}" se crearía con '
                f'{preguntas_creadas} preguntas.'
            ))
            return

        marker_enc = '[+]' if created else '[=]'
        self.stdout.write(
            f'  {marker_enc} Encuesta: {encuesta.titulo} '
            f'(id={encuesta.pk}, total preguntas={encuesta.preguntas.count()})'
        )
        if preguntas_creadas:
            self.stdout.write(
                f'      [+] {preguntas_creadas} preguntas nuevas agregadas'
            )
        else:
            self.stdout.write('      [=] Sin preguntas nuevas (todas existían)')

        self.stdout.write(self.style.SUCCESS(
            f'{prefix}seed_exit_interview: OK · '
            f'encuesta {"creada" if created else "reutilizada"}.'
        ))
