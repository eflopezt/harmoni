"""
Vistas para gestión de roster.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
import pandas as pd
from datetime import datetime, timedelta
from calendar import monthrange
from collections import defaultdict
import json
import re

from ..models import SubArea, Personal, Roster
from ..forms import RosterForm, ImportExcelForm
from ..permissions import (
    filtrar_personal, filtrar_personal_por_request,
    puede_editar_roster, get_context_usuario, es_responsable_area
)


@login_required
def roster_list(request):
    """Lista de registros de roster."""
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    if not config.mod_roster and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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

    Solo disponible si mod_roster=True en ConfiguracionSistema.
    El personal que aparece depende de roster_aplica_a:
      - FORANEOS → solo condicion='FORANEO'
      - TODOS    → todo el personal activo
    Las celdas sin entrada muestran 'T' implícito (el empleado trabaja por defecto).
    """
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()

    # Guard: si el módulo está desactivado (por rubro/toggle/jornada), redirigir
    if not config.roster_activo() and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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
    # Empresa-aware: en consolidado muestra todos; al elegir una empresa (ej. Minera
    # Demo) el roster se acota a esa empresa. El default consolidado evita vacíos.
    personal_qs = filtrar_personal_por_request(request).filter(estado='Activo').select_related('subarea', 'subarea__area')

    # Filtrar por roster_aplica_a: solo foráneos o todos
    roster_aplica_a = config.roster_aplica_a
    if roster_aplica_a == 'FORANEOS':
        personal_qs = personal_qs.filter(condicion='FORANEO')

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
            codigo_db  = roster_dict[persona.id].get(fecha)     # None = sin entrada explícita
            estado     = roster_estados[persona.id].get(fecha, 'aprobado')
            roster_id  = roster_ids[persona.id].get(fecha, None)
            dia_semana = fecha.weekday()
            es_sabado  = dia_semana == 5
            es_domingo = dia_semana == 6

            # Celda sin entrada = T implícito (el empleado trabaja por defecto).
            # Es solo visual: roster_id=None indica que no hay entrada real en BD.
            # El template distingue 'T_IMPLICITO' de 'T' explícito para colorear diferente.
            if codigo_db is None:
                # Sin entrada real — aplicar lógica de régimen:
                # Si es sábado/domingo y regimen es 5x2 → D implícito
                regimen = (persona.regimen_turno or '').strip()
                if regimen.startswith('5x') and (es_sabado or es_domingo):
                    codigo_display = 'D'
                    es_implicito   = True
                else:
                    codigo_display = 'T'
                    es_implicito   = True
            else:
                codigo_display = codigo_db
                es_implicito   = False

            codigos_mes.append({
                'fecha':      fecha,
                'codigo':     codigo_display,
                'es_implicito': es_implicito,   # True = sin entrada real en BD
                'estado':     estado,
                'roster_id':  roster_id,
                'es_sabado':  es_sabado,
                'es_domingo': es_domingo,
                'es_hoy':     fecha == fecha_hoy,
            })

        # Calcular días libres ganados del mes usando el régimen de turno
        # Nota: contamos solo los T/TR explícitos (no los implícitos) para evitar
        # sobrecontar; el saldo real se calcula desde todos los registros históricos.
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
        'borradores_count': borradores_count,
        'roster_estados': json.dumps(roster_estados_dict),
        # Config roster
        'roster_aplica_a':     roster_aplica_a,
        'roster_solo_foraneos': roster_aplica_a == 'FORANEOS',
    }

    return render(request, 'personal/roster_matricial.html', context)


@login_required
def roster_create(request):
    """Crear nuevo registro de roster."""
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    if not config.mod_roster and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    if not config.mod_roster and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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
from ..excel_utils import crear_plantilla_roster


@login_required
def roster_export(request):
    """Exportar roster a Excel con plantilla y catálogos."""
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    if not config.mod_roster and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    if not config.mod_roster and not request.user.is_superuser:
        messages.warning(request, 'El módulo Roster no está activo en esta empresa.')
        return redirect('home')

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
        from ..permissions import get_areas_responsable

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
