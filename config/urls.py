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


def portal_alias(request):
    """Alias /portal/ → /mi-portal/. Útil cuando el cliente teclea la URL corta."""
    from django.shortcuts import redirect
    return redirect('portal_home', permanent=False)


def demo_landing(request, demo_slug='demo'):
    """
    Landing pública por cada demo. Muestra brochure + botón "Entrar al demo"
    que redirige a demo.harmoni.pe con credenciales pre-completadas.

    Demos disponibles:
    - demo:   Grupo EDO (gastronomía, 24 RUCs, 800 trabajadores)
    - demo2:  Pixel Motion (diseño / audiovisual, 25 trabajadores)
    """
    DEMOS = {
        'demo': {
            'titulo':       'Grupo EDO — Gastronomía Premium',
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
    path('d/<str:slug>/', __import__('core.views_demo_autologin', fromlist=['demo_autologin']).demo_autologin, name='demo_autologin'),
    # Onboarding Plan Starter — wizard 3 pasos
    path('onboarding/starter/',       __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step1']).onboarding_starter_step1, name='onboarding_starter_step1'),
    path('onboarding/starter/admin/', __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step2']).onboarding_starter_step2, name='onboarding_starter_step2'),
    path('onboarding/starter/listo/', __import__('core.views_onboarding_starter', fromlist=['onboarding_starter_step3']).onboarding_starter_step3, name='onboarding_starter_step3'),
    # Mi cuenta — dashboard del plan vigente
    path('cuenta/plan/', __import__('core.views_mi_cuenta', fromlist=['mi_cuenta_plan']).mi_cuenta_plan, name='mi_cuenta_plan'),
    path('admin/', admin.site.urls),
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
    path('empresas/', include('empresas.urls')),
    path('workflows/', include('workflows.urls')),
    path('', include('wa_marketing.urls')),
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
