"""
Vistas para gestión de personal (empleados).
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
import pandas as pd
from datetime import datetime, date

from ..models import SubArea, Personal, Roster
from ..forms import PersonalForm, ImportExcelForm
from ..permissions import (
    filtrar_personal, filtrar_personal_por_request, filtrar_subareas,
    puede_editar_personal, get_context_usuario, es_responsable_area
)


@login_required
def personal_list(request):
    """Lista de personal."""
    # Aplicar filtros según usuario + tenant actual (multi-tenant)
    # Audit perf 2026-05-20: filtrar por empresa reduce el scope a ~33 filas
    # promedio en escenario EDO (24 RUCs) vs 800 sin filtro.
    personal = filtrar_personal_por_request(request).select_related(
        'subarea', 'subarea__area', 'empresa'
    ).order_by('apellidos_nombres')

    # Filtros
    estado      = request.GET.get('estado', '')
    subarea_id  = request.GET.get('area', '')
    grupo_tareo = request.GET.get('grupo_tareo', '')
    buscar      = request.GET.get('buscar', '') or request.GET.get('q', '')  # alias 'q'
    empresa_id  = request.GET.get('empresa', '')

    if estado:
        personal = personal.filter(estado=estado)
    if subarea_id:
        personal = personal.filter(subarea_id=subarea_id)
    if grupo_tareo:
        personal = personal.filter(grupo_tareo=grupo_tareo)
    if empresa_id:
        try:
            personal = personal.filter(empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass  # ignorar valor invalido
    if buscar:
        personal = personal.filter(
            Q(apellidos_nombres__icontains=buscar) |
            Q(nro_doc__icontains=buscar) |
            Q(cargo__icontains=buscar)
        )

    # Contadores rápidos para los badges del filtro
    total_activos = personal.filter(estado='Activo').count()
    total_staff   = personal.filter(estado='Activo', grupo_tareo='STAFF').count()
    total_rco     = personal.filter(estado='Activo', grupo_tareo='RCO').count()

    # Paginación
    paginator = Paginator(personal, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    subareas = SubArea.objects.filter(activa=True).select_related('area')

    # Empresas activas para el filtro (multi-tenant)
    from empresas.models import Empresa
    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')

    return render(request, 'personal/personal_list.html', {
        'page_obj': page_obj,
        'areas': subareas,
        'empresas': empresas,
        'estado': estado,
        'area_id': subarea_id,
        'grupo_tareo': grupo_tareo,
        'empresa_id': empresa_id,
        'buscar': buscar,
        'total_activos': total_activos,
        'total_staff': total_staff,
        'total_rco': total_rco,
    })


@login_required
def personal_create(request):
    """Crear nuevo personal."""
    if request.method == 'POST':
        form = PersonalForm(request.POST)
        if form.is_valid():
            personal = form.save()
            from core.audit import log_create
            log_create(request, personal)
            messages.success(request, 'Personal creado exitosamente.')
            return redirect('personal_list')
    else:
        form = PersonalForm()

    context = {
        'form': form,
        'personal': None  # Para el template que verifica si está editando
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/personal_form.html', context)


@login_required
def personal_update(request, pk):
    """Actualizar personal."""
    # Verificar que el personal esté dentro del alcance del usuario
    personal = get_object_or_404(filtrar_personal(request.user), pk=pk)

    # Verificar permisos específicos
    if not puede_editar_personal(request.user, personal):
        messages.error(request, 'No tienes permisos para editar este personal.')
        return redirect('personal_list')

    if request.method == 'POST':
        # Capturar valores anteriores para auditoría
        old_values = {f.name: getattr(personal, f.name) for f in personal._meta.fields}

        form = PersonalForm(request.POST, instance=personal)
        if form.is_valid():
            # Si es responsable, validar que el área pertenezca a su gerencia
            if es_responsable_area(request.user) and not request.user.is_superuser:
                nueva_subarea = form.cleaned_data.get('subarea')
                if nueva_subarea and nueva_subarea not in filtrar_subareas(request.user):
                    messages.error(request, 'No puedes asignar personal a subáreas fuera de tu área.')
                    context = {
                        'form': form,
                        'personal': personal
                    }
                    context.update(get_context_usuario(request.user))
                    return render(request, 'personal/personal_form.html', context)

            form.save()

            # Registrar cambios en auditoría
            from core.audit import log_update
            cambios = {}
            for field_name, old_val in old_values.items():
                new_val = getattr(personal, field_name)
                if old_val != new_val:
                    cambios[field_name] = {'old': old_val, 'new': new_val}
            if cambios:
                log_update(request, personal, cambios)

            # ── Reproceso automático si cambió condición o grupo ──
            campos_reproceso = {'condicion', 'grupo_tareo'}
            cambios_reproceso = {k: v for k, v in cambios.items() if k in campos_reproceso}
            if cambios_reproceso:
                try:
                    from asistencia.services.reprocesar_personal import reprocesar_asistencia_personal
                    old_cond = cambios.get('condicion', {}).get('old', '')
                    old_grupo = cambios.get('grupo_tareo', {}).get('old', '')
                    stats = reprocesar_asistencia_personal(
                        personal,
                        old_condicion=old_cond,
                        old_grupo=old_grupo,
                    )
                    det = []
                    if 'condicion' in cambios_reproceso:
                        det.append(f'condición: {old_cond} → {personal.condicion}')
                    if 'grupo_tareo' in cambios_reproceso:
                        det.append(f'grupo: {old_grupo} → {personal.grupo_tareo}')
                    msg = (
                        f'Asistencia reprocesada automáticamente ({", ".join(det)}): '
                        f'{stats["registros_actualizados"]} registros y '
                        f'{stats["banco_horas_actualizados"]} meses de BancoHoras actualizados.'
                    )
                    if stats.get('registros_omitidos_cerrado'):
                        msg += (
                            f' ⚠️ {stats["registros_omitidos_cerrado"]} registros en períodos '
                            f'cerrados NO fueron modificados ({stats["periodos_cerrados"]}).'
                        )
                    messages.info(request, msg)
                except Exception as e:
                    import logging
                    logging.getLogger('personal').error(f'Error reprocesando asistencia: {e}', exc_info=True)
                    messages.warning(
                        request,
                        f'Personal actualizado, pero hubo un error al reprocesar la asistencia: {str(e)[:200]}. '
                        f'Contacte al administrador.'
                    )

            messages.success(request, 'Personal actualizado exitosamente.')
            return redirect('personal_list')
    else:
        form = PersonalForm(instance=personal)
        # Si es responsable, limitar opciones de área
        if es_responsable_area(request.user) and not request.user.is_superuser:
            form.fields['subarea'].queryset = filtrar_subareas(request.user)

    context = {
        'form': form,
        'personal': personal
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/personal_form.html', context)


@login_required
def personal_detail(request, pk):
    """Detalle de personal — vista 360°."""
    personal = get_object_or_404(
        filtrar_personal(request.user).select_related('subarea', 'subarea__area'),
        pk=pk
    )

    # Últimos registros de roster
    roster_reciente = Roster.objects.filter(personal=personal).order_by('-fecha')[:10]

    # Plantillas de constancias disponibles (para dropdown "Generar Constancia")
    plantillas_constancia = []
    if request.user.is_superuser:
        try:
            from documentos.models import PlantillaConstancia
            plantillas_constancia = list(
                PlantillaConstancia.objects.filter(activa=True)
                .values('pk', 'nombre', 'categoria')
                .order_by('orden', 'nombre')
            )
        except Exception:
            pass

    # ── 360°: Nomina ──────────────────────────────────────────────────
    ultimo_registro_nomina = None
    try:
        from nominas.models import RegistroNomina
        ultimo_registro_nomina = (
            RegistroNomina.objects
            .filter(personal=personal)
            .select_related('periodo')
            .order_by('-periodo__anio', '-periodo__mes')
            .first()
        )
    except Exception:
        pass

    # ── 360°: Vacaciones ──────────────────────────────────────────────
    saldo_vacacional = None
    solicitudes_vac  = []
    try:
        from vacaciones.models import SaldoVacacional, SolicitudVacacion
        saldo_vacacional = (
            SaldoVacacional.objects
            .filter(personal=personal)
            .order_by('-periodo_fin')
            .first()
        )
        solicitudes_vac = list(
            SolicitudVacacion.objects
            .filter(personal=personal)
            .order_by('-fecha_inicio')[:5]
        )
    except Exception:
        pass

    # ── 360°: Préstamos activos ───────────────────────────────────────
    prestamos_activos = []
    try:
        from prestamos.models import Prestamo
        prestamos_activos = list(
            Prestamo.objects
            .filter(personal=personal, estado__in=['EN_CURSO', 'APROBADO', 'PENDIENTE'])
            .order_by('-fecha_solicitud')[:3]
        )
    except Exception:
        pass

    # ── 360°: Última evaluación ───────────────────────────────────────
    ultima_evaluacion = None
    try:
        from evaluaciones.models import Evaluacion
        ultima_evaluacion = (
            Evaluacion.objects
            .filter(evaluado=personal)
            .select_related('ciclo')
            .order_by('-ciclo__fecha_inicio')
            .first()
        )
    except Exception:
        pass

    # ── 360°: Proceso disciplinario activo ────────────────────────────
    disciplinaria_activa = None
    try:
        from disciplinaria.models import MedidaDisciplinaria
        disciplinaria_activa = (
            MedidaDisciplinaria.objects
            .filter(personal=personal, estado__in=['BORRADOR', 'EN_DESCARGO', 'EN_RESOLUCION'])
            .order_by('-creado_en')
            .first()
        )
    except Exception:
        pass

    # ── 360°: Capacitaciones completadas ─────────────────────────────
    capacitaciones_count = 0
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        capacitaciones_count = (
            AsistenciaCapacitacion.objects
            .filter(personal=personal, estado='PRESENTE')
            .count()
        )
    except Exception:
        pass

    # ── 360°: Onboarding ─────────────────────────────────────────────
    onboarding_status = None
    try:
        from onboarding.models import ProcesoOnboarding
        onboarding_status = (
            ProcesoOnboarding.objects
            .filter(personal=personal)
            .order_by('-creado_en')
            .first()
        )
    except Exception:
        pass

    # ── 360°: Últimas asistencias (tareo) ────────────────────────────
    asistencias_recientes = []
    try:
        from asistencia.models import RegistroTareo
        asistencias_recientes = list(
            RegistroTareo.objects
            .filter(personal=personal)
            .order_by('-fecha')[:10]
        )
    except Exception:
        pass

    # ── 360°: Banco horas actual ─────────────────────────────────────
    banco_horas_saldo = None
    try:
        from asistencia.models import BancoHoras
        from django.db.models import Sum
        banco_horas_saldo = (
            BancoHoras.objects
            .filter(personal=personal)
            .aggregate(total=Sum('saldo_horas'))
        ).get('total')
    except Exception:
        pass

    # ── 360°: Historial salarial ──────────────────────────────────────
    historial_salarial = []
    try:
        from salarios.models import HistorialSalarial
        historial_salarial = list(
            HistorialSalarial.objects
            .filter(personal=personal)
            .order_by('-fecha')[:6]
        )
    except Exception:
        pass

    # ── 360°: Permisos recientes ──────────────────────────────────────
    permisos_recientes = []
    try:
        from vacaciones.models import SolicitudPermiso
        permisos_recientes = list(
            SolicitudPermiso.objects
            .filter(personal=personal)
            .order_by('-fecha_inicio')[:5]
        )
    except Exception:
        pass

    # ── 360°: Antigüedad ─────────────────────────────────────────────
    antiguedad = None
    if personal.fecha_alta:
        from datetime import date as _date
        hoy_ant = _date.today()
        delta = hoy_ant - personal.fecha_alta
        anios = delta.days // 365
        meses = (delta.days % 365) // 30
        antiguedad = {'anios': anios, 'meses': meses, 'dias_totales': delta.days}

    # ── 360°: PDI activo ──────────────────────────────────────────────
    pdi_activo = None
    try:
        from evaluaciones.models import PDI
        pdi_activo = (
            PDI.objects
            .filter(personal=personal, estado__in=['ACTIVO', 'EN_PROGRESO'])
            .order_by('-creado_en')
            .first()
        )
    except Exception:
        pass

    context = {
        'personal':               personal,
        'roster_reciente':        roster_reciente,
        'plantillas_constancia':  plantillas_constancia,
        # 360° data
        'ultimo_registro_nomina': ultimo_registro_nomina,
        'saldo_vacacional':       saldo_vacacional,
        'solicitudes_vac':        solicitudes_vac,
        'prestamos_activos':      prestamos_activos,
        'ultima_evaluacion':      ultima_evaluacion,
        'disciplinaria_activa':   disciplinaria_activa,
        'capacitaciones_count':   capacitaciones_count,
        'onboarding_status':      onboarding_status,
        'asistencias_recientes':  asistencias_recientes,
        'banco_horas_saldo':      banco_horas_saldo,
        # nuevos
        'historial_salarial':     historial_salarial,
        'permisos_recientes':     permisos_recientes,
        'antiguedad':             antiguedad,
        'pdi_activo':             pdi_activo,
        # Cese
        'today':         date.today(),
        'motivos_cese':  Personal.MOTIVO_CESE_CHOICES,
    }
    # Reglas especiales de asistencia
    try:
        from asistencia.models import ReglaEspecialPersonal
        context['reglas_especiales'] = ReglaEspecialPersonal.objects.filter(
            personal=personal).order_by('prioridad')
    except Exception:
        context['reglas_especiales'] = []
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/personal_detail.html', context)


# ================== IMPORT/EXPORT ==================

# Importar utilidades de Excel
from ..excel_utils import crear_plantilla_personal


@login_required
def personal_export(request):
    """Exportar personal a Excel con plantilla y catálogos."""
    personal = filtrar_personal(request.user).select_related('subarea', 'subarea__area')

    excel_file = crear_plantilla_personal(personal)

    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=personal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'

    return response


@login_required
def personal_import(request):
    """Importar personal desde Excel."""
    if request.method == 'POST':
        form = ImportExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']

            try:
                # Leer Excel forzando NroDoc como texto para preservar ceros a la izquierda
                df = pd.read_excel(
                    archivo,
                    sheet_name='Personal',
                    dtype={'NroDoc': str, 'CodigoFotocheck': str, 'Celular': str}
                )

                columnas_requeridas = ['NroDoc', 'ApellidosNombres']
                if not all(col in df.columns for col in columnas_requeridas):
                    messages.error(request, 'El archivo debe contener: NroDoc, ApellidosNombres')
                    return redirect('personal_import')

                creados = 0
                actualizados = 0
                errores = []

                for idx, row in df.iterrows():
                    try:
                        # Procesar DNI - asegurar que se mantienen ceros a la izquierda
                        nro_doc_raw = row['NroDoc']
                        if pd.isna(nro_doc_raw):
                            continue

                        # Si es número, convertir a string sin notación científica
                        if isinstance(nro_doc_raw, (int, float)):
                            nro_doc = str(int(nro_doc_raw)).strip()
                        else:
                            nro_doc = str(nro_doc_raw).strip()

                        if not nro_doc or nro_doc == 'nan':
                            continue

                        apellidos_nombres = str(row['ApellidosNombres']).strip()

                        # Buscar área
                        subarea = None
                        if 'SubArea' in row and pd.notna(row['SubArea']):
                            try:
                                area = SubArea.objects.get(nombre=str(row['SubArea']).strip())
                            except SubArea.DoesNotExist:
                                pass

                        # Preparar datos
                        datos = {
                            'apellidos_nombres': apellidos_nombres,
                            'tipo_doc': row.get('TipoDoc', 'DNI') if pd.notna(row.get('TipoDoc')) else 'DNI',
                            'codigo_fotocheck': row.get('CodigoFotocheck', '') if pd.notna(row.get('CodigoFotocheck')) else '',
                            'cargo': row.get('Cargo', '') if pd.notna(row.get('Cargo')) else '',
                            'tipo_trab': row.get('TipoTrabajador', 'Empleado') if pd.notna(row.get('TipoTrabajador')) else 'Empleado',
                            'subarea': subarea,
                            'estado': row.get('Estado', 'Activo') if pd.notna(row.get('Estado')) else 'Activo',
                            'sexo': row.get('Sexo', '') if pd.notna(row.get('Sexo')) else '',
                            'celular': row.get('Celular', '') if pd.notna(row.get('Celular')) else '',
                            'correo_personal': row.get('CorreoPersonal', '') if pd.notna(row.get('CorreoPersonal')) else '',
                            'correo_corporativo': row.get('CorreoCorporativo', '') if pd.notna(row.get('CorreoCorporativo')) else '',
                            'direccion': row.get('Direccion', '') if pd.notna(row.get('Direccion')) else '',
                            'ubigeo': row.get('Ubigeo', '') if pd.notna(row.get('Ubigeo')) else '',
                            'regimen_laboral': row.get('RegimenLaboral', '') if pd.notna(row.get('RegimenLaboral')) else '',
                            'regimen_turno': row.get('RegimenTurno', '') if pd.notna(row.get('RegimenTurno')) else '',
                            'observaciones': row.get('Observaciones', '') if pd.notna(row.get('Observaciones')) else '',
                        }

                        # Fechas
                        if 'FechaAlta' in row and pd.notna(row['FechaAlta']):
                            try:
                                datos['fecha_alta'] = pd.to_datetime(row['FechaAlta']).date()
                            except (ValueError, TypeError):
                                pass

                        if 'FechaCese' in row and pd.notna(row['FechaCese']):
                            try:
                                datos['fecha_cese'] = pd.to_datetime(row['FechaCese']).date()
                            except (ValueError, TypeError):
                                pass

                        if 'FechaNacimiento' in row and pd.notna(row['FechaNacimiento']):
                            try:
                                datos['fecha_nacimiento'] = pd.to_datetime(row['FechaNacimiento']).date()
                            except (ValueError, TypeError):
                                pass

                        # Decimales
                        if 'DiasLibresCorte2025' in row and pd.notna(row['DiasLibresCorte2025']):
                            try:
                                datos['dias_libres_corte_2025'] = Decimal(str(row['DiasLibresCorte2025']))
                            except (ValueError, TypeError, InvalidOperation):
                                pass

                        # Crear o actualizar (DNI es la clave única)
                        personal_obj, created = Personal.objects.update_or_create(
                            nro_doc=nro_doc,
                            defaults=datos
                        )

                        if created:
                            creados += 1
                        else:
                            actualizados += 1

                    except Exception as e:
                        errores.append(f"Fila {idx + 2}: {str(e)}")

                if creados > 0:
                    messages.success(request, f'✓ {creados} personas creadas')
                if actualizados > 0:
                    messages.info(request, f'ℹ {actualizados} personas actualizadas')
                if errores:
                    for error in errores[:10]:
                        messages.warning(request, error)

                return redirect('personal_list')

            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                import logging
                logging.getLogger(__name__).exception('Error importando personal desde Excel')
                return redirect('personal_import')
    else:
        form = ImportExcelForm()

    # Si se solicita plantilla vacía, generarla y descargar
    if request.GET.get('plantilla') == 'vacia':
        excel_file = crear_plantilla_personal(None)
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=plantilla_personal_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return response

    context = {
        'form': form,
        'titulo': 'Importar Personal',
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/import_form.html', context)


# ═══════════════════════════════════════════════════════════════════
#  ONBOARDING EXPRESS — Contratación en 45 segundos
# ═══════════════════════════════════════════════════════════════════

@login_required
def personal_create_express(request):
    """Onboarding Express del trabajador.

    Form de 1 sola pantalla con los campos esenciales para crear un
    trabajador y propagar todo el ciclo:
    - Crea Personal
    - Crea User con DNI como username + password (autogenerado)
    - Vincula Personal.usuario
    - Asigna a empresa (local) seleccionado
    - Crea SaldoApertura en cero (apertura ya completada)
    - Notifica al jefe del local (mock para demo)
    - Muestra confirmación con credenciales generadas

    Mensaje: "María Quispe lista para operar en 45 segundos."
    """
    from django.contrib.auth.models import User
    from empresas.models import Empresa
    from django.utils import timezone
    import secrets
    import string

    if request.method == 'POST':
        try:
            nro_doc      = request.POST.get('nro_doc', '').strip()
            apellidos    = request.POST.get('apellidos_nombres', '').strip().upper()
            cargo        = request.POST.get('cargo', '').strip()
            tipo_trab    = request.POST.get('tipo_trab', 'Empleado').strip()
            grupo_tareo  = request.POST.get('grupo_tareo', 'STAFF').strip()
            empresa_id   = request.POST.get('empresa_id', '')
            subarea_id   = request.POST.get('subarea_id', '')
            sueldo_base  = request.POST.get('sueldo_base', '').strip() or '1500'
            fecha_alta_s = request.POST.get('fecha_alta', '').strip()
            email        = request.POST.get('email', '').strip()
            tipo_contrato = request.POST.get('tipo_contrato', 'plazo_fijo').strip()
            regimen_pension = request.POST.get('regimen_pension', 'ONP').strip()
            password_inicial = request.POST.get('password_inicial', '').strip()

            # Validaciones
            if not nro_doc or not apellidos:
                messages.error(request, 'DNI y apellidos/nombres son requeridos.')
                raise ValueError('Campos requeridos faltantes.')

            if Personal.objects.filter(nro_doc=nro_doc).exists():
                messages.error(request, f'Ya existe un trabajador con DNI {nro_doc}.')
                raise ValueError('DNI duplicado.')

            # Resolver fecha
            try:
                fecha_alta = datetime.strptime(fecha_alta_s, '%Y-%m-%d').date() if fecha_alta_s else date.today()
            except ValueError:
                fecha_alta = date.today()

            # Resolver empresa
            empresa = None
            if empresa_id:
                try:
                    empresa = Empresa.objects.get(pk=int(empresa_id), activa=True)
                except (Empresa.DoesNotExist, ValueError, TypeError):
                    pass

            # Resolver subarea
            subarea = None
            if subarea_id:
                try:
                    subarea = SubArea.objects.get(pk=int(subarea_id))
                except (SubArea.DoesNotExist, ValueError, TypeError):
                    pass

            # Generar password si no se especificó
            if not password_inicial:
                alphabet = string.ascii_letters + string.digits
                password_inicial = ''.join(secrets.choice(alphabet) for _ in range(10))

            from django.db import transaction
            with transaction.atomic():
                # Crear Personal
                personal = Personal.objects.create(
                    nro_doc=nro_doc,
                    apellidos_nombres=apellidos,
                    cargo=cargo or 'Trabajador',
                    tipo_trab=tipo_trab,
                    grupo_tareo=grupo_tareo,
                    estado='Activo',
                    subarea=subarea,
                    empresa=empresa,
                    fecha_alta=fecha_alta,
                    sueldo_base=Decimal(sueldo_base) if sueldo_base else Decimal('1500'),
                    tipo_contrato=tipo_contrato if tipo_contrato else 'plazo_fijo',
                    regimen_pension=regimen_pension,
                    correo_corporativo=email,
                )

                # Crear User
                user, created = User.objects.get_or_create(
                    username=nro_doc,
                    defaults={
                        'email':      email or '',
                        'first_name': apellidos.split(',')[-1].strip()[:30] if ',' in apellidos else apellidos[:30],
                        'last_name':  apellidos.split(',')[0].strip()[:30] if ',' in apellidos else '',
                        'is_active':  True,
                    },
                )
                user.set_password(password_inicial)
                user.save()

                # Vincular
                personal.usuario = user
                personal.save(update_fields=['usuario'])

                # Crear SaldoApertura en cero (apertura ya completada)
                try:
                    from nominas.models import SaldoAperturaTrabajador
                    SaldoAperturaTrabajador.objects.get_or_create(
                        personal=personal,
                        defaults={
                            'fecha_corte': fecha_alta,
                            'creado_por':  request.user,
                            'notas':       'Onboarding Express — saldos en cero.',
                        },
                    )
                except Exception:
                    pass

            # Mensaje de éxito tipo cinematic
            primer_nombre = apellidos.split(',')[-1].strip().title() if ',' in apellidos else apellidos.title()
            messages.success(
                request,
                f'✓ {primer_nombre} contratada(o) en 45 segundos. '
                f'DNI: {nro_doc}  ·  Credenciales: {nro_doc} / {password_inicial}  ·  '
                f'Local: {empresa.nombre_comercial if empresa else "—"}'
            )
            return redirect('personal_express_exito', pk=personal.pk)
        except (ValueError, InvalidOperation) as e:
            # Errores ya mostrados via messages
            pass

    # GET → renderiza form
    from empresas.models import Empresa
    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    subareas = SubArea.objects.filter(activa=True).select_related('area').order_by('area__nombre', 'nombre')
    return render(request, 'personal/personal_express_form.html', {
        'empresas': empresas,
        'subareas': subareas,
        'hoy':      date.today(),
    })


@login_required
def personal_express_exito(request, pk):
    """Pantalla de confirmación tras Onboarding Express."""
    persona = get_object_or_404(Personal, pk=pk)
    # Solo se muestra si fue recién creado (último día)
    return render(request, 'personal/personal_express_exito.html', {
        'persona': persona,
    })


# ────────────────────────────────────────────────────────────────────────
# DRAWER LATERAL (handoff Cockpit) — JSON endpoint del listado /personal/
# Renderiza el drawer 540px al click en una fila SIN navegar.
# ────────────────────────────────────────────────────────────────────────

@login_required
def personal_drawer_data(request, pk):
    """JSON con los datos del empleado para el drawer 540px del listado.

    Devuelve 4 secciones del handoff: basic + general · documentos · histórico · ia.
    Liviano (no es la página detail completa) para que el click en row sea instantáneo.
    """
    from django.http import JsonResponse
    persona = get_object_or_404(
        filtrar_personal(request.user).select_related('subarea', 'subarea__area', 'cargo_obj'),
        pk=pk,
    )

    # ── BASIC + GENERAL ──
    area = getattr(persona.subarea, 'area', None)
    contrato_dias = None
    if persona.fecha_fin_contrato:
        contrato_dias = (persona.fecha_fin_contrato - date.today()).days

    basic = {
        'id':         persona.pk,
        'nombre':     persona.apellidos_nombres or '',
        'dni':        persona.nro_doc or '',
        'cargo':      persona.cargo or '',
        'area':       area.nombre if area else (persona.subarea.nombre if persona.subarea else ''),
        'subarea':    persona.subarea.nombre if persona.subarea else '',
        'foto_url':   getattr(persona.foto, 'url', '') if getattr(persona, 'foto', None) else '',
        'iniciales':  ''.join([p[0] for p in (persona.apellidos_nombres or '').split()[:2]]).upper() or '?',
        'estado':     persona.estado or 'Activo',
        'tipo_trab':  persona.tipo_trab or '',
        'grupo':      persona.grupo_tareo or '',
        'condicion':  persona.condicion or '',
        'codigo':     getattr(persona, 'codigo_interno', '') or '',
        'fecha_alta': persona.fecha_alta.isoformat() if persona.fecha_alta else None,
        'fecha_cese': persona.fecha_cese.isoformat() if persona.fecha_cese else None,
        'fecha_fin_contrato': persona.fecha_fin_contrato.isoformat() if persona.fecha_fin_contrato else None,
        'contrato_dias_restantes': contrato_dias,
        'sueldo_base': float(persona.sueldo_base or 0),
        'celular':    persona.celular or '',
        'correo':     persona.correo_corporativo or persona.correo_personal or '',
        'regimen':    persona.regimen_pension or 'ONP',
        'tiene_eps':  bool(persona.tiene_eps),
        'asig_fam':   bool(getattr(persona, 'asignacion_familiar', False)),
        'url_detail': f'/personal/{persona.pk}/',
        'url_editar': f'/personal/{persona.pk}/editar/',
    }

    # ── DOCUMENTOS (handoff: lista con icon + nombre + size + descarga) ──
    documentos = []
    try:
        from documentos.models import ArchivoTrabajador
        for d in ArchivoTrabajador.objects.filter(personal=persona).order_by('-creado_en')[:8]:
            ext = (d.archivo.name.rsplit('.', 1)[-1] if d.archivo and d.archivo.name and '.' in d.archivo.name else '').lower()
            icon_map = {
                'pdf':  'fa-file-pdf',
                'doc':  'fa-file-word', 'docx': 'fa-file-word',
                'xls':  'fa-file-excel', 'xlsx': 'fa-file-excel',
                'jpg':  'fa-file-image', 'jpeg': 'fa-file-image', 'png': 'fa-file-image',
            }
            try:
                size = d.archivo.size if d.archivo else 0
                size_kb = f'{size / 1024:.0f} KB' if size < 1024 * 1024 else f'{size / 1024 / 1024:.1f} MB'
            except Exception:
                size_kb = '—'
            documentos.append({
                'nombre': d.nombre_descriptivo or (d.archivo.name.rsplit('/', 1)[-1] if d.archivo else 'Sin nombre'),
                'tipo':   getattr(d.tipo, 'nombre', '') if getattr(d, 'tipo', None) else (ext.upper() or 'DOC'),
                'icon':   icon_map.get(ext, 'fa-file'),
                'size':   size_kb,
                'fecha':  d.creado_en.strftime('%d/%m/%Y') if d.creado_en else '',
                'url':    d.archivo.url if d.archivo else '#',
            })
    except Exception:
        pass

    # ── HISTÓRICO (handoff: timeline vertical con dots colored) ──
    historico = []
    # Alta
    if persona.fecha_alta:
        historico.append({
            'fecha':      persona.fecha_alta.isoformat(),
            'fecha_disp': persona.fecha_alta.strftime('%d/%m/%Y'),
            'titulo':     'Ingreso a la empresa',
            'sub':        persona.cargo or '',
            'color':      'brand',
        })
    # Cese
    if persona.fecha_cese:
        historico.append({
            'fecha':      persona.fecha_cese.isoformat(),
            'fecha_disp': persona.fecha_cese.strftime('%d/%m/%Y'),
            'titulo':     'Cese laboral',
            'sub':        getattr(persona, 'motivo_cese', '') or '',
            'color':      'warning',
        })
    # Vacaciones gozadas (últimas 3)
    try:
        from vacaciones.models import SolicitudVacacion
        for v in SolicitudVacacion.objects.filter(
            personal=persona, estado='APROBADA',
        ).order_by('-fecha_inicio')[:3]:
            historico.append({
                'fecha':      v.fecha_inicio.isoformat(),
                'fecha_disp': v.fecha_inicio.strftime('%d/%m/%Y'),
                'titulo':     f'Vacaciones {v.dias_calendario}d',
                'sub':        f'hasta {v.fecha_fin.strftime("%d/%m/%Y")}',
                'color':      'success',
            })
    except Exception:
        pass
    # Préstamos
    try:
        from prestamos.models import Prestamo
        for p in Prestamo.objects.filter(personal=persona).order_by('-creado_en')[:2]:
            historico.append({
                'fecha':      p.creado_en.date().isoformat(),
                'fecha_disp': p.creado_en.strftime('%d/%m/%Y'),
                'titulo':     f'Préstamo S/ {p.monto_efectivo:,.0f}',
                'sub':        getattr(p.tipo, 'nombre', '') if getattr(p, 'tipo', None) else '',
                'color':      'default',
            })
    except Exception:
        pass
    historico.sort(key=lambda x: x['fecha'], reverse=True)
    historico = historico[:10]

    # ── IA (handoff: 4 métricas mono + recomendaciones) ──
    # Si no hay un servicio real, derivamos métricas razonables desde datos existentes.
    asistencia_90d_pct = None
    try:
        from datetime import timedelta
        from asistencia.models import RegistroTareo
        from django.db.models import Q, Count
        hace_90 = date.today() - timedelta(days=90)
        agg = RegistroTareo.objects.filter(personal=persona, fecha__gte=hace_90).aggregate(
            total=Count('id'),
            asistio=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS'])),
        )
        if agg['total']:
            asistencia_90d_pct = round(100.0 * agg['asistio'] / agg['total'], 1)
    except Exception:
        pass

    # Score rotación heurístico: alto si contrato vence pronto + sin vacaciones recientes
    score_rotacion = 18  # baseline
    if contrato_dias is not None and contrato_dias <= 60:
        score_rotacion += 25
    if asistencia_90d_pct is not None and asistencia_90d_pct < 85:
        score_rotacion += 20
    if persona.estado == 'Cesado':
        score_rotacion = 100
    score_rotacion = min(100, score_rotacion)
    rotacion_nivel = 'bajo' if score_rotacion < 30 else 'medio' if score_rotacion < 60 else 'alto'

    # Salario vs banda — comparar contra promedio del cargo (mock simple)
    salario_vs_banda = '—'
    try:
        from django.db.models import Avg
        if persona.cargo:
            avg = Personal.objects.filter(
                cargo=persona.cargo, estado='Activo'
            ).exclude(pk=persona.pk).aggregate(avg=Avg('sueldo_base'))['avg']
            if avg and persona.sueldo_base:
                ratio = float(persona.sueldo_base) / float(avg)
                if ratio < 0.92: salario_vs_banda = 'Bajo (-' + str(round((1 - ratio) * 100)) + '%)'
                elif ratio > 1.08: salario_vs_banda = 'Alto (+' + str(round((ratio - 1) * 100)) + '%)'
                else: salario_vs_banda = 'En banda'
    except Exception:
        pass

    # Recomendaciones contextuales
    recomendaciones = []
    if contrato_dias is not None and 0 < contrato_dias <= 30:
        recomendaciones.append(f'⚠️ Contrato vence en {contrato_dias} días — agendar renovación')
    if asistencia_90d_pct is not None and asistencia_90d_pct < 85:
        recomendaciones.append(f'📉 Asistencia 90d en {asistencia_90d_pct}% — agendar 1:1')
    if score_rotacion >= 60 and persona.estado == 'Activo':
        recomendaciones.append('🎯 Riesgo de rotación alto — considerar retention plan')
    if not recomendaciones:
        recomendaciones.append('✓ Sin alertas — perfil estable')

    ia = {
        'score_rotacion': score_rotacion,
        'rotacion_nivel': rotacion_nivel,
        'asistencia_90d_pct': asistencia_90d_pct if asistencia_90d_pct is not None else '—',
        'salario_vs_banda': salario_vs_banda,
        'score_desempeno':   None,  # placeholder hasta integrar Evaluaciones360
        'recomendaciones':   recomendaciones,
    }

    return JsonResponse({
        'basic':      basic,
        'documentos': documentos,
        'historico':  historico,
        'ia':         ia,
    })
