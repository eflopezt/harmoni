"""
Servicios de negocio con transacciones atómicas.
"""
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
import logging
import pandas as pd
import re
from datetime import datetime

from .models import Area, Personal, Roster, RosterAudit
from .validators import (
    PersonalValidator, RosterValidator,
    validar_archivo_excel
)

logger = logging.getLogger('personal.business')
security_logger = logging.getLogger('personal.security')


class AreaService:
    """Servicio para operaciones con Gerencias."""
    
    @staticmethod
    @transaction.atomic
    def crear_gerencia(nombre, responsable=None, responsables=None, descripcion='', activa=True, usuario=None):
        """
        Crea una gerencia de forma segura con validaciones.
        
        Args:
            nombre: Nombre de la gerencia
            responsable: Personal responsable (opcional, compatibilidad)
            responsables: Lista de Personal responsables (opcional)
            descripcion: Descripción
            activa: Si está activa
            usuario: Usuario que realiza la acción
        
        Returns:
            Área creada
        
        Raises:
            ValidationError: Si los datos no son válidos
        """
        logger.info(f"Creando gerencia '{nombre}' por usuario {usuario}")
        
        # Validaciones
        if not nombre or not nombre.strip():
            raise ValidationError('El nombre de la gerencia es obligatorio.')
        
        responsables_list = []
        if responsables:
            responsables_list = list(responsables)
        elif responsable:
            responsables_list = [responsable]
        
        area = Area.objects.create(
            nombre=nombre.strip(),
            descripcion=descripcion,
            activa=activa
        )
        if responsables_list:
            area.responsables.set(responsables_list)
        
        logger.info(f"Gerencia '{nombre}' creada exitosamente (ID: {area.id})")
        return area
    
    @staticmethod
    @transaction.atomic
    def importar_desde_excel(archivo, usuario):
        """
        Importa gerencias desde un archivo Excel de forma transaccional.
        
        Args:
            archivo: Archivo Excel (UploadedFile)
            usuario: Usuario que realiza la importación
        
        Returns:
            dict: Resultado con contadores y errores
        """
        logger.info(f"Iniciando importación de gerencias por usuario {usuario.username}")
        
        # Validar archivo
        validar_archivo_excel(archivo)
        
        try:
            df = pd.read_excel(archivo, sheet_name='Gerencias')
        except Exception as e:
            logger.error(f"Error al leer Excel: {str(e)}")
            raise ValidationError(f"Error al leer el archivo Excel: {str(e)}")
        
        # Validar columnas
        columnas_requeridas = ['Nombre']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            raise ValidationError(f"Columnas faltantes: {', '.join(columnas_faltantes)}")
        
        creados = 0
        actualizados = 0
        errores = []
        
        for idx, row in df.iterrows():
            try:
                nombre = str(row['Nombre']).strip()
                if not nombre or nombre == 'nan':
                    continue
                
                responsables_list = None
                fila_con_error = False
                if 'Responsable_DNI' in row:
                    responsables_list = []
                    if pd.notna(row['Responsable_DNI']):
                        dni_raw = str(row['Responsable_DNI'])
                        dni_list = [d.strip() for d in re.split(r'[;,]', dni_raw) if d.strip()]
                        for dni in dni_list:
                            try:
                                responsables_list.append(
                                    Personal.objects.get(nro_doc=dni)
                                )
                            except Personal.DoesNotExist:
                                errores.append(
                                    f"Fila {idx + 2}: Responsable con DNI {dni} no encontrado"
                                )
                                fila_con_error = True

                    if fila_con_error:
                        continue
                
                # Determinar si está activa
                activa = True
                if 'Activa' in row and pd.notna(row['Activa']):
                    activa = str(row['Activa']).strip().lower() in ['sí', 'si', 'yes', '1', 'true']
                
                # Crear o actualizar
                gerencia, created = Area.objects.update_or_create(
                    nombre=nombre,
                    defaults={
                        'descripcion': row.get('Descripcion', '') if pd.notna(row.get('Descripcion')) else '',
                        'activa': activa,
                    }
                )
                if responsables_list is not None:
                    gerencia.responsables.set(responsables_list)
                
                if created:
                    creados += 1
                    logger.info(f"Área creada: {nombre}")
                else:
                    actualizados += 1
                    logger.info(f"Área actualizada: {nombre}")
            
            except ValidationError as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
            except Exception as e:
                logger.error(f"Error en fila {idx + 2}: {str(e)}")
                errores.append(f"Fila {idx + 2}: Error inesperado - {str(e)}")
        
        resultado = {
            'creados': creados,
            'actualizados': actualizados,
            'errores': errores
        }
        
        logger.info(
            f"Importación completada: {creados} creadas, "
            f"{actualizados} actualizadas, {len(errores)} errores"
        )
        
        return resultado


class RosterService:
    """Servicio para operaciones con Roster."""
    
    @staticmethod
    @transaction.atomic
    def actualizar_roster(roster_id, codigo, usuario, observaciones=''):
        """
        Actualiza un registro de roster con validaciones y auditoría.
        
        Args:
            roster_id: ID del roster a actualizar
            codigo: Nuevo código
            usuario: Usuario que realiza la acción
            observaciones: Observaciones adicionales
        
        Returns:
            Roster actualizado
        
        Raises:
            ValidationError: Si la operación no es válida
        """
        try:
            roster = Roster.objects.select_related('personal').get(pk=roster_id)
        except Roster.DoesNotExist:
            logger.error(f"Roster {roster_id} no encontrado")
            raise ValidationError('Registro de roster no encontrado.')
        
        # Validar permisos
        RosterValidator.validar_fecha_edicion(roster.fecha, usuario)
        
        # Validar código
        codigo_validado = RosterValidator.validar_codigo(codigo)
        
        # Guardar valor anterior para auditoría
        codigo_anterior = roster.codigo
        
        # Actualizar
        roster.codigo = codigo_validado
        roster.observaciones = observaciones
        roster.modificado_por = usuario
        
        # Determinar estado
        if usuario.is_superuser:
            roster.estado = 'aprobado'
            roster.aprobado_por = usuario
            roster.aprobado_en = timezone.now()
        else:
            roster.estado = 'pendiente'
        
        roster.save()
        
        # Crear registro de auditoría
        RosterAudit.objects.create(
            personal=roster.personal,
            fecha=roster.fecha,
            campo_modificado='codigo',
            valor_anterior=codigo_anterior,
            valor_nuevo=codigo_validado,
            usuario=usuario
        )
        
        logger.info(
            f"Roster actualizado: {roster.personal} - {roster.fecha} - "
            f"{codigo_anterior} → {codigo_validado} por {usuario.username}"
        )
        
        return roster
    
    @staticmethod
    @transaction.atomic
    def aprobar_cambio(roster_id, usuario):
        """
        Aprueba un cambio pendiente en el roster.
        
        Args:
            roster_id: ID del roster a aprobar
            usuario: Usuario que aprueba
        
        Returns:
            Roster aprobado
        
        Raises:
            ValidationError: Si no se puede aprobar
        """
        try:
            roster = Roster.objects.select_related('personal', 'personal__subarea__area').get(pk=roster_id)
        except Roster.DoesNotExist:
            logger.error(f"Roster {roster_id} no encontrado")
            raise ValidationError('Registro de roster no encontrado.')
        
        # Validar que el usuario puede aprobar
        if not roster.puede_aprobar(usuario):
            security_logger.warning(
                f"Usuario {usuario.username} intentó aprobar roster {roster_id} sin permisos"
            )
            raise ValidationError('No tienes permisos para aprobar este cambio.')
        
        # Validar que está pendiente
        if roster.estado != 'pendiente':
            raise ValidationError(f'El registro no está pendiente de aprobación (estado: {roster.estado}).')
        
        # Aprobar
        roster.estado = 'aprobado'
        roster.aprobado_por = usuario
        roster.aprobado_en = timezone.now()
        roster.save()
        
        # Auditoría
        RosterAudit.objects.create(
            personal=roster.personal,
            fecha=roster.fecha,
            campo_modificado='estado',
            valor_anterior='pendiente',
            valor_nuevo='aprobado',
            usuario=usuario
        )
        
        logger.info(
            f"Cambio aprobado: {roster.personal} - {roster.fecha} - "
            f"{roster.codigo} por {usuario.username}"
        )
        
        return roster
    
    @staticmethod
    @transaction.atomic
    def rechazar_cambio(roster_id, usuario, motivo=''):
        """
        Rechaza un cambio pendiente en el roster.
        
        Args:
            roster_id: ID del roster a rechazar
            usuario: Usuario que rechaza
            motivo: Motivo del rechazo
        
        Returns:
            Roster rechazado
        
        Raises:
            ValidationError: Si no se puede rechazar
        """
        try:
            roster = Roster.objects.select_related('personal', 'personal__subarea__area').get(pk=roster_id)
        except Roster.DoesNotExist:
            logger.error(f"Roster {roster_id} no encontrado")
            raise ValidationError('Registro de roster no encontrado.')
        
        # Validar que el usuario puede aprobar/rechazar
        if not roster.puede_aprobar(usuario):
            security_logger.warning(
                f"Usuario {usuario.username} intentó rechazar roster {roster_id} sin permisos"
            )
            raise ValidationError('No tienes permisos para rechazar este cambio.')
        
        # Validar que está pendiente
        if roster.estado != 'pendiente':
            raise ValidationError(f'El registro no está pendiente de aprobación (estado: {roster.estado}).')
        
        # Rechazar (eliminar el cambio pendiente o revertir a aprobado)
        codigo_anterior = roster.codigo
        
        # Si existe un valor aprobado anterior, restaurarlo
        # Por ahora, simplemente eliminamos el registro pendiente
        roster.delete()
        
        # Auditoría
        RosterAudit.objects.create(
            personal=roster.personal,
            fecha=roster.fecha,
            campo_modificado='estado',
            valor_anterior='pendiente',
            valor_nuevo=f'rechazado: {motivo}',
            usuario=usuario
        )
        
        logger.info(
            f"Cambio rechazado: {roster.personal} - {roster.fecha} - "
            f"{codigo_anterior} por {usuario.username}. Motivo: {motivo}"
        )
        
        return roster
    
    @staticmethod
    @transaction.atomic
    def importar_desde_excel(archivo, usuario):
        """
        Importa roster desde un archivo Excel de forma transaccional.
        
        Args:
            archivo: Archivo Excel (UploadedFile)
            usuario: Usuario que realiza la importación
        
        Returns:
            dict: Resultado con contadores y errores
        """
        logger.info(f"Iniciando importación de roster por usuario {usuario.username}")
        
        # Validar archivo
        validar_archivo_excel(archivo)
        
        try:
            df = pd.read_excel(archivo, sheet_name=0)
        except Exception as e:
            logger.error(f"Error al leer Excel: {str(e)}")
            raise ValidationError(f"Error al leer el archivo Excel: {str(e)}")
        
        # Validar columnas
        columnas_requeridas = ['DNI', 'Fecha', 'Codigo']
        columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
        if columnas_faltantes:
            raise ValidationError(f"Columnas faltantes: {', '.join(columnas_faltantes)}")
        
        creados = 0
        actualizados = 0
        errores = []
        
        for idx, row in df.iterrows():
            try:
                # Obtener datos
                dni = str(row['DNI']).strip()
                fecha_str = str(row['Fecha']).strip()
                codigo = str(row['Codigo']).strip().upper()
                
                if not dni or dni == 'nan' or not fecha_str or not codigo:
                    continue
                
                # Buscar personal
                try:
                    personal = Personal.objects.get(nro_doc=dni)
                except Personal.DoesNotExist:
                    errores.append(f"Fila {idx + 2}: Personal con DNI {dni} no encontrado")
                    continue
                
                # Parsear fecha
                try:
                    if isinstance(row['Fecha'], pd.Timestamp):
                        fecha = row['Fecha'].date()
                    else:
                        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                except ValueError:
                    errores.append(f"Fila {idx + 2}: Formato de fecha inválido: {fecha_str}")
                    continue
                
                # Validar código
                try:
                    codigo = RosterValidator.validar_codigo(codigo)
                except ValidationError as e:
                    errores.append(f"Fila {idx + 2}: {str(e)}")
                    continue
                
                # Crear o actualizar
                roster, created = Roster.objects.update_or_create(
                    personal=personal,
                    fecha=fecha,
                    defaults={
                        'codigo': codigo,
                        'modificado_por': usuario,
                        'estado': 'aprobado' if usuario.is_superuser else 'pendiente',
                        'fuente': f'Importación Excel por {usuario.username}'
                    }
                )
                
                if created:
                    creados += 1
                else:
                    actualizados += 1
                    # Crear auditoría
                    RosterAudit.objects.create(
                        personal=personal,
                        fecha=fecha,
                        campo_modificado='codigo',
                        valor_anterior='',
                        valor_nuevo=codigo,
                        usuario=usuario
                    )
            
            except ValidationError as e:
                errores.append(f"Fila {idx + 2}: {str(e)}")
            except Exception as e:
                logger.error(f"Error en fila {idx + 2}: {str(e)}")
                errores.append(f"Fila {idx + 2}: Error inesperado - {str(e)}")
        
        resultado = {
            'creados': creados,
            'actualizados': actualizados,
            'errores': errores
        }
        
        logger.info(
            f"Importación completada: {creados} creados, "
            f"{actualizados} actualizados, {len(errores)} errores"
        )
        
        return resultado


class PersonalService:
    """Servicio para operaciones con Personal."""
    
    @staticmethod
    @transaction.atomic
    def crear_personal(datos, usuario):
        """
        Crea un registro de personal con validaciones completas.
        
        Args:
            datos: Diccionario con los datos del personal
            usuario: Usuario que realiza la acción
        
        Returns:
            Personal creado
        
        Raises:
            ValidationError: Si los datos no son válidos
        """
        logger.info(f"Creando personal por usuario {usuario.username}")
        
        # Validaciones
        nro_doc = datos.get('nro_doc')
        tipo_doc = datos.get('tipo_doc', 'DNI')
        
        if not nro_doc:
            raise ValidationError('El número de documento es obligatorio.')
        
        PersonalValidator.validar_nro_doc(nro_doc, tipo_doc)
        
        # Validar régimen si existe
        regimen_turno = datos.get('regimen_turno')
        if regimen_turno:
            PersonalValidator.validar_regimen_turno(regimen_turno)
        
        # Crear personal
        personal = Personal.objects.create(**datos)
        
        logger.info(
            f"Personal creado: {personal.apellidos_nombres} ({personal.nro_doc}) "
            f"por {usuario.username}"
        )
        
        return personal
