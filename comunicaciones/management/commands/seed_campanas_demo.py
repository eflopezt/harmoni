"""
Seed de 3 campañas demo para CampanaComunicacion.

Crea (idempotente por nombre):
  1. BORRADOR — Cocineros de Miraflores (canal IN_APP, sin enviar)
  2. PROGRAMADA — Staff próxima semana (canal IN_APP)
  3. ENVIADA — Bienvenida birthday week (canal IN_APP)

No envía nada realmente (todos IN_APP, no requiere SMTP ni WhatsApp).
"""
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from comunicaciones.models import CampanaComunicacion
from comunicaciones.segmentacion import resolver_destinatarios


class Command(BaseCommand):
    help = 'Crea 3 campañas demo de comunicación (idempotente).'

    def handle(self, *args, **opts):
        autor = User.objects.filter(is_superuser=True).first()

        # 1. BORRADOR — Cocineros Miraflores
        c1, created1 = CampanaComunicacion.objects.get_or_create(
            nombre='Capacitación cocineros — Miraflores',
            defaults={
                'asunto': 'Capacitación obligatoria: nuevas técnicas de mise en place',
                'cuerpo': (
                    '<p>Estimado equipo de cocina,</p>'
                    '<p>El próximo viernes tendremos una sesión de capacitación '
                    'sobre nuevas técnicas de <strong>mise en place</strong>. '
                    'Asistencia obligatoria.</p>'
                    '<p>— Chef Ejecutivo</p>'
                ),
                'canal': 'IN_APP',
                'estado': 'BORRADOR',
                'filtro_cargo': 'cocinero',
                'filtro_solo_activos': True,
                'creado_por': autor,
            }
        )
        if created1:
            c1.destinatarios_count = resolver_destinatarios(c1).count()
            c1.save(update_fields=['destinatarios_count'])
            self.stdout.write(self.style.SUCCESS(
                f'  [+] BORRADOR: "{c1.nombre}" — {c1.destinatarios_count} destinatarios estimados'
            ))

        # 2. PROGRAMADA — Staff próxima semana
        c2, created2 = CampanaComunicacion.objects.get_or_create(
            nombre='Reunión mensual STAFF — Próxima semana',
            defaults={
                'asunto': 'Reunión mensual del equipo administrativo',
                'cuerpo': (
                    '<p>Hola equipo,</p>'
                    '<p>Recordatorio: nuestra reunión mensual será el próximo lunes '
                    'a las 9:00 AM en sala de directorio.</p>'
                    '<p>— RRHH</p>'
                ),
                'canal': 'IN_APP',
                'estado': 'PROGRAMADA',
                'filtro_grupo_tareo': 'STAFF',
                'filtro_solo_activos': True,
                'programada_para': timezone.now() + timedelta(days=7),
                'creado_por': autor,
            }
        )
        if created2:
            c2.destinatarios_count = resolver_destinatarios(c2).count()
            c2.save(update_fields=['destinatarios_count'])
            self.stdout.write(self.style.SUCCESS(
                f'  [+] PROGRAMADA: "{c2.nombre}" — {c2.destinatarios_count} destinatarios estimados'
            ))

        # 3. ENVIADA — Birthday week (simulada)
        c3, created3 = CampanaComunicacion.objects.get_or_create(
            nombre='Felicitaciones cumpleañeros de la semana',
            defaults={
                'asunto': '¡Feliz cumpleaños! 🎉',
                'cuerpo': (
                    '<p>Te deseamos un excelente cumpleaños y un año lleno de éxitos.</p>'
                    '<p>— Todo el equipo</p>'
                ),
                'canal': 'IN_APP',
                'estado': 'ENVIADA',
                'filtro_solo_activos': True,
                'enviada_en': timezone.now() - timedelta(days=2),
                'destinatarios_count': 12,
                'enviados_ok': 12,
                'enviados_fallidos': 0,
                'creado_por': autor,
            }
        )
        if created3:
            self.stdout.write(self.style.SUCCESS(
                f'  [+] ENVIADA: "{c3.nombre}" — 12 destinatarios simulados'
            ))

        total = CampanaComunicacion.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f'\nOK. Total CampanaComunicacion en BD: {total}'
        ))
