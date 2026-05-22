"""Tests for workflows.engine (capa publica del motor de aprobaciones).

Cubre:
  - crear_instancia inicializa correctamente
  - avanzar_instancia con APROBAR avanza paso
  - avanzar_instancia con RECHAZAR cierra como RECHAZADO
  - Aprobar el ultimo paso -> estado APROBADO
  - aprobadores_actuales devuelve lista correcta (USUARIO/GRUPO/SUPERUSER)
  - signal_objeto_completado invoca hook personalizado y metodos estandar
  - Vista bandeja responde 200
"""
from unittest.mock import PropertyMock, patch

import pytest
from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.test import Client, TestCase
from django.urls import reverse

from workflows.engine import (
    aprobadores_actuales,
    avanzar_instancia,
    crear_instancia,
    signal_objeto_completado,
)
from workflows.models import (
    EtapaFlujo,
    FlujoTrabajo,
    InstanciaFlujo,
    PasoFlujo,
)


def _self_ct():
    """ContentType seguro como placeholder de objeto vinculado."""
    return ContentType.objects.get_for_model(FlujoTrabajo)


# ---------------------------------------------------------------------------
# crear_instancia
# ---------------------------------------------------------------------------

class CrearInstanciaTests(TestCase):

    def setUp(self):
        self.solicitante = User.objects.create_user(
            'solicit', 'solicit@test.com', 'pass',
        )
        self.aprobador = User.objects.create_user(
            'aprob', 'aprob@test.com', 'pass', is_superuser=True,
        )
        self.flujo = FlujoTrabajo.objects.create(
            nombre='Flujo Test Engine',
            content_type=_self_ct(),
            valor_trigger='X',
        )

    @patch('workflows.services._notificar_aprobadores')
    def test_crear_instancia_basica(self, _mock_notif):
        EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='E1',
            tipo_aprobador='SUPERUSER',
        )

        inst = crear_instancia(
            flujo_codigo='Flujo Test Engine',
            solicitante=self.solicitante,
            titulo='Mi solicitud',
            descripcion='Detalle',
        )

        assert inst is not None
        assert inst.flujo == self.flujo
        assert inst.solicitante == self.solicitante
        assert inst.estado == 'EN_PROCESO'
        assert inst.etapa_actual.orden == 1
        assert inst.etapa_vence_en is not None
        assert inst.metadata['titulo'] == 'Mi solicitud'
        assert inst.metadata['descripcion'] == 'Detalle'

    @patch('workflows.services._notificar_aprobadores')
    def test_crear_acepta_flujo_por_pk_y_objeto(self, _mock_notif):
        EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='E1',
            tipo_aprobador='SUPERUSER',
        )
        # Por pk numerico
        inst = crear_instancia(self.flujo.pk, self.solicitante)
        assert inst is not None and inst.flujo == self.flujo

        # Por instancia directa
        inst2 = crear_instancia(self.flujo, self.solicitante)
        assert inst2 is not None and inst2.flujo == self.flujo

    def test_crear_flujo_inexistente_devuelve_none(self):
        assert crear_instancia('No Existe', self.solicitante) is None

    def test_crear_flujo_sin_etapas_lanza(self):
        with pytest.raises(ValueError, match='no tiene etapas'):
            crear_instancia(self.flujo, self.solicitante)

    def test_crear_flujo_inactivo_devuelve_none(self):
        EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='E1',
            tipo_aprobador='SUPERUSER',
        )
        self.flujo.activo = False
        self.flujo.save()
        assert crear_instancia(self.flujo, self.solicitante) is None


# ---------------------------------------------------------------------------
# avanzar_instancia
# ---------------------------------------------------------------------------

class AvanzarInstanciaTests(TestCase):

    def setUp(self):
        self.solicitante = User.objects.create_user(
            'solicit', 'solicit@test.com', 'pass',
        )
        self.aprobador = User.objects.create_user(
            'aprob', 'aprob@test.com', 'pass', is_superuser=True,
        )
        self.no_aprobador = User.objects.create_user(
            'noaprob', 'noaprob@test.com', 'pass',
        )
        self.flujo = FlujoTrabajo.objects.create(
            nombre='Flujo Avance',
            content_type=_self_ct(),
            valor_trigger='X',
            notificar_email=False,
        )
        self.e1 = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='E1',
            tipo_aprobador='SUPERUSER',
        )
        self.e2 = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=2, nombre='E2',
            tipo_aprobador='SUPERUSER',
        )

    def _instancia(self, etapa=None):
        return InstanciaFlujo.objects.create(
            flujo=self.flujo,
            content_type=_self_ct(),
            object_id=self.flujo.pk,
            etapa_actual=etapa or self.e1,
            estado='EN_PROCESO',
            solicitante=self.solicitante,
        )

    @patch('workflows.services._notificar_aprobadores')
    def test_aprobar_avanza_a_siguiente_paso(self, _mock_notif):
        inst = self._instancia()

        ok = avanzar_instancia(inst, self.aprobador, 'APROBAR', 'OK')

        assert ok is True
        inst.refresh_from_db()
        assert inst.etapa_actual == self.e2
        assert inst.estado == 'EN_PROCESO'
        # PasoFlujo registrado
        paso = PasoFlujo.objects.get(instancia=inst, etapa=self.e1)
        assert paso.decision == 'APROBADO'
        assert paso.aprobador == self.aprobador

    @patch('workflows.services._notificar_aprobadores')
    def test_aprobar_ultimo_paso_cierra_como_aprobado(self, _mock_notif):
        inst = self._instancia(etapa=self.e2)

        ok = avanzar_instancia(inst, self.aprobador, 'APROBAR')

        assert ok is True
        inst.refresh_from_db()
        assert inst.estado == 'APROBADO'
        assert inst.completado_en is not None
        assert inst.etapa_actual is None

    def test_rechazar_cierra_inmediatamente(self):
        inst = self._instancia()

        ok = avanzar_instancia(
            inst, self.aprobador, 'RECHAZAR', 'No procede',
        )

        assert ok is True
        inst.refresh_from_db()
        assert inst.estado == 'RECHAZADO'
        assert inst.completado_en is not None

    def test_usuario_sin_permiso_devuelve_false(self):
        inst = self._instancia()

        ok = avanzar_instancia(inst, self.no_aprobador, 'APROBAR')

        assert ok is False
        assert PasoFlujo.objects.filter(instancia=inst).count() == 0

    def test_accion_invalida_lanza_valueerror(self):
        inst = self._instancia()
        with pytest.raises(ValueError, match='Accion invalida'):
            avanzar_instancia(inst, self.aprobador, 'EXPLOTAR')

    @patch('workflows.services._notificar_aprobadores')
    def test_comentar_no_avanza_pero_registra(self, _mock_notif):
        inst = self._instancia()

        ok = avanzar_instancia(
            inst, self.no_aprobador, 'COMENTAR', 'Tengo dudas',
        )

        assert ok is True
        inst.refresh_from_db()
        # No avanzo
        assert inst.etapa_actual == self.e1
        assert inst.estado == 'EN_PROCESO'
        # Pero quedo registro
        paso = PasoFlujo.objects.get(instancia=inst)
        assert '[Comentario]' in paso.comentario
        assert 'Tengo dudas' in paso.comentario

    def test_comentar_vacio_lanza(self):
        inst = self._instancia()
        with pytest.raises(ValueError, match='vacio'):
            avanzar_instancia(inst, self.aprobador, 'COMENTAR', '')

    def test_no_avanza_si_instancia_ya_finalizada(self):
        inst = self._instancia()
        inst.estado = 'APROBADO'
        inst.save()

        ok = avanzar_instancia(inst, self.aprobador, 'APROBAR')

        assert ok is False


# ---------------------------------------------------------------------------
# aprobadores_actuales
# ---------------------------------------------------------------------------

class AprobadoresActualesTests(TestCase):

    def setUp(self):
        self.super = User.objects.create_user(
            'super', 's@t.com', 'pass', is_superuser=True,
        )
        self.user_a = User.objects.create_user('user_a', 'a@t.com', 'pass')
        self.user_b = User.objects.create_user('user_b', 'b@t.com', 'pass')
        self.user_c = User.objects.create_user('user_c', 'c@t.com', 'pass')
        self.grupo = Group.objects.create(name='G1')
        self.user_a.groups.add(self.grupo)
        self.user_b.groups.add(self.grupo)

        self.flujo = FlujoTrabajo.objects.create(
            nombre='F', content_type=_self_ct(), valor_trigger='X',
        )

    def _instancia(self, etapa):
        return InstanciaFlujo.objects.create(
            flujo=self.flujo,
            content_type=_self_ct(),
            object_id=self.flujo.pk,
            etapa_actual=etapa,
            estado='EN_PROCESO',
            solicitante=self.user_c,
        )

    def test_superuser(self):
        e = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='S',
            tipo_aprobador='SUPERUSER',
        )
        inst = self._instancia(e)
        assert self.super in aprobadores_actuales(inst)

    def test_usuario_especifico(self):
        e = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='U',
            tipo_aprobador='USUARIO', aprobador_usuario=self.user_a,
        )
        inst = self._instancia(e)
        assert aprobadores_actuales(inst) == [self.user_a]

    def test_grupo_django(self):
        e = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='G',
            tipo_aprobador='GRUPO_DJANGO', aprobador_grupo=self.grupo,
        )
        inst = self._instancia(e)
        aprobadores = aprobadores_actuales(inst)
        assert self.user_a in aprobadores
        assert self.user_b in aprobadores
        assert self.user_c not in aprobadores

    def test_incluye_usuario_escalado(self):
        e = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='U',
            tipo_aprobador='USUARIO', aprobador_usuario=self.user_a,
        )
        inst = self._instancia(e)
        inst.metadata = {'escalado_a_user_id': self.user_c.pk}
        inst.save()
        aprobadores = aprobadores_actuales(inst)
        assert self.user_a in aprobadores
        assert self.user_c in aprobadores

    def test_instancia_finalizada_devuelve_vacio(self):
        e = EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='S',
            tipo_aprobador='SUPERUSER',
        )
        inst = self._instancia(e)
        inst.estado = 'APROBADO'
        inst.save()
        assert aprobadores_actuales(inst) == []


# ---------------------------------------------------------------------------
# signal_objeto_completado
# ---------------------------------------------------------------------------

class SignalObjetoCompletadoTests(TestCase):
    """Verifica que el helper invoque hook personalizado o aprobar()/rechazar()."""

    def setUp(self):
        self.user = User.objects.create_user('u', 'u@t.com', 'pass')
        self.flujo = FlujoTrabajo.objects.create(
            nombre='F', content_type=_self_ct(), valor_trigger='X',
        )

    def _instancia(self, estado='APROBADO'):
        inst = InstanciaFlujo.objects.create(
            flujo=self.flujo,
            content_type=_self_ct(),
            object_id=self.flujo.pk,
            estado=estado, solicitante=self.user,
        )
        return inst

    def test_invoca_hook_personalizado(self):
        inst = self._instancia(estado='APROBADO')

        class FakeObjeto:
            def __init__(self):
                self.llamado = False
                self.instancia_recibida = None

            def on_workflow_completado(self, instancia):
                self.llamado = True
                self.instancia_recibida = instancia

        fake = FakeObjeto()
        with patch.object(
            InstanciaFlujo, 'objeto',
            new_callable=PropertyMock, return_value=fake,
        ):
            ok = signal_objeto_completado(inst)

        assert ok is True
        assert fake.llamado is True
        assert fake.instancia_recibida is inst

    def test_invoca_aprobar_si_existe(self):
        inst = self._instancia(estado='APROBADO')

        class FakeObjeto:
            def __init__(self):
                self.aprobado = False
            def aprobar(self):
                self.aprobado = True

        fake = FakeObjeto()
        with patch.object(
            InstanciaFlujo, 'objeto',
            new_callable=PropertyMock, return_value=fake,
        ):
            ok = signal_objeto_completado(inst)

        assert ok is True
        assert fake.aprobado is True

    def test_invoca_rechazar_si_rechazado(self):
        inst = self._instancia(estado='RECHAZADO')

        class FakeObjeto:
            def __init__(self):
                self.rechazado = False
            def rechazar(self):
                self.rechazado = True

        fake = FakeObjeto()
        with patch.object(
            InstanciaFlujo, 'objeto',
            new_callable=PropertyMock, return_value=fake,
        ):
            ok = signal_objeto_completado(inst)

        assert ok is True
        assert fake.rechazado is True


# ---------------------------------------------------------------------------
# Integracion: flujo completo de 2 etapas
# ---------------------------------------------------------------------------

class FlujoCompletoTests(TestCase):
    """End-to-end: crear + avanzar 2 etapas hasta APROBADO."""

    def setUp(self):
        self.solicitante = User.objects.create_user(
            'sol', 's@t.com', 'pass',
        )
        self.aprobador = User.objects.create_user(
            'apr', 'a@t.com', 'pass', is_superuser=True,
        )
        self.flujo = FlujoTrabajo.objects.create(
            nombre='Completo',
            content_type=_self_ct(),
            valor_trigger='X',
            notificar_email=False,
        )
        EtapaFlujo.objects.create(
            flujo=self.flujo, orden=1, nombre='E1',
            tipo_aprobador='SUPERUSER',
        )
        EtapaFlujo.objects.create(
            flujo=self.flujo, orden=2, nombre='E2',
            tipo_aprobador='SUPERUSER',
        )

    @patch('workflows.services._notificar_aprobadores')
    def test_recorrido_completo(self, _mock_notif):
        inst = crear_instancia('Completo', self.solicitante, titulo='X')
        assert inst.estado == 'EN_PROCESO'

        # Paso 1
        avanzar_instancia(inst, self.aprobador, 'APROBAR', 'paso 1 ok')
        inst.refresh_from_db()
        assert inst.estado == 'EN_PROCESO'
        assert inst.etapa_actual.orden == 2

        # Paso 2 -> cierra
        avanzar_instancia(inst, self.aprobador, 'APROBAR', 'paso 2 final')
        inst.refresh_from_db()
        assert inst.estado == 'APROBADO'
        assert PasoFlujo.objects.filter(instancia=inst).count() == 2


# ---------------------------------------------------------------------------
# Vista bandeja responde 200
# ---------------------------------------------------------------------------

class VistaBandejaTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'aprob', 'a@t.com', 'pass', is_superuser=True,
        )
        self.client = Client()
        self.client.login(username='aprob', password='pass')

    def test_bandeja_200(self):
        url = reverse('workflow_bandeja')
        resp = self.client.get(url)
        assert resp.status_code == 200

    def test_bandeja_resumen_ajax_200(self):
        url = reverse('workflow_bandeja_resumen')
        resp = self.client.get(url)
        assert resp.status_code == 200
        data = resp.json()
        assert 'pendientes_total' in data
        assert 'urgentes' in data
        assert 'vencidos' in data
