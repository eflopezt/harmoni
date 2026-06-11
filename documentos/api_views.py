"""
API Views - Documentos (Legajo Digital, Boletas).
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import TipoDocumento, DocumentoTrabajador, BoletaPago
from .api_serializers import (
    TipoDocumentoSerializer,
    DocumentoTrabajadorSerializer,
    BoletaPagoSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Documentos']),
    retrieve=extend_schema(tags=['Documentos']),
)
class TipoDocumentoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Catálogo de tipos de documento (compartido)."""
    empresa_global = True
    queryset = TipoDocumento.objects.select_related('categoria').filter(activo=True)
    serializer_class = TipoDocumentoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categoria', 'obligatorio', 'aplica_staff', 'aplica_rco']
    search_fields = ['nombre']
    ordering = ['orden', 'nombre']


@extend_schema_view(
    list=extend_schema(tags=['Documentos']),
    retrieve=extend_schema(tags=['Documentos']),
)
class DocumentoTrabajadorViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Documentos del legajo (metadatos, sin descarga)."""
    empresa_field = 'personal__empresa'
    queryset = DocumentoTrabajador.objects.select_related('personal', 'tipo').all()
    serializer_class = DocumentoTrabajadorSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'tipo', 'estado']
    search_fields = ['personal__apellidos_nombres', 'nombre_archivo']
    ordering = ['-creado_en']


@extend_schema_view(
    list=extend_schema(tags=['Documentos']),
    retrieve=extend_schema(tags=['Documentos']),
)
class BoletaPagoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Boletas de pago (metadatos, sin descarga)."""
    empresa_field = 'personal__empresa'
    queryset = BoletaPago.objects.select_related('personal').all()
    serializer_class = BoletaPagoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'tipo', 'estado', 'confirmada']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-periodo']
