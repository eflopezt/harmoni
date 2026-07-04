"""
URL configuration for gestion_personal project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)

def health_check(request):
    """Health check endpoint"""
    checks = {'status': 'ok'}
    try:
        from django.db import connection
        connection.ensure_connection()
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'
        checks['status'] = 'degraded'
    return JsonResponse(checks)

@require_GET
@cache_page(86400)
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /$",
        "Disallow: /",
        "",
        "Sitemap: https://harmoni.pe/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def landing(request):
    """Landing page pública — si ya está autenticado, va al dashboard.

    En instancias de cliente (subdominio o DEMO_MODE), saltar el landing
    comercial y mandar directo al login: el cliente ya conoce el producto.
    """
    import os
    if request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('home')

    # En instancias de cliente o demo, saltar landing
    es_subdominio_cliente = bool(getattr(request, 'empresa_subdomain', None))
    es_demo = os.environ.get('DEMO_MODE', 'False').lower() in ('true', '1', 'yes')
    if es_subdominio_cliente or es_demo:
        from django.shortcuts import redirect
        return redirect('login')

    return render(request, 'landing.html')

@require_GET
@cache_page(86400)
def sitemap_xml(request):
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    xml += '  <url><loc>https://harmoni.pe/</loc><changefreq>weekly</changefreq><priority>1.0</priority></url>\n'
    xml += '</urlset>'
    return HttpResponse(xml, content_type="application/xml")

def offline_view(request):
    """Offline fallback page for PWA."""
    return render(request, 'offline.html')


def service_worker(request):
    """Sirve el Service Worker desde la raíz para que su scope sea '/'.

    Servirlo desde /static/js/ limita el scope a /static/js/ y el registro
    con scope '/' falla con SecurityError. Servirlo en /sw.js + el header
    Service-Worker-Allowed resuelve el registro PWA en dev y prod.
    """
    import os
    from django.conf import settings
    path_sw = os.path.join(settings.BASE_DIR, 'static', 'js', 'sw.js')
    try:
        with open(path_sw, encoding='utf-8') as fh:
            contenido = fh.read()
    except FileNotFoundError:
        return HttpResponse('// sw.js no encontrado', status=404,
                            content_type='application/javascript')
    resp = HttpResponse(contenido, content_type='application/javascript')
    resp['Service-Worker-Allowed'] = '/'
    resp['Cache-Control'] = 'no-cache'
    return resp


def portal_alias(request):
    """Alias /portal/ → /mi-portal/. Útil cuando el cliente teclea la URL corta."""
    from django.shortcuts import redirect
    return redirect('portal_home', permanent=False)


def demo_landing(request, demo_slug='demo'):
    """
    Landing pública por cada demo. Muestra brochure + botón "Entrar al demo"
    que redirige a demo.harmoni.pe con credenciales pre-completadas.

    Demos disponibles:
    - demo:   Grupo Sabores (gastronomía, 24 RUCs, 800 trabajadores)
    - demo2:  Pixel Motion (diseño / audiovisual, 25 trabajadores)
    """
    DEMOS = {
        'demo': {
            'titulo':       'Grupo Sabores — Gastronomía Premium',
            'descripcion':  'Cadena gastronómica con 24 RUCs y ~800 trabajadores. Restaurantes, bares y catering.',
            'plan':         'Enterprise (multi-empresa + integraciones)',
            'trabajadores': 800,
            'empresas':     24,
            'usuario':      'admin',
            'password':     'demo',
            'features':     [
                'Multi-empresa (24 RUCs consolidados)',
                'Pipeline Reclutamiento Kanban',
                'Briefing del Día (pre-shift)',
                'Cuadrícula Semanal de turnos',
                'BPM / HACCP tracking',
                'Pulse del Grupo (multi-local)',
                'Dashboard Ejecutivo',
                'Predictor IA de Rotación',
            ],
            'color':        '#0f766e',
        },
        'demo2': {
            'titulo':       'Pixel Motion — Agencia Diseño & Audiovisual',
            'descripcion':  'Agencia creativa pequeña: diseño gráfico, motion graphics, post-producción. 25 trabajadores.',
            'plan':         'Starter (S/ 149 + IGV / mes — hasta 30 colaboradores)',
            'trabajadores': 25,
            'empresas':     1,
            'usuario':      'demo2',
            'password':     'demo',
            'features':     [
                'Personal (CRUD básico)',
                'Asistencia + papeletas (admin)',
                'Planilla mensual completa',
                'Boleta PDF (descarga local)',
                'Vacaciones (gestión admin)',
                'Exportes contables y SUNAT',
                'Soporte por email',
            ],
            'color':        '#a855f7',
        },
    }
    ctx = {
        'demo_slug': demo_slug,
        'demo':      DEMOS.get(demo_slug, DEMOS['demo']),
    }
    return render(request, 'demo_landing.html', ctx)


urlpatterns = [
    path('offline/', offline_view, name='offline'),
    path('sw.js', service_worker, name='service_worker'),
    path('health/', health_check, name='health_check'),
    path('robots.txt', robots_txt, name='robots_txt'),
    # Status page público (sin prefijo /sistema/)
    path('status/', __import__('core.views_status', fromlist=['status_page']).status_page, name='status_page_public'),
    path('status/json/', __import__('core.views_status', fromlist=['status_json']).status_json, name='status_json_public'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
    path('portal/', portal_alias, name='portal_alias'),
    # Demos comerciales públicas (brochure + login)
    path('demo/',  lambda r: demo_landing(r, 'demo'),  name='demo_landing'),
    path('demo2/', lambda r: demo_landing(r, 'demo2'), name='demo2_landing'),
    # Upgrade plan (mostrado al usuario Starter cuando intenta feature bloqueada)
    path('upgrade/', __import__('core.views_upgrade', fromlist=['upgrade_plan']).upgrade_plan, name='upgrade_plan'),
    # Auto-login para demos comerciales (link directo sin teclear credenciales)
    # Solo funciona en hosts demo.*
    path('d/', __import__('core.views_demo_autologin', fromlist=['demo_landing']).demo_landing, name='demo_landing'),
    path('d/<str:slug>/', __import__('core.views_demo_autologin', fromlist=['demo_autologin']).demo_autologin, name='demo_autologin'),
    # Onboarding Plan Starter — wizard 3 pasos
    path('onboarding/starter/',       __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step1']).onboarding_starter_step1, name='onboarding_starter_step1'),
    path('onboarding/starter/admin/', __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step2']).onboarding_starter_step2, name='onboarding_starter_step2'),
    path('onboarding/starter/listo/', __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step3']).onboarding_starter_step3, name='onboarding_starter_step3'),
    # Mi cuenta — dashboard del plan vigente
    path('cuenta/plan/', __import__('core.views_mi_cuenta', fromlist=['mi_cuenta_plan']).mi_cuenta_plan, name='mi_cuenta_plan'),
    # Cobro online de suscripciones — MercadoPago Checkout Pro
    path('cuenta/plan/pagar/', __import__('core.views_pagos', fromlist=['iniciar_pago']).iniciar_pago, name='pago_iniciar'),
    path('cuenta/plan/pago/retorno/', __import__('core.views_pagos', fromlist=['retorno_pago']).retorno_pago, name='pago_retorno'),
    path('webhooks/mercadopago/', __import__('core.views_pagos', fromlist=['webhook_mercadopago']).webhook_mercadopago, name='webhook_mercadopago'),
    # Tour interactivo demo Sabores del Sur Enterprise
    path('tour/edo/', __import__('core.views_tour_edo', fromlist=['tour_edo']).tour_edo, name='tour_edo'),
    # Centro de Comando — dashboard ejecutivo "1 vista"
    path('comando/', __import__('core.views_centro_comando', fromlist=['centro_comando']).centro_comando, name='centro_comando'),
    # Calculadora ROI (público, sin login)
    path('roi/', __import__('core.views_roi', fromlist=['calculadora_roi']).calculadora_roi, name='calculadora_roi'),
    # QR para demos en vivo (escaneo durante presentación)
    path('qr-demo/', __import__('core.views_qr_demo', fromlist=['qr_demo']).qr_demo, name='qr_demo'),
    # Reporte ejecutivo PDF — "El Grupo en 1 página"
    path('reportes/grupo-ejecutivo/', __import__('core.views_reporte_ejecutivo_grupo', fromlist=['reporte_grupo_ejecutivo']).reporte_grupo_ejecutivo, name='reporte_grupo_ejecutivo'),
    # FAQ pública gastronomía
    path('faq/', __import__('core.views_faq', fromlist=['faq_publica']).faq_publica, name='faq_publica'),
    # Caso de uso comercial — Grupo Sabores (público, sin login)
    path('casos/edo/', __import__('core.views_caso_edo', fromlist=['caso_edo']).caso_edo, name='caso_edo'),
    # Página pública de precios (los 4 planes)
    path('precios/', __import__('core.views_precios', fromlist=['precios']).precios, name='precios_publico'),
    # Página pública de seguridad y compliance
    path('seguridad/', __import__('core.views_seguridad', fromlist=['seguridad']).seguridad, name='seguridad_publica'),
    # RFC 9116 — contacto para reportes de vulnerabilidades
    path('.well-known/security.txt', __import__('core.views_seguridad', fromlist=['security_txt']).security_txt, name='security_txt'),
    # Página pública de clientes y testimonios
    path('clientes/', __import__('core.views_clientes', fromlist=['clientes']).clientes, name='clientes_publico'),
    # Sales Hub — hub central de material comercial
    path('h/', __import__('core.views_sales_hub', fromlist=['sales_hub']).sales_hub, name='sales_hub'),
    # Demo guiado contratación 5 minutos
    path('demos/contratar/', __import__('core.views_demo_contratar', fromlist=['demo_contratar']).demo_contratar, name='demo_contratar'),
    path('admin/', admin.site.urls),
    # MFA TOTP (segundo factor con app autenticadora)
    path('cuenta/2fa/', include('core.urls_mfa')),
    path('', include('personal.urls')),
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    path('api/v1/', include('core.api_urls')),
    path('api/', include('personal.api_urls')),  # backward compat
    path('asistencia/', include('asistencia.urls')),
    path('mi-portal/', include('portal.urls')),
    path('cierre/', include('cierre.urls')),
    path('documentos/', include('documentos.urls')),
    path('sistema/', include('core.urls')),
    # Shortcut: /buscar/ → same views as /sistema/buscar/ (avoids prefix)
    path('buscar/', include(('core.urls_buscar', 'buscar'))),
    path('prestamos/', include('prestamos.urls')),
    path('descuentos/', include('descuentos.urls')),
    path('viaticos/', include('viaticos.urls')),
    path('vacaciones/', include('vacaciones.urls')),
    path('capacitaciones/', include('capacitaciones.urls')),
    path('disciplinaria/', include('disciplinaria.urls')),
    path('salarios/', include('salarios.urls')),
    path('evaluaciones/', include('evaluaciones.urls')),
    path('encuestas/', include('encuestas.urls')),
    path('calendario/', include('calendario.urls')),
    path('onboarding/', include('onboarding.urls')),
    path('reclutamiento/', include('reclutamiento.urls')),
    path('comunicaciones/', include('comunicaciones.urls')),
    path('analytics/', include('analytics.urls')),
    path('integraciones/', include('integraciones.urls')),
    path('nominas/', include('nominas.urls')),
    # Calculadora pública sin login (SEO + lead gen)
    path('calculadora/', __import__('nominas.views_calculadora', fromlist=['calculadora_publica']).calculadora_publica, name='calculadora_publica'),
    path('api/calculadora/', __import__('nominas.views_calculadora', fromlist=['calculadora_api']).calculadora_api, name='api_calculadora'),
    path('api/health/nominas/', __import__('nominas.views_health', fromlist=['nominas_health']).nominas_health, name='api_health_nominas'),
    path('empresas/', include('empresas.urls')),
    path('workflows/', include('workflows.urls')),
]

# Add debug toolbar URLs in development
if settings.DEBUG:
    try:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns
    except ImportError:
        pass
    
    # Serve media files in development
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
