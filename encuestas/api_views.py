"""
API Views — Encuestas y Clima Laboral.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import Encuesta, ResultadoEncuesta
from .api_serializers import (
    EncuestaSerializer,
    EncuestaListSerializer,
    ResultadoEncuestaSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Encuestas']),
    retrieve=extend_schema(tags=['Encuestas']),
)
class EncuestaViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Encuestas de clima laboral / eNPS.

    Encuesta no tiene ruta ORM a Empresa → deny-by-default por API."""
    queryset = Encuesta.objects.prefetch_related('preguntas').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado', 'anonima']
    search_fields = ['titulo', 'descripcion']
    ordering = ['-fecha_inicio']

    def get_serializer_class(self):
        if self.action == 'list':
            return EncuestaListSerializer
        return EncuestaSerializer


@extend_schema_view(
    list=extend_schema(tags=['Encuestas']),
    retrieve=extend_schema(tags=['Encuestas']),
)
class ResultadoEncuestaViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Resultados consolidados de encuestas (sin tenancy → deny-by-default)."""
    queryset = ResultadoEncuesta.objects.select_related('encuesta').all()
    serializer_class = ResultadoEncuestaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['encuesta']
    ordering = ['-id']
