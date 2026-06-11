"""
API Views — Préstamos y Adelantos.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import TipoPrestamo, Prestamo, CuotaPrestamo
from .api_serializers import (
    TipoPrestamoSerializer,
    PrestamoSerializer,
    PrestamoListSerializer,
    CuotaPrestamoSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Préstamos']),
    retrieve=extend_schema(tags=['Préstamos']),
)
class TipoPrestamoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Tipos de préstamo configurados (catálogo compartido)."""
    empresa_global = True
    queryset = TipoPrestamo.objects.filter(activo=True)
    serializer_class = TipoPrestamoSerializer
    permission_classes = [IsAuthenticated]
    search_fields = ['nombre', 'codigo']
    ordering = ['nombre']


@extend_schema_view(
    list=extend_schema(tags=['Préstamos']),
    retrieve=extend_schema(tags=['Préstamos']),
)
class PrestamoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Préstamos y adelantos."""
    empresa_field = 'personal__empresa'
    queryset = Prestamo.objects.select_related('personal', 'tipo').prefetch_related('cuotas').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'tipo', 'estado']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-fecha_solicitud']

    def get_serializer_class(self):
        if self.action == 'list':
            return PrestamoListSerializer
        return PrestamoSerializer


@extend_schema_view(
    list=extend_schema(tags=['Préstamos']),
    retrieve=extend_schema(tags=['Préstamos']),
)
class CuotaPrestamoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Cuotas de préstamos."""
    empresa_field = 'prestamo__personal__empresa'
    queryset = CuotaPrestamo.objects.select_related('prestamo', 'prestamo__personal').all()
    serializer_class = CuotaPrestamoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['prestamo', 'estado']
    ordering = ['numero']
