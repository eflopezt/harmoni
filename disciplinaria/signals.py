"""
Signals del módulo Disciplinaria.

Cuando se crea o pasa a estado notificado/en descargo una MedidaDisciplinaria,
se genera una Notificacion IN_APP al trabajador (si tiene Personal vinculado).

Maneja gracefully el caso en que el modelo Notificacion no exista (módulo
opcional).
"""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import MedidaDisciplinaria


# Estados que justifican notificar al trabajador
ESTADOS_NOTIFICAR_WORKER = {'NOTIFICADA', 'EN_DESCARGO', 'DESCARGO_RECIBIDO', 'RESUELTA'}


@receiver(post_save, sender=MedidaDisciplinaria)
def notificar_trabajador_in_app(sender, instance: MedidaDisciplinaria, created, **kwargs):
    """
    Crea una Notificacion IN_APP al trabajador cuando la medida está en
    un estado distinto de BORRADOR.

    - Solo crea la notificación una vez por (medida, estado) usando metadata
      para evitar duplicados en re-saves.
    """
    if not instance or not instance.personal_id:
        return
    if instance.estado not in ESTADOS_NOTIFICAR_WORKER:
        return

    # Importar Notificacion en runtime (módulo opcional)
    try:
        from comunicaciones.models import Notificacion
    except Exception:
        return

    # Evitar duplicados por save sucesivos en el mismo estado
    try:
        ya_existe = Notificacion.objects.filter(
            destinatario=instance.personal,
            metadata__modulo='disciplinaria',
            metadata__medida_id=instance.pk,
            metadata__estado=instance.estado,
        ).exists()
    except Exception:
        ya_existe = False
    if ya_existe:
        return

    tipo_label = instance.get_tipo_medida_display() if hasattr(instance, 'get_tipo_medida_display') else instance.tipo_medida
    asunto = f'Medida disciplinaria — {tipo_label}'
    cuerpo = (
        f'<i class="fas fa-gavel me-2"></i>'
        f'Has recibido una <strong>{tipo_label}</strong>. '
        f'Revisa tu portal para los detalles, plazo de descargo y descarga '
        f'de la carta correspondiente.<br>'
        f'<a href="/mi-portal/disciplinaria/">Ir al portal</a>'
    )

    try:
        Notificacion.objects.create(
            destinatario=instance.personal,
            asunto=asunto,
            cuerpo=cuerpo,
            tipo='IN_APP',
            estado='ENVIADA',
            enviada_en=timezone.now(),
            metadata={
                'modulo':   'disciplinaria',
                'medida_id': instance.pk,
                'estado':    instance.estado,
                'tipo_medida': instance.tipo_medida,
            },
        )
    except Exception:
        # Nunca romper el save de la medida por un fallo de notificación
        pass
