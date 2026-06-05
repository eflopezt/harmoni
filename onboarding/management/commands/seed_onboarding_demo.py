"""
Siembra PROCESOS de onboarding EN CURSO con progreso variado, para que el panel
de Onboarding de la DEMO no se vea vacío ("No hay procesos de onboarding").

Las plantillas/checklists ya se siembran aparte, pero no había procesos activos →
un prospecto que entra a la etapa de Onboarding (gancho del flujo) ve la pantalla
muerta. Este comando crea ~4 procesos para ingresos recientes, cada uno con un %
distinto de pasos completados (progreso realista).

Idempotente: si ya hay procesos, no hace nada. Solo DEMO/seed.

Uso:
    python manage.py seed_onboarding_demo
"""
from datetime import date, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone


class Command(BaseCommand):
    help = "Siembra procesos de onboarding EN CURSO (solo DEMO) para poblar el panel"

    def handle(self, *args, **opts):
        from onboarding.models import (PlantillaOnboarding, ProcesoOnboarding,
                                       PasoOnboarding)
        from personal.models import Personal
        User = get_user_model()

        if ProcesoOnboarding.objects.exists():
            self.stdout.write(self.style.SUCCESS(
                f"Ya hay {ProcesoOnboarding.objects.count()} proceso(s) de onboarding. OK."))
            return

        # Asegurar que exista al menos una plantilla con pasos.
        plantilla = (PlantillaOnboarding.objects.filter(activa=True)
                     .filter(pasos__isnull=False).distinct().first())
        if not plantilla:
            call_command('seed_plantillas_onboarding')
            plantilla = (PlantillaOnboarding.objects.filter(activa=True)
                         .filter(pasos__isnull=False).distinct().first())
        if not plantilla:
            self.stdout.write(self.style.WARNING(
                "No hay plantilla de onboarding con pasos — nada que sembrar."))
            return

        pasos_tpl = list(plantilla.pasos.all().order_by('orden'))
        if not pasos_tpl:
            self.stdout.write(self.style.WARNING("La plantilla no tiene pasos."))
            return

        admin = (User.objects.filter(username='demo').first()
                 or User.objects.filter(is_superuser=True).first())

        # Ingresos recientes (con fecha_alta) → candidatos naturales a onboarding.
        recientes = list(Personal.objects.filter(
            estado='Activo', fecha_alta__isnull=False).order_by('-fecha_alta')[:4])
        if len(recientes) < 4:
            extra = Personal.objects.filter(estado='Activo').exclude(
                pk__in=[p.pk for p in recientes]).order_by('id')[:4 - len(recientes)]
            recientes += list(extra)
        if not recientes:
            self.stdout.write(self.style.WARNING("No hay empleados activos."))
            return

        hoy = date.today()
        # % de pasos completados por proceso (progreso variado y realista)
        pct_por_proceso = [0.20, 0.45, 0.70, 0.90]
        n = 0
        for i, p in enumerate(recientes):
            pct = pct_por_proceso[i % len(pct_por_proceso)]
            fecha_ingreso = hoy - timedelta(days=10 + i * 5)
            proceso = ProcesoOnboarding.objects.create(
                personal=p, plantilla=plantilla,
                fecha_ingreso=fecha_ingreso, fecha_inicio=fecha_ingreso,
                estado='EN_CURSO', iniciado_por=admin,
                notas='Proceso de demostración.',
            )
            n_completar = int(round(len(pasos_tpl) * pct))
            for idx, tpl in enumerate(pasos_tpl):
                completado = idx < n_completar
                PasoOnboarding.objects.create(
                    proceso=proceso, paso_plantilla=tpl, orden=tpl.orden,
                    titulo=tpl.titulo,
                    estado='COMPLETADO' if completado else 'PENDIENTE',
                    fecha_limite=fecha_ingreso + timedelta(days=tpl.dias_plazo),
                    fecha_completado=(timezone.now() if completado else None),
                    completado_por=(admin if completado else None),
                )
            n += 1

        self.stdout.write(self.style.SUCCESS(
            f"{n} proceso(s) de onboarding EN CURSO sembrados "
            f"(plantilla '{plantilla.nombre}', {len(pasos_tpl)} pasos c/u)."))
