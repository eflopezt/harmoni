"""
Comando de management: seed_checklists_demo

Crea checklists de gastronomía para los 8 trabajadores más recientes
(ordenados por fecha_alta). Pobla con datos realistas:
- ~3 completados
- ~3 en proceso (50% items)
- ~2 en riesgo (>30 días desde ingreso, faltan items)

Idempotente: si ya existe checklist para un Personal, lo actualiza
(usa --force para reiniciar valores) o lo deja como está.

Uso:
    python manage.py seed_checklists_demo
    python manage.py seed_checklists_demo --force
    python manage.py seed_checklists_demo --count 12
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


class Command(BaseCommand):
    help = "Seed de ChecklistGastronomia para demo (escenarios mixtos)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', type=int, default=8,
            help='Número de trabajadores a poblar (default 8)',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Reescribe checklists existentes',
        )

    def handle(self, *args, **options):
        from personal.models import Personal
        from onboarding.models import ChecklistGastronomia

        count = options['count']
        force = options['force']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== Seed ChecklistGastronomia (count={count}, force={force}) ==="
        ))

        # Tomamos los más recientes por fecha_alta. Si no hay suficientes con
        # fecha_alta, completamos con los más recientes por id.
        qs_alta = Personal.objects.filter(
            estado='Activo', fecha_alta__isnull=False
        ).order_by('-fecha_alta')[:count]
        trabajadores = list(qs_alta)

        if len(trabajadores) < count:
            faltan = count - len(trabajadores)
            ya_ids = [p.pk for p in trabajadores]
            extras = list(
                Personal.objects.filter(estado='Activo')
                .exclude(pk__in=ya_ids)
                .order_by('-id')[:faltan]
            )
            trabajadores.extend(extras)

        if not trabajadores:
            self.stdout.write(self.style.WARNING(
                "No hay trabajadores activos disponibles. Aborto."
            ))
            return

        hoy = timezone.localdate()

        # Definir 3 perfiles: completado, en_proceso, en_riesgo
        # Distribución aproximada según count.
        n_completados = max(1, count // 3)
        n_riesgo      = max(1, count // 4)
        n_proceso     = max(0, len(trabajadores) - n_completados - n_riesgo)

        perfiles = (
            (['completado'] * n_completados) +
            (['proceso']    * n_proceso) +
            (['riesgo']     * n_riesgo)
        )
        # Recortar / rellenar para que coincida con la cantidad
        perfiles = perfiles[:len(trabajadores)]
        while len(perfiles) < len(trabajadores):
            perfiles.append('proceso')

        random.seed(42)
        creados = 0
        actualizados = 0
        omitidos = 0

        with transaction.atomic():
            for personal, perfil in zip(trabajadores, perfiles):
                existe = ChecklistGastronomia.objects.filter(personal=personal).first()
                if existe and not force:
                    omitidos += 1
                    self.stdout.write(
                        f"  · {personal.apellidos_nombres} — ya tiene checklist, omitido"
                    )
                    continue

                if existe:
                    checklist = existe
                    actualizados += 1
                else:
                    checklist = ChecklistGastronomia(personal=personal, fecha_ingreso=hoy)
                    creados += 1

                self._aplicar_perfil(checklist, perfil, hoy)
                checklist.save()
                self.stdout.write(
                    f"  ✓ {personal.apellidos_nombres:<40} [{perfil:11}] "
                    f"{checklist.porcentaje_completado:>3}% ({checklist.dias_desde_ingreso}d)"
                )

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. creados={creados}, actualizados={actualizados}, omitidos={omitidos}"
        ))

    # ── perfiles ──────────────────────────────────────────────

    def _aplicar_perfil(self, checklist, perfil, hoy):
        """Configura el checklist según uno de los 3 perfiles."""
        if perfil == 'completado':
            # 95-100 días, todo OK con notas y calificaciones
            checklist.fecha_ingreso = hoy - timedelta(days=random.randint(95, 110))
            self._marcar_todo(checklist, hoy)
            checklist.evaluacion_30_calificacion = random.randint(7, 10)
            checklist.evaluacion_30_notas = "Buen desempeño inicial, integración rápida."
            checklist.evaluacion_60_calificacion = random.randint(7, 10)
            checklist.evaluacion_60_notas = "Domina BPM y técnicas básicas."
            checklist.evaluacion_90_calificacion = random.randint(8, 10)
            checklist.evaluacion_90_notas = "Confirmado. Promovido a su puesto definitivo."
            checklist.completado = True

        elif perfil == 'proceso':
            # 10-25 días, ~40-60% items
            checklist.fecha_ingreso = hoy - timedelta(days=random.randint(10, 25))
            # Documentos básicos sí
            checklist.contrato_firmado = True
            checklist.contrato_firmado_fecha = checklist.fecha_ingreso + timedelta(days=1)
            checklist.examen_medico = True
            checklist.examen_medico_fecha = checklist.fecha_ingreso + timedelta(days=3)
            checklist.induccion_general = True
            checklist.induccion_general_fecha = checklist.fecha_ingreso + timedelta(days=2)
            checklist.uniforme_entregado = True
            checklist.uniforme_entregado_fecha = checklist.fecha_ingreso + timedelta(days=2)
            # Algunas certs sí, otras no
            checklist.manipulacion_alimentos = random.random() < 0.5
            if checklist.manipulacion_alimentos:
                checklist.manipulacion_alimentos_fecha = checklist.fecha_ingreso + timedelta(days=10)
            checklist.bpm_certificado = random.random() < 0.4
            if checklist.bpm_certificado:
                checklist.bpm_certificado_fecha = checklist.fecha_ingreso + timedelta(days=12)
            # Evaluaciones aún no
            checklist.completado = False

        elif perfil == 'riesgo':
            # 35-50 días, faltan items críticos
            checklist.fecha_ingreso = hoy - timedelta(days=random.randint(35, 50))
            checklist.contrato_firmado = True
            checklist.contrato_firmado_fecha = checklist.fecha_ingreso + timedelta(days=2)
            # Faltó el examen médico — alerta
            checklist.examen_medico = False
            checklist.induccion_general = True
            checklist.induccion_general_fecha = checklist.fecha_ingreso + timedelta(days=4)
            checklist.uniforme_entregado = True
            checklist.uniforme_entregado_fecha = checklist.fecha_ingreso + timedelta(days=2)
            # Solo manipulación, falta BPM
            checklist.manipulacion_alimentos = True
            checklist.manipulacion_alimentos_fecha = checklist.fecha_ingreso + timedelta(days=15)
            checklist.bpm_certificado = False
            # Falta evaluación 30 — vencida
            checklist.evaluacion_30 = False
            checklist.completado = False

    def _marcar_todo(self, checklist, hoy):
        """Marca todos los items en True con fechas escalonadas."""
        base = checklist.fecha_ingreso
        checklist.contrato_firmado = True
        checklist.contrato_firmado_fecha = base + timedelta(days=1)
        checklist.examen_medico = True
        checklist.examen_medico_fecha = base + timedelta(days=3)
        checklist.uniforme_entregado = True
        checklist.uniforme_entregado_fecha = base + timedelta(days=2)
        checklist.induccion_general = True
        checklist.induccion_general_fecha = base + timedelta(days=2)
        checklist.bpm_certificado = True
        checklist.bpm_certificado_fecha = base + timedelta(days=18)
        checklist.haccp_certificado = True
        checklist.haccp_certificado_fecha = base + timedelta(days=25)
        checklist.manipulacion_alimentos = True
        checklist.manipulacion_alimentos_fecha = base + timedelta(days=10)
        checklist.carne_sanitario = True
        checklist.carne_sanitario_fecha = base + timedelta(days=14)
        checklist.evaluacion_30 = True
        checklist.evaluacion_30_fecha = base + timedelta(days=30)
        checklist.evaluacion_60 = True
        checklist.evaluacion_60_fecha = base + timedelta(days=60)
        checklist.evaluacion_90 = True
        checklist.evaluacion_90_fecha = base + timedelta(days=90)
