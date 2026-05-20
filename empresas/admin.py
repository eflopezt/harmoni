from django.contrib import admin
from django.urls import reverse
from .models import Empresa
from .models_billing import Plan, Suscripcion, HistorialPago


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display  = ('razon_social', 'ruc', 'subdominio', 'regimen_laboral', 'sector', 'activa', 'es_principal')
    list_filter   = ('activa', 'es_principal', 'regimen_laboral', 'sector')
    search_fields = ('ruc', 'razon_social', 'nombre_comercial', 'subdominio')
    readonly_fields = ('creado_en', 'actualizado_en', 'creado_por')
    fieldsets = (
        ('Identificación', {
            'fields': ('ruc', 'razon_social', 'nombre_comercial', 'subdominio', 'codigo_empleador'),
        }),
        ('Dirección', {
            'fields': ('direccion', 'ubigeo', 'distrito', 'provincia', 'departamento'),
            'classes': ('collapse',),
        }),
        ('Contacto', {
            'fields': ('telefono', 'email_rrhh', 'web'),
            'classes': ('collapse',),
        }),
        ('Clasificación', {
            'fields': ('regimen_laboral', 'sector', 'actividad_economica'),
        }),
        ('Correo electrónico (SMTP)', {
            'fields': (
                'email_proveedor',
                ('email_host', 'email_port'),
                ('email_use_tls', 'email_use_ssl'),
                ('email_host_user', 'email_host_password'),
                ('email_from', 'email_reply_to'),
            ),
            'description': 'Configuración SMTP por empresa. Gmail requiere App Password (no la contraseña normal).',
        }),
        ('Estado', {
            'fields': ('activa', 'es_principal'),
        }),
        ('Auditoría', {
            'fields': ('creado_por', 'creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['onboarding_url'] = reverse('onboarding_step1')
        return super().changelist_view(request, extra_context=extra_context)

    change_list_template = 'admin/empresas/empresa/change_list.html'


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'codigo', 'precio_mensual', 'max_empleados', 'orden', 'activo', 'destacado')
    list_filter = ('activo', 'destacado')
    list_editable = ('orden', 'activo', 'destacado')
    search_fields = ('nombre', 'codigo')
    prepopulated_fields = {'codigo': ('nombre',)}


@admin.register(Suscripcion)
class SuscripcionAdmin(admin.ModelAdmin):
    list_display = ('empresa', 'plan', 'estado', 'ciclo', 'fecha_inicio', 'proximo_pago')
    list_filter = ('estado', 'ciclo', 'plan')
    search_fields = ('empresa__razon_social', 'empresa__ruc')
    raw_id_fields = ('empresa',)
    readonly_fields = ('creado_en', 'actualizado_en')


@admin.register(HistorialPago)
class HistorialPagoAdmin(admin.ModelAdmin):
    list_display = ('pk', 'suscripcion', 'monto', 'metodo_pago', 'estado', 'fecha_pago', 'referencia')
    list_filter = ('estado', 'metodo_pago')
    search_fields = ('referencia', 'suscripcion__empresa__razon_social')
    readonly_fields = ('creado_en', 'actualizado_en')
    date_hierarchy = 'fecha_pago'
