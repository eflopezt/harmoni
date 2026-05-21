"""Briefing del Día — vistas (admin + worker).

Pre-shift handover de gastronomía premium. Brigade kitchen style.
"""
from datetime import date as _date
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from asistencia.models import BriefingServicio, BriefingLectura
from empresas.models import Empresa

solo_admin_o_jefe = user_passes_test(lambda u: u.is_superuser or u.is_staff)


@login_required
@solo_admin_o_jefe
def briefing_panel(request):
    """Lista de briefings del local — recientes primero."""
    fecha_filtro = request.GET.get('fecha', '')
    empresa_id = request.GET.get('empresa_id', '')

    qs = BriefingServicio.objects.select_related('empresa', 'publicado_por').order_by('-fecha', '-id')

    if fecha_filtro:
        try:
            qs = qs.filter(fecha=fecha_filtro)
        except (ValueError, TypeError):
            pass
    if empresa_id:
        try:
            qs = qs.filter(empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass

    # Stats
    hoy = _date.today()
    hoy_count       = BriefingServicio.objects.filter(fecha=hoy).count()
    publicados_hoy  = BriefingServicio.objects.filter(fecha=hoy, estado='PUBLICADO').count()
    borradores_hoy  = BriefingServicio.objects.filter(fecha=hoy, estado='BORRADOR').count()

    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')

    return render(request, 'asistencia/briefing_panel.html', {
        'briefings':      qs[:50],
        'fecha_filtro':   fecha_filtro,
        'empresa_filtro': empresa_id,
        'empresas':       empresas,
        'hoy':            hoy,
        'hoy_count':      hoy_count,
        'publicados_hoy': publicados_hoy,
        'borradores_hoy': borradores_hoy,
    })


@login_required
@solo_admin_o_jefe
def briefing_crear(request):
    """Crea un nuevo briefing (form simple)."""
    if request.method == 'POST':
        empresa_id = request.POST.get('empresa')
        fecha      = request.POST.get('fecha')
        servicio   = request.POST.get('servicio', 'ALMUERZO')

        try:
            empresa = Empresa.objects.get(pk=int(empresa_id))
        except (Empresa.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Empresa inválida.')
            return redirect('briefing_panel')

        try:
            anio, mes, dia = fecha.split('-')
            fecha_obj = _date(int(anio), int(mes), int(dia))
        except (ValueError, AttributeError):
            messages.error(request, 'Fecha inválida.')
            return redirect('briefing_panel')

        # Evitar duplicado (unique_together)
        if BriefingServicio.objects.filter(
            empresa=empresa, fecha=fecha_obj, servicio=servicio,
        ).exists():
            messages.warning(
                request,
                f'Ya existe un briefing de {servicio} para {empresa} el {fecha_obj}. Edítalo en su lugar.',
            )
            existing = BriefingServicio.objects.get(
                empresa=empresa, fecha=fecha_obj, servicio=servicio,
            )
            return redirect('briefing_detalle', pk=existing.pk)

        b = BriefingServicio.objects.create(
            empresa=empresa,
            fecha=fecha_obj,
            servicio=servicio,
            covers_esperados=int(request.POST.get('covers_esperados') or 0),
            notas_chef=request.POST.get('notas_chef', '').strip(),
            especiales=request.POST.get('especiales', '').strip(),
            items_86=request.POST.get('items_86', '').strip(),
            vips_alergias=request.POST.get('vips_alergias', '').strip(),
            dress_code=request.POST.get('dress_code', '').strip(),
            notas_operativas=request.POST.get('notas_operativas', '').strip(),
            estado='BORRADOR',
        )

        # Si "publicar=1" lo publica inmediatamente
        if request.POST.get('publicar') == '1':
            b.publicar(request.user)
            messages.success(
                request,
                f'✓ Briefing publicado: {b}. Los trabajadores asignados lo verán al hacer login.',
            )
        else:
            messages.success(request, f'Briefing guardado como borrador: {b}.')

        return redirect('briefing_detalle', pk=b.pk)

    # GET → form
    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    return render(request, 'asistencia/briefing_form.html', {
        'briefing':         None,
        'empresas':         empresas,
        'fecha_default':    _date.today().isoformat(),
        'servicio_choices': BriefingServicio.SERVICIO_CHOICES,
    })


@login_required
@solo_admin_o_jefe
def briefing_detalle(request, pk):
    """Detalle/edición de un briefing. Permite publicar/cerrar."""
    b = get_object_or_404(BriefingServicio.objects.select_related('empresa', 'publicado_por'), pk=pk)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'editar':
            b.covers_esperados = int(request.POST.get('covers_esperados') or 0)
            b.notas_chef       = request.POST.get('notas_chef', '').strip()
            b.especiales       = request.POST.get('especiales', '').strip()
            b.items_86         = request.POST.get('items_86', '').strip()
            b.vips_alergias    = request.POST.get('vips_alergias', '').strip()
            b.dress_code       = request.POST.get('dress_code', '').strip()
            b.notas_operativas = request.POST.get('notas_operativas', '').strip()
            b.save()
            messages.success(request, 'Briefing actualizado.')

        elif accion == 'publicar' and b.estado == 'BORRADOR':
            b.publicar(request.user)
            messages.success(
                request,
                f'✓ Briefing publicado. Los trabajadores asignados al servicio '
                f'lo verán al hacer login.',
            )

        elif accion == 'cerrar' and b.estado == 'PUBLICADO':
            b.estado = 'CERRADO'
            b.save(update_fields=['estado', 'actualizado_en'])
            messages.info(request, 'Briefing cerrado.')

        elif accion == 'eliminar' and b.estado == 'BORRADOR':
            b.delete()
            messages.warning(request, 'Briefing eliminado.')
            return redirect('briefing_panel')

        return redirect('briefing_detalle', pk=b.pk)

    # Lecturas del briefing
    lecturas = b.lecturas.select_related('personal').order_by('-leido_en')
    total_lecturas = lecturas.count()

    return render(request, 'asistencia/briefing_detalle.html', {
        'briefing':       b,
        'lecturas':       lecturas[:30],
        'total_lecturas': total_lecturas,
    })


@login_required
@solo_admin_o_jefe
def briefing_pdf(request, pk):
    """Genera PDF imprimible del briefing (tipo ticket largo para cocina)."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT, TA_CENTER
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )
    from django.http import HttpResponse

    b = get_object_or_404(
        BriefingServicio.objects.select_related('empresa', 'publicado_por'),
        pk=pk,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=15*mm, bottomMargin=15*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )

    TEAL_DARK = colors.HexColor('#0d2b27')
    TEAL = colors.HexColor('#0f766e')
    AMBER = colors.HexColor('#92400e')
    GREEN = colors.HexColor('#065f46')
    RED = colors.HexColor('#991b1b')
    GRAY = colors.HexColor('#475569')

    styles = getSampleStyleSheet()
    st_title = ParagraphStyle(
        'T', parent=styles['Heading1'],
        fontName='Helvetica-Bold', fontSize=18, textColor=TEAL_DARK,
        alignment=TA_CENTER, leading=22, spaceAfter=6,
    )
    st_sub = ParagraphStyle(
        'S', parent=styles['Normal'], fontName='Helvetica', fontSize=11,
        textColor=GRAY, alignment=TA_CENTER, spaceAfter=12,
    )
    st_section_title = ParagraphStyle(
        'ST', parent=styles['Heading2'], fontName='Helvetica-Bold',
        fontSize=11, textColor=TEAL, leading=14, spaceAfter=4,
        spaceBefore=10, alignment=TA_LEFT,
    )
    st_body = ParagraphStyle(
        'B', parent=styles['Normal'], fontName='Helvetica', fontSize=10,
        textColor=colors.HexColor('#1f2937'), leading=14,
    )
    st_warn = ParagraphStyle(
        'W', parent=st_body, fontName='Helvetica-Bold', textColor=RED,
    )

    story = []
    story.append(Paragraph(
        f"BRIEFING DEL DÍA — {b.get_servicio_display().upper()}",
        st_title,
    ))
    story.append(Paragraph(
        f"{b.empresa.nombre_comercial or b.empresa.razon_social}  ·  {b.fecha.strftime('%A %d de %B %Y')}",
        st_sub,
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=TEAL,
                            spaceBefore=0, spaceAfter=10))

    # Header info
    info_data = [
        ['Servicio:', b.get_servicio_display(), 'Covers:', str(b.covers_esperados or '—')],
        ['Estado:', b.get_estado_display(), 'Dress code:', b.dress_code or '—'],
    ]
    info_t = Table(info_data, colWidths=[25*mm, 60*mm, 25*mm, 60*mm])
    info_t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (0, 0), (0, -1), GRAY),
        ('TEXTCOLOR', (2, 0), (2, -1), GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 6))

    def add_section(title, body, color=TEAL_DARK):
        story.append(Paragraph(title.upper(), ParagraphStyle(
            'sectT', parent=st_section_title, textColor=color)))
        # Reemplaza saltos de línea por <br/>
        body_html = body.replace('\n', '<br/>').replace('\r', '')
        story.append(Paragraph(body_html, st_body))

    if b.notas_chef:
        add_section('Notas del Chef', b.notas_chef, color=colors.HexColor('#06b6d4'))

    if b.especiales:
        add_section('Especiales del día', b.especiales, color=GREEN)

    if b.items_86:
        add_section("Items 86'd (NO disponibles)", b.items_86, color=RED)
        story.append(Paragraph(
            '⚠ Comunicar al salón ANTES de tomar pedidos.',
            st_warn,
        ))

    if b.vips_alergias:
        add_section('VIPs · Alergias · Cumpleaños', b.vips_alergias, color=AMBER)

    if b.notas_operativas:
        add_section('Notas operativas', b.notas_operativas, color=GRAY)

    # Footer
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#cbd5e1'),
                            spaceBefore=0, spaceAfter=6))
    footer_lines = []
    if b.publicado_en:
        footer_lines.append(
            f"Publicado por {b.publicado_por.username if b.publicado_por else '—'} "
            f"el {b.publicado_en.strftime('%d/%m %H:%M')}"
        )
    footer_lines.append('Harmoni ERP · Briefing del Día · Imprimir y colgar en cocina')
    for line in footer_lines:
        story.append(Paragraph(line, ParagraphStyle(
            'foot', parent=st_body, fontSize=8, textColor=GRAY, alignment=TA_CENTER)))

    doc.build(story)
    pdf = buf.getvalue()
    buf.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    fname = f'briefing_{b.empresa.subdominio or b.empresa.pk}_{b.fecha.strftime("%Y%m%d")}_{b.servicio}.pdf'
    response['Content-Disposition'] = f'inline; filename="{fname}"'
    return response


@login_required
def briefing_marcar_leido(request, pk):
    """Endpoint AJAX para que un trabajador marque que leyó el briefing."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requerido'}, status=405)

    b = get_object_or_404(BriefingServicio, pk=pk, estado='PUBLICADO')

    # Personal asociado al user
    try:
        from personal.models import Personal
        personal = Personal.objects.get(usuario=request.user)
    except (Personal.DoesNotExist, AttributeError):
        return JsonResponse({'ok': False, 'error': 'No es trabajador'}, status=403)

    lectura, created = BriefingLectura.objects.get_or_create(
        briefing=b, personal=personal,
    )
    return JsonResponse({
        'ok':       True,
        'created':  created,
        'leido_en': lectura.leido_en.isoformat(),
    })
