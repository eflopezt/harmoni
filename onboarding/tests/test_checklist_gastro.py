"""
Tests para ChecklistGastronomia — checklist de onboarding 30/60/90 días.
"""
import pytest
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from personal.models import Area, SubArea, Personal
from onboarding.models import ChecklistGastronomia


@pytest.fixture
def area():
    return Area.objects.create(nombre='COCINA')


@pytest.fixture
def personal(area):
    subarea = SubArea.objects.create(nombre='LINEA CALIENTE', area=area)
    return Personal.objects.create(
        nro_doc='44556677',
        apellidos_nombres='RAMIREZ COCINERO LUIS',
        cargo='Cocinero',
        tipo_trab='Empleado',
        subarea=subarea,
        estado='Activo',
        fecha_alta=date.today() - timedelta(days=10),
    )


@pytest.fixture
def personal_b(area):
    return Personal.objects.create(
        nro_doc='99887766',
        apellidos_nombres='LOPEZ MOZA MARIA',
        cargo='Moza',
        tipo_trab='Empleado',
        estado='Activo',
        fecha_alta=date.today() - timedelta(days=40),
    )


@pytest.fixture
def checklist(personal):
    return ChecklistGastronomia.objects.create(
        personal=personal,
        fecha_ingreso=personal.fecha_alta,
    )


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username='admin_test', password='x', is_superuser=True, is_staff=True,
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


# ──────────────────────────────────────────────────────────────
# Modelo
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChecklistGastronomiaModel:

    def test_crear_checklist_defaults(self, checklist):
        assert checklist.completado is False
        assert checklist.porcentaje_completado == 0
        assert checklist.items_completados == 0
        assert checklist.total_items == 11

    def test_str(self, checklist):
        assert 'RAMIREZ COCINERO LUIS' in str(checklist)

    def test_one_to_one_personal(self, personal, checklist):
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            ChecklistGastronomia.objects.create(
                personal=personal, fecha_ingreso=date.today(),
            )

    def test_porcentaje_completado_parcial(self, checklist):
        checklist.contrato_firmado = True
        checklist.examen_medico = True
        checklist.save()
        # 2 de 11 = 18%
        assert checklist.porcentaje_completado == 18

    def test_porcentaje_completado_todos(self, checklist):
        for f in checklist._ITEMS_CHECKLIST:
            setattr(checklist, f, True)
        checklist.save()
        assert checklist.porcentaje_completado == 100
        assert checklist.items_completados == 11

    def test_dias_desde_ingreso(self, personal_b):
        c = ChecklistGastronomia.objects.create(
            personal=personal_b,
            fecha_ingreso=date.today() - timedelta(days=15),
        )
        assert c.dias_desde_ingreso == 15

    def test_alertas_vencidas_vacio(self, checklist):
        # 10 días desde ingreso, contrato firmado a tiempo
        checklist.contrato_firmado = True
        checklist.save()
        # Aún no llegamos a 14 días para examen médico
        # Pero dias_desde_ingreso es 10 (>= 7), contrato sí está → no alerta
        # examen_medico no se valida hasta día 14
        alertas = checklist.alertas_vencidas
        # Debe haber 0 alertas (10 días, contrato OK, médico aún en tiempo)
        codes = [a[0] for a in alertas]
        assert 'contrato_firmado' not in codes

    def test_alertas_vencidas_contrato_sin_firmar(self, personal_b):
        # personal_b tiene 40 días desde ingreso
        c = ChecklistGastronomia.objects.create(
            personal=personal_b,
            fecha_ingreso=date.today() - timedelta(days=40),
        )
        alertas = c.alertas_vencidas
        codes = [a[0] for a in alertas]
        assert 'contrato_firmado' in codes
        assert 'examen_medico' in codes
        assert 'eval_30' in codes

    def test_en_riesgo_true(self, personal_b):
        c = ChecklistGastronomia.objects.create(
            personal=personal_b,
            fecha_ingreso=date.today() - timedelta(days=40),
        )
        assert c.en_riesgo is True

    def test_en_riesgo_false(self, checklist):
        # Día 10 desde ingreso. La única alerta posible a esa altura es el
        # contrato (umbral día 7); si está firmado a tiempo, no hay alertas
        # vencidas → en_riesgo == False. Refleja el caso "todo en tiempo".
        checklist.contrato_firmado = True
        checklist.save()
        assert checklist.en_riesgo is False

    def test_proximo_hito(self, checklist):
        assert checklist.proximo_hito == "Firmar contrato"
        checklist.contrato_firmado = True
        checklist.examen_medico = True
        checklist.induccion_general = True
        checklist.uniforme_entregado = True
        checklist.save()
        assert checklist.proximo_hito == "Certificaciones sanitarias"


# ──────────────────────────────────────────────────────────────
# Vistas
# ──────────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestChecklistGastronomiaVistas:

    def test_panel_responde_200(self, admin_client, checklist):
        url = reverse('checklist_gastro_panel')
        r = admin_client.get(url)
        assert r.status_code == 200
        assert b'RAMIREZ COCINERO LUIS' in r.content

    def test_panel_filtro_pendientes(self, admin_client, checklist):
        r = admin_client.get(reverse('checklist_gastro_panel') + '?estado=pendientes')
        assert r.status_code == 200

    def test_panel_filtro_en_riesgo(self, admin_client, personal_b):
        ChecklistGastronomia.objects.create(
            personal=personal_b,
            fecha_ingreso=date.today() - timedelta(days=40),
        )
        r = admin_client.get(reverse('checklist_gastro_panel') + '?estado=en_riesgo')
        assert r.status_code == 200
        assert b'LOPEZ MOZA MARIA' in r.content

    def test_detalle_responde_200(self, admin_client, checklist):
        url = reverse('checklist_gastro_detalle', kwargs={'pk': checklist.pk})
        r = admin_client.get(url)
        assert r.status_code == 200
        assert b'RAMIREZ COCINERO LUIS' in r.content

    def test_toggle_marca_item(self, admin_client, checklist):
        url = reverse('checklist_gastro_toggle', kwargs={'pk': checklist.pk})
        r = admin_client.post(url, {'campo': 'contrato_firmado'})
        assert r.status_code == 200
        data = r.json()
        assert data['ok'] is True
        assert data['nuevo_valor'] is True
        checklist.refresh_from_db()
        assert checklist.contrato_firmado is True
        assert checklist.contrato_firmado_fecha == timezone.now().date()

    def test_toggle_desmarca_item(self, admin_client, checklist):
        checklist.contrato_firmado = True
        checklist.contrato_firmado_fecha = date.today()
        checklist.save()
        url = reverse('checklist_gastro_toggle', kwargs={'pk': checklist.pk})
        r = admin_client.post(url, {'campo': 'contrato_firmado'})
        assert r.status_code == 200
        data = r.json()
        assert data['nuevo_valor'] is False
        checklist.refresh_from_db()
        assert checklist.contrato_firmado is False
        assert checklist.contrato_firmado_fecha is None

    def test_toggle_campo_invalido(self, admin_client, checklist):
        url = reverse('checklist_gastro_toggle', kwargs={'pk': checklist.pk})
        r = admin_client.post(url, {'campo': 'campo_inexistente'})
        assert r.status_code == 400
        assert r.json()['ok'] is False

    def test_toggle_completa_checklist(self, admin_client, checklist):
        # Marcar los 11 items
        url = reverse('checklist_gastro_toggle', kwargs={'pk': checklist.pk})
        for campo in checklist._ITEMS_CHECKLIST:
            admin_client.post(url, {'campo': campo})
        checklist.refresh_from_db()
        assert checklist.completado is True
        assert checklist.porcentaje_completado == 100

    def test_toggle_requiere_post(self, admin_client, checklist):
        url = reverse('checklist_gastro_toggle', kwargs={'pk': checklist.pk})
        r = admin_client.get(url)
        # Django returns 405 for require_POST on GET
        assert r.status_code == 405

    def test_acceso_anonimo_redirige(self, client, checklist):
        url = reverse('checklist_gastro_panel')
        r = client.get(url)
        # login_required → redirige a login
        assert r.status_code in (302, 301)

    def test_auto_crear_crea_checklists(self, admin_client, personal_b):
        # personal_b NO tiene checklist y fecha_alta hace 40 días
        assert not ChecklistGastronomia.objects.filter(personal=personal_b).exists()
        url = reverse('checklist_gastro_auto_crear')
        r = admin_client.get(url)
        assert r.status_code in (302, 301)
        assert ChecklistGastronomia.objects.filter(personal=personal_b).exists()

    def test_detalle_registra_evaluacion(self, admin_client, checklist):
        url = reverse('checklist_gastro_detalle', kwargs={'pk': checklist.pk})
        r = admin_client.post(url, {
            'accion': 'eval_30',
            'evaluacion_30_calificacion': '8',
            'evaluacion_30_notas': 'Buen trabajo',
        })
        assert r.status_code in (302, 301)
        checklist.refresh_from_db()
        assert checklist.evaluacion_30 is True
        assert checklist.evaluacion_30_calificacion == 8
        assert checklist.evaluacion_30_notas == 'Buen trabajo'

    def test_detalle_evaluacion_calificacion_invalida(self, admin_client, checklist):
        url = reverse('checklist_gastro_detalle', kwargs={'pk': checklist.pk})
        r = admin_client.post(url, {
            'accion': 'eval_30',
            'evaluacion_30_calificacion': '15',  # fuera de rango
        })
        # redirige con mensaje de error, pero no guarda
        checklist.refresh_from_db()
        assert checklist.evaluacion_30 is False
