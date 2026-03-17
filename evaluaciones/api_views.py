"""
API Views — Evaluaciones de Desempeño.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import (
    Competencia, CicloEvaluacion, Evaluacion,
    ResultadoConsolidado, PlanDesarrollo,
    ObjetivoClave, ResultadoClave, CheckInOKR,
)
from .api_serializers import (
    CompetenciaSerializer,
    CicloEvaluacionSerializer,
    EvaluacionSerializer,
    ResultadoConsolidadoSerializer,
    PlanDesarrolloSerializer,
    ObjetivoClaveSerializer,
    ResultadoClaveSerializer,
    CheckInOKRSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Evaluaciones']),
    retrieve=extend_schema(tags=['Evaluaciones']),
)
class CompetenciaViewSet(viewsets.ReadOnlyModelViewSet):
    """Catálogo de competencias."""
    queryset = Competencia.objects.filter(activa=True)
    serializer_class = CompetenciaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['categoria']
    search_fields = ['nombre', 'codigo', 'descripcion']
    ordering = ['orden', 'nombre']


@extend_schema_view(
    list=extend_schema(tags=['Evaluaciones']),
    retrieve=extend_schema(tags=['Evaluaciones']),
)
class CicloEvaluacionViewSet(viewsets.ReadOnlyModelViewSet):
    """Ciclos de evaluación de desempeño."""
    queryset = CicloEvaluacion.objects.select_related('plantilla', 'creado_por').all()
    serializer_class = CicloEvaluacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['tipo', 'estado']
    search_fields = ['nombre', 'descripcion']
    ordering = ['-fecha_inicio']


@extend_schema_view(
    list=extend_schema(tags=['Evaluaciones']),
    retrieve=extend_schema(tags=['Evaluaciones']),
)
class EvaluacionViewSet(viewsets.ReadOnlyModelViewSet):
    """Evaluaciones individuales."""
    queryset = Evaluacion.objects.select_related(
        'ciclo', 'evaluado', 'evaluador').all()
    serializer_class = EvaluacionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['ciclo', 'evaluado', 'evaluador', 'relacion', 'estado']
    search_fields = ['evaluado__apellidos_nombres', 'evaluador__apellidos_nombres']
    ordering = ['-creado_en']


@extend_schema_view(
    list=extend_schema(tags=['Evaluaciones']),
    retrieve=extend_schema(tags=['Evaluaciones']),
)
class ResultadoConsolidadoViewSet(viewsets.ReadOnlyModelViewSet):
    """Resultados consolidados (9-Box)."""
    queryset = ResultadoConsolidado.objects.select_related('ciclo', 'personal').all()
    serializer_class = ResultadoConsolidadoSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['ciclo']
    ordering = ['-ciclo__fecha_inicio']


@extend_schema_view(
    list=extend_schema(tags=['Evaluaciones']),
    retrieve=extend_schema(tags=['Evaluaciones']),
)
class PlanDesarrolloViewSet(viewsets.ReadOnlyModelViewSet):
    """Planes de desarrollo individual (PDI)."""
    queryset = PlanDesarrollo.objects.select_related('personal', 'ciclo').all()
    serializer_class = PlanDesarrolloSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'ciclo']
    search_fields = ['personal__apellidos_nombres']
    ordering = ['-creado_en']


@extend_schema_view(
    list=extend_schema(tags=['OKRs']),
    retrieve=extend_schema(tags=['OKRs']),
)
class ObjetivoClaveViewSet(viewsets.ReadOnlyModelViewSet):
    """Objetivos y Resultados Clave (OKRs)."""
    queryset = ObjetivoClave.objects.select_related(
        'personal', 'area', 'objetivo_padre',
    ).prefetch_related('resultados_clave').all()
    serializer_class = ObjetivoClaveSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['nivel', 'status', 'anio', 'personal', 'area']
    search_fields = ['titulo']
    ordering = ['-anio', 'trimestre']


@extend_schema_view(
    list=extend_schema(tags=['OKRs']),
    retrieve=extend_schema(tags=['OKRs']),
)
class ResultadoClaveViewSet(viewsets.ReadOnlyModelViewSet):
    """Key Results vinculados a objetivos OKR."""
    queryset = ResultadoClave.objects.select_related(
        'objetivo', 'responsable',
    ).all()
    serializer_class = ResultadoClaveSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['objetivo', 'responsable']
    ordering = ['objetivo', 'orden']


@extend_schema_view(
    list=extend_schema(tags=['OKRs']),
    retrieve=extend_schema(tags=['OKRs']),
)
class CheckInOKRViewSet(viewsets.ReadOnlyModelViewSet):
    """Check-ins de progreso de Key Results."""
    queryset = CheckInOKR.objects.select_related(
        'resultado_clave__objetivo', 'registrado_por',
    ).all()
    serializer_class = CheckInOKRSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['resultado_clave']
    ordering = ['-fecha']
