"""
Wizard de onboarding — Plan Starter.

URL: /onboarding/starter/

Guía a un cliente nuevo en 3 pasos:
  1. Datos de la empresa (RUC, razón social, contacto)
  2. Primer trabajador (admin del sistema)
  3. Activación (resumen + crear)

Pensado para que el cliente reciba el link después de comprar el plan y
auto-configure su instancia. Para producción real se complementa con
docker-compose.starter (containers aislados por cliente).
"""
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.backends import ModelBackend
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from empresas.models import Empresa


User = get_user_model()


def _session_data(request):
    """Datos parciales del wizard guardados en session."""
    return request.session.setdefault('onboarding_starter', {})


def _save_session(request, data):
    request.session['onboarding_starter'] = data
    request.session.modified = True


def _validate_step1(post):
    """Valida datos paso 1. Devuelve (data, errors)."""
    data = {
        'ruc':          (post.get('ruc') or '').strip(),
        'razon_social': (post.get('razon_social') or '').strip(),
        'email_rrhh':   (post.get('email_rrhh') or '').strip(),
        'telefono':     (post.get('telefono') or '').strip(),
    }
    errors = []
    if not data['ruc'] or len(data['ruc']) != 11 or not data['ruc'].isdigit():
        errors.append('RUC debe tener 11 dígitos.')
    if not data['razon_social']:
        errors.append('Razón social es obligatoria.')
    if Empresa.objects.filter(ruc=data['ruc']).exists():
        errors.append(f'Ya existe una empresa con RUC {data["ruc"]}.')
    return data, errors


def _validate_step2(post):
    data = {
        'username':       (post.get('username') or '').strip().lower(),
        'first_name':     (post.get('first_name') or '').strip(),
        'last_name':      (post.get('last_name') or '').strip(),
        'email':          (post.get('email') or '').strip(),
        'password':       post.get('password') or '',
        'password_confirm': post.get('password_confirm') or '',
    }
    errors = []
    if not data['username'] or len(data['username']) < 3:
        errors.append('Usuario debe tener al menos 3 caracteres.')
    if User.objects.filter(username=data['username']).exists():
        errors.append(f'El usuario "{data["username"]}" ya existe.')
    if not data['first_name'] or not data['last_name']:
        errors.append('Nombres y apellidos son obligatorios.')
    if not data['email'] or '@' not in data['email']:
        errors.append('Email inválido.')
    if len(data['password']) < 8:
        errors.append('Contraseña debe tener al menos 8 caracteres.')
    if data['password'] != data['password_confirm']:
        errors.append('Las contraseñas no coinciden.')
    # No guardamos la confirmación en session
    data.pop('password_confirm')
    return data, errors


@require_http_methods(['GET', 'POST'])
def onboarding_starter_step1(request):
    """Paso 1 — Datos de la empresa."""
    data = _session_data(request).get('empresa', {})
    errors = []
    if request.method == 'POST':
        data, errors = _validate_step1(request.POST)
        if not errors:
            session = _session_data(request)
            session['empresa'] = data
            _save_session(request, session)
            return redirect('onboarding_starter_step2')
    return render(request, 'onboarding/starter_step1.html', {
        'step': 1, 'total_steps': 3, 'data': data, 'errors': errors,
    })


@require_http_methods(['GET', 'POST'])
def onboarding_starter_step2(request):
    """Paso 2 — Primer usuario admin."""
    session = _session_data(request)
    if 'empresa' not in session:
        messages.warning(request, 'Completa primero los datos de tu empresa.')
        return redirect('onboarding_starter_step1')

    data = session.get('admin', {})
    errors = []
    if request.method == 'POST':
        data, errors = _validate_step2(request.POST)
        if not errors:
            session['admin'] = data
            _save_session(request, session)
            return redirect('onboarding_starter_step3')
    return render(request, 'onboarding/starter_step2.html', {
        'step': 2, 'total_steps': 3, 'data': data, 'errors': errors,
    })


@require_http_methods(['GET', 'POST'])
def onboarding_starter_step3(request):
    """Paso 3 — Resumen y activación."""
    session = _session_data(request)
    if 'empresa' not in session or 'admin' not in session:
        messages.warning(request, 'Completa los pasos previos.')
        return redirect('onboarding_starter_step1')

    if request.method == 'POST':
        # Crear empresa + user + login
        emp_data = session['empresa']
        adm_data = session['admin']

        empresa = Empresa.objects.create(
            ruc=emp_data['ruc'],
            razon_social=emp_data['razon_social'],
            email_rrhh=emp_data.get('email_rrhh', ''),
            telefono=emp_data.get('telefono', ''),
            plan='ASISTENCIA',   # plan de entrada (antes 'STARTER')
            activa=True,
            es_principal=False,  # no tocar empresa principal
        )
        user = User.objects.create_user(
            username=adm_data['username'],
            email=adm_data['email'],
            password=adm_data['password'],
            first_name=adm_data['first_name'],
            last_name=adm_data['last_name'],
        )
        # Marcar como admin
        user.is_staff = True
        user.save(update_fields=['is_staff'])

        # Limpiar wizard de session
        request.session.pop('onboarding_starter', None)

        # Auto-login
        user.backend = f'{ModelBackend.__module__}.{ModelBackend.__name__}'
        login(request, user)
        messages.success(
            request,
            f'¡Bienvenido a Harmoni! Tu Plan Starter está activo. '
            f'Empresa: {empresa.razon_social}.'
        )
        return redirect('/')

    return render(request, 'onboarding/starter_step3.html', {
        'step': 3, 'total_steps': 3,
        'empresa': session['empresa'],
        'admin':   session['admin'],
    })
