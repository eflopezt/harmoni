"""
Vistas para gestión de usuarios del sistema.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from ..models import Personal
from ..permissions import get_context_usuario


@login_required
def usuario_list(request):
    """Lista de usuarios del sistema con sus perfiles vinculados."""
    if not request.user.is_superuser:
        messages.error(request, 'Solo los administradores pueden gestionar usuarios')
        return redirect('home')

    from django.contrib.auth.models import User

    usuarios = User.objects.all().select_related('personal_data').order_by('username')

    # Buscar personal sin usuario asignado
    personal_sin_usuario = Personal.objects.filter(
        usuario__isnull=True,
        estado='Activo'
    ).select_related('subarea').order_by('apellidos_nombres')

    context = {
        'usuarios': usuarios,
        'personal_sin_usuario': personal_sin_usuario,
        'total_usuarios': usuarios.count(),
        'total_sin_vincular': personal_sin_usuario.count()
    }
    context.update(get_context_usuario(request.user))

    return render(request, 'personal/usuario_list.html', context)


@login_required
@require_http_methods(["POST"])
def usuario_vincular(request):
    """Vincular un usuario existente con un perfil de Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)

    from django.contrib.auth.models import User

    usuario_id = request.POST.get('usuario_id')
    personal_id = request.POST.get('personal_id')

    try:
        usuario = User.objects.get(pk=usuario_id)
        personal = Personal.objects.get(pk=personal_id)

        # Desvincular cualquier otro usuario que tenga este personal
        Personal.objects.filter(usuario=usuario).update(usuario=None)

        # Vincular
        personal.usuario = usuario
        personal.save()

        messages.success(request, f'Usuario {usuario.username} vinculado con {personal.nombre_completo}')
        return redirect('usuario_list')

    except (User.DoesNotExist, Personal.DoesNotExist) as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('usuario_list')


@login_required
@require_http_methods(["POST"])
def usuario_crear_y_vincular(request):
    """Crear un nuevo usuario y vincularlo automáticamente con Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)

    from django.contrib.auth.models import User

    personal_id = request.POST.get('personal_id')
    username = request.POST.get('username')
    password = request.POST.get('password')
    email = request.POST.get('email', '')

    try:
        personal = Personal.objects.get(pk=personal_id)

        # Verificar si ya existe el username
        if User.objects.filter(username=username).exists():
            messages.error(request, f'El usuario "{username}" ya existe')
            return redirect('usuario_list')

        # Crear usuario
        usuario = User.objects.create_user(
            username=username,
            password=password,
            email=email,
            first_name=personal.apellidos_nombres.split(',')[1].strip() if ',' in personal.apellidos_nombres else '',
            last_name=personal.apellidos_nombres.split(',')[0].strip() if ',' in personal.apellidos_nombres else personal.apellidos_nombres
        )

        # Vincular con personal
        personal.usuario = usuario
        personal.save()

        messages.success(request, f'Usuario {username} creado y vinculado con {personal.nombre_completo}')
        return redirect('usuario_list')

    except Personal.DoesNotExist:
        messages.error(request, 'Personal no encontrado')
        return redirect('usuario_list')
    except Exception as e:
        messages.error(request, f'Error al crear usuario: {str(e)}')
        return redirect('usuario_list')


@login_required
@require_http_methods(["POST"])
def usuario_desvincular(request, user_id):
    """Desvincular un usuario de su perfil de Personal."""
    if not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'No autorizado'}, status=403)

    try:
        personal = Personal.objects.get(usuario_id=user_id)
        personal.usuario = None
        personal.save()

        messages.success(request, 'Usuario desvinculado correctamente')
    except Personal.DoesNotExist:
        messages.warning(request, 'El usuario no estaba vinculado')

    return redirect('usuario_list')


@login_required
def usuario_sincronizar(request):
    """Vista para sincronizar usuarios automáticamente."""
    if not request.user.is_superuser:
        messages.error(request, 'No tiene permisos para esta acción')
        return redirect('home')

    from django.contrib.auth.models import User, Group
    from django.db import transaction

    if request.method == 'POST':

        accion = request.POST.get('accion', 'ambas')  # vincular, crear, ambas
        password_default = request.POST.get('password', 'dni')
        solo_activos = request.POST.get('solo_activos') == 'on'

        # LÍMITE DE SEGURIDAD: Máximo 50 usuarios por operación web
        LIMITE_WEB = 50

        stats = {
            'vinculados': 0,
            'creados': 0,
            'ya_vinculados': 0,
            'errores': [],
            'usuarios_creados': []
        }

        # Filtrar personal
        personal_qs = Personal.objects.select_related('usuario', 'subarea__area')
        if solo_activos:
            personal_qs = personal_qs.filter(estado='Activo')

        # Contar ya vinculados
        stats['ya_vinculados'] = personal_qs.filter(usuario__isnull=False).count()

        # Verificar cantidad a procesar
        personal_sin_usuario = personal_qs.filter(usuario__isnull=True, tipo_doc='DNI').exclude(nro_doc='')
        total_procesar = personal_sin_usuario.count()

        if total_procesar > LIMITE_WEB:
            messages.warning(
                request,
                f'⚠️ Hay {total_procesar} registros para procesar. '
                f'La interfaz web tiene un límite de {LIMITE_WEB} por operación. '
                f'Use el comando de terminal para sincronización masiva: '
                f'python manage.py sincronizar_usuarios'
            )
            return render(request, 'personal/usuario_sincronizar.html', {
                'total_personal': Personal.objects.count(),
                'personal_con_usuario': personal_qs.filter(usuario__isnull=False).count(),
                'personal_sin_usuario': total_procesar,
                'usuarios_sin_vincular': User.objects.filter(personal_data__isnull=True, is_superuser=False).count(),
                'limite_excedido': True,
                'total_procesar': total_procesar,
                'limite': LIMITE_WEB,
            })

        try:
            # 1. VINCULAR USUARIOS EXISTENTES
            if accion in ['vincular', 'ambas']:
                personal_sin_usuario = personal_qs.filter(usuario__isnull=True, tipo_doc='DNI')[:LIMITE_WEB]  # Limitar cantidad

                for persona in personal_sin_usuario:
                    if not persona.nro_doc:
                        continue

                    try:
                        usuario = User.objects.get(username=persona.nro_doc)

                        # Verificar que no esté vinculado a otro
                        if hasattr(usuario, 'personal_data'):
                            continue

                        persona.usuario = usuario
                        persona.save(update_fields=['usuario'])
                        stats['vinculados'] += 1

                    except User.DoesNotExist:
                        pass
                    except Exception as e:
                        stats['errores'].append(f'{persona.apellidos_nombres}: {str(e)}')

            # 2. CREAR USUARIOS NUEVOS
            if accion in ['crear', 'ambas']:
                personal_sin_usuario = personal_qs.filter(
                    usuario__isnull=True,
                    tipo_doc='DNI'
                ).exclude(nro_doc__isnull=True).exclude(nro_doc='')[:LIMITE_WEB]  # Limitar cantidad

                for persona in personal_sin_usuario:
                    try:
                        # Generar username: primera letra nombre + apellido paterno
                        nombres = persona.apellidos_nombres.strip().split()
                        if len(nombres) < 2:
                            stats['errores'].append(f'{persona.apellidos_nombres}: Formato de nombre inválido')
                            continue

                        apellido_paterno = nombres[0].lower()
                        primer_nombre = nombres[-1] if len(nombres) >= 2 else nombres[0]
                        primera_letra = primer_nombre[0].lower()
                        username = f'{primera_letra}{apellido_paterno}'.lower()

                        # Si ya existe, agregar número
                        username_base = username
                        counter = 1
                        while User.objects.filter(username=username).exists():
                            username = f'{username_base}{counter}'
                            counter += 1
                            if counter > 99:
                                stats['errores'].append(f'{persona.apellidos_nombres}: No se pudo generar username único')
                                break

                        if counter > 99:
                            continue

                        # Generar email
                        email = persona.correo_corporativo or persona.correo_personal or f'{username}@temp.com'

                        # Extraer nombres
                        first_name = ' '.join(nombres[2:]) if len(nombres) > 2 else nombres[-1]
                        last_name = ' '.join(nombres[:2]) if len(nombres) >= 2 else nombres[0]

                        # Contraseña: DNI o personalizada
                        password = persona.nro_doc if password_default.lower() == 'dni' else password_default

                        with transaction.atomic():
                            # Crear usuario
                            usuario = User.objects.create_user(
                                username=username,
                                email=email,
                                password=password,
                                first_name=first_name[:30],
                                last_name=last_name[:30],
                                is_staff=False,
                                is_active=True
                            )

                            # Vincular
                            persona.usuario = usuario
                            persona.save(update_fields=['usuario'])

                            # Si es responsable, agregar a grupo
                            if persona.areas_responsable.exists():
                                grupo, _ = Group.objects.get_or_create(name='Responsable de Área')
                                usuario.groups.add(grupo)

                            stats['creados'] += 1
                            stats['usuarios_creados'].append({
                                'nombre': persona.apellidos_nombres,
                                'usuario': username,
                                'password': password
                            })

                    except Exception as e:
                        stats['errores'].append(f'{persona.apellidos_nombres}: {str(e)}')

            # Mostrar resultados
            if stats['vinculados'] > 0:
                messages.success(request, f'✓ {stats["vinculados"]} usuarios vinculados exitosamente')

            if stats['creados'] > 0:
                messages.success(request, f'✓ {stats["creados"]} usuarios creados exitosamente')
                # Guardar lista de usuarios creados en sesión para mostrarlos
                request.session['usuarios_creados'] = stats['usuarios_creados']

            if stats['errores']:
                for error in stats['errores'][:5]:
                    messages.warning(request, f'⚠ {error}')

            if stats['vinculados'] == 0 and stats['creados'] == 0:
                messages.info(request, 'No se encontraron usuarios para sincronizar')

            return redirect('usuario_sincronizar')

        except Exception as e:
            messages.error(request, f'Error en sincronización: {str(e)}')
            return redirect('usuario_sincronizar')

    # GET - Mostrar formulario y estadísticas
    total_personal = Personal.objects.count()
    personal_con_usuario = Personal.objects.filter(usuario__isnull=False).count()
    personal_sin_usuario = Personal.objects.filter(usuario__isnull=True, tipo_doc='DNI').exclude(nro_doc='').count()
    usuarios_sin_vincular = User.objects.filter(personal_data__isnull=True, is_superuser=False).count()

    # Obtener lista de usuarios creados de la sesión
    usuarios_creados = request.session.pop('usuarios_creados', [])

    context = {
        'total_personal': total_personal,
        'personal_con_usuario': personal_con_usuario,
        'personal_sin_usuario': personal_sin_usuario,
        'usuarios_sin_vincular': usuarios_sin_vincular,
        'usuarios_creados': usuarios_creados,
    }

    return render(request, 'personal/usuario_sincronizar.html', context)


# ── Gestión de Accesos (RBAC) ─────────────────────────────────────────────────

def _puede_gestionar_accesos(user) -> bool:
    """
    Puede gestionar accesos quien sea:
      - Superusuario
      - Admin RRHH (perfil admin-rrhh)
      - Cualquier usuario con puede_aprobar=True Y mod_personal=True en su perfil
    """
    if user.is_superuser:
        return True
    try:
        personal = Personal.objects.select_related('perfil_acceso').get(usuario=user)
        p = personal.perfil_acceso
        if p is None:
            return False
        return p.puede_aprobar and p.mod_personal
    except Personal.DoesNotExist:
        return False


@login_required
def accesos_gestion(request):
    """
    Panel de Gestión de Accesos: lista todos los usuarios con Personal vinculado,
    muestra su PerfilAcceso actual y permite cambiarlo.
    Accesible para superusuarios y usuarios con perfil admin-rrhh.
    """
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'No tienes permisos para gestionar accesos de usuarios.')
        return redirect('home')

    from core.models import PerfilAcceso

    # Personal con usuario vinculado (puede loguearse)
    personal_con_acceso = (
        Personal.objects
        .filter(usuario__isnull=False)
        .select_related('usuario', 'perfil_acceso', 'subarea__area')
        .order_by('apellidos_nombres')
    )

    # Filtros
    buscar     = request.GET.get('buscar', '').strip()
    filtro_perfil = request.GET.get('perfil', '').strip()
    filtro_sin_perfil = request.GET.get('sin_perfil', '')

    if buscar:
        from django.db.models import Q
        personal_con_acceso = personal_con_acceso.filter(
            Q(apellidos_nombres__icontains=buscar) |
            Q(nro_doc__icontains=buscar) |
            Q(usuario__username__icontains=buscar)
        )
    if filtro_perfil:
        personal_con_acceso = personal_con_acceso.filter(
            perfil_acceso__codigo=filtro_perfil
        )
    if filtro_sin_perfil:
        personal_con_acceso = personal_con_acceso.filter(perfil_acceso__isnull=True)

    perfiles_disponibles = PerfilAcceso.objects.order_by('nombre')

    # Stats
    total = Personal.objects.filter(usuario__isnull=False).count()
    sin_perfil = Personal.objects.filter(usuario__isnull=False, perfil_acceso__isnull=True).count()

    return render(request, 'personal/accesos_gestion.html', {
        'personal_con_acceso':   personal_con_acceso,
        'perfiles_disponibles':  perfiles_disponibles,
        'total_con_acceso':      total,
        'sin_perfil_count':      sin_perfil,
        'buscar':                buscar,
        'filtro_perfil':         filtro_perfil,
        'filtro_sin_perfil':     filtro_sin_perfil,
    })


@login_required
def accesos_detalle_usuario(request, personal_pk):
    """
    Devuelve JSON con el estado de módulos del usuario:
    - perfil base (de PerfilAcceso)
    - overrides individuales (de PermisoModulo)
    - estado efectivo (la combinación de ambos)
    Usado para poblar el modal de edición de accesos granulares.
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    try:
        personal = Personal.objects.select_related('perfil_acceso', 'usuario').get(pk=personal_pk)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado.'}, status=404)

    from core.models import PermisoModulo, MODULOS_SISTEMA

    # Perfil base
    perfil_base = personal.perfil_acceso.as_modulos_dict() if personal.perfil_acceso else {}

    # Overrides individuales existentes para este usuario
    overrides_qs = PermisoModulo.objects.filter(usuario=personal.usuario) if personal.usuario else []
    overrides = {f'mod_{ov.modulo}': ov.puede_ver for ov in overrides_qs}

    modulos_info = []
    for codigo_modulo, nombre_modulo in MODULOS_SISTEMA:
        key = f'mod_{codigo_modulo}'
        perfil_val   = perfil_base.get(key)   # None si no tiene perfil
        override_val = overrides.get(key)      # None si sin override

        # Estado efectivo: override tiene prioridad
        if override_val is not None:
            efectivo = override_val
            fuente   = 'override'
        elif perfil_val is not None:
            efectivo = perfil_val
            fuente   = 'perfil'
        else:
            efectivo = True   # Sin perfil ni override → acceso completo según empresa
            fuente   = 'empresa'

        modulos_info.append({
            'codigo':   codigo_modulo,
            'nombre':   nombre_modulo,
            'perfil':   perfil_val,    # None = sin perfil
            'override': override_val,  # None = sin override personal
            'efectivo': efectivo,
            'fuente':   fuente,        # 'perfil' | 'override' | 'empresa'
        })

    return JsonResponse({
        'success':         True,
        'personal_pk':     personal.pk,
        'personal_nombre': personal.apellidos_nombres,
        'perfil_nombre':   personal.perfil_acceso.nombre if personal.perfil_acceso else None,
        'modulos':         modulos_info,
    })


@login_required
@require_http_methods(["POST"])
def accesos_toggle_modulo(request):
    """
    AJAX: activa, desactiva o resetea el override de un módulo para un usuario.
      conceder → PermisoModulo(puede_ver=True)  — ve el módulo aunque el perfil lo niegue
      revocar  → PermisoModulo(puede_ver=False) — no ve aunque el perfil lo incluya
      reset    → elimina el override — vuelve a la regla del perfil
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    personal_pk = request.POST.get('personal_id')
    modulo      = request.POST.get('modulo', '').strip()
    accion      = request.POST.get('accion', '').strip()

    if accion not in ('conceder', 'revocar', 'reset'):
        return JsonResponse({'success': False, 'error': 'Acción inválida.'}, status=400)

    from core.models import PermisoModulo, MODULOS_SISTEMA
    from personal.context_processors import invalidar_perfil

    codigos_validos = {c for c, _ in MODULOS_SISTEMA}
    if modulo not in codigos_validos:
        return JsonResponse({'success': False, 'error': f'Módulo "{modulo}" no existe.'}, status=400)

    try:
        personal = Personal.objects.select_related('usuario').get(pk=personal_pk)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado.'}, status=404)

    if not personal.usuario:
        return JsonResponse({'success': False, 'error': 'El personal no tiene usuario vinculado.'}, status=400)

    if accion == 'reset':
        PermisoModulo.objects.filter(usuario=personal.usuario, modulo=modulo).delete()
        nuevo_estado = None
        fuente       = 'perfil'
    else:
        puede_ver = (accion == 'conceder')
        PermisoModulo.objects.update_or_create(
            usuario=personal.usuario,
            modulo=modulo,
            defaults={
                'puede_ver':     puede_ver,
                'puede_crear':   puede_ver,
                'puede_editar':  puede_ver,
                'puede_aprobar': False,
                'puede_exportar': puede_ver,
            },
        )
        nuevo_estado = puede_ver
        fuente       = 'override'

    invalidar_perfil(personal.usuario_id)

    return JsonResponse({
        'success':         True,
        'modulo':          modulo,
        'accion':          accion,
        'nuevo_estado':    nuevo_estado,
        'fuente':          fuente,
        'personal_nombre': personal.apellidos_nombres,
    })


@login_required
@require_http_methods(["POST"])
def accesos_asignar_perfil(request):
    """
    AJAX: asigna o quita un PerfilAcceso a un Personal.
    Invalida el cache RBAC del usuario afectado.
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    personal_pk = request.POST.get('personal_id')
    perfil_codigo = request.POST.get('perfil_codigo', '').strip()  # '' = quitar perfil

    try:
        personal = Personal.objects.select_related('usuario', 'perfil_acceso').get(pk=personal_pk)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado.'}, status=404)

    from core.models import PerfilAcceso
    from personal.context_processors import invalidar_perfil

    if perfil_codigo:
        try:
            perfil = PerfilAcceso.objects.get(codigo=perfil_codigo)
        except PerfilAcceso.DoesNotExist:
            return JsonResponse({'success': False, 'error': f'Perfil "{perfil_codigo}" no existe.'}, status=400)
        personal.perfil_acceso = perfil
        perfil_nombre = perfil.nombre
    else:
        personal.perfil_acceso = None
        perfil_nombre = '(sin perfil)'

    personal.save(update_fields=['perfil_acceso'])

    # Invalida cache RBAC del usuario afectado
    if personal.usuario_id:
        invalidar_perfil(personal.usuario_id)

    return JsonResponse({
        'success': True,
        'personal_nombre': personal.apellidos_nombres,
        'perfil_nombre':   perfil_nombre,
        'perfil_codigo':   perfil_codigo,
    })


# ── Portal: Crear / Restablecer Acceso ───────────────────────────────────────

@login_required
@require_http_methods(["POST"])
def portal_crear_acceso(request, personal_pk):
    """
    Crea acceso al Portal del Empleado para un Personal dado.

    Lógica:
        - Username = DNI (estándar, fácil de recordar)
        - Password inicial = DNI (el empleado debe cambiarlo en el primer login)
        - Vincula el User creado a personal.usuario
        - Envía email de bienvenida con credenciales si tiene email configurado
        - Devuelve JSON para AJAX desde personal_detail

    Acceso: superusuarios y usuarios con puede_aprobar + mod_personal.
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos para gestionar accesos.'}, status=403)

    try:
        personal = Personal.objects.select_related('usuario').get(pk=personal_pk)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado.'}, status=404)

    if personal.usuario:
        return JsonResponse({
            'success': False,
            'error': f'Ya tiene acceso al portal (usuario: {personal.usuario.username}).',
        }, status=400)

    if not personal.nro_doc:
        return JsonResponse({'success': False, 'error': 'El empleado no tiene número de documento registrado.'}, status=400)

    from django.contrib.auth.models import User
    from django.db import transaction

    username = personal.nro_doc.strip()

    if User.objects.filter(username=username).exists():
        # El username (DNI) ya existe — vincular si no está asignado a nadie
        usuario_existente = User.objects.get(username=username)
        if hasattr(usuario_existente, 'personal_data'):
            return JsonResponse({
                'success': False,
                'error': f'El usuario "{username}" ya existe y está asignado a otro empleado.',
            }, status=400)
        # Vincular el usuario existente
        personal.usuario = usuario_existente
        personal.save(update_fields=['usuario'])
        return JsonResponse({
            'success': True,
            'mensaje': f'Usuario existente "{username}" vinculado al empleado.',
            'username': username,
            'creado':  False,
        })

    email = personal.correo_corporativo or personal.correo_personal or ''

    # Parsear apellidos_nombres → first_name / last_name
    partes     = personal.apellidos_nombres.strip().split(',')
    last_name  = partes[0].strip()[:150] if partes else ''
    first_name = partes[1].strip()[:150] if len(partes) > 1 else ''

    with transaction.atomic():
        usuario = User.objects.create_user(
            username   = username,
            password   = username,         # contraseña inicial = DNI
            email      = email,
            first_name = first_name,
            last_name  = last_name,
            is_staff   = False,
            is_active  = True,
        )
        personal.usuario = usuario
        personal.save(update_fields=['usuario'])

    # Enviar email de bienvenida si tiene correo
    if email:
        try:
            from comunicaciones.services import NotificacionService
            nombre_display = personal.nombre_completo if hasattr(personal, 'nombre_completo') else personal.apellidos_nombres

            try:
                from asistencia.models import ConfiguracionSistema
                empresa = ConfiguracionSistema.get().empresa_nombre
            except Exception:
                empresa = 'Harmoni'

            asunto = f'Bienvenido al Portal del Empleado — {empresa}'
            cuerpo = (
                f'Hola {nombre_display},\n\n'
                f'Se ha creado tu acceso al Portal del Empleado de {empresa}.\n\n'
                f'Tus credenciales de ingreso:\n'
                f'  • Usuario: {username}\n'
                f'  • Contraseña inicial: {username} (tu número de documento)\n\n'
                f'Por seguridad, te recomendamos cambiar tu contraseña luego del primer ingreso.\n\n'
                f'Saludos,\nEquipo de Recursos Humanos — {empresa}'
            )
            NotificacionService.enviar(
                destinatario = personal,
                asunto       = asunto,
                cuerpo       = cuerpo,
                tipo         = 'EMAIL',
            )
        except Exception:
            pass  # El acceso se creó igual — el email es best-effort

    return JsonResponse({
        'success':  True,
        'mensaje':  f'Acceso creado. Usuario: {username} | Contraseña inicial: DNI del empleado.',
        'username': username,
        'creado':   True,
        'email_enviado': bool(email),
    })


@login_required
@require_http_methods(["POST"])
def portal_reset_credenciales(request, personal_pk):
    """
    Restablece la contraseña del portal al DNI del empleado y (opcionalmente) envía email.

    Útil cuando el empleado olvidó su contraseña o necesita re-envio de credenciales.
    La nueva contraseña queda como el DNI — el empleado debe cambiarla luego.
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos para gestionar accesos.'}, status=403)

    try:
        personal = Personal.objects.select_related('usuario').get(pk=personal_pk)
    except Personal.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Personal no encontrado.'}, status=404)

    if not personal.usuario:
        return JsonResponse({'success': False, 'error': 'El empleado no tiene acceso al portal.'}, status=400)

    if not personal.nro_doc:
        return JsonResponse({'success': False, 'error': 'El empleado no tiene número de documento registrado.'}, status=400)

    nueva_password = personal.nro_doc.strip()
    personal.usuario.set_password(nueva_password)
    personal.usuario.save(update_fields=['password'])

    email = personal.correo_corporativo or personal.correo_personal or ''

    if email:
        try:
            from comunicaciones.services import NotificacionService
            nombre_display = personal.nombre_completo if hasattr(personal, 'nombre_completo') else personal.apellidos_nombres

            try:
                from asistencia.models import ConfiguracionSistema
                empresa = ConfiguracionSistema.get().empresa_nombre
            except Exception:
                empresa = 'Harmoni'

            asunto = f'Restablecimiento de contraseña — Portal {empresa}'
            cuerpo = (
                f'Hola {nombre_display},\n\n'
                f'Se ha restablecido tu contraseña del Portal del Empleado de {empresa}.\n\n'
                f'Tus credenciales actuales:\n'
                f'  • Usuario: {personal.usuario.username}\n'
                f'  • Nueva contraseña: {nueva_password} (tu número de documento)\n\n'
                f'Por seguridad, cambia tu contraseña luego del primer ingreso.\n\n'
                f'Saludos,\nEquipo de Recursos Humanos — {empresa}'
            )
            NotificacionService.enviar(
                destinatario = personal,
                asunto       = asunto,
                cuerpo       = cuerpo,
                tipo         = 'EMAIL',
            )
        except Exception:
            pass

    return JsonResponse({
        'success':       True,
        'mensaje':       f'Contraseña restablecida al DNI del empleado.',
        'username':      personal.usuario.username,
        'email_enviado': bool(email),
    })


# ══════════════════════════════════════════════════════════════════════════════
# GESTIÓN COMPLETA DE USUARIOS (interfaz ERP — no Django admin)
# ══════════════════════════════════════════════════════════════════════════════

def _get_modulos_permisos_for_user(user):
    """
    Construye la lista de módulos con sus permisos (ver/crear/editar/aprobar/exportar)
    para renderizar la matriz de permisos en templates.
    """
    from core.models import PermisoModulo, MODULOS_SISTEMA

    # Obtener overrides existentes
    overrides = {}
    for pm in PermisoModulo.objects.filter(usuario=user):
        overrides[pm.modulo] = pm

    modulos = []
    for codigo, nombre in MODULOS_SISTEMA:
        pm = overrides.get(codigo)
        campos = ['puede_ver', 'puede_crear', 'puede_editar', 'puede_aprobar', 'puede_exportar']
        permisos = []
        for campo in campos:
            valor = getattr(pm, campo, False) if pm else False
            permisos.append({'campo': campo, 'valor': valor})
        modulos.append({
            'codigo': codigo,
            'nombre': nombre,
            'permisos': permisos,
        })
    return modulos


@login_required
def gestion_usuario_lista(request):
    """Lista completa de usuarios con filtros, búsqueda y acciones masivas."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'No tienes permisos para gestionar usuarios.')
        return redirect('home')

    from django.contrib.auth.models import User
    from django.db.models import Q
    from core.models import PerfilAcceso

    qs = User.objects.select_related('personal_data', 'personal_data__perfil_acceso',
                                      'personal_data__subarea__area',
                                      'personal_data__empresa').order_by('username')

    filtros = {
        'q': request.GET.get('q', '').strip(),
        'estado': request.GET.get('estado', '').strip(),
        'perfil': request.GET.get('perfil', '').strip(),
        'empresa': request.GET.get('empresa', '').strip(),
    }

    if filtros['q']:
        qs = qs.filter(
            Q(username__icontains=filtros['q']) |
            Q(email__icontains=filtros['q']) |
            Q(first_name__icontains=filtros['q']) |
            Q(last_name__icontains=filtros['q']) |
            Q(personal_data__apellidos_nombres__icontains=filtros['q'])
        )
    if filtros['estado'] == 'activo':
        qs = qs.filter(is_active=True)
    elif filtros['estado'] == 'inactivo':
        qs = qs.filter(is_active=False)
    if filtros['perfil'] == 'sin_perfil':
        qs = qs.filter(
            Q(personal_data__perfil_acceso__isnull=True) | Q(personal_data__isnull=True)
        ).exclude(is_superuser=True)
    elif filtros['perfil']:
        qs = qs.filter(personal_data__perfil_acceso__codigo=filtros['perfil'])
    if filtros['empresa']:
        qs = qs.filter(personal_data__empresa_id=filtros['empresa'])

    # Stats
    all_users = User.objects.all()
    stats = {
        'total': all_users.count(),
        'activos': all_users.filter(is_active=True).count(),
        'inactivos': all_users.filter(is_active=False).count(),
        'sin_vincular': all_users.filter(personal_data__isnull=True).exclude(is_superuser=True).count(),
    }

    # Empresas para filtro
    try:
        from empresas.models import Empresa
        empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    except Exception:
        empresas = []

    context = {
        'usuarios': qs,
        'filtros': filtros,
        'stats': stats,
        'perfiles': PerfilAcceso.objects.order_by('nombre'),
        'empresas': empresas,
    }
    return render(request, 'personal/usuarios/lista.html', context)


@login_required
def gestion_usuario_crear(request):
    """Crear un nuevo usuario con vinculación a Personal y perfil de acceso."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'No tienes permisos para crear usuarios.')
        return redirect('home')

    from django.contrib.auth.models import User
    from django.db import transaction
    from core.models import PerfilAcceso

    try:
        from empresas.models import Empresa
        empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    except Exception:
        empresas = []

    personal_sin_usuario = Personal.objects.filter(
        usuario__isnull=True, estado='Activo'
    ).select_related('subarea').order_by('apellidos_nombres')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')
        personal_id = request.POST.get('personal_id', '').strip()
        perfil_id = request.POST.get('perfil_acceso', '').strip()
        empresa_id = request.POST.get('empresa', '').strip()
        is_active = request.POST.get('is_active') == 'on'

        # Validations
        if not username:
            messages.error(request, 'El username es obligatorio.')
        elif password != password2:
            messages.error(request, 'Las passwords no coinciden.')
        elif len(password) < 6:
            messages.error(request, 'La password debe tener al menos 6 caracteres.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f'El username "{username}" ya existe.')
        else:
            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password,
                        is_active=is_active,
                    )

                    # Vincular con Personal si se seleccionó
                    if personal_id:
                        personal = Personal.objects.get(pk=personal_id)
                        personal.usuario = user

                        # Asignar perfil si se seleccionó
                        if perfil_id:
                            perfil = PerfilAcceso.objects.get(pk=perfil_id)
                            personal.perfil_acceso = perfil

                        # Asignar empresa
                        if empresa_id:
                            personal.empresa_id = empresa_id

                        personal.save()

                        # Extraer nombre del personal
                        partes = personal.apellidos_nombres.strip().split(',')
                        user.last_name = partes[0].strip()[:150] if partes else ''
                        user.first_name = partes[1].strip()[:150] if len(partes) > 1 else ''
                        user.save(update_fields=['first_name', 'last_name'])

                messages.success(request, f'Usuario "{username}" creado exitosamente.')
                return redirect('gestion_usuario_detalle', pk=user.pk)

            except Personal.DoesNotExist:
                messages.error(request, 'Empleado no encontrado.')
            except PerfilAcceso.DoesNotExist:
                messages.error(request, 'Perfil de acceso no encontrado.')
            except Exception as e:
                messages.error(request, f'Error al crear usuario: {e}')

        # Preserve form data on error
        form_data = request.POST.dict()
    else:
        form_data = {}

    return render(request, 'personal/usuarios/crear.html', {
        'personal_sin_usuario': personal_sin_usuario,
        'perfiles': PerfilAcceso.objects.order_by('nombre'),
        'empresas': empresas,
        'form_data': form_data,
    })


@login_required
def gestion_usuario_editar(request, pk):
    """Editar datos de cuenta, perfil y password de un usuario."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'No tienes permisos para editar usuarios.')
        return redirect('home')

    from django.contrib.auth.models import User
    from core.models import PerfilAcceso

    try:
        usuario = User.objects.select_related('personal_data', 'personal_data__perfil_acceso',
                                               'personal_data__empresa').get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('gestion_usuario_lista')

    personal = getattr(usuario, 'personal_data', None)

    try:
        from empresas.models import Empresa
        empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    except Exception:
        empresas = []

    if request.method == 'POST':
        section = request.POST.get('section', '')

        if section == 'account':
            new_username = request.POST.get('username', '').strip()
            if new_username and new_username != usuario.username:
                if User.objects.filter(username=new_username).exclude(pk=pk).exists():
                    messages.error(request, f'El username "{new_username}" ya existe.')
                else:
                    usuario.username = new_username
            usuario.email = request.POST.get('email', '').strip()
            usuario.first_name = request.POST.get('first_name', '').strip()[:150]
            usuario.last_name = request.POST.get('last_name', '').strip()[:150]
            usuario.is_active = request.POST.get('is_active') == 'on'
            usuario.save()
            messages.success(request, 'Datos de cuenta actualizados.')

        elif section == 'profile' and personal:
            perfil_id = request.POST.get('perfil_acceso', '').strip()
            empresa_id = request.POST.get('empresa', '').strip()

            if perfil_id:
                try:
                    personal.perfil_acceso = PerfilAcceso.objects.get(pk=perfil_id)
                except PerfilAcceso.DoesNotExist:
                    pass
            else:
                personal.perfil_acceso = None

            personal.empresa_id = empresa_id if empresa_id else None
            personal.save(update_fields=['perfil_acceso', 'empresa'])

            # Invalidate RBAC cache
            from personal.context_processors import invalidar_perfil
            invalidar_perfil(usuario.pk)

            messages.success(request, 'Perfil y empresa actualizados.')

        elif section == 'password':
            new_pw = request.POST.get('new_password', '')
            new_pw2 = request.POST.get('new_password2', '')
            if new_pw != new_pw2:
                messages.error(request, 'Las passwords no coinciden.')
            elif len(new_pw) < 6:
                messages.error(request, 'La password debe tener al menos 6 caracteres.')
            else:
                usuario.set_password(new_pw)
                usuario.save(update_fields=['password'])
                messages.success(request, 'Password actualizada exitosamente.')

        return redirect('gestion_usuario_editar', pk=pk)

    modulos_permisos = _get_modulos_permisos_for_user(usuario) if personal and not usuario.is_superuser else []

    return render(request, 'personal/usuarios/editar.html', {
        'usuario': usuario,
        'personal': personal,
        'perfiles': PerfilAcceso.objects.order_by('nombre'),
        'empresas': empresas,
        'modulos_permisos': modulos_permisos,
    })


@login_required
def gestion_usuario_detalle(request, pk):
    """Vista detalle de un usuario con permisos y actividad."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'No tienes permisos para ver usuarios.')
        return redirect('home')

    from django.contrib.auth.models import User
    from django.contrib.contenttypes.models import ContentType
    from core.models import AuditLog

    try:
        usuario = User.objects.select_related('personal_data', 'personal_data__perfil_acceso',
                                               'personal_data__subarea__area',
                                               'personal_data__empresa').get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('gestion_usuario_lista')

    personal = getattr(usuario, 'personal_data', None)

    # Audit logs for this user
    audit_logs = AuditLog.objects.filter(usuario=usuario).select_related('content_type')[:50]

    modulos_permisos = _get_modulos_permisos_for_user(usuario) if personal and not usuario.is_superuser else []

    return render(request, 'personal/usuarios/detalle.html', {
        'usuario': usuario,
        'personal': personal,
        'modulos_permisos': modulos_permisos,
        'audit_logs': audit_logs,
    })


@login_required
@require_http_methods(["POST"])
def gestion_usuario_bulk(request):
    """Acciones masivas: activar, desactivar, reset password."""
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    from django.contrib.auth.models import User

    action = request.POST.get('action', '')
    user_ids = request.POST.getlist('user_ids')

    if not user_ids:
        return JsonResponse({'success': False, 'error': 'No se seleccionaron usuarios.'})

    users = User.objects.filter(pk__in=user_ids, is_superuser=False)
    count = users.count()

    if action == 'activate':
        users.update(is_active=True)
        msg = f'{count} usuario(s) activados.'
    elif action == 'deactivate':
        users.update(is_active=False)
        msg = f'{count} usuario(s) desactivados.'
    elif action == 'reset_password':
        reset_count = 0
        for user in users.select_related('personal_data'):
            personal = getattr(user, 'personal_data', None)
            if personal and personal.nro_doc:
                user.set_password(personal.nro_doc.strip())
                user.save(update_fields=['password'])
                reset_count += 1
        msg = f'Password restablecida para {reset_count} usuario(s) (usando DNI).'
    else:
        return JsonResponse({'success': False, 'error': 'Accion invalida.'})

    return JsonResponse({'success': True, 'message': msg})


@login_required
@require_http_methods(["POST"])
def gestion_usuario_permiso_ajax(request):
    """AJAX: cambia un permiso individual (PermisoModulo) para un usuario."""
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    from django.contrib.auth.models import User
    from core.models import PermisoModulo, MODULOS_SISTEMA
    from personal.context_processors import invalidar_perfil

    user_id = request.POST.get('user_id')
    modulo = request.POST.get('modulo', '').strip()
    permiso = request.POST.get('permiso', '').strip()
    valor = request.POST.get('valor', '0') == '1'

    codigos_validos = {c for c, _ in MODULOS_SISTEMA}
    campos_validos = {'puede_ver', 'puede_crear', 'puede_editar', 'puede_aprobar', 'puede_exportar'}

    if modulo not in codigos_validos:
        return JsonResponse({'success': False, 'error': f'Modulo "{modulo}" invalido.'}, status=400)
    if permiso not in campos_validos:
        return JsonResponse({'success': False, 'error': f'Permiso "{permiso}" invalido.'}, status=400)

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuario no encontrado.'}, status=404)

    pm, created = PermisoModulo.objects.get_or_create(
        usuario=user,
        modulo=modulo,
        defaults={
            'puede_ver': False,
            'puede_crear': False,
            'puede_editar': False,
            'puede_aprobar': False,
            'puede_exportar': False,
        }
    )
    setattr(pm, permiso, valor)
    pm.save()

    invalidar_perfil(user.pk)

    return JsonResponse({'success': True, 'modulo': modulo, 'permiso': permiso, 'valor': valor})


@login_required
@require_http_methods(["POST"])
def gestion_usuario_prefill_perfil(request):
    """
    AJAX: Reemplaza todos los PermisoModulo de un usuario
    con los valores base de su PerfilAcceso asignado.
    """
    if not _puede_gestionar_accesos(request.user):
        return JsonResponse({'success': False, 'error': 'Sin permisos.'}, status=403)

    from django.contrib.auth.models import User
    from core.models import PermisoModulo, MODULOS_SISTEMA
    from personal.context_processors import invalidar_perfil

    user_id = request.POST.get('user_id')

    try:
        user = User.objects.get(pk=user_id)
        personal = Personal.objects.select_related('perfil_acceso').get(usuario=user)
    except (User.DoesNotExist, Personal.DoesNotExist):
        return JsonResponse({'success': False, 'error': 'Usuario o personal no encontrado.'}, status=404)

    perfil = personal.perfil_acceso
    if not perfil:
        return JsonResponse({'success': False, 'error': 'El usuario no tiene perfil asignado.'}, status=400)

    # Delete existing overrides
    PermisoModulo.objects.filter(usuario=user).delete()

    # Create new ones based on profile
    perfil_mods = perfil.as_modulos_dict()
    for codigo, _nombre in MODULOS_SISTEMA:
        key = f'mod_{codigo}'
        tiene_acceso = perfil_mods.get(key, False)
        PermisoModulo.objects.create(
            usuario=user,
            modulo=codigo,
            puede_ver=tiene_acceso,
            puede_crear=tiene_acceso,
            puede_editar=tiene_acceso,
            puede_aprobar=perfil.puede_aprobar if tiene_acceso else False,
            puede_exportar=perfil.puede_exportar if tiene_acceso else False,
        )

    invalidar_perfil(user.pk)

    return JsonResponse({'success': True, 'message': f'Permisos rellenados desde perfil "{perfil.nombre}".'})


@login_required
@require_http_methods(["POST"])
def gestion_usuario_toggle_activo(request, pk):
    """Toggle active/inactive state of a user."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'Sin permisos.')
        return redirect('home')

    from django.contrib.auth.models import User

    try:
        user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('gestion_usuario_lista')

    if user.is_superuser and not request.user.is_superuser:
        messages.error(request, 'No puedes modificar un superusuario.')
        return redirect('gestion_usuario_detalle', pk=pk)

    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])

    estado = 'activado' if user.is_active else 'desactivado'
    messages.success(request, f'Usuario "{user.username}" {estado}.')
    return redirect('gestion_usuario_detalle', pk=pk)


@login_required
@require_http_methods(["POST"])
def gestion_usuario_reset_password(request, pk):
    """Reset a user's password to their DNI."""
    if not _puede_gestionar_accesos(request.user):
        messages.error(request, 'Sin permisos.')
        return redirect('home')

    from django.contrib.auth.models import User

    try:
        user = User.objects.get(pk=pk)
        personal = Personal.objects.get(usuario=user)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('gestion_usuario_lista')
    except Personal.DoesNotExist:
        messages.error(request, 'El usuario no tiene empleado vinculado para obtener DNI.')
        return redirect('gestion_usuario_detalle', pk=pk)

    if not personal.nro_doc:
        messages.error(request, 'El empleado no tiene numero de documento.')
        return redirect('gestion_usuario_detalle', pk=pk)

    user.set_password(personal.nro_doc.strip())
    user.save(update_fields=['password'])
    messages.success(request, f'Password de "{user.username}" restablecida al DNI.')
    return redirect('gestion_usuario_detalle', pk=pk)


@login_required
@require_http_methods(["POST"])
def gestion_usuario_impersonar(request, pk):
    """
    Impersonate: Admin logs in as another user temporarily.
    Stores original user ID in session for de-impersonation.
    Only superusers can impersonate.
    """
    if not request.user.is_superuser:
        messages.error(request, 'Solo superusuarios pueden impersonar.')
        return redirect('home')

    from django.contrib.auth.models import User
    from django.contrib.auth import login

    try:
        target_user = User.objects.get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, 'Usuario no encontrado.')
        return redirect('gestion_usuario_lista')

    if target_user.is_superuser:
        messages.error(request, 'No se puede impersonar a otro superusuario.')
        return redirect('gestion_usuario_detalle', pk=pk)

    # Store original user for de-impersonation
    request.session['_impersonator_id'] = request.user.pk
    request.session['_impersonator_username'] = request.user.username

    # Login as target user
    target_user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, target_user)

    messages.info(request, f'Ahora estas navegando como "{target_user.username}". '
                           f'Cierra sesion para volver a tu cuenta de administrador.')
    return redirect('home')


@login_required
def gestion_usuario_dejar_impersonar(request):
    """
    De-impersonate: return to original admin session.
    """
    impersonator_id = request.session.get('_impersonator_id')
    if not impersonator_id:
        messages.warning(request, 'No estas impersonando a nadie.')
        return redirect('home')

    from django.contrib.auth.models import User
    from django.contrib.auth import login

    try:
        original_user = User.objects.get(pk=impersonator_id)
    except User.DoesNotExist:
        messages.error(request, 'Usuario original no encontrado.')
        return redirect('home')

    # Clean up session keys
    del request.session['_impersonator_id']
    del request.session['_impersonator_username']

    original_user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, original_user)

    messages.success(request, f'Has vuelto a tu sesion de administrador ({original_user.username}).')
    return redirect('gestion_usuario_lista')
