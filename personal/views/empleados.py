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
    filtrar_personal, filtrar_subareas,
    puede_editar_personal, get_context_usuario, es_responsable_area
)


@login_required
def personal_list(request):
    """Lista de personal."""
    # Aplicar filtros según usuario
    personal = filtrar_personal(request.user).select_related('subarea', 'subarea__area').order_by('apellidos_nombres')

    # Filtros
    estado      = request.GET.get('estado', '')
    subarea_id  = request.GET.get('area', '')
    grupo_tareo = request.GET.get('grupo_tareo', '')
    buscar      = request.GET.get('buscar', '')

    if estado:
        personal = personal.filter(estado=estado)
    if subarea_id:
        personal = personal.filter(subarea_id=subarea_id)
    if grupo_tareo:
        personal = personal.filter(grupo_tareo=grupo_tareo)
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

    return render(request, 'personal/personal_list.html', {
        'page_obj': page_obj,
        'areas': subareas,
        'estado': estado,
        'area_id': subarea_id,
        'grupo_tareo': grupo_tareo,
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
                import traceback
                print(traceback.format_exc())
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
