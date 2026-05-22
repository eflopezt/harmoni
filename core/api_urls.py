"""
Harmoni ERP — Central API v1 Router.
Agrega todos los endpoints de módulos bajo /api/v1/.
"""
from django.urls import path, include
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_health(request):
    """Health check endpoint — sin autenticación requerida."""
    return Response({
        'status': 'ok',
        'version': '1.0.0',
        'app': 'Harmoni ERP',
    })


urlpatterns = [
    # ── Health ──
    path('health/', api_health, name='api_health'),

    # ── Auth (JWT) ──
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # ── OpenAPI Schema + Docs ──
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # ── Plan / billing ──
    path('me/plan/', __import__('core.api_plan', fromlist=['api_me_plan']).api_me_plan, name='api_me_plan'),

    # ── Module APIs ──
    path('personal/', include('personal.api_urls')),
    path('asistencia/', include('asistencia.api_urls')),
    path('vacaciones/', include('vacaciones.api_urls')),
    path('prestamos/', include('prestamos.api_urls')),
    path('documentos/', include('documentos.api_urls')),
    path('capacitaciones/', include('capacitaciones.api_urls')),
    path('evaluaciones/', include('evaluaciones.api_urls')),
    path('encuestas/', include('encuestas.api_urls')),
    path('salarios/', include('salarios.api_urls')),
    path('reclutamiento/', include('reclutamiento.api_urls')),
    path('comunicaciones/', include('comunicaciones.api_urls')),
    path('analytics/', include('analytics.api_urls')),
]
