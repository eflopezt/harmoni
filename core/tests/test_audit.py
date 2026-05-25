"""
Tests for the audit log v2 system (core.audit_models.AuditEntry +
core.audit_signals.register_auditable).

Cubre item 🟡 #5 del plan estabilización Q2 2026.

Los signals automáticos sobre Personal, SolicitudVacacion, Prestamo,
PeriodoNomina y RegistroPapeleta se conectan en CoreConfig.ready() vía
auto_register_default_models(). Estos tests verifican:
- register_auditable conecta los signals y arma el registry
- CREATE / UPDATE / DELETE generan AuditEntry correctos
- Cambios fuera de fields_to_track NO crean entries (UPDATE)
- La vista timeline solo es accesible para admin
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from core.audit_models import AuditEntry
from core.audit_signals import (
    _REGISTERED,
    get_registered,
    register_auditable,
)
from personal.models import Area, Personal

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _make_personal(nro_doc='40000001', sueldo=Decimal('2500.00'),
                   cargo='Analista', estado='Activo'):
    Area.objects.get_or_create(nombre='Administracion')
    return Personal.objects.create(
        nro_doc=nro_doc,
        apellidos_nombres='Test, Empleado',
        cargo=cargo,
        tipo_trab='Empleado',
        sueldo_base=sueldo,
        estado=estado,
    )


# ─────────────────────────────────────────────────────────────────────
# 1. Registry & introspección
# ─────────────────────────────────────────────────────────────────────

class TestRegisterAuditable(TestCase):
    """register_auditable arma el registry y conecta los signals."""

    def test_default_models_registered_via_apps_ready(self):
        """auto_register_default_models() corrió en CoreConfig.ready()."""
        reg = get_registered()
        assert 'personal.Personal' in reg
        assert 'vacaciones.SolicitudVacacion' in reg
        assert 'prestamos.Prestamo' in reg
        assert 'nominas.PeriodoNomina' in reg
        # asistencia usa label='tareo' por compat legacy
        assert 'tareo.RegistroPapeleta' in reg

    def test_registry_includes_tracked_fields(self):
        """El registry guarda la lista de fields_to_track para introspección."""
        reg = get_registered()
        personal_fields = reg['personal.Personal']
        assert 'sueldo_base' in personal_fields
        assert 'cargo' in personal_fields
        assert 'estado' in personal_fields

    def test_double_register_is_idempotent(self):
        """Registrar el mismo modelo dos veces no duplica signals."""
        # Personal ya está registrado por auto_register_default_models;
        # llamar de nuevo debe ser no-op (warning + return).
        before = list(_REGISTERED['personal.Personal'])
        register_auditable(Personal, fields_to_track=['nro_doc', 'cargo'])
        after = list(_REGISTERED['personal.Personal'])
        # Los fields originales se preservan (no se sobreescriben).
        assert before == after


# ─────────────────────────────────────────────────────────────────────
# 2. Comportamiento de signals: CREATE / UPDATE / DELETE
# ─────────────────────────────────────────────────────────────────────

class TestAuditEntrySignals(TestCase):
    """Signals automáticos generan AuditEntry con el diff correcto."""

    def setUp(self):
        AuditEntry.objects.all().delete()

    def test_create_personal_emits_create_entry(self):
        p = _make_personal()
        entries = AuditEntry.objects.filter(
            entity_type='Personal', entity_id=p.pk
        )
        assert entries.count() == 1
        e = entries.first()
        assert e.accion == 'CREATE'
        # cambios debe tener old=None y new=valor para cada field trackeado
        assert e.cambios['sueldo_base']['old'] is None
        assert e.cambios['sueldo_base']['new'] == '2500.00'
        assert e.cambios['estado']['new'] == 'Activo'

    def test_update_personal_sueldo_creates_update_entry_with_diff(self):
        p = _make_personal(sueldo=Decimal('2000.00'))
        # Limpio el CREATE para aislar el UPDATE
        AuditEntry.objects.all().delete()

        p.sueldo_base = Decimal('3500.00')
        p.save()

        entries = AuditEntry.objects.filter(
            entity_type='Personal', entity_id=p.pk, accion='UPDATE'
        )
        assert entries.count() == 1
        e = entries.first()
        assert 'sueldo_base' in e.cambios
        assert e.cambios['sueldo_base']['old'] == '2000.00'
        assert e.cambios['sueldo_base']['new'] == '3500.00'
        # Solo el campo cambiado figura en el diff
        assert list(e.cambios.keys()) == ['sueldo_base']

    def test_update_without_tracked_field_change_does_not_create_entry(self):
        """Modificar un campo NO trackeado (ej. correo) no crea AuditEntry."""
        p = _make_personal()
        AuditEntry.objects.all().delete()

        # `correo_personal` no está en fields_to_track de Personal
        p.correo_personal = 'nuevo@test.com'
        p.save()

        # Como el diff es vacío (ningún tracked field cambió) → no se registra.
        assert AuditEntry.objects.filter(
            entity_type='Personal', entity_id=p.pk, accion='UPDATE'
        ).count() == 0

    def test_delete_personal_creates_delete_entry(self):
        p = _make_personal(nro_doc='40000099')
        pk = p.pk
        AuditEntry.objects.all().delete()

        p.delete()

        entries = AuditEntry.objects.filter(
            entity_type='Personal', entity_id=pk, accion='DELETE'
        )
        assert entries.count() == 1
        e = entries.first()
        # En DELETE el diff lleva el snapshot del valor old.
        assert e.cambios['sueldo_base']['old'] == '2500.00'
        assert e.cambios['sueldo_base']['new'] is None

    def test_multiple_updates_create_multiple_entries(self):
        p = _make_personal()
        AuditEntry.objects.all().delete()

        p.cargo = 'Jefe'
        p.save()
        p.cargo = 'Gerente'
        p.save()

        entries = AuditEntry.objects.filter(
            entity_type='Personal', entity_id=p.pk, accion='UPDATE'
        ).order_by('fecha')
        assert entries.count() == 2
        assert entries[0].cambios['cargo'] == {'old': 'Analista', 'new': 'Jefe'}
        assert entries[1].cambios['cargo'] == {'old': 'Jefe', 'new': 'Gerente'}


# ─────────────────────────────────────────────────────────────────────
# 3. Vista timeline — permisos y rendering
# ─────────────────────────────────────────────────────────────────────

@override_settings(ALLOWED_HOSTS=['*', 'testserver', 'demo.harmoni.pe'])
class TestAuditTimelineView(TestCase):
    """Permisos y respuestas de la vista /sistema/audit/<entity>/<id>/."""

    def setUp(self):
        AuditEntry.objects.all().delete()
        self.admin = User.objects.create_superuser(
            username='admin_audit', password='pw1234',
            email='a@test.com',
        )
        self.normal = User.objects.create_user(
            username='normal_audit', password='pw1234',
        )
        self.personal = _make_personal(nro_doc='40000050')
        self.url = reverse(
            'audit_entry_timeline',
            kwargs={'entity_type': 'Personal', 'entity_id': self.personal.pk},
        )

    def test_anonymous_redirects_to_login(self):
        resp = self.client.get(self.url)
        # @login_required redirige a login (302).
        assert resp.status_code in (302, 301)
        assert '/login' in resp['Location'].lower() or 'login' in resp['Location'].lower()

    def test_normal_user_gets_redirect_or_403(self):
        """user_passes_test redirige a login_url cuando falla el check."""
        self.client.login(username='normal_audit', password='pw1234')
        resp = self.client.get(self.url)
        # solo_admin = user_passes_test(is_superuser, login_url='login')
        # → si no es admin, redirige a login (302).
        assert resp.status_code in (302, 403)

    def test_admin_sees_timeline_with_entries(self):
        # Genero algo de actividad en este Personal
        self.personal.cargo = 'Jefe'
        self.personal.save()

        self.client.login(username='admin_audit', password='pw1234')
        resp = self.client.get(self.url)
        assert resp.status_code == 200
        content = resp.content.decode('utf-8')
        # Aparece el entity_type y se ven los cambios
        assert 'Personal' in content
        assert 'cargo' in content
        # El template incluye 'Creación' (CREATE inicial) y 'Modificación'
        assert 'Modificación' in content or 'UPDATE' in content
