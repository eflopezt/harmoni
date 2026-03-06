"""
Disparadores automáticos de comunicaciones.

Ejecutar diariamente vía cron o Render scheduler:
    manage.py triggers_automaticos
    manage.py triggers_automaticos --dry-run   # solo muestra, no envía

Detecta y notifica:
  1. Cumpleaños del día   → felicitación a empleado (IN_APP + EMAIL)
  2. Aniversarios laborales (1, 2, 3... años) → reconocimiento (IN_APP + EMAIL)
  3. Fin de período de prueba en 15 / 7 / 1 día → aviso a empleado (IN_APP)

Los PlantillaNotificacion se crean automáticamente si no existen.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


# ── Definición de plantillas de notificación ──────────────────────────────────
_PLANTILLAS = {
    'cumpleanos_felicitacion': {
        'nombre': 'Felicitación Cumpleaños',
        'asunto_template': '¡Feliz Cumpleaños, {{ nombre }}! 🎉',
        'cuerpo_template': (
            '<p>Estimado/a <strong>{{ nombre }}</strong>,</p>'
            '<p>En nombre de todo el equipo de <strong>{{ empresa }}</strong>, '
            'te deseamos un muy feliz cumpleaños. ¡Que este nuevo año esté '
            'lleno de éxitos, salud y alegría!</p>'
            '<p>Con cariño,<br><strong>Equipo RRHH</strong></p>'
        ),
        'tipo': 'AMBOS',
        'modulo': 'RRHH',
        'variables_disponibles': 'nombre, empresa',
    },
    'aniversario_laboral': {
        'nombre': 'Aniversario Laboral',
        'asunto_template': '¡{{ anios }} año(s) con nosotros, {{ nombre }}! 🏆',
        'cuerpo_template': (
            '<p>Estimado/a <strong>{{ nombre }}</strong>,</p>'
            '<p>Hoy se cumplen <strong>{{ anios }} año(s)</strong> desde que te uniste '
            'a <strong>{{ empresa }}</strong>. Tu dedicación y compromiso son un ejemplo '
            'para todo el equipo. ¡Gracias por ser parte de esta historia!</p>'
            '<p>Con aprecio,<br><strong>Equipo RRHH</strong></p>'
        ),
        'tipo': 'AMBOS',
        'modulo': 'RRHH',
        'variables_disponibles': 'nombre, empresa, anios',
    },
    'fin_periodo_prueba_aviso': {
        'nombre': 'Aviso Fin Período de Prueba',
        'asunto_template': 'Tu período de prueba finaliza en {{ dias_restantes }} día(s)',
        'cuerpo_template': (
            '<p>Estimado/a <strong>{{ nombre }}</strong>,</p>'
            '<p>Te informamos que tu <strong>período de prueba</strong> finaliza el '
            '<strong>{{ fecha_fin }}</strong> (en {{ dias_restantes }} día(s)).</p>'
            '<p>Ante cualquier consulta sobre tu situación laboral, no dudes en '
            'comunicarte con el área de RRHH.</p>'
            '<p>Atentamente,<br><strong>Equipo RRHH</strong></p>'
        ),
        'tipo': 'IN_APP',
        'modulo': 'RRHH',
        'variables_disponibles': 'nombre, fecha_fin, dias_restantes',
    },
}

# Días antes del fin de período de prueba en que se avisa al empleado
_DIAS_AVISO_PERIODO_PRUEBA = [15, 7, 1]


class Command(BaseCommand):
    help = (
        'Dispara notificaciones automáticas diarias: cumpleaños, '
        'aniversarios laborales y fin de período de prueba.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué enviaría sin enviar realmente.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        hoy     = timezone.localdate()
        prefix  = '[DRY-RUN] ' if dry_run else ''

        self._ensure_plantillas()

        n_cum = self._procesar_cumpleanos(hoy, dry_run)
        n_ani = self._procesar_aniversarios(hoy, dry_run)
        n_pp  = self._procesar_periodo_prueba(hoy, dry_run)
        total = n_cum + n_ani + n_pp

        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix}triggers_automaticos {hoy} — '
                f'cumpleanos:{n_cum} aniversarios:{n_ani} '
                f'periodo_prueba:{n_pp} TOTAL:{total}'
            )
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _ensure_plantillas(self):
        """Crea PlantillaNotificacion si no existen (idempotente)."""
        from comunicaciones.models import PlantillaNotificacion
        for codigo, data in _PLANTILLAS.items():
            obj, created = PlantillaNotificacion.objects.get_or_create(
                codigo=codigo,
                defaults={
                    'nombre':                data.get('nombre', codigo),
                    'asunto_template':       data['asunto_template'],
                    'cuerpo_template':       data['cuerpo_template'],
                    'tipo':                  data['tipo'],
                    'modulo':                data['modulo'],
                    'variables_disponibles': data['variables_disponibles'],
                    'activa':                True,
                },
            )
            if created:
                self.stdout.write(f'  [plantilla] creada: {codigo}')

    def _empresa(self):
        try:
            from asistencia.models import ConfiguracionSistema
            c = ConfiguracionSistema.get()
            return c.empresa_nombre or 'la empresa'
        except Exception:
            return 'la empresa'

    def _primer_nombre(self, apellidos_nombres: str) -> str:
        """Extrae el primer nombre de 'APELLIDOS, Nombres'."""
        if not apellidos_nombres:
            return ''
        if ',' in apellidos_nombres:
            nombres_part = apellidos_nombres.split(',', 1)[1].strip()
            return nombres_part.split()[0].capitalize() if nombres_part else apellidos_nombres
        return apellidos_nombres.split()[0].capitalize()

    def _enviar(self, personal, codigo: str, contexto: dict, dry_run: bool) -> bool:
        """Envía notificación desde plantilla. Retorna True si OK."""
        if dry_run:
            return True
        try:
            from comunicaciones.services import NotificacionService
            NotificacionService.enviar_desde_plantilla(
                destinatario=personal,
                plantilla_codigo=codigo,
                contexto_dict=contexto,
            )
            return True
        except Exception as exc:
            self.stderr.write(f'    ERROR al enviar a {personal}: {exc}')
            return False

    # ── Procesadores ──────────────────────────────────────────────────────────

    def _procesar_cumpleanos(self, hoy: date, dry_run: bool) -> int:
        """Felicitación a empleados activos que cumplen años hoy."""
        from personal.models import Personal

        cumpleaneros = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__isnull=False,
            fecha_nacimiento__month=hoy.month,
            fecha_nacimiento__day=hoy.day,
        )

        empresa = self._empresa()
        count   = 0
        for p in cumpleaneros:
            nombre = self._primer_nombre(p.apellidos_nombres)
            self.stdout.write(f'  [cumpleanos] {p.apellidos_nombres}')
            ok = self._enviar(p, 'cumpleanos_felicitacion',
                              {'nombre': nombre, 'empresa': empresa}, dry_run)
            if ok:
                count += 1
        return count

    def _procesar_aniversarios(self, hoy: date, dry_run: bool) -> int:
        """Reconocimiento a empleados activos que cumplen N años laborales hoy."""
        from personal.models import Personal

        candidatos = Personal.objects.filter(
            estado='Activo',
            fecha_alta__isnull=False,
            fecha_alta__month=hoy.month,
            fecha_alta__day=hoy.day,
        ).exclude(fecha_alta=hoy)  # excluir ingresados hoy mismo

        empresa = self._empresa()
        count   = 0
        for p in candidatos:
            anios = hoy.year - p.fecha_alta.year
            if anios <= 0:
                continue
            nombre = self._primer_nombre(p.apellidos_nombres)
            self.stdout.write(f'  [aniversario] {p.apellidos_nombres} — {anios} ano(s)')
            ok = self._enviar(p, 'aniversario_laboral',
                              {'nombre': nombre, 'empresa': empresa, 'anios': anios}, dry_run)
            if ok:
                count += 1
        return count

    def _procesar_periodo_prueba(self, hoy: date, dry_run: bool) -> int:
        """Aviso a empleados cuyo período de prueba termina en 15 / 7 / 1 día."""
        from personal.models import Personal

        # Solo activos ingresados en el último año (máximo período prueba = 12 meses dirección)
        fecha_corte = hoy - timedelta(days=380)
        candidatos  = Personal.objects.filter(
            estado='Activo',
            fecha_alta__isnull=False,
            fecha_alta__gte=fecha_corte,
        )

        count = 0
        for p in candidatos:
            fin_pp = p.fecha_fin_periodo_prueba
            if not fin_pp or fin_pp < hoy:
                continue
            dias = (fin_pp - hoy).days
            if dias not in _DIAS_AVISO_PERIODO_PRUEBA:
                continue
            nombre = self._primer_nombre(p.apellidos_nombres)
            self.stdout.write(
                f'  [periodo_prueba] {p.apellidos_nombres} — {dias} dia(s) restantes '
                f'(fin: {fin_pp})'
            )
            ok = self._enviar(p, 'fin_periodo_prueba_aviso',
                              {'nombre': nombre,
                               'fecha_fin': fin_pp.strftime('%d/%m/%Y'),
                               'dias_restantes': dias}, dry_run)
            if ok:
                count += 1
        return count
