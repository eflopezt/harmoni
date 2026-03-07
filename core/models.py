"""
Modelos transversales del sistema Harmoni.

AuditLog: registro automático de cambios en modelos críticos.
PreferenciaUsuario: configuración personalizada por usuario.
"""
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class AuditLog(models.Model):
    """Registro de auditoría genérico para cualquier modelo del sistema.

    Captura CREATE, UPDATE y DELETE con detalle de campos modificados.
    """

    ACCION_CHOICES = [
        ('CREATE', 'Creación'),
        ('UPDATE', 'Modificación'),
        ('DELETE', 'Eliminación'),
    ]

    # Referencia genérica al objeto modificado
    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE,
        related_name='audit_logs',
    )
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Qué pasó
    accion = models.CharField(max_length=10, choices=ACCION_CHOICES)
    descripcion = models.CharField(
        max_length=255, blank=True,
        help_text='Resumen legible del cambio.',
    )

    # Detalle de cambios (solo para UPDATE)
    cambios = models.JSONField(
        default=dict, blank=True,
        help_text='Dict con {campo: {old: ..., new: ...}} para cada campo modificado.',
    )

    # Quién lo hizo
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    # Cuándo
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['usuario', '-timestamp']),
            models.Index(fields=['accion', '-timestamp']),
        ]

    def __str__(self):
        return f'{self.get_accion_display()} · {self.content_type} #{self.object_id}'


class PreferenciaUsuario(models.Model):
    """Preferencias personalizadas por usuario (singleton por user).

    Se crea automáticamente con get_or_create la primera vez que se necesita.
    """

    ITEMS_PAGINA_CHOICES = [
        (10, '10 por página'),
        (20, '20 por página'),
        (30, '30 por página'),
        (50, '50 por página'),
    ]

    TEMA_CHOICES = [
        ('AUTO', 'Sistema (auto)'),
        ('LIGHT', 'Claro'),
        ('DARK', 'Oscuro'),
    ]

    IDIOMA_CHOICES = [
        ('es', 'Español'),
        ('en', 'English'),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='preferencias',
        verbose_name='Usuario',
    )

    # ── Interfaz ──────────────────────────────────────────────────────
    sidebar_colapsado = models.BooleanField(
        default=False,
        verbose_name='Sidebar colapsado por defecto',
    )
    items_por_pagina = models.PositiveSmallIntegerField(
        default=20,
        choices=ITEMS_PAGINA_CHOICES,
        verbose_name='Elementos por página',
    )
    tema = models.CharField(
        max_length=6,
        choices=TEMA_CHOICES,
        default='AUTO',
        verbose_name='Tema de color',
    )
    idioma = models.CharField(
        max_length=5,
        choices=IDIOMA_CHOICES,
        default='es',
        verbose_name='Idioma',
    )

    # ── Notificaciones ────────────────────────────────────────────────
    notif_email_habilitado = models.BooleanField(
        default=True,
        verbose_name='Recibir notificaciones por email',
    )
    notif_contratos = models.BooleanField(
        default=True,
        verbose_name='Alertas de contratos y período de prueba',
    )
    notif_vacaciones = models.BooleanField(
        default=True,
        verbose_name='Alertas de vacaciones',
    )
    notif_documentos = models.BooleanField(
        default=True,
        verbose_name='Alertas de documentos laborales',
    )

    # ── Dashboard ────────────────────────────────────────────────────
    dashboard_widgets = models.JSONField(
        default=list,
        blank=True,
        verbose_name='Widgets del dashboard activos',
        help_text='Lista de slugs de widgets que el usuario quiere ver en su home.',
    )

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Preferencia de Usuario'
        verbose_name_plural = 'Preferencias de Usuarios'

    def __str__(self):
        return f'Preferencias de {self.usuario}'

    @classmethod
    def para(cls, user):
        """Retorna (o crea) las preferencias del usuario dado."""
        prefs, _ = cls.objects.get_or_create(usuario=user)
        return prefs


# ─────────────────────────────────────────────────────────────────────
# PerfilAcceso — Roles/perfiles que controlan visibilidad de módulos
# ─────────────────────────────────────────────────────────────────────

class PerfilAcceso(models.Model):
    """
    Perfil de acceso (rol): define qué módulos del sidebar puede ver y usar
    un grupo de usuarios.

    Lógica de aplicación:
      - Superusuarios ignoran el perfil (acceso total siempre).
      - Los módulos del perfil son INTERSECCIÓN con los activados en
        ConfiguracionSistema: un perfil no puede habilitar lo que la empresa
        tiene desactivado.
      - Se asigna a Personal.perfil_acceso. Usuarios sin Personal asociado
        (staff sin empleado) heredan acceso de superuser o acceso mínimo.

    Roles predefinidos (creados por seed_perfiles_acceso):
      ADMIN_RRHH · JEFE_AREA · CONSULTOR · EMPLEADO
    """

    CODIGO_CHOICES = [
        ('ADMIN_RRHH',    'Administrador RRHH'),
        ('JEFE_AREA',     'Jefe de Área'),
        ('CONSULTOR',     'Consultor / Solo lectura'),
        ('EMPLEADO',      'Empleado (solo portal)'),
        ('PERSONALIZADO', 'Personalizado'),
    ]

    nombre      = models.CharField(max_length=100, verbose_name='Nombre del Perfil')
    codigo      = models.SlugField(max_length=50, unique=True, verbose_name='Código')
    descripcion = models.TextField(blank=True, verbose_name='Descripción')
    es_sistema  = models.BooleanField(
        default=False,
        verbose_name='Perfil del sistema',
        help_text='Los perfiles del sistema no se pueden eliminar.',
    )

    # ── Módulos del sidebar admin ──────────────────────────────────────
    mod_personal        = models.BooleanField(default=True,  verbose_name='Personal')
    mod_asistencia      = models.BooleanField(default=True,  verbose_name='Asistencia & Tareo')
    mod_vacaciones      = models.BooleanField(default=True,  verbose_name='Vacaciones')
    mod_documentos      = models.BooleanField(default=True,  verbose_name='Documentos')
    mod_capacitaciones  = models.BooleanField(default=True,  verbose_name='Capacitaciones')
    mod_disciplinaria   = models.BooleanField(default=False, verbose_name='Disciplinaria')
    mod_evaluaciones    = models.BooleanField(default=False, verbose_name='Evaluaciones')
    mod_encuestas       = models.BooleanField(default=True,  verbose_name='Encuestas')
    mod_salarios        = models.BooleanField(default=False, verbose_name='Salarios')
    mod_reclutamiento   = models.BooleanField(default=False, verbose_name='Reclutamiento')
    mod_prestamos       = models.BooleanField(default=True,  verbose_name='Préstamos')
    mod_viaticos        = models.BooleanField(default=False, verbose_name='Viáticos')
    mod_onboarding      = models.BooleanField(default=False, verbose_name='Onboarding')
    mod_calendario      = models.BooleanField(default=True,  verbose_name='Calendario')
    mod_analytics       = models.BooleanField(default=False, verbose_name='Analytics')
    mod_configuracion   = models.BooleanField(default=False, verbose_name='Configuración')
    mod_roster          = models.BooleanField(default=False, verbose_name='Roster')

    # ── Capacidades globales ──────────────────────────────────────────
    puede_aprobar  = models.BooleanField(
        default=False,
        verbose_name='Puede aprobar solicitudes',
        help_text='Habilita botones de aprobación en vacaciones, permisos, roster, etc.',
    )
    puede_exportar = models.BooleanField(
        default=True,
        verbose_name='Puede exportar datos',
        help_text='Habilita botones de exportación a Excel/PDF en todas las vistas.',
    )

    creado_en      = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Perfil de Acceso'
        verbose_name_plural = 'Perfiles de Acceso'
        ordering            = ['nombre']

    def __str__(self):
        return self.nombre

    def delete(self, *args, **kwargs):
        if self.es_sistema:
            raise ValueError(
                f'El perfil "{self.nombre}" es de sistema y no puede eliminarse.'
            )
        super().delete(*args, **kwargs)

    def as_modulos_dict(self) -> dict:
        """Retorna dict {mod_<modulo>: bool} para aplicar en el context processor."""
        return {
            'mod_personal':       self.mod_personal,
            'mod_asistencia':     self.mod_asistencia,
            'mod_vacaciones':     self.mod_vacaciones,
            'mod_documentos':     self.mod_documentos,
            'mod_capacitaciones': self.mod_capacitaciones,
            'mod_disciplinaria':  self.mod_disciplinaria,
            'mod_evaluaciones':   self.mod_evaluaciones,
            'mod_encuestas':      self.mod_encuestas,
            'mod_salarios':       self.mod_salarios,
            'mod_reclutamiento':  self.mod_reclutamiento,
            'mod_prestamos':      self.mod_prestamos,
            'mod_viaticos':       self.mod_viaticos,
            'mod_onboarding':     self.mod_onboarding,
            'mod_calendario':     self.mod_calendario,
            'mod_analytics':      self.mod_analytics,
            'mod_configuracion':  self.mod_configuracion,
            'mod_roster':         self.mod_roster,
        }


# ─────────────────────────────────────────────────────────────────────
# PermisoModulo — Permisos granulares por módulo (INFRA.3)
# ─────────────────────────────────────────────────────────────────────

MODULOS_SISTEMA = [
    ('personal',        'Personal'),
    ('asistencia',      'Asistencia & Tareo'),
    ('nominas',         'Nóminas'),
    ('vacaciones',      'Vacaciones & Permisos'),
    ('documentos',      'Documentos'),
    ('capacitaciones',  'Capacitaciones'),
    ('disciplinaria',   'Disciplinaria'),
    ('evaluaciones',    'Evaluaciones'),
    ('encuestas',       'Encuestas'),
    ('salarios',        'Salarios'),
    ('reclutamiento',   'Reclutamiento'),
    ('comunicaciones',  'Comunicaciones'),
    ('prestamos',       'Préstamos'),
    ('viaticos',        'Viáticos'),
    ('onboarding',      'Onboarding'),
    ('calendario',      'Calendario'),
    ('analytics',       'Analytics'),
    ('configuracion',   'Configuración'),
]


class PermisoModulo(models.Model):
    """
    Permisos granulares por módulo para usuarios no-superusuarios.
    Los superusuarios siempre tienen acceso total (bypass).
    """
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permisos_modulos',
        verbose_name='Usuario',
    )
    modulo = models.CharField(
        max_length=30,
        choices=MODULOS_SISTEMA,
        verbose_name='Módulo',
    )
    puede_ver     = models.BooleanField(default=False, verbose_name='Ver')
    puede_crear   = models.BooleanField(default=False, verbose_name='Crear')
    puede_editar  = models.BooleanField(default=False, verbose_name='Editar')
    puede_aprobar = models.BooleanField(default=False, verbose_name='Aprobar')
    puede_exportar= models.BooleanField(default=False, verbose_name='Exportar')

    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['usuario', 'modulo']
        verbose_name = 'Permiso de Módulo'
        verbose_name_plural = 'Permisos de Módulos'
        ordering = ['usuario', 'modulo']

    def __str__(self):
        return f'{self.usuario} — {self.get_modulo_display()}'


# ══════════════════════════════════════════════════════════════════════════════
# BASE DE CONOCIMIENTO IA (RAG — Fase A: keyword search / Fase B: pgvector)
# ══════════════════════════════════════════════════════════════════════════════

class KnowledgeArticle(models.Model):
    """
    Artículo de conocimiento para el asistente IA de Harmoni.

    La IA busca artículos relevantes para cada pregunta y los inyecta en el
    system prompt, permitiendo respuestas precisas sobre ley laboral peruana,
    políticas internas y procesos del sistema.

    Fase A (actual): búsqueda por keywords (ilike).
    Fase B (futura): columna `embedding vector(1536)` con pgvector para
                     búsqueda semántica por similitud de coseno.
    """

    CATEGORIA_CHOICES = [
        ('ley_laboral',   'Ley Laboral Perú'),
        ('beneficios',    'Beneficios Sociales (CTS, Grat., etc.)'),
        ('planilla',      'Planilla y Remuneraciones'),
        ('asistencia',    'Asistencia y Jornada'),
        ('vacaciones',    'Vacaciones y Permisos'),
        ('disciplinaria', 'Procedimiento Disciplinario'),
        ('politica_rrhh', 'Políticas RRHH Internas'),
        ('proceso',       'Procesos del Sistema Harmoni'),
        ('onboarding',    'Onboarding y Offboarding'),
        ('faq',           'Preguntas Frecuentes'),
        ('otro',          'Otro'),
    ]

    titulo     = models.CharField(max_length=300)
    categoria  = models.CharField(max_length=20, choices=CATEGORIA_CHOICES, db_index=True)
    contenido  = models.TextField(
        help_text='Texto en markdown. Sé específico y conciso — la IA usa esto como contexto directo.'
    )
    tags       = models.CharField(
        max_length=500, blank=True,
        help_text='Palabras clave separadas por coma. Mejoran la búsqueda. Ej: horas extra, 25%, artículo 10'
    )
    prioridad  = models.PositiveSmallIntegerField(
        default=5,
        help_text='1=alta, 10=baja. Artículos de menor número aparecen primero en resultados.'
    )
    activo     = models.BooleanField(default=True, db_index=True)
    creado_en  = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    # ── Fase B: embedding vectorial (text-embedding-3-small, 1536 dims) ──
    # Almacenado como JSON string para compatibilidad SQLite/PostgreSQL.
    # Para producción con pgvector: migrar a VectorField(dimensions=1536).
    embedding_json = models.TextField(
        blank=True, null=True,
        help_text=(
            'Vector de embedding en JSON (float[1536]). '
            'Auto-generado por: python manage.py index_knowledge_embeddings'
        ),
    )

    class Meta:
        app_label = 'core'
        verbose_name = 'Artículo de Conocimiento IA'
        verbose_name_plural = 'Base de Conocimiento IA'
        ordering = ['prioridad', 'categoria', 'titulo']

    def __str__(self):
        return f'[{self.get_categoria_display()}] {self.titulo}'

    def snippet(self, chars: int = 120) -> str:
        """Primeros N chars del contenido para previsualización."""
        c = self.contenido.strip()
        return c[:chars] + '…' if len(c) > chars else c
