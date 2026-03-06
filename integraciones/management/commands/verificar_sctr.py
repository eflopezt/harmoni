"""
Verificación diaria de vencimiento de pólizas SCTR.

Ejecutar vía cron o Render scheduler:
    manage.py verificar_sctr
    manage.py verificar_sctr --dry-run

Detecta y notifica:
  1. Pólizas VENCIDAS HOY  → alerta crítica a RRHH (IN_APP + EMAIL)
  2. Pólizas con N días para vencer (según dias_alerta de cada póliza) → aviso a RRHH
  3. Auto-actualiza estado a 'VENCIDA' si fecha_fin < hoy
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Verifica vencimiento de pólizas SCTR y envía alertas a RRHH.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra, no envía notificaciones.',
        )

    def handle(self, *args, **options):
        from integraciones.models import PolizaSCTR

        dry_run = options['dry_run']
        hoy     = timezone.localdate()
        prefix  = '[DRY-RUN] ' if dry_run else ''

        polizas = PolizaSCTR.objects.filter(activa=True)

        n_vencidas  = 0
        n_alertas   = 0
        n_renovadas = 0

        for p in polizas:
            dias = (p.fecha_fin - hoy).days

            # ── 1. Auto-actualizar estado si venció ──
            if dias < 0 and p.estado == 'VIGENTE':
                if not dry_run:
                    p.estado = 'VENCIDA'
                    p.activa = False
                    p.save(update_fields=['estado', 'activa'])
                self.stdout.write(
                    self.style.ERROR(
                        f'  {prefix}[VENCIDA] {p.numero_poliza} ({p.get_tipo_display()}) '
                        f'— {p.proveedor_nombre} — venció el {p.fecha_fin}'
                    )
                )
                self._notificar_vencida(p, dry_run)
                n_vencidas += 1

            # ── 2. Alerta si está próxima a vencer ──
            elif 0 <= dias <= p.dias_alerta and p.estado == 'VIGENTE':
                self.stdout.write(
                    self.style.WARNING(
                        f'  {prefix}[ALERTA] {p.numero_poliza} ({p.get_tipo_display()}) '
                        f'— vence en {dias} día(s) ({p.fecha_fin})'
                    )
                )
                self._notificar_alerta(p, dias, dry_run)
                n_alertas += 1

        total = n_vencidas + n_alertas
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix}verificar_sctr {hoy} — '
                f'vencidas_hoy:{n_vencidas} alertas:{n_alertas} TOTAL:{total}'
            )
        )

    def _get_rrhh_users(self):
        """Retorna queryset de usuarios con permiso de RRHH (superuser o staff)."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        return User.objects.filter(is_active=True, is_staff=True)[:5]

    def _notificar_vencida(self, poliza, dry_run: bool):
        """Alerta crítica: póliza ya venció."""
        if dry_run:
            return
        try:
            from comunicaciones.services import NotificacionService
            from personal.models import Personal

            asunto = f'🚨 Póliza SCTR VENCIDA: {poliza.numero_poliza}'
            cuerpo = (
                f'<p><strong>ALERTA CRÍTICA:</strong> La póliza SCTR '
                f'<strong>{poliza.numero_poliza}</strong> ({poliza.get_tipo_display()}) '
                f'de <strong>{poliza.proveedor_nombre}</strong> '
                f'<span style="color:red;">venció el {poliza.fecha_fin}</span>.</p>'
                f'<p>Se requiere renovación inmediata para mantener la cobertura legal '
                f'de los trabajadores.</p>'
                f'<p><strong>Trabajadores cubiertos:</strong> {poliza.trabajadores_cubiertos}</p>'
            )
            # Notificar a todos los usuarios RRHH/staff
            for user in self._get_rrhh_users():
                personal = getattr(user, 'personal_data', None)
                if personal:
                    NotificacionService.enviar(
                        destinatario = personal,
                        asunto       = asunto,
                        cuerpo       = cuerpo,
                        tipo         = 'AMBOS',
                        destinatario_email = user.email,
                    )
        except Exception as exc:
            self.stderr.write(f'    ERROR notificando vencimiento SCTR: {exc}')

    def _notificar_alerta(self, poliza, dias: int, dry_run: bool):
        """Alerta preventiva: póliza próxima a vencer."""
        if dry_run:
            return
        # Solo notificar en días específicos para no ser spam
        if dias not in (30, 15, 7, 3, 1):
            return
        try:
            from comunicaciones.services import NotificacionService

            asunto = f'⚠️ Póliza SCTR vence en {dias} día(s): {poliza.numero_poliza}'
            cuerpo = (
                f'<p>La póliza SCTR <strong>{poliza.numero_poliza}</strong> '
                f'({poliza.get_tipo_display()}) de <strong>{poliza.proveedor_nombre}</strong> '
                f'vence el <strong>{poliza.fecha_fin}</strong> '
                f'(en <strong>{dias} día(s)</strong>).</p>'
                f'<p>Gestione la renovación con anticipación para evitar cobertura descontinuada.</p>'
            )
            for user in self._get_rrhh_users():
                personal = getattr(user, 'personal_data', None)
                if personal:
                    NotificacionService.enviar(
                        destinatario = personal,
                        asunto       = asunto,
                        cuerpo       = cuerpo,
                        tipo         = 'IN_APP',
                    )
        except Exception as exc:
            self.stderr.write(f'    ERROR notificando alerta SCTR: {exc}')
