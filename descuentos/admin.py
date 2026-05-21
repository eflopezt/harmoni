from django.contrib import admin

from .models import DescuentoPlanilla, AplicacionDescuento


class AplicacionInline(admin.TabularInline):
    model = AplicacionDescuento
    extra = 0
    readonly_fields = ('creado_en',)
    fields = ('periodo_anio', 'periodo_mes', 'monto_aplicado', 'registro_nomina', 'creado_en')


@admin.register(DescuentoPlanilla)
class DescuentoPlanillaAdmin(admin.ModelAdmin):
    list_display = (
        'personal', 'causal', 'monto_total', 'cuota_mensual',
        'num_cuotas', 'estado', 'fecha_registro',
    )
    list_filter = ('estado', 'causal', 'fecha_registro')
    search_fields = ('personal__apellidos_nombres', 'personal__nro_doc', 'detalle')
    autocomplete_fields = ('personal',)
    readonly_fields = ('creado_en', 'actualizado_en', 'fecha_aprobacion')
    inlines = [AplicacionInline]
    fieldsets = (
        (None, {
            'fields': ('personal', 'causal', 'detalle'),
        }),
        ('Monto y cuotas', {
            'fields': ('monto_total', 'num_cuotas', 'cuota_mensual',
                       'fecha_inicio_descuento'),
        }),
        ('Estado y aprobación', {
            'fields': ('estado', 'requiere_consentimiento',
                       'consentimiento_firmado', 'documento_soporte',
                       'aprobado_por', 'fecha_aprobacion'),
        }),
        ('Auditoría', {
            'fields': ('solicitado_por', 'observaciones',
                       'creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )


@admin.register(AplicacionDescuento)
class AplicacionDescuentoAdmin(admin.ModelAdmin):
    list_display = ('descuento', 'periodo_anio', 'periodo_mes', 'monto_aplicado')
    list_filter = ('periodo_anio', 'periodo_mes')
    autocomplete_fields = ('descuento',)
    readonly_fields = ('creado_en',)
