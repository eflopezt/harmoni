from django.contrib import admin
from .models import WaConversacion, WaMensaje, WaLead


class WaMensajeInline(admin.TabularInline):
    model = WaMensaje
    extra = 0
    readonly_fields = ('direccion', 'tipo', 'cuerpo', 'enviado_por', 'creado_en', 'wa_message_id')
    can_delete = False
    ordering = ('creado_en',)


@admin.register(WaConversacion)
class WaConversacionAdmin(admin.ModelAdmin):
    list_display = ('telefono', 'nombre_wa', 'estado', 'menu_state', 'asignado_a',
                    'no_leidos', 'ultimo_mensaje_at')
    list_filter = ('estado', 'menu_state')
    search_fields = ('telefono', 'nombre_wa')
    readonly_fields = ('creado_en', 'actualizado_en', 'ultimo_mensaje_at')
    inlines = [WaMensajeInline]


@admin.register(WaMensaje)
class WaMensajeAdmin(admin.ModelAdmin):
    list_display = ('creado_en', 'conversacion', 'direccion', 'tipo', 'cuerpo_corto', 'enviado_por')
    list_filter = ('direccion', 'tipo')
    search_fields = ('conversacion__telefono', 'cuerpo')
    readonly_fields = ('creado_en',)

    def cuerpo_corto(self, obj):
        return (obj.cuerpo or '')[:80]
    cuerpo_corto.short_description = 'Cuerpo'


@admin.register(WaLead)
class WaLeadAdmin(admin.ModelAdmin):
    list_display = ('creado_en', 'nombre', 'empresa', 'num_empleados', 'telefono',
                    'origen', 'contactado')
    list_filter = ('origen', 'contactado')
    search_fields = ('nombre', 'empresa', 'telefono')
    list_editable = ('contactado',)
