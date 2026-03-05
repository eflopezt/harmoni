"""
Vistas del módulo Tareo — Importaciones.
"""
import logging
import os
import tempfile
from datetime import date
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render

from asistencia.views._common import solo_admin

logger = logging.getLogger('personal.business')


# ---------------------------------------------------------------------------
# IMPORTAR (upload web)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_view(request):
    """Hub de importaciones y formulario inline para Reloj Excel."""
    from asistencia.models import ConfiguracionSistema, TareoImportacion
    from personal.models import Personal

    if request.method == 'POST':
        archivo = request.FILES.get('archivo_excel')
        dry_run = request.POST.get('dry_run') == '1'
        force   = request.POST.get('force') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo Excel.')
            return redirect('asistencia_importar')

        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser formato Excel (.xlsx o .xls).')
            return redirect('asistencia_importar')

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

            if dry_run:
                messages.info(request, '[DRY-RUN] Simulación completada. Sin cambios guardados.')
            else:
                messages.success(request, 'Importación Reloj completada correctamente.')

        except Exception as e:
            messages.error(request, f'Error durante la importación: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('asistencia_importar')

    # GET — Hub: estadísticas de importadores
    config = ConfiguracionSistema.get()
    ia_provider   = getattr(config, 'ia_provider', 'NINGUNO')
    ia_modelo     = getattr(config, 'ia_modelo', '') or ''
    ia_endpoint   = getattr(config, 'ia_endpoint', '') or ''
    ia_disponible = False
    if ia_provider != 'NINGUNO':
        try:
            from asistencia.services.ai_service import get_service
            svc = get_service()
            ia_disponible = svc.test_connection()['ok'] if svc else False
        except Exception:
            pass

    def _last(tipo):
        return TareoImportacion.objects.filter(tipo=tipo).order_by('-creado_en').first()

    total_activos = Personal.objects.filter(estado='Activo')
    context = {
        'titulo':        'Hub de Importaciones',
        'ultimas_imports': TareoImportacion.objects.select_related('usuario').order_by('-creado_en')[:20],
        'stats_synkro':  _last('RELOJ'),
        'stats_sunat':   _last('SUNAT'),
        'stats_s10':     _last('S10'),
        'total_staff':   total_activos.filter(grupo_tareo='STAFF').count(),
        'total_rco':     total_activos.filter(grupo_tareo='RCO').count(),
        'ia_disponible': ia_disponible,
    }
    return render(request, 'asistencia/importar.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR SYNKRO (Reloj + Papeletas combinado)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_synkro_view(request):
    """
    Importa archivo de asistencia con deteccion automatica de formato.

    Formatos soportados:
      - WIDE:          DNI + columnas-fecha (formato Synkro / matrices de reloj)
      - TRANSACCIONAL: DNI + Fecha + Ingreso + Salida (una fila por persona-dia)
      - PAPELETAS:     TipoPermiso + DNI + FechaInicio + FechaFin
    """
    from asistencia.models import ConfiguracionSistema, TareoImportacion
    from asistencia.services.flexible_importer import (
        FlexibleAttendanceParser,
        FORMAT_WIDE, FORMAT_TRANSACCIONAL, FORMAT_PAPELETAS,
    )
    from asistencia.services.processor import TareoProcessor

    config = ConfiguracionSistema.get()

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        periodo_fin = request.POST.get('periodo_fin')
        grupo_default = request.POST.get('grupo_default', 'STAFF')
        dry_run = request.POST.get('dry_run') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo.')
            return redirect('asistencia_importar_synkro')

        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser formato Excel (.xlsx o .xls).')
            return redirect('asistencia_importar_synkro')

        suffix = '.xlsx' if archivo.name.lower().endswith('.xlsx') else '.xls'
        tmp_path = None
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from datetime import datetime as dt
            p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else None
            p_fin = dt.strptime(periodo_fin, '%Y-%m-%d').date() if periodo_fin else None

            parser    = FlexibleAttendanceParser(tmp_path, config)
            resultado = parser.parse_todo()

            hojas     = parser.hojas_disponibles()
            registros = resultado['registros']
            papeletas = resultado['papeletas']
            fechas    = resultado['fechas']
            hojas_fmt = resultado['hojas']

            # ── Validación 1: Apertura del sistema ─────────────
            # Si el cliente tiene fecha_apertura configurada, advertir si el
            # archivo contiene datos anteriores a esa fecha.
            fecha_apertura = getattr(config, 'fecha_apertura', None)
            if fecha_apertura and fechas:
                fechas_previas = [f for f in fechas if f < fecha_apertura]
                if fechas_previas:
                    resultado['advertencias'].append(
                        f'El archivo contiene {len(fechas_previas)} fecha(s) anteriores '
                        f'a la apertura del sistema ({fecha_apertura.strftime("%d/%m/%Y")}): '
                        f'{fechas_previas[0]} … {fechas_previas[-1]}. '
                        f'Esos registros se importarán igualmente (sin bloqueo), '
                        f'pero verifica si es correcto.'
                    )

            # ── Validación 2: Empleados cesados ────────────────
            # Detecta DNIs del archivo que existen en la BD pero tienen fecha_cese.
            # No bloquea la importación (datos históricos son válidos), pero informa.
            if registros or papeletas:
                from personal.models import Personal
                dnis_archivo = (
                    {r['dni'] for r in registros}
                    | {p['dni'] for p in papeletas}
                )
                # Buscar también variantes con/sin zero-padding
                dnis_exp = set(dnis_archivo)
                for d in dnis_archivo:
                    if d.isdigit():
                        if len(d) == 7:
                            dnis_exp.add(d.zfill(8))
                        elif len(d) == 8 and d.startswith('0'):
                            dnis_exp.add(d.lstrip('0'))
                cesados = Personal.objects.filter(
                    nro_doc__in=dnis_exp,
                    fecha_cese__isnull=False,
                ).values_list('nro_doc', 'nombres', 'apellidos', 'fecha_cese')
                if cesados:
                    n = len(cesados)
                    ejemplos = '; '.join(
                        f'{ap} {nm} (cese: {fc.strftime("%d/%m/%Y")})'
                        for _, nm, ap, fc in list(cesados)[:3]
                    )
                    resultado['advertencias'].append(
                        f'{n} empleado(s) del archivo tienen cese registrado: {ejemplos}'
                        + (' …' if n > 3 else '') +
                        '. Sus registros históricos se importarán correctamente.'
                    )

            # Resumen de formatos detectados
            fmt_resumen = ', '.join(
                f'"{h}": {f}' for h, f in hojas_fmt.items()
            )

            # Contar por tipo de formato para el mensaje
            n_wide   = sum(1 for f in hojas_fmt.values() if f == FORMAT_WIDE)
            n_trans  = sum(1 for f in hojas_fmt.values() if f == FORMAT_TRANSACCIONAL)
            n_pap    = sum(1 for f in hojas_fmt.values() if f == FORMAT_PAPELETAS)

            if dry_run:
                partes = []
                if registros:
                    partes.append(f'{len(registros)} registros de asistencia')
                if papeletas:
                    partes.append(f'{len(papeletas)} papeletas/permisos')
                if fechas:
                    partes.append(f'{len(fechas)} fechas ({fechas[0]} - {fechas[-1]})')
                fmt_info = []
                if n_wide:
                    fmt_info.append(f'{n_wide} hoja(s) WIDE')
                if n_trans:
                    fmt_info.append(f'{n_trans} hoja(s) TRANSACCIONAL')
                if n_pap:
                    fmt_info.append(f'{n_pap} hoja(s) PAPELETAS')
                msg = (
                    f'[DRY-RUN] {" | ".join(partes) or "Sin datos validos"}. '
                    f'Formato: {", ".join(fmt_info) or "No reconocido"}.'
                )
                if resultado['errores']:
                    msg += f' Errores: {"; ".join(resultado["errores"][:3])}'
                messages.info(request, msg)
                return redirect('asistencia_importar_synkro')

            if not registros and not papeletas:
                errs = '; '.join(resultado['errores'][:3])
                messages.error(
                    request,
                    f'No se encontraron datos validos en el archivo. {errs}'
                )
                return redirect('asistencia_importar_synkro')

            # Determinar periodo del archivo
            fecha_ini_archivo = p_ini or (fechas[0] if fechas else date.today())
            fecha_fin_archivo = p_fin or (fechas[-1] if fechas else date.today())

            # Crear registro de importacion
            importacion = TareoImportacion.objects.create(
                tipo='RELOJ',
                periodo_inicio=fecha_ini_archivo,
                periodo_fin=fecha_fin_archivo,
                archivo_nombre=archivo.name,
                estado='PROCESANDO',
                usuario=request.user,
                metadata={
                    'hojas':   hojas,
                    'archivo': archivo.name,
                    'formatos': hojas_fmt,
                    'n_wide':   n_wide,
                    'n_trans':  n_trans,
                    'n_pap':    n_pap,
                },
            )

            proc = TareoProcessor(importacion, config)
            res_proc = proc.procesar(
                registros,
                papeletas,
                grupo_default=grupo_default,
            )

            # Guardar advertencias de parseo
            todas_adv = resultado['advertencias'] + resultado['errores']
            if todas_adv:
                importacion.advertencias = (importacion.advertencias or []) + todas_adv
                importacion.save(update_fields=['advertencias'])

            fmt_str = ', '.join(set(hojas_fmt.values()))
            msg = (
                f'Importacion completada ({fmt_str}): '
                f'{res_proc["creados"]} nuevos, '
                f'{res_proc["actualizados"]} actualizados, '
                f'{res_proc["sin_match"]} sin match en BD.'
            )
            if papeletas:
                msg += f' Papeletas: {len(papeletas)}.'
            if res_proc.get('errores'):
                messages.warning(request, msg)
            else:
                messages.success(request, msg)

        except Exception as e:
            import traceback
            logger.error('importar_synkro_view error: %s\n%s', e, traceback.format_exc())
            messages.error(request, f'Error durante la importacion: {e}')
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        return redirect('asistencia_dashboard')

    # GET
    context = {
        'titulo':  'Importador Flexible de Asistencia',
        'config':  config,
        'ultimas': TareoImportacion.objects.order_by('-creado_en')[:5],
    }
    return render(request, 'asistencia/importar_synkro.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR SUNAT TR5
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_sunat_view(request):
    """Importa el archivo TR5 de SUNAT T-Registro."""
    from asistencia.models import TareoImportacion
    from asistencia.services.sunat_importer import importar_tr5

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        actualizar_personal = request.POST.get('actualizar_personal') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar el archivo TR5.')
            return redirect('asistencia_importar_sunat')

        from datetime import datetime as dt
        p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else date.today()

        suffix = '.txt' if archivo.name.lower().endswith('.txt') else ''
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        importacion = TareoImportacion.objects.create(
            tipo='SUNAT',
            periodo_inicio=p_ini,
            periodo_fin=p_ini,
            archivo_nombre=archivo.name,
            estado='PROCESANDO',
            usuario=request.user,
        )

        try:
            resultado = importar_tr5(tmp_path, importacion,
                                     actualizar_personal=actualizar_personal)
            messages.success(
                request,
                f'TR5 importado: {resultado["creados"]} trabajadores, '
                f'{resultado["sin_match"]} sin match en BD.')
        except Exception as e:
            importacion.estado = 'FALLIDO'
            importacion.save()
            messages.error(request, f'Error: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('asistencia_dashboard')

    context = {
        'titulo': 'Importar SUNAT TR5',
        'ultimas': TareoImportacion.objects.filter(tipo='SUNAT').order_by('-creado_en')[:5],
    }
    return render(request, 'asistencia/importar_sunat.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR S10
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_s10_view(request):
    """Importa el reporte de personal del sistema S10."""
    from asistencia.models import ConfiguracionSistema, TareoImportacion
    from asistencia.services.s10_importer import importar_s10
    from asistencia.services.ai_service import get_service

    config = ConfiguracionSistema.get()
    ia_provider  = getattr(config, 'ia_provider', 'NINGUNO')
    ia_modelo    = getattr(config, 'ia_modelo', '') or ''

    # Verificar conectividad con el provider configurado
    ia_disponible = False
    if ia_provider != 'NINGUNO':
        try:
            svc = get_service()
            ia_disponible = svc.test_connection()['ok'] if svc else False
        except Exception:
            pass

    resultado_post = None  # resultado del import previo en esta sesión

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        actualizar_personal = request.POST.get('actualizar_personal') == '1'
        usar_ia = request.POST.get('usar_ia') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar el archivo S10.')
        else:
            from datetime import datetime as dt
            p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else date.today()

            suffix = '.xlsx'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                for chunk in archivo.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name

            importacion = TareoImportacion.objects.create(
                tipo='S10',
                periodo_inicio=p_ini,
                periodo_fin=p_ini,
                archivo_nombre=archivo.name,
                estado='PROCESANDO',
                usuario=request.user,
            )

            try:
                resultado_post = importar_s10(
                    tmp_path, importacion,
                    actualizar_personal=actualizar_personal,
                    usar_ia=usar_ia,
                )
                msg = (f'S10 importado: {resultado_post["creados"]} registros, '
                       f'{resultado_post["sin_match"]} sin match.')
                if resultado_post.get('advertencias'):
                    msg += f' {len(resultado_post["advertencias"])} advertencias.'
                messages.success(request, msg)
            except Exception as e:
                importacion.estado = 'FALLIDO'
                importacion.save()
                messages.error(request, f'Error: {e}')
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    context = {
        'titulo':        'Importar Reporte S10',
        'ultimas':       TareoImportacion.objects.filter(tipo='S10').order_by('-creado_en')[:5],
        'ia_disponible': ia_disponible,
        'ia_modelo':     ia_modelo,
        'resultado':     resultado_post,
    }
    return render(request, 'asistencia/importar_s10.html', context)


# ---------------------------------------------------------------------------
# AJAX IMPORTACIONES
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def ajax_importaciones(request):
    """JSON lista de importaciones completadas."""
    from asistencia.models import TareoImportacion

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
