"""
Tests del módulo Disciplinaria:
- workflow.sugerir_proxima_medida (escalado por historial)
- PDF carta amonestación / suspensión
- Vista timeline personal
- Signal: notificación in-app al trabajador al notificar medida
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from disciplinaria.models import MedidaDisciplinaria, TipoFalta
from disciplinaria.pdf_carta import (
    build_carta_amonestacion_pdf,
    build_carta_suspension_pdf,
)
from disciplinaria.workflow import (
    ESCALAS,
    resolver_clave_escala,
    sugerir_proxima_medida,
)
from personal.models import Personal


# ──────────────────────────────────────────────────────────────
# FIXTURES
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_disc', password='x', email='a@d.com',
    )


@pytest.fixture
def client_admin(admin_user):
    c = Client()
    c.force_login(admin_user)
    return c


def _make_personal(**kw):
    defaults = {
        'tipo_doc': 'DNI',
        'nro_doc': '12345678',
        'apellidos_nombres': 'WORKER TEST',
        'cargo': 'Mozo',
        'tipo_trab': 'Empleado',
        'estado': 'Activo',
        'grupo_tareo': 'STAFF',
    }
    defaults.update(kw)
    return Personal.objects.create(**defaults)


@pytest.fixture
def trabajador(db):
    return _make_personal(nro_doc='40000001', apellidos_nombres='LOPEZ JUAN')


@pytest.fixture
def trabajador2(db):
    return _make_personal(nro_doc='40000002', apellidos_nombres='PEREZ ANA')


@pytest.fixture
def tipo_falta_tardanza(db):
    return TipoFalta.objects.create(
        nombre='Tardanza reiterada', codigo='tardanza',
        gravedad='LEVE', base_legal='Reglamento Interno',
    )


@pytest.fixture
def tipo_falta_higiene(db):
    return TipoFalta.objects.create(
        nombre='Incumplimiento de normas de vestimenta',
        codigo='vestimenta', gravedad='LEVE',
    )


@pytest.fixture
def tipo_falta_grave(db):
    return TipoFalta.objects.create(
        nombre='Apropiación de bienes', codigo='apropiacion-bienes',
        gravedad='MUY_GRAVE', base_legal='DS 003-97-TR Art. 25 inc. c)',
    )


# ──────────────────────────────────────────────────────────────
# WORKFLOW — sugerir_proxima_medida
# ──────────────────────────────────────────────────────────────

class TestSugerirProximaMedida:

    def test_sin_historial_devuelve_primera_escala(
        self, trabajador, tipo_falta_tardanza,
    ):
        """Sin medidas previas → primera medida de la escala TARDANZA."""
        sug = sugerir_proxima_medida(trabajador, tipo_falta_tardanza)
        assert sug['escala'] == 'TARDANZA'
        # ESCALAS['TARDANZA'][0] = 'VERBAL'
        assert sug['nivel'] == ESCALAS['TARDANZA'][0]
        assert sug['nivel'] == 'VERBAL'
        assert sug['tipo_medida'] == 'VERBAL'
        assert sug['index'] == 0
        assert sug['total_previas'] == 0
        assert not sug['escala_completa']

    def test_con_1_verbal_devuelve_escrita(
        self, trabajador, tipo_falta_tardanza,
    ):
        """Una verbal previa → siguiente es ESCRITA."""
        MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='VERBAL',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=30),
            descripcion_hechos='Tardanza 1',
            estado='RESUELTA',
        )
        sug = sugerir_proxima_medida(trabajador, tipo_falta_tardanza)
        assert sug['nivel'] == 'ESCRITA'
        assert sug['tipo_medida'] == 'ESCRITA'
        assert sug['total_previas'] == 1
        assert sug['index'] == 1

    def test_escala_agotada_devuelve_ultimo_nivel(
        self, trabajador, tipo_falta_tardanza,
    ):
        """Más medidas que la escala → devuelve el último nivel."""
        # ESCALAS['TARDANZA'] tiene 4 niveles. Creamos 6 medidas previas.
        for i in range(6):
            MedidaDisciplinaria.objects.create(
                personal=trabajador,
                tipo_medida='VERBAL',
                tipo_falta=tipo_falta_tardanza,
                fecha_hechos=date.today() - timedelta(days=180 - i*30),
                descripcion_hechos=f'Tardanza {i}',
                estado='RESUELTA',
            )
        sug = sugerir_proxima_medida(trabajador, tipo_falta_tardanza)
        assert sug['nivel'] == ESCALAS['TARDANZA'][-1]   # SUSPENSION_3D
        assert sug['escala_completa'] is True
        assert sug['index'] == len(ESCALAS['TARDANZA']) - 1

    def test_medidas_anuladas_no_cuentan(
        self, trabajador, tipo_falta_tardanza,
    ):
        """Las medidas ANULADAS no se cuentan en el historial."""
        MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='VERBAL',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=10),
            descripcion_hechos='Anulada',
            estado='ANULADA',
        )
        sug = sugerir_proxima_medida(trabajador, tipo_falta_tardanza)
        assert sug['total_previas'] == 0
        assert sug['nivel'] == 'VERBAL'

    def test_resolver_clave_string_directo(self):
        assert resolver_clave_escala('TARDANZA') == 'TARDANZA'
        assert resolver_clave_escala('HIGIENE') == 'HIGIENE'

    def test_resolver_clave_codigo_tipo_falta(self, tipo_falta_higiene):
        """vestimenta → HIGIENE."""
        assert resolver_clave_escala(tipo_falta_higiene) == 'HIGIENE'

    def test_resolver_clave_gravedad_muy_grave_default(self, tipo_falta_grave):
        """Falta MUY_GRAVE no mapeada → FALTA_GRAVE (con suspensión directa)."""
        clave = resolver_clave_escala(tipo_falta_grave)
        assert clave == 'FALTA_GRAVE'

    def test_higiene_gastronomia(self, trabajador, tipo_falta_higiene):
        """La escala HIGIENE (gastro) empieza por VERBAL."""
        sug = sugerir_proxima_medida(trabajador, tipo_falta_higiene)
        assert sug['escala'] == 'HIGIENE'
        assert sug['nivel'] == 'VERBAL'


# ──────────────────────────────────────────────────────────────
# PDF Carta
# ──────────────────────────────────────────────────────────────

class TestPDFCarta:

    def test_carta_amonestacion_renderiza_bytes(
        self, trabajador, tipo_falta_tardanza,
    ):
        medida = MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='ESCRITA',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=3),
            descripcion_hechos='Tardanza grave de 45 minutos.',
            estado='NOTIFICADA',
        )
        pdf = build_carta_amonestacion_pdf(medida)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b'%PDF')
        assert len(pdf) > 1500  # sanity check

    def test_carta_suspension_renderiza_bytes(
        self, trabajador, tipo_falta_tardanza,
    ):
        medida = MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='SUSPENSION',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=5),
            descripcion_hechos='Faltas reiteradas.',
            estado='NOTIFICADA',
            dias_suspension=3,
        )
        pdf = build_carta_suspension_pdf(medida)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b'%PDF')

    def test_carta_pdf_view_responde_pdf(
        self, client_admin, trabajador, tipo_falta_tardanza,
    ):
        medida = MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='ESCRITA',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=2),
            descripcion_hechos='Tardanza',
            estado='NOTIFICADA',
        )
        url = reverse('medida_carta_pdf', args=[medida.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content.startswith(b'%PDF')


# ──────────────────────────────────────────────────────────────
# Vista Timeline Personal
# ──────────────────────────────────────────────────────────────

class TestTimelinePersonal:

    def test_timeline_personal_200(
        self, client_admin, trabajador, tipo_falta_tardanza,
    ):
        MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='VERBAL',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=30),
            descripcion_hechos='Primera tardanza',
            estado='RESUELTA',
        )
        url = reverse('disciplinaria_timeline_personal', args=[trabajador.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 200
        assert b'Timeline' in resp.content or b'timeline' in resp.content.lower()
        assert trabajador.apellidos_nombres.encode() in resp.content

    def test_timeline_personal_sin_medidas_200(
        self, client_admin, trabajador,
    ):
        url = reverse('disciplinaria_timeline_personal', args=[trabajador.pk])
        resp = client_admin.get(url)
        assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────
# Endpoint AJAX — sugerir-medida
# ──────────────────────────────────────────────────────────────

class TestSugerirMedidaAjax:

    def test_endpoint_devuelve_sugerencia(
        self, client_admin, trabajador, tipo_falta_tardanza,
    ):
        url = reverse('disciplinaria_sugerir_medida')
        resp = client_admin.get(
            url,
            {'personal_id': trabajador.pk, 'tipo_falta_id': tipo_falta_tardanza.pk},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data['ok'] is True
        assert data['sugerencia']['nivel'] == 'VERBAL'
        assert data['sugerencia']['escala'] == 'TARDANZA'

    def test_endpoint_sin_personal_400(self, client_admin):
        url = reverse('disciplinaria_sugerir_medida')
        resp = client_admin.get(url)
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# Signal — crea Notificacion al notificar medida
# ──────────────────────────────────────────────────────────────

class TestSignalNotificacion:

    def test_signal_crea_notificacion_al_notificar(
        self, trabajador, tipo_falta_tardanza,
    ):
        try:
            from comunicaciones.models import Notificacion
        except ImportError:
            pytest.skip("Módulo comunicaciones no disponible")

        n_before = Notificacion.objects.filter(destinatario=trabajador).count()

        medida = MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='ESCRITA',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today() - timedelta(days=1),
            descripcion_hechos='Tardanza notificada',
            estado='NOTIFICADA',
        )
        n_after = Notificacion.objects.filter(destinatario=trabajador).count()
        assert n_after == n_before + 1
        notif = Notificacion.objects.filter(destinatario=trabajador).latest('creado_en')
        assert notif.tipo == 'IN_APP'
        assert notif.metadata.get('modulo') == 'disciplinaria'
        assert notif.metadata.get('medida_id') == medida.pk

    def test_signal_no_crea_para_borrador(
        self, trabajador, tipo_falta_tardanza,
    ):
        try:
            from comunicaciones.models import Notificacion
        except ImportError:
            pytest.skip("Módulo comunicaciones no disponible")

        n_before = Notificacion.objects.filter(destinatario=trabajador).count()
        MedidaDisciplinaria.objects.create(
            personal=trabajador,
            tipo_medida='ESCRITA',
            tipo_falta=tipo_falta_tardanza,
            fecha_hechos=date.today(),
            descripcion_hechos='Borrador',
            estado='BORRADOR',
        )
        n_after = Notificacion.objects.filter(destinatario=trabajador).count()
        assert n_after == n_before  # ninguna creada
