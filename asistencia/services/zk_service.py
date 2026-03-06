"""
Harmoni — ZKTeco Biometric Integration Service.

Conecta directamente con relojes biométricos ZKTeco (y compatibles)
via protocolo ZK sobre TCP/UDP en el puerto 4370.

Funcionalidades:
  - Probar conexión y obtener info del dispositivo
  - Extraer marcaciones raw → guardar en MarcacionBiometrica
  - Convertir marcaciones a formato TareoProcessor → RegistroTareo
  - Obtener lista de usuarios enrollados en el dispositivo

Requisito: pip install pyzk

Compatibilidad:
  ZKTeco (todos los modelos), Anviz, FingerTec, y otros con firmware ZK.
  Puerto estándar: 4370 (no cambiar sin modificar firmware).

Perú: ZKTeco tiene distribución local (www.zkteco.com.pe).
  Modelos comunes: ZK-F18 (huella+tarjeta), ZKBio800 (facial),
  ZKTeco MA300 (palm), ProFace X (multifactor).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

logger = logging.getLogger('harmoni.zk')

if TYPE_CHECKING:
    from asistencia.models import RelojBiometrico


# ── Mapeo de códigos punch ZKTeco → Harmoni ────────────────────────────────

_PUNCH_MAP: dict[int, str] = {
    0: 'ENTRADA',
    1: 'SALIDA',
    2: 'DESCANSO_SALIDA',
    3: 'DESCANSO_REGRESO',
    4: 'HE_SALIDA',
    5: 'OTRO',
    255: 'OTRO',
}


def _map_punch(punch: int) -> str:
    """Traduce código punch ZKTeco a tipo_marcacion de Harmoni."""
    return _PUNCH_MAP.get(punch, 'OTRO')


# ── ZKService ──────────────────────────────────────────────────────────────

class ZKService:
    """
    Servicio de integración con relojes biométricos ZKTeco.

    Uso:
        from asistencia.services.zk_service import ZKService
        from asistencia.models import RelojBiometrico

        reloj = RelojBiometrico.objects.get(pk=1)
        svc   = ZKService(reloj)
        info  = svc.test_connection()        # → {'ok': True, 'detail': '...'}
        result = svc.pull_attendance()       # → {'ok': True, 'nuevos': N, ...}
    """

    def __init__(self, reloj: 'RelojBiometrico'):
        self.reloj = reloj

    # ── Conexión ────────────────────────────────────────────────────────

    def _make_zk(self):
        """
        Crea objeto ZK configurado.
        Lanza ImportError si pyzk no está instalado.
        """
        try:
            from zk import ZK  # pyzk
        except ImportError:
            raise ImportError(
                'pyzk no está instalado. '
                'Ejecuta: pip install pyzk'
            )
        return ZK(
            self.reloj.ip,
            port=self.reloj.puerto,
            timeout=self.reloj.timeout,
            ommit_ping=False,
            force_udp=(self.reloj.protocolo == 'UDP'),
            verbose=False,
        )

    def test_connection(self) -> dict:
        """
        Prueba conectividad con el dispositivo.

        Actualiza estado_conexion, numero_serie y modelo_dispositivo en BD.

        Returns:
            {
                'ok': bool,
                'detail': str,    # mensaje para mostrar al usuario
                'info': {         # datos del dispositivo (si ok)
                    'serial': str,
                    'firmware': str,
                    'plataforma': str,
                    'hora_dispositivo': str,
                }
            }
        """
        from asistencia.models import RelojBiometrico

        try:
            zk = self._make_zk()
        except ImportError as e:
            return {'ok': False, 'detail': str(e), 'info': {}}

        conn = None
        try:
            conn = zk.connect()
            serial   = conn.get_serialnumber() or ''
            firmware = ''
            plataforma = ''
            hora_disp  = ''

            try:
                firmware = str(conn.get_firmware_version() or '')
            except Exception:
                pass
            try:
                plataforma = str(conn.get_platform() or '')
            except Exception:
                pass
            try:
                hora_disp = str(conn.get_time())
            except Exception:
                pass

            modelo = plataforma or firmware or ''

            # Actualizar datos del dispositivo en BD
            RelojBiometrico.objects.filter(pk=self.reloj.pk).update(
                estado_conexion='CONECTADO',
                ultima_verificacion=timezone.now(),
                numero_serie=serial,
                modelo_dispositivo=modelo,
            )

            info = {
                'serial': serial,
                'firmware': firmware,
                'plataforma': plataforma,
                'hora_dispositivo': hora_disp,
            }
            return {
                'ok': True,
                'detail': f'Conectado correctamente. Serie: {serial or "N/D"}',
                'info': info,
            }

        except Exception as exc:
            logger.warning('ZK test_connection [%s]: %s', self.reloj.ip, exc)
            RelojBiometrico.objects.filter(pk=self.reloj.pk).update(
                estado_conexion='ERROR',
                ultima_verificacion=timezone.now(),
            )
            return {
                'ok': False,
                'detail': f'No se pudo conectar: {exc}',
                'info': {},
            }
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    def get_users(self) -> list[dict]:
        """
        Obtiene lista de usuarios enrollados en el dispositivo.

        Returns:
            Lista de {'uid': int, 'user_id': str, 'nombre': str,
                      'privilegio': int, 'password': str, 'tarjeta': str}
        """
        try:
            zk = self._make_zk()
        except ImportError:
            return []

        conn = None
        try:
            conn = zk.connect()
            users = conn.get_users()
            return [
                {
                    'uid': u.uid,
                    'user_id': u.user_id,
                    'nombre': u.name,
                    'privilegio': u.privilege,
                    'password': u.password,
                    'tarjeta': u.card,
                }
                for u in (users or [])
            ]
        except Exception as exc:
            logger.error('ZK get_users [%s]: %s', self.reloj.ip, exc)
            return []
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

    # ── Pull de marcaciones ─────────────────────────────────────────────

    def pull_attendance(self, user=None) -> dict:
        """
        Descarga todas las marcaciones del dispositivo y las guarda en
        MarcacionBiometrica (deduplicando por unique_together).

        Args:
            user: Usuario Django que inicia la sincronización (para auditoría).

        Returns:
            {
                'ok': bool,
                'total': int,      # total de registros en el dispositivo
                'nuevos': int,     # registros nuevos guardados
                'omitidos': int,   # ya existían (duplicados)
                'sin_match': int,  # user_id no encontrado como DNI
                'error': str,      # mensaje de error si ok=False
            }
        """
        from asistencia.models import MarcacionBiometrica, RelojBiometrico
        from personal.models import Personal

        try:
            zk = self._make_zk()
        except ImportError as e:
            return {'ok': False, 'total': 0, 'nuevos': 0,
                    'omitidos': 0, 'sin_match': 0, 'error': str(e)}

        conn = None
        try:
            conn = zk.connect()
            attendances = conn.get_attendance() or []
        except Exception as exc:
            logger.error('ZK pull_attendance [%s]: %s', self.reloj.ip, exc)
            RelojBiometrico.objects.filter(pk=self.reloj.pk).update(
                estado_conexion='ERROR')
            return {'ok': False, 'total': 0, 'nuevos': 0,
                    'omitidos': 0, 'sin_match': 0, 'error': str(exc)}
        finally:
            if conn:
                try:
                    conn.disconnect()
                except Exception:
                    pass

        total = len(attendances)
        if total == 0:
            RelojBiometrico.objects.filter(pk=self.reloj.pk).update(
                ultima_sincronizacion=timezone.now(),
                estado_conexion='CONECTADO',
            )
            return {'ok': True, 'total': 0, 'nuevos': 0,
                    'omitidos': 0, 'sin_match': 0, 'error': ''}

        # Construir mapa DNI → Personal (si el dispositivo usa DNI como user_id)
        user_ids = set()
        for att in attendances:
            uid = str(getattr(att, 'user_id', '') or '').strip()
            if uid:
                user_ids.add(uid)

        personal_map: dict[str, object] = {}
        if self.reloj.campo_id_empleado == 'USER_ID' and user_ids:
            qs = Personal.objects.filter(nro_doc__in=user_ids).only('id', 'nro_doc')
            personal_map = {p.nro_doc: p for p in qs}

        nuevos = omitidos = sin_match = 0

        for att in attendances:
            uid_str = str(getattr(att, 'user_id', '') or '').strip()
            if not uid_str:
                continue

            punch  = int(getattr(att, 'punch', 0) or 0)
            ts_raw = getattr(att, 'timestamp', None)

            # Normalizar timestamp
            if ts_raw is None:
                continue
            if isinstance(ts_raw, datetime):
                ts = ts_raw
            else:
                try:
                    ts = datetime.combine(date.today(), ts_raw)
                except Exception:
                    continue

            personal_obj = personal_map.get(uid_str)
            if not personal_obj:
                sin_match += 1

            tipo = _map_punch(punch)

            _, created = MarcacionBiometrica.objects.get_or_create(
                reloj=self.reloj,
                user_id_dispositivo=uid_str,
                timestamp=ts,
                defaults={
                    'personal': personal_obj,
                    'tipo_marcacion': tipo,
                    'punch_raw': punch,
                },
            )
            if created:
                nuevos += 1
            else:
                omitidos += 1

        # Actualizar estado del reloj
        RelojBiometrico.objects.filter(pk=self.reloj.pk).update(
            ultima_sincronizacion=timezone.now(),
            estado_conexion='CONECTADO',
        )

        logger.info(
            'ZK sync [%s]: total=%d nuevos=%d omitidos=%d sin_match=%d',
            self.reloj.nombre, total, nuevos, omitidos, sin_match,
        )

        return {
            'ok': True,
            'total': total,
            'nuevos': nuevos,
            'omitidos': omitidos,
            'sin_match': sin_match,
            'error': '',
        }

    # ── Conversión a formato TareoProcessor ────────────────────────────

    def generar_registros_reloj(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        solo_no_procesados: bool = True,
    ) -> list[dict]:
        """
        Convierte MarcacionBiometrica del período al formato que espera
        TareoProcessor.procesar(registros_reloj=[...]).

        Agrupa por (user_id_dispositivo, fecha):
          - Primera marcación ENTRADA del día → hora_entrada
          - Última marcación SALIDA/HE_SALIDA del día → hora_salida
          - Calcula horas brutas (sin descontar almuerzo — TareoProcessor lo hace)

        Args:
            fecha_inicio: Primer día del período (inclusive).
            fecha_fin:    Último día del período (inclusive).
            solo_no_procesados: Si True, excluye marcaciones ya en un RegistroTareo.

        Returns:
            Lista de dicts con las claves que espera TareoProcessor:
            {
                'dni': str,
                'nombre': str,
                'condicion': 'LOCAL' | 'FORANEO',
                'tipo_trabajador': 'STAFF' | 'RCO',
                'area': str,
                'cargo': str,
                'fecha': date,
                'valor_raw': str,
                'codigo': str | None,
                'horas': Decimal | None,
            }
        """
        from asistencia.models import MarcacionBiometrica
        from personal.models import Personal

        qs = MarcacionBiometrica.objects.filter(
            reloj=self.reloj,
            timestamp__date__gte=fecha_inicio,
            timestamp__date__lte=fecha_fin,
        )
        if solo_no_procesados:
            qs = qs.filter(procesado=False)

        qs = qs.order_by('user_id_dispositivo', 'timestamp').select_related('personal')

        # Agrupar por (user_id, fecha)
        grupos: dict[tuple[str, date], list] = defaultdict(list)
        for m in qs:
            key = (m.user_id_dispositivo, m.timestamp.date())
            grupos[key].append(m)

        # Enriquecer con datos de Personal
        user_ids = {uid for uid, _ in grupos}
        pers_qs = (
            Personal.objects
            .filter(nro_doc__in=user_ids)
            .select_related('subarea__area')
            .only('nro_doc', 'apellidos_nombres', 'grupo_tareo',
                  'condicion', 'subarea__area__nombre')
        )
        personal_map: dict[str, object] = {p.nro_doc: p for p in pers_qs}

        registros = []
        for (uid, fecha_dia), marcas in grupos.items():
            p = personal_map.get(uid)

            # Separar por tipo
            entradas = [m for m in marcas if m.tipo_marcacion == 'ENTRADA']
            salidas  = [m for m in marcas if m.tipo_marcacion in ('SALIDA', 'HE_SALIDA')]

            hora_entrada = (
                min(m.timestamp for m in entradas).time() if entradas else None
            )
            hora_salida = (
                max(m.timestamp for m in salidas).time() if salidas else None
            )

            # Calcular horas brutas
            horas: Decimal | None = None
            codigo: str | None = None

            if hora_entrada and hora_salida:
                dt_e = datetime.combine(fecha_dia, hora_entrada)
                dt_s = datetime.combine(fecha_dia, hora_salida)
                diff_h = (dt_s - dt_e).total_seconds() / 3600
                if diff_h > 0:
                    horas = Decimal(str(round(diff_h, 2)))
                else:
                    # Salida antes que entrada (turno nocturno cruzando medianoche)
                    dt_s += timedelta(days=1)
                    diff_h = (dt_s - dt_e).total_seconds() / 3600
                    horas = Decimal(str(round(diff_h, 2)))
            elif hora_entrada and not hora_salida:
                # Solo marcó entrada → SS (sin salida)
                codigo = 'SS'
            elif not hora_entrada and salidas:
                # Solo marcó salida → tratar como SS
                codigo = 'SS'

            valor_raw = (
                str(horas) if horas is not None
                else (codigo or 'SS')
            )

            registro = {
                'dni':            uid,
                'nombre':         p.nombre_completo if p else f'ID-{uid}',
                'condicion':      (getattr(p, 'condicion', 'LOCAL') or 'LOCAL') if p else 'LOCAL',
                'tipo_trabajador': (p.grupo_tareo or 'STAFF') if p else 'STAFF',
                'area':           (
                    p.subarea.area.nombre
                    if p and p.subarea and p.subarea.area else ''
                ),
                'cargo':          (p.cargo.nombre if p and p.cargo else ''),
                'fecha':          fecha_dia,
                'valor_raw':      valor_raw,
                'codigo':         codigo,
                'horas':          horas,
            }
            registros.append(registro)

        return registros

    def procesar_a_tareo(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        user,
    ) -> dict:
        """
        Flujo completo: convierte MarcacionBiometrica → RegistroTareo.

        1. Genera registros_reloj con generar_registros_reloj()
        2. Crea TareoImportacion (tipo='ZK')
        3. Llama a TareoProcessor.procesar()
        4. Marca las MarcacionBiometrica como procesadas
        5. Retorna resumen

        Args:
            fecha_inicio: Primer día a procesar.
            fecha_fin:    Último día a procesar.
            user:         Usuario Django que ejecuta el proceso.

        Returns:
            {
                'ok': bool,
                'importacion_id': int | None,
                'creados': int,
                'actualizados': int,
                'sin_match': int,
                'errores': list,
                'advertencias': list,
                'error': str,
            }
        """
        from asistencia.models import MarcacionBiometrica, TareoImportacion
        from asistencia.services.processor import TareoProcessor

        # 1. Generar registros_reloj
        registros_reloj = self.generar_registros_reloj(fecha_inicio, fecha_fin)

        if not registros_reloj:
            return {
                'ok': False,
                'importacion_id': None,
                'creados': 0,
                'actualizados': 0,
                'sin_match': 0,
                'errores': [],
                'advertencias': [],
                'error': 'No hay marcaciones sin procesar en el período indicado.',
            }

        # 2. Crear TareoImportacion
        importacion = TareoImportacion.objects.create(
            tipo='ZK',
            periodo_inicio=fecha_inicio,
            periodo_fin=fecha_fin,
            archivo_nombre=f'ZKTeco — {self.reloj.nombre}',
            estado='PROCESANDO',
            usuario=user,
            metadata={
                'reloj_id': self.reloj.pk,
                'reloj_nombre': self.reloj.nombre,
                'reloj_ip': self.reloj.ip,
            },
        )

        try:
            # 3. Procesar con TareoProcessor
            proc = TareoProcessor(importacion)
            resultado = proc.procesar(
                registros_reloj=registros_reloj,
                papeletas=[],
            )

            # 4. Actualizar estado de la importación
            importacion.estado = (
                'COMPLETADO' if not resultado.get('errores') else 'COMPLETADO_CON_ERRORES'
            )
            importacion.total_registros  = len(registros_reloj)
            importacion.registros_ok     = resultado.get('creados', 0) + resultado.get('actualizados', 0)
            importacion.registros_error  = len(resultado.get('errores', []))
            importacion.registros_sin_match = resultado.get('sin_match', 0)
            importacion.errores          = resultado.get('errores', [])
            importacion.advertencias     = resultado.get('advertencias', [])
            importacion.save()

            # 5. Marcar MarcacionBiometrica como procesadas
            ids_procesadas = [
                r['dni'] for r in registros_reloj
            ]
            (
                MarcacionBiometrica.objects
                .filter(
                    reloj=self.reloj,
                    timestamp__date__gte=fecha_inicio,
                    timestamp__date__lte=fecha_fin,
                    user_id_dispositivo__in=ids_procesadas,
                    procesado=False,
                )
                .update(procesado=True, importacion=importacion)
            )

            return {
                'ok': True,
                'importacion_id': importacion.pk,
                'creados': resultado.get('creados', 0),
                'actualizados': resultado.get('actualizados', 0),
                'sin_match': resultado.get('sin_match', 0),
                'errores': resultado.get('errores', []),
                'advertencias': resultado.get('advertencias', []),
                'error': '',
            }

        except Exception as exc:
            importacion.estado = 'FALLIDO'
            importacion.errores = [{'mensaje': str(exc)}]
            importacion.save()
            logger.exception('ZK procesar_a_tareo error: %s', exc)
            return {
                'ok': False,
                'importacion_id': importacion.pk,
                'creados': 0,
                'actualizados': 0,
                'sin_match': 0,
                'errores': [str(exc)],
                'advertencias': [],
                'error': str(exc),
            }
