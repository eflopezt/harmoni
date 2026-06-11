"""
API Views — Vacaciones y Permisos.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import SaldoVacacional, SolicitudVacacion, SolicitudPermiso
from .api_serializers import (
    SaldoVacacionalSerializer,
    SolicitudVacacionSerializer,
    SolicitudPermisoSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Vacaciones']),
    retrieve=extend_schema(tags=['Vacaciones']),
)
class SaldoVacacionalViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Saldos vacacionales por periodo."""
    empresa_field = 'personal__empresa'
    queryset = SaldoVacacional.objects.select_related('personal').all()
    serializer_class = SaldoVacacionalSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'estado']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-periodo_inicio']


@extend_schema_view(
    list=extend_schema(tags=['Vacaciones']),
    retrieve=extend_schema(tags=['Vacaciones']),
    create=extend_schema(tags=['Vacaciones']),
)
class SolicitudVacacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ModelViewSet):
    """Solicitudes de vacaciones (lectura + creación)."""
    empresa_field = 'personal__empresa'
    queryset = SolicitudVacacion.objects.select_related('personal', 'saldo').all()
    serializer_class = SolicitudVacacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'estado']
    search_fields = ['personal__apellidos_nombres', 'motivo']
    ordering = ['-creado_en']
    http_method_names = ['get', 'post', 'head', 'options']


@extend_schema_view(
    list=extend_schema(tags=['Vacaciones']),
    retrieve=extend_schema(tags=['Vacaciones']),
    create=extend_schema(tags=['Vacaciones']),
)
class SolicitudPermisoViewSet(EmpresaFilteredViewSetMixin, viewsets.ModelViewSet):
    """Solicitudes de permisos (lectura + creación)."""
    empresa_field = 'personal__empresa'
    queryset = SolicitudPermiso.objects.select_related('personal', 'tipo').all()
    serializer_class = SolicitudPermisoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'tipo', 'estado']
    search_fields = ['personal__apellidos_nombres', 'motivo']
    ordering = ['-creado_en']
    http_method_names = ['get', 'post', 'head', 'options']
