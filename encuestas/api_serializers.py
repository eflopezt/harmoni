"""
API Serializers — Encuestas y Clima Laboral.
"""
from rest_framework import serializers
from .models import Encuesta, PreguntaEncuesta, ResultadoEncuesta


class PreguntaEncuestaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreguntaEncuesta
        fields = [
            'id', 'encuesta', 'texto', 'tipo',
            'obligatoria', 'opciones', 'categoria', 'orden',
        ]
        read_only_fields = fields


class EncuestaSerializer(serializers.ModelSerializer):
    preguntas = PreguntaEncuestaSerializer(many=True, read_only=True)

    class Meta:
        model = Encuesta
        fields = [
            'id', 'titulo', 'descripcion', 'tipo', 'estado',
            'anonima', 'fecha_inicio', 'fecha_fin',
            'aplica_grupos', 'max_respuestas', 'recordatorio_dias',
            'creado_en', 'preguntas',
        ]
        read_only_fields = fields


class EncuestaListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listado."""
    class Meta:
        model = Encuesta
        fields = [
            'id', 'titulo', 'tipo', 'estado',
            'anonima', 'fecha_inicio', 'fecha_fin',
            'creado_en',
        ]
        read_only_fields = fields


class ResultadoEncuestaSerializer(serializers.ModelSerializer):
    encuesta_titulo = serializers.CharField(
        source='encuesta.titulo', read_only=True)

    class Meta:
        model = ResultadoEncuesta
        fields = '__all__'
        read_only_fields = ['id', 'calculado_en']
