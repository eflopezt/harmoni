"""
API Serializers — Estructura Salarial.
"""
from rest_framework import serializers
from .models import BandaSalarial, HistorialSalarial, SimulacionIncremento, DetalleSimulacion


class BandaSalarialSerializer(serializers.ModelSerializer):
    class Meta:
        model = BandaSalarial
        fields = [
            'id', 'cargo', 'nivel',
            'minimo', 'medio', 'maximo', 'moneda',
            'activa', 'creado_en',
        ]
        read_only_fields = fields


class HistorialSalarialSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True)

    class Meta:
        model = HistorialSalarial
        fields = [
            'id', 'personal', 'personal_nombre',
            'fecha_efectiva',
            'remuneracion_anterior', 'remuneracion_nueva',
            'motivo', 'observaciones',
            'creado_en',
        ]
        read_only_fields = fields


class DetalleSimulacionSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True)

    class Meta:
        model = DetalleSimulacion
        fields = '__all__'
        read_only_fields = ['id', 'creado_en', 'actualizado_en']


class SimulacionIncrementoSerializer(serializers.ModelSerializer):
    detalles = DetalleSimulacionSerializer(many=True, read_only=True)

    class Meta:
        model = SimulacionIncremento
        fields = [
            'id', 'nombre', 'fecha', 'descripcion',
            'estado', 'tipo', 'presupuesto_total',
            'creado_en', 'detalles',
        ]
        read_only_fields = fields


class SimulacionListSerializer(serializers.ModelSerializer):
    """Serializer ligero sin detalles anidados."""
    class Meta:
        model = SimulacionIncremento
        fields = [
            'id', 'nombre', 'fecha', 'estado', 'tipo',
            'presupuesto_total', 'creado_en',
        ]
        read_only_fields = fields
