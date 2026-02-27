"""
Vistas para el módulo personal.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict
import json
import re

from .models import Area, SubArea, Personal, Roster, RosterAudit
from .forms import AreaForm, SubAreaForm, PersonalForm, RosterForm, ImportExcelForm
from .permissions import (
    filtrar_areas, filtrar_subareas, filtrar_personal,
    puede_editar_personal, puede_editar_roster, get_context_usuario, es_responsable_area
)


@login_required
def home(request):
    """Vista principal del sistema."""
    # Aplicar filtros según usuario
    gerencias_filtradas = filtrar_areas(request.user)
    areas_filtradas = filtrar_subareas(request.user)
    personal_filtrado = filtrar_personal(request.user)
    
    context = {
        'total_gerencias': gerencias_filtradas.filter(activa=True).count(),
        'total_areas': areas_filtradas.filter(activa=True).count(),
        'total_personal': personal_filtrado.filter(estado='Activo').count(),
        'total_roster_hoy': Roster.objects.filter(
            fecha=datetime.now().date(),
            personal__in=personal_filtrado
        ).count(),
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'home.html', context)


def logout_view(request):
    """Vista personalizada de logout que acepta GET y POST."""
    auth_logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente.')
    return redirect('login')


# ================== GERENCIAS ==================

@login_required
def area_list(request):
    """Lista de areas."""
    # Aplicar filtros según usuario
    areas = filtrar_areas(request.user).annotate(
        total_subareas=Count('subareas'),
    ).order_by('nombre')
    
    # Filtros
    buscar = request.GET.get('buscar', '')
    if buscar:
        areas = areas.filter(
            Q(nombre__icontains=buscar) |
            Q(responsables__apellidos_nombres__icontains=buscar)
        ).distinct()
    
    context = {
        'areas': areas,
        'buscar': buscar,
        'puede_crear': request.user.is_superuser,  # Solo superusuarios pueden crear áreas
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/area_list.html', context)


@login_required
def area_create(request):
    """Crear nueva area."""
    # Solo superusuarios pueden crear áreas
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden crear áreas.')
        return redirect('area_list')
    
    if request.method == 'POST':
        form = AreaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Área creada exitosamente.')
            return redirect('area_list')
    else:
        form = AreaForm()
    
    context = {
        'form': form,
        'area': None  # Para el template que verifica si está editando
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/area_form.html', context)


@login_required
def area_update(request, pk):
    """Actualizar area."""
    # Solo superusuarios pueden editar áreas
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden editar áreas.')
        return redirect('area_list')
    
    area = get_object_or_404(Area, pk=pk)
    
    if request.method == 'POST':
        form = AreaForm(request.POST, instance=area)
        if form.is_valid():
            form.save()
            messages.success(request, 'Área actualizada exitosamente.')
            return redirect('area_list')
    else:
        form = AreaForm(instance=area)
    
    context = {
        'form': form,
        'area': area
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/area_form.html', context)


# ================== ÁREAS ==================

@login_required
def subarea_list(request):
    """Lista de áreas."""
    # Aplicar filtros según usuario
    subareas = filtrar_subareas(request.user).select_related('area').annotate(
        total_personal=Count('personal_asignado')
    ).order_by('area__nombre', 'nombre')
    
    # Filtros
    area_id = request.GET.get('area', '')
    buscar = request.GET.get('buscar', '')
    
    if area_id:
        subareas = subareas.filter(area_id=area_id)
    if buscar:
        subareas = subareas.filter(nombre__icontains=buscar)
    
    areas = Area.objects.filter(activa=True)
    
    context = {
        'subareas': subareas,
        'areas': areas,
        'buscar': buscar,
        'area_id': area_id
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/subarea_list.html', context)


@login_required
def subarea_create(request):
    """Crear nueva SubÁrea."""
    if request.method == 'POST':
        form = SubAreaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'SubÁrea creada exitosamente.')
            return redirect('subarea_list')
    else:
        form = SubAreaForm()
    
    context = {
        'form': form,
        'subarea': None  # Para el template que verifica si está editando
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/subarea_form.html', context)


@login_required
def subarea_update(request, pk):
    """Actualizar SubÁrea."""
    subarea = get_object_or_404(SubArea, pk=pk)
    
    if request.method == 'POST':
        form = SubAreaForm(request.POST, instance=subarea)
        if form.is_valid():
            form.save()
            messages.success(request, 'SubÁrea actualizada exitosamente.')
            return redirect('subarea_list')
    else:
        form = SubAreaForm(instance=subarea)
    
    context = {
        'form': form,
        'subarea': subarea
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/subarea_form.html', context)


# ================== PERSONAL ==================

@login_required
def personal_list(request):
    """Lista de personal."""
    # Aplicar filtros según usuario
    personal = filtrar_personal(request.user).select_related('subarea', 'subarea__area').order_by('apellidos_nombres')
    
    # Filtros
    estado = request.GET.get('estado', '')
    subarea_id = request.GET.get('area', '')
    buscar = request.GET.get('buscar', '')
    
    if estado:
        personal = personal.filter(estado=estado)
    if subarea_id:
        personal = personal.filter(subarea_id=subarea_id)
    if buscar:
        personal = personal.filter(
            Q(apellidos_nombres__icontains=buscar) |
            Q(nro_doc__icontains=buscar) |
            Q(cargo__icontains=buscar)
        )
    
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
        'buscar': buscar
    })


@login_required
def personal_create(request):
    """Crear nuevo personal."""
    if request.method == 'POST':
        form = PersonalForm(request.POST)
        if form.is_valid():
            form.save()
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
    """Detalle de personal."""
    personal = get_object_or_404(
        filtrar_personal(request.user).select_related('subarea', 'subarea__area'),
        pk=pk
    )
    
    # Últimos registros de roster
    roster_reciente = Roster.objects.filter(personal=personal).order_by('-fecha')[:10]
    
    context = {
        'personal': personal,
        'roster_reciente': roster_reciente
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/personal_detail.html', context)


# ================== ROSTER ==================

@login_required
def roster_list(request):
    """Lista de registros de roster."""
    rosters = Roster.objects.select_related('personal', 'personal__subarea__area').all()
    
    # Filtros
    buscar = request.GET.get('buscar', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    if buscar:
        rosters = rosters.filter(
            Q(personal__nro_doc__icontains=buscar) |
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(codigo__icontains=buscar)
        )
    
    if fecha_desde:
        rosters = rosters.filter(fecha__gte=fecha_desde)
    
    if fecha_hasta:
        rosters = rosters.filter(fecha__lte=fecha_hasta)
    
    rosters = rosters.order_by('-fecha', 'personal__apellidos_nombres')
    
    # Paginación
    paginator = Paginator(rosters, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'personal/roster_list.html', {
        'page_obj': page_obj,
        'buscar': buscar,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta
    })


@login_required
def roster_matricial(request):
    """
    Vista matricial del roster: filas=personal, columnas=días del mes.
    Incluye columna de días libres ganados y días trabajados calculados.
    """
    # Obtener mes y año de los parámetros o usar el actual
    hoy = datetime.now().date()
    mes = int(request.GET.get('mes', hoy.month))
    anio = int(request.GET.get('anio', hoy.year))
    
    # Filtros adicionales
    subarea_id = request.GET.get('area', '')
    buscar = request.GET.get('buscar', '')
    page = request.GET.get('page', 1)
    per_page = request.GET.get('per_page', '10')
    
    # Validar per_page
    if per_page == 'todos':
        per_page_num = None
    else:
        try:
            per_page_num = int(per_page)
        except ValueError:
            per_page_num = 10
    
    # Calcular primer y último día del mes
    primer_dia = datetime(anio, mes, 1).date()
    ultimo_dia = datetime(anio, mes, monthrange(anio, mes)[1]).date()
    
    # Generar lista de fechas del mes
    fechas_mes = []
    fecha_actual = primer_dia
    while fecha_actual <= ultimo_dia:
        fechas_mes.append(fecha_actual)
        fecha_actual += timedelta(days=1)
    
    # Obtener personal activo con filtros según usuario
    personal_qs = filtrar_personal(request.user).filter(estado='Activo').select_related('subarea', 'subarea__area')
    
    if subarea_id:
        personal_qs = personal_qs.filter(subarea_id=subarea_id)
    
    if buscar:
        personal_qs = personal_qs.filter(
            Q(nro_doc__icontains=buscar) |
            Q(apellidos_nombres__icontains=buscar)
        )
    
    personal_qs = personal_qs.order_by('apellidos_nombres')
    
    # Obtener todos los registros de roster del mes
    rosters = Roster.objects.filter(
        fecha__gte=primer_dia,
        fecha__lte=ultimo_dia,
        personal__in=personal_qs
    ).select_related('personal')
    
    # Organizar roster por personal y fecha (incluyendo estado)
    roster_dict = defaultdict(dict)
    roster_estados = defaultdict(dict)  # Nuevo: guardar estados
    roster_ids = defaultdict(dict)  # Nuevo: guardar IDs de roster
    for r in rosters:
        roster_dict[r.personal_id][r.fecha] = r.codigo
        roster_estados[r.personal_id][r.fecha] = r.estado  # Guardar estado
        roster_ids[r.personal_id][r.fecha] = r.id  # Guardar ID
    
    # Construir datos para la tabla
    tabla_datos = []
    fecha_hoy = datetime.now().date()
    
    for persona in personal_qs:
        # Obtener códigos del mes con sus fechas
        codigos_mes = []
        for fecha in fechas_mes:
            codigo = roster_dict[persona.id].get(fecha, '')
            estado = roster_estados[persona.id].get(fecha, 'aprobado')  # Nuevo: obtener estado
            roster_id = roster_ids[persona.id].get(fecha, None)  # Nuevo: obtener ID
            # Determinar día de la semana (0=lunes, 6=domingo)
            dia_semana = fecha.weekday()
            codigos_mes.append({
                'fecha': fecha,
                'codigo': codigo,
                'estado': estado,  # Nuevo: incluir estado
                'roster_id': roster_id,  # Nuevo: incluir ID
                'es_sabado': dia_semana == 5,
                'es_domingo': dia_semana == 6,
                'es_hoy': fecha == fecha_hoy
            })
        
        # Calcular días libres ganados del mes usando el régimen de turno
        count_t = sum(1 for item in codigos_mes if item['codigo'] == 'T')
        count_tr = sum(1 for item in codigos_mes if item['codigo'] == 'TR')
        count_dl = sum(1 for item in codigos_mes if item['codigo'] == 'DL')
        count_dla = sum(1 for item in codigos_mes if item['codigo'] == 'DLA')
        
        # Calcular factor para T según régimen de turno de la persona
        factor_t = 3  # Por defecto 21x7 -> 21/7 = 3
        if persona.regimen_turno:
            try:
                partes = persona.regimen_turno.strip().split('x')
                if len(partes) == 2:
                    dias_trabajo = int(partes[0])
                    dias_descanso = int(partes[1])
                    if dias_descanso > 0:
                        factor_t = dias_trabajo / dias_descanso
            except (ValueError, ZeroDivisionError):
                pass
        
        # TR siempre es 5x2
        factor_tr = 5.0 / 2.0  # 2.5 días TR por cada día libre
        
        # Calcular días libres ganados en el mes (con decimales)
        dias_libres_ganados_mes = round(count_t / factor_t + count_tr / factor_tr)
        
        # Calcular días libres pendientes totales
        dias_libres_ganados_total = persona.dias_libres_ganados
        dias_dl_usados_total = persona.calcular_dias_dl_usados()
        dias_dla_usados_total = persona.calcular_dias_dla_usados()
        
        # Saldo al 31/12/25 después de DLA
        saldo_corte_2025 = float(persona.dias_libres_corte_2025) - dias_dla_usados_total
        
        # Días libres pendientes = saldo del corte + ganados - DL usados
        dias_libres_pendientes_total = saldo_corte_2025 + dias_libres_ganados_total - dias_dl_usados_total
        
        fila = {
            'personal': persona,
            'dias_libres_corte_2025': round(saldo_corte_2025),
            'dias_libres_ganados': dias_libres_ganados_total,
            'dias_libres_pendientes': dias_libres_pendientes_total,
            'count_t': count_t,
            'count_tr': count_tr,
            'count_dl': count_dl,
            'count_dla': count_dla,
            'codigos': codigos_mes
        }
        tabla_datos.append(fila)
    
    # Obtener todas las áreas para el filtro
    areas = SubArea.objects.filter(activa=True).select_related('area').order_by('area__nombre', 'nombre')
    
    # Aplicar paginación
    if per_page_num is not None:
        paginator = Paginator(tabla_datos, per_page_num)
        try:
            tabla_datos_paginada = paginator.get_page(page)
        except:
            tabla_datos_paginada = paginator.get_page(1)
    else:
        # Mostrar todos sin paginación
        tabla_datos_paginada = tabla_datos
        paginator = None
    
    # Lista de meses para el selector
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre')
    ]
    
    # Lista de años (últimos 3 y próximos 2)
    anios = list(range(hoy.year - 3, hoy.year + 3))
    
    # Contar borradores del usuario actual (si es personal regular)
    borradores_count = 0
    if hasattr(request.user, 'personal_data'):
        borradores_count = Roster.objects.filter(
            personal=request.user.personal_data,
            estado='borrador'
        ).count()
    
    # Crear diccionario de estados por roster_id para JavaScript
    roster_estados_dict = {}
    for r in rosters:
        roster_estados_dict[r.id] = r.estado
    
    context = {
        'tabla_datos': tabla_datos_paginada,
        'fechas_mes': fechas_mes,
        'mes': mes,
        'anio': anio,
        'mes_nombre': dict(meses)[mes],
        'meses': meses,
        'anios': anios,
        'areas': areas,
        'area_id': subarea_id,
        'buscar': buscar,
        'page_obj': tabla_datos_paginada if paginator else None,
        'paginator': paginator,
        'per_page': per_page,
        'borradores_count': borradores_count,  # Nuevo: contador de borradores
        'roster_estados': json.dumps(roster_estados_dict),  # Nuevo: estados para JavaScript
    }
    
    return render(request, 'personal/roster_matricial.html', context)


@login_required
def roster_create(request):
    """Crear nuevo registro de roster."""
    if not request.user.is_superuser and not es_responsable_area(request.user):
        messages.error(request, 'No tienes permisos para crear registros de roster.')
        return redirect('roster_matricial')

    if request.method == 'POST':
        form = RosterForm(request.POST)
        if form.is_valid():
            personal = form.cleaned_data.get('personal')
            if personal and not puede_editar_roster(request.user, personal):
                messages.error(request, 'No tienes permisos para editar el roster de este personal.')
                return redirect('roster_matricial')
            form.save()
            messages.success(request, 'Registro de roster creado exitosamente.')
            return redirect('roster_matricial')
    else:
        form = RosterForm()
    
    return render(request, 'personal/roster_form.html', {'form': form})


@login_required
def roster_update(request, pk):
    """Actualizar registro de roster."""
    roster = get_object_or_404(Roster, pk=pk)

    puede, mensaje = roster.puede_editar(request.user)
    if not puede:
        messages.error(request, mensaje)
        return redirect('roster_matricial')
    
    if request.method == 'POST':
        form = RosterForm(request.POST, instance=roster)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registro de roster actualizado exitosamente.')
            return redirect('roster_matricial')
    else:
        form = RosterForm(instance=roster)
    
    return render(request, 'personal/roster_form.html', {
        'form': form,
        'roster': roster
    })


# ================== IMPORT/EXPORT ==================

# Importar utilidades de Excel
from .excel_utils import (
    crear_plantilla_personal, crear_plantilla_gerencias,
    crear_plantilla_areas, crear_plantilla_roster
)

# ===== GERENCIAS =====

@login_required
def area_export(request):
    """Exportar gerencias a Excel con plantilla y catálogos."""
    areas = filtrar_areas(request.user)
    
    # Crear plantilla con datos actuales
    excel_file = crear_plantilla_gerencias(areas)
    
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=gerencias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return response


@login_required
def area_import(request):
    """Importar gerencias desde Excel."""
    if request.method == 'POST':
        form = ImportExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            
            try:
                # Forzar DNI como texto para preservar ceros a la izquierda
                df = pd.read_excel(
                    archivo, 
                    sheet_name='Gerencias',
                    dtype={'Responsable_DNI': str}
                )
                
                # Validar columnas
                columnas_requeridas = ['Nombre']
                if not all(col in df.columns for col in columnas_requeridas):
                    messages.error(request, 'El archivo debe contener al menos la columna: Nombre')
                    return redirect('area_import')
                
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
                                dni_responsable = row['Responsable_DNI']
                                if isinstance(dni_responsable, (int, float)):
                                    dni_responsable = str(int(dni_responsable)).strip()
                                else:
                                    dni_responsable = str(dni_responsable).strip()

                                dni_list = [d.strip() for d in re.split(r'[;,]', dni_responsable) if d.strip()]
                                for dni in dni_list:
                                    try:
                                        responsables_list.append(Personal.objects.get(nro_doc=dni))
                                    except Personal.DoesNotExist:
                                        errores.append(f"Fila {idx + 2}: Responsable con DNI {dni} no encontrado")
                                        fila_con_error = True

                            if fila_con_error:
                                continue
                        
                        # Determinar si está activa
                        activa = True
                        if 'Activa' in row and pd.notna(row['Activa']):
                            activa = str(row['Activa']).strip().lower() in ['sí', 'si', 'yes', '1', 'true']
                        
                        # Crear o actualizar
                        area, created = Area.objects.update_or_create(
                            nombre=nombre,
                            defaults={
                                'descripcion': row.get('Descripcion', '') if pd.notna(row.get('Descripcion')) else '',
                                'activa': activa,
                            }
                        )
                        if responsables_list is not None:
                            area.responsables.set(responsables_list)
                        
                        if created:
                            creados += 1
                        else:
                            actualizados += 1
                    
                    except Exception as e:
                        errores.append(f"Fila {idx + 2}: {str(e)}")
                
                if creados > 0:
                    messages.success(request, f'✓ {creados} gerencias creadas')
                if actualizados > 0:
                    messages.info(request, f'ℹ {actualizados} gerencias actualizadas')
                if errores:
                    for error in errores[:10]:
                        messages.warning(request, error)
                
                return redirect('area_list')
            
            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                return redirect('area_import')
    else:
        form = ImportExcelForm()
    
    # Si se solicita plantilla vacía, generarla y descargar
    if request.GET.get('plantilla') == 'vacia':
        excel_file = crear_plantilla_gerencias(None)
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=plantilla_gerencias_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return response
    
    context = {
        'form': form,
        'titulo': 'Importar Gerencias',
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/import_form.html', context)


# ===== ÁREAS =====

@login_required
def subarea_export(request):
    """Exportar áreas a Excel con plantilla y catálogos."""
    subareas = filtrar_subareas(request.user)
    
    excel_file = crear_plantilla_areas(subareas)
    
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=areas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    
    return response


@login_required
def subarea_import(request):
    """Importar áreas desde Excel."""
    if request.method == 'POST':
        form = ImportExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            
            try:
                df = pd.read_excel(archivo, sheet_name='Areas')
                
                columnas_requeridas = ['Nombre', 'Gerencia']
                if not all(col in df.columns for col in columnas_requeridas):
                    messages.error(request, 'El archivo debe contener: Nombre, Area')
                    return redirect('subarea_import')
                
                creados = 0
                actualizados = 0
                errores = []
                
                for idx, row in df.iterrows():
                    try:
                        nombre = str(row['Nombre']).strip()
                        area_nombre = str(row['Area']).strip()
                        
                        if not nombre or nombre == 'nan' or not area_nombre or area_nombre == 'nan':
                            continue
                        
                        # Buscar área
                        try:
                            area = Area.objects.get(nombre=area_nombre)
                        except Area.DoesNotExist:
                            errores.append(f"Fila {idx + 2}: Área '{area_nombre}' no encontrada")
                            continue
                        
                        activa = True
                        if 'Activa' in row and pd.notna(row['Activa']):
                            activa = str(row['Activa']).strip().lower() in ['sí', 'si', 'yes', '1', 'true']
                        
                        area, created = SubArea.objects.update_or_create(
                            nombre=nombre,
                            area=area,
                            defaults={
                                'descripcion': row.get('Descripcion', '') if pd.notna(row.get('Descripcion')) else '',
                                'activa': activa,
                            }
                        )
                        
                        if created:
                            creados += 1
                        else:
                            actualizados += 1
                    
                    except Exception as e:
                        errores.append(f"Fila {idx + 2}: {str(e)}")
                
                if creados > 0:
                    messages.success(request, f'✓ {creados} áreas creadas')
                if actualizados > 0:
                    messages.info(request, f'ℹ {actualizados} áreas actualizadas')
                if errores:
                    for error in errores[:10]:
                        messages.warning(request, error)
                
                return redirect('subarea_list')
            
            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                return redirect('subarea_import')
    else:
        form = ImportExcelForm()
    
    # Si se solicita plantilla vacía, generarla y descargar
    if request.GET.get('plantilla') == 'vacia':
        excel_file = crear_plantilla_areas(None)
        response = HttpResponse(
            excel_file.read(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename=plantilla_areas_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return response
    
    context = {
        'form': form,
        'titulo': 'Importar Áreas',
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/import_form.html', context)


# ===== PERSONAL =====

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


# ===== ROSTER =====

@login_required
def roster_export(request):
    """Exportar roster a Excel con plantilla y catálogos."""
    mes = int(request.GET.get('mes', datetime.now().month))
    anio = int(request.GET.get('anio', datetime.now().year))
    
    primer_dia = datetime(anio, mes, 1).date()
    ultimo_dia = datetime(anio, mes, monthrange(anio, mes)[1]).date()
    
    personal_qs = filtrar_personal(request.user).filter(estado='Activo').order_by('apellidos_nombres')
    rosters = Roster.objects.filter(fecha__gte=primer_dia, fecha__lte=ultimo_dia, personal__in=personal_qs)
    
    excel_file = crear_plantilla_roster(mes, anio, personal_qs, rosters)
    
    response = HttpResponse(
        excel_file.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=roster_{anio}_{mes:02d}_{datetime.now().strftime("%H%M%S")}.xlsx'
    
    return response


@login_required
def roster_import(request):
    """Importar roster desde Excel."""
    if not request.user.is_superuser and not es_responsable_area(request.user):
        messages.error(request, 'No tienes permisos para importar roster.')
        return redirect('roster_matricial')

    if request.method == 'POST':
        form = ImportExcelForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            
            try:
                # Forzar DNI como texto para preservar ceros a la izquierda
                df = pd.read_excel(
                    archivo, 
                    sheet_name='Roster',
                    dtype={'DNI': str}
                )
                
                columnas_requeridas = ['DNI']
                if not all(col in df.columns for col in columnas_requeridas):
                    messages.error(request, 'El archivo debe contener la columna: DNI')
                    return redirect('roster_import')
                
                # Detectar mes y año (pedir al usuario o extraer del nombre del archivo)
                mes = int(request.POST.get('mes', datetime.now().month))
                anio = int(request.POST.get('anio', datetime.now().year))
                
                # Obtener columnas de días (solo formato Dia1, Dia2, ... Dia31)
                import re
                columnas_dias = []
                for col in df.columns:
                    # Solo columnas que sean exactamente "Dia" seguido de un número
                    if re.match(r'^Dia\d+$', str(col)):
                        columnas_dias.append(col)
                
                creados = 0
                actualizados = 0
                errores = []
                
                for idx, row in df.iterrows():
                    try:
                        # Procesar DNI correctamente para preservar ceros
                        dni_raw = row['DNI']
                        if pd.isna(dni_raw):
                            continue
                        
                        if isinstance(dni_raw, (int, float)):
                            nro_doc = str(int(dni_raw)).strip()
                        else:
                            nro_doc = str(dni_raw).strip()
                        
                        if not nro_doc or nro_doc == 'nan':
                            continue
                        
                        personal = Personal.objects.get(nro_doc=nro_doc)

                        if not puede_editar_roster(request.user, personal):
                            errores.append(
                                f"Fila {idx + 2}: No tienes permisos para editar el roster de {personal.apellidos_nombres}"
                            )
                            continue
                        
                        # Procesar cada día
                        for col_dia in columnas_dias:
                            dia = int(col_dia.replace('Dia', '').strip())
                            codigo = str(row[col_dia]).strip().upper() if pd.notna(row[col_dia]) else ''
                            
                            if codigo and codigo != 'NAN':
                                fecha = datetime(anio, mes, dia).date()
                                
                                # Validaciones especiales para DLA
                                if codigo == 'DLA':
                                    # 1. Validar saldo disponible al 31/12/25
                                    es_valido_saldo, mensaje_saldo, saldo = personal.validar_saldo_dla(nueva_dla=True)
                                    if not es_valido_saldo:
                                        errores.append(f"Fila {idx + 2}, Día {dia}: No se puede usar DLA. {mensaje_saldo}")
                                        continue
                                    
                                    # 2. Validar máximo 7 días consecutivos
                                    es_valido_consecutivos, mensaje_consecutivos = personal.validar_dla_consecutivos(fecha)
                                    if not es_valido_consecutivos:
                                        errores.append(f"Fila {idx + 2}, Día {dia}: {mensaje_consecutivos}")
                                        continue
                                
                                # Validaciones especiales para DL
                                if codigo == 'DL':
                                    # Validar que haya días libres pendientes disponibles
                                    es_valido_dl, mensaje_dl, dias_pendientes = personal.validar_saldo_dl(nuevo_dl=True)
                                    if not es_valido_dl:
                                        errores.append(f"Fila {idx + 2}, Día {dia}: {mensaje_dl}")
                                        continue
                                
                                roster, created = Roster.objects.update_or_create(
                                    personal=personal,
                                    fecha=fecha,
                                    defaults={'codigo': codigo}
                                )
                                
                                if created:
                                    creados += 1
                                else:
                                    actualizados += 1
                    
                    except Personal.DoesNotExist:
                        errores.append(f"Fila {idx + 2}: Personal con DNI {nro_doc} no encontrado")
                    except Exception as e:
                        errores.append(f"Fila {idx + 2}: {str(e)}")
                
                if creados > 0:
                    messages.success(request, f'✓ {creados} registros creados')
                if actualizados > 0:
                    messages.info(request, f'ℹ {actualizados} registros actualizados')
                if errores:
                    for error in errores[:10]:
                        messages.warning(request, error)
                
                return redirect('roster_matricial')
            
            except Exception as e:
                messages.error(request, f'Error al procesar el archivo: {str(e)}')
                import traceback
                print(traceback.format_exc())
                return redirect('roster_import')
    else:
        form = ImportExcelForm()
    
    # Obtener mes y año actuales
    mes_actual = datetime.now().month
    anio_actual = datetime.now().year
    
    context = {
        'form': form,
        'titulo': 'Importar Roster',
        'mes': mes_actual,
        'anio': anio_actual,
    }
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/roster_import.html', context)


@login_required
@require_POST
def roster_update_cell(request):
    """Actualizar una celda del roster via AJAX."""
    try:
        data = json.loads(request.body)
        personal_id = data.get('personal_id')
        fecha_str = data.get('fecha')
        codigo = data.get('codigo', '').strip().upper()
        
        # Parsear fecha
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        
        # Buscar personal dentro del alcance del usuario
        personal = get_object_or_404(filtrar_personal(request.user), pk=personal_id)
        
        # Verificar permisos
        if not puede_editar_roster(request.user, personal):
            return JsonResponse({'success': False, 'error': 'No tienes permisos para editar este personal'}, status=403)
        
        # Verificar restricciones de fecha (solo admin puede editar días anteriores)
        if not request.user.is_superuser and fecha < datetime.now().date():
            return JsonResponse({
                'success': False, 
                'error': 'Solo el administrador puede editar días anteriores al actual'
            }, status=403)
        
        # No permitir editar antes de enero 2026
        if fecha.year < 2026:
            return JsonResponse({
                'success': False,
                'error': 'No se puede editar el roster antes de enero 2026'
            }, status=400)
        
        # Validar que la fecha no sea anterior a la fecha de alta
        if personal.fecha_alta and fecha < personal.fecha_alta:
            return JsonResponse({
                'success': False, 
                'error': f'No se puede registrar antes de la fecha de alta ({personal.fecha_alta.strftime("%d/%m/%Y")})'
            }, status=400)
        
        # Obtener el código anterior para poder revertir si es necesario
        roster_anterior = Roster.objects.filter(personal=personal, fecha=fecha).first()
        codigo_anterior = roster_anterior.codigo if roster_anterior else ''
        
        # Validaciones especiales para DLA
        if codigo == 'DLA':
            # 1. Validar saldo disponible al 31/12/25
            es_valido_saldo, mensaje_saldo, saldo = personal.validar_saldo_dla(nueva_dla=True)
            if not es_valido_saldo:
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede usar DLA. {mensaje_saldo}. El saldo de días al 31/12/25 no puede ser negativo.',
                    'revert': True,
                    'old_value': codigo_anterior
                }, status=400)
            
            # 2. Validar máximo 7 días consecutivos
            es_valido_consecutivos, mensaje_consecutivos = personal.validar_dla_consecutivos(fecha)
            if not es_valido_consecutivos:
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede usar DLA. {mensaje_consecutivos}',
                    'revert': True,
                    'old_value': codigo_anterior
                }, status=400)
        
        # Validaciones especiales para DL
        if codigo == 'DL':
            # Validar que haya días libres pendientes disponibles
            es_valido_dl, mensaje_dl, dias_pendientes = personal.validar_saldo_dl(nuevo_dl=True)
            if not es_valido_dl:
                return JsonResponse({
                    'success': False,
                    'error': f'No se puede usar DL. {mensaje_dl}',
                    'revert': True,
                    'old_value': codigo_anterior
                }, status=400)
        
        # Determinar el estado según el usuario
        from .permissions import get_areas_responsable
        
        estado_inicial = 'aprobado'  # Por defecto aprobado para admin
        
        if not request.user.is_superuser:
            areas_responsable = get_areas_responsable(request.user)
            if personal.subarea and areas_responsable.filter(pk=personal.subarea.area_id).exists():
                estado_inicial = 'aprobado'
            elif hasattr(request.user, 'personal_data') and request.user.personal_data == personal:
                estado_inicial = 'borrador'
        
        if codigo:
            # Crear o actualizar roster
            roster, created = Roster.objects.update_or_create(
                personal=personal,
                fecha=fecha,
                defaults={
                    'codigo': codigo,
                    'estado': estado_inicial,
                    'modificado_por': request.user
                }
            )
            mensaje = 'Registro creado' if created else 'Registro actualizado'
            if estado_inicial == 'borrador':
                mensaje += ' (en borrador - debe enviar para aprobación)'
            roster_id = roster.id
            estado = roster.estado
        else:
            # Eliminar si el código está vacío
            Roster.objects.filter(personal=personal, fecha=fecha).delete()
            mensaje = 'Registro eliminado'
            roster_id = None
            estado = None
        
        # Calcular días libres ganados y pendientes para retornar
        dias_libres_ganados = personal.dias_libres_ganados
        dias_dl_usados = personal.calcular_dias_dl_usados()
        dias_dla_usados = personal.calcular_dias_dla_usados()
        
        # Calcular saldo al 31/12/25 después de DLA
        saldo_corte_2025 = float(personal.dias_libres_corte_2025) - dias_dla_usados
        
        # Días pendientes = saldo del corte + ganados - DL usados
        dias_libres_pendientes = saldo_corte_2025 + dias_libres_ganados - dias_dl_usados
        
        return JsonResponse({
            'success': True,
            'mensaje': mensaje,
            'codigo': codigo,
            'roster_id': roster_id,
            'estado': estado,
            'dias_libres_ganados': dias_libres_ganados,
            'dias_libres_pendientes': round(dias_libres_pendientes),
            'dias_libres_corte_2025': round(saldo_corte_2025)
        })
    
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado'}, status=404)
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERROR EN roster_update_cell: {error_traceback}")
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ================== SISTEMA DE APROBACIONES ==================

@login_required
def dashboard_aprobaciones(request):
    """Dashboard completo de aprobaciones para responsables."""
    from .permissions import get_areas_responsable
    from django.db.models import Q, Count
    
    # Verificar permisos
    areas_responsable = Area.objects.none()
    if request.user.is_superuser:
        pendientes_qs = Roster.objects.filter(estado='pendiente')
        borradores_qs = Roster.objects.filter(estado='borrador')
        aprobados_qs = Roster.objects.filter(estado='aprobado')
    else:
        areas_responsable = get_areas_responsable(request.user)
        if not areas_responsable.exists():
            messages.error(request, 'No tiene permisos para ver el dashboard de aprobaciones.')
            return redirect('home')
        
        pendientes_qs = Roster.objects.filter(
            estado='pendiente',
            personal__subarea__area__in=areas_responsable
        )
        borradores_qs = Roster.objects.filter(
            estado='borrador',
            personal__subarea__area__in=areas_responsable
        )
        aprobados_qs = Roster.objects.filter(
            estado='aprobado',
            personal__subarea__area__in=areas_responsable
        )
    
    # Filtros
    buscar = request.GET.get('buscar', '')
    subarea_filtro = request.GET.get('area', '')
    codigo_filtro = request.GET.get('codigo', '')
    fecha_desde = request.GET.get('fecha_desde', '')
    fecha_hasta = request.GET.get('fecha_hasta', '')
    
    # Aplicar filtros a pendientes
    if buscar:
        pendientes_qs = pendientes_qs.filter(
            Q(personal__nro_doc__icontains=buscar) |
            Q(personal__apellidos_nombres__icontains=buscar)
        )
    
    if subarea_filtro:
        pendientes_qs = pendientes_qs.filter(personal__subarea__area_id=subarea_filtro)
    
    if codigo_filtro:
        pendientes_qs = pendientes_qs.filter(codigo=codigo_filtro)
    
    if fecha_desde:
        pendientes_qs = pendientes_qs.filter(fecha__gte=fecha_desde)
    
    if fecha_hasta:
        pendientes_qs = pendientes_qs.filter(fecha__lte=fecha_hasta)
    
    pendientes = pendientes_qs.select_related(
        'personal', 'personal__subarea__area', 'modificado_por'
    ).order_by('-actualizado_en')
    
    # Estadísticas
    hoy = timezone.now().date()
    inicio_semana = hoy - timedelta(days=hoy.weekday())
    
    stats = {
        'pendientes': pendientes_qs.count(),
        'borradores': borradores_qs.count(),
        'aprobados_hoy': aprobados_qs.filter(aprobado_en__date=hoy).count(),
        'total_semana': aprobados_qs.filter(aprobado_en__date__gte=inicio_semana).count(),
    }
    
    # Obtener áreas para filtro
    if request.user.is_superuser:
        areas = SubArea.objects.filter(activa=True).order_by('nombre')
    elif areas_responsable.exists():
        areas = SubArea.objects.filter(area__in=areas_responsable, activa=True).order_by('nombre')
    else:
        areas = SubArea.objects.none()
    
    context = {
        'pendientes': pendientes,
        'stats': stats,
        'areas_responsable': areas_responsable,
        'subareas': areas,
        'buscar': buscar,
        'area_filtro': subarea_filtro,
        'codigo_filtro': codigo_filtro,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    }
    
    return render(request, 'personal/dashboard_aprobaciones.html', context)


@login_required
def cambios_pendientes(request):
    """Vista simplificada - redirige al dashboard."""
    return redirect('dashboard_aprobaciones')


@login_required
@require_http_methods(["POST"])
def aprobar_cambio(request, pk):
    """Aprobar un cambio de roster pendiente."""
    roster = get_object_or_404(Roster, pk=pk)
    
    # Verificar permisos
    if not roster.puede_aprobar(request.user):
        return JsonResponse({
            'success': False,
            'error': 'No tiene permisos para aprobar este cambio'
        }, status=403)
    
    roster.estado = 'aprobado'
    roster.aprobado_por = request.user
    roster.aprobado_en = timezone.now()
    roster.save()
    
    messages.success(request, f'Cambio aprobado para {roster.personal} en {roster.fecha}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'mensaje': 'Cambio aprobado'})
    
    return redirect('cambios_pendientes')


@login_required
@require_http_methods(["POST"])
def rechazar_cambio(request, pk):
    """Rechazar un cambio de roster pendiente (elimina el cambio)."""
    roster = get_object_or_404(Roster, pk=pk)
    
    # Verificar permisos
    if not roster.puede_aprobar(request.user):
        return JsonResponse({
            'success': False,
            'error': 'No tiene permisos para rechazar este cambio'
        }, status=403)
    
    personal_nombre = str(roster.personal)
    fecha = roster.fecha
    
    # Eliminar el registro rechazado
    roster.delete()
    
    messages.warning(request, f'Cambio rechazado y eliminado para {personal_nombre} en {fecha}')
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'mensaje': 'Cambio rechazado'})
    
    return redirect('cambios_pendientes')


@login_required
@require_http_methods(["POST"])
def enviar_cambios_aprobacion(request):
    """Enviar cambios en borrador para aprobación."""
    # Obtener los registros en borrador del usuario actual
    if hasattr(request.user, 'personal_data'):
        personal = request.user.personal_data
        borradores = Roster.objects.filter(
            personal=personal,
            estado='borrador'
        )
        
        count = borradores.update(estado='pendiente')
        
        if count > 0:
            messages.success(request, f'{count} cambio(s) enviado(s) para aprobación')
        else:
            messages.info(request, 'No hay cambios pendientes de enviar')
    else:
        messages.error(request, 'No se pudo identificar su perfil de personal')
    
    return redirect('roster_matricial')


@login_required
@require_http_methods(["POST"])
def aprobar_lote(request):
    """Aprobar múltiples cambios en lote."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        if not ids:
            return JsonResponse({'success': False, 'error': 'No se proporcionaron IDs'}, status=400)
        
        # Filtrar solo los que el usuario puede aprobar
        rosters = Roster.objects.filter(pk__in=ids, estado='pendiente')
        
        aprobados = 0
        for roster in rosters:
            if roster.puede_aprobar(request.user):
                roster.estado = 'aprobado'
                roster.aprobado_por = request.user
                roster.aprobado_en = timezone.now()
                roster.save()
                aprobados += 1
        
        return JsonResponse({
            'success': True,
            'aprobados': aprobados,
            'mensaje': f'{aprobados} cambio(s) aprobado(s)'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["POST"])
def rechazar_lote(request):
    """Rechazar múltiples cambios en lote."""
    try:
        data = json.loads(request.body)
        ids = data.get('ids', [])
        
        if not ids:
            return JsonResponse({'success': False, 'error': 'No se proporcionaron IDs'}, status=400)
        
        # Filtrar solo los que el usuario puede rechazar
        rosters = Roster.objects.filter(pk__in=ids, estado='pendiente')
        
        rechazados = 0
        for roster in rosters:
            if roster.puede_aprobar(request.user):
                roster.delete()
                rechazados += 1
        
        return JsonResponse({
            'success': True,
            'rechazados': rechazados,
            'mensaje': f'{rechazados} cambio(s) rechazado(s)'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# ================== GESTIÓN DE USUARIOS ==================

@login_required
def usuario_list(request):
    """Lista de usuarios del sistema con sus perfiles vinculados."""
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden gestionar usuarios')
        return redirect('home')
    
    from django.contrib.auth.models import User
    
    usuarios = User.objects.all().select_related('personal_data').order_by('username')
    
    # Buscar personal sin usuario asignado
    personal_sin_usuario = Personal.objects.filter(
        usuario__isnull=True,
        estado='Activo'
    ).order_by('apellidos_nombres')
    
    context = {
        'usuarios': usuarios,
        'personal_sin_usuario': personal_sin_usuario,
        'total_usuarios': usuarios.count(),
        'total_sin_vincular': personal_sin_usuario.count()
    }
    context.update(get_context_usuario(request.user))
    
    return render(request, 'personal/usuario_list.html', context)


@login_required
@require_http_methods(["POST"])
def usuario_vincular(request):
    """Vincular un usuario existente con un perfil de Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    
    from django.contrib.auth.models import User
    
    usuario_id = request.POST.get('usuario_id')
    personal_id = request.POST.get('personal_id')
    
    try:
        usuario = User.objects.get(pk=usuario_id)
        personal = Personal.objects.get(pk=personal_id)
        
        # Desvincular cualquier otro usuario que tenga este personal
        Personal.objects.filter(usuario=usuario).update(usuario=None)
        
        # Vincular
        personal.usuario = usuario
        personal.save()
        
        messages.success(request, f'Usuario {usuario.username} vinculado con {personal.nombre_completo}')
        return redirect('usuario_list')
        
    except (User.DoesNotExist, Personal.DoesNotExist) as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('usuario_list')


@login_required
@require_http_methods(["POST"])
def usuario_crear_y_vincular(request):
    """Crear un nuevo usuario y vincularlo automáticamente con Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    
    from django.contrib.auth.models import User
    
    personal_id = request.POST.get('personal_id')
    username = request.POST.get('username')
    password = request.POST.get('password')
    email = request.POST.get('email', '')
    
    try:
        personal = Personal.objects.get(pk=personal_id)
        
        # Verificar si ya existe el username
        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe')
            return redirect('usuario_list')
        
        # Crear usuario
        usuario = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=personal.apellidos_nombres.split(',')[1].strip() if ',' in personal.apellidos_nombres else '',
            last_name=personal.apellidos_nombres.split(',')[0].strip() if ',' in personal.apellidos_nombres else personal.apellidos_nombres
        )
        
        # Vincular con personal
        personal.usuario = usuario
        personal.save()
        
        messages.success(request, f'Usuario {username} creado y vinculado con {personal.nombre_completo}')
        return redirect('usuario_list')
        
    except Personal.DoesNotExist:
        messages.error(request, 'Personal no encontrado')
        return redirect('usuario_list')
    except Exception as e:
        messages.error(request, f'Error al crear usuario: {str(e)}')
        return redirect('usuario_list')


@login_required
@require_http_methods(["POST"])
def usuario_desvincular(request, user_id):
    """Desvincular un usuario de su perfil de Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)
    
    try:
        personal = Personal.objects.get(usuario_id=user_id)
        personal.usuario = None
        personal.save()
        
        messages.success(request, 'Usuario desvinculado correctamente')
    except Personal.DoesNotExist:
        messages.warning(request, 'El usuario no estaba vinculado')
    
    return redirect('usuario_list')


@login_required
def usuario_sincronizar(request):
    """Vista para sincronizar usuarios automáticamente."""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para esta acción')
        return redirect('home')
    
    from django.contrib.auth.models import User, Group
    from django.db import transaction
    
    if request.method == 'POST':
        
        accion = request.POST.get('accion', 'ambas')  # vincular, crear, ambas
        password_default = request.POST.get('password', 'dni')
        solo_activos = request.POST.get('solo_activos') == 'on'
        
        # LÍMITE DE SEGURIDAD: Máximo 50 usuarios por operación web
        LIMITE_WEB = 50
        
        stats = {
            'vinculados': 0,
            'creados': 0,
            'ya_vinculados': 0,
            'errores': [],
            'usuarios_creados': []
        }
        
        # Filtrar personal
        personal_qs = Personal.objects.select_related('usuario', 'subarea__area')
        if solo_activos:
            personal_qs = personal_qs.filter(estado='Activo')
        
        # Contar ya vinculados
        stats['ya_vinculados'] = personal_qs.filter(usuario__isnull=False).count()
        
        # Verificar cantidad a procesar
        personal_sin_usuario = personal_qs.filter(usuario__isnull=True, tipo_doc='DNI').exclude(nro_doc='')
        total_procesar = personal_sin_usuario.count()
        
        if total_procesar > LIMITE_WEB:
            messages.warning(
                request, 
                f'⚠️ Hay {total_procesar} registros para procesar. '
                f'La interfaz web tiene un límite de {LIMITE_WEB} por operación. '
                f'Use el comando de terminal para sincronización masiva: '
                f'python manage.py sincronizar_usuarios'
            )
            return render(request, 'personal/usuario_sincronizar.html', {
                'total_personal': Personal.objects.count(),
                'personal_con_usuario': personal_qs.filter(usuario__isnull=False).count(),
                'personal_sin_usuario': total_procesar,
                'usuarios_sin_vincular': User.objects.filter(personal_data__isnull=True, is_superuser=False).count(),
                'limite_excedido': True,
                'total_procesar': total_procesar,
                'limite': LIMITE_WEB,
            })
        
        try:
            # 1. VINCULAR USUARIOS EXISTENTES
            if accion in ['vincular', 'ambas']:
                personal_sin_usuario = personal_qs.filter(usuario__isnull=True, tipo_doc='DNI')[:LIMITE_WEB]  # Limitar cantidad
                
                for persona in personal_sin_usuario:
                    if not persona.nro_doc:
                        continue
                    
                    try:
                        usuario = User.objects.get(username=persona.nro_doc)
                        
                        # Verificar que no esté vinculado a otro
                        if hasattr(usuario, 'personal_data'):
                            continue
                        
                        persona.usuario = usuario
                        persona.save(update_fields=['usuario'])
                        stats['vinculados'] += 1
                        
                    except User.DoesNotExist:
                        pass
                    except Exception as e:
                        stats['errores'].append(f'{persona.apellidos_nombres}: {str(e)}')
            
            # 2. CREAR USUARIOS NUEVOS
            if accion in ['crear', 'ambas']:
                personal_sin_usuario = personal_qs.filter(
                    usuario__isnull=True,
                    tipo_doc='DNI'
                ).exclude(nro_doc__isnull=True).exclude(nro_doc='')[:LIMITE_WEB]  # Limitar cantidad
                
                for persona in personal_sin_usuario:
                    try:
                        # Generar username: primera letra nombre + apellido paterno
                        nombres = persona.apellidos_nombres.strip().split()
                        if len(nombres) < 2:
                            stats['errores'].append(f'{persona.apellidos_nombres}: Formato de nombre inválido')
                            continue
                        
                        apellido_paterno = nombres[0].lower()
                        primer_nombre = nombres[-1] if len(nombres) >= 2 else nombres[0]
                        primera_letra = primer_nombre[0].lower()
                        username = f'{primera_letra}{apellido_paterno}'.lower()
                        
                        # Si ya existe, agregar número
                        username_base = username
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f'{username_base}{counter}'
                            counter += 1
                            if counter > 99:
                                stats['errores'].append(f'{persona.apellidos_nombres}: No se pudo generar username único')
                                break
                        
                        if counter > 99:
                            continue
                        
                        # Generar email
                        email = persona.correo_corporativo or persona.correo_personal or f'{username}@temp.com'
                        
                        # Extraer nombres
                        first_name = ' '.join(nombres[2:]) if len(nombres) > 2 else nombres[-1]
                        last_name = ' '.join(nombres[:2]) if len(nombres) >= 2 else nombres[0]
                        
                        # Contraseña: DNI o personalizada
                        password = persona.nro_doc if password_default.lower() == 'dni' else password_default
                        
                        with transaction.atomic():
                            # Crear usuario
                            usuario = User.objects.create_user(
                                username=username,
                                email=email,
                                password=password,
                                first_name=first_name[:30],
                                last_name=last_name[:30],
                                is_staff=False,
                                is_active=True
                            )
                            
                            # Vincular
                            persona.usuario = usuario
                            persona.save(update_fields=['usuario'])
                            
                            # Si es responsable, agregar a grupo
                            if persona.areas_responsable.exists():
                                grupo, _ = Group.objects.get_or_create(name='Responsable de Área')
                                usuario.groups.add(grupo)
                            
                            stats['creados'] += 1
                            stats['usuarios_creados'].append({
                                'nombre': persona.apellidos_nombres,
                                'usuario': username,
                                'password': password
                            })
                    
                    except Exception as e:
                        stats['errores'].append(f'{persona.apellidos_nombres}: {str(e)}')
            
            # Mostrar resultados
            if stats['vinculados'] > 0:
                messages.success(request, f'✓ {stats["vinculados"]} usuarios vinculados exitosamente')
            
            if stats['creados'] > 0:
                messages.success(request, f'✓ {stats["creados"]} usuarios creados exitosamente')
                # Guardar lista de usuarios creados en sesión para mostrarlos
                request.session['usuarios_creados'] = stats['usuarios_creados']
            
            if stats['errores']:
                for error in stats['errores'][:5]:
                    messages.warning(request, f'⚠ {error}')
            
            if stats['vinculados'] == 0 and stats['creados'] == 0:
                messages.info(request, 'No se encontraron usuarios para sincronizar')
            
            return redirect('usuario_sincronizar')
        
        except Exception as e:
            messages.error(request, f'Error en sincronización: {str(e)}')
            return redirect('usuario_sincronizar')
    
    # GET - Mostrar formulario y estadísticas
    total_personal = Personal.objects.count()
    personal_con_usuario = Personal.objects.filter(usuario__isnull=False).count()
    personal_sin_usuario = Personal.objects.filter(usuario__isnull=True, tipo_doc='DNI').exclude(nro_doc='').count()
    usuarios_sin_vincular = User.objects.filter(personal_data__isnull=True, is_superuser=False).count()
    
    # Obtener lista de usuarios creados de la sesión
    usuarios_creados = request.session.pop('usuarios_creados', [])
    
    context = {
        'total_personal': total_personal,
        'personal_con_usuario': personal_con_usuario,
        'personal_sin_usuario': personal_sin_usuario,
        'usuarios_sin_vincular': usuarios_sin_vincular,
        'usuarios_creados': usuarios_creados,
    }
    
    return render(request, 'personal/usuario_sincronizar.html', context)
