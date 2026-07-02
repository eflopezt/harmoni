"""
Signals para el módulo vacaciones.

Responsabilidades:
  - Invalidar caché del badge de superusers cuando cambia el estado de
    SolicitudVacacion o SolicitudPermiso.
  - Cuando se aprueba una SolicitudPermiso de tipo bajada (codigo=bajada-dl / bajada-dla),
    crear automáticamente las entradas de Roster correspondientes.
  - Cuando se aprueba una SolicitudVacacion, crear la RegistroPapeleta
    VACACIONES (fuente única de ausencias: el signal de asistencia la aplica
    al tareo) y marcar el Roster con código VAC.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
import logging

logger = logging.getLogger('personal.business')


# Estado previo cacheado para detectar transiciones BORRADOR/PENDIENTE → APROBADA/RECHAZADA
_estados_previos = {}


@receiver(pre_save, sender='vacaciones.SolicitudVacacion')
def cachear_estado_previo_vacacion(sender, instance, **kwargs):
    """Cachea el estado anterior antes de guardar — usado por el post_save
    para detectar transiciones y enviar notificaciones al trabajador.
    """
    if instance.pk:
        try:
            prev = sender.objects.only('estado').get(pk=instance.pk)
            _estados_previos[instance.pk] = prev.estado
        except sender.DoesNotExist:
            _estados_previos[instance.pk] = None


def _notif_trabajador_vacacion(solicitud, estado_anterior):
    """Crea notificación IN_APP al trabajador al cambiar el estado de su solicitud."""
    try:
        from comunicaciones.models import Notificacion
        if solicitud.estado == 'APROBADA' and estado_anterior in ('BORRADOR', 'PENDIENTE'):
            Notificacion.objects.create(
                destinatario=solicitud.personal,
                asunto=f'Tu solicitud de vacaciones fue APROBADA',
                cuerpo=(
                    f'<p>Tu solicitud del '
                    f'<b>{solicitud.fecha_inicio:%d/%m/%Y}</b> al '
                    f'<b>{solicitud.fecha_fin:%d/%m/%Y}</b> '
                    f'({solicitud.dias_calendario} días) ha sido aprobada.</p>'
                    f'<p>Puedes descargar tu constancia de vacaciones desde el portal.</p>'
                ),
                tipo='IN_APP',
                metadata={'solicitud_id': solicitud.pk, 'tipo': 'vacacion_aprobada'},
            )
        elif solicitud.estado == 'RECHAZADA' and estado_anterior in ('BORRADOR', 'PENDIENTE'):
            Notificacion.objects.create(
                destinatario=solicitud.personal,
                asunto='Tu solicitud de vacaciones fue rechazada',
                cuerpo=(
                    f'<p>Tu solicitud del '
                    f'<b>{solicitud.fecha_inicio:%d/%m/%Y}</b> al '
                    f'<b>{solicitud.fecha_fin:%d/%m/%Y}</b> fue rechazada.</p>'
                    f'<p>Motivo: {solicitud.motivo_rechazo or "sin especificar"}</p>'
                ),
                tipo='IN_APP',
                metadata={'solicitud_id': solicitud.pk, 'tipo': 'vacacion_rechazada'},
            )
    except Exception:
        pass  # Best-effort


def _invalidar_badge_superusers():
    """Borra el caché del badge de todos los superusers activos."""
    try:
        from django.core.cache import cache
        from django.contrib.auth.models import User
        pks = User.objects.filter(
            is_superuser=True, is_active=True
        ).values_list('pk', flat=True)
        cache.delete_many([f'harmoni_badge_{pk}_v3' for pk in pks])
    except Exception:
        pass


# ── Solicitudes de Vacación ────────────────────────────────────────────────────

@receiver(post_save, sender='vacaciones.SolicitudVacacion')
def badge_solicitud_vacacion(sender, instance, created=False, **kwargs):
    """Invalida badge al crear/modificar una solicitud de vacación.
    También dispara notif IN_APP al trabajador en transiciones de estado
    y sincroniza papeleta + roster al quedar APROBADA.
    """
    _invalidar_badge_superusers()
    estado_anterior = _estados_previos.pop(instance.pk, None)
    if estado_anterior and estado_anterior != instance.estado:
        _notif_trabajador_vacacion(instance, estado_anterior)

    aprobada_ahora = instance.estado == 'APROBADA' and (
        created or (estado_anterior and estado_anterior != 'APROBADA')
    )
    if aprobada_ahora:
        _sincronizar_vacacion_aprobada(instance)


def _sincronizar_vacacion_aprobada(solicitud):
    """Papeleta como fuente única de ausencias: al aprobar vacaciones se crea
    la RegistroPapeleta VACACIONES (su signal en asistencia la aplica al
    RegistroTareo del rango) y el Roster queda con código VAC.

    Idempotente (no duplica si ya hay papeleta VACACIONES solapada) y
    best-effort (un fallo no bloquea la aprobación).
    """
    _crear_papeleta_vacaciones(solicitud)
    _crear_roster_vacaciones(solicitud)


def _crear_papeleta_vacaciones(solicitud):
    try:
        from asistencia.models import RegistroPapeleta
        solapada = RegistroPapeleta.objects.filter(
            personal=solicitud.personal,
            tipo_permiso='VACACIONES',
            estado__in=['APROBADA', 'EJECUTADA'],
            fecha_inicio__lte=solicitud.fecha_fin,
            fecha_fin__gte=solicitud.fecha_inicio,
        ).exists()
        if solapada:
            logger.info(
                'Papeleta VAC ya existente para %s (%s→%s): no se duplica.',
                solicitud.personal.nro_doc,
                solicitud.fecha_inicio, solicitud.fecha_fin,
            )
            return
        RegistroPapeleta.objects.create(
            origen='SISTEMA',
            personal=solicitud.personal,
            dni=solicitud.personal.nro_doc,
            nombre_archivo=solicitud.personal.apellidos_nombres,
            tipo_permiso='VACACIONES',
            iniciales='VAC',
            fecha_inicio=solicitud.fecha_inicio,
            fecha_fin=solicitud.fecha_fin,
            detalle=f'Auto: SolicitudVacacion #{solicitud.pk} aprobada',
            dias_habiles=solicitud.dias_habiles,
            estado='APROBADA',
            creado_por=solicitud.aprobado_por,
            aprobado_por=solicitud.aprobado_por,
            fecha_aprobacion=solicitud.fecha_aprobacion,
        )
        logger.info(
            'Papeleta VAC auto-creada desde SolicitudVacacion #%s (%s, %s→%s)',
            solicitud.pk, solicitud.personal.nro_doc,
            solicitud.fecha_inicio, solicitud.fecha_fin,
        )
    except Exception as e:
        logger.warning('Error creando papeleta VAC desde solicitud #%s: %s',
                       solicitud.pk, e)


def _crear_roster_vacaciones(solicitud):
    """Marca VAC en el Roster para el rango aprobado (mismo patrón que las
    bajadas DL/DLA). Solo si el módulo roster está activo."""
    try:
        from asistencia.models import ConfiguracionSistema
        if not ConfiguracionSistema.get().mod_roster:
            return
    except Exception:
        return

    try:
        from personal.models import Roster
        from datetime import timedelta

        fecha = solicitud.fecha_inicio
        while fecha <= solicitud.fecha_fin:
            Roster.objects.update_or_create(
                personal=solicitud.personal,
                fecha=fecha,
                defaults={
                    'codigo':       'VAC',
                    'estado':       'aprobado',
                    'fuente':       f'SolicitudVacacion #{solicitud.pk}',
                    'observaciones': (solicitud.motivo or '')[:200],
                    'aprobado_por': solicitud.aprobado_por,
                },
            )
            fecha += timedelta(days=1)
    except Exception as e:
        logger.warning('Error marcando VAC en roster desde solicitud #%s: %s',
                       solicitud.pk, e)


# ── Solicitudes de Permiso ─────────────────────────────────────────────────────

@receiver(post_save, sender='vacaciones.SolicitudPermiso')
def badge_solicitud_permiso(sender, instance, **kwargs):
    """Invalida badge al crear/modificar una solicitud de permiso."""
    _invalidar_badge_superusers()
    # Bajadas → crear Roster automáticamente al aprobar
    _crear_roster_desde_bajada(instance)


def _crear_roster_desde_bajada(solicitud):
    """
    Si la solicitud es de tipo bajada (DL / DLA) y está APROBADA,
    crea entradas de Roster para cada día del rango fecha_inicio → fecha_fin.

    Códigos de roster:
      TipoPermiso.codigo = 'bajada-dl'  → Roster.codigo = 'DL'
      TipoPermiso.codigo = 'bajada-dla' → Roster.codigo = 'DLA'

    Solo actúa si mod_roster=True en ConfiguracionSistema.
    """
    if solicitud.estado != 'APROBADA':
        return

    codigo_permiso = solicitud.tipo.codigo if solicitud.tipo else ''
    if codigo_permiso not in ('bajada-dl', 'bajada-dla'):
        return

    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.get()
        if not config.mod_roster:
            return  # Módulo roster desactivado — no crear entradas
    except Exception:
        return

    from personal.models import Roster
    from datetime import timedelta

    codigo_roster = 'DL' if codigo_permiso == 'bajada-dl' else 'DLA'
    personal = solicitud.personal
    aprobado_por = solicitud.aprobado_por
    fecha = solicitud.fecha_inicio
    creados = 0
    actualizados = 0

    while fecha <= solicitud.fecha_fin:
        roster, created = Roster.objects.update_or_create(
            personal=personal,
            fecha=fecha,
            defaults={
                'codigo':       codigo_roster,
                'estado':       'aprobado',
                'fuente':       f'SolicitudPermiso #{solicitud.pk} — {solicitud.tipo.nombre}',
                'observaciones': solicitud.motivo[:200] if solicitud.motivo else '',
                'aprobado_por': aprobado_por,
            },
        )
        if created:
            creados += 1
        else:
            actualizados += 1
        fecha += timedelta(days=1)

    logger.info(
        'Roster auto-creado desde bajada: personal=%s, tipo=%s, fechas=%s→%s, '
        'creados=%d, actualizados=%d',
        personal.apellidos_nombres,
        codigo_roster,
        solicitud.fecha_inicio,
        solicitud.fecha_fin,
        creados,
        actualizados,
    )
