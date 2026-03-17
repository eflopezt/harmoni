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

    class Meta:
        model = Postulacion
        fields = [
            'id', 'vacante', 'vacante_titulo',
            'etapa', 'etapa_nombre',
            'nombre_completo', 'email', 'telefono',
            'experiencia_anos', 'educacion', 'salario_pretendido',
            'fuente', 'estado', 'notas',
            'fecha_postulacion',
        ]
        read_only_fields = [
            'id', 'vacante_titulo', 'etapa_nombre',
            'fecha_postulacion',
        ]
