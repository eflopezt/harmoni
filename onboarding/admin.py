from django.contrib import admin
from .models import (
    PlantillaOnboarding, PasoPlantilla,
    ProcesoOnboarding, PasoOnboarding,
    PlantillaOffboarding, PasoPlantillaOff,
    ProcesoOffboarding, PasoOffboarding,
    ChecklistGastronomia,
)

admin.site.register(PlantillaOnboarding)
admin.site.register(PasoPlantilla)
admin.site.register(ProcesoOnboarding)
admin.site.register(PasoOnboarding)
admin.site.register(PlantillaOffboarding)
admin.site.register(PasoPlantillaOff)
admin.site.register(ProcesoOffboarding)
admin.site.register(PasoOffboarding)


@admin.register(ChecklistGastronomia)
class ChecklistGastronomiaAdmin(admin.ModelAdmin):
    list_display = ('personal', 'fecha_ingreso', 'completado', 'creado_en')
    list_filter = ('completado',)
    search_fields = ('personal__apellidos_nombres', 'personal__nro_doc')
    readonly_fields = ('creado_en', 'actualizado_en')
