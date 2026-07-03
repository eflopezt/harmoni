"""
Tests del digest diario del Centro de Acción (comunicaciones/tasks.py).

Cubre:
- Con pendientes (préstamo + vacación PENDIENTE) → 1 Notificacion EMAIL por
  superuser con email, con totales y deep-links en el cuerpo.
- Sin pendientes → no se crea ninguna notificación (anti-spam).
- Superuser sin email no recibe.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from comunicaciones.models import Notificacion
from comunicaciones.tasks import enviar_digest_diario_admins
from personal.models import Area, Personal, SubArea


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def trabajador(subarea):
    return Personal.objects.create(
        nro_doc="71000050", apellidos_nombres="DIGEST PRUEBA, EVA",
        cargo="Operario", tipo_trab="Empleado", estado="Activo",
        subarea=subarea, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("2000.00"),
    )


@pytest.fixture
def admin_con_email(db):
    return User.objects.create_superuser("jefe", "jefe@harmoni.pe", "x")


def _crear_prestamo_pendiente(trabajador):
    from prestamos.models import Prestamo, TipoPrestamo
    tipo, _ = TipoPrestamo.objects.get_or_create(
        codigo="prestamo-test", defaults={"nombre": "Préstamo Test"},
    )
    return Prestamo.objects.create(
        personal=trabajador, tipo=tipo,
        monto_solicitado=Decimal("500.00"),
        num_cuotas=1,
        estado="PENDIENTE",
    )


class TestDigestDiario:
    def test_con_pendientes_envia_a_admins(self, admin_con_email, trabajador):
        _crear_prestamo_pendiente(trabajador)

        resultado = enviar_digest_diario_admins()
        assert resultado["total_pendientes"] >= 1
        assert resultado["enviados"] == 1

        notif = Notificacion.objects.filter(
            tipo="EMAIL", destinatario_email="jefe@harmoni.pe",
        ).order_by("-id").first()
        assert notif is not None
        assert "pendiente" in notif.asunto.lower()
        assert "Préstamos" in notif.cuerpo
        # El link apunta a la bandeja unificada (F2/F3), no al módulo suelto
        assert "/aprobaciones/?tab=prestamos" in notif.cuerpo

    def test_tool_incluye_permisos_y_workflows(self, trabajador):
        """F3: la tool consolidada cubre también permisos y workflows,
        con deep-link a la bandeja unificada."""
        from django.contrib.contenttypes.models import ContentType
        from nominas.agente_ia.tools import tool_listar_aprobaciones_pendientes
        from vacaciones.models import SolicitudPermiso, TipoPermiso
        from workflows.models import EtapaFlujo, FlujoTrabajo, InstanciaFlujo

        tipo = TipoPermiso.objects.create(nombre="Permiso Digest", codigo="perm-digest")
        SolicitudPermiso.objects.create(
            personal=trabajador, tipo=tipo,
            fecha_inicio=date(2026, 8, 3), fecha_fin=date(2026, 8, 3),
            estado="PENDIENTE",
        )
        ct = ContentType.objects.get_for_model(User)
        flujo = FlujoTrabajo.objects.create(
            nombre="Flujo Digest", content_type=ct,
            campo_trigger="first_name", valor_trigger="P",
            campo_resultado="first_name",
            valor_aprobado="A", valor_rechazado="R",
        )
        etapa = EtapaFlujo.objects.create(
            flujo=flujo, orden=1, nombre="E1", tipo_aprobador="SUPERUSER")
        solicitante = User.objects.create_user("sol.digest", "sd@test.pe", "x")
        InstanciaFlujo.objects.create(
            flujo=flujo, content_type=ct, object_id=solicitante.pk,
            etapa_actual=etapa, estado="EN_PROCESO", solicitante=solicitante,
        )

        res = tool_listar_aprobaciones_pendientes()
        assert res["bloques"]["permisos"]["total"] == 1
        assert res["bloques"]["permisos"]["donde_aprobar"] == "/aprobaciones/?tab=permisos"
        assert res["bloques"]["workflows"]["total"] == 1
        assert res["bloques"]["workflows"]["donde_aprobar"] == "/aprobaciones/?tab=workflows"

    def test_sin_pendientes_no_envia(self, admin_con_email):
        resultado = enviar_digest_diario_admins()
        assert resultado == {"enviados": 0, "total_pendientes": 0}
        assert not Notificacion.objects.filter(
            metadata__tipo_evento="digest_diario_admin"
        ).exists()

    def test_admin_sin_email_no_recibe(self, db, trabajador):
        User.objects.create_superuser("sinmail", "", "x")
        _crear_prestamo_pendiente(trabajador)

        resultado = enviar_digest_diario_admins()
        assert resultado["enviados"] == 0
