from django.contrib import admin
from django.utils.html import format_html
from core.models import AuditLog, KnowledgeArticle, PerfilAcceso, PermisoModulo


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'accion', 'content_type', 'object_id', 'descripcion', 'usuario', 'ip_address')
    list_filter = ('accion', 'content_type', 'usuario')
    search_fields = ('descripcion',)
    readonly_fields = ('content_type', 'object_id', 'accion', 'descripcion', 'cambios', 'usuario', 'ip_address', 'timestamp')
    date_hierarchy = 'timestamp'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


# ── PerfilAcceso ──────────────────────────────────────────────────────────────

@admin.register(PerfilAcceso)
class PerfilAccesoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre', 'codigo', 'es_sistema',
        '_modulos_activos',
        'puede_aprobar', 'puede_exportar',
        'actualizado_en',
    )
    list_filter = ('es_sistema', 'puede_aprobar', 'puede_exportar')
    search_fields = ('nombre', 'codigo', 'descripcion')
    readonly_fields = ('creado_en', 'actualizado_en')

    fieldsets = (
        ('Identificación', {
            'fields': ('nombre', 'codigo', 'descripcion', 'es_sistema'),
        }),
        ('Módulos del Sidebar', {
            'description': (
                'Define qué secciones del panel de administración puede ver este perfil. '
                'Los módulos desactivados en Configuración del Sistema nunca aparecen, '
                'independientemente de lo que se marque aquí.'
            ),
            'fields': (
                ('mod_personal', 'mod_asistencia'),
                ('mod_vacaciones', 'mod_documentos'),
                ('mod_capacitaciones', 'mod_evaluaciones'),
                ('mod_disciplinaria', 'mod_encuestas'),
                ('mod_salarios', 'mod_reclutamiento'),
                ('mod_prestamos', 'mod_viaticos'),
                ('mod_onboarding', 'mod_calendario'),
                ('mod_analytics', 'mod_configuracion'),
                ('mod_roster', ),
            ),
        }),
        ('Capacidades', {
            'fields': ('puede_aprobar', 'puede_exportar'),
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    def _modulos_activos(self, obj):
        mods = obj.as_modulos_dict()
        activos = [k.replace('mod_', '') for k, v in mods.items() if v]
        total   = len(mods)
        cuenta  = len(activos)
        color   = '#16a34a' if cuenta >= total * 0.6 else ('#ca8a04' if cuenta >= 3 else '#dc2626')
        return format_html(
            '<span style="color:{};font-weight:600">{}/{}</span> — {}',
            color, cuenta, total,
            ', '.join(activos[:5]) + ('…' if len(activos) > 5 else ''),
        )
    _modulos_activos.short_description = 'Módulos activos'

    def has_delete_permission(self, request, obj=None):
        if obj and obj.es_sistema:
            return False
        return super().has_delete_permission(request, obj)


# ── PermisoModulo ─────────────────────────────────────────────────────────────

@admin.register(PermisoModulo)
class PermisoModuloAdmin(admin.ModelAdmin):
    list_display  = ('usuario', 'modulo', 'puede_ver', 'puede_crear', 'puede_editar', 'puede_aprobar', 'puede_exportar')
    list_filter   = ('modulo', 'puede_ver', 'puede_aprobar')
    search_fields = ('usuario__username', 'usuario__first_name', 'usuario__last_name')
    list_editable = ('puede_ver', 'puede_crear', 'puede_editar', 'puede_aprobar', 'puede_exportar')
    raw_id_fields = ('usuario',)


# ── KnowledgeArticle — Base de Conocimiento IA ────────────────────────────────

@admin.register(KnowledgeArticle)
class KnowledgeArticleAdmin(admin.ModelAdmin):
    list_display  = ('titulo', 'categoria', 'prioridad', '_snippet', 'activo', 'actualizado_en')
    list_filter   = ('categoria', 'activo', 'prioridad')
    search_fields = ('titulo', 'contenido', 'tags')
    list_editable = ('activo', 'prioridad')
    ordering      = ('prioridad', 'categoria', 'titulo')
    readonly_fields = ('creado_en', 'actualizado_en')

    fieldsets = (
        ('Identificación', {
            'fields': ('titulo', 'categoria', 'prioridad', 'activo'),
        }),
        ('Contenido', {
            'description': (
                'Escribe en Markdown. La IA usa este texto textualmente como contexto. '
                'Sé específico: incluye números exactos, artículos de ley, porcentajes. '
                'Máximo ~800 chars efectivos (el resto se trunca).'
            ),
            'fields': ('contenido', 'tags'),
        }),
        ('Auditoría', {
            'fields': ('creado_en', 'actualizado_en'),
            'classes': ('collapse',),
        }),
    )

    def _snippet(self, obj):
        s = obj.snippet(100)
        return format_html('<span style="color:#64748b;font-size:.85em">{}</span>', s)
    _snippet.short_description = 'Vista previa'
