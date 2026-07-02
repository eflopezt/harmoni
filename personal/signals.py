"""
Signals para el modulo personal.

Responsabilidades:
  1. Auditoria de cambios en Roster
  2. Auto-crear UserProfile al crear User
  3. Invalidar cache de badge cuando cambia el estado de items pendientes
  4. Automatizacion de cese: constancia PDF, notificacion RRHH, email empleado
  5. Notificacion de alta / reingreso a RRHH
"""
import logging
from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Roster, RosterAudit

logger = logging.getLogger(__name__)


# -- 1. Auditoria de Roster ------------------------------------------------

@receiver(pre_save, sender=Roster)
def audit_roster_changes(sender, instance, **kwargs):
    """Registra cambios en el roster antes de guardar."""
    if instance.pk:
        try:
            old_instance = Roster.objects.get(pk=instance.pk)
            for campo in ['codigo', 'observaciones']:
                valor_anterior = str(getattr(old_instance, campo))
                valor_nuevo = str(getattr(instance, campo))
                if valor_anterior != valor_nuevo:
                    RosterAudit.objects.create(
                        personal=instance.personal,
                        fecha=instance.fecha,
                        campo_modificado=campo,
                        valor_anterior=valor_anterior,
                        valor_nuevo=valor_nuevo,
                        usuario=None,
                    )
        except Roster.DoesNotExist:
            pass


# -- 2. Auto-crear UserProfile al crear User --------------------------------

@receiver(post_save, sender=User)
def crear_userprofile_automatico(sender, instance, created, **kwargs):
    """
    Crea UserProfile automaticamente cuando se crea un nuevo User.
    Evita DoesNotExist en runtime para usuarios sin perfil.
    """
    if created:
        try:
            from .user_models import UserProfile
            UserProfile.objects.get_or_create(user=instance)
        except Exception:
            pass


# -- 3. Invalidar badge cuando cambia estado de aprobaciones ---------------

@receiver(post_save, sender=Roster)
def invalidar_badge_roster(sender, instance, **kwargs):
    """Invalida el badge de pendientes al aprobar/rechazar un Roster."""
    _invalidar_badge_superusers()


def _invalidar_badge_superusers():
    """Utility: borra el cache del badge de todos los superusers activos."""
    try:
        from django.core.cache import cache
        pks = User.objects.filter(
            is_superuser=True, is_active=True
        ).values_list('pk', flat=True)
        cache.delete_many([f'harmoni_badge_{pk}_v3' for pk in pks])
    except Exception:
        pass


# -- 4 & 5. Automatizacion de cambios de estado en Personal ----------------

@receiver(pre_save, sender='personal.Personal')
def _capturar_estado_anterior(sender, instance, **kwargs):
    """Guarda el estado anterior y condicion antes de persistir para detectar cambios."""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._estado_anterior = old.estado
            instance._condicion_anterior = old.condicion
        except sender.DoesNotExist:
            instance._estado_anterior = None
            instance._condicion_anterior = None
    else:
        instance._estado_anterior = None
        instance._condicion_anterior = None


@receiver(post_save, sender='personal.Personal')
def _on_personal_post_save(sender, instance, created, **kwargs):
    """Dispatcher principal para cambios de estado y condicion de Personal."""
    if created:
        _handle_nueva_alta(instance)
        return

    # Cambio de condicion → reprocesar asistencia
    condicion_anterior = getattr(instance, '_condicion_anterior', None)
    if condicion_anterior and condicion_anterior != instance.condicion:
        _handle_cambio_condicion(instance, condicion_anterior)

    # Cambio de estado
    estado_anterior = getattr(instance, '_estado_anterior', None)
    estado_actual = instance.estado
    if estado_anterior == estado_actual:
        return
    if estado_actual == 'Cesado' and estado_anterior != 'Cesado':
        _handle_cese(instance)
    elif estado_actual == 'Activo' and estado_anterior not in ('Activo', None):
        _handle_reingreso(instance, estado_anterior)


# -- Handler de cambio de condicion ----------------------------------------

def _handle_cambio_condicion(personal, condicion_anterior):
    """
    Reprocesa TODOS los registros de asistencia cuando cambia la condicion
    (LOCAL ↔ FORÁNEO ↔ LIMA). La condicion afecta la jornada diaria y
    el calculo de horas extra.

    Jornadas (Consorcio SRT):
      LOCAL:   L-V 8.5h, Sab 5.5h, Dom todo al 100%
      FORÁNEO: L-S 10h (efectiva), Dom 4h jornada
      LIMA:    auto-presente L-S sin biometrico
    """
    from asistencia.models import RegistroTareo
    from datetime import date
    from decimal import Decimal, ROUND_FLOOR

    condicion_nueva = (personal.condicion or '').upper().replace('Á', 'A')
    logger.info(
        '[Signal Condicion] %s (%s): %s → %s — reprocesando asistencia',
        personal.apellidos_nombres, personal.nro_doc,
        condicion_anterior, personal.condicion
    )

    CERO = Decimal('0')
    GRACIA = Decimal('7') / 60

    def round_half(h):
        return ((h + GRACIA) * 2).to_integral_value(rounding=ROUND_FLOOR) / 2

    # Jornadas por condicion
    if condicion_nueva == 'FORANEO':
        jornada_lv = Decimal('10')
        jornada_sab = Decimal('10')
        dom_todo_100 = False
        jornada_dom = Decimal('4')
    elif condicion_nueva == 'LIMA':
        jornada_lv = Decimal('8')
        jornada_sab = Decimal('5.5')
        dom_todo_100 = True
        jornada_dom = CERO
    else:  # LOCAL
        jornada_lv = Decimal('8.5')
        jornada_sab = Decimal('5.5')
        dom_todo_100 = True
        jornada_dom = CERO

    # Reprocesar todos los registros con horas (no tocar feriados ni ausencias)
    regs = RegistroTareo.objects.filter(
        personal=personal,
        fecha__gte=date(2026, 1, 1),  # desde inicio de año
    ).exclude(
        codigo_dia__in=['VAC', 'DL', 'LCG', 'LSG', 'FER', 'FA', 'NA', 'DM', 'LPT', 'LFA']
    )

    fixed = 0
    # Perf audit fix: antes hacia r.save() en loop (N saves sincronos).
    # Ahora junto las modificaciones y hago bulk_update al final (1 query).
    para_update = []
    for r in regs:
        total_h = r.horas_normales + r.he_25 + r.he_35 + r.he_100
        if total_h == CERO:
            continue

        dow = r.fecha.weekday()  # 0=Lu, 5=Sa, 6=Do

        if dow == 6:  # DOMINGO
            if dom_todo_100:
                # LOCAL/LIMA: todo al 100%
                r.horas_normales = CERO
                r.he_25 = CERO
                r.he_35 = CERO
                r.he_100 = total_h
                if r.codigo_dia not in ('DS', 'DSE'):
                    r.codigo_dia = 'DS'
            else:
                # FORÁNEO: normal hasta jornada_dom, exceso 100%
                r.horas_normales = min(total_h, jornada_dom)
                r.he_25 = CERO
                r.he_35 = CERO
                r.he_100 = max(CERO, total_h - jornada_dom)
        elif dow == 5:  # SÁBADO
            jornada = jornada_sab
            exceso = round_half(max(CERO, total_h - jornada))
            r.horas_normales = jornada
            r.he_25 = min(exceso, Decimal('2'))
            r.he_35 = max(CERO, exceso - Decimal('2'))
            r.he_100 = CERO
        else:  # L-V
            jornada = jornada_lv
            exceso = round_half(max(CERO, total_h - jornada))
            r.horas_normales = jornada
            r.he_25 = min(exceso, Decimal('2'))
            r.he_35 = max(CERO, exceso - Decimal('2'))
            r.he_100 = CERO

        para_update.append(r)
        fixed += 1

    if para_update:
        from asistencia.models import RegistroTareo as _RT
        _RT.objects.bulk_update(
            para_update,
            ['horas_normales', 'he_25', 'he_35', 'he_100', 'codigo_dia'],
            batch_size=500,
        )

    logger.info(
        '[Signal Condicion] %s: %d registros reprocesados (%s → %s)',
        personal.nro_doc, fixed, condicion_anterior, personal.condicion
    )

    # Notificar al admin
    try:
        from comunicaciones.services import NotificacionService
        from django.contrib.auth.models import User
        for admin in User.objects.filter(is_superuser=True, is_active=True):
            personal_admin = getattr(admin, 'personal_data', None)
            NotificacionService.enviar(
                destinatario=personal_admin,
                asunto=f'Condición cambiada: {personal.apellidos_nombres}',
                cuerpo=(
                    f'{personal.apellidos_nombres} ({personal.nro_doc}) cambió de '
                    f'{condicion_anterior} a {personal.condicion}. '
                    f'{fixed} registros de asistencia reprocesados automáticamente.'
                ),
                tipo='IN_APP',
            )
    except Exception as e:
        logger.warning('[Signal Condicion] Error notificando: %s', e)


# -- Handlers de cese ------------------------------------------------------

def _handle_cese(personal):
    """Ejecuta las acciones automaticas al cesar a un empleado."""
    logger.info('[Signal Cese] Procesando cese de %s (%s)', personal.apellidos_nombres, personal.nro_doc)
    _notificar_admins_cese(personal)
    _generar_constancia_cese(personal)
    _email_cese_empleado(personal)
    _cancelar_onboarding_en_curso(personal)
    _crear_proceso_offboarding(personal)


def _crear_proceso_offboarding(personal):
    """Crea el ProcesoOffboarding con los pasos de la plantilla activa.

    Vive en el signal para que TODO camino de cese (wizard, dar-baja
    programático, admin) lo genere. Idempotente: no duplica si ya hay un
    proceso EN_CURSO para el trabajador.
    """
    try:
        from onboarding.models import (
            PasoOffboarding, PasoPlantillaOff,
            PlantillaOffboarding, ProcesoOffboarding,
        )
        from personal.motivos_cese import PERSONAL_A_OFFBOARDING

        if ProcesoOffboarding.objects.filter(
                personal=personal, estado='EN_CURSO').exists():
            return

        plantilla = PlantillaOffboarding.objects.filter(activa=True).first()
        if not plantilla:
            return

        from datetime import date as _date, timedelta as _td
        fecha_cese = personal.fecha_cese or _date.today()
        proceso = ProcesoOffboarding.objects.create(
            personal=personal,
            plantilla=plantilla,
            motivo_cese=PERSONAL_A_OFFBOARDING.get(
                personal.motivo_cese, 'FIN_CONTRATO'),
            fecha_cese=fecha_cese,
        )
        for paso_tmpl in PasoPlantillaOff.objects.filter(
                plantilla=plantilla).order_by('orden'):
            PasoOffboarding.objects.create(
                proceso=proceso,
                paso_plantilla=paso_tmpl,
                orden=paso_tmpl.orden,
                titulo=paso_tmpl.titulo,
                estado='PENDIENTE',
                fecha_limite=fecha_cese + _td(days=paso_tmpl.dias_plazo),
            )
        logger.info('[Signal Cese] ProcesoOffboarding #%s creado para %s',
                    proceso.pk, personal.nro_doc)
    except Exception as e:
        logger.warning('[Signal Cese] Error creando offboarding: %s', e)


def _cancelar_onboarding_en_curso(personal):
    """Un cesado no debe seguir con onboarding activo (ej. cese en período
    de prueba): se cancela el proceso, no se borra el avance."""
    try:
        from onboarding.models import ProcesoOnboarding
        n = ProcesoOnboarding.objects.filter(
            personal=personal, estado='EN_CURSO',
        ).update(estado='CANCELADO')
        if n:
            logger.info('[Signal Cese] %s proceso(s) de onboarding cancelado(s) para %s',
                        n, personal.nro_doc)
    except Exception as e:
        logger.warning('[Signal Cese] Error cancelando onboarding: %s', e)


def _notificar_admins_cese(personal):
    """
    Envia notificacion in-app a todos los superusers sobre el cese.
    Usa NotificacionService con destinatario=Personal o None si no tiene registro.
    """
    try:
        from comunicaciones.services import NotificacionService
        admins = User.objects.filter(is_superuser=True, is_active=True).select_related('personal_data')
        fecha_cese_str = personal.fecha_cese.strftime('%d/%m/%Y') if personal.fecha_cese else 'no registrada'
        motivo_str = personal.get_motivo_cese_display() if personal.motivo_cese else 'no registrado'
        for admin in admins:
            personal_admin = getattr(admin, 'personal_data', None)
            NotificacionService.enviar(
                destinatario=personal_admin,
                asunto=f'Cese registrado: {personal.apellidos_nombres}',
                cuerpo=(
                    f'<p>Se registro el cese de <strong>{personal.apellidos_nombres}</strong> (DNI: {personal.nro_doc}).</p>'
                    f'<p>Fecha: <strong>{fecha_cese_str}</strong>. Motivo: {motivo_str}.</p>'
                    f'<p>Verifica la documentacion de cese correspondiente.</p>'
                    f'<p><a href="/personal/{personal.pk}/">Ver ficha del empleado</a></p>'
                ),
                tipo='IN_APP',
                destinatario_email=admin.email or '',
            )
        logger.info('[Signal Cese] Notificaciones enviadas a %d admins', admins.count())
    except Exception as exc:
        logger.warning('[Signal Cese] Error notificando admins: %s', exc)


def _generar_constancia_cese(personal):
    """
    Busca una PlantillaConstancia activa, genera el PDF usando el servicio
    oficial de documentos y crea un DocumentoFirmaDigital para firma electronica.
    Registra en ConstanciaGenerada para auditoria (sin archivo adjunto).
    No lanza excepciones: el cese no debe romperse por un error de PDF.
    """
    try:
        from documentos.models import PlantillaConstancia, ConstanciaGenerada
        plantilla = (
            PlantillaConstancia.objects.filter(activa=True, codigo__icontains='cese').first()
            or PlantillaConstancia.objects.filter(activa=True, categoria='CARTA').first()
            or PlantillaConstancia.objects.filter(activa=True, categoria='CONSTANCIA').first()
        )
        if not plantilla:
            logger.info('[Signal Cese] Sin plantilla -- omitiendo PDF para %s', personal)
            return
        from documentos.services import generar_constancia_pdf
        extra_ctx = {
            'fecha_cese_texto': _fecha_texto(personal.fecha_cese) if personal.fecha_cese else None,
            'motivo_cese': personal.get_motivo_cese_display() if personal.motivo_cese else '',
        }
        pdf_bytes = generar_constancia_pdf(plantilla, personal, extra_context=extra_ctx)
        ConstanciaGenerada.objects.create(plantilla=plantilla, personal=personal, generado_por=None, origen='ADMIN')
        logger.info('[Signal Cese] ConstanciaGenerada registrada para %s', personal)
        _crear_firma_digital_cese(personal, pdf_bytes, plantilla)
    except Exception as exc:
        logger.warning('[Signal Cese] Error generando constancia: %s', exc, exc_info=True)


def _crear_firma_digital_cese(personal, pdf_bytes, plantilla):
    """
    Crea un DocumentoFirmaDigital (estado PENDIENTE) con el PDF de cese.
    El documento queda en estado PENDIENTE. El envio a ZapSign es un paso
    posterior (manual o tarea). Vence a los 15 dias para presionar la firma.
    """
    try:
        from documentos.models import DocumentoFirmaDigital
        from django.core.files.base import ContentFile
        from django.utils import timezone
        from datetime import timedelta
        hoy = timezone.localdate()
        nombre_archivo = f'Carta_Cese_{personal.nro_doc}_{hoy.strftime("%Y%m%d")}.pdf'
        doc = DocumentoFirmaDigital(
            personal=personal,
            nombre=f'Carta de Cese -- {personal.apellidos_nombres}',
            tipo='FINIQUITO',
            descripcion=f'Cese generado el {hoy.strftime("%d/%m/%Y")}. Plantilla: {plantilla.nombre}.',
            vence_en=hoy + timedelta(days=15),
        )
        doc.archivo_pdf.save(nombre_archivo, ContentFile(pdf_bytes), save=False)
        doc.save()
        logger.info('[Signal Cese] DocumentoFirmaDigital pk=%d creado para %s', doc.pk, personal)
    except Exception as exc:
        logger.warning('[Signal Cese] Error creando DocumentoFirmaDigital: %s', exc)


def _email_cese_empleado(personal):
    """
    Envia notificacion AMBOS (in-app + email) al empleado cesado si tiene correo.
    Usa NotificacionService para consistencia con el resto del sistema.
    """
    try:
        email = personal.correo_personal or personal.correo_corporativo or ''
        if not email:
            logger.info('[Signal Cese] %s sin correo -- omitiendo notificacion', personal)
            return
        empresa_nombre = _get_empresa_nombre()
        from comunicaciones.services import NotificacionService
        fecha_cese_str = personal.fecha_cese.strftime('%d/%m/%Y') if personal.fecha_cese else 'segun registro'
        NotificacionService.enviar(
            destinatario=personal,
            asunto=f'Notificacion de cese laboral -- {empresa_nombre}',
            cuerpo=(
                f'<p>Estimado(a) <strong>{personal.apellidos_nombres}</strong>,</p>'
                f'<p>Le comunicamos que su relacion laboral con <strong>{empresa_nombre}</strong> ha concluido con fecha <strong>{fecha_cese_str}</strong>.</p>'
                f'<p>Para consultas comuniquese con el area de Recursos Humanos.</p>'
                f'<p>Atentamente,<br><strong>{empresa_nombre}</strong><br>Area de RRHH</p>'
            ),
            tipo='AMBOS',
            destinatario_email=email,
        )
        logger.info('[Signal Cese] Notificacion enviada a %s', email)
    except Exception as exc:
        logger.warning('[Signal Cese] Error enviando notificacion al empleado: %s', exc)


# -- Handlers de alta / reingreso ------------------------------------------

def _handle_nueva_alta(personal):
    """Notifica a superusers sobre una nueva incorporacion."""
    try:
        from comunicaciones.services import NotificacionService
        fecha_alta_str = personal.fecha_alta.strftime('%d/%m/%Y') if personal.fecha_alta else 'no registrada'
        admins = User.objects.filter(is_superuser=True, is_active=True).select_related('personal_data')
        for admin in admins:
            personal_admin = getattr(admin, 'personal_data', None)
            NotificacionService.enviar(
                destinatario=personal_admin,
                asunto=f'Nueva incorporacion: {personal.apellidos_nombres}',
                cuerpo=(
                    f'<p>Se registro: <strong>{personal.apellidos_nombres}</strong> (DNI: {personal.nro_doc}).</p>'
                    f'<p>Cargo: {personal.cargo or "sin cargo"}. Alta: {fecha_alta_str}.</p>'
                    f'<p>Recuerda iniciar el proceso de onboarding.</p>'
                    f'<p><a href="/personal/{personal.pk}/">Ver ficha del empleado</a></p>'
                ),
                tipo='IN_APP',
                destinatario_email=admin.email or '',
            )
        logger.info('[Signal Alta] Notificaciones enviadas para %s', personal)
    except Exception as exc:
        logger.warning('[Signal Alta] Error notificando admins: %s', exc)


def _handle_reingreso(personal, estado_anterior):
    """Notifica a superusers cuando un empleado regresa al estado Activo."""
    try:
        from comunicaciones.services import NotificacionService
        admins = User.objects.filter(is_superuser=True, is_active=True).select_related('personal_data')
        for admin in admins:
            personal_admin = getattr(admin, 'personal_data', None)
            NotificacionService.enviar(
                destinatario=personal_admin,
                asunto=f'Reingreso: {personal.apellidos_nombres}',
                cuerpo=(
                    f'<p><strong>{personal.apellidos_nombres}</strong> (DNI: {personal.nro_doc}) cambio de estado <em>{estado_anterior}</em> a <strong>Activo</strong>.</p>'
                    f'<p>Verifica la documentacion de reingreso.</p>'
                    f'<p><a href="/personal/{personal.pk}/">Ver ficha del empleado</a></p>'
                ),
                tipo='IN_APP',
                destinatario_email=admin.email or '',
            )
        logger.info('[Signal Reingreso] Notificaciones enviadas para %s', personal)
    except Exception as exc:
        logger.warning('[Signal Reingreso] Error: %s', exc)


# -- M2. Sincronizar Contrato VIGENTE → campos de Personal -----------------

@receiver(post_save, sender='personal.Contrato')
def sincronizar_contrato_con_personal(sender, instance, **kwargs):
    """
    Cuando se guarda un Contrato VIGENTE, sincroniza automáticamente los campos
    de contrato en la ficha Personal (tipo_contrato, fecha_inicio/fin, renovacion).
    Evita que ambos registros diverjan silenciosamente.
    """
    if instance.estado == 'VIGENTE':
        try:
            instance.sincronizar_con_personal()
        except Exception as exc:
            logger.warning('[Signal Contrato] Error sincronizando con Personal pk=%s: %s',
                           instance.personal_id, exc)


# -- Funcion utilitaria: alertar contratos por vencer ----------------------

def alertar_contratos_por_vencer():
    """
    Genera alertas in-app para contratos que vencen en los proximos 30 dias.

    Llamar desde una tarea periodica o management command:
        from personal.signals import alertar_contratos_por_vencer
        alertar_contratos_por_vencer()

    Returns:
        int -- numero de contratos proximos a vencer encontrados.
    """
    try:
        from datetime import date, timedelta
        from comunicaciones.services import NotificacionService
        from personal.models import Personal
        hoy = date.today()
        en_30_dias = hoy + timedelta(days=30)
        proximos = Personal.objects.filter(
            estado='Activo',
            fecha_fin_contrato__isnull=False,
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=en_30_dias,
        ).order_by('fecha_fin_contrato')
        if not proximos.exists():
            return 0
        total = proximos.count()
        nombres = ', '.join(
            f'{p.apellidos_nombres} ({p.fecha_fin_contrato.strftime("%d/%m")})'
            for p in proximos[:5]
        )
        extra = f' y {total - 5} mas' if total > 5 else ''
        plural = 's' if total != 1 else ''
        admins = User.objects.filter(is_superuser=True, is_active=True).select_related('personal_data')
        for admin in admins:
            personal_admin = getattr(admin, 'personal_data', None)
            NotificacionService.enviar(
                destinatario=personal_admin,
                asunto=f'{total} contrato{plural} por vencer en 30 dias',
                cuerpo=(
                    f'<p>Contratos proximos a vencer (30 dias):</p>'
                    f'<p><strong>{nombres}{extra}</strong></p>'
                    f'<p>Gestiona la renovacion o el proceso de cese segun corresponda.</p>'
                    f'<p><a href="/personal/?filtro=contratos_por_vencer">Ver listado completo</a></p>'
                ),
                tipo='IN_APP',
                destinatario_email=admin.email or '',
            )
        logger.info('[Contratos] Alerta enviada: %d contratos por vencer', total)
        return total
    except Exception as exc:
        logger.warning('[Contratos] Error generando alertas: %s', exc)
        return 0


# -- Helpers privados ------------------------------------------------------

def _fecha_texto(fecha):
    """Convierte date a texto: 01 de marzo de 2026."""
    MESES = ['', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
    return f'{fecha.day:02d} de {MESES[fecha.month]} de {fecha.year}'


def _get_empresa_nombre():
    """Obtiene el nombre de empresa desde ConfiguracionSistema (asistencia.models)."""
    try:
        from asistencia.models import ConfiguracionSistema
        config = ConfiguracionSistema.objects.first()
        if config:
            return config.empresa_nombre or 'La empresa'
    except Exception:
        pass
    return 'La empresa'
