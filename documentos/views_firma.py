"""
Documentos -- Vistas de Firma Digital (ZapSign).
"""
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DocumentoFirmaDigital

# RBAC (WS1): staff con mod_documentos (staff sin perfil conserva acceso, compat).
from core.permisos import requiere_modulo_o_staff
solo_admin = requiere_modulo_o_staff('documentos')
@login_required
@solo_admin
def firma_panel(request):
    """Panel principal de firma digital."""
    docs = DocumentoFirmaDigital.objects.select_related(
        "personal", "enviado_por"
    ).order_by("-creado_en")

    estado = request.GET.get("estado", "")
    q      = request.GET.get("q", "")
    if estado:
        docs = docs.filter(estado=estado)
    if q:
        docs = docs.filter(personal__apellidos_nombres__icontains=q)

    from django.db.models import Count, Q
    stats = DocumentoFirmaDigital.objects.aggregate(
        total=Count("id"),
        pendientes=Count("id", filter=Q(estado__in=["PENDIENTE", "ENVIADO", "FIRMANDO"])),
        firmados=Count("id", filter=Q(estado="FIRMADO")),
        errores=Count("id", filter=Q(estado__in=["ERROR", "RECHAZADO", "VENCIDO"])),
    )

    zapsign_activo = False
    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.objects.first()
        zapsign_activo = bool(cfg and cfg.zapsign_api_key)
    except Exception:
        pass

    return render(request, "documentos/firma_panel.html", {
        "titulo": "Firma Digital",
        "docs": docs,
        "stats": stats,
        "estado_filtro": estado,
        "q": q,
        "estado_choices": DocumentoFirmaDigital.ESTADO_CHOICES,
        "zapsign_activo": zapsign_activo,
        "today": date.today(),
    })


@login_required
@solo_admin
def firma_crear(request):
    """Crear nuevo documento para firma."""
    from personal.models import Personal

    if request.method == "POST":
        personal_id  = request.POST.get("personal_id")
        nombre       = request.POST.get("nombre", "").strip()
        tipo         = request.POST.get("tipo", "OTRO")
        descripcion  = request.POST.get("descripcion", "").strip()
        archivo      = request.FILES.get("archivo_pdf")
        try:
            dias_exp = int(request.POST.get("dias_expiracion", 30))
        except (ValueError, TypeError):
            dias_exp = 30

        if not personal_id or not nombre or not archivo:
            messages.error(request, "Trabajador, nombre y archivo PDF son requeridos.")
            return redirect("firma_crear")

        personal = get_object_or_404(Personal, pk=personal_id)

        doc = DocumentoFirmaDigital.objects.create(
            personal=personal,
            nombre=nombre,
            tipo=tipo,
            descripcion=descripcion,
            archivo_pdf=archivo,
            vence_en=date.today() + timedelta(days=dias_exp),
            enviado_por=request.user,
        )

        enviar = request.POST.get("enviar_ahora") == "1"
        if enviar:
            return _do_enviar(request, doc)

        messages.success(request, f"Documento creado. Ahora puedes enviarlo a ZapSign.")
        return redirect("firma_panel")

    personal_qs = Personal.objects.filter(estado="Activo").order_by("apellidos_nombres")
    return render(request, "documentos/firma_form.html", {
        "titulo": "Nuevo documento para firma",
        "personal_list": personal_qs,
        "tipo_choices": DocumentoFirmaDigital.TIPO_CHOICES,
    })


def _do_enviar(request, doc):
    """Logica de envio a ZapSign."""
    from .services_firma import crear_documento_firma

    personal = doc.personal
    firmante_email = (
        getattr(personal, "correo_corporativo", "") or
        getattr(personal, "correo_personal", "") or
        ""
    )
    if not firmante_email:
        messages.error(
            request,
            "El trabajador no tiene correo registrado. Agregue un correo antes de enviar."
        )
        return redirect("firma_panel")

    base_url = request.build_absolute_uri("/").rstrip("/")
    pdf_url  = f"{base_url}{doc.archivo_pdf.url}"
    firmantes = [{"name": personal.apellidos_nombres, "email": firmante_email}]
    dias_exp  = max((doc.vence_en - date.today()).days, 1) if doc.vence_en else 30

    try:
        resultado = crear_documento_firma(doc.nombre, pdf_url, firmantes, dias_exp)
        doc.zapsign_token   = resultado.get("token", "")
        doc.zapsign_doc_url = resultado.get("open_id", "")
        doc.estado          = "ENVIADO"
        doc.enviado_en      = timezone.now()
        signers = resultado.get("signers", [])
        if signers:
            doc.signer_token = signers[0].get("token", "")
            doc.signer_url   = signers[0].get("sign_url", "")
        doc.save()
        messages.success(request, "Documento enviado a ZapSign. El trabajador recibira un email para firmar.")
    except Exception as e:
        doc.estado        = "ERROR"
        doc.error_detalle = str(e)
        doc.save()
        messages.error(request, f"Error enviando a ZapSign: {e}")

    return redirect("firma_panel")


@login_required
@solo_admin
@require_POST
def firma_enviar(request, pk):
    """Envia el documento a ZapSign para firma."""
    doc = get_object_or_404(DocumentoFirmaDigital, pk=pk)
    if doc.estado not in ("PENDIENTE", "ERROR"):
        messages.warning(request, f"El documento ya esta en estado: {doc.get_estado_display()}")
        return redirect("firma_panel")
    return _do_enviar(request, doc)


@login_required
@solo_admin
@require_POST
def firma_sincronizar(request, pk):
    """Consulta ZapSign y actualiza el estado del documento."""
    from .services_firma import sincronizar_estado
    doc = get_object_or_404(DocumentoFirmaDigital, pk=pk)
    changed = sincronizar_estado(doc)
    if changed:
        messages.success(request, f"Estado actualizado: {doc.get_estado_display()}")
    else:
        messages.info(request, "Sin cambios de estado.")
    return redirect("firma_panel")


@login_required
@solo_admin
@require_POST
def firma_cancelar(request, pk):
    """Cancela el documento en ZapSign y localmente."""
    from .services_firma import cancelar_documento
    doc = get_object_or_404(DocumentoFirmaDigital, pk=pk)
    if doc.zapsign_token:
        try:
            cancelar_documento(doc.zapsign_token)
        except Exception as e:
            messages.warning(request, f"ZapSign: {e}")
    doc.estado = "CANCELADO"
    doc.save()
    messages.success(request, "Documento cancelado.")
    return redirect("firma_panel")


@login_required
@solo_admin
def firma_sincronizar_todos(request):
    """Sincroniza todos los documentos en estado activo."""
    from .services_firma import sincronizar_estado
    docs = DocumentoFirmaDigital.objects.filter(estado__in=["ENVIADO", "FIRMANDO"])
    total = docs.count()
    actualizados = sum(1 for doc in docs if sincronizar_estado(doc))
    messages.success(
        request,
        f"Sincronizacion completada: {actualizados} documentos actualizados de {total} revisados."
    )
    return redirect("firma_panel")
