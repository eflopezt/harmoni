from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Empresa


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
