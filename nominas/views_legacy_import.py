"""
Vista web para subir archivo legacy de planilla y procesarlo sin SSH.

Pensado para que el cliente o el staff de soporte pueda hacer la migración
histórica desde el browser, viendo el cuadre y los errores en pantalla.
"""
from __future__ import annotations

import os
import tempfile
from io import StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.management import call_command
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods


def _es_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@login_required
@require_http_methods(["GET", "POST"])
def importar_legacy(request):
    """Sube un Excel/CSV y procesa la migración con el comando management.

    GET:  muestra el formulario.
    POST: procesa con --dry-run primero, muestra resultados. Si hay un segundo
          submit con flag 'confirmar', persiste sin --dry-run.
    """
    if not _es_admin(request.user):
        messages.error(request, "Solo administradores pueden ejecutar migración legacy.")
        return redirect("nominas_panel")

    from empresas.models import Empresa
    empresas = Empresa.objects.filter(activa=True).order_by("razon_social")

    context = {
        "empresas": empresas,
        "resultado": None,
        "form_data": {},
    }

    if request.method != "POST":
        return render(request, "nominas/importar_legacy.html", context)

    # POST: procesar el archivo
    archivo = request.FILES.get("archivo")
    if not archivo:
        messages.error(request, "Debe seleccionar un archivo Excel o CSV.")
        return render(request, "nominas/importar_legacy.html", context)

    if not archivo.name.lower().endswith((".xlsx", ".xls", ".csv")):
        messages.error(request, "Solo se aceptan archivos .xlsx, .xls o .csv.")
        return render(request, "nominas/importar_legacy.html", context)

    # Guardar archivo a temp para que el management command lo lea
    suffix = os.path.splitext(archivo.name)[1] or ".xlsx"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in archivo.chunks():
            tmp.write(chunk)
        tmp_path = tmp.name

    # Parámetros del form
    empresa_id   = request.POST.get("empresa") or None
    tolerancia   = request.POST.get("tolerancia", "1.00")
    confirmar    = request.POST.get("confirmar") == "1"
    dry_run      = not confirmar  # default: dry-run; solo persiste si el usuario confirma

    # Ejecutar el management command capturando stdout
    out = StringIO()
    err = StringIO()
    args = [tmp_path]
    kwargs = {
        "stdout": out,
        "stderr": err,
        "dry_run": dry_run,
        "tolerancia": float(tolerancia),
    }
    if empresa_id:
        try:
            kwargs["empresa"] = int(empresa_id)
        except (ValueError, TypeError):
            pass

    error_critico = None
    try:
        call_command("importar_planilla_legacy", *args, **kwargs)
    except Exception as exc:
        error_critico = str(exc)

    # Cleanup
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    resultado = {
        "stdout":   out.getvalue(),
        "stderr":   err.getvalue(),
        "error":    error_critico,
        "dry_run":  dry_run,
        "confirmado": confirmar,
    }

    if confirmar and not error_critico:
        messages.success(
            request,
            "Migración legacy ejecutada. Revisar el detalle del cuadre antes de cerrar este panel.",
        )
    elif not confirmar and not error_critico:
        messages.info(
            request,
            "Vista previa (dry-run). Si el cuadre es correcto, confirme con el botón verde.",
        )

    context["resultado"]  = resultado
    context["form_data"]  = {
        "empresa_id": empresa_id,
        "tolerancia": tolerancia,
        "filename":   archivo.name,
    }
    return render(request, "nominas/importar_legacy.html", context)
