"""
seed_demo_nominas.py
Genera 2 períodos de planilla cerrados (mes actual − 1 y mes actual − 2) con
RegistroNomina + LineaNomina calculadas vía engine.generar_periodo.

Esto deja el módulo /nominas/ con data realista para presentaciones de venta.
Las boletas PDF se generan a demanda desde la UI; no se materializan aquí.

Idempotente: usa get_or_create + engine.generar_periodo (que es idempotente).
"""
import calendar
from datetime import date

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from nominas.engine import generar_periodo
from nominas.models import ConceptoRemunerativo, PeriodoNomina
from personal.models import Personal


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _periodo_anterior(meses_atras: int) -> tuple[int, int]:
    """Retorna (anio, mes) restando N meses al actual."""
    hoy = date.today()
    anio, mes = hoy.year, hoy.month
    mes -= meses_atras
    while mes <= 0:
        mes += 12
        anio -= 1
    return anio, mes


class Command(BaseCommand):
    help = 'Genera 2 períodos de planilla cerrados con cálculos completos.'

    def handle(self, *args, **options):
        self.stdout.write('\n=== SEED DEMO NOMINAS ===')

        if not ConceptoRemunerativo.objects.exists():
            self.stdout.write('  Conceptos no existen, ejecutando seed_conceptos...')
            call_command('seed_conceptos')

        empleados_activos = Personal.objects.filter(estado='Activo').count()
        if empleados_activos == 0:
            self.stdout.write('  [ERROR] No hay personal activo')
            return
        self.stdout.write(f'  Personal activo: {empleados_activos}')

        from django.contrib.auth import get_user_model
        admin = get_user_model().objects.filter(is_superuser=True).first()

        # Generar los 2 meses más recientes ya cerrados
        for meses_atras in (1, 2):
            anio, mes = _periodo_anterior(meses_atras)
            fecha_inicio = date(anio, mes, 1)
            fecha_fin    = date(anio, mes, _last_day(anio, mes))
            descripcion  = f'Planilla {fecha_fin.strftime("%B %Y").capitalize()}'

            periodo, created = PeriodoNomina.objects.get_or_create(
                tipo='REGULAR', anio=anio, mes=mes,
                defaults={
                    'descripcion':  descripcion,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin':    fecha_fin,
                    'fecha_pago':   fecha_fin,
                    'generado_por': admin,
                    'generado_en':  timezone.now(),
                },
            )
            verb = 'creado' if created else 'reutilizado'
            self.stdout.write(f'  Período {periodo} ({verb})')

            stats = generar_periodo(periodo, usuario=admin)
            self.stdout.write(
                f'    Registros: {stats["generados"]} nuevos / '
                f'{stats["actualizados"]} actualizados / '
                f'{stats["errores"]} errores'
            )

            # Marcar el más antiguo como CERRADO (para mostrar histórico cerrado)
            # y el más reciente como APROBADO (próximo a cerrar)
            agg = periodo.registros.aggregate(
                t=Sum('neto_a_pagar'),
                n=Sum('total_ingresos'),
            )
            periodo.total_trabajadores = periodo.registros.count()
            periodo.total_bruto        = agg['n'] or 0
            periodo.total_neto         = agg['t'] or 0
            periodo.estado = 'CERRADO' if meses_atras == 2 else 'APROBADO'
            if periodo.estado != 'BORRADOR':
                periodo.aprobado_por = admin
                periodo.aprobado_en  = timezone.now()
            periodo.save()

            self.stdout.write(self.style.SUCCESS(
                f'    [OK] {periodo.total_trabajadores} trabajadores, '
                f'neto S/. {periodo.total_neto:,.2f}, estado {periodo.estado}'
            ))

        self.stdout.write('=== FIN SEED NOMINAS ===\n')
