"""
Serializers para la API REST del módulo personal.
"""
from rest_framework import serializers
from .models import Area, SubArea, Personal, Roster, RosterAudit


class AreaSerializer(serializers.ModelSerializer):
    responsables_nombres = serializers.SerializerMethodField()
    total_areas = serializers.SerializerMethodField()
    total_personal = serializers.SerializerMethodField()
    
    class Meta:
        model = Area
        fields = [
            'id', 'nombre', 'responsables', 'responsables_nombres',
            'descripcion', 'activa', 'total_areas', 'total_personal',
            'creado_en', 'actualizado_en'
        ]
        read_only_fields = ['creado_en', 'actualizado_en']
    
    def get_total_areas(self, obj):
        return obj.subareas.filter(activa=True).count()
    
    def get_total_personal(self, obj):
        return Personal.objects.filter(
            subarea__area=obj,
            estado='Activo'
        ).count()

    def get_responsables_nombres(self, obj):
        return [p.apellidos_nombres for p in obj.responsables.all()]


class SubAreaSerializer(serializers.ModelSerializer):
    area_nombre = serializers.CharField(source='area.nombre', read_only=True)
    total_personal = serializers.SerializerMethodField()
    
    class Meta:
        model = SubArea
        fields = [
            'id', 'nombre', 'area', 'area_nombre',
            'descripcion', 'activa', 'total_personal',
            'creado_en', 'actualizado_en'
        ]
        read_only_fields = ['creado_en', 'actualizado_en']
    
    def get_total_personal(self, obj):
        return obj.personal_asignado.filter(estado='Activo').count()


class PersonalListSerializer(serializers.ModelSerializer):
    """Serializer ligero para listados."""
    subarea_nombre = serializers.CharField(source='subarea.nombre', read_only=True)
    area_nombre = serializers.CharField(source='subarea.area.nombre', read_only=True)
    
    class Meta:
        model = Personal
        fields = [
            'id', 'nro_doc', 'apellidos_nombres', 'cargo',
            'tipo_trab', 'subarea', 'subarea_nombre', 'area_nombre',
            'estado', 'celular', 'correo_corporativo'
        ]


class PersonalDetailSerializer(serializers.ModelSerializer):
    """Serializer completo para detalles."""
    subarea_nombre = serializers.CharField(source='subarea.nombre', read_only=True)
    area_nombre = serializers.CharField(source='subarea.area.nombre', read_only=True)
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)
    
    class Meta:
        model = Personal
        fields = '__all__'
        read_only_fields = ['creado_en', 'actualizado_en']


class PersonalCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer para creación y actualización."""
    
    class Meta:
        model = Personal
        exclude = ['creado_en', 'actualizado_en']
    
    def validate_nro_doc(self, value):
        """Validar que el número de documento sea único."""
        instance = self.instance
        if Personal.objects.filter(nro_doc=value).exclude(
            pk=instance.pk if instance else None
        ).exists():
            raise serializers.ValidationError(
                "Ya existe un registro con este número de documento."
            )
        return value


class RosterSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(source='personal.apellidos_nombres', read_only=True)
    personal_doc = serializers.CharField(source='personal.nro_doc', read_only=True)
    subarea_nombre = serializers.CharField(source='personal.subarea.nombre', read_only=True)
    
    class Meta:
        model = Roster
        fields = [
            'id', 'personal', 'personal_nombre', 'personal_doc',
            'subarea_nombre', 'fecha', 'codigo',
            'observaciones', 'creado_en', 'actualizado_en'
        ]
        read_only_fields = ['creado_en', 'actualizado_en']


class RosterBulkCreateSerializer(serializers.Serializer):
    """Serializer para creación masiva de registros de roster."""
    registros = RosterSerializer(many=True)
    
    def create(self, validated_data):
        registros_data = validated_data.get('registros', [])
        roster_instances = []
        
        for registro_data in registros_data:
            roster, created = Roster.objects.update_or_create(
                personal=registro_data['personal'],
                fecha=registro_data['fecha'],
                defaults={
                    'codigo': registro_data.get('codigo', ''),
                    'observaciones': registro_data.get('observaciones', ''),
                }
            )
            roster_instances.append(roster)
        
        return roster_instances


class RosterAuditSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(source='personal.apellidos_nombres', read_only=True)
    usuario_username = serializers.CharField(source='usuario.username', read_only=True)
    
    class Meta:
        model = RosterAudit
        fields = [
            'id', 'personal', 'personal_nombre', 'fecha',
            'campo_modificado', 'valor_anterior', 'valor_nuevo',
            'usuario', 'usuario_username', 'creado_en'
        ]
        read_only_fields = ['creado_en']
