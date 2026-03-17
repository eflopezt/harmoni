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
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /login/",
        "Disallow: /asistencia/ia/",
        "Crawl-delay: 10",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")

def landing(request):
    """Landing page pública — si ya está autenticado, va al dashboard."""
    if request.user.is_authenticated:
        from django.shortcuts import redirect
        return redirect('home')
    return render(request, 'landing.html')

def offline_view(request):
    """Offline fallback page for PWA."""
    return render(request, 'offline.html')

urlpatterns = [
    path('offline/', offline_view, name='offline'),
    path('health/', health_check, name='health_check'),
    path('robots.txt', robots_txt, name='robots_txt'),
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
