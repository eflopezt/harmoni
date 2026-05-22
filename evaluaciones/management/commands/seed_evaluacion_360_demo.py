"""
Seed demo de Evaluación 360° para gastronomía.
Crea una evaluación de muestra con 5 participantes (3 completados, 2 pendientes)
sobre las 6 competencias gastro estándar.
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from evaluaciones.models import (
    COMPETENCIAS_GASTRO_360,
    Competencia,
    Evaluacion360,
    ParticipanteEvaluacion360,
    RespuestaCompetencia360,
)

try:
    from personal.models import Personal
except ImportError:
    Personal = None


class Command(BaseCommand):
    help = 'Crea una evaluación 360° demo con 5 participantes y 3 completados.'

    def add_arguments(self, parser):
        parser.add_argument('--periodo', default=None, help='Periodo (ej: 2026-Q2)')
        parser.add_argument('--force', action='store_true',
                            help='Crear aunque ya exista una demo para el mismo evaluado/periodo')

    @transaction.atomic
    def handle(self, *args, **opts):
        if Personal is None:
            self.stdout.write(self.style.ERROR('Modelo Personal no disponible.'))
            return

        periodo = opts.get('periodo') or f'{date.today().year}-Q{((date.today().month - 1)//3) + 1}'

        # Evaluado: supervisor activo con más antigüedad si se puede determinar,
        # si no, el primer Personal activo con cargo que contenga "Supervisor"/"Jefe".
        evaluado = (
            Personal.objects
            .filter(estado='Activo')
            .filter(cargo__iregex=r'(supervisor|jefe|chef|gerente)')
            .order_by('id')
            .first()
        )
        if evaluado is None:
            evaluado = Personal.objects.filter(estado='Activo').order_by('id').first()
        if evaluado is None:
            self.stdout.write(self.style.ERROR('No hay Personal activo para usar como evaluado.'))
            return

        # ¿Ya existe?
        existente = Evaluacion360.objects.filter(
            personal_evaluado=evaluado, periodo=periodo,
        ).first()
        if existente and not opts.get('force'):
            self.stdout.write(self.style.WARNING(
                f'Ya existe evaluación 360 demo para {evaluado.apellidos_nombres} en {periodo}. '
                f'Use --force para recrear.'
            ))
            return
        if existente:
            existente.delete()

        eval360 = Evaluacion360.objects.create(
            personal_evaluado=evaluado,
            periodo=periodo,
            estado='EN_CURSO',
            fecha_inicio=date.today() - timedelta(days=7),
            fecha_cierre=date.today() + timedelta(days=14),
        )

        # Selecciona compañeros: el resto de activos
        otros = list(
            Personal.objects.filter(estado='Activo')
            .exclude(pk=evaluado.pk)
            .order_by('id')[:10]
        )

        def pick(n):
            random.shuffle(otros)
            return otros[:n] if otros else []

        manager = otros[0] if otros else None
        peers = otros[1:3] if len(otros) >= 3 else otros[1:]
        subord = otros[3] if len(otros) >= 4 else None

        participantes_spec = [
            ('AUTOEVALUACION', evaluado, True),
            ('MANAGER',        manager,  True),
            ('PEER',           peers[0] if len(peers) >= 1 else None, True),
            ('PEER',           peers[1] if len(peers) >= 2 else None, False),
            ('SUBORDINADO',    subord,   False),
        ]

        # Asegurar Competencia objetos si existen
        comp_objs = {}
        for cod, label in COMPETENCIAS_GASTRO_360:
            comp, _ = Competencia.objects.get_or_create(
                codigo=cod,
                defaults={
                    'nombre': label,
                    'categoria': 'INTERPERSONAL',
                    'descripcion': f'Competencia gastronómica: {label}.',
                },
            )
            comp_objs[cod] = comp

        creados = 0
        completados = 0

        for tipo, persona, completar in participantes_spec:
            p = ParticipanteEvaluacion360.objects.create(
                evaluacion=eval360,
                tipo=tipo,
                personal_evaluador=persona,
            )
            creados += 1
            if not completar:
                continue

            # Sembrar puntajes
            for cod, label in COMPETENCIAS_GASTRO_360:
                # Auto tiende a calificarse alto; manager más realista
                if tipo == 'AUTOEVALUACION':
                    base = random.uniform(4.0, 4.8)
                elif tipo == 'MANAGER':
                    base = random.uniform(3.0, 4.0)
                else:
                    base = random.uniform(3.2, 4.4)
                puntaje = Decimal(str(round(base, 1)))
                RespuestaCompetencia360.objects.create(
                    participante=p,
                    competencia=comp_objs.get(cod),
                    competencia_codigo=cod,
                    competencia_label=label,
                    puntaje=puntaje,
                    comentario='',
                )

            p.fortalezas = {
                'AUTOEVALUACION': 'Compromiso con el equipo\nOrganización del servicio',
                'MANAGER': 'Compromiso con el equipo\nPuntualidad',
                'PEER': 'Buena disposición\nTrabajo bajo presión',
            }.get(tipo, '')
            p.areas_mejora = {
                'AUTOEVALUACION': 'Delegar más\nMejor manejo del estrés',
                'MANAGER': 'Comunicación con cocina\nMejor manejo del estrés',
                'PEER': 'Mejor comunicación\nFeedback más frecuente',
            }.get(tipo, '')
            p.comentario_general = f'Sembrado demo — perspectiva {tipo.lower()}.'
            p.completada = True
            from django.utils import timezone
            p.fecha_completada = timezone.now()
            p.save()
            p.calcular_puntaje_global()
            completados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Evaluación 360° demo creada para {evaluado.apellidos_nombres} '
            f'(periodo {periodo}). Participantes: {creados} · Completados: {completados}.'
        ))
