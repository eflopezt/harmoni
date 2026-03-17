"""
API Serializers — Evaluaciones de Desempeño.
"""
from rest_framework import serializers
from .models import (
    Competencia, CicloEvaluacion, Evaluacion,
    ResultadoConsolidado, PlanDesarrollo,
    ObjetivoClave, ResultadoClave, CheckInOKR,
)


class CompetenciaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competencia
        fields = [
            'id', 'nombre', 'codigo', 'descripcion',
            'categoria', 'activa', 'orden',
        ]
        read_only_fields = fields


class CicloEvaluacionSerializer(serializers.ModelSerializer):
    plantilla_nombre = serializers.CharField(
        source='plantilla.nombre', read_only=True, default='')

    class Meta:
        model = CicloEvaluacion
        fields = [
            'id', 'nombre', 'tipo',
            'plantilla', 'plantilla_nombre',
            'fecha_inicio', 'fecha_fin', 'estado',
            'descripcion', 'creado_en',
        ]
        read_only_fields = fields


class EvaluacionSerializer(serializers.ModelSerializer):
    evaluado_nombre = serializers.CharField(
        source='evaluado.apellidos_nombres', read_only=True)
    evaluador_nombre = serializers.CharField(
        source='evaluador.apellidos_nombres', read_only=True, default='')
    ciclo_nombre = serializers.CharField(
        source='ciclo.nombre', read_only=True)

    class Meta:
        model = Evaluacion
        fields = [
            'id', 'ciclo', 'ciclo_nombre',
            'evaluado', 'evaluado_nombre',
            'evaluador', 'evaluador_nombre',
            'relacion', 'estado',
            'puntaje_total', 'puntaje_calibrado',
            'comentario_general', 'fortalezas', 'areas_mejora',
            'fecha_completada', 'creado_en',
        ]
        read_only_fields = fields


class ResultadoConsolidadoSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True, default='')

    class Meta:
        model = ResultadoConsolidado
        fields = '__all__'
        read_only_fields = ['id', 'fecha_consolidacion']


class PlanDesarrolloSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True)

    class Meta:
        model = PlanDesarrollo
        fields = '__all__'
        read_only_fields = ['id', 'creado_en', 'actualizado_en']


# ── OKRs ──────────────────────────────────────────────────────────

class ResultadoClaveSerializer(serializers.ModelSerializer):
    responsable_nombre = serializers.CharField(
        source='responsable.apellidos_nombres', read_only=True, default='')
    porcentaje_avance  = serializers.IntegerField(read_only=True)
    unidad_label       = serializers.CharField(read_only=True)

    class Meta:
        model = ResultadoClave
        fields = [
            'id', 'objetivo', 'descripcion',
            'unidad', 'unidad_label', 'unidad_personalizada',
            'valor_inicial', 'valor_meta', 'valor_actual',
            'completado_binario', 'fecha_limite',
            'responsable', 'responsable_nombre',
            'porcentaje_avance', 'orden',
        ]
        read_only_fields = ['id', 'porcentaje_avance', 'unidad_label']


class CheckInOKRSerializer(serializers.ModelSerializer):
    registrado_por_username = serializers.CharField(
        source='registrado_por.username', read_only=True, default='')

    class Meta:
        model = CheckInOKR
        fields = [
            'id', 'resultado_clave', 'fecha', 'valor_nuevo',
            'comentario', 'registrado_por', 'registrado_por_username', 'creado_en',
        ]
        read_only_fields = ['id', 'creado_en']


class ObjetivoClaveSerializer(serializers.ModelSerializer):
    personal_nombre    = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True, default='')
    area_nombre        = serializers.CharField(
        source='area.nombre', read_only=True, default='')
    padre_titulo       = serializers.CharField(
        source='objetivo_padre.titulo', read_only=True, default='')
    avance_promedio    = serializers.IntegerField(read_only=True)
    periodo_display    = serializers.CharField(read_only=True)
    resultados_clave   = ResultadoClaveSerializer(many=True, read_only=True)

    class Meta:
        model = ObjetivoClave
        fields = [
            'id', 'titulo', 'descripcion',
            'objetivo_padre', 'padre_titulo',
            'nivel', 'personal', 'personal_nombre',
            'area', 'area_nombre',
            'periodo', 'periodo_display', 'anio', 'trimestre',
            'status', 'peso', 'ciclo_evaluacion',
            'avance_promedio',
            'resultados_clave',
            'creado_en', 'actualizado_en',
        ]
        read_only_fields = ['id', 'avance_promedio', 'periodo_display', 'creado_en', 'actualizado_en']
