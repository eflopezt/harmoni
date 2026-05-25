from django.contrib import admin
from .models import (
    ConceptoRemunerativo, PeriodoNomina, RegistroNomina, LineaNomina,
    LiquidacionLaboral,
)

admin.site.register(ConceptoRemunerativo)
admin.site.register(PeriodoNomina)
admin.site.register(RegistroNomina)
admin.site.register(LineaNomina)


@admin.register(LiquidacionLaboral)
class LiquidacionLaboralAdmin(admin.ModelAdmin):
    list_display  = ('personal', 'fecha_cese', 'motivo_cese', 'estado',
                     'total_bruto', 'total_neto')
    list_filter   = ('estado', 'motivo_cese')
    search_fields = ('personal__apellidos_nombres', 'personal__nro_doc')
    readonly_fields = ('creado_en', 'actualizado_en', 'total_bruto', 'total_neto')
