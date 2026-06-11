"""
API Views — Analytics.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import KPISnapshot, AlertaRRHH
from .api_serializers import KPISnapshotSerializer, AlertaRRHHSerializer


@extend_schema_view(
    list=extend_schema(tags=['Analytics']),
    retrieve=extend_schema(tags=['Analytics']),
)
class KPISnapshotViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Snapshots KPI mensuales.

    KPISnapshot agrega data de TODO el deployment sin campo empresa →
    deny-by-default (IsAdminUser deja pasar a cualquier is_staff, incluidos
    los admins trial de /onboarding/starter/)."""
    queryset = KPISnapshot.objects.all()
    serializer_class = KPISnapshotSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-periodo']


@extend_schema_view(
    list=extend_schema(tags=['Analytics']),
    retrieve=extend_schema(tags=['Analytics']),
)
class AlertaRRHHViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Alertas RRHH automáticas (sin tenancy → deny-by-default)."""
    queryset = AlertaRRHH.objects.select_related('area').all()
    serializer_class = AlertaRRHHSerializer
    permission_classes = [IsAdminUser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['categoria', 'severidad', 'estado']
    search_fields = ['titulo', 'descripcion']
    ordering = ['-creado_en']
