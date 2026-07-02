"""
Post-proceso automático de importaciones de asistencia.

Tras una importación de tareo, dos pasos quedaban como comandos manuales
y, si el admin los olvidaba, los reportes salían incompletos:

  1. ``generar_faltas_auto`` — persiste FA/DS/A de los días sin marca.
  2. Cruce Tareo↔Roster — puebla ``CruceTareoRoster`` con las variaciones.

``postprocesar_importacion()`` los ejecuta best-effort al final de cada
importación exitosa: un fallo aquí NO revierte ni marca como fallida la
importación (queda en el log y en el dict de resultado).
"""
import logging
from io import StringIO

from django.core.management import call_command

logger = logging.getLogger('personal.business')


def postprocesar_importacion(importacion=None, fecha_ini=None, fecha_fin=None) -> dict:
    """Corre faltas automáticas + cruce Tareo-Roster para el período importado.

    El período se resuelve con los argumentos explícitos o, en su defecto,
    con ``importacion.periodo_inicio/fin``. Sin período, se omite (nunca
    levanta excepción).
    """
    from asistencia.models import RegistroTareo
    from asistencia.services.cruce_roster import poblar_cruce

    # El propio generar_faltas_auto registra un TareoImportacion de
    # trazabilidad: nunca post-procesarlo (evita re-entradas).
    if importacion is not None and importacion.archivo_nombre == 'generar_faltas_auto':
        return {'skipped': 'importacion de faltas automaticas'}

    if not (fecha_ini and fecha_fin) and importacion is not None:
        fecha_ini = fecha_ini or importacion.periodo_inicio
        fecha_fin = fecha_fin or importacion.periodo_fin

    if not (fecha_ini and fecha_fin):
        return {'skipped': 'periodo no determinable'}

    resultado = {
        'periodo': (fecha_ini.isoformat(), fecha_fin.isoformat()),
        'faltas_creadas': None,
        'cruce': None,
    }

    try:
        antes = RegistroTareo.objects.filter(
            fecha__gte=fecha_ini, fecha__lte=fecha_fin).count()
        call_command(
            'generar_faltas_auto',
            fecha_ini=fecha_ini.isoformat(),
            fecha_fin=fecha_fin.isoformat(),
            stdout=StringIO(),
        )
        despues = RegistroTareo.objects.filter(
            fecha__gte=fecha_ini, fecha__lte=fecha_fin).count()
        resultado['faltas_creadas'] = despues - antes
    except Exception as exc:  # best-effort: no tumbar la importación
        logger.error('Post-proceso faltas auto falló (%s → %s): %s',
                     fecha_ini, fecha_fin, exc)
        resultado['faltas_error'] = str(exc)

    try:
        resultado['cruce'] = poblar_cruce(fecha_ini, fecha_fin)
    except Exception as exc:
        logger.error('Post-proceso cruce tareo-roster falló (%s → %s): %s',
                     fecha_ini, fecha_fin, exc)
        resultado['cruce_error'] = str(exc)

    logger.info('Post-proceso importación %s: %s',
                getattr(importacion, 'pk', '—'), resultado)
    return resultado
