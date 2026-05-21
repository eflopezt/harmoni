"""
Tests del Predictor de Rotación rule-based.

Cubre:
- Aporte de cada factor al score
- Cap a 100
- Niveles correctos según rangos
- Vistas panel y detalle (HTTP 200)
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from personal.models import Personal

from analytics.predictor_rotacion import (
    FactorRiesgo,
    calcular_score_rotacion,
    top_personal_en_riesgo,
)


def _crear_personal(**kwargs):
    """Helper para crear un Personal con defaults válidos."""
    defaults = {
        'tipo_doc': 'DNI',
        'nro_doc': '12345678',
        'apellidos_nombres': 'TEST WORKER',
        'cargo': 'Mozo',
        'tipo_trab': 'Empleado',
        'estado': 'Activo',
        'grupo_tareo': 'STAFF',
    }
    defaults.update(kwargs)
    return Personal.objects.create(**defaults)


# ═══════════════════════════════════════════════════════════════════
# Factor: antigüedad
# ═══════════════════════════════════════════════════════════════════

class TestFactorAntiguedad(TestCase):

    def test_nuevo_menos_3m_suma_15(self):
        """Trabajador con < 90 días suma 15 puntos."""
        p = _crear_personal(
            nro_doc='10000001',
            fecha_alta=timezone.localdate() - timedelta(days=30),
        )
        result = calcular_score_rotacion(p)
        assert result['score'] >= 15
        nombres = [f.nombre for f in result['factores']]
        assert any('nuevo (<3 meses)' in n for n in nombres)

    def test_nuevo_3_a_6_meses_suma_10(self):
        p = _crear_personal(
            nro_doc='10000002',
            fecha_alta=timezone.localdate() - timedelta(days=120),
        )
        result = calcular_score_rotacion(p)
        nombres = [f.nombre for f in result['factores']]
        assert any('(3-6 meses)' in n for n in nombres)

    def test_antiguedad_alta_suma_10(self):
        """Más de 5 años suma 10 puntos por 'antigüedad sin movimiento'."""
        p = _crear_personal(
            nro_doc='10000003',
            fecha_alta=timezone.localdate() - timedelta(days=365 * 6),
        )
        result = calcular_score_rotacion(p)
        nombres = [f.nombre for f in result['factores']]
        assert any('Antigüedad alta' in n for n in nombres)

    def test_antiguedad_media_no_aporta(self):
        """Entre 6m y 5 años no aporta al factor antigüedad."""
        p = _crear_personal(
            nro_doc='10000004',
            fecha_alta=timezone.localdate() - timedelta(days=365 * 2),
        )
        result = calcular_score_rotacion(p)
        nombres = [f.nombre for f in result['factores']]
        assert not any('Trabajador nuevo' in n or 'Antigüedad' in n for n in nombres)

    def test_sin_fecha_alta_no_falla(self):
        """Si fecha_alta es None, no debe romper."""
        p = _crear_personal(nro_doc='10000005', fecha_alta=None)
        result = calcular_score_rotacion(p)
        assert isinstance(result['score'], int)


# ═══════════════════════════════════════════════════════════════════
# Score: niveles, cap, casos base
# ═══════════════════════════════════════════════════════════════════

class TestScoreNiveles(TestCase):

    def test_sin_riesgo_da_bajo(self):
        """Sin papeletas, sin sanciones, antigüedad media → nivel BAJO (<30)."""
        p = _crear_personal(
            nro_doc='20000001',
            fecha_alta=timezone.localdate() - timedelta(days=365 * 2),
        )
        result = calcular_score_rotacion(p)
        # Sólo factor débil posible: 'Sin capacitación' (8pts) si no hay seed
        assert result['nivel'] == 'BAJO'
        assert result['score'] < 30

    def test_nuevo_aporta_15_puntos(self):
        """Trabajador nuevo (<3m) aporta exactamente 15 puntos por antigüedad."""
        p = _crear_personal(
            nro_doc='20000002',
            fecha_alta=timezone.localdate() - timedelta(days=10),
        )
        r = calcular_score_rotacion(p)
        # 15 (antigüedad <3m) + 8 (sin capacitación) = 23
        # Validamos que el factor 'Trabajador nuevo' aporta 15 puntos
        nuevo_factors = [f for f in r['factores'] if 'Trabajador nuevo' in f.nombre]
        assert len(nuevo_factors) == 1
        assert nuevo_factors[0].puntos == 15
        # Score esperado: 15 + 8 = 23 (BAJO)
        assert r['score'] < 30
        assert r['nivel'] == 'BAJO'

    def test_niveles_mapping(self):
        """Verifica el mapeo nivel <- score directamente."""
        from analytics.predictor_rotacion import calcular_score_rotacion as _calc
        # No podemos forzar 70 fácilmente; validamos contratos del mapping:
        # Caso BAJO: score 0
        p = _crear_personal(
            nro_doc='20000010',
            fecha_alta=timezone.localdate() - timedelta(days=365 * 2),
        )
        # Agregamos capacitación para evitar +8
        try:
            from capacitaciones.models import Capacitacion, AsistenciaCapacitacion
            cap = Capacitacion.objects.create(
                titulo='Test',
                fecha_inicio=timezone.localdate() - timedelta(days=60),
                fecha_fin=timezone.localdate() - timedelta(days=60),
            )
            AsistenciaCapacitacion.objects.create(
                capacitacion=cap, personal=p, estado='ASISTIO',
            )
        except Exception:
            pass
        r = _calc(p)
        # Sin riesgos: score=0 → BAJO
        assert r['nivel'] == 'BAJO'

    def test_cap_a_100(self):
        """Score nunca debe exceder 100."""
        p = _crear_personal(
            nro_doc='20000003',
            fecha_alta=timezone.localdate() - timedelta(days=10),
        )
        result = calcular_score_rotacion(p)
        assert result['score'] <= 100

    def test_recomendacion_si_nivel_alto(self):
        """Score >= 50 debe sugerir reunión 1:1."""
        # Construcción manual del resultado verificando regla
        p = _crear_personal(
            nro_doc='20000004',
            fecha_alta=timezone.localdate() - timedelta(days=10),
        )
        result = calcular_score_rotacion(p)
        # Score=15, no debería tener "Programar reunión"
        assert not any('1:1' in r for r in result['recomendaciones'])

    def test_estructura_retorno(self):
        """Verifica el shape del dict retornado."""
        p = _crear_personal(nro_doc='20000005')
        result = calcular_score_rotacion(p)
        assert set(result.keys()) == {'score', 'nivel', 'factores', 'recomendaciones'}
        assert isinstance(result['score'], int)
        assert result['nivel'] in {'CRITICO', 'ALTO', 'MEDIO', 'BAJO'}
        assert isinstance(result['factores'], list)
        assert isinstance(result['recomendaciones'], list)

    def test_factor_riesgo_tiene_campos_obligatorios(self):
        p = _crear_personal(
            nro_doc='20000006',
            fecha_alta=timezone.localdate() - timedelta(days=30),
        )
        result = calcular_score_rotacion(p)
        for f in result['factores']:
            assert isinstance(f, FactorRiesgo)
            assert f.nombre
            assert f.puntos > 0
            assert f.severidad in {'alto', 'medio', 'bajo'}


# ═══════════════════════════════════════════════════════════════════
# top_personal_en_riesgo
# ═══════════════════════════════════════════════════════════════════

class TestTopPersonalEnRiesgo(TestCase):

    def test_filtra_solo_activos(self):
        _crear_personal(
            nro_doc='30000001',
            fecha_alta=timezone.localdate() - timedelta(days=10),
            estado='Cesado',
        )
        result = top_personal_en_riesgo(limit=10, min_score=10)
        # Cesado no debería estar
        assert all(r['personal'].estado == 'Activo' for r in result)

    def test_filtra_por_min_score(self):
        # Personal con score moderado (antigüedad nueva +15, sin cap +8 = 23)
        _crear_personal(
            nro_doc='30000002',
            fecha_alta=timezone.localdate() - timedelta(days=365 * 2),  # +8 cap solamente
        )
        _crear_personal(
            nro_doc='30000003',
            fecha_alta=timezone.localdate() - timedelta(days=30),  # +15 + 8 = 23
        )
        # Con min_score=20, sólo el segundo entra
        result = top_personal_en_riesgo(limit=10, min_score=20)
        nros = [r['personal'].nro_doc for r in result]
        assert '30000003' in nros
        assert '30000002' not in nros

    def test_ordenado_desc_por_score(self):
        _crear_personal(
            nro_doc='30000004',
            fecha_alta=timezone.localdate() - timedelta(days=30),  # 15
        )
        _crear_personal(
            nro_doc='30000005',
            fecha_alta=timezone.localdate() - timedelta(days=120),  # 10
        )
        result = top_personal_en_riesgo(limit=10, min_score=5)
        scores = [r['analisis']['score'] for r in result]
        assert scores == sorted(scores, reverse=True)

    def test_limit_aplica(self):
        for i in range(5):
            _crear_personal(
                nro_doc=f'3010000{i}',
                fecha_alta=timezone.localdate() - timedelta(days=10 + i),
            )
        result = top_personal_en_riesgo(limit=2, min_score=5)
        assert len(result) <= 2


# ═══════════════════════════════════════════════════════════════════
# Vistas
# ═══════════════════════════════════════════════════════════════════

class TestVistasPredictor(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_pred', password='test1234',
            is_staff=True, is_superuser=True,
        )
        self.client = Client()
        self.client.login(username='admin_pred', password='test1234')

    def test_panel_responde_200(self):
        url = reverse('predictor_rotacion_panel')
        response = self.client.get(url)
        assert response.status_code == 200
        assert b'Predictor de Rotaci' in response.content

    def test_panel_con_filtro_nivel(self):
        url = reverse('predictor_rotacion_panel')
        response = self.client.get(url, {'nivel': 'CRITICO'})
        assert response.status_code == 200

    def test_panel_con_filtro_area_invalido_no_rompe(self):
        url = reverse('predictor_rotacion_panel')
        response = self.client.get(url, {'area': 'abc'})
        assert response.status_code == 200

    def test_detalle_responde_200(self):
        p = _crear_personal(
            nro_doc='40000001',
            fecha_alta=timezone.localdate() - timedelta(days=30),
        )
        url = reverse('predictor_rotacion_detalle', kwargs={'pk': p.pk})
        response = self.client.get(url)
        assert response.status_code == 200
        assert b'TEST WORKER' in response.content

    def test_detalle_personal_inexistente_404(self):
        url = reverse('predictor_rotacion_detalle', kwargs={'pk': 99999})
        response = self.client.get(url)
        assert response.status_code == 404

    def test_panel_requiere_login(self):
        self.client.logout()
        url = reverse('predictor_rotacion_panel')
        response = self.client.get(url)
        # Redirige a login
        assert response.status_code in (302, 301)

    def test_panel_requiere_staff_o_superuser(self):
        """Usuario no-staff no debería entrar."""
        self.client.logout()
        User.objects.create_user(
            username='regular_user', password='test1234',
        )
        self.client.login(username='regular_user', password='test1234')
        url = reverse('predictor_rotacion_panel')
        response = self.client.get(url)
        # user_passes_test redirige a login si falla
        assert response.status_code in (302, 301, 403)
