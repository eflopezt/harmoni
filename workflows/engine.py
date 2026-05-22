"""Workflow Engine - API publica reutilizable para el motor de aprobaciones.

Este modulo es una capa adaptadora sobre `workflows.services` y los modelos
existentes (`FlujoTrabajo`, `EtapaFlujo`, `InstanciaFlujo`, `PasoFlujo`). Provee
una interfaz limpia y estable que otros modulos del ERP pueden invocar para:

  - Crear instancias de workflow desde cualquier objeto del dominio.
  - Avanzar (aprobar / rechazar / comentar) una instancia.
  - Consultar quien puede aprobar el paso actual.
  - Notificar al objeto vinculado cuando el flujo termina.

Diseñado para que vacaciones, prestamos, reembolsos, disciplinaria, etc. puedan
delegar la logica de aprobaciones a un motor unico sin duplicarla.

Ejemplo de uso desde otro modulo:

    from workflows.engine import crear_instancia, avanzar_instancia

    # 1) Al crear una SolicitudVacacion con estado PENDIENTE:
    crear_instancia(
        flujo_codigo='Aprobacion de Vacaciones',
        solicitante=request.user,
        objeto=solicitud,
        titulo=f'Vacaciones {solicitud.fecha_inicio} - {solicitud.fecha_fin}',
    )

    # 2) Cuando un aprobador decide:
    avanzar_instancia(instancia, request.user, 'APROBAR', comentario='OK')
"""
import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone

from . import services
from .models import (
    EtapaFlujo,
    FlujoTrabajo,
    InstanciaFlujo,
    PasoFlujo,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Mapeo de acciones publicas -> decisiones internas
# ---------------------------------------------------------------------------

ACCION_A_DECISION = {
    'APROBAR':  'APROBADO',
    'RECHAZAR': 'RECHAZADO',
    'COMENTAR': None,    # No avanza, solo registra
    'REASIGNAR': 'DELEGADO',
}


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------

@transaction.atomic
def crear_instancia(flujo_codigo, solicitante, objeto=None,
                    titulo='', descripcion='', metadata=None):
    """Crea una `InstanciaFlujo` y notifica al primer aprobador.

    Args:
        flujo_codigo: Nombre del `FlujoTrabajo` (o pk numerico).
        solicitante: `User` que solicita la aprobacion.
        objeto: Instancia de modelo Django vinculada (Vacacion, Prestamo, etc.).
        titulo: Texto descriptivo (se guarda en metadata).
        descripcion: Detalle adicional (se guarda en metadata).
        metadata: Dict adicional para guardar en `InstanciaFlujo.metadata`.

    Returns:
        `InstanciaFlujo` creada, o None si el flujo no existe / no esta activo.

    Raises:
        ValueError: Si el flujo no tiene etapas configuradas.
    """
    flujo = _resolver_flujo(flujo_codigo)
    if flujo is None:
        logger.warning(f'[Engine] Flujo no encontrado: {flujo_codigo!r}')
        return None

    if not flujo.activo:
        logger.warning(f'[Engine] Flujo inactivo: {flujo.nombre}')
        return None

    primera_etapa = flujo.etapas.order_by('orden').first()
    if not primera_etapa:
        raise ValueError(
            f'El flujo "{flujo.nombre}" no tiene etapas configuradas.'
        )

    # ContentType opcional (None si no hay objeto vinculado)
    if objeto is not None:
        ct = ContentType.objects.get_for_model(objeto.__class__)
        object_id = objeto.pk
    else:
        # GenericFK no acepta NULL en este modelo; usamos un sentinel
        # razonable (ContentType del propio FlujoTrabajo) y object_id=flujo.pk.
        ct = ContentType.objects.get_for_model(FlujoTrabajo)
        object_id = flujo.pk

    meta = dict(metadata or {})
    if titulo:
        meta['titulo'] = titulo
    if descripcion:
        meta['descripcion'] = descripcion

    vence_en = None
    if primera_etapa.tiempo_limite_horas:
        vence_en = timezone.now() + timedelta(hours=primera_etapa.tiempo_limite_horas)

    instancia = InstanciaFlujo.objects.create(
        flujo=flujo,
        content_type=ct,
        object_id=object_id,
        etapa_actual=primera_etapa,
        estado='EN_PROCESO',
        solicitante=solicitante,
        etapa_vence_en=vence_en,
        metadata=meta,
    )

    # Notificar al primer aprobador (best-effort, no falla si comunicaciones no esta)
    try:
        services._notificar_aprobadores(instancia, primera_etapa, objeto)
    except Exception as exc:
        logger.warning(f'[Engine] No se pudo notificar aprobadores: {exc}')

    logger.info(f'[Engine] Instancia creada #{instancia.pk} (flujo={flujo.nombre})')
    return instancia


@transaction.atomic
def avanzar_instancia(instancia, usuario, accion, comentario=''):
    """Procesa una accion sobre una instancia de flujo.

    Acciones soportadas:
      - APROBAR:    avanza al siguiente paso o cierra como APROBADO si era el ultimo.
      - RECHAZAR:   cierra inmediatamente como RECHAZADO.
      - COMENTAR:   registra un comentario sin avanzar (PasoFlujo informativo).
      - REASIGNAR:  delega la decision (registra como DELEGADO).

    Args:
        instancia: `InstanciaFlujo`.
        usuario: `User` que ejecuta la accion.
        accion: 'APROBAR' | 'RECHAZAR' | 'COMENTAR' | 'REASIGNAR'.
        comentario: Texto opcional.

    Returns:
        True si la accion se proceso, False si el usuario no tiene permiso o la
        instancia ya no esta en proceso.

    Raises:
        ValueError: Si la accion es invalida, o si la etapa exige comentario y
            no se proporciono.
    """
    if accion not in ACCION_A_DECISION:
        raise ValueError(
            f'Accion invalida: {accion!r}. Permitidas: {list(ACCION_A_DECISION)}'
        )

    if instancia.estado != 'EN_PROCESO':
        logger.warning(
            f'[Engine] Instancia #{instancia.pk} no esta EN_PROCESO ({instancia.estado})'
        )
        return False

    # COMENTAR: registra sin avanzar, sin requerir ser aprobador formal
    if accion == 'COMENTAR':
        if not comentario.strip():
            raise ValueError('El comentario no puede estar vacio.')
        PasoFlujo.objects.create(
            instancia=instancia,
            etapa=instancia.etapa_actual,
            aprobador=usuario,
            decision='APROBADO',   # placeholder: el modelo no tiene COMENTARIO
            comentario=f'[Comentario] {comentario}',
        )
        return True

    if accion == 'REASIGNAR':
        if not usuario.is_superuser and not usuario.is_staff:
            logger.warning(
                f'[Engine] Solo admin puede REASIGNAR (intento: {usuario})'
            )
            return False
        PasoFlujo.objects.create(
            instancia=instancia,
            etapa=instancia.etapa_actual,
            aprobador=usuario,
            decision='DELEGADO',
            comentario=comentario or 'Reasignado por administrador',
        )
        return True

    # APROBAR / RECHAZAR -> delega en services.decidir
    decision = ACCION_A_DECISION[accion]
    ok = services.decidir(instancia, usuario, decision, comentario)
    if ok:
        instancia.refresh_from_db()
        # Si el flujo termino (APROBADO o RECHAZADO), notificar al objeto vinculado
        if instancia.estado in ('APROBADO', 'RECHAZADO'):
            signal_objeto_completado(instancia)
    return ok


def aprobadores_actuales(instancia):
    """Devuelve la lista de Users que pueden aprobar el paso actual.

    Si la instancia fue escalada (metadata['escalado_a_user_id']), incluye al
    usuario escalado.
    """
    from django.contrib.auth.models import User

    if not instancia.etapa_actual or instancia.estado != 'EN_PROCESO':
        return []

    aprobadores = list(instancia.etapa_actual.get_aprobadores(instancia.objeto))

    meta = instancia.metadata or {}
    user_id_escalado = meta.get('escalado_a_user_id')
    if user_id_escalado:
        try:
            user_esc = User.objects.get(pk=user_id_escalado, is_active=True)
            if user_esc not in aprobadores:
                aprobadores.append(user_esc)
        except User.DoesNotExist:
            pass

    return aprobadores


def signal_objeto_completado(instancia):
    """Notifica al objeto vinculado que el workflow termino.

    Si el objeto define un metodo `on_workflow_completado(instancia)` lo invoca.
    Como fallback, intenta los metodos estandar:
      - `aprobar()` / `rechazar()` si el objeto tiene esos metodos.
      - Caso contrario, setattr del campo configurado en el flujo
        (manejado por services._finalizar_flujo).

    Es seguro llamar esto multiples veces — el flujo solo se cierra una vez.
    """
    objeto = instancia.objeto
    if objeto is None:
        return False

    aprobado = (instancia.estado == 'APROBADO')

    # Hook personalizado: si el objeto define on_workflow_completado, prevalece
    hook = getattr(objeto, 'on_workflow_completado', None)
    if callable(hook):
        try:
            hook(instancia)
            logger.info(
                f'[Engine] Hook on_workflow_completado ejecutado en {objeto}'
            )
            return True
        except Exception as exc:
            logger.error(
                f'[Engine] Error en hook on_workflow_completado: {exc}'
            )

    # Metodos estandar aprobar() / rechazar()
    metodo_nombre = 'aprobar' if aprobado else 'rechazar'
    metodo = getattr(objeto, metodo_nombre, None)
    if callable(metodo):
        try:
            metodo()
            logger.info(f'[Engine] {metodo_nombre}() invocado en {objeto}')
            return True
        except Exception as exc:
            logger.error(f'[Engine] Error invocando {metodo_nombre}(): {exc}')

    return False


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _resolver_flujo(flujo_codigo):
    """Resuelve un FlujoTrabajo por pk numerico o por nombre (case-insensitive).

    Esto da flexibilidad a los modulos consumidores: pueden referenciar el flujo
    por nombre estable ("Aprobacion de Vacaciones") sin acoplarse al pk.
    """
    if isinstance(flujo_codigo, FlujoTrabajo):
        return flujo_codigo
    if isinstance(flujo_codigo, int) or (
        isinstance(flujo_codigo, str) and flujo_codigo.isdigit()
    ):
        return FlujoTrabajo.objects.filter(pk=int(flujo_codigo)).first()
    return FlujoTrabajo.objects.filter(nombre__iexact=str(flujo_codigo)).first()
