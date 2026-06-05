"""
Signals para Plan Starter — early upsell alerts.

Cuando una empresa Starter alcanza 28 trabajadores activos (≥93% del cap),
enviamos un email a ventas para contactar al cliente proactivamente.

Tope alert: 28 (de 30) — deja margen para reaccionar antes del block.

Anti-flood: alerta solo 1 vez por empresa+día via cache (sentinel 24h TTL).
"""
import logging

from django.conf import settings
from django.core.cache import cache
from django.core.mail import mail_admins, send_mail
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

logger = logging.getLogger('core.plan_starter_signals')


# Tope de trabajadores por plan: fuente única core/planes.py
from core.planes import plan_max_trabajadores

# Email destinatario de alertas
VENTAS_EMAIL = getattr(settings, 'VENTAS_ALERT_EMAIL', 'ventas@harmoni.pe')


def _maybe_alert_upsell(empresa):
    """Verifica si la empresa cruzó umbral de alerta. Envía mail si sí."""
    if not empresa or not empresa.plan:
        return

    tope = plan_max_trabajadores(empresa.plan)
    if tope is None:
        return  # ENTERPRISE no tiene tope

    # Umbral relativo: 93% del tope
    threshold = int(tope * 0.93)

    try:
        from personal.models import Personal
        actuales = Personal.objects.filter(
            empresa=empresa, estado='Activo',
        ).count()
    except Exception:
        return

    if actuales < threshold:
        return  # aún hay margen

    # Anti-flood: solo 1 alerta por día por empresa
    cache_key = f'upsell_alert:{empresa.pk}:{empresa.plan}'
    if cache.get(cache_key):
        return  # ya alertamos hoy
    cache.set(cache_key, True, timeout=86400)  # 24h

    subject = (
        f'[Harmoni — Upsell] {empresa.razon_social} alcanzó {actuales}/{tope} '
        f'workers (Plan {empresa.plan})'
    )
    body = (
        f'La empresa {empresa.razon_social} (RUC {empresa.ruc}) está cerca '
        f'del cap de su plan actual:\n\n'
        f'  Plan:                {empresa.plan}\n'
        f'  Trabajadores activos:{actuales} / {tope}\n'
        f'  Uso:                 {int(actuales/tope*100)}%\n\n'
        f'Recomendación: contactar al cliente para ofrecer upgrade al plan '
        f'siguiente antes de que llegue al tope (en cuyo caso no podrá dar '
        f'de alta más trabajadores).\n\n'
        f'Contacto: {empresa.email_rrhh or "(no registrado)"} | '
        f'{empresa.telefono or "(sin teléfono)"}\n'
    )

    try:
        send_mail(
            subject, body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[VENTAS_EMAIL],
            fail_silently=True,
        )
        logger.info(
            f'Upsell alert enviado: {empresa.razon_social} {actuales}/{tope}'
        )
    except Exception as e:
        logger.error(f'Error enviando upsell alert: {e}')


@receiver(pre_save, sender='personal.Personal')
def enforce_plan_worker_cap(sender, instance, **kwargs):
    """
    Hard cap a nivel signal — bloquea ALTA (no edición) si supera el tope.

    Captura altas que no llaman clean() — por ejemplo bulk_create.
    Lanza ValidationError que el caller debe manejar.
    """
    # Solo aplica a altas nuevas (sin pk) y workers activos
    if instance.pk is not None:
        return
    if getattr(instance, 'estado', None) == 'Inactivo':
        return
    if not instance.empresa_id:
        return
    try:
        plan = getattr(instance.empresa, 'plan', None)
    except Exception:
        return
    tope = plan_max_trabajadores(plan)
    if tope is None:
        return  # ENTERPRISE o plan desconocido — sin tope

    from personal.models import Personal
    actuales = Personal.objects.filter(
        empresa=instance.empresa,
        estado='Activo',
    ).count()
    if actuales >= tope:
        raise ValidationError(
            f'El Plan {plan} permite hasta {tope} trabajadores activos. '
            f'Esta empresa ya tiene {actuales}. '
            f'Actualiza a un plan superior en /upgrade/ para agregar más.'
        )


@receiver(post_save, sender='personal.Personal')
def alert_on_personal_save(sender, instance, created, **kwargs):
    """Alerta cuando se crea/activa un worker que cruza el threshold."""
    if not created and instance.estado != 'Activo':
        return  # solo nos interesan altas y reactivaciones
    try:
        _maybe_alert_upsell(instance.empresa)
    except Exception as e:
        logger.error(f'alert_on_personal_save error: {e}')
