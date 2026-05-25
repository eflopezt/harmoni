"""
core/audit_signals.py — Sistema de signals para AuditEntry.

Uso:
    from core.audit_signals import register_auditable
    from personal.models import Personal

    register_auditable(Personal, fields_to_track=['sueldo_base', 'cargo', 'estado', 'fecha_cese'])

El registro engancha:
- `pre_save`  → snapshot ANTES del cambio (in-memory) para calcular diff
- `post_save` → crea AuditEntry CREATE o UPDATE con diff
- `post_delete` → crea AuditEntry DELETE

El usuario y la IP se toman del thread-local set por `core.middleware.AuditMiddleware`.
Si no hay request (Celery/command), `usuario=None` y `metadata['source']` indica el origen.

Diseño:
- `_PRE_SAVE_SNAPSHOTS` es un dict thread-local indexado por id(instance) → dict
  de valores ANTES. Se limpia en post_save/post_delete para no leak memoria.
- El registro es idempotente: registrar dos veces el mismo modelo no conecta
  signals duplicados (dispatch_uid garantizado por sender+nombre).
"""
from __future__ import annotations

import logging
import threading
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable

from django.db.models.signals import post_delete, post_save, pre_save

from core.audit import get_current_request, _get_client_ip

logger = logging.getLogger('harmoni.audit')

# Thread-local: snapshots de valores ANTES por instancia (id() como key).
# Se borra en post_save/post_delete para evitar leak en procesos long-lived.
_thread = threading.local()

# Registry: { model_label: [fields_to_track] }. Útil para introspección/tests.
_REGISTERED: dict[str, list[str]] = {}


def _snapshots() -> dict:
    if not hasattr(_thread, 'snapshots'):
        _thread.snapshots = {}
    return _thread.snapshots


def _serialize(value):
    """Convierte un valor a algo serializable para JSON."""
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, 'pk'):
        return str(value)
    if isinstance(value, (list, tuple, dict, str, int, float, bool)):
        return value
    return str(value)


def _capture_fields(instance, fields: list[str]) -> dict:
    """Extrae {campo: valor_serializado} del instance (solo campos pedidos)."""
    out = {}
    for f in fields:
        try:
            # Usa el FK id directo para evitar query extra.
            field_obj = instance._meta.get_field(f)
            if field_obj.is_relation and field_obj.many_to_one:
                out[f] = getattr(instance, f'{f}_id', None)
            else:
                out[f] = _serialize(getattr(instance, f, None))
        except Exception:
            out[f] = _serialize(getattr(instance, f, None))
    return out


def _diff(old: dict, new: dict) -> dict:
    """Genera {campo: {'old':X, 'new':Y}} solo para campos cambiados."""
    out = {}
    for k, new_v in new.items():
        old_v = old.get(k)
        if old_v != new_v:
            out[k] = {'old': old_v, 'new': new_v}
    return out


def _build_metadata(source_hint: str | None = None) -> dict:
    """Arma metadata estándar (IP, user_agent, source) desde el request."""
    request = get_current_request()
    meta: dict = {}
    if request is not None:
        meta['request_ip'] = _get_client_ip(request)
        ua = request.META.get('HTTP_USER_AGENT', '')
        if ua:
            meta['user_agent'] = ua[:255]
        meta['source'] = source_hint or 'web'
        path = getattr(request, 'path', '')
        if path:
            meta['path'] = path[:255]
    else:
        meta['source'] = source_hint or 'signal'
    return meta


def _resolve_user():
    """Devuelve el User actual del request, o None."""
    request = get_current_request()
    if request is None:
        return None
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    return None


def _resolve_empresa(instance):
    """Intenta encontrar la empresa asociada al instance (FK directo o vía personal)."""
    # FK directo
    if hasattr(instance, 'empresa_id') and instance.empresa_id:
        try:
            from empresas.models import Empresa
            return Empresa.objects.filter(pk=instance.empresa_id).first()
        except Exception:
            return None
    # Vía personal
    personal = getattr(instance, 'personal', None)
    if personal is not None:
        emp_id = getattr(personal, 'empresa_id', None)
        if emp_id:
            try:
                from empresas.models import Empresa
                return Empresa.objects.filter(pk=emp_id).first()
            except Exception:
                return None
    return None


def register_auditable(model, fields_to_track: Iterable[str] | None = None):
    """Conecta signals para auditar el modelo dado.

    Args:
        model: Clase Django Model (no string).
        fields_to_track: lista de campos a observar para detectar cambios.
                         Si es None, observa TODOS los campos concretos.

    Returns:
        El propio model (para encadenar / decorador).

    Idempotente: si se llama dos veces para el mismo modelo, el primer registro
    se respeta y el segundo se ignora (con warning).
    """
    label = f'{model._meta.app_label}.{model._meta.object_name}'

    if label in _REGISTERED:
        logger.warning('register_auditable: %s ya estaba registrado, ignorando.', label)
        return model

    if fields_to_track is None:
        fields = [f.name for f in model._meta.concrete_fields
                  if not f.primary_key]
    else:
        fields = list(fields_to_track)

    _REGISTERED[label] = fields

    # ── pre_save: snapshot del estado anterior ──
    def _on_pre_save(sender, instance, **kwargs):
        if instance.pk is None:
            return  # CREATE — nada que snapshotear
        try:
            previous = sender.objects.filter(pk=instance.pk).first()
        except Exception:
            previous = None
        if previous is None:
            return
        _snapshots()[id(instance)] = _capture_fields(previous, fields)

    # ── post_save: crea AuditEntry CREATE o UPDATE ──
    def _on_post_save(sender, instance, created, **kwargs):
        from core.audit_models import AuditEntry
        new_vals = _capture_fields(instance, fields)
        snap = _snapshots().pop(id(instance), None)

        if created:
            cambios = {f: {'old': None, 'new': v} for f, v in new_vals.items()}
            accion = 'CREATE'
        else:
            if snap is None:
                # No teníamos snapshot → no podemos calcular diff fiable;
                # registrar UPDATE genérico sin diff por campo.
                cambios = {}
            else:
                cambios = _diff(snap, new_vals)
                if not cambios:
                    # Nada cambió en los campos trackeados → no registrar.
                    return
            accion = 'UPDATE'

        try:
            AuditEntry.objects.create(
                entity_type=model._meta.object_name,
                entity_id=instance.pk,
                accion=accion,
                cambios=cambios,
                metadata=_build_metadata(),
                usuario=_resolve_user(),
                empresa=_resolve_empresa(instance),
            )
        except Exception as exc:
            # No queremos romper la transacción del usuario por un fallo de audit.
            logger.warning('AuditEntry create falló para %s#%s: %s',
                           label, instance.pk, exc)

    # ── post_delete: registra eliminación ──
    def _on_post_delete(sender, instance, **kwargs):
        from core.audit_models import AuditEntry
        try:
            old_vals = _capture_fields(instance, fields)
            cambios = {f: {'old': v, 'new': None} for f, v in old_vals.items()}
            AuditEntry.objects.create(
                entity_type=model._meta.object_name,
                entity_id=instance.pk or 0,
                accion='DELETE',
                cambios=cambios,
                metadata=_build_metadata(),
                usuario=_resolve_user(),
                empresa=_resolve_empresa(instance),
            )
        except Exception as exc:
            logger.warning('AuditEntry delete falló para %s: %s', label, exc)
        finally:
            _snapshots().pop(id(instance), None)

    dispatch_uid = f'audit_entry_{label}'
    pre_save.connect(_on_pre_save, sender=model,
                     dispatch_uid=f'{dispatch_uid}_pre')
    post_save.connect(_on_post_save, sender=model,
                      dispatch_uid=f'{dispatch_uid}_post')
    post_delete.connect(_on_post_delete, sender=model,
                        dispatch_uid=f'{dispatch_uid}_del')

    logger.info('register_auditable: %s registrado (%d campos)', label, len(fields))
    return model


def get_registered() -> dict[str, list[str]]:
    """Retorna snapshot del registry (para introspección/tests)."""
    return dict(_REGISTERED)


def _reset_registry_for_tests():
    """Limpia el registry y desconecta signals — SOLO para tests."""
    for label, _fields in list(_REGISTERED.items()):
        # No tenemos referencia a la clase aquí; lo dejamos como no-op y los
        # tests que requieran limpieza usarán flush + restart de la app.
        pass
    _REGISTERED.clear()


def auto_register_default_models():
    """Registra los modelos críticos definidos en el plan estabilización Q2 2026.

    Se llama una sola vez desde `CoreConfig.ready()`. Si un modelo falla al
    importarse (app no instalada en algún entorno), se loguea warning y sigue.
    """
    targets = [
        ('personal',   'Personal',
         ['sueldo_base', 'cargo', 'cargo_obj', 'estado', 'fecha_cese',
          'motivo_cese', 'area', 'grupo_tareo', 'condicion', 'categoria']),
        ('vacaciones', 'SolicitudVacacion',
         ['estado', 'fecha_inicio', 'fecha_fin', 'dias_calendario',
          'aprobado_por', 'fecha_aprobacion', 'motivo_rechazo']),
        ('prestamos',  'Prestamo',
         ['monto_solicitado', 'monto_aprobado', 'num_cuotas', 'cuota_mensual',
          'tasa_interes', 'estado', 'fecha_aprobacion', 'fecha_desembolso']),
        # NOTE: la app `asistencia` está registrada con label='tareo' en
        # asistencia/apps.py (preserva tablas legacy). Usamos el label real.
        ('tareo',      'RegistroPapeleta',
         ['estado', 'tipo_permiso', 'fecha_inicio', 'fecha_fin',
          'fecha_referencia', 'dias_habiles']),
        ('nominas',    'PeriodoNomina',
         ['estado', 'total_bruto', 'total_neto', 'total_descuentos',
          'total_trabajadores', 'fecha_pago', 'contabilizado']),
    ]
    from django.apps import apps as django_apps
    for app_label, model_name, fields in targets:
        try:
            model = django_apps.get_model(app_label, model_name)
            if model is None:
                logger.warning('auto_register_default_models: %s.%s no existe',
                               app_label, model_name)
                continue
            register_auditable(model, fields_to_track=fields)
        except LookupError:
            logger.warning('auto_register_default_models: app %s no instalada',
                           app_label)
        except Exception as exc:
            logger.exception('auto_register_default_models: error en %s.%s: %s',
                             app_label, model_name, exc)
