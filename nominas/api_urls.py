"""API REST URLs para nominas — conceptos remunerativos + onboarding."""
from django.urls import path
from rest_framework.routers import DefaultRouter

from .api_conceptos import ConceptoViewSet
from .views_mi_dia import mi_dia_api
from .views_onboarding_validator import onboarding_validador_api


router = DefaultRouter()
router.register(r'conceptos', ConceptoViewSet, basename='concepto')

urlpatterns = router.urls + [
    path('onboarding/', onboarding_validador_api, name='api_onboarding_validador'),
    path('mi-dia/',     mi_dia_api,              name='api_mi_dia'),
]
