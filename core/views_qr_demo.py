"""
QR de demo mobile — para que el cliente escanee y vea el portal en su celular.

URL: /qr-demo/

Muestra un QR grande con la URL del portal del trabajador (con auto-login).
Útil durante presentación: cliente saca su celular, escanea, y ve el portal en vivo.

Auto-login simulado: el QR apunta a /d/worker-mobile/ que es una variante de
/d/<slug>/ con un user worker default (Hans Benavides).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def qr_demo(request):
    """
    Vista que muestra QR grande para que el cliente escanee con su mobile.
    """
    # URLs públicas con auto-login para mobile demo
    qr_urls = [
        {
            'titulo':     'Portal del trabajador',
            'descripcion': 'Boletas, vacaciones, asistencia, préstamos — desde el celular',
            'url':        'https://demo.harmoni.pe/d/enterprise/',
            'color':      '#0f766e',
            'icon':       'fa-mobile-alt',
        },
        {
            'titulo':     'Plan Starter (Pixel Motion)',
            'descripcion': 'Vista del demo de la agencia de diseño con Plan Starter',
            'url':        'https://demo.harmoni.pe/d/starter/',
            'color':      '#94a3b8',
            'icon':       'fa-leaf',
        },
        {
            'titulo':     'Calculadora ROI',
            'descripcion': 'Para que el cliente calcule su ahorro en vivo',
            'url':        'https://demo.harmoni.pe/roi/',
            'color':      '#16a34a',
            'icon':       'fa-calculator',
        },
        {
            'titulo':     'Tour Demo Sabores del Sur',
            'descripcion': '12 features estrella con CTAs',
            'url':        'https://demo.harmoni.pe/tour/edo/',
            'color':      '#a855f7',
            'icon':       'fa-rocket',
        },
    ]
    return render(request, 'qr_demo/index.html', {'qr_urls': qr_urls})
