"""
Tareas Celery del módulo Tareo.

Tareas disponibles:
  - enviar_resumen_semanal_asistencia  → email individual cada trabajador
  - enviar_reporte_mensual_gerencia    → resumen ejecutivo a gerencia
  - procesar_importacion_synkro        → importación Synkro en background
  - procesar_importacion_sunat         → importación SUNAT TR5 en background
  - procesar_importacion_s10           → importación S10 en background
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger('personal.business')


# ──────────────────────────────────────────────────────────────
# EMAILS
# ──────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=60)
def enviar_resumen_semanal_asistencia(self):
    """
    Envía a cada trabajador un resumen de su asistencia de la semana anterior.

    Se programa para ejecutarse el día configurado en ConfiguracionSistema.email_dia_envio.
    Solo se ejecuta si email_habilitado=True.
    """
    from tareo.models import ConfiguracionSistema, RegistroTareo
    from personal.models import Personal

    config = ConfiguracionSistema.get()
    if not config.email_habilitado:
        logger.info('Emails tareo deshabilitados. Tarea omitida.')
        return {'omitido': True, 'razon': 'email_habilitado=False'}

    hoy = date.today()
    # Semana anterior: lunes → domingo
    lunes = hoy - timedelta(days=hoy.weekday() + 7)
    domingo = lunes + timedelta(days=6)

    empresa = config.empresa_nombre or settings.SITE_NAME if hasattr(settings, 'SITE_NAME') else 'Sistema'
    asunto_tpl = config.email_asunto_semanal
    enviados = 0
    errores = []

    personal_con_email = Personal.objects.filter(
        correo_corporativo__isnull=False
    ).exclude(correo_corporativo='').select_related()

    for persona in personal_con_email:
        try:
            registros = list(
                RegistroTareo.objects.filter(
                    personal=persona,
                    fecha__gte=lunes,
                    fecha__lte=domingo,
                ).order_by('fecha')
            )

            if not registros:
                continue

            # Calcular resumen
            dias_trabajados = sum(1 for r in registros if r.codigo_dia in ('T', 'NOR', 'TR'))
            faltas = sum(1 for r in registros if r.codigo_dia == 'FA')
            he_total = sum((r.he_25 or Decimal('0')) + (r.he_35 or Decimal('0')) +
                           (r.he_100 or Decimal('0')) for r in registros)

            asunto = (
                asunto_tpl
                .replace('{empresa}', empresa)
                .replace('{semana}', f'{lunes.strftime("%d/%m")} – {domingo.strftime("%d/%m/%Y")}')
                .replace('{empleado}', persona.apellidos_nombres or persona.nro_doc)
            )

            ctx = {
                'persona': persona,
                'empresa': empresa,
                'semana_inicio': lunes,
                'semana_fin': domingo,
                'registros': registros,
                'dias_trabajados': dias_trabajados,
                'faltas': faltas,
                'he_total': he_total,
                'grupo': persona.grupo_tareo,
            }

            html_body = render_to_string('tareo/emails/resumen_semanal.html', ctx)
            text_body = strip_tags(html_body)

            msg = EmailMultiAlternatives(
                subject=asunto,
                body=text_body,
                from_email=config.email_desde or settings.DEFAULT_FROM_EMAIL,
                to=[persona.correo_corporativo],
            )
            msg.attach_alternative(html_body, 'text/html')
            msg.send(fail_silently=False)
            enviados += 1

        except Exception as exc:
            logger.warning(f'Email fallido para {persona.nro_doc}: {exc}')
            errores.append({'dni': persona.nro_doc, 'error': str(exc)})

    logger.info(f'Emails semanales enviados: {enviados}, errores: {len(errores)}')
    return {'enviados': enviados, 'errores': errores,
            'periodo': f'{lunes} → {domingo}'}


@shared_task(bind=True, max_retries=2, default_retry_delay=120)
def enviar_reporte_mensual_gerencia(self, anio: int, mes: int, emails_destino: list[str]):
    """
    Envía resumen ejecutivo mensual de asistencia a la lista de emails indicada.

    Args:
        anio, mes: Período del reporte
        emails_destino: Lista de emails (gerencia, RRHH, etc.)
    """
    from tareo.models import ConfiguracionSistema, RegistroTareo, BancoHoras
    from django.db.models import Count, Sum, Q

    config = ConfiguracionSistema.get()
    empresa = config.empresa_nombre or 'Sistema'

    inicio, fin = config.get_ciclo_asistencia(anio, mes)

    qs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin)
    total = qs.count()
    trabajados = qs.filter(codigo_dia__in=['T', 'NOR', 'TR']).count()
    faltas = qs.filter(codigo_dia='FA').count()

    inicio_he, fin_he = config.get_ciclo_he(anio, mes)
    agg_he = RegistroTareo.objects.filter(fecha__gte=inicio_he, fecha__lte=fin_he).aggregate(
        t25=Sum('he_25'), t35=Sum('he_35'), t100=Sum('he_100')
    )

    banco = BancoHoras.objects.filter(periodo_anio=anio, periodo_mes=mes).aggregate(
        personas=Count('id'), saldo=Sum('saldo_horas')
    )

    MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    ctx = {
        'empresa': empresa,
        'mes_nombre': MESES[mes - 1],
        'anio': anio,
        'periodo_asist': f'{inicio.strftime("%d/%m/%Y")} → {fin.strftime("%d/%m/%Y")}',
        'periodo_he': f'{inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
        'total_dias': total,
        'trabajados': trabajados,
        'faltas': faltas,
        'tasa_asistencia': round(trabajados / total * 100, 1) if total else 0,
        'he_25': agg_he['t25'] or 0,
        'he_35': agg_he['t35'] or 0,
        'he_100': agg_he['t100'] or 0,
        'banco_personas': banco['personas'] or 0,
        'banco_saldo': banco['saldo'] or 0,
    }

    try:
        html_body = render_to_string('tareo/emails/reporte_mensual.html', ctx)
        text_body = strip_tags(html_body)

        msg = EmailMultiAlternatives(
            subject=f'Reporte Mensual Asistencia — {MESES[mes-1]} {anio} | {empresa}',
            body=text_body,
            from_email=config.email_desde or settings.DEFAULT_FROM_EMAIL,
            to=emails_destino,
        )
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
        logger.info(f'Reporte mensual {mes}/{anio} enviado a {emails_destino}')
        return {'ok': True, 'enviado_a': emails_destino}

    except Exception as exc:
        logger.error(f'Error enviando reporte mensual: {exc}')
        raise self.retry(exc=exc)


# ──────────────────────────────────────────────────────────────
# IMPORTACIONES EN BACKGROUND
# ──────────────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=1, time_limit=600)
def procesar_importacion_synkro(self, importacion_id: int, ruta_archivo: str,
                                 grupo_default: str = 'STAFF', dry_run: bool = False):
    """
    Procesa una importación Synkro de forma asíncrona.

    Se llama desde la vista después de guardar el archivo temporalmente.
    Actualiza TareoImportacion.estado durante el proceso.
    """
    from tareo.models import TareoImportacion
    from tareo.services.synkro import SynkroParser
    from tareo.services.processor import TareoProcessor

    try:
        importacion = TareoImportacion.objects.get(pk=importacion_id)
        importacion.estado = 'EN_PROCESO'
        importacion.save(update_fields=['estado'])

        parser = SynkroParser(ruta_archivo, importacion)
        registros_reloj = parser.parse_reloj()
        papeletas = parser.parse_papeletas()

        if not dry_run:
            processor = TareoProcessor(importacion)
            resultado = processor.procesar(registros_reloj, papeletas, grupo_default)
        else:
            resultado = {
                'simulado': True,
                'reloj': len(registros_reloj),
                'papeletas': len(papeletas),
            }
            importacion.estado = 'COMPLETADO'
            importacion.save(update_fields=['estado'])

        logger.info(f'Synkro importacion {importacion_id}: {resultado}')
        return resultado

    except TareoImportacion.DoesNotExist:
        logger.error(f'TareoImportacion {importacion_id} no encontrada.')
        return {'error': f'Importacion {importacion_id} no existe'}
    except Exception as exc:
        logger.error(f'Error en importacion Synkro {importacion_id}: {exc}')
        try:
            imp = TareoImportacion.objects.get(pk=importacion_id)
            imp.estado = 'FALLIDO'
            imp.errores = [str(exc)]
            imp.save(update_fields=['estado', 'errores'])
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, time_limit=300)
def procesar_importacion_sunat(self, importacion_id: int, ruta_archivo: str,
                                actualizar_personal: bool = True):
    """Procesa una importación SUNAT TR5 de forma asíncrona."""
    from tareo.models import TareoImportacion
    from tareo.services.sunat_importer import importar_tr5

    try:
        importacion = TareoImportacion.objects.get(pk=importacion_id)
        importacion.estado = 'EN_PROCESO'
        importacion.save(update_fields=['estado'])

        resultado = importar_tr5(ruta_archivo, importacion, actualizar_personal)
        logger.info(f'SUNAT importacion {importacion_id}: {resultado}')
        return resultado

    except TareoImportacion.DoesNotExist:
        return {'error': f'Importacion {importacion_id} no existe'}
    except Exception as exc:
        logger.error(f'Error en importacion SUNAT {importacion_id}: {exc}')
        try:
            imp = TareoImportacion.objects.get(pk=importacion_id)
            imp.estado = 'FALLIDO'
            imp.errores = [str(exc)]
            imp.save(update_fields=['estado', 'errores'])
        except Exception:
            pass
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=1, time_limit=300)
def procesar_importacion_s10(self, importacion_id: int, ruta_archivo: str,
                              actualizar_personal: bool = True, usar_ia: bool = False):
    """Procesa una importación S10 de forma asíncrona."""
    from tareo.models import TareoImportacion
    from tareo.services.s10_importer import importar_s10

    try:
        importacion = TareoImportacion.objects.get(pk=importacion_id)
        importacion.estado = 'EN_PROCESO'
        importacion.save(update_fields=['estado'])

        resultado = importar_s10(ruta_archivo, importacion, actualizar_personal, usar_ia)
        logger.info(f'S10 importacion {importacion_id}: {resultado}')
        return resultado

    except TareoImportacion.DoesNotExist:
        return {'error': f'Importacion {importacion_id} no existe'}
    except Exception as exc:
        logger.error(f'Error en importacion S10 {importacion_id}: {exc}')
        try:
            imp = TareoImportacion.objects.get(pk=importacion_id)
            imp.estado = 'FALLIDO'
            imp.errores = [str(exc)]
            imp.save(update_fields=['estado', 'errores'])
        except Exception:
            pass
        raise self.retry(exc=exc)
