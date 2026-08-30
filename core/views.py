"""
Vistas del módulo core — Audit Trail viewer + búsqueda global.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import AuditLog, PreferenciaUsuario

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


def _can_use_process_shortcuts(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    try:
        from core.permisos import puede_aprobar

        return puede_aprobar(user)
    except Exception:
        return False


@login_required
@solo_admin
def audit_log_view(request):
    """Vista del registro de auditoría con filtros."""
    qs = AuditLog.objects.select_related('usuario', 'content_type').all()

    # Filtros
    accion = request.GET.get('accion', '')
    usuario_id = request.GET.get('usuario', '')
    modelo = request.GET.get('modelo', '')
    buscar = request.GET.get('q', '')

    if accion:
        qs = qs.filter(accion=accion)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if modelo:
        try:
            ct = ContentType.objects.get(pk=modelo)
            qs = qs.filter(content_type=ct)
        except ContentType.DoesNotExist:
            pass
    if buscar:
        from django.db.models import Q
        qs = qs.filter(
            Q(descripcion__icontains=buscar) |
            Q(usuario__username__icontains=buscar)
        )

    # Modelos con registros de auditoría para el filtro
    modelos_con_logs = ContentType.objects.filter(
        pk__in=AuditLog.objects.values_list('content_type_id', flat=True).distinct()
    ).order_by('model')

    # Usuarios que tienen registros
    from django.contrib.auth import get_user_model
    User = get_user_model()
    usuarios_con_logs = User.objects.filter(
        pk__in=AuditLog.objects.values_list('usuario_id', flat=True).distinct()
    ).order_by('username')

    context = {
        'titulo': 'Auditoría del Sistema',
        'logs': qs[:500],
        'total': qs.count(),
        'filtro_accion': accion,
        'filtro_usuario': usuario_id,
        'filtro_modelo': modelo,
        'buscar': buscar,
        'modelos': modelos_con_logs,
        'usuarios': usuarios_con_logs,
    }
    return render(request, 'core/audit_log.html', context)


@login_required
def global_search(request):
    """Búsqueda global AJAX — busca en empleados, papeletas y documentos."""
    from django.db.models import Q
    q = request.GET.get('q', '').strip()

    if len(q) < 2:
        return JsonResponse({'results': []})

    if _can_use_process_shortcuts(request.user):
        from core.process_map import get_process_search_shortcuts

        results = get_process_search_shortcuts(q)
    else:
        results = []

    # ── Empleados ──
    from personal.models import Personal
    empleados = Personal.objects.filter(
        Q(apellidos_nombres__icontains=q) |
        Q(nro_doc__icontains=q) |
        Q(cargo__icontains=q)
    ).order_by('apellidos_nombres')[:8]

    for e in empleados:
        results.append({
            'tipo': 'personal',
            'icono': 'fa-user',
            'color': '#0f766e',
            'titulo': e.apellidos_nombres,
            'detalle': f'{e.nro_doc} · {e.cargo or "Sin cargo"} · {e.grupo_tareo}',
            'url': f'/personal/{e.pk}/',
        })

    # ── Papeletas (solo admin) ──
    if request.user.is_superuser:
        from asistencia.models import RegistroPapeleta
        papeletas = RegistroPapeleta.objects.filter(
            Q(personal__apellidos_nombres__icontains=q) |
            Q(dni__icontains=q) |
            Q(tipo_permiso__icontains=q)
        ).select_related('personal').order_by('-fecha_inicio')[:5]

        for p in papeletas:
            results.append({
                'tipo': 'papeleta',
                'icono': 'fa-file-alt',
                'color': '#3b82f6',
                'titulo': f'{p.get_tipo_permiso_display()} — {p.personal.apellidos_nombres if p.personal else p.dni}',
                'detalle': f'{p.fecha_inicio.strftime("%d/%m/%Y")} · {p.get_estado_display()}',
                'url': f'/asistencia/papeletas/?buscar={q}',
            })

    # ── Documentos (tipos) ──
    if request.user.is_superuser:
        from documentos.models import DocumentoTrabajador
        docs = DocumentoTrabajador.objects.filter(
            Q(personal__apellidos_nombres__icontains=q) |
            Q(tipo__nombre__icontains=q) |
            Q(nombre_archivo__icontains=q)
        ).exclude(estado='ANULADO').select_related('personal', 'tipo').order_by('-creado_en')[:5]

        for d in docs:
            results.append({
                'tipo': 'documento',
                'icono': 'fa-folder-open',
                'color': '#0d9488',
                'titulo': f'{d.tipo.nombre} — {d.personal.apellidos_nombres}',
                'detalle': f'{d.nombre_archivo[:30]} · {d.get_estado_display()}',
                'url': f'/documentos/legajo/{d.personal_id}/',
            })

    # ── Préstamos (solo admin) ──
    if request.user.is_superuser:
        try:
            from prestamos.models import Prestamo
            prestamos = Prestamo.objects.filter(
                Q(personal__apellidos_nombres__icontains=q) |
                Q(tipo__nombre__icontains=q) |
                Q(personal__nro_doc__icontains=q) |
                Q(motivo__icontains=q)
            ).select_related('personal', 'tipo').order_by('-fecha_solicitud')[:5]

            for pr in prestamos:
                estado_txt = pr.get_estado_display()
                results.append({
                    'tipo': 'prestamo',
                    'icono': 'fa-hand-holding-usd',
                    'color': '#7c3aed',
                    'titulo': f'{pr.tipo.nombre} — {pr.personal.apellidos_nombres}',
                    'detalle': f'S/ {pr.monto_efectivo:,.2f} · {pr.num_cuotas} cuotas · {estado_txt}',
                    'url': f'/prestamos/{pr.pk}/',
                })
        except Exception:
            pass  # Módulo no instalado

    # ── Vacaciones/Permisos (solo admin) ──
    if request.user.is_superuser:
        try:
            from vacaciones.models import SolicitudVacacion
            vacs = SolicitudVacacion.objects.filter(
                Q(personal__apellidos_nombres__icontains=q)
            ).select_related('personal').order_by('-creado_en')[:4]
            for v in vacs:
                results.append({
                    'tipo': 'vacacion',
                    'icono': 'fa-umbrella-beach',
                    'color': '#f59e0b',
                    'titulo': f'Vacación — {v.personal.apellidos_nombres}',
                    'detalle': f'{v.fecha_inicio.strftime("%d/%m/%Y") if v.fecha_inicio else "—"} · {v.get_estado_display()}',
                    'url': '/vacaciones/',
                })
        except Exception:
            pass

    # ── OKRs (solo admin) ──
    if request.user.is_superuser:
        try:
            from evaluaciones.models import ObjetivoClave
            okrs = ObjetivoClave.objects.filter(
                Q(titulo__icontains=q)
            ).order_by('-creado_en')[:4]
            for o in okrs:
                results.append({
                    'tipo': 'okr',
                    'icono': 'fa-bullseye',
                    'color': '#6366f1',
                    'titulo': o.titulo[:60],
                    'detalle': f'{o.get_nivel_display()} · {o.get_status_display()} · {o.anio}',
                    'url': f'/evaluaciones/okrs/{o.pk}/',
                })
        except Exception:
            pass

    # ── Nóminas: períodos (solo admin) ──
    if request.user.is_superuser:
        try:
            from nominas.models import PeriodoNomina
            periodos = PeriodoNomina.objects.filter(
                Q(descripcion__icontains=q)
            ).order_by('-anio', '-mes')[:3]
            for p in periodos:
                results.append({
                    'tipo': 'nomina',
                    'icono': 'fa-file-invoice-dollar',
                    'color': '#059669',
                    'titulo': str(p),
                    'detalle': f'{p.get_tipo_display()} · {p.get_estado_display()} · {p.total_trabajadores or 0} trabajadores',
                    'url': f'/nominas/periodos/{p.pk}/',
                })
        except Exception:
            pass

    # ── Vacantes (reclutamiento) ──
    if request.user.is_superuser:
        try:
            from reclutamiento.models import Vacante
            vacantes = Vacante.objects.filter(
                Q(titulo__icontains=q) |
                Q(descripcion__icontains=q)
            ).order_by('-creado_en')[:4]
            for v in vacantes:
                results.append({
                    'tipo': 'vacante',
                    'icono': 'fa-briefcase',
                    'color': '#d97706',
                    'titulo': v.titulo,
                    'detalle': f'{v.get_estado_display()} · {getattr(v.area, "nombre", "Sin área")}',
                    'url': f'/reclutamiento/{v.pk}/',
                })
        except Exception:
            pass

    # ── Postulaciones (candidatos) ──
    if request.user.is_superuser:
        try:
            from reclutamiento.models import Postulacion
            posts = Postulacion.objects.filter(
                Q(nombre_completo__icontains=q) |
                Q(email__icontains=q) |
                Q(telefono__icontains=q)
            ).select_related('vacante', 'etapa').order_by('-cv_score', '-fecha_postulacion')[:6]
            for p in posts:
                score_badge = f' · ★ {p.cv_score}/100' if p.cv_score else ''
                results.append({
                    'tipo': 'candidato',
                    'icono': 'fa-user-tie',
                    'color': '#ec4899',
                    'titulo': p.nombre_completo,
                    'detalle': f'{p.vacante.titulo[:30]} · {p.etapa.nombre if p.etapa else "—"} · {p.get_estado_display()}{score_badge}',
                    'url': f'/reclutamiento/postulacion/{p.pk}/',
                })
        except Exception:
            pass

    # ── Capacitaciones ──
    if request.user.is_superuser:
        try:
            from capacitaciones.models import Capacitacion
            caps = Capacitacion.objects.filter(
                Q(titulo__icontains=q) |
                Q(descripcion__icontains=q)
            ).order_by('-fecha_inicio')[:4]
            for c in caps:
                results.append({
                    'tipo': 'capacitacion',
                    'icono': 'fa-graduation-cap',
                    'color': '#7c3aed',
                    'titulo': c.titulo,
                    'detalle': f'{c.fecha_inicio.strftime("%d/%m/%Y") if c.fecha_inicio else "Sin fecha"} · {c.get_estado_display() if hasattr(c, "get_estado_display") else ""}',
                    'url': f'/capacitaciones/{c.pk}/',
                })
        except Exception:
            pass

    # ── Workflows: instancias pendientes ──
    if request.user.is_superuser:
        try:
            from workflows.models import InstanciaFlujo
            wfs = InstanciaFlujo.objects.filter(
                Q(flujo__nombre__icontains=q) |
                Q(solicitante__first_name__icontains=q) |
                Q(solicitante__last_name__icontains=q)
            ).select_related('flujo', 'solicitante').order_by('-creado_en')[:3]
            for w in wfs:
                results.append({
                    'tipo': 'workflow',
                    'icono': 'fa-code-branch',
                    'color': '#0891b2',
                    'titulo': f'{w.flujo.nombre} — {w.solicitante.get_full_name() or w.solicitante.username}',
                    'detalle': f'{w.get_estado_display()} · {w.creado_en.strftime("%d/%m/%Y")}',
                    'url': f'/workflows/bandeja/{w.pk}/',
                })
        except Exception:
            pass

    return JsonResponse({'results': results[:22]})


# ─────────────────────────────────────────────────────────────────────
# BÚSQUEDA GLOBAL — PÁGINA COMPLETA
# ─────────────────────────────────────────────────────────────────────

@login_required
def busqueda_pagina(request):
    """Página completa de resultados de búsqueda global, agrupados por tipo."""
    from django.db.models import Q

    q = request.GET.get('q', '').strip()
    grupos = []
    total = 0

    if len(q) >= 2:
        # ── Empleados ──
        from personal.models import Personal
        empleados = Personal.objects.filter(
            Q(apellidos_nombres__icontains=q) |
            Q(nro_doc__icontains=q) |
            Q(cargo__icontains=q)
        ).select_related('subarea').order_by('apellidos_nombres')[:20]

        if empleados:
            items = []
            for e in empleados:
                items.append({
                    'tipo': 'personal',
                    'icono': 'fa-user',
                    'color': '#0f766e',
                    'titulo': e.apellidos_nombres,
                    'detalle': f'{e.nro_doc} · {e.cargo or "Sin cargo"}',
                    'extra': getattr(e.subarea, 'nombre', 'Sin área') if e.subarea else 'Sin área',
                    'estado': e.estado,
                    'url': f'/personal/{e.pk}/',
                })
            grupos.append({'nombre': 'Empleados', 'icono': 'fa-users', 'color': '#0f766e', 'items': items})
            total += len(items)

        # ── Papeletas (admin) ──
        if request.user.is_superuser:
            try:
                from asistencia.models import RegistroPapeleta
                papeletas = RegistroPapeleta.objects.filter(
                    Q(personal__apellidos_nombres__icontains=q) |
                    Q(dni__icontains=q) |
                    Q(tipo_permiso__icontains=q)
                ).select_related('personal').order_by('-fecha_inicio')[:10]
                if papeletas:
                    items = []
                    for p in papeletas:
                        items.append({
                            'tipo': 'papeleta',
                            'icono': 'fa-file-alt',
                            'color': '#3b82f6',
                            'titulo': f'{p.get_tipo_permiso_display()} — {p.personal.apellidos_nombres if p.personal else p.dni}',
                            'detalle': f'{p.fecha_inicio.strftime("%d/%m/%Y")} · {p.get_estado_display()}',
                            'extra': '',
                            'estado': p.estado,
                            'url': f'/asistencia/papeletas/?buscar={q}',
                        })
                    grupos.append({'nombre': 'Papeletas', 'icono': 'fa-file-alt', 'color': '#3b82f6', 'items': items})
                    total += len(items)
            except Exception:
                pass

        # ── Documentos (admin) ──
        if request.user.is_superuser:
            try:
                from documentos.models import DocumentoTrabajador
                docs = DocumentoTrabajador.objects.filter(
                    Q(personal__apellidos_nombres__icontains=q) |
                    Q(tipo__nombre__icontains=q) |
                    Q(nombre_archivo__icontains=q)
                ).exclude(estado='ANULADO').select_related('personal', 'tipo').order_by('-creado_en')[:10]
                if docs:
                    items = []
                    for d in docs:
                        items.append({
                            'tipo': 'documento',
                            'icono': 'fa-folder-open',
                            'color': '#0d9488',
                            'titulo': f'{d.tipo.nombre} — {d.personal.apellidos_nombres}',
                            'detalle': d.nombre_archivo[:50],
                            'extra': d.get_estado_display(),
                            'estado': d.estado,
                            'url': f'/documentos/legajo/{d.personal_id}/',
                        })
                    grupos.append({'nombre': 'Documentos', 'icono': 'fa-folder-open', 'color': '#0d9488', 'items': items})
                    total += len(items)
            except Exception:
                pass

        # ── Préstamos (admin) ──
        if request.user.is_superuser:
            try:
                from prestamos.models import Prestamo
                prestamos = Prestamo.objects.filter(
                    Q(personal__apellidos_nombres__icontains=q) |
                    Q(personal__nro_doc__icontains=q) |
                    Q(motivo__icontains=q)
                ).select_related('personal', 'tipo').order_by('-fecha_solicitud')[:10]
                if prestamos:
                    items = []
                    for pr in prestamos:
                        items.append({
                            'tipo': 'prestamo',
                            'icono': 'fa-hand-holding-usd',
                            'color': '#7c3aed',
                            'titulo': f'{pr.tipo.nombre} — {pr.personal.apellidos_nombres}',
                            'detalle': f'S/ {pr.monto_efectivo:,.2f} · {pr.num_cuotas} cuotas',
                            'extra': pr.get_estado_display(),
                            'estado': pr.estado,
                            'url': f'/prestamos/{pr.pk}/',
                        })
                    grupos.append({'nombre': 'Préstamos', 'icono': 'fa-hand-holding-usd', 'color': '#7c3aed', 'items': items})
                    total += len(items)
            except Exception:
                pass

        # ── Vacantes (admin) ──
        if request.user.is_superuser:
            try:
                from reclutamiento.models import Vacante
                vacantes = Vacante.objects.filter(
                    Q(titulo__icontains=q) |
                    Q(descripcion__icontains=q)
                ).order_by('-creado_en')[:10]
                if vacantes:
                    items = []
                    for v in vacantes:
                        items.append({
                            'tipo': 'vacante',
                            'icono': 'fa-briefcase',
                            'color': '#d97706',
                            'titulo': v.titulo,
                            'detalle': getattr(v.area, 'nombre', 'Sin área') if hasattr(v, 'area') and v.area else 'Sin área',
                            'extra': v.get_estado_display(),
                            'estado': getattr(v, 'estado', ''),
                            'url': f'/reclutamiento/vacantes/{v.pk}/',
                        })
                    grupos.append({'nombre': 'Vacantes', 'icono': 'fa-briefcase', 'color': '#d97706', 'items': items})
                    total += len(items)
            except Exception:
                pass

    context = {
        'titulo': f'Resultados para "{q}"' if q else 'Búsqueda',
        'query': q,
        'grupos': grupos,
        'total': total,
    }
    return render(request, 'core/busqueda.html', context)


# ─────────────────────────────────────────────────────────────────────
# PREFERENCIAS DE USUARIO
# ─────────────────────────────────────────────────────────────────────

@login_required
def preferencias_usuario(request):
    """Vista para que el usuario edite sus preferencias personales."""
    prefs = PreferenciaUsuario.para(request.user)

    if request.method == 'POST':
        prefs.sidebar_colapsado    = bool(request.POST.get('sidebar_colapsado'))
        prefs.tema                 = request.POST.get('tema', 'AUTO')
        prefs.idioma               = request.POST.get('idioma', 'es')
        landing = request.POST.get('landing_default', prefs.landing_default)
        if landing in dict(PreferenciaUsuario.LANDING_CHOICES):
            prefs.landing_default = landing
        prefs.notif_email_habilitado = bool(request.POST.get('notif_email_habilitado'))
        prefs.notif_contratos      = bool(request.POST.get('notif_contratos'))
        prefs.notif_vacaciones     = bool(request.POST.get('notif_vacaciones'))
        prefs.notif_documentos     = bool(request.POST.get('notif_documentos'))

        items_str = request.POST.get('items_por_pagina', '20')
        try:
            prefs.items_por_pagina = int(items_str)
        except ValueError:
            prefs.items_por_pagina = 20

        prefs.save()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True, 'mensaje': 'Preferencias guardadas.'})

        from django.contrib import messages
        messages.success(request, 'Preferencias actualizadas.')
        return redirect('preferencias_usuario')

    context = {
        'prefs': prefs,
        'items_opciones': PreferenciaUsuario.ITEMS_PAGINA_CHOICES,
        'tema_opciones': PreferenciaUsuario.TEMA_CHOICES,
        'idioma_opciones': PreferenciaUsuario.IDIOMA_CHOICES,
        'landing_opciones': PreferenciaUsuario.LANDING_CHOICES,
    }
    return render(request, 'core/preferencias.html', context)


@login_required
def preferencias_api(request):
    """API AJAX para guardar/obtener preferencias individuales."""
    prefs = PreferenciaUsuario.para(request.user)

    if request.method == 'POST':
        import json
        try:
            data = json.loads(request.body)
        except Exception:
            data = {}

        campo = data.get('campo')
        valor = data.get('valor')

        campos_permitidos = {
            'sidebar_colapsado', 'items_por_pagina', 'tema', 'idioma',
            'notif_email_habilitado', 'notif_contratos', 'notif_vacaciones', 'notif_documentos',
        }

        if campo in campos_permitidos and valor is not None:
            setattr(prefs, campo, valor)
            prefs.save(update_fields=[campo, 'actualizado_en'])
            return JsonResponse({'ok': True})

    return JsonResponse({'ok': False, 'error': 'Campo no permitido'}, status=400)

# ─────────────────────────────────────────────────────────────────────
# PERMISOS GRANULARES (INFRA.3)
# ─────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def permisos_panel(request):
    """Panel de gestión de permisos granulares por módulo."""
    from django.contrib.auth import get_user_model

    from core.models import MODULOS_SISTEMA, PermisoModulo
    User = get_user_model()

    usuarios = User.objects.filter(is_active=True, is_superuser=False).order_by('username')

    # Seleccionar usuario a editar
    user_id = request.GET.get('usuario') or (usuarios.first().pk if usuarios.exists() else None)
    usuario_sel = None
    filas = []

    if user_id:
        try:
            usuario_sel = User.objects.get(pk=user_id, is_superuser=False)
            permisos_map = {
                pm.modulo: pm
                for pm in PermisoModulo.objects.filter(usuario=usuario_sel)
            }
            for codigo, nombre in MODULOS_SISTEMA:
                pm = permisos_map.get(codigo)
                filas.append((
                    codigo, nombre,
                    pm.puede_ver      if pm else False,
                    pm.puede_crear    if pm else False,
                    pm.puede_editar   if pm else False,
                    pm.puede_aprobar  if pm else False,
                    pm.puede_exportar if pm else False,
                ))
        except User.DoesNotExist:
            pass

    return render(request, 'core/permisos_panel.html', {
        'titulo': 'Permisos por Módulo',
        'usuarios': usuarios,
        'usuario_sel': usuario_sel,
        'filas': filas,
    })


@login_required
@solo_admin
def permisos_guardar(request, user_id):
    """Guarda permisos de un usuario vía POST."""
    from django.contrib.auth import get_user_model

    from core.models import MODULOS_SISTEMA, PermisoModulo
    User = get_user_model()

    if request.method != 'POST':
        return redirect('permisos_modulos_panel')

    usuario_obj = get_object_or_404(User, pk=user_id, is_superuser=False)

    for modulo, _ in MODULOS_SISTEMA:
        prefix = f'{modulo}_'
        puede_ver      = bool(request.POST.get(f'{prefix}ver'))
        puede_crear    = bool(request.POST.get(f'{prefix}crear'))
        puede_editar   = bool(request.POST.get(f'{prefix}editar'))
        puede_aprobar  = bool(request.POST.get(f'{prefix}aprobar'))
        puede_exportar = bool(request.POST.get(f'{prefix}exportar'))

        if any([puede_ver, puede_crear, puede_editar, puede_aprobar, puede_exportar]):
            PermisoModulo.objects.update_or_create(
                usuario=usuario_obj, modulo=modulo,
                defaults={
                    'puede_ver': puede_ver,
                    'puede_crear': puede_crear,
                    'puede_editar': puede_editar,
                    'puede_aprobar': puede_aprobar,
                    'puede_exportar': puede_exportar,
                }
            )
        else:
            # Sin ningún permiso → eliminar el registro si existe
            PermisoModulo.objects.filter(usuario=usuario_obj, modulo=modulo).delete()

    from django.contrib import messages
    messages.success(request, f'Permisos de {usuario_obj.get_full_name() or usuario_obj.username} actualizados.')
    return redirect(f'/sistema/permisos-modulos/?usuario={user_id}')

