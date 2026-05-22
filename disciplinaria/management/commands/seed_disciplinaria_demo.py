"""
Seed demo de medidas disciplinarias para el módulo Disciplinaria.

Crea 8 medidas para distintos trabajadores con mix de tipos:
- 3 tardanzas escalonadas (verbal → escrita → suspensión 1d) en el mismo trabajador
- Faltas injustificadas
- Higiene (gastro-specific)
- Estados variados: BORRADOR, NOTIFICADA, EN_DESCARGO, RESUELTA

Asegura que `seed_tipos_falta` se haya ejecutado primero.

Uso:
    python manage.py seed_disciplinaria_demo
    python manage.py seed_disciplinaria_demo --reset   # borra demos previas
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from disciplinaria.models import MedidaDisciplinaria, TipoFalta
from personal.models import Personal


class Command(BaseCommand):
    help = 'Crea medidas disciplinarias demo (8 medidas, 1 trabajador con 3 escalonadas).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Elimina medidas demo previas antes de crear',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        # Asegurar TipoFalta existe
        if not TipoFalta.objects.exists():
            self.stdout.write(self.style.WARNING(
                'No hay TipoFalta. Ejecutando seed_tipos_falta primero...'
            ))
            from django.core.management import call_command
            call_command('seed_tipos_falta')

        tf_tardanza = TipoFalta.objects.filter(codigo='tardanza').first() \
            or TipoFalta.objects.filter(gravedad='LEVE').first()
        tf_falta_inj = TipoFalta.objects.filter(codigo='inasistencia-injustificada').first() \
            or TipoFalta.objects.filter(gravedad='GRAVE').first()
        tf_higiene = TipoFalta.objects.filter(codigo='vestimenta').first() \
            or TipoFalta.objects.filter(codigo='higiene').first() \
            or tf_tardanza
        tf_ssoma = TipoFalta.objects.filter(codigo='incumplimiento-ssoma').first() \
            or TipoFalta.objects.filter(gravedad='GRAVE').first()

        if not all([tf_tardanza, tf_falta_inj, tf_higiene, tf_ssoma]):
            self.stdout.write(self.style.ERROR(
                'No se encontraron tipos de falta necesarios. Aborta.'
            ))
            return

        personal_activos = list(
            Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')[:8]
        )
        if len(personal_activos) < 4:
            self.stdout.write(self.style.WARNING(
                f'Solo {len(personal_activos)} trabajadores activos encontrados. '
                f'Se requieren al menos 4 para datos demo significativos. '
                f'Se ejecutará con los disponibles.'
            ))

        if not personal_activos:
            self.stdout.write(self.style.ERROR(
                'No hay personal activo en la BD. Aborta.'
            ))
            return

        if opts.get('reset'):
            # Borrar medidas demo previas (descripción marcada con [DEMO])
            n = MedidaDisciplinaria.objects.filter(
                descripcion_hechos__startswith='[DEMO]',
            ).delete()
            self.stdout.write(self.style.WARNING(f'Eliminadas {n[0]} medidas demo previas.'))

        hoy = date.today()
        creadas = 0

        def crear(personal, tipo_medida, tipo_falta, fecha_hechos, descripcion,
                  estado='NOTIFICADA', dias_suspension=0, fecha_resolucion=None,
                  fecha_preaviso=None):
            nonlocal creadas
            m = MedidaDisciplinaria(
                personal=personal,
                tipo_medida=tipo_medida,
                tipo_falta=tipo_falta,
                fecha_hechos=fecha_hechos,
                descripcion_hechos='[DEMO] ' + descripcion,
                estado=estado,
                dias_suspension=dias_suspension,
            )
            if fecha_preaviso:
                m.fecha_carta_preaviso = fecha_preaviso
            if estado in ('NOTIFICADA', 'EN_DESCARGO'):
                if not m.fecha_carta_preaviso:
                    m.fecha_carta_preaviso = fecha_hechos + timedelta(days=2)
                m.fecha_limite_descargo = m.fecha_carta_preaviso + timedelta(days=6)
            if estado == 'RESUELTA':
                m.fecha_resolucion = fecha_resolucion or (fecha_hechos + timedelta(days=10))
                m.resolucion = 'Resolución demo: se confirma la sanción aplicada.'
                if not m.fecha_carta_preaviso:
                    m.fecha_carta_preaviso = fecha_hechos + timedelta(days=2)
                if not m.fecha_limite_descargo:
                    m.fecha_limite_descargo = m.fecha_carta_preaviso + timedelta(days=6)
            m.save()
            creadas += 1
            return m

        # ── Trabajador #1: 3 tardanzas escalonadas ──
        p1 = personal_activos[0]
        crear(
            p1, 'VERBAL', tf_tardanza,
            hoy - timedelta(days=90),
            'Tardanza de 15 minutos en el turno mañana. Primera ocurrencia.',
            estado='RESUELTA',
            fecha_resolucion=hoy - timedelta(days=82),
        )
        crear(
            p1, 'ESCRITA', tf_tardanza,
            hoy - timedelta(days=45),
            'Segunda tardanza reiterada (22 minutos). Se emite memorándum de amonestación escrita.',
            estado='RESUELTA',
            fecha_resolucion=hoy - timedelta(days=35),
        )
        crear(
            p1, 'SUSPENSION', tf_tardanza,
            hoy - timedelta(days=10),
            'Tercera tardanza reiterada (35 minutos). Se aplica suspensión sin goce de 1 día '
            'conforme al principio de progresividad.',
            estado='NOTIFICADA',
            dias_suspension=1,
        )

        # ── Trabajador #2: falta injustificada en descargo ──
        if len(personal_activos) > 1:
            p2 = personal_activos[1]
            crear(
                p2, 'ESCRITA', tf_falta_inj,
                hoy - timedelta(days=8),
                'Inasistencia injustificada el día sábado durante el turno de mayor afluencia '
                'en el local. No se reportó al supervisor.',
                estado='EN_DESCARGO',
                fecha_preaviso=hoy - timedelta(days=6),
            )

        # ── Trabajador #3: incumplimiento higiene (resuelta) ──
        if len(personal_activos) > 2:
            p3 = personal_activos[2]
            crear(
                p3, 'VERBAL', tf_higiene,
                hoy - timedelta(days=60),
                'Incumplimiento de normas de higiene en cocina: no uso de gorro y guantes '
                'durante manipulación de alimentos.',
                estado='RESUELTA',
                fecha_resolucion=hoy - timedelta(days=55),
            )

        # ── Trabajador #4: borrador (pendiente notificar) ──
        if len(personal_activos) > 3:
            p4 = personal_activos[3]
            crear(
                p4, 'ESCRITA', tf_ssoma,
                hoy - timedelta(days=3),
                'No utilizó EPP (zapatos antideslizantes) durante labores en cocina. '
                'Tercera observación en el mes.',
                estado='BORRADOR',
            )

        # ── Trabajador #5: suspensión notificada ──
        if len(personal_activos) > 4:
            p5 = personal_activos[4]
            crear(
                p5, 'SUSPENSION', tf_falta_inj,
                hoy - timedelta(days=15),
                'Tres inasistencias en 30 días sin justificación. Se aplica suspensión sin goce.',
                estado='NOTIFICADA',
                dias_suspension=3,
            )

        # ── Trabajador #6: amonestación verbal resuelta ──
        if len(personal_activos) > 5:
            p6 = personal_activos[5]
            crear(
                p6, 'VERBAL', tf_tardanza,
                hoy - timedelta(days=20),
                'Tardanza ocasional. Primera vez en su record laboral.',
                estado='RESUELTA',
                fecha_resolucion=hoy - timedelta(days=15),
            )

        self.stdout.write(self.style.SUCCESS(
            f'OK — {creadas} medidas disciplinarias demo creadas.'
        ))
        self.stdout.write(self.style.HTTP_INFO(
            f'Trabajador con timeline escalonado: {p1.apellidos_nombres} (pk={p1.pk})'
        ))
