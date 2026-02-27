"""
Vistas del módulo Tareo.
Solo accesibles para superusuarios (administradores).
"""
import os
import tempfile
from decimal import Decimal
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.management import call_command
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _get_importacion_activa(tipo='RELOJ', importacion_id=None):
    """Devuelve la importación activa (por ID o la última completada de ese tipo)."""
    from tareo.models import TareoImportacion
    if importacion_id:
        try:
            return TareoImportacion.objects.get(pk=importacion_id)
        except TareoImportacion.DoesNotExist:
            pass
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')
        .first()
    )


def _lista_importaciones(tipo='RELOJ'):
    """Lista de importaciones completadas para selector."""
    from tareo.models import TareoImportacion
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')[:30]
    )


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def tareo_dashboard(request):
    """Panel principal del módulo Tareo (solo admin)."""
    from tareo.models import BancoHoras, RegistroTareo, TareoImportacion

    ultimas_imports = TareoImportacion.objects.order_by('-creado_en')[:10]
    ultima_reloj = _get_importacion_activa('RELOJ')

    stats = {}
    if ultima_reloj:
        qs = RegistroTareo.objects.filter(importacion=ultima_reloj)
        stats = {
            'total_registros': qs.count(),
            'staff_personas': qs.filter(grupo='STAFF').values('dni').distinct().count(),
            'rco_personas': qs.filter(grupo='RCO').values('dni').distinct().count(),
            'he_25_total': qs.aggregate(t=Sum('he_25'))['t'] or Decimal('0'),
            'he_35_total': qs.aggregate(t=Sum('he_35'))['t'] or Decimal('0'),
            'he_100_total': qs.aggregate(t=Sum('he_100'))['t'] or Decimal('0'),
            'faltas': qs.filter(codigo_dia='F').count(),
            'vacaciones': qs.filter(codigo_dia__in=['V', 'VAC']).count(),
        }
        stats['he_total'] = stats['he_25_total'] + stats['he_35_total'] + stats['he_100_total']

    banco_stats = BancoHoras.objects.aggregate(
        personas=Count('personal', distinct=True),
        saldo_total=Sum('saldo_horas'),
        acumulado_25=Sum('he_25_acumuladas'),
        acumulado_35=Sum('he_35_acumuladas'),
        acumulado_100=Sum('he_100_acumuladas'),
        compensado=Sum('he_compensadas'),
    )

    context = {
        'titulo': 'Módulo Tareo',
        'ultimas_imports': ultimas_imports,
        'ultima_reloj': ultima_reloj,
        'stats': stats,
        'banco_stats': banco_stats,
    }
    return render(request, 'tareo/dashboard.html', context)


# ---------------------------------------------------------------------------
# VISTA STAFF — Matriz persona × día
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def vista_staff(request):
    """Matriz de asistencia para personal STAFF."""
    from tareo.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        messages.warning(request, 'No hay importaciones RELOJ completadas.')
        return redirect('tareo_dashboard')

    registros = (
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='STAFF')
        .order_by('nombre_archivo', 'fecha')
        .values(
            'dni', 'nombre_archivo', 'fecha', 'codigo_dia',
            'horas_marcadas', 'horas_efectivas',
            'he_25', 'he_35', 'he_100', 'he_al_banco',
        )
    )

    # Estructura: { dni: { 'nombre': str, 'dias': {fecha: registro}, totales } }
    personas = {}
    fechas_set = set()

    for r in registros:
        dni = r['dni']
        fecha = r['fecha']
        fechas_set.add(fecha)

        if dni not in personas:
            personas[dni] = {
                'dni': dni,
                'nombre': r['nombre_archivo'],
                'dias': {},
                'total_he_banco': Decimal('0'),
                'total_he_25': Decimal('0'),
                'total_he_35': Decimal('0'),
                'total_he_100': Decimal('0'),
                'total_horas': Decimal('0'),
                'faltas': 0,
                'vacaciones': 0,
                'dias_trabajados': 0,
            }

        personas[dni]['dias'][fecha] = r
        personas[dni]['total_he_banco'] += (r['he_25'] + r['he_35'] + r['he_100'])
        personas[dni]['total_he_25'] += r['he_25']
        personas[dni]['total_he_35'] += r['he_35']
        personas[dni]['total_he_100'] += r['he_100']
        personas[dni]['total_horas'] += (r['horas_marcadas'] or Decimal('0'))

        cod = (r['codigo_dia'] or '').upper()
        if cod == 'F':
            personas[dni]['faltas'] += 1
        elif cod in ('V', 'VAC'):
            personas[dni]['vacaciones'] += 1
        else:
            personas[dni]['dias_trabajados'] += 1

    fechas = sorted(fechas_set)
    personas_list = sorted(personas.values(), key=lambda x: x['nombre'])

    # Pre-procesar filas para el template (evita lookups dinámicos en Django templates)
    for p in personas_list:
        p['row'] = [p['dias'].get(f) for f in fechas]

    context = {
        'titulo': 'Vista STAFF — Matriz de Asistencia',
        'importacion': importacion,
        'importaciones': _lista_importaciones('RELOJ'),
        'personas': personas_list,
        'fechas': fechas,
        'total_personas': len(personas_list),
    }
    return render(request, 'tareo/vista_staff.html', context)


# ---------------------------------------------------------------------------
# VISTA RCO — Tabla detalle con HE 25/35/100
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def vista_rco(request):
    """Tabla detalle de horas extra para personal RCO."""
    from tareo.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        messages.warning(request, 'No hay importaciones RELOJ completadas.')
        return redirect('tareo_dashboard')

    buscar_dni = request.GET.get('dni', '').strip()
    solo_con_he = request.GET.get('solo_he', '') == '1'

    qs = (
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='RCO')
        .order_by('nombre_archivo', 'fecha')
    )

    if buscar_dni:
        qs = qs.filter(Q(dni__icontains=buscar_dni) | Q(nombre_archivo__icontains=buscar_dni))

    if solo_con_he:
        qs = qs.filter(Q(he_25__gt=0) | Q(he_35__gt=0) | Q(he_100__gt=0))

    # Resumen por persona
    resumen = (
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='RCO')
        .values('dni', 'nombre_archivo')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
            dias_trabajados=Count('id'),
        )
        .order_by('nombre_archivo')
    )

    totales = qs.aggregate(
        t_he_25=Sum('he_25'),
        t_he_35=Sum('he_35'),
        t_he_100=Sum('he_100'),
        t_horas=Sum('horas_marcadas'),
    )

    context = {
        'titulo': 'Vista RCO — Horas Extra Detalle',
        'importacion': importacion,
        'importaciones': _lista_importaciones('RELOJ'),
        'registros': qs,
        'resumen': resumen,
        'totales': totales,
        'buscar_dni': buscar_dni,
        'solo_con_he': solo_con_he,
        'total_registros': qs.count(),
    }
    return render(request, 'tareo/vista_rco.html', context)


# ---------------------------------------------------------------------------
# BANCO DE HORAS (solo STAFF)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def banco_horas_view(request):
    """Saldo del banco de horas acumulativas por personal STAFF."""
    from tareo.models import BancoHoras

    anio = request.GET.get('anio', timezone.now().year)
    try:
        anio = int(anio)
    except (ValueError, TypeError):
        anio = timezone.now().year

    mes = request.GET.get('mes', '')
    buscar = request.GET.get('buscar', '').strip()

    qs = BancoHoras.objects.filter(periodo_anio=anio).select_related('personal')

    if mes:
        try:
            qs = qs.filter(periodo_mes=int(mes))
        except (ValueError, TypeError):
            pass

    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    qs = qs.order_by('-periodo_mes', 'personal__apellidos_nombres')

    totales = qs.aggregate(
        t_acum_25=Sum('he_25_acumuladas'),
        t_acum_35=Sum('he_35_acumuladas'),
        t_acum_100=Sum('he_100_acumuladas'),
        t_compensadas=Sum('he_compensadas'),
        t_saldo=Sum('saldo_horas'),
    )

    anios_disponibles = (
        BancoHoras.objects
        .values_list('periodo_anio', flat=True)
        .distinct()
        .order_by('-periodo_anio')
    )

    MESES = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    context = {
        'titulo': 'Banco de Horas — STAFF',
        'banco_list': qs,
        'totales': totales,
        'anio_sel': anio,
        'mes_sel': mes,
        'buscar': buscar,
        'anios': anios_disponibles,
        'meses': MESES,
        'total_personas': qs.values('personal').distinct().count(),
    }
    return render(request, 'tareo/banco_horas.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR (upload web)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_view(request):
    """Formulario web para importar archivo Excel de tareo."""
    from tareo.models import TareoImportacion

    if request.method == 'POST':
        archivo = request.FILES.get('archivo_excel')
        tipo_import = request.POST.get('tipo_import', 'RELOJ')
        dry_run = request.POST.get('dry_run') == '1'
        force = request.POST.get('force') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo Excel.')
            return redirect('tareo_importar')

        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser formato Excel (.xlsx o .xls).')
            return redirect('tareo_importar')

        suffix = '.xlsx' if archivo.name.lower().endswith('.xlsx') else '.xls'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            out = StringIO()
            kwargs = {'archivo': tmp_path, 'stdout': out, 'stderr': out}
            if dry_run:
                kwargs['dry_run'] = True
            if force:
                kwargs['force'] = True

            call_command('importar_tareo_excel', **kwargs)
            output = out.getvalue()

            if dry_run:
                messages.info(request, f'[DRY-RUN] Simulación completada. Revisa los logs del servidor para detalles.')
            else:
                messages.success(request, 'Importación completada correctamente.')

        except Exception as e:
            messages.error(request, f'Error durante la importación: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('tareo_dashboard')

    # GET — mostrar formulario
    ultimas = TareoImportacion.objects.order_by('-creado_en')[:5]
    context = {
        'titulo': 'Importar Tareo Excel',
        'ultimas_imports': ultimas,
    }
    return render(request, 'tareo/importar.html', context)


# ---------------------------------------------------------------------------
# PARÁMETROS / CONFIGURACIÓN
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def parametros_view(request):
    """Vista de parámetros y configuración del módulo Tareo."""
    from tareo.models import (
        FeriadoCalendario, HomologacionCodigo,
        RegimenTurno, TipoHorario,
    )

    context = {
        'titulo': 'Parámetros del Módulo Tareo',
        'regimenes': RegimenTurno.objects.all().order_by('nombre'),
        'horarios': TipoHorario.objects.all().order_by('nombre'),
        'feriados': FeriadoCalendario.objects.all().order_by('fecha'),
        'homologaciones': HomologacionCodigo.objects.all().order_by('prioridad', 'codigo_origen'),
    }
    return render(request, 'tareo/parametros.html', context)


# ---------------------------------------------------------------------------
# AJAX ENDPOINTS
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def ajax_staff_data(request):
    """JSON con datos STAFF para la matriz."""
    from tareo.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        return JsonResponse({'error': 'Sin importación activa'}, status=404)

    data = list(
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='STAFF')
        .values('dni', 'nombre_archivo', 'fecha', 'codigo_dia',
                'horas_marcadas', 'he_25', 'he_35', 'he_100')
        .order_by('nombre_archivo', 'fecha')
    )

    for row in data:
        row['fecha'] = row['fecha'].isoformat()
        row['horas_marcadas'] = float(row['horas_marcadas'] or 0)
        row['he_25'] = float(row['he_25'])
        row['he_35'] = float(row['he_35'])
        row['he_100'] = float(row['he_100'])

    return JsonResponse({
        'importacion': str(importacion),
        'total': len(data),
        'data': data,
    })


@login_required
@solo_admin
def ajax_rco_data(request):
    """JSON con resumen HE por persona para personal RCO."""
    from tareo.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        return JsonResponse({'error': 'Sin importación activa'}, status=404)

    data = list(
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='RCO')
        .values('dni', 'nombre_archivo')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
        )
        .order_by('nombre_archivo')
    )

    for row in data:
        row['total_he_25'] = float(row['total_he_25'] or 0)
        row['total_he_35'] = float(row['total_he_35'] or 0)
        row['total_he_100'] = float(row['total_he_100'] or 0)
        row['total_horas'] = float(row['total_horas'] or 0)
        row['total_he'] = row['total_he_25'] + row['total_he_35'] + row['total_he_100']

    return JsonResponse({'total': len(data), 'data': data})


@login_required
@solo_admin
def ajax_importaciones(request):
    """JSON lista de importaciones completadas."""
    from tareo.models import TareoImportacion

    tipo = request.GET.get('tipo', 'RELOJ')
    imports = list(
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')
        .values('id', 'tipo', 'estado', 'periodo_inicio', 'periodo_fin',
                'total_registros', 'registros_error', 'creado_en')[:30]
    )

    for row in imports:
        row['periodo_inicio'] = row['periodo_inicio'].isoformat() if row['periodo_inicio'] else None
        row['periodo_fin'] = row['periodo_fin'].isoformat() if row['periodo_fin'] else None
        row['creado_en'] = row['creado_en'].strftime('%d/%m/%Y %H:%M')

    return JsonResponse({'tipo': tipo, 'total': len(imports), 'data': imports})
