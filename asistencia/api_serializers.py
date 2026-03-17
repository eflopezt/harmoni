"""
API Serializers — Asistencia (tareo).
"""
from rest_framework import serializers
from .models import RegistroTareo, BancoHoras, ConfiguracionSistema


class RegistroTareoSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True)

    class Meta:
        model = RegistroTareo
        fields = [
            'id', 'personal', 'personal_nombre', 'dni', 'fecha',
            'dia_semana', 'es_feriado', 'codigo_dia', 'fuente_codigo',
            'hora_entrada_real', 'hora_salida_real',
            'horas_marcadas', 'horas_efectivas', 'horas_normales',
            'he_25', 'he_35', 'he_100', 'he_al_banco',
            'grupo', 'condicion', 'observaciones',
            'creado_en', 'actualizado_en',
        ]
        read_only_fields = fields


class BancoHorasSerializer(serializers.ModelSerializer):
    personal_nombre = serializers.CharField(
        source='personal.apellidos_nombres', read_only=True)

    class Meta:
        model = BancoHoras
        fields = [
            'id', 'personal', 'personal_nombre',
            'periodo_anio', 'periodo_mes',
            'he_25_acumuladas', 'he_35_acumuladas', 'he_100_acumuladas',
            'he_compensadas', 'saldo_horas', 'cerrado',
            'observaciones', 'creado_en',
        ]
        read_only_fields = fields


class ConfiguracionSistemaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfiguracionSistema
        exclude = [
            'ia_api_key',
            'ia_gemini_api_key',
            'zapsign_api_key',
            'telegram_bot_token',
            'whatsapp_access_token',
        ]
        read_only_fields = ['id']
