"""
core/audit_models.py — Sistema de auditoría v2 (AuditEntry).

Modelo paralelo a `core.models.AuditLog` (legacy) y `asistencia.CambioCodigoLog`
(legacy, scope-limited a códigos de tareo).

`AuditEntry` cubre el item 🟡 #5 del plan estabilización Q2 2026:
audit log COMPLETO automático para Personal, Vacaciones, Préstamos,
RegistroPapeleta y PeriodoNomina vía señales `pre_save`/`post_save`/`post_delete`
registradas por `core.audit_signals.register_auditable`.

Diferencia con AuditLog (que usa GenericForeignKey/ContentType):
- AuditEntry usa CharField `entity_type` + BigIntegerField `entity_id`,
  más ligero y simple para consultas y para entidades borradas (no FK roto).
- Captura `empresa` para multi-tenant.
- `metadata` JSONField separado para request_ip, user_agent, source.

Los modelos legacy se conservan en paralelo (no se rompen).
"""
from django.conf import settings
from django.db import models


class AuditEntry(models.Model):
    """Registro de auditoría genérico de cambios en entidades críticas.

    Una fila por cada CREATE / UPDATE / DELETE en un modelo registrado vía
    `core.audit_signals.register_auditable`.
    """

    ACCION_CHOICES = [
        ('CREATE', 'Creación'),
        ('UPDATE', 'Modificación'),
        ('DELETE', 'Eliminación'),
    ]

    SOURCE_CHOICES = [
        ('web',     'Petición Web'),
        ('admin',   'Django Admin'),
        ('celery',  'Tarea Celery'),
        ('command', 'Management Command'),
        ('import',  'Importación / Bulk'),
        ('api',     'API REST'),
        ('signal',  'Señal interna (default)'),
    ]

    # ── Identidad de la entidad auditada (NO usa FK para no romper si se borra) ──
    entity_type = models.CharField(
        max_length=80,
        db_index=True,
        help_text='Nombre del modelo: Personal, SolicitudVacacion, Prestamo, etc.',
    )
    entity_id = models.BigIntegerField(
        db_index=True,
        help_text='PK del objeto modificado (puede no existir si fue DELETE).',
    )

    # ── Qué pasó ──
    accion = models.CharField(max_length=10, choices=ACCION_CHOICES, db_index=True)
    cambios = models.JSONField(
        default=dict, blank=True,
        help_text='Diff por campo: {campo: {"old": valor_ant, "new": valor_nuevo}}.',
    )
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Contexto: request_ip, user_agent, source (web/celery/admin), etc.',
    )

    # ── Quién / dónde ──
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    empresa = models.ForeignKey(
        'empresas.Empresa',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )

    # ── Cuándo ──
    fecha = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'core'
        ordering = ['-fecha']
        verbose_name = 'Entrada de Auditoría'
        verbose_name_plural = 'Entradas de Auditoría'
        indexes = [
            models.Index(fields=['entity_type', 'entity_id', '-fecha'],
                         name='audit_entry_entity_fecha_idx'),
            models.Index(fields=['usuario', '-fecha'],
                         name='audit_entry_usuario_fecha_idx'),
            models.Index(fields=['-fecha'],
                         name='audit_entry_fecha_idx'),
        ]

    def __str__(self):
        return f'{self.get_accion_display()} · {self.entity_type}#{self.entity_id}'

    @property
    def campos_modificados(self):
        """Lista de nombres de campos cambiados (vacía para CREATE/DELETE)."""
        return list(self.cambios.keys()) if isinstance(self.cambios, dict) else []
