"""
API Views — Estructura Salarial.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import BandaSalarial, HistorialSalarial, SimulacionIncremento
from .api_serializers import (
    BandaSalarialSerializer,
    HistorialSalarialSerializer,
    SimulacionIncrementoSerializer,
    SimulacionListSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Salarios']),
    retrieve=extend_schema(tags=['Salarios']),
)
class BandaSalarialViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Bandas salariales por cargo/nivel.

    BandaSalarial no tiene ruta ORM a Empresa y es data salarial sensible
    → deny-by-default por API (solo superuser)."""
    queryset = BandaSalarial.objects.filter(activa=True)
    serializer_class = BandaSalarialSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['nivel', 'moneda']
    search_fields = ['cargo', 'nivel']
    ordering = ['cargo', 'nivel']


@extend_schema_view(
    list=extend_schema(tags=['Salarios']),
    retrieve=extend_schema(tags=['Salarios']),
)
class HistorialSalarialViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Historial de cambios salariales."""
    empresa_field = 'personal__empresa'
    queryset = HistorialSalarial.objects.select_related('personal', 'aprobado_por').all()
    serializer_class = HistorialSalarialSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'motivo']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-fecha_efectiva']


@extend_schema_view(
    list=extend_schema(tags=['Salarios']),
    retrieve=extend_schema(tags=['Salarios']),
)
class SimulacionIncrementoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Simulaciones de incremento salarial (sin tenancy → deny-by-default)."""
    queryset = SimulacionIncremento.objects.prefetch_related('detalles').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'tipo']
    search_fields = ['nombre']
    ordering = ['-fecha']

    def get_serializer_class(self):
        if self.action == 'list':
            return SimulacionListSerializer
        return SimulacionIncrementoSerializer
