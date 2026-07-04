"""
Documentos -- Vistas de Firma Digital Interna (Signature Pad).

Flujo:
1. Admin solicita firma -> se genera FirmaDigital con token unico
2. Trabajador accede al link (con o sin login) -> ve documento + pad de firma
3. Trabajador firma -> se guarda imagen + hash SHA-256
4. Cualquiera puede verificar la firma con el hash
5. Se puede descargar PDF con firma embebida
"""
import hashlib
import io
import json
import base64
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import (
    FirmaDigital, ConstanciaGenerada, DocumentoTrabajador,
    DocumentoLaboral,
)

# RBAC (WS1): staff con mod_documentos (staff sin perfil conserva acceso, compat).
from core.permisos import requiere_modulo_o_staff
solo_admin = requiere_modulo_o_staff('documentos')
def _get_client_ip(request):
    """Obtiene la IP real del cliente."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


def _calcular_hash_constancia(constancia):
    """Calcula SHA-256 del contenido de una constancia generada."""
    from django.template import Template, Context

    plantilla = constancia.plantilla
    personal = constancia.personal
    hoy = date.today()
    meses = [
        '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    ]
    hoy_texto = f'{hoy.day:02d} de {meses[hoy.month]} de {hoy.year}'

    # Calcular antiguedad
    antiguedad = ''
    if personal.fecha_ingreso:
        delta = hoy - personal.fecha_ingreso
        years = delta.days // 365
        months = (delta.days % 365) // 30
        parts = []
        if years:
            parts.append(f'{years} año{"s" if years > 1 else ""}')
        if months:
            parts.append(f'{months} mes{"es" if months > 1 else ""}')
        antiguedad = ' y '.join(parts) if parts else 'menos de 1 mes'

    ctx = {
        'personal': personal,
        'hoy': hoy,
        'hoy_texto': hoy_texto,
        'antiguedad': antiguedad,
    }

    try:
        from asistencia.models import ConfiguracionSistema
        cfg = ConfiguracionSistema.objects.first()
        if cfg:
            ctx['empresa'] = cfg
    except Exception:
        pass

    try:
        tpl = Template(plantilla.contenido_html)
        html = tpl.render(Context(ctx))
    except Exception:
        html = plantilla.contenido_html

    return hashlib.sha256(html.encode('utf-8')).hexdigest(), html


def _calcular_hash_archivo(archivo_field):
    """Calcula SHA-256 de un archivo (DocumentoTrabajador, etc.)."""
    try:
        archivo_field.seek(0)
        content = archivo_field.read()
        archivo_field.seek(0)
        return hashlib.sha256(content).hexdigest()
    except Exception:
        return ''


# ═══════════════════════════════════════════════════════════════
# PANEL DE FIRMAS INTERNAS (Admin)
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def firma_interna_panel(request):
    """Panel de firmas digitales internas."""
    from django.db.models import Count, Q

    firmas = FirmaDigital.objects.select_related(
        'firmante', 'solicitado_por', 'constancia', 'documento_trabajador',
    ).order_by('-solicitado_en')

    # Filtros
    estado = request.GET.get('estado', '')
    q = request.GET.get('q', '')
    if estado:
        firmas = firmas.filter(estado=estado)
    if q:
        firmas = firmas.filter(firmante__apellidos_nombres__icontains=q)

    stats = FirmaDigital.objects.aggregate(
        total=Count('id'),
        pendientes=Count('id', filter=Q(estado='PENDIENTE')),
        firmados=Count('id', filter=Q(estado='FIRMADO')),
        rechazados=Count('id', filter=Q(estado__in=['RECHAZADO', 'VENCIDO'])),
    )

    # Auto-vencer firmas expiradas
    vencidas = FirmaDigital.objects.filter(
        estado='PENDIENTE',
        vence_en__lt=date.today(),
    )
    if vencidas.exists():
        vencidas.update(estado='VENCIDO')

    return render(request, 'documentos/firma/panel.html', {
        'titulo': 'Firmas Digitales',
        'firmas': firmas[:100],
        'stats': stats,
        'estado_filtro': estado,
        'q': q,
        'estado_choices': FirmaDigital.ESTADO_CHOICES,
    })


# ═══════════════════════════════════════════════════════════════
# SOLICITAR FIRMA (Admin)
# ═══════════════════════════════════════════════════════════════

@login_required
@solo_admin
def solicitar_firma(request):
    """Formulario para solicitar firma a un trabajador."""
    from personal.models import Personal

    if request.method == 'POST':
        personal_id = request.POST.get('personal_id')
        tipo_doc = request.POST.get('tipo_documento', 'CONSTANCIA')
        constancia_id = request.POST.get('constancia_id')
        documento_id = request.POST.get('documento_id')
        doc_laboral_id = request.POST.get('doc_laboral_id')
        titulo = request.POST.get('titulo', '').strip()
        notas = request.POST.get('notas', '').strip()
        try:
            dias = int(request.POST.get('dias_expiracion', 15))
        except (ValueError, TypeError):
            dias = 15

        if not personal_id or not titulo:
            messages.error(request, 'Trabajador y titulo son requeridos.')
            return redirect('firma_interna_solicitar')

        personal = get_object_or_404(Personal, pk=personal_id)

        # Calcular hash del documento
        hash_doc = ''
        constancia = None
        documento_trabajador = None
        documento_laboral = None

        if tipo_doc == 'CONSTANCIA' and constancia_id:
            constancia = get_object_or_404(ConstanciaGenerada, pk=constancia_id)
            hash_doc, _ = _calcular_hash_constancia(constancia)
        elif tipo_doc == 'DOCUMENTO' and documento_id:
            documento_trabajador = get_object_or_404(DocumentoTrabajador, pk=documento_id)
            if documento_trabajador.archivo:
                hash_doc = _calcular_hash_archivo(documento_trabajador.archivo)
        elif tipo_doc == 'LABORAL' and doc_laboral_id:
            documento_laboral = get_object_or_404(DocumentoLaboral, pk=doc_laboral_id)
            if documento_laboral.archivo:
                hash_doc = _calcular_hash_archivo(documento_laboral.archivo)

        firma = FirmaDigital.objects.create(
            tipo_documento=tipo_doc,
            constancia=constancia,
            documento_trabajador=documento_trabajador,
            documento_laboral=documento_laboral,
            titulo_documento=titulo,
            firmante=personal,
            hash_documento=hash_doc,
            solicitado_por=request.user,
            vence_en=date.today() + timedelta(days=dias),
            notas=notas,
        )

        # Generar URL para compartir
        firma_url = request.build_absolute_uri(f'/documentos/firma/firmar/{firma.token}/')
        messages.success(
            request,
            f'Solicitud de firma creada. Comparta este link con el trabajador: {firma_url}'
        )
        return redirect('firma_interna_panel')

    # GET: mostrar formulario
    personal_qs = Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')
    constancias = ConstanciaGenerada.objects.select_related(
        'plantilla', 'personal',
    ).order_by('-fecha_generacion')[:50]

    return render(request, 'documentos/firma/solicitar.html', {
        'titulo': 'Solicitar Firma Digital',
        'personal_list': personal_qs,
        'constancias': constancias,
        'tipo_choices': FirmaDigital.TIPO_DOCUMENTO_CHOICES,
    })


# ═══════════════════════════════════════════════════════════════
# FIRMAR DOCUMENTO (Trabajador — acceso por token, sin login)
# ═══════════════════════════════════════════════════════════════

def firmar_documento(request, token):
    """
    Pagina de firma: muestra el documento + signature pad.
    Accesible sin login via token unico.
    """
    firma = get_object_or_404(FirmaDigital, token=token)

    # Verificar que no este ya firmado
    if firma.estado == 'FIRMADO':
        return render(request, 'documentos/firma/ya_firmado.html', {
            'firma': firma,
        })

    # Verificar vencimiento
    if firma.esta_vencido:
        firma.estado = 'VENCIDO'
        firma.save(update_fields=['estado'])
        return render(request, 'documentos/firma/vencido.html', {
            'firma': firma,
        })

    # Obtener preview HTML del documento (si es constancia)
    preview_html = ''
    if firma.constancia:
        try:
            _, preview_html = _calcular_hash_constancia(firma.constancia)
        except Exception:
            preview_html = '<p class="text-muted">No se pudo cargar la vista previa del documento.</p>'

    if request.method == 'POST':
        firma_data = request.POST.get('firma_imagen', '')
        if not firma_data:
            # Tambien intentar body JSON
            try:
                body = json.loads(request.body)
                firma_data = body.get('firma_imagen', '')
            except Exception:
                pass

        if not firma_data or not firma_data.startswith('data:image/'):
            messages.error(request, 'Debe dibujar su firma antes de confirmar.')
            return render(request, 'documentos/firma/firmar.html', {
                'firma': firma,
                'preview_html': preview_html,
            })

        # Guardar firma
        firma.firma_imagen = firma_data
        firma.estado = 'FIRMADO'
        firma.firmado_en = timezone.now()
        firma.ip_address = _get_client_ip(request)
        firma.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
        firma.save()

        return render(request, 'documentos/firma/firma_exitosa.html', {
            'firma': firma,
        })

    return render(request, 'documentos/firma/firmar.html', {
        'firma': firma,
        'preview_html': preview_html,
    })


# ═══════════════════════════════════════════════════════════════
# FIRMAR VIA AJAX (retorna JSON)
# ═══════════════════════════════════════════════════════════════

@require_POST
def firmar_ajax(request, token):
    """Endpoint AJAX para guardar firma."""
    firma = get_object_or_404(FirmaDigital, token=token)

    if firma.estado == 'FIRMADO':
        return JsonResponse({'ok': False, 'error': 'Este documento ya fue firmado.'})

    if firma.esta_vencido:
        firma.estado = 'VENCIDO'
        firma.save(update_fields=['estado'])
        return JsonResponse({'ok': False, 'error': 'El link de firma ha vencido.'})

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'ok': False, 'error': 'Datos invalidos.'})

    firma_data = body.get('firma_imagen', '')
    if not firma_data or not firma_data.startswith('data:image/'):
        return JsonResponse({'ok': False, 'error': 'Imagen de firma invalida.'})

    firma.firma_imagen = firma_data
    firma.estado = 'FIRMADO'
    firma.firmado_en = timezone.now()
    firma.ip_address = _get_client_ip(request)
    firma.user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    firma.save()

    return JsonResponse({
        'ok': True,
        'message': 'Documento firmado exitosamente.',
        'firmado_en': firma.firmado_en.strftime('%d/%m/%Y %H:%M'),
    })


# ═══════════════════════════════════════════════════════════════
# VERIFICAR FIRMA
# ═══════════════════════════════════════════════════════════════

def verificar_firma(request, token=None):
    """
    Verifica autenticidad de una firma digital.
    Accesible publicamente para validacion de terceros.
    """
    firma = None
    verificacion = None
    hash_buscar = request.GET.get('hash', '') or (token or '')

    if token:
        firma = FirmaDigital.objects.filter(token=token).select_related(
            'firmante', 'constancia__plantilla',
        ).first()
    elif hash_buscar:
        firma = FirmaDigital.objects.filter(hash_documento=hash_buscar).select_related(
            'firmante', 'constancia__plantilla',
        ).first()

    if firma and firma.estado == 'FIRMADO':
        # Recalcular hash actual del documento para comparar
        hash_actual = ''
        if firma.constancia:
            try:
                hash_actual, _ = _calcular_hash_constancia(firma.constancia)
            except Exception:
                hash_actual = ''

        integridad_ok = (
            hash_actual == firma.hash_documento if hash_actual else None
        )

        verificacion = {
            'firma': firma,
            'valida': True,
            'integridad': integridad_ok,
            'hash_original': firma.hash_documento,
            'hash_actual': hash_actual,
        }

    return render(request, 'documentos/firma/verificar.html', {
        'titulo': 'Verificar Firma Digital',
        'firma': firma,
        'verificacion': verificacion,
        'hash_buscar': hash_buscar,
    })


# ═══════════════════════════════════════════════════════════════
# DESCARGAR PDF CON FIRMA EMBEBIDA
# ═══════════════════════════════════════════════════════════════

@login_required
def descargar_firmado(request, token):
    """Genera y descarga PDF con firma embebida + QR de verificacion."""
    firma = get_object_or_404(
        FirmaDigital.objects.select_related(
            'firmante', 'constancia__plantilla', 'constancia__personal',
        ),
        token=token,
        estado='FIRMADO',
    )

    try:
        pdf_bytes = _generar_pdf_firmado(firma, request)
    except Exception as e:
        messages.error(request, f'Error generando PDF: {e}')
        return redirect('firma_interna_panel')

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    nombre = f'firmado_{firma.titulo_documento[:50]}_{firma.firmante.nro_doc}.pdf'
    nombre = nombre.replace(' ', '_')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


def _generar_pdf_firmado(firma, request):
    """Genera PDF con la firma embebida usando ReportLab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image,
        HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=2.5 * cm, bottomMargin=3 * cm,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        'DocTitle', parent=styles['Heading1'],
        fontSize=16, alignment=TA_CENTER, spaceAfter=12,
        textColor=colors.HexColor('#0f766e'),
    )
    style_body = ParagraphStyle(
        'DocBody', parent=styles['Normal'],
        fontSize=10, leading=14, alignment=TA_JUSTIFY,
    )
    style_small = ParagraphStyle(
        'DocSmall', parent=styles['Normal'],
        fontSize=8, leading=10, textColor=colors.grey,
    )
    style_center = ParagraphStyle(
        'DocCenter', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER,
    )

    elements = []

    # Titulo
    elements.append(Paragraph(firma.titulo_documento, style_title))
    elements.append(Spacer(1, 0.5 * cm))

    # Contenido del documento (si es constancia)
    if firma.constancia:
        try:
            _, html_content = _calcular_hash_constancia(firma.constancia)
            # Sanitize HTML for ReportLab (basic)
            import re
            html_clean = re.sub(r'<(div|section|article|header|footer|nav)[^>]*>', '<br/>', html_content)
            html_clean = re.sub(r'</(div|section|article|header|footer|nav)>', '', html_clean)
            html_clean = re.sub(r'style="[^"]*"', '', html_clean)
            elements.append(Paragraph(html_clean, style_body))
        except Exception:
            elements.append(Paragraph(
                'Contenido del documento no disponible para preview.',
                style_body,
            ))
    else:
        elements.append(Paragraph(
            f'Documento: {firma.titulo_documento}',
            style_body,
        ))

    elements.append(Spacer(1, 1.5 * cm))
    elements.append(HRFlowable(
        width='100%', thickness=1,
        color=colors.HexColor('#0f766e'), spaceAfter=10,
    ))

    # Seccion de firma
    elements.append(Paragraph('FIRMA DIGITAL', style_title))
    elements.append(Spacer(1, 0.3 * cm))

    # Imagen de la firma
    if firma.firma_imagen and ',' in firma.firma_imagen:
        try:
            img_data = firma.firma_imagen.split(',', 1)[1]
            img_bytes = base64.b64decode(img_data)
            img_buf = io.BytesIO(img_bytes)
            firma_img = Image(img_buf, width=6 * cm, height=3 * cm)
            firma_img.hAlign = 'CENTER'
            elements.append(firma_img)
        except Exception:
            elements.append(Paragraph('[Firma digital registrada]', style_center))
    else:
        elements.append(Paragraph('[Firma digital registrada]', style_center))

    elements.append(Spacer(1, 0.3 * cm))

    # Linea de firma
    elements.append(HRFlowable(
        width='50%', thickness=0.5,
        color=colors.black, spaceAfter=5,
    ))
    elements.append(Paragraph(
        firma.firmante.apellidos_nombres,
        style_center,
    ))
    elements.append(Paragraph(
        f'DNI: {firma.firmante.nro_doc}',
        style_center,
    ))

    elements.append(Spacer(1, 1 * cm))

    # Informacion de verificacion
    verify_url = request.build_absolute_uri(
        f'/documentos/firma/verificar/{firma.token}/'
    )

    # QR Code (try to generate, fallback to text)
    qr_generated = False
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=3, border=1)
        qr.add_data(verify_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color='black', back_color='white')
        qr_buf = io.BytesIO()
        qr_img.save(qr_buf, format='PNG')
        qr_buf.seek(0)
        qr_rl = Image(qr_buf, width=2.5 * cm, height=2.5 * cm)
        qr_rl.hAlign = 'LEFT'

        # Tabla con QR + info
        info_text = (
            f'<b>Verificacion de firma digital</b><br/>'
            f'<font size="7">Firmado el: {firma.firmado_en.strftime("%d/%m/%Y %H:%M:%S")}<br/>'
            f'IP: {firma.ip_address or "N/D"}<br/>'
            f'Hash SHA-256: {firma.hash_documento[:16]}...{firma.hash_documento[-8:]}<br/>'
            f'Token: {firma.token[:12]}...<br/>'
            f'Verificar en: {verify_url}</font>'
        )

        tbl = Table(
            [[qr_rl, Paragraph(info_text, style_small)]],
            colWidths=[3 * cm, 13 * cm],
        )
        tbl.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fffe')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#0f766e')),
            ('PADDING', (0, 0), (-1, -1), 8),
        ]))
        elements.append(tbl)
        qr_generated = True
    except ImportError:
        pass

    if not qr_generated:
        # Fallback sin QR
        info_text = (
            f'<b>Verificacion de firma digital</b><br/>'
            f'Firmado el: {firma.firmado_en.strftime("%d/%m/%Y %H:%M:%S")}<br/>'
            f'IP: {firma.ip_address or "N/D"}<br/>'
            f'Hash SHA-256: {firma.hash_documento}<br/>'
            f'Token: {firma.token[:20]}...<br/>'
            f'Verificar en: {verify_url}'
        )
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(Paragraph(info_text, style_small))

    doc.build(elements)
    return buf.getvalue()
