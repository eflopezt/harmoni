"""
API Views — Asistencia (tareo).
"""
from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import RegistroTareo, BancoHoras, ConfiguracionSistema
from .api_serializers import (
    RegistroTareoSerializer,
    BancoHorasSerializer,
    ConfiguracionSistemaSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Asistencia']),
    retrieve=extend_schema(tags=['Asistencia']),
)
class RegistroTareoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Registros de asistencia diarios (solo lectura)."""
    empresa_field = 'personal__empresa'
    queryset = RegistroTareo.objects.select_related('personal', 'regimen').all()
    serializer_class = RegistroTareoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'fecha', 'codigo_dia', 'grupo', 'condicion', 'es_feriado']
    search_fields = ['personal__apellidos_nombres', 'dni']
    ordering_fields = ['fecha', 'personal__apellidos_nombres']
    ordering = ['-fecha']


@extend_schema_view(
    list=extend_schema(tags=['Asistencia']),
    retrieve=extend_schema(tags=['Asistencia']),
)
class BancoHorasViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Banco de horas compensatorias (solo lectura)."""
    empresa_field = 'personal__empresa'
    queryset = BancoHoras.objects.select_related('personal').all()
    serializer_class = BancoHorasSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'periodo_anio', 'periodo_mes', 'cerrado']
    search_fields = ['personal__apellidos_nombres']
    ordering_fields = ['periodo_anio', 'periodo_mes']
    ordering = ['-periodo_anio', '-periodo_mes']


@extend_schema(tags=['Asistencia'])
@api_view(['GET'])
@permission_classes([IsAdminUser])
def configuracion_sistema_api(request):
    """Configuración del sistema (singleton, solo admin)."""
    config = ConfiguracionSistema.get()
    serializer = ConfiguracionSistemaSerializer(config)
    return Response(serializer.data)
