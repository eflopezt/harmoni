"""
Signal handlers para registrar cambios sobre ConceptoRemunerativo.

Captura automática vía pre_save + post_save + post_delete:
- Compara estado anterior vs nuevo, registra solo campos modificados.
- Detecta CREATE vs UPDATE vs DELETE.
- Detecta activación/desactivación específicamente para visibilidad rápida.

Usuario y contexto se inyectan vía thread-local — set por middleware o vista.
"""
import threading
from decimal import Decimal

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import ConceptoAuditLog, ConceptoRemunerativo


# ─── Thread-local para inyectar usuario/contexto desde la vista ───────
_local = threading.local()


def set_audit_context(usuario=None, ip=None, user_agent=None, contexto=None, accion_override=None, empresa=None):
    """Llamado desde middleware o vista antes de save/delete."""
    _local.usuario = usuario
    _local.ip = ip
    _local.user_agent = user_agent or ''
    _local.contexto = contexto or ''
    _local.accion_override = accion_override
    _local.empresa = empresa


def clear_audit_context():
    for attr in ('usuario', 'ip', 'user_agent', 'contexto', 'accion_override', 'empresa'):
        if hasattr(_local, attr):
            delattr(_local, attr)


def _get_ctx():
    return {
        'usuario':       getattr(_local, 'usuario', None),
        'ip':            getattr(_local, 'ip', None),
        'user_agent':    getattr(_local, 'user_agent', ''),
        'contexto':      getattr(_local, 'contexto', ''),
        'accion_override': getattr(_local, 'accion_override', None),
        'empresa':       getattr(_local, 'empresa', None),
    }


def _empresa_actual_del_request(request=None):
    """Detecta la empresa activa del usuario.

    Estrategia:
    1. Si está en thread-local (set explícito) → úsala
    2. Si el usuario tiene Personal.empresa → úsala
    3. Si no, primera empresa de la DB
    """
    ctx_empresa = getattr(_local, 'empresa', None)
    if ctx_empresa:
        return ctx_empresa
    if request and request.user.is_authenticated:
        try:
            from personal.models import Personal
            p = Personal.objects.filter(usuario=request.user).select_related('empresa').first()
            if p and p.empresa:
                return p.empresa
        except Exception:
            pass
    try:
        from empresas.models import Empresa
        return Empresa.objects.order_by('pk').first()
    except Exception:
        return None


# ─── Campos a monitorear ──────────────────────────────────────────────
TRACKED_FIELDS = [
    'codigo', 'nombre', 'descripcion', 'categoria',
    'tipo', 'subtipo', 'formula', 'porcentaje', 'monto_fijo',
    'afecto_essalud', 'afecto_afp', 'afecto_onp',
    'afecto_renta', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
    'codigo_plame', 'casilla_plame', 'codigo_tregistro',
    'activo', 'orden',
]


def _serialize(value):
    """Convierte Decimal/None a algo JSON-compatible."""
    if isinstance(value, Decimal):
        return str(value)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    return str(value) if not isinstance(value, (int, float)) else value


# ─── pre_save: guardar snapshot del estado anterior ─────────────────
@receiver(pre_save, sender=ConceptoRemunerativo)
def concepto_pre_save(sender, instance, **kwargs):
    """Captura estado anterior en _audit_old para comparar luego en post_save."""
    if instance.pk:
        try:
            old = ConceptoRemunerativo.objects.get(pk=instance.pk)
            instance._audit_old = {f: getattr(old, f) for f in TRACKED_FIELDS}
        except ConceptoRemunerativo.DoesNotExist:
            instance._audit_old = None
    else:
        instance._audit_old = None


# ─── post_save: comparar y registrar ─────────────────────────────────
# ─── Campos críticos cuya modificación dispara email ──────────────
# Estos campos afectan cálculos legales y deben dejar trail VISIBLE.
CRITICAL_FIELDS = {
    'afecto_essalud', 'afecto_afp', 'afecto_onp',
    'afecto_renta', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
    'codigo_plame', 'casilla_plame',
    'tipo', 'subtipo', 'porcentaje',
}


def _enviar_email_cambio_critico(instance, cambios_criticos, usuario):
    """Envía email a admins cuando se modifica campo crítico de un concepto."""
    if not cambios_criticos:
        return
    try:
        from django.conf import settings as dj_settings
        from django.core.mail import send_mail
        from django.contrib.auth import get_user_model

        # Destinatarios: todos los superusers
        User = get_user_model()
        emails = list(User.objects.filter(
            is_superuser=True, is_active=True,
        ).exclude(email='').values_list('email', flat=True))
        if not emails:
            return

        user_name = (usuario.get_full_name() or usuario.username) if usuario else 'sistema (CLI)'
        cambios_str = '\n'.join(
            f'  • {k}: {v.get("antes")} → {v.get("despues")}'
            for k, v in cambios_criticos.items()
        )

        subject = f'[Harmoni Nóminas] Cambio crítico en concepto "{instance.codigo}"'
        body = f"""\
Se modificó un campo CRÍTICO en el catálogo de conceptos remunerativos:

Concepto:   [{instance.codigo}] {instance.nombre}
Modificado: {user_name}
Cambios:
{cambios_str}

Estos campos afectan cálculos legales (PLAME, afectaciones, fórmulas).
Si este cambio no fue autorizado, revisa el audit log de inmediato:

  /nominas/conceptos/configurar/{instance.pk}/historial/

Ignorar este aviso si el cambio fue intencional.

—
Harmoni ERP · Audit log automático
"""

        send_mail(
            subject=subject,
            message=body,
            from_email=getattr(dj_settings, 'DEFAULT_FROM_EMAIL', 'noreply@harmoni.pe'),
            recipient_list=emails,
            fail_silently=True,
        )
    except Exception:
        # Email es best-effort, NO falla la operación de save si email no se envía
        pass


@receiver(post_save, sender=ConceptoRemunerativo)
def concepto_post_save(sender, instance, created, **kwargs):
    ctx = _get_ctx()
    usuario = ctx['usuario']
    user_username = (usuario.username if usuario and hasattr(usuario, 'username') else '') or ''

    if created:
        # Crear log de creación con snapshot inicial completo
        cambios = {
            f: {'antes': None, 'despues': _serialize(getattr(instance, f))}
            for f in TRACKED_FIELDS
        }
        ConceptoAuditLog.objects.create(
            concepto=instance,
            concepto_codigo=instance.codigo,
            concepto_nombre=instance.nombre,
            accion=ctx['accion_override'] or 'CREATE',
            campos_cambiados=cambios,
            usuario=usuario,
            usuario_username=user_username,
            ip=ctx['ip'],
            user_agent=(ctx['user_agent'] or '')[:300],
            contexto=(ctx['contexto'] or '')[:200],
            empresa=ctx['empresa'],
        )
        return

    old = getattr(instance, '_audit_old', None)
    if not old:
        return

    # Comparar tracked fields → registrar solo los que cambiaron
    cambios = {}
    activo_cambio = None
    for f in TRACKED_FIELDS:
        v_antes = old.get(f)
        v_dsp   = getattr(instance, f)
        if v_antes != v_dsp:
            cambios[f] = {'antes': _serialize(v_antes), 'despues': _serialize(v_dsp)}
            if f == 'activo':
                activo_cambio = v_dsp

    if not cambios:
        return

    # Determinar acción
    if ctx['accion_override']:
        accion = ctx['accion_override']
    elif activo_cambio is True and len(cambios) == 1:
        accion = 'ACTIVAR'
    elif activo_cambio is False and len(cambios) == 1:
        accion = 'DESACTIVAR'
    else:
        accion = 'UPDATE'

    ConceptoAuditLog.objects.create(
        concepto=instance,
        concepto_codigo=instance.codigo,
        concepto_nombre=instance.nombre,
        accion=accion,
        campos_cambiados=cambios,
        usuario=usuario,
        usuario_username=user_username,
        ip=ctx['ip'],
        user_agent=(ctx['user_agent'] or '')[:300],
        contexto=(ctx['contexto'] or '')[:200],
        empresa=ctx['empresa'],
    )

    # Email alert si cambió un campo crítico (best-effort)
    criticos = {k: v for k, v in cambios.items() if k in CRITICAL_FIELDS}
    if criticos:
        _enviar_email_cambio_critico(instance, criticos, usuario)


# ─── post_delete: registrar eliminación ─────────────────────────────
@receiver(post_delete, sender=ConceptoRemunerativo)
def concepto_post_delete(sender, instance, **kwargs):
    ctx = _get_ctx()
    usuario = ctx['usuario']
    user_username = (usuario.username if usuario and hasattr(usuario, 'username') else '') or ''

    cambios = {
        f: {'antes': _serialize(getattr(instance, f)), 'despues': None}
        for f in TRACKED_FIELDS
    }
    ConceptoAuditLog.objects.create(
        concepto=None,  # se va con el SET_NULL
        concepto_codigo=instance.codigo,
        concepto_nombre=instance.nombre,
        accion='DELETE',
        campos_cambiados=cambios,
        usuario=usuario,
        usuario_username=user_username,
        ip=ctx['ip'],
        user_agent=(ctx['user_agent'] or '')[:300],
        contexto=(ctx['contexto'] or '')[:200],
        empresa=ctx['empresa'],
    )
