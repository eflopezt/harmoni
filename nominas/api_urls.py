"""API REST URLs para nominas — conceptos remunerativos."""
from rest_framework.routers import DefaultRouter

from .api_conceptos import ConceptoViewSet


router = DefaultRouter()
router.register(r'conceptos', ConceptoViewSet, basename='concepto')

urlpatterns = router.urls
