"""
API Serializers — Reclutamiento y Selección.
"""
from rest_framework import serializers
from .models import Vacante, EtapaPipeline, Postulacion


class EtapaPipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtapaPipeline
        fields = [
            'id', 'nombre', 'codigo', 'orden', 'color', 'activa',
        ]
        read_only_fields = fields


class VacanteSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(
        source='area.nombre', read_only=True, default='')
    total_postulantes = serializers.SerializerMethodField()

    class Meta:
        model = Vacante
        fields = [
            'id', 'titulo', 'area', 'area_nombre',
            'descripcion', 'requisitos',
            'experiencia_minima', 'educacion_minima',
            'tipo_contrato', 'salario_min', 'salario_max', 'moneda',
            'estado', 'prioridad', 'publica',
            'fecha_publicacion', 'fecha_limite',
            'total_postulantes', 'creado_en',
        ]
        read_only_fields = fields

    def get_total_postulantes(self, obj):
        # Use len() to leverage prefetch_related from the viewset
        # instead of count() which hits the DB per row
        return len(obj.postulaciones.all())


class VacanteListSerializer(serializers.ModelSerializer):
    """Ligero para listado."""
    area_nombre = serializers.CharField(
        source='area.nombre', read_only=True, default='')

    class Meta:
        model = Vacante
        fields = [
            'id', 'titulo', 'area_nombre', 'estado', 'prioridad',
            'tipo_contrato', 'publica',
            'fecha_publicacion', 'fecha_limite', 'creado_en',
        ]
        read_only_fields = fields


class PostulacionSerializer(serializers.ModelSerializer):
    vacante_titulo = serializers.CharField(
        source='vacante.titulo', read_only=True)
    etapa_nombre = serializers.CharField(
        source='etapa.nombre', read_only=True, default='')
    etapa_color = serializers.CharField(
        source='etapa.color', read_only=True, default='')
    dias_en_proceso = serializers.ReadOnlyField()
    tags_display = serializers.SerializerMethodField()

    class Meta:
        model = Postulacion
        fields = [
            'id', 'vacante', 'vacante_titulo',
            'etapa', 'etapa_nombre', 'etapa_color',
            'nombre_completo', 'email', 'telefono',
            'experiencia_anos', 'educacion', 'salario_pretendido',
            'fuente', 'estado', 'notas',
            'fecha_postulacion', 'dias_en_proceso',
            'cv_score', 'cv_skills', 'cv_idiomas', 'cv_parsed_at',
            'tags', 'tags_display',
        ]
        read_only_fields = [
            'id', 'vacante_titulo', 'etapa_nombre', 'etapa_color',
            'fecha_postulacion', 'dias_en_proceso', 'tags_display',
            'cv_skills', 'cv_idiomas', 'cv_parsed_at', 'cv_score',
        ]

    def get_tags_display(self, obj):
        if not obj.tags:
            return []
        d = dict(obj.TAG_CHOICES)
        return [{'code': c, 'label': d.get(c, c)} for c in obj.tags]


class PostulacionListSerializer(serializers.ModelSerializer):
    """Light serializer para listados (apps mobile)."""
    vacante_titulo = serializers.CharField(
        source='vacante.titulo', read_only=True)
    etapa_nombre = serializers.CharField(
        source='etapa.nombre', read_only=True, default='')
    etapa_color = serializers.CharField(
        source='etapa.color', read_only=True, default='')

    class Meta:
        model = Postulacion
        fields = [
            'id', 'nombre_completo', 'email',
            'vacante_titulo', 'etapa_nombre', 'etapa_color',
            'estado', 'fuente', 'cv_score', 'fecha_postulacion',
            'tags',
        ]
        read_only_fields = fields


class MoverEtapaSerializer(serializers.Serializer):
    """Para action mover_etapa."""
    etapa_id = serializers.IntegerField()
    comentario = serializers.CharField(required=False, allow_blank=True, max_length=500)


class DescartarSerializer(serializers.Serializer):
    """Para action descartar."""
    motivo = serializers.CharField(max_length=500)


class ToggleTagSerializer(serializers.Serializer):
    """Para action toggle_tag."""
    tag = serializers.CharField(max_length=30)


class BulkActionSerializer(serializers.Serializer):
    """Para action bulk."""
    ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1, max_length=200,
    )
    accion = serializers.ChoiceField(choices=['mover', 'descartar', 'tag_add', 'tag_remove', 'nota'])
    etapa_id = serializers.IntegerField(required=False)
    tag = serializers.CharField(required=False, allow_blank=True, max_length=30)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=500)
    texto = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class FunnelStatsSerializer(serializers.Serializer):
    """Para action stats."""
    etapa_id = serializers.IntegerField()
    etapa_nombre = serializers.CharField()
    count = serializers.IntegerField()
    color = serializers.CharField()
