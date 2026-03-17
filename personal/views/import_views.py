"""
Vistas para importación masiva de personal desde Excel.

Flujo:
1. upload   — subir archivo, validar, guardar en sesión, redirigir a preview
2. preview  — mostrar datos parseados con errores resaltados
3. confirm  — ejecutar importación real después de aprobación
4. template — descargar plantilla Excel vacía
5. validate — endpoint AJAX para validación en tiempo real
"""
import json
import logging
import tempfile
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from personal.services.import_service import PersonalImportService
from ..permissions import get_context_usuario

logger = logging.getLogger('personal')


def _get_empresa_actual(request):
    """Obtiene la empresa actual de la sesión."""
    from empresas.models import Empresa
    empresa_id = request.session.get('empresa_actual_id')
    if empresa_id:
        try:
            return Empresa.objects.get(pk=empresa_id)
        except Empresa.DoesNotExist:
            pass
    # Fallback a empresa principal
    return Empresa.objects.filter(es_principal=True).first()


@login_required
def import_upload(request):
    """
    Paso 1: Subir archivo Excel y mostrar preview con validación.
    GET  — muestra formulario de upload con drag-and-drop
    POST — valida archivo y redirige a preview
    """
    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo Excel.')
            return redirect('personal_import_upload')

        # Validar extensión
        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'Solo se aceptan archivos .xlsx o .xls')
            return redirect('personal_import_upload')

        # Validar tamaño (max 10MB)
        if archivo.size > 10 * 1024 * 1024:
            messages.error(request, 'El archivo no debe superar 10 MB.')
            return redirect('personal_import_upload')

        service = PersonalImportService()
        result = service.validate_excel(archivo)

        # Guardar archivo temporalmente para importar después
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix='.xlsx', prefix='harmoni_import_'
        )
        archivo.seek(0)
        for chunk in archivo.chunks():
            tmp.write(chunk)
        tmp.close()

        # Guardar path en sesión
        request.session['import_temp_file'] = tmp.name
        request.session['import_filename'] = archivo.name
        request.session['import_stats'] = result['stats']

        context = {
            'result': result,
            'filename': archivo.name,
            'stats': result['stats'],
        }
        context.update(get_context_usuario(request.user))
        return render(request, 'personal/import/preview.html', context)

    context = {}
    context.update(get_context_usuario(request.user))
    return render(request, 'personal/import/upload.html', context)


@login_required
@require_POST
def import_confirm(request):
    """
    Paso 2: Ejecutar la importación real después de que el usuario aprueba el preview.
    """
    temp_file = request.session.get('import_temp_file')
    filename = request.session.get('import_filename', 'archivo.xlsx')

    if not temp_file or not os.path.exists(temp_file):
        messages.error(request, 'Sesión expirada. Suba el archivo nuevamente.')
        return redirect('personal_import_upload')

    try:
        empresa = _get_empresa_actual(request)
        service = PersonalImportService()

        with open(temp_file, 'rb') as f:
            result = service.import_excel(f, empresa, request.user)

        # Limpiar sesión y archivo temporal
        try:
            os.unlink(temp_file)
        except OSError:
            pass
        request.session.pop('import_temp_file', None)
        request.session.pop('import_filename', None)
        request.session.pop('import_stats', None)

        # Log de auditoría
        if result['created'] > 0 or result['updated'] > 0:
            try:
                from core.models import AuditLog
                AuditLog.objects.create(
                    usuario=request.user,
                    accion='IMPORT',
                    modelo='Personal',
                    descripcion=(
                        f'Importación masiva desde "{filename}": '
                        f'{result["created"]} creados, {result["updated"]} actualizados, '
                        f'{len(result["errors"])} errores'
                    ),
                )
            except Exception:
                pass

        context = {
            'result': result,
            'filename': filename,
        }
        context.update(get_context_usuario(request.user))
        return render(request, 'personal/import/result.html', context)

    except Exception as e:
        logger.exception('Error en importación masiva de personal')
        messages.error(request, f'Error durante la importación: {str(e)}')
        return redirect('personal_import_upload')


@login_required
def import_template_download(request):
    """Descargar plantilla Excel vacía con instrucciones y validaciones."""
    service = PersonalImportService()
    content = service.generate_template()

    response = HttpResponse(
        content,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=plantilla_importacion_personal.xlsx'
    return response


@login_required
def import_validate_ajax(request):
    """
    Endpoint AJAX: validar archivo Excel sin importar.
    Retorna JSON con estadísticas y errores.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    archivo = request.FILES.get('archivo')
    if not archivo:
        return JsonResponse({'error': 'No se recibió archivo'}, status=400)

    if not archivo.name.lower().endswith(('.xlsx', '.xls')):
        return JsonResponse({'error': 'Solo se aceptan archivos .xlsx o .xls'}, status=400)

    service = PersonalImportService()
    result = service.validate_excel(archivo)

    # Simplificar preview para JSON (limitar a 50 filas)
    preview_rows = []
    for row in result['preview'][:50]:
        preview_rows.append({
            'row_num': row['row_num'],
            'nro_doc': row['nro_doc'],
            'apellidos_nombres': row['apellidos_nombres'],
            'cargo': row['cargo'],
            'is_update': row['is_update'],
            'errors': row['errors'],
            'warnings': row['warnings'],
        })

    return JsonResponse({
        'valid': result['valid'],
        'stats': result['stats'],
        'errors': result['errors'][:20],
        'warnings': result['warnings'][:20],
        'preview': preview_rows,
        'headers': result['headers'],
    })
