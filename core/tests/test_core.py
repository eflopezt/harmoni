"""
Tests for the Core module — AuditLog, PerfilAcceso, PermisoModulo.

Uses pytest with Django TestCase.
"""
import pytest
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db import IntegrityError
from django.test import TestCase

from core.models import (
    AuditLog,
    PerfilAcceso,
    PermisoModulo,
    PreferenciaUsuario,
    MODULOS_SISTEMA,
)


# ═══════════════════════════════════════════════════════════════════
# AuditLog
# ═══════════════════════════════════════════════════════════════════

class TestAuditLogCreation(TestCase):
    """Test creation and querying of AuditLog entries."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='auditor', password='test1234'
        )
        # Use the User model itself as the audited content type for testing
        self.ct = ContentType.objects.get_for_model(User)

    def _create_log(self, accion='CREATE', **kwargs):
        defaults = {
            'content_type': self.ct,
            'object_id': self.user.pk,
            'accion': accion,
            'descripcion': f'{accion} test',
            'usuario': self.user,
        }
        defaults.update(kwargs)
        return AuditLog.objects.create(**defaults)

    def test_create_audit_log(self):
        log = self._create_log()
        assert log.accion == 'CREATE'
        assert log.content_type == self.ct
        assert log.object_id == self.user.pk
        assert log.timestamp is not None

    def test_str_representation(self):
        log = self._create_log(accion='UPDATE')
        expected = f'Modificación · {self.ct} #{self.user.pk}'
        assert str(log) == expected

    def test_create_action(self):
        log = self._create_log(accion='CREATE', descripcion='Created employee')
        assert log.get_accion_display() == 'Creación'

    def test_update_action_with_cambios(self):
        """UPDATE logs store field-level changes in the cambios JSONField."""
        cambios = {
            'nombre': {'old': 'Juan', 'new': 'Juan Carlos'},
            'email': {'old': 'j@test.com', 'new': 'jc@test.com'},
        }
        log = self._create_log(accion='UPDATE', cambios=cambios)
        log.refresh_from_db()
        assert log.cambios['nombre']['old'] == 'Juan'
        assert log.cambios['nombre']['new'] == 'Juan Carlos'
        assert log.cambios['email']['new'] == 'jc@test.com'

    def test_delete_action(self):
        log = self._create_log(accion='DELETE', descripcion='Deleted record')
        assert log.get_accion_display() == 'Eliminación'

    def test_cambios_defaults_to_empty_dict(self):
        log = AuditLog.objects.create(
            content_type=self.ct,
            object_id=self.user.pk,
            accion='CREATE',
        )
        assert log.cambios == {}

    def test_ip_address_stored(self):
        log = self._create_log(ip_address='192.168.1.100')
        log.refresh_from_db()
        assert log.ip_address == '192.168.1.100'

    def test_ip_address_ipv6(self):
        log = self._create_log(ip_address='::1')
        log.refresh_from_db()
        assert log.ip_address == '::1'

    def test_usuario_set_null_on_delete(self):
        """Deleting the acting user sets usuario to NULL, preserving the log."""
        log = self._create_log()
        self.user.delete()
        log.refresh_from_db()
        assert log.usuario is None

    def test_ordering_by_timestamp_descending(self):
        """Logs are ordered by timestamp descending (most recent first)."""
        log1 = self._create_log(descripcion='First')
        log2 = self._create_log(descripcion='Second')
        log3 = self._create_log(descripcion='Third')
        descs = list(AuditLog.objects.values_list('descripcion', flat=True))
        assert descs == ['Third', 'Second', 'First']

    def test_filter_by_accion(self):
        self._create_log(accion='CREATE')
        self._create_log(accion='UPDATE')
        self._create_log(accion='UPDATE')
        self._create_log(accion='DELETE')
        assert AuditLog.objects.filter(accion='UPDATE').count() == 2
        assert AuditLog.objects.filter(accion='CREATE').count() == 1
        assert AuditLog.objects.filter(accion='DELETE').count() == 1

    def test_filter_by_content_type_and_object_id(self):
        """Filtering by content_type + object_id returns logs for a specific object."""
        other_user = User.objects.create_user(username='other', password='pw')
        self._create_log(object_id=self.user.pk)
        self._create_log(object_id=other_user.pk)
        logs = AuditLog.objects.filter(
            content_type=self.ct, object_id=self.user.pk
        )
        assert logs.count() == 1

    def test_filter_by_usuario(self):
        other_user = User.objects.create_user(username='other2', password='pw')
        self._create_log(usuario=self.user)
        self._create_log(usuario=other_user)
        assert AuditLog.objects.filter(usuario=self.user).count() == 1

    def test_generic_foreign_key_resolves(self):
        """content_object resolves to the actual model instance."""
        log = self._create_log()
        assert log.content_object == self.user


# ═══════════════════════════════════════════════════════════════════
# PerfilAcceso — RBAC Profile
# ═══════════════════════════════════════════════════════════════════

class TestPerfilAcceso(TestCase):
    """Test RBAC profile creation, module flags, and deletion protection."""

    def _create_perfil(self, **kwargs):
        defaults = {
            'nombre': 'Admin RRHH',
            'codigo': 'ADMIN_RRHH',
            'descripcion': 'Full RRHH access',
            'es_sistema': False,
        }
        defaults.update(kwargs)
        return PerfilAcceso.objects.create(**defaults)

    def test_create_perfil(self):
        perfil = self._create_perfil()
        assert perfil.nombre == 'Admin RRHH'
        assert perfil.codigo == 'ADMIN_RRHH'
        assert perfil.creado_en is not None

    def test_str_representation(self):
        perfil = self._create_perfil()
        assert str(perfil) == 'Admin RRHH'

    def test_codigo_is_unique(self):
        self._create_perfil(codigo='ADMIN_RRHH')
        with pytest.raises(IntegrityError):
            self._create_perfil(codigo='ADMIN_RRHH', nombre='Duplicate')

    def test_default_module_flags(self):
        """Verify default True/False for each module flag."""
        perfil = self._create_perfil()
        # Defaults True
        assert perfil.mod_personal is True
        assert perfil.mod_asistencia is True
        assert perfil.mod_vacaciones is True
        assert perfil.mod_documentos is True
        assert perfil.mod_capacitaciones is True
        assert perfil.mod_encuestas is True
        assert perfil.mod_prestamos is True
        assert perfil.mod_calendario is True
        # Defaults False
        assert perfil.mod_disciplinaria is False
        assert perfil.mod_evaluaciones is False
        assert perfil.mod_salarios is False
        assert perfil.mod_reclutamiento is False
        assert perfil.mod_viaticos is False
        assert perfil.mod_onboarding is False
        assert perfil.mod_analytics is False
        assert perfil.mod_configuracion is False
        assert perfil.mod_roster is False

    def test_puede_aprobar_default_false(self):
        perfil = self._create_perfil()
        assert perfil.puede_aprobar is False

    def test_puede_exportar_default_true(self):
        perfil = self._create_perfil()
        assert perfil.puede_exportar is True

    def test_as_modulos_dict(self):
        """as_modulos_dict returns a dict with all 17 module flags."""
        perfil = self._create_perfil()
        d = perfil.as_modulos_dict()
        assert isinstance(d, dict)
        assert len(d) == 17
        assert d['mod_personal'] is True
        assert d['mod_analytics'] is False
        # All keys start with 'mod_'
        assert all(k.startswith('mod_') for k in d)

    def test_as_modulos_dict_reflects_custom_flags(self):
        """Custom module flags are reflected in as_modulos_dict."""
        perfil = self._create_perfil(
            mod_analytics=True,
            mod_salarios=True,
            mod_personal=False,
        )
        d = perfil.as_modulos_dict()
        assert d['mod_analytics'] is True
        assert d['mod_salarios'] is True
        assert d['mod_personal'] is False

    def test_sistema_perfil_cannot_be_deleted(self):
        """System profiles (es_sistema=True) raise ValueError on delete."""
        perfil = self._create_perfil(
            codigo='EMPLEADO', nombre='Empleado', es_sistema=True
        )
        with pytest.raises(ValueError, match='no puede eliminarse'):
            perfil.delete()
        # Verify it still exists
        assert PerfilAcceso.objects.filter(pk=perfil.pk).exists()

    def test_non_sistema_perfil_can_be_deleted(self):
        """Non-system profiles can be deleted normally."""
        perfil = self._create_perfil(
            codigo='CUSTOM', nombre='Custom', es_sistema=False
        )
        pk = perfil.pk
        perfil.delete()
        assert not PerfilAcceso.objects.filter(pk=pk).exists()

    def test_ordering_by_nombre(self):
        self._create_perfil(codigo='C_CONSULTOR', nombre='Consultor')
        self._create_perfil(codigo='A_ADMIN', nombre='Admin RRHH')
        self._create_perfil(codigo='E_EMPLEADO', nombre='Empleado')
        nombres = list(PerfilAcceso.objects.values_list('nombre', flat=True))
        assert nombres == ['Admin RRHH', 'Consultor', 'Empleado']

    def test_empleado_profile_minimal_access(self):
        """An 'Empleado' profile should have most modules disabled."""
        perfil = self._create_perfil(
            codigo='EMPLEADO_TEST', nombre='Empleado',
            mod_personal=False,
            mod_asistencia=False,
            mod_vacaciones=False,
            mod_documentos=False,
            mod_capacitaciones=False,
            mod_encuestas=False,
            mod_prestamos=False,
            mod_calendario=True,
        )
        d = perfil.as_modulos_dict()
        enabled = [k for k, v in d.items() if v]
        assert enabled == ['mod_calendario']


# ═══════════════════════════════════════════════════════════════════
# PermisoModulo — Granular Module Permissions
# ═══════════════════════════════════════════════════════════════════

class TestPermisoModulo(TestCase):
    """Test granular per-user, per-module permission mapping."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='perm_user', password='test1234'
        )

    def _create_permiso(self, modulo='personal', **kwargs):
        defaults = {
            'usuario': self.user,
            'modulo': modulo,
            'puede_ver': False,
            'puede_crear': False,
            'puede_editar': False,
            'puede_aprobar': False,
            'puede_exportar': False,
        }
        defaults.update(kwargs)
        return PermisoModulo.objects.create(**defaults)

    def test_create_permiso(self):
        perm = self._create_permiso(modulo='personal', puede_ver=True)
        assert perm.usuario == self.user
        assert perm.modulo == 'personal'
        assert perm.puede_ver is True
        assert perm.puede_crear is False

    def test_str_representation(self):
        perm = self._create_permiso(modulo='nominas')
        assert 'Nóminas' in str(perm)
        assert self.user.username in str(perm)

    def test_unique_usuario_modulo_constraint(self):
        """A user can only have one permission record per module."""
        self._create_permiso(modulo='personal')
        with pytest.raises(IntegrityError):
            self._create_permiso(modulo='personal')

    def test_all_permissions_false_by_default(self):
        perm = self._create_permiso()
        assert perm.puede_ver is False
        assert perm.puede_crear is False
        assert perm.puede_editar is False
        assert perm.puede_aprobar is False
        assert perm.puede_exportar is False

    def test_full_permissions(self):
        """A user with all permissions enabled."""
        perm = self._create_permiso(
            modulo='personal',
            puede_ver=True,
            puede_crear=True,
            puede_editar=True,
            puede_aprobar=True,
            puede_exportar=True,
        )
        assert perm.puede_ver is True
        assert perm.puede_crear is True
        assert perm.puede_editar is True
        assert perm.puede_aprobar is True
        assert perm.puede_exportar is True

    def test_multiple_modules_per_user(self):
        """A user can have permissions for multiple modules."""
        self._create_permiso(modulo='personal', puede_ver=True)
        self._create_permiso(modulo='nominas', puede_ver=True, puede_crear=True)
        self._create_permiso(modulo='vacaciones', puede_ver=True)
        perms = PermisoModulo.objects.filter(usuario=self.user)
        assert perms.count() == 3

    def test_filter_modules_user_can_view(self):
        """Query which modules a user can view."""
        self._create_permiso(modulo='personal', puede_ver=True)
        self._create_permiso(modulo='nominas', puede_ver=False)
        self._create_permiso(modulo='vacaciones', puede_ver=True)
        viewable = PermisoModulo.objects.filter(
            usuario=self.user, puede_ver=True
        ).values_list('modulo', flat=True)
        assert set(viewable) == {'personal', 'vacaciones'}

    def test_filter_modules_user_can_approve(self):
        """Query which modules a user can approve."""
        self._create_permiso(modulo='vacaciones', puede_aprobar=True)
        self._create_permiso(modulo='personal', puede_aprobar=False)
        approvable = PermisoModulo.objects.filter(
            usuario=self.user, puede_aprobar=True
        ).values_list('modulo', flat=True)
        assert list(approvable) == ['vacaciones']

    def test_modulos_sistema_list(self):
        """MODULOS_SISTEMA contains the expected core modules."""
        codigos = [code for code, _ in MODULOS_SISTEMA]
        assert 'personal' in codigos
        assert 'nominas' in codigos
        assert 'asistencia' in codigos
        assert 'vacaciones' in codigos
        assert 'analytics' in codigos
        assert 'configuracion' in codigos
        assert len(codigos) == 18

    def test_ordering_by_usuario_and_modulo(self):
        """Permissions are ordered by usuario then modulo."""
        self._create_permiso(modulo='vacaciones')
        self._create_permiso(modulo='asistencia')
        self._create_permiso(modulo='personal')
        modulos = list(
            PermisoModulo.objects.filter(usuario=self.user)
            .values_list('modulo', flat=True)
        )
        assert modulos == sorted(modulos)

    def test_permissions_deleted_on_user_cascade(self):
        """Deleting a user cascades to delete their module permissions."""
        self._create_permiso(modulo='personal')
        self._create_permiso(modulo='nominas')
        assert PermisoModulo.objects.filter(usuario=self.user).count() == 2
        self.user.delete()
        assert PermisoModulo.objects.count() == 0

    def test_actualizado_en_auto_updated(self):
        perm = self._create_permiso(modulo='personal')
        assert perm.actualizado_en is not None
        old_ts = perm.actualizado_en
        perm.puede_ver = True
        perm.save()
        perm.refresh_from_db()
        assert perm.actualizado_en >= old_ts
