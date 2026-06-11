"""
API Views — Comunicaciones.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import Notificacion, ComunicadoMasivo
from .api_serializers import NotificacionSerializer, ComunicadoMasivoSerializer


@extend_schema_view(
    list=extend_schema(tags=['Comunicaciones']),
    retrieve=extend_schema(tags=['Comunicaciones']),
)
class NotificacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Notificaciones enviadas.

    Nota: notificaciones sin destinatario Personal (destinatario NULL,
    solo email) quedan ocultas para usuarios tenant — no hay forma de
    atribuirles empresa."""
    empresa_field = 'destinatario__empresa'
    queryset = Notificacion.objects.select_related('destinatario', 'plantilla').all()
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['destinatario', 'tipo', 'estado']
    search_fields = ['asunto', 'destinatario_email']
    ordering = ['-creado_en']


@extend_schema_view(
    list=extend_schema(tags=['Comunicaciones']),
    retrieve=extend_schema(tags=['Comunicaciones']),
)
class ComunicadoMasivoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Comunicados masivos (sin tenancy → deny-by-default)."""
    queryset = ComunicadoMasivo.objects.select_related('creado_por').all()
    serializer_class = ComunicadoMasivoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado']
    search_fields = ['titulo']
    ordering = ['-creado_en']
