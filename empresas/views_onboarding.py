"""
Empresas -- Wizard de onboarding multi-paso para nuevos clientes.

5 pasos:
  1. Datos de empresa (RUC, razon social, direccion, regimen, subdominio)
  2. Configuracion de email (SMTP)
  3. Usuario admin (superuser vinculado a la empresa)
  4. Datos iniciales (seeds + importacion Excel opcional)
  5. Resumen y enlace directo

Almacena estado en request.session['onboarding_data'] entre pasos.
"""
import json
import logging
import re
import smtplib
from email.mime.text import MIMEText

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.core.management import call_command
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from .models import Empresa

logger = logging.getLogger(__name__)

solo_admin = user_passes_test(lambda u: u.is_superuser)

SESSION_KEY = 'onboarding_data'

# ─── Helpers ────────────────────────────────────────────────────────


def _get_onboarding_data(request):
    """Return mutable dict from session (or empty dict)."""
    return request.session.get(SESSION_KEY, {})


def _set_onboarding_data(request, data):
    request.session[SESSION_KEY] = data
    request.session.modified = True


def _clear_onboarding_data(request):
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True


def _suggest_subdomain(nombre):
    """Generate a clean slug from nombre comercial."""
    if not nombre:
        return ''
    slug = slugify(nombre)
    # Truncate to 50 chars max
    return slug[:50]


# ─── Step 1: Company Info ───────────────────────────────────────────


@login_required
@solo_admin
def step1_company(request):
    data = _get_onboarding_data(request)

    if request.method == 'POST':
        ruc = request.POST.get('ruc', '').strip()
        razon_social = request.POST.get('razon_social', '').strip()
        nombre_comercial = request.POST.get('nombre_comercial', '').strip()
        direccion = request.POST.get('direccion', '').strip()
        telefono = request.POST.get('telefono', '').strip()
        email_rrhh = request.POST.get('email_rrhh', '').strip()
        regimen_laboral = request.POST.get('regimen_laboral', 'GENERAL')
        sector = request.POST.get('sector', 'PRIVADO')
        subdominio = request.POST.get('subdominio', '').strip().lower()

        # Validation
        errors = []
        if not ruc or len(ruc) != 11 or not ruc.isdigit():
            errors.append('El RUC debe tener exactamente 11 digitos.')
        if not razon_social:
            errors.append('La razon social es requerida.')
        if Empresa.objects.filter(ruc=ruc).exists():
            errors.append(f'Ya existe una empresa con RUC {ruc}.')
        if subdominio:
            if not re.match(r'^[a-z0-9]([a-z0-9-]*[a-z0-9])?$', subdominio):
                errors.append('El subdominio solo puede contener letras, numeros y guiones.')
            if Empresa.objects.filter(subdominio=subdominio).exists():
                errors.append(f'El subdominio "{subdominio}" ya esta en uso.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'empresas/onboarding/step1_company.html', {
                'step': 1,
                'data': request.POST,
                'regimen_choices': Empresa.REGIMEN_CHOICES,
                'sector_choices': Empresa.SECTOR_CHOICES,
            })

        data['company'] = {
            'ruc': ruc,
            'razon_social': razon_social,
            'nombre_comercial': nombre_comercial,
            'direccion': direccion,
            'telefono': telefono,
            'email_rrhh': email_rrhh,
            'regimen_laboral': regimen_laboral,
            'sector': sector,
            'subdominio': subdominio or _suggest_subdomain(nombre_comercial or razon_social),
        }
        _set_onboarding_data(request, data)
        return redirect('onboarding_step2')

    return render(request, 'empresas/onboarding/step1_company.html', {
        'step': 1,
        'data': data.get('company', {}),
        'regimen_choices': Empresa.REGIMEN_CHOICES,
        'sector_choices': Empresa.SECTOR_CHOICES,
    })


# ─── Step 2: Email Config ──────────────────────────────────────────


@login_required
@solo_admin
def step2_email(request):
    data = _get_onboarding_data(request)
    if 'company' not in data:
        messages.warning(request, 'Complete primero el paso 1.')
        return redirect('onboarding_step1')

    if request.method == 'POST':
        proveedor = request.POST.get('email_proveedor', 'NONE')
        data['email'] = {
            'email_proveedor': proveedor,
            'email_host': request.POST.get('email_host', '').strip(),
            'email_port': int(request.POST.get('email_port', 587) or 587),
            'email_use_tls': request.POST.get('email_use_tls') == '1',
            'email_use_ssl': request.POST.get('email_use_ssl') == '1',
            'email_host_user': request.POST.get('email_host_user', '').strip(),
            'email_host_password': request.POST.get('email_host_password', '').strip(),
            'email_from': request.POST.get('email_from', '').strip(),
            'email_reply_to': request.POST.get('email_reply_to', '').strip(),
        }
        _set_onboarding_data(request, data)
        return redirect('onboarding_step3')

    return render(request, 'empresas/onboarding/step2_email.html', {
        'step': 2,
        'data': data.get('email', {}),
        'proveedor_choices': Empresa.PROVEEDOR_EMAIL_CHOICES,
    })


@login_required
@solo_admin
@require_POST
def test_smtp(request):
    """AJAX endpoint to test SMTP connection."""
    host = request.POST.get('email_host', '').strip()
    port = int(request.POST.get('email_port', 587) or 587)
    user = request.POST.get('email_host_user', '').strip()
    password = request.POST.get('email_host_password', '').strip()
    use_tls = request.POST.get('email_use_tls') == '1'
    use_ssl = request.POST.get('email_use_ssl') == '1'

    if not host or not user or not password:
        return JsonResponse({
            'ok': False,
            'message': 'Servidor, usuario y contrasena son requeridos.',
        })

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(host, port, timeout=10)
        else:
            server = smtplib.SMTP(host, port, timeout=10)
            if use_tls:
                server.starttls()
        server.login(user, password)
        server.quit()
        return JsonResponse({'ok': True, 'message': 'Conexion SMTP exitosa.'})
    except smtplib.SMTPAuthenticationError:
        return JsonResponse({'ok': False, 'message': 'Error de autenticacion. Verifique usuario y contrasena (usar App Password para Gmail).'})
    except smtplib.SMTPConnectError:
        return JsonResponse({'ok': False, 'message': 'No se pudo conectar al servidor SMTP. Verifique host y puerto.'})
    except Exception as exc:
        return JsonResponse({'ok': False, 'message': f'Error: {str(exc)}'})


# ─── Step 3: Admin User ────────────────────────────────────────────


@login_required
@solo_admin
def step3_admin(request):
    data = _get_onboarding_data(request)
    if 'company' not in data:
        messages.warning(request, 'Complete primero el paso 1.')
        return redirect('onboarding_step1')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()

        errors = []
        if not username:
            errors.append('El nombre de usuario es requerido.')
        elif User.objects.filter(username=username).exists():
            errors.append(f'El usuario "{username}" ya existe.')
        if not email:
            errors.append('El email es requerido.')
        if not password1:
            errors.append('La contrasena es requerida.')
        elif len(password1) < 8:
            errors.append('La contrasena debe tener al menos 8 caracteres.')
        elif password1 != password2:
            errors.append('Las contrasenas no coinciden.')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'empresas/onboarding/step3_admin.html', {
                'step': 3,
                'data': request.POST,
            })

        data['admin'] = {
            'username': username,
            'email': email,
            'password': password1,
            'first_name': first_name,
            'last_name': last_name,
        }
        _set_onboarding_data(request, data)
        return redirect('onboarding_step4')

    return render(request, 'empresas/onboarding/step3_admin.html', {
        'step': 3,
        'data': data.get('admin', {}),
    })


# ─── Step 4: Initial Data ──────────────────────────────────────────


@login_required
@solo_admin
def step4_data(request):
    data = _get_onboarding_data(request)
    if 'company' not in data:
        messages.warning(request, 'Complete primero el paso 1.')
        return redirect('onboarding_step1')

    if request.method == 'POST':
        run_seeds = request.POST.get('run_seeds') == '1'
        excel_file = request.FILES.get('excel_file')

        data['initial'] = {
            'run_seeds': run_seeds,
            'has_excel': bool(excel_file),
        }

        # Store the excel file temporarily if provided
        if excel_file:
            import os
            import tempfile
            tmp_dir = os.path.join(settings.MEDIA_ROOT, 'onboarding_tmp')
            os.makedirs(tmp_dir, exist_ok=True)
            tmp_path = os.path.join(tmp_dir, f'employees_{data["company"]["ruc"]}.xlsx')
            with open(tmp_path, 'wb') as f:
                for chunk in excel_file.chunks():
                    f.write(chunk)
            data['initial']['excel_path'] = tmp_path

        _set_onboarding_data(request, data)
        return redirect('onboarding_step5')

    return render(request, 'empresas/onboarding/step4_data.html', {
        'step': 4,
        'data': data.get('initial', {}),
    })


# ─── Step 5: Summary & Execute ─────────────────────────────────────


@login_required
@solo_admin
def step5_summary(request):
    data = _get_onboarding_data(request)
    if 'company' not in data:
        messages.warning(request, 'Complete primero el paso 1.')
        return redirect('onboarding_step1')

    if request.method == 'POST':
        # Execute everything
        results = _execute_onboarding(request, data)
        _clear_onboarding_data(request)

        if results.get('success'):
            messages.success(request, 'Empresa configurada exitosamente. Todo listo para empezar.')
            return redirect('onboarding_complete', empresa_id=results['empresa_id'])
        else:
            for err in results.get('errors', []):
                messages.error(request, err)
            return render(request, 'empresas/onboarding/step5_summary.html', {
                'step': 5,
                'data': data,
            })

    return render(request, 'empresas/onboarding/step5_summary.html', {
        'step': 5,
        'data': data,
    })


@login_required
@solo_admin
def onboarding_complete(request, empresa_id):
    """Final page after successful onboarding."""
    from django.shortcuts import get_object_or_404
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    return render(request, 'empresas/onboarding/complete.html', {
        'empresa': empresa,
    })


# ─── Execution Engine ──────────────────────────────────────────────


def _execute_onboarding(request, data):
    """
    Execute all onboarding steps atomically.
    Returns dict with 'success', 'empresa_id', and any 'errors'.
    """
    from django.db import transaction
    errors = []
    empresa = None
    admin_user = None

    try:
        with transaction.atomic():
            # 1. Create the Empresa
            company = data['company']
            empresa = Empresa.objects.create(
                ruc=company['ruc'],
                razon_social=company['razon_social'],
                nombre_comercial=company.get('nombre_comercial', ''),
                direccion=company.get('direccion', ''),
                telefono=company.get('telefono', ''),
                email_rrhh=company.get('email_rrhh', ''),
                regimen_laboral=company.get('regimen_laboral', 'GENERAL'),
                sector=company.get('sector', 'PRIVADO'),
                subdominio=company.get('subdominio') or None,
                activa=True,
                creado_por=request.user,
            )

            # 2. Apply email config
            email_data = data.get('email', {})
            if email_data and email_data.get('email_proveedor', 'NONE') != 'NONE':
                empresa.email_proveedor = email_data['email_proveedor']
                empresa.email_host = email_data.get('email_host', '')
                empresa.email_port = email_data.get('email_port', 587)
                empresa.email_use_tls = email_data.get('email_use_tls', True)
                empresa.email_use_ssl = email_data.get('email_use_ssl', False)
                empresa.email_host_user = email_data.get('email_host_user', '')
                empresa.email_host_password = email_data.get('email_host_password', '')
                empresa.email_from = email_data.get('email_from', '')
                empresa.email_reply_to = email_data.get('email_reply_to', '')
                empresa.save()

            # 3. Create admin user
            admin_data = data.get('admin', {})
            if admin_data:
                admin_user = User.objects.create_superuser(
                    username=admin_data['username'],
                    email=admin_data['email'],
                    password=admin_data['password'],
                    first_name=admin_data.get('first_name', ''),
                    last_name=admin_data.get('last_name', ''),
                )
                # Link via Personal record
                from personal.models import Personal
                Personal.objects.create(
                    empresa=empresa,
                    usuario=admin_user,
                    tipo_doc='DNI',
                    nro_doc=f'ADMIN-{empresa.ruc}',
                    apellidos_nombres=f"{admin_data.get('last_name', '')} {admin_data.get('first_name', '')}".strip() or admin_data['username'],
                    cargo='Administrador del Sistema',
                    tipo_trab='Empleado',
                    estado='Activo',
                    correo_corporativo=admin_data['email'],
                )

        # 4. Run seeds (outside transaction -- management commands manage their own)
        initial = data.get('initial', {})
        if initial.get('run_seeds'):
            try:
                call_command('setup_harmoni', '--no-input', verbosity=0)
                logger.info(f'Seeds ejecutados para empresa {empresa.ruc}')
            except Exception as exc:
                logger.warning(f'Error ejecutando seeds: {exc}')
                errors.append(f'Advertencia: algunos datos iniciales no se cargaron ({exc}).')

        # 5. Import employees from Excel
        excel_path = initial.get('excel_path')
        if excel_path:
            try:
                import_count = _import_employees_from_excel(empresa, excel_path)
                logger.info(f'{import_count} empleados importados para empresa {empresa.ruc}')
            except Exception as exc:
                logger.warning(f'Error importando Excel: {exc}')
                errors.append(f'Advertencia: no se pudo importar el Excel ({exc}).')
            finally:
                # Cleanup temp file
                import os
                try:
                    os.remove(excel_path)
                except OSError:
                    pass

        # 6. Send WhatsApp notification (best-effort)
        if admin_user and empresa:
            try:
                _send_whatsapp_welcome(empresa, admin_user)
            except Exception:
                pass  # Non-critical

        return {
            'success': True,
            'empresa_id': empresa.pk,
            'errors': errors,
        }

    except Exception as exc:
        logger.exception(f'Error en onboarding: {exc}')
        return {
            'success': False,
            'errors': [f'Error al crear la empresa: {str(exc)}'],
        }


def _import_employees_from_excel(empresa, filepath):
    """
    Import employees from an Excel file.
    Expects columns: nro_doc, apellidos_nombres, cargo, sueldo_base
    Optional: tipo_doc, tipo_trab, email, celular, fecha_alta, area
    Returns count of imported records.
    """
    import pandas as pd
    from personal.models import Personal

    df = pd.read_excel(filepath)

    # Normalize column names
    df.columns = [c.strip().lower().replace(' ', '_') for c in df.columns]

    # Map common column name variants
    col_map = {
        'documento': 'nro_doc',
        'dni': 'nro_doc',
        'numero_documento': 'nro_doc',
        'nombre': 'apellidos_nombres',
        'nombres': 'apellidos_nombres',
        'apellidos_y_nombres': 'apellidos_nombres',
        'nombre_completo': 'apellidos_nombres',
        'puesto': 'cargo',
        'posicion': 'cargo',
        'sueldo': 'sueldo_base',
        'remuneracion': 'sueldo_base',
        'telefono': 'celular',
        'correo': 'correo_corporativo',
        'email': 'correo_corporativo',
    }
    df.rename(columns={k: v for k, v in col_map.items() if k in df.columns}, inplace=True)

    required = ['nro_doc', 'apellidos_nombres']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f'Columnas requeridas faltantes: {", ".join(missing)}')

    count = 0
    for _, row in df.iterrows():
        nro_doc = str(row.get('nro_doc', '')).strip()
        nombre = str(row.get('apellidos_nombres', '')).strip()
        if not nro_doc or not nombre:
            continue

        # Skip if already exists
        if Personal.objects.filter(nro_doc=nro_doc).exists():
            continue

        Personal.objects.create(
            empresa=empresa,
            nro_doc=nro_doc,
            apellidos_nombres=nombre,
            tipo_doc=str(row.get('tipo_doc', 'DNI')).strip() or 'DNI',
            cargo=str(row.get('cargo', 'Empleado')).strip() or 'Empleado',
            tipo_trab=str(row.get('tipo_trab', 'Empleado')).strip() or 'Empleado',
            sueldo_base=row.get('sueldo_base') if pd.notna(row.get('sueldo_base')) else None,
            celular=str(row.get('celular', '')).strip() if pd.notna(row.get('celular')) else '',
            correo_corporativo=str(row.get('correo_corporativo', '')).strip() if pd.notna(row.get('correo_corporativo')) else '',
            estado='Activo',
        )
        count += 1

    return count


def _send_whatsapp_welcome(empresa, admin_user):
    """
    Send a WhatsApp welcome notification to the admin (best-effort).
    Uses the system's primary empresa WhatsApp config if available.
    """
    try:
        principal = Empresa.objects.filter(es_principal=True).first()
        if not principal or not principal.tiene_whatsapp_configurado:
            return

        # Only send if we have a phone number for the admin
        from personal.models import Personal
        personal = Personal.objects.filter(usuario=admin_user).first()
        if not personal or not personal.celular:
            return

        message = (
            f"Bienvenido a Harmoni ERP.\n\n"
            f"Se ha configurado la empresa *{empresa.nombre_display}* (RUC: {empresa.ruc}).\n"
            f"Su usuario de acceso es: *{admin_user.username}*\n\n"
            f"Puede acceder al sistema en: https://{empresa.subdominio}.harmoni.pe"
        )

        from comunicaciones.services import enviar_whatsapp
        enviar_whatsapp(principal, personal.celular, message)
    except Exception as exc:
        logger.debug(f'WhatsApp welcome not sent: {exc}')


# ─── AJAX: suggest subdomain ───────────────────────────────────────


@login_required
@solo_admin
def suggest_subdomain(request):
    """AJAX endpoint returning a subdomain suggestion from a name."""
    nombre = request.GET.get('nombre', '')
    suggestion = _suggest_subdomain(nombre)
    # Check availability
    available = not Empresa.objects.filter(subdominio=suggestion).exists() if suggestion else True
    return JsonResponse({
        'subdomain': suggestion,
        'available': available,
    })
