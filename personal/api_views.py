"""
API Views para el módulo personal usando Django REST Framework.
"""
from rest_framework import viewsets, filters, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend

from .models import Area, SubArea, Personal, Roster, RosterAudit
from .serializers import (
    AreaSerializer, SubAreaSerializer,
    PersonalListSerializer, PersonalDetailSerializer, PersonalCreateUpdateSerializer,
    RosterSerializer, RosterBulkCreateSerializer, RosterAuditSerializer
)
from .permissions import puede_editar_roster


class AreaViewSet(viewsets.ModelViewSet):
    """ViewSet para Gerencias."""
    queryset = Area.objects.prefetch_related('subareas', 'responsables').all()
    serializer_class = AreaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['activa']
    search_fields = ['nombre', 'responsables__apellidos_nombres']
    ordering_fields = ['nombre', 'creado_en']
    ordering = ['nombre']


class SubAreaViewSet(viewsets.ModelViewSet):
    """ViewSet para SubÁreas."""
    queryset = SubArea.objects.select_related('area').all()
    serializer_class = SubAreaSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['area', 'activa']
    search_fields = ['nombre', 'area__nombre']
    ordering_fields = ['nombre', 'area__nombre', 'creado_en']
    ordering = ['area__nombre', 'nombre']


class PersonalViewSet(viewsets.ModelViewSet):
    """ViewSet para Personal."""
    queryset = Personal.objects.select_related('subarea', 'subarea__area', 'usuario').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['estado', 'tipo_trab', 'subarea', 'subarea__area']
    search_fields = ['apellidos_nombres', 'nro_doc', 'cargo', 'celular']
    ordering_fields = ['apellidos_nombres', 'fecha_alta', 'creado_en']
    ordering = ['apellidos_nombres']
    
    def get_serializer_class(self):
        """Usar diferentes serializers según la acción."""
        if self.action == 'list':
            return PersonalListSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return PersonalCreateUpdateSerializer
        return PersonalDetailSerializer
    
    @action(detail=False, methods=['get'])
    def activos(self, request):
        """Endpoint para obtener solo personal activo."""
        personal_activo = self.filter_queryset(
            self.queryset.filter(estado='Activo')
        )
        page = self.paginate_queryset(personal_activo)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(personal_activo, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def roster(self, request, pk=None):
        """Obtener roster de un personal específico."""
        personal = self.get_object()
        roster = Roster.objects.filter(personal=personal).order_by('-fecha')[:30]
        serializer = RosterSerializer(roster, many=True)
        return Response(serializer.data)


class RosterViewSet(viewsets.ModelViewSet):
    """ViewSet para Roster."""
    queryset = Roster.objects.select_related('personal', 'personal__subarea__area').all()
    serializer_class = RosterSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'fecha', 'personal__subarea__area']
    search_fields = ['personal__apellidos_nombres', 'personal__nro_doc', 'codigo']
    ordering_fields = ['fecha', 'personal__apellidos_nombres']
    ordering = ['-fecha', 'personal__apellidos_nombres']

    def _validar_permiso_roster(self, personal):
        if not puede_editar_roster(self.request.user, personal):
            raise PermissionDenied('No tienes permisos para editar el roster de este personal.')

    def perform_create(self, serializer):
        personal = serializer.validated_data.get('personal')
        if personal is not None:
            self._validar_permiso_roster(personal)
        serializer.save(modificado_por=self.request.user)

    def perform_update(self, serializer):
        personal = serializer.validated_data.get('personal', serializer.instance.personal)
        self._validar_permiso_roster(personal)
        serializer.save(modificado_por=self.request.user)
    
    @action(detail=False, methods=['post'])
    def bulk_create(self, request):
        """Creación masiva de registros de roster."""
        serializer = RosterBulkCreateSerializer(data=request.data)
        if serializer.is_valid():
            registros = serializer.validated_data.get('registros', [])
            for registro in registros:
                self._validar_permiso_roster(registro['personal'])
            serializer.save()
            return Response(
                {'mensaje': 'Registros creados exitosamente'},
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def por_rango(self, request):
        """Obtener roster por rango de fechas."""
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')

        if not fecha_desde or not fecha_hasta:
            return Response(
                {'error': 'Debe proporcionar fecha_desde y fecha_hasta'},
                status=status.HTTP_400_BAD_REQUEST
            )

        roster = self.filter_queryset(
            self.queryset.filter(fecha__range=[fecha_desde, fecha_hasta])
        )
        page = self.paginate_queryset(roster)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(roster, many=True)
        return Response(serializer.data)


class RosterAuditViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet para auditoría de Roster (solo lectura)."""
    queryset = RosterAudit.objects.select_related('personal', 'usuario').all()
    serializer_class = RosterAuditSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['personal', 'fecha', 'campo_modificado']
    search_fields = ['personal__apellidos_nombres', 'personal__nro_doc']
    ordering_fields = ['creado_en']
    ordering = ['-creado_en']
