"""
views_cese.py — Vistas para el flujo de cese de trabajadores.

Digitaliza el flujo de la macro Excel (Módulo2 + Módulo3):
  - pdf_cese_panel    → panel unificado de documentos de cese
  - pdf_cese_upload   → upload masivo de PDFs (Bajas SUNAT + BLIQ S10)
  - pdf_cese_procesar → AJAX: procesa un PDF → retorna datos + empleado encontrado
  - pdf_cese_confirmar → guarda DocumentoTrabajador definitivo tras revisión
"""
import json
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST, require_http_methods

from documentos.models import (
    CategoriaDocumento, TipoDocumento, DocumentoTrabajador,
)
from documentos.services_pdf import buscar_empleado_por_pdf, procesar_pdf_cese

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')

# ── Constantes ──────────────────────────────────────────────────────────────

_CAT_CESE_NOMBRE = 'Cese y Liquidación'
_TIPO_BAJA_NOMBRE = 'Baja SUNAT (T-Registro)'
_TIPO_BLIQ_NOMBRE = 'Boleta de Liquidación S10'
_TIPO_CERT_TRABAJO = 'Certificado de Trabajo'
_TIPO_CERT_5TA = 'Certificado de 5ta Categoría'

_TIPO_MAP = {
    'BAJA_SUNAT':  _TIPO_BAJA_NOMBRE,
    'BLIQ':        _TIPO_BLIQ_NOMBRE,
    'DESCONOCIDO': _TIPO_BAJA_NOMBRE,  # default
}

_MAX_MB = 10  # límite por PDF


def _get_o_crear_categoria_cese() -> CategoriaDocumento:
    cat, _ = CategoriaDocumento.objects.get_or_create(
        nombre=_CAT_CESE_NOMBRE,
        defaults={'orden': 99, 'activa': True, 'icono': 'fas fa-user-slash'},
    )
    return cat


def _get_o_crear_tipo(nombre: str, categoria: CategoriaDocumento) -> TipoDocumento:
    tipo, _ = TipoDocumento.objects.get_or_create(
        nombre=nombre,
        defaults={
            'categoria': categoria,
            'descripcion': f'Documento de cese: {nombre}',
            'obligatorio': False,
            'vence': False,
        },
    )
    return tipo


# ── Panel principal de cese ──────────────────────────────────────────────────

@login_required
@solo_admin
def pdf_cese_panel(request):
    """Panel de cese: acceso rápido a upload PDFs y listado de documentos de cese."""
    cat = CategoriaDocumento.objects.filter(nombre=_CAT_CESE_NOMBRE).first()
    docs_recientes = []
    if cat:
        tipo_ids = TipoDocumento.objects.filter(categoria=cat).values_list('id', flat=True)
        docs_recientes = (
            DocumentoTrabajador.objects
            .filter(tipo__in=tipo_ids)
            .select_related('personal', 'tipo', 'subido_por')
            .order_by('-creado_en')[:50]
        )

    return render(request, 'documentos/pdf_cese_panel.html', {
        'docs_recientes': docs_recientes,
        'cat': cat,
    })


# ── Upload masivo de PDFs ────────────────────────────────────────────────────

@login_required
@solo_admin
def pdf_cese_upload(request):
    """
    GET:  Muestra formulario drag-drop de upload masivo.
    POST: Procesa los archivos subidos (con AJAX desde JS).
    """
    return render(request, 'documentos/pdf_cese_upload.html', {
        'max_mb': _MAX_MB,
    })


@login_required
@solo_admin
@require_POST
def pdf_cese_procesar(request):
    """
    AJAX endpoint: recibe UN PDF, extrae DNI/nombre, busca empleado.
    Retorna JSON con datos del PDF y match del empleado (si encontró).

    No guarda nada todavía — solo análisis.
    """
    archivo = request.FILES.get('pdf')
    if not archivo:
        return JsonResponse({'error': 'No se recibió archivo.'}, status=400)

    if archivo.size > _MAX_MB * 1024 * 1024:
        return JsonResponse({'error': f'Archivo demasiado grande (máx {_MAX_MB} MB).'}, status=400)

    filename = archivo.name
    personal, resultado = buscar_empleado_por_pdf(archivo, filename)

    resp = {
        'filename':  filename,
        'tipo_doc':  resultado['tipo_doc'],
        'dni':       resultado['dni'],
        'nombre_pdf': resultado['nombre'],
        'error':     resultado['error'],
        'empleado':  None,
    }

    if personal:
        resp['empleado'] = {
            'pk':           personal.pk,
            'nro_doc':      personal.nro_doc,
            'nombre':       personal.apellidos_nombres,
            'cargo':        personal.cargo,
            'area':         str(personal.subarea.area) if personal.subarea else '',
            'estado':       personal.estado,
            'fecha_cese':   personal.fecha_cese.isoformat() if personal.fecha_cese else None,
        }

    return JsonResponse(resp)


@login_required
@solo_admin
@require_POST
def pdf_cese_confirmar(request):
    """
    AJAX endpoint: confirma y guarda los PDFs ya procesados como DocumentoTrabajador.
    Recibe JSON en body: lista de {personal_pk, tipo_doc, filename, file_content_b64}.
    O bien recibe multipart con file + personal_pk + tipo_doc.
    """
    personal_pk = request.POST.get('personal_pk')
    tipo_doc    = request.POST.get('tipo_doc', 'BAJA_SUNAT')
    archivo     = request.FILES.get('pdf')

    if not personal_pk or not archivo:
        return JsonResponse({'error': 'Faltan datos: personal_pk o pdf.'}, status=400)

    from personal.models import Personal
    personal = get_object_or_404(Personal, pk=personal_pk)

    # Obtener o crear categoría y tipo
    cat  = _get_o_crear_categoria_cese()
    tipo = _get_o_crear_tipo(_TIPO_MAP.get(tipo_doc, _TIPO_BAJA_NOMBRE), cat)

    # Guardar documento
    doc = DocumentoTrabajador(
        personal=personal,
        tipo=tipo,
        nombre_archivo=(archivo.name or '')[:255],
        archivo=archivo,
        estado='VIGENTE',
        subido_por=request.user,
        notas=f'Cargado via PDF Cese. Tipo detectado: {tipo_doc}',
    )
    doc.save()

    return JsonResponse({
        'success':  True,
        'doc_pk':   doc.pk,
        'personal': personal.apellidos_nombres,
        'tipo':     tipo.nombre,
        'legajo_url': f'/documentos/legajo/{personal.pk}/',
    })
