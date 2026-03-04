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
    ).order_by('apellidos_nombres')

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
