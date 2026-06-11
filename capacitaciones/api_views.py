"""
API Views — Capacitaciones (LMS).
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import Capacitacion, RequerimientoCapacitacion, CertificacionTrabajador
from .api_serializers import (
    CapacitacionSerializer,
    RequerimientoCapacitacionSerializer,
    CertificacionTrabajadorSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Capacitaciones']),
    retrieve=extend_schema(tags=['Capacitaciones']),
)
class CapacitacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Capacitaciones (cursos, talleres, charlas).

    Capacitacion no tiene ruta ORM a Empresa → deny-by-default por API
    (solo superuser) hasta que el modelo gane tenancy."""
    queryset = Capacitacion.objects.select_related('categoria', 'creado_por').all()
    serializer_class = CapacitacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['categoria', 'tipo', 'estado', 'obligatoria']
    search_fields = ['titulo', 'instructor', 'descripcion']
    ordering = ['-fecha_inicio']


@extend_schema_view(
    list=extend_schema(tags=['Capacitaciones']),
    retrieve=extend_schema(tags=['Capacitaciones']),
)
class RequerimientoCapacitacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Requerimientos de capacitación obligatoria (catálogo normativo compartido)."""
    empresa_global = True
    queryset = RequerimientoCapacitacion.objects.select_related('categoria').filter(activo=True)
    serializer_class = RequerimientoCapacitacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categoria', 'obligatorio', 'aplica_staff', 'aplica_rco']
    search_fields = ['nombre', 'base_legal']
    ordering = ['nombre']


@extend_schema_view(
    list=extend_schema(tags=['Capacitaciones']),
    retrieve=extend_schema(tags=['Capacitaciones']),
)
class CertificacionTrabajadorViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Certificaciones obtenidas por trabajadores."""
    empresa_field = 'personal__empresa'
    queryset = CertificacionTrabajador.objects.select_related(
        'personal', 'requerimiento', 'capacitacion').all()
    serializer_class = CertificacionTrabajadorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'requerimiento', 'estado']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-fecha_obtencion']
