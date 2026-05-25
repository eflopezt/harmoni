"""
Configuración del admin para el módulo personal.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Area, SubArea, Cargo, Personal, Roster, RosterAudit
from .user_models import UserProfile


# Inline para mostrar el perfil dentro del admin de User
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Perfil con DNI'
    fk_name = 'user'


# Extender el UserAdmin para incluir el perfil
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_dni', 'is_staff']
    
    def get_dni(self, obj):
        try:
            return obj.profile.dni
        except UserProfile.DoesNotExist:
            return '-'
    get_dni.short_description = 'DNI'


# Re-registrar UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Area)
class AreaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'responsables_display', 'activa', 'creado_en']
    list_filter = ['activa', 'creado_en']
    search_fields = ['nombre', 'responsables__apellidos_nombres']
    filter_horizontal = ['responsables']

    def responsables_display(self, obj):
        return ", ".join(p.apellidos_nombres for p in obj.responsables.all()) or "-"
    responsables_display.short_description = 'Responsables'


@admin.register(SubArea)
class SubAreaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'area', 'activa', 'creado_en']
    list_filter = ['area', 'activa', 'creado_en']
    search_fields = ['nombre', 'area__nombre']


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'nivel', 'es_confianza', 'es_fiscalizable', 'activo']
    list_filter = ['nivel', 'es_confianza', 'es_fiscalizable', 'activo']
    search_fields = ['nombre', 'descripcion', 'funciones']
    list_editable = ['nivel', 'es_confianza', 'es_fiscalizable', 'activo']
    fieldsets = (
        (None, {
            'fields': ('nombre', 'descripcion', 'nivel')
        }),
        ('Clasificación Laboral', {
            'fields': ('es_confianza', 'es_fiscalizable'),
            'description': 'Art. 43 DL 728: Personal de confianza no sujeto a fiscalización de jornada.',
        }),
        ('Funciones del Cargo', {
            'fields': ('funciones',),
            'description': 'Una función por línea. Se insertarán en los contratos laborales.',
        }),
        ('Estado', {
            'fields': ('activo',)
        }),
    )


@admin.register(Personal)
class PersonalAdmin(admin.ModelAdmin):
    list_display = [
        'apellidos_nombres', 'nro_doc', 'cargo', 'cargo_obj', 'subarea',
        'estado', 'categoria', 'grupo_tareo', 'fecha_alta', 'tipo_trab',
    ]
    list_filter = ['estado', 'tipo_trab', 'categoria', 'grupo_tareo', 'subarea__area', 'subarea']
    search_fields = ['apellidos_nombres', 'nro_doc', 'cargo', 'celular']
    raw_id_fields = ['usuario', 'subarea']
    fieldsets = (
        ('Información Básica', {
            'fields': ('usuario', 'tipo_doc', 'nro_doc', 'apellidos_nombres', 'codigo_fotocheck')
        }),
        ('Datos Laborales', {
            'fields': ('cargo', 'cargo_obj', 'tipo_trab', 'categoria', 'subarea', 'fecha_alta',
                       'fecha_cese', 'motivo_cese', 'estado', 'asignacion_familiar')
        }),
        ('Pensión y Banca', {
            'fields': ('regimen_pension', 'afp', 'cuspp', 'banco',
                      'cuenta_ahorros', 'cuenta_cci', 'cuenta_cts')
        }),
        ('Tareo / Régimen', {
            'fields': ('grupo_tareo', 'condicion', 'regimen_laboral', 'regimen_turno',
                      'dia_descanso_semanal',
                      'codigo_sap', 'codigo_s10', 'partida_control')
        }),
        ('Roster', {
            'fields': ('dias_libres_corte_2025',)
        }),
        ('Datos Personales', {
            'fields': ('fecha_nacimiento', 'sexo', 'celular', 'correo_personal',
                      'correo_corporativo', 'direccion', 'ubigeo')
        }),
        ('Económicos', {
            'fields': (
                'sueldo_base', 'bonos',
                'cond_trabajo_mensual', 'alimentacion_mensual', 'viaticos_mensual',
                'tiene_eps', 'eps_descuento_mensual',
            )
        }),
        ('Observaciones', {
            'fields': ('observaciones',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Roster)
class RosterAdmin(admin.ModelAdmin):
    list_display = ['personal', 'fecha', 'codigo', 'observaciones']
    list_filter = ['fecha', 'personal__subarea']
    search_fields = ['personal__apellidos_nombres', 'personal__nro_doc', 'codigo']
    raw_id_fields = ['personal']
    date_hierarchy = 'fecha'


@admin.register(RosterAudit)
class RosterAuditAdmin(admin.ModelAdmin):
    list_display = ['personal', 'fecha', 'campo_modificado', 'usuario', 'creado_en']
    list_filter = ['campo_modificado', 'creado_en']
    search_fields = ['personal__apellidos_nombres', 'personal__nro_doc']
    raw_id_fields = ['personal', 'usuario']
    date_hierarchy = 'creado_en'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
