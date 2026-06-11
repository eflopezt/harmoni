"""
API Views — Evaluaciones de Desempeño.
"""
from rest_framework import viewsets, filters
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view

from core.api_mixins import EmpresaFilteredViewSetMixin
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
class CompetenciaViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Catálogo de competencias (compartido)."""
    empresa_global = True
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
class CicloEvaluacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Ciclos de evaluación de desempeño.

    CicloEvaluacion no tiene ruta ORM a Empresa → deny-by-default por API."""
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
class EvaluacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Evaluaciones individuales."""
    empresa_field = 'evaluado__empresa'
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
class ResultadoConsolidadoViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Resultados consolidados (9-Box)."""
    empresa_field = 'personal__empresa'
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
class PlanDesarrolloViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Planes de desarrollo individual (PDI)."""
    empresa_field = 'personal__empresa'
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
class ObjetivoClaveViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Objetivos y Resultados Clave (OKRs).

    Nota: OKRs de nivel EMPRESA/ÁREA (personal NULL) quedan ocultos por API
    para usuarios tenant — el modelo no registra a qué empresa pertenecen."""
    empresa_field = 'personal__empresa'
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
class ResultadoClaveViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Key Results vinculados a objetivos OKR."""
    empresa_field = 'objetivo__personal__empresa'
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
class CheckInOKRViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Check-ins de progreso de Key Results."""
    empresa_field = 'resultado_clave__objetivo__personal__empresa'
    queryset = CheckInOKR.objects.select_related(
        'resultado_clave__objetivo', 'registrado_por',
    ).all()
    serializer_class = CheckInOKRSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['resultado_clave']
    ordering = ['-fecha']
