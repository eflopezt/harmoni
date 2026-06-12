"""
MFA TOTP con apps autenticadoras (Google Authenticator, Authy, 1Password…).

Flujo:
  /cuenta/2fa/             — estado + activar/desactivar
  /cuenta/2fa/activar/     — genera device sin confirmar + QR; POST código → confirma
  /cuenta/2fa/verificar/   — segundo factor al iniciar sesión (lo fuerza
                             MFAEnforceMiddleware si hay device confirmado)
  /cuenta/2fa/desactivar/  — POST con contraseña → elimina los devices

El QR se genera localmente (librería qrcode, ya en requirements) — el
secreto TOTP nunca sale del servidor hacia terceros.
"""
import base64
import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from django_otp import login as otp_login
from django_otp.plugins.otp_totp.models import TOTPDevice


def _qr_data_uri(texto: str) -> str:
    import qrcode
    img = qrcode.make(texto)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()


@login_required
def mfa_estado(request):
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    return render(request, 'cuenta/mfa_estado.html', {
        'device': device,
        'verificado': request.user.is_verified(),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def mfa_activar(request):
    if TOTPDevice.objects.filter(user=request.user, confirmed=True).exists():
        messages.info(request, 'Ya tienes MFA activo.')
        return redirect('mfa_estado')

    # Device pendiente de confirmar (uno solo; regenerar = nuevo secreto)
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    if device is None or request.GET.get('regenerar'):
        TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
        device = TOTPDevice.objects.create(
            user=request.user, name='Autenticador', confirmed=False,
        )

    if request.method == 'POST':
        token = (request.POST.get('token') or '').strip().replace(' ', '')
        if device.verify_token(token):
            device.confirmed = True
            device.save(update_fields=['confirmed'])
            otp_login(request, device)
            messages.success(
                request,
                'MFA activado. Desde ahora, al iniciar sesión se te pedirá '
                'el código de tu app autenticadora.'
            )
            return redirect('mfa_estado')
        messages.error(request, 'Código incorrecto. Verifica la hora de tu teléfono e intenta de nuevo.')

    return render(request, 'cuenta/mfa_activar.html', {
        'qr': _qr_data_uri(device.config_url),
        'secreto': base64.b32encode(device.bin_key).decode(),
    })


@login_required
@require_http_methods(['GET', 'POST'])
def mfa_verificar(request):
    device = TOTPDevice.objects.filter(user=request.user, confirmed=True).first()
    if device is None:
        return redirect('home')

    if request.method == 'POST':
        token = (request.POST.get('token') or '').strip().replace(' ', '')
        if device.verify_token(token):
            otp_login(request, device)
            nxt = request.POST.get('next') or request.GET.get('next') or ''
            if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
                return redirect(nxt)
            return redirect('home')
        messages.error(request, 'Código incorrecto.')

    return render(request, 'cuenta/mfa_verificar.html', {
        'next': request.GET.get('next', ''),
    })


@login_required
@require_http_methods(['POST'])
def mfa_desactivar(request):
    pwd = request.POST.get('password') or ''
    if not request.user.check_password(pwd):
        messages.error(request, 'Contraseña incorrecta — MFA sigue activo.')
        return redirect('mfa_estado')
    TOTPDevice.objects.filter(user=request.user).delete()
    messages.success(request, 'MFA desactivado.')
    return redirect('mfa_estado')
