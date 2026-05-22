from django.contrib import admin
from .models import (
    Encuesta, PreguntaEncuesta, PulseSemanal, RespuestaEncuesta,
    ResultadoEncuesta,
)

admin.site.register(Encuesta)
admin.site.register(PreguntaEncuesta)
admin.site.register(RespuestaEncuesta)
admin.site.register(ResultadoEncuesta)


@admin.register(PulseSemanal)
class PulseSemanalAdmin(admin.ModelAdmin):
    list_display = ('semana', 'anio', 'empresa', 'personal', 'animo', 'nps', 'creado_en')
    list_filter = ('anio', 'semana', 'empresa', 'animo')
    search_fields = ('personal__apellidos_nombres', 'que_falta', 'propuestas')
    date_hierarchy = 'creado_en'
