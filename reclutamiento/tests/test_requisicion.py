"""
Tests del flujo de aprobación de requisición de vacante.

Flujo esperado:
    BORRADOR → POR_APROBAR → APROBADA (nuevo estado, ya no regresa a borrador)
                           → BORRADOR (si se rechaza)

Publicar queda bloqueado SOLO mientras está POR_APROBAR; una vacante que
nunca pasó por aprobación puede publicarse igual (flujo aditivo).
"""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area
from reclutamiento.models import Vacante

pytestmark = pytest.mark.django_db


@pytest.fixture
def aprobador(client):
    u = User.objects.create_user(
        username='jefe_rrhh', password='x', is_staff=True, is_superuser=True)
    client.force_login(u)
    return u


@pytest.fixture
def vacante():
    area = Area.objects.create(nombre='OPERACIONES')
    return Vacante.objects.create(
        titulo='Supervisor de Campo', area=area,
        descripcion='x', estado='BORRADOR',
    )


class TestAprobacion:
    def test_solicitar_pasa_a_por_aprobar(self, client, aprobador, vacante):
        resp = client.post(
            reverse('vacante_solicitar_aprobacion', args=[vacante.pk]),
            {'justificacion': 'Reemplazo por renuncia'})
        assert resp.status_code == 302
        vacante.refresh_from_db()
        assert vacante.estado == 'POR_APROBAR'
        assert vacante.justificacion == 'Reemplazo por renuncia'

    def test_aprobar_deja_estado_aprobada(self, client, aprobador, vacante):
        vacante.estado = 'POR_APROBAR'
        vacante.save(update_fields=['estado'])
        resp = client.post(reverse('vacante_aprobar', args=[vacante.pk]))
        assert resp.status_code == 302
        vacante.refresh_from_db()
        assert vacante.estado == 'APROBADA'
        assert vacante.aprobada_por == aprobador
        assert vacante.fecha_aprobacion is not None

    def test_rechazar_regresa_a_borrador(self, client, aprobador, vacante):
        vacante.estado = 'POR_APROBAR'
        vacante.save(update_fields=['estado'])
        resp = client.post(
            reverse('vacante_rechazar', args=[vacante.pk]),
            {'motivo': 'Sin presupuesto'})
        assert resp.status_code == 302
        vacante.refresh_from_db()
        assert vacante.estado == 'BORRADOR'
        assert vacante.aprobada_por is None
        assert '[Rechazo] Sin presupuesto' in vacante.justificacion


class TestPublicarBloqueado:
    def test_publicar_bloqueado_mientras_por_aprobar(self, client, aprobador, vacante):
        vacante.estado = 'POR_APROBAR'
        vacante.save(update_fields=['estado'])
        client.post(reverse('vacante_publicar', args=[vacante.pk]))
        vacante.refresh_from_db()
        assert vacante.estado == 'POR_APROBAR'  # no cambió

    def test_publicar_permitido_desde_aprobada(self, client, aprobador, vacante):
        vacante.estado = 'APROBADA'
        vacante.save(update_fields=['estado'])
        client.post(reverse('vacante_publicar', args=[vacante.pk]))
        vacante.refresh_from_db()
        assert vacante.estado == 'PUBLICADA'
        assert vacante.fecha_publicacion is not None

    def test_publicar_permitido_desde_borrador_sin_aprobacion(self, client, aprobador, vacante):
        # Flujo aditivo: vacante que nunca entró a aprobación se publica igual
        client.post(reverse('vacante_publicar', args=[vacante.pk]))
        vacante.refresh_from_db()
        assert vacante.estado == 'PUBLICADA'
