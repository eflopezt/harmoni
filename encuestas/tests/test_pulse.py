"""
Tests del Pulse Semanal:
- Modelo + unique_together
- pulse_analytics: calcular_animo_semanal / heatmap / propuestas
- Vistas: dashboard 200, responder 200
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.db.utils import IntegrityError
from django.urls import reverse
from django.utils import timezone

from empresas.models import Empresa
from encuestas import pulse_analytics
from encuestas.models import PulseSemanal
from personal.models import Area, Personal, SubArea


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_pulse_t', password='x', email='ap@x.com',
    )


@pytest.fixture
def client_admin(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def empresa_demo(db):
    return Empresa.objects.create(
        ruc='20100000123',
        razon_social='Restaurante Demo S.A.C.',
        nombre_comercial='Resto Demo',
        subdominio='resto-demo-test',
        activa=True,
    )


@pytest.fixture
def workers(db, empresa_demo):
    area = Area.objects.create(nombre='Salón Test')
    sub = SubArea.objects.create(nombre='Servicio Test', area=area)
    out = []
    for i in range(10):
        out.append(Personal.objects.create(
            nro_doc=f'PT{i:08d}',
            apellidos_nombres=f'TRABAJADOR PULSE {i}',
            cargo='Mesero',
            tipo_trab='Empleado',
            estado='Activo',
            subarea=sub,
            empresa=empresa_demo,
            fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal('1500.00'),
        ))
    return out


@pytest.fixture
def worker_user(db, workers):
    """Usuario vinculado al primer trabajador."""
    u = User.objects.create_user(username='wt_pulse', password='x')
    p = workers[0]
    p.usuario = u
    p.save(update_fields=['usuario'])
    return u, p


def _semana_actual():
    iso = timezone.now().date().isocalendar()
    return iso.year, iso.week


# ─── Modelo ───────────────────────────────────────────────────────────────────

class TestPulseSemanalModel:
    def test_crear_pulse_ok(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        p = PulseSemanal.objects.create(
            semana=semana, anio=anio,
            empresa=empresa_demo, personal=workers[0],
            animo=4, que_falta='Mejor comunicación', propuestas='Reuniones semanales',
            nps=9,
        )
        assert p.pk is not None
        assert p.animo == 4
        assert p.categoria_nps == 'promotor'

    def test_unique_together_personal_semana_anio(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        PulseSemanal.objects.create(
            semana=semana, anio=anio, empresa=empresa_demo,
            personal=workers[0], animo=3,
        )
        with pytest.raises(IntegrityError):
            PulseSemanal.objects.create(
                semana=semana, anio=anio, empresa=empresa_demo,
                personal=workers[0], animo=5,
            )

    def test_categoria_nps(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        p = PulseSemanal(personal=workers[0], anio=anio, semana=semana, animo=3, nps=10)
        assert p.categoria_nps == 'promotor'
        p.nps = 7
        assert p.categoria_nps == 'neutro'
        p.nps = 4
        assert p.categoria_nps == 'detractor'
        p.nps = None
        assert p.categoria_nps is None


# ─── Analytics ────────────────────────────────────────────────────────────────

class TestPulseAnalytics:
    def test_calcular_animo_semanal_vacio(self, db):
        anio, semana = _semana_actual()
        r = pulse_analytics.calcular_animo_semanal(semana=semana, anio=anio)
        assert r['respuestas'] == 0
        assert r['animo_promedio'] is None

    def test_calcular_animo_semanal_con_datos(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        for i, w in enumerate(workers[:5]):
            PulseSemanal.objects.create(
                semana=semana, anio=anio, empresa=empresa_demo,
                personal=w, animo=(i % 5) + 1,
                nps=10 if i % 2 == 0 else 5,
            )
        r = pulse_analytics.calcular_animo_semanal(
            empresa_id=empresa_demo.pk, semana=semana, anio=anio,
        )
        assert r['respuestas'] == 5
        assert r['animo_promedio'] is not None
        assert r['universo'] >= 10
        # Breakdown debe sumar 5
        assert sum(r['breakdown'].values()) == 5
        # eNPS calculado
        assert r['enps_score'] is not None

    def test_heatmap_por_local(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        # Crear datos en 2 semanas (esta y la anterior)
        sem_prev = semana - 1 if semana > 1 else semana
        for i, w in enumerate(workers[:5]):
            PulseSemanal.objects.create(
                semana=semana, anio=anio, empresa=empresa_demo,
                personal=w, animo=4,
            )
        for i, w in enumerate(workers[5:8]):
            PulseSemanal.objects.create(
                semana=sem_prev, anio=anio, empresa=empresa_demo,
                personal=w, animo=3,
            )

        result = pulse_analytics.heatmap_por_local(
            anio=anio, semana_inicio=sem_prev, semana_fin=semana,
        )
        assert 'semanas' in result
        assert 'filas' in result
        assert len(result['filas']) >= 1
        fila = result['filas'][0]
        assert 'celdas' in fila
        # Esta empresa debe tener celda en la semana actual
        assert any(v is not None for v in fila['celdas'].values())

    def test_top_propuestas(self, workers, empresa_demo):
        anio, semana = _semana_actual()
        for i, w in enumerate(workers[:6]):
            PulseSemanal.objects.create(
                semana=semana, anio=anio, empresa=empresa_demo,
                personal=w, animo=3,
                que_falta='turnos turnos comunicacion',
                propuestas='comunicacion sueldo',
            )
        top = pulse_analytics.top_propuestas(empresa_id=empresa_demo.pk, top_n=5)
        palabras = [t['palabra'] for t in top]
        assert 'turnos' in palabras
        assert 'comunicacion' in palabras

    def test_tendencia_12_semanas_shape(self, workers, empresa_demo):
        out = pulse_analytics.tendencia_12_semanas(n_semanas=4)
        assert len(out) == 4
        for tup in out:
            assert len(tup) == 5  # (semana, anio, animo, n, nps)


# ─── Vistas ───────────────────────────────────────────────────────────────────

class TestPulseViews:
    def test_dashboard_admin_200(self, client_admin, workers, empresa_demo):
        anio, semana = _semana_actual()
        PulseSemanal.objects.create(
            semana=semana, anio=anio, empresa=empresa_demo,
            personal=workers[0], animo=4,
        )
        resp = client_admin.get(reverse('pulse_dashboard'))
        assert resp.status_code == 200
        body = resp.content.decode()
        assert 'Pulse Semanal' in body

    def test_dashboard_filtro_empresa(self, client_admin, workers, empresa_demo):
        url = reverse('pulse_dashboard') + f'?empresa={empresa_demo.pk}'
        resp = client_admin.get(url)
        assert resp.status_code == 200

    def test_historico_200(self, client_admin, workers, empresa_demo):
        anio, semana = _semana_actual()
        PulseSemanal.objects.create(
            semana=semana, anio=anio, empresa=empresa_demo,
            personal=workers[0], animo=3,
        )
        resp = client_admin.get(reverse('pulse_historico'))
        assert resp.status_code == 200

    def test_responder_get_200(self, client, worker_user):
        u, _p = worker_user
        client.force_login(u)
        resp = client.get(reverse('portal_pulse_responder'))
        assert resp.status_code == 200
        assert 'Pulse Semanal' in resp.content.decode()

    def test_responder_post_crea_pulse(self, client, worker_user):
        u, p = worker_user
        client.force_login(u)
        resp = client.post(reverse('portal_pulse_responder'), {
            'animo': 4,
            'que_falta': 'Test falta',
            'propuestas': 'Test propuesta',
            'nps': 9,
        })
        # Redirige al portal_home tras crear
        assert resp.status_code in (302, 200)
        anio, semana = _semana_actual()
        assert PulseSemanal.objects.filter(
            personal=p, anio=anio, semana=semana,
        ).exists()

    def test_responder_no_duplica_si_ya_respondio(self, client, worker_user, empresa_demo):
        u, p = worker_user
        anio, semana = _semana_actual()
        PulseSemanal.objects.create(
            semana=semana, anio=anio, empresa=empresa_demo,
            personal=p, animo=3,
        )
        client.force_login(u)
        resp = client.get(reverse('portal_pulse_responder'))
        # Debe redirigir porque ya respondió
        assert resp.status_code == 302
        assert PulseSemanal.objects.filter(
            personal=p, anio=anio, semana=semana,
        ).count() == 1


# ─── Permisos ─────────────────────────────────────────────────────────────────

class TestPulsePermisos:
    def test_dashboard_anonimo_redirige(self, client):
        resp = client.get(reverse('pulse_dashboard'))
        assert resp.status_code == 302

    def test_dashboard_no_admin_no_pasa(self, db, client):
        u = User.objects.create_user(username='no_adm', password='x', is_superuser=False)
        client.force_login(u)
        resp = client.get(reverse('pulse_dashboard'))
        assert resp.status_code in (302, 403)

    def test_responder_anonimo_redirige(self, client):
        resp = client.get(reverse('portal_pulse_responder'))
        assert resp.status_code == 302
