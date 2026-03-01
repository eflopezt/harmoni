"""
Admin del módulo Tareo.
Solo accesible para superusuarios (is_superuser).
"""
from django.contrib import admin
from django.utils.html import format_html
from .models import (
    RegimenTurno, TipoHorario,
    FeriadoCalendario, HomologacionCodigo,
    TareoImportacion,
    RegistroTareo, RegistroPapeleta,
    BancoHoras, MovimientoBancoHoras,
    RegistroSUNAT, RegistroS10,
    CruceTareoRoster,
    ConfiguracionSistema, ConceptoMapeoS10,
)


# ── Mixin: solo superusuario ──────────────────────────────────
class AdminSoloSuperusuario(admin.ModelAdmin):
    def has_module_perms(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ── Sección 1: Configuración ──────────────────────────────────

class TipoHorarioInline(admin.TabularInline):
    model = TipoHorario
    extra = 1
    fields = ('nombre', 'tipo_dia', 'hora_entrada', 'hora_salida',
              'salida_dia_siguiente', 'activo')


@admin.register(RegimenTurno)
class RegimenTurnoAdmin(AdminSoloSuperusuario):
    list_display = ('nombre', 'codigo', 'jornada_tipo',
                    'dias_trabajo_ciclo', 'dias_descanso_ciclo',
                    'minutos_almuerzo', 'horas_max_ciclo_display', 'activo')
    list_filter = ('jornada_tipo', 'activo', 'es_nocturno')
    search_fields = ('nombre', 'codigo')
    inlines = [TipoHorarioInline]

    @admin.display(description='Horas máx. ciclo (48h×semanas)')
    def horas_max_ciclo_display(self, obj):
        return f"{obj.horas_max_ciclo} h"


@admin.register(TipoHorario)
class TipoHorarioAdmin(AdminSoloSuperusuario):
    list_display = ('nombre', 'regimen', 'tipo_dia',
                    'hora_entrada', 'hora_salida',
                    'horas_efectivas_display', 'activo')
    list_filter = ('regimen', 'tipo_dia', 'activo')

    @admin.display(description='Horas efectivas')
    def horas_efectivas_display(self, obj):
        return f"{obj.horas_efectivas} h"


@admin.register(FeriadoCalendario)
class FeriadoCalendarioAdmin(AdminSoloSuperusuario):
    list_display = ('fecha', 'nombre', 'tipo', 'activo')
    list_filter = ('tipo', 'activo')
    search_fields = ('nombre',)
    date_hierarchy = 'fecha'


@admin.register(HomologacionCodigo)
class HomologacionCodigoAdmin(AdminSoloSuperusuario):
    list_display = ('codigo_origen', 'codigo_tareo', 'codigo_roster',
                    'tipo_evento', 'signo', 'cuenta_asistencia',
                    'genera_he', 'prioridad', 'activo')
    list_filter = ('tipo_evento', 'signo', 'cuenta_asistencia', 'activo')
    search_fields = ('codigo_origen', 'codigo_tareo', 'descripcion')
    ordering = ('prioridad', 'codigo_origen')


# ── Sección 2: Importaciones ──────────────────────────────────

@admin.register(TareoImportacion)
class TareoImportacionAdmin(AdminSoloSuperusuario):
    list_display = ('id', 'tipo', 'periodo_inicio', 'periodo_fin',
                    'estado_coloreado', 'total_registros', 'registros_ok',
                    'registros_error', 'registros_sin_match',
                    'usuario', 'creado_en')
    list_filter = ('tipo', 'estado')
    search_fields = ('archivo_nombre',)
    readonly_fields = ('creado_en', 'procesado_en', 'total_registros',
                       'registros_ok', 'registros_error', 'registros_sin_match',
                       'errores', 'advertencias', 'metadata')
    date_hierarchy = 'creado_en'

    @admin.display(description='Estado')
    def estado_coloreado(self, obj):
        colores = {
            'COMPLETADO': 'green',
            'COMPLETADO_CON_ERRORES': 'orange',
            'FALLIDO': 'red',
            'PROCESANDO': 'blue',
            'PENDIENTE': 'gray',
        }
        color = colores.get(obj.estado, 'black')
        return format_html(
            '<span style="color:{}; font-weight:bold">{}</span>',
            color, obj.get_estado_display()
        )


# ── Sección 3: Registros diarios ─────────────────────────────

class RegistroPapeletaInline(admin.TabularInline):
    model = RegistroPapeleta
    extra = 0
    fields = ('dni', 'tipo_permiso', 'fecha_inicio', 'fecha_fin', 'iniciales')
    readonly_fields = ('dni', 'tipo_permiso', 'fecha_inicio', 'fecha_fin', 'iniciales')
    can_delete = False


@admin.register(RegistroTareo)
class RegistroTareoAdmin(AdminSoloSuperusuario):
    list_display = ('dni', 'nombre_archivo', 'fecha', 'grupo', 'condicion',
                    'codigo_dia', 'fuente_codigo',
                    'horas_normales', 'he_25', 'he_35', 'he_100',
                    'he_al_banco', 'importacion')
    list_filter = ('grupo', 'condicion', 'fuente_codigo',
                   'es_feriado', 'he_al_banco', 'importacion')
    search_fields = ('dni', 'nombre_archivo', 'codigo_dia')
    date_hierarchy = 'fecha'
    readonly_fields = ('creado_en', 'actualizado_en', 'dia_semana')
    raw_id_fields = ('personal', 'importacion', 'regimen')

    fieldsets = (
        ('Identificación', {
            'fields': ('importacion', 'personal', 'dni', 'nombre_archivo',
                       'grupo', 'condicion', 'regimen')
        }),
        ('Datos del día', {
            'fields': ('fecha', 'dia_semana', 'es_feriado',
                       'valor_reloj_raw', 'hora_entrada_real', 'hora_salida_real',
                       'horas_marcadas')
        }),
        ('Resultado procesado', {
            'fields': ('codigo_dia', 'fuente_codigo', 'papeleta_ref',
                       'horas_efectivas', 'horas_normales',
                       'he_25', 'he_35', 'he_100', 'he_al_banco')
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )


@admin.register(RegistroPapeleta)
class RegistroPapeletaAdmin(AdminSoloSuperusuario):
    list_display = ('dni', 'nombre_archivo', 'tipo_permiso',
                    'iniciales', 'fecha_inicio', 'fecha_fin',
                    'dias_habiles', 'area_trabajo')
    list_filter = ('tipo_permiso', 'importacion')
    search_fields = ('dni', 'nombre_archivo', 'detalle')
    date_hierarchy = 'fecha_inicio'
    raw_id_fields = ('personal', 'importacion')


# ── Sección 4: Banco de horas ─────────────────────────────────

class MovimientoBancoHorasInline(admin.TabularInline):
    model = MovimientoBancoHoras
    extra = 0
    fields = ('fecha', 'tipo', 'tasa', 'horas', 'descripcion', 'usuario')
    readonly_fields = ('creado_en',)


@admin.register(BancoHoras)
class BancoHorasAdmin(AdminSoloSuperusuario):
    list_display = ('personal', 'periodo_mes', 'periodo_anio',
                    'total_acumulado', 'he_compensadas', 'saldo_horas', 'cerrado')
    list_filter = ('periodo_anio', 'periodo_mes', 'cerrado')
    search_fields = ('personal__apellidos_nombres', 'personal__nro_doc')
    raw_id_fields = ('personal',)
    inlines = [MovimientoBancoHorasInline]
    readonly_fields = ('creado_en', 'actualizado_en')


@admin.register(MovimientoBancoHoras)
class MovimientoBancoHorasAdmin(AdminSoloSuperusuario):
    list_display = ('banco', 'fecha', 'tipo', 'tasa', 'horas', 'descripcion')
    list_filter = ('tipo', 'tasa')
    date_hierarchy = 'fecha'
    raw_id_fields = ('banco', 'registro_tareo', 'papeleta_ref', 'usuario')


# ── Sección 5: Cruces externos ────────────────────────────────

@admin.register(RegistroSUNAT)
class RegistroSUNATAdmin(AdminSoloSuperusuario):
    list_display = ('nro_doc', 'apellidos_nombres', 'periodo',
                    'dias_laborados', 'remuneracion_basica',
                    'horas_extras_reportadas', 'fecha_ingreso', 'fecha_cese')
    list_filter = ('periodo', 'tipo_trabajador_sunat')
    search_fields = ('nro_doc', 'apellidos_nombres')
    raw_id_fields = ('personal', 'importacion')


@admin.register(RegistroS10)
class RegistroS10Admin(AdminSoloSuperusuario):
    list_display = ('codigo_s10', 'nro_doc', 'apellidos_nombres',
                    'condicion', 'categoria', 'periodo',
                    'horas_extra_25', 'horas_extra_35', 'en_tareo')
    list_filter = ('condicion', 'categoria', 'en_tareo', 'periodo')
    search_fields = ('nro_doc', 'apellidos_nombres', 'codigo_s10')
    raw_id_fields = ('personal', 'importacion')


# ── Sección 6: Configuración sistema ─────────────────────────

@admin.register(ConfiguracionSistema)
class ConfiguracionSistemaAdmin(AdminSoloSuperusuario):
    """Singleton — solo existe una instancia (pk=1). Siempre editar, nunca crear."""

    def has_add_permission(self, request):
        return not ConfiguracionSistema.objects.exists()

    fieldsets = (
        ('Empresa', {
            'fields': ('empresa_nombre', 'ruc'),
        }),
        ('Ciclo de Planilla', {
            'fields': ('dia_corte_planilla', 'regularizacion_activa',
                       'jornada_local_horas', 'jornada_foraneo_horas'),
        }),
        ('Synkro — Columnas', {
            'fields': ('synkro_hoja_reloj', 'synkro_hoja_papeletas',
                       'reloj_col_dni', 'reloj_col_nombre', 'reloj_col_condicion',
                       'reloj_col_tipo_trab', 'reloj_col_area', 'reloj_col_cargo',
                       'reloj_col_inicio_dias'),
            'classes': ('collapse',),
        }),
        ('Notificaciones Email', {
            'fields': ('email_habilitado', 'email_desde',
                       'email_asunto_semanal', 'email_dia_envio'),
            'classes': ('collapse',),
        }),
        ('Inteligencia Artificial', {
            'fields': ('anthropic_api_key', 'ia_mapeo_activo'),
            'classes': ('collapse',),
        }),
        ('Conceptos S10', {
            'fields': ('s10_nombre_concepto_he25', 's10_nombre_concepto_he35',
                       's10_nombre_concepto_he100'),
            'classes': ('collapse',),
        }),
        ('Auditoría', {
            'fields': ('actualizado_en', 'actualizado_por'),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('actualizado_en',)


@admin.register(ConceptoMapeoS10)
class ConceptoMapeoS10Admin(AdminSoloSuperusuario):
    list_display = ('codigo_tareo', 'nombre_concepto_s10', 'tipo_valor', 'activo', 'descripcion')
    list_filter = ('tipo_valor', 'activo')
    search_fields = ('codigo_tareo', 'nombre_concepto_s10')
    list_editable = ('activo',)
    ordering = ('codigo_tareo',)


# ── Sección 7: Cruce Tareo–Roster ────────────────────────────

@admin.register(CruceTareoRoster)
class CruceTareoRosterAdmin(AdminSoloSuperusuario):
    list_display = ('registro_tareo', 'roster_codigo',
                    'variacion', 'impacta_pasaje', 'dias_libres_diff')
    list_filter = ('variacion', 'impacta_pasaje')
    search_fields = ('registro_tareo__dni',)
    raw_id_fields = ('registro_tareo',)
