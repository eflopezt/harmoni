"""
API Views — Reclutamiento y Selección.
"""
from django.db.models import Count
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse

from core.api_mixins import EmpresaFilteredViewSetMixin
from .models import Vacante, EtapaPipeline, Postulacion, NotaPostulacion
from .api_serializers import (
    VacanteSerializer,
    VacanteListSerializer,
    EtapaPipelineSerializer,
    PostulacionSerializer,
    PostulacionListSerializer,
    MoverEtapaSerializer,
    DescartarSerializer,
    ToggleTagSerializer,
    BulkActionSerializer,
    FunnelStatsSerializer,
)


@extend_schema_view(
    list=extend_schema(tags=['Reclutamiento']),
    retrieve=extend_schema(tags=['Reclutamiento']),
)
class EtapaPipelineViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Etapas del pipeline de selección (catálogo compartido)."""
    empresa_global = True
    queryset = EtapaPipeline.objects.filter(activa=True)
    serializer_class = EtapaPipelineSerializer
    permission_classes = [IsAuthenticated]
    ordering = ['orden']


@extend_schema_view(
    list=extend_schema(tags=['Reclutamiento']),
    retrieve=extend_schema(tags=['Reclutamiento']),
)
class VacanteViewSet(EmpresaFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """Vacantes abiertas.

    Vacante no tiene ruta ORM a Empresa (area es catálogo global) →
    deny-by-default por API hasta que el modelo gane tenancy."""
    queryset = Vacante.objects.select_related('area', 'responsable').prefetch_related('postulaciones').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['area', 'estado', 'prioridad', 'tipo_contrato', 'publica']
    search_fields = ['titulo', 'descripcion', 'requisitos']
    ordering = ['-fecha_publicacion']

    def get_serializer_class(self):
        if self.action == 'list':
            return VacanteListSerializer
        return VacanteSerializer


@extend_schema_view(
    list=extend_schema(tags=['Reclutamiento']),
    retrieve=extend_schema(tags=['Reclutamiento']),
    create=extend_schema(tags=['Reclutamiento']),
    mover_etapa=extend_schema(tags=['Reclutamiento'], request=MoverEtapaSerializer),
    descartar=extend_schema(tags=['Reclutamiento'], request=DescartarSerializer),
    toggle_tag=extend_schema(tags=['Reclutamiento'], request=ToggleTagSerializer),
    bulk=extend_schema(tags=['Reclutamiento'], request=BulkActionSerializer),
    funnel_stats=extend_schema(
        tags=['Reclutamiento'],
        responses={200: FunnelStatsSerializer(many=True)},
    ),
)
class PostulacionViewSet(EmpresaFilteredViewSetMixin, viewsets.ModelViewSet):
    """
    Postulaciones a vacantes con acciones de pipeline.

    Postulacion (PII de candidatos) no tiene ruta ORM a Empresa →
    deny-by-default por API: solo superuser lee/escribe.

    Extra actions:
    - POST /api/reclutamiento/postulaciones/<pk>/mover-etapa/  — mover etapa
    - POST /api/reclutamiento/postulaciones/<pk>/descartar/    — descartar
    - POST /api/reclutamiento/postulaciones/<pk>/toggle-tag/   — toggle tag
    - POST /api/reclutamiento/postulaciones/bulk/              — acciones masivas
    - GET  /api/reclutamiento/postulaciones/funnel-stats/      — stats por etapa
    """
    queryset = Postulacion.objects.select_related('vacante', 'etapa').all()
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vacante', 'etapa', 'estado', 'fuente']
    search_fields = ['nombre_completo', 'email', 'telefono']
    ordering = ['-fecha_postulacion']
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action == 'list':
            return PostulacionListSerializer
        return PostulacionSerializer

    @action(detail=True, methods=['post'], url_path='mover-etapa')
    def mover_etapa(self, request, pk=None):
        """Mueve la postulación a otra etapa. Body: {etapa_id, comentario}"""
        postulacion = self.get_object()
        if postulacion.estado != 'ACTIVA':
            return Response(
                {'error': 'Solo postulaciones activas pueden moverse.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = MoverEtapaSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        etapa_destino = get_object_or_404(
            EtapaPipeline, pk=ser.validated_data['etapa_id'], activa=True,
        )
        etapa_anterior = postulacion.etapa
        postulacion.etapa = etapa_destino
        postulacion.save(update_fields=['etapa'])

        # Nota historia
        try:
            NotaPostulacion.objects.create(
                postulacion=postulacion,
                autor=request.user,
                tipo='NOTA',
                texto=(f'[API] Movido de "{etapa_anterior}" a "{etapa_destino}". '
                       f'{ser.validated_data.get("comentario", "")}').strip(),
            )
        except Exception:
            pass

        # Email + notif in-app best-effort
        try:
            from reclutamiento.emails import email_por_etapa, notif_in_app_reclutadores
            email_por_etapa(postulacion, etapa_destino)
            notif_in_app_reclutadores(
                postulacion,
                f'{postulacion.nombre_completo} avanzó a "{etapa_destino.nombre}"',
                tipo='etapa',
            )
        except Exception:
            pass

        return Response(PostulacionSerializer(postulacion).data)

    @action(detail=True, methods=['post'])
    def descartar(self, request, pk=None):
        """Descarta una postulación. Body: {motivo}"""
        postulacion = self.get_object()
        if postulacion.estado != 'ACTIVA':
            return Response(
                {'error': 'Postulación ya no está activa.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ser = DescartarSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        motivo = ser.validated_data['motivo']

        postulacion.estado = 'DESCARTADA'
        postulacion.save(update_fields=['estado'])

        try:
            NotaPostulacion.objects.create(
                postulacion=postulacion,
                autor=request.user,
                tipo='NOTA',
                texto=f'[API DESCARTE] {motivo}',
            )
        except Exception:
            pass

        try:
            from reclutamiento.emails import email_descarte, notif_in_app_reclutadores
            email_descarte(postulacion, motivo=motivo)
            notif_in_app_reclutadores(
                postulacion,
                f'{postulacion.nombre_completo} fue descartado/a. Motivo: {motivo[:60]}',
                tipo='descarte',
            )
        except Exception:
            pass

        return Response(PostulacionSerializer(postulacion).data)

    @action(detail=True, methods=['post'], url_path='toggle-tag')
    def toggle_tag(self, request, pk=None):
        """Toggle de tag. Body: {tag}"""
        postulacion = self.get_object()
        ser = ToggleTagSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        code = ser.validated_data['tag']
        valid = {c for c, _ in Postulacion.TAG_CHOICES}
        if code not in valid:
            return Response(
                {'error': f'Tag inválido. Válidos: {sorted(valid)}'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        nuevos = postulacion.toggle_tag(code)
        return Response({
            'ok': True, 'tags': nuevos, 'has_tag': code in nuevos,
        })

    @action(detail=False, methods=['post'])
    def bulk(self, request):
        """
        Acciones masivas.
        Body: {ids: [1,2,3], accion: 'mover'|'descartar'|'tag_add'|'tag_remove'|'nota', ...}
        """
        ser = BulkActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        accion = data['accion']
        qs = self.get_queryset().filter(pk__in=data['ids'], estado='ACTIVA')

        count = 0
        if accion == 'mover':
            etapa_id = data.get('etapa_id')
            if not etapa_id:
                return Response({'error': 'etapa_id requerido'}, status=400)
            try:
                etapa = EtapaPipeline.objects.get(pk=etapa_id, activa=True)
            except EtapaPipeline.DoesNotExist:
                return Response({'error': 'etapa invalida'}, status=400)
            for p in qs:
                p.etapa = etapa
                p.save(update_fields=['etapa'])
                count += 1

        elif accion == 'descartar':
            motivo = data.get('motivo', 'Descarte bulk via API')
            for p in qs:
                p.estado = 'DESCARTADA'
                p.save(update_fields=['estado'])
                count += 1

        elif accion in ('tag_add', 'tag_remove'):
            tag = data.get('tag')
            valid = {c for c, _ in Postulacion.TAG_CHOICES}
            if tag not in valid:
                return Response({'error': 'tag invalido'}, status=400)
            for p in qs:
                if accion == 'tag_add':
                    p.add_tag(tag)
                else:
                    p.remove_tag(tag)
                count += 1

        elif accion == 'nota':
            texto = data.get('texto', '').strip()
            if not texto:
                return Response({'error': 'texto requerido'}, status=400)
            for p in qs:
                NotaPostulacion.objects.create(
                    postulacion=p, autor=request.user,
                    tipo='NOTA', texto=f'[BULK API] {texto}',
                )
                count += 1

        return Response({'ok': True, 'count': count, 'accion': accion})

    @action(detail=False, methods=['get'], url_path='funnel-stats')
    def funnel_stats(self, request):
        """Stats agregadas por etapa para apps mobile."""
        etapas = EtapaPipeline.objects.filter(activa=True).order_by('orden')
        data = []
        for e in etapas:
            count = self.get_queryset().filter(etapa=e, estado='ACTIVA').count()
            data.append({
                'etapa_id':     e.pk,
                'etapa_nombre': e.nombre,
                'count':        count,
                'color':        e.color or '#94a3b8',
            })
        return Response(data)
