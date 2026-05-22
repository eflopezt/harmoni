"""
Tests del workflow extendido de Vacaciones:
- calcular_saldo_vacaciones
- Wizard view del trabajador
- Calendario anual
- PDF Constancia
- Notificaciones IN_APP en transiciones de estado

Estos tests complementan test_vacaciones.py (que cubre el modelo).
"""
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from personal.models import Personal
from vacaciones.models import SaldoVacacional, SolicitudVacacion
from vacaciones.calculadora_saldo import (
    calcular_saldo_vacaciones, validar_solicitud
)

User = get_user_model()


# ════════════════════════════════════════════════════════════════════
# 1. Calculadora de saldo
# ════════════════════════════════════════════════════════════════════

class TestCalculadoraSaldo(TestCase):
    """Tests de calcular_saldo_vacaciones."""

    @classmethod
    def setUpTestData(cls):
        cls.hoy = date.today()
        # Empleado con 13 meses de servicio
        cls.emp_13m = Personal.objects.create(
            nro_doc='10000001',
            apellidos_nombres='Trece Meses, Test',
            tipo_doc='DNI',
            fecha_alta=cls.hoy - timedelta(days=395),
            estado='Activo',
        )
        # Empleado con 6 meses (no cumple año)
        cls.emp_6m = Personal.objects.create(
            nro_doc='10000002',
            apellidos_nombres='Seis Meses, Test',
            tipo_doc='DNI',
            fecha_alta=cls.hoy - timedelta(days=180),
            estado='Activo',
        )
        # Empleado SIN fecha_alta
        cls.emp_sin_fecha = Personal.objects.create(
            nro_doc='10000003',
            apellidos_nombres='Sin Fecha, Test',
            tipo_doc='DNI',
            fecha_alta=None,
            estado='Activo',
        )

    def test_empleado_13_meses_tiene_30_dias_completos(self):
        """Un trabajador con 13 meses tiene 30 días + truncos del 2° período.

        El "1 año cumplido" garantiza los 30 días completos del DL 713 Art. 10.
        Adicionalmente, ya está acumulando truncos del 2° año en curso
        (~30/12 × meses del período actual).
        """
        saldo = calcular_saldo_vacaciones(self.emp_13m)
        self.assertEqual(saldo['dias_completos'], 30)
        self.assertEqual(saldo['anios_servicio'], 1)
        self.assertTrue(saldo['cumple_anio'])
        self.assertTrue(saldo['tiene_fecha_alta'])
        # Disponibles >= 30 (incluye truncos del 2° período en curso)
        self.assertGreaterEqual(saldo['dias_disponibles'], 30)
        self.assertEqual(saldo['dias_consumidos'], 0)

    def test_empleado_6_meses_no_tiene_dias_completos(self):
        """Un trabajador con 6 meses tiene 0 días completos, sólo truncos."""
        saldo = calcular_saldo_vacaciones(self.emp_6m)
        self.assertEqual(saldo['dias_completos'], 0)
        self.assertFalse(saldo['cumple_anio'])
        # Truncos calculados pero no disponibles (no cumple año)
        self.assertEqual(saldo['dias_disponibles'], 0)
        self.assertIsNotNone(saldo['fecha_cumple_anio'])

    def test_empleado_sin_fecha_alta_saldo_cero(self):
        """Edge case: trabajador sin fecha_alta retorna saldo 0."""
        saldo = calcular_saldo_vacaciones(self.emp_sin_fecha)
        self.assertEqual(saldo['dias_disponibles'], 0)
        self.assertEqual(saldo['dias_completos'], 0)
        self.assertFalse(saldo['tiene_fecha_alta'])

    def test_none_personal_retorna_saldo_cero(self):
        """Edge case: None retorna saldo 0 sin crashear."""
        saldo = calcular_saldo_vacaciones(None)
        self.assertEqual(saldo['dias_disponibles'], 0)
        self.assertFalse(saldo['tiene_fecha_alta'])

    def test_consumidos_descuentan_disponibles(self):
        """Solicitudes APROBADAS deben descontarse de dias_disponibles."""
        saldo_antes = calcular_saldo_vacaciones(self.emp_13m)
        SolicitudVacacion.objects.create(
            personal=self.emp_13m,
            fecha_inicio=self.hoy - timedelta(days=60),
            fecha_fin=self.hoy - timedelta(days=51),  # 10 días
            dias_calendario=0,  # se recalcula
            estado='APROBADA',
        )
        saldo = calcular_saldo_vacaciones(self.emp_13m)
        self.assertEqual(saldo['dias_consumidos'], 10)
        # Después de consumir 10 días, disponibles bajan en 10
        self.assertEqual(
            saldo['dias_disponibles'],
            saldo_antes['dias_disponibles'] - 10
        )

    def test_pendientes_descuentan_disponibles(self):
        """Solicitudes PENDIENTE deben descontarse de dias_disponibles
        para evitar que el trabajador 'sobre-solicite'."""
        saldo_antes = calcular_saldo_vacaciones(self.emp_13m)
        SolicitudVacacion.objects.create(
            personal=self.emp_13m,
            fecha_inicio=self.hoy + timedelta(days=10),
            fecha_fin=self.hoy + timedelta(days=16),  # 7 días
            dias_calendario=0,
            estado='PENDIENTE',
        )
        saldo = calcular_saldo_vacaciones(self.emp_13m)
        self.assertEqual(saldo['dias_pendientes_aprobacion'], 7)
        self.assertEqual(
            saldo['dias_disponibles'],
            saldo_antes['dias_disponibles'] - 7
        )


class TestValidarSolicitud(TestCase):
    """Tests de validar_solicitud."""

    @classmethod
    def setUpTestData(cls):
        cls.hoy = date.today()
        cls.emp = Personal.objects.create(
            nro_doc='20000001',
            apellidos_nombres='Validar Test',
            tipo_doc='DNI',
            fecha_alta=cls.hoy - timedelta(days=400),
            estado='Activo',
        )

    def test_solicitud_valida(self):
        """Solicitud de 10 días con saldo suficiente pasa validación."""
        ini = self.hoy + timedelta(days=30)
        fin = ini + timedelta(days=9)  # 10 días
        v = validar_solicitud(self.emp, ini, fin)
        self.assertTrue(v['ok'])
        self.assertEqual(v['dias_solicitados'], 10)
        self.assertEqual(len(v['errores']), 0)

    def test_no_se_puede_solicitar_mas_que_saldo(self):
        """Solicitud > saldo disponible falla validación."""
        ini = self.hoy + timedelta(days=30)
        fin = ini + timedelta(days=50)  # 51 días > 30
        v = validar_solicitud(self.emp, ini, fin)
        self.assertFalse(v['ok'])
        self.assertTrue(any('Saldo insuficiente' in e for e in v['errores']))

    def test_fecha_fin_anterior_a_inicio_falla(self):
        ini = self.hoy + timedelta(days=30)
        fin = ini - timedelta(days=2)
        v = validar_solicitud(self.emp, ini, fin)
        self.assertFalse(v['ok'])

    def test_periodo_menor_a_7_dias_genera_aviso(self):
        """Fracción menor a 7 días genera aviso (no error)."""
        ini = self.hoy + timedelta(days=30)
        fin = ini + timedelta(days=4)  # 5 días
        v = validar_solicitud(self.emp, ini, fin)
        self.assertTrue(v['ok'])  # OK con aviso
        self.assertTrue(len(v['avisos']) > 0)
        self.assertTrue(any('7 días' in a for a in v['avisos']))


# ════════════════════════════════════════════════════════════════════
# 2. Vistas: wizard, calendario anual, PDF
# ════════════════════════════════════════════════════════════════════

@override_settings(LANGUAGE_CODE='es')
class TestVistasWorkflow(TestCase):
    """Tests de smoke para las vistas nuevas."""

    @classmethod
    def setUpTestData(cls):
        cls.hoy = date.today()
        cls.admin = User.objects.create_superuser(
            username='admin_wf', password='testpass123', email='admin@test.com'
        )
        cls.user_worker = User.objects.create_user(
            username='worker1', password='testpass123', email='worker@test.com'
        )
        cls.empleado = Personal.objects.create(
            nro_doc='30000001',
            apellidos_nombres='Worker, Test',
            tipo_doc='DNI',
            fecha_alta=cls.hoy - timedelta(days=400),
            estado='Activo',
            usuario=cls.user_worker,
        )
        cls.saldo = SaldoVacacional.objects.create(
            personal=cls.empleado,
            periodo_inicio=cls.hoy - timedelta(days=400),
            periodo_fin=cls.hoy - timedelta(days=35),
            dias_derecho=30,
            dias_gozados=0,
            dias_vendidos=0,
            dias_pendientes=30,
            estado='PENDIENTE',
        )
        cls.solicitud_aprobada = SolicitudVacacion.objects.create(
            personal=cls.empleado,
            saldo=cls.saldo,
            fecha_inicio=cls.hoy - timedelta(days=60),
            fecha_fin=cls.hoy - timedelta(days=54),  # 7 días
            dias_calendario=0,
            estado='APROBADA',
            aprobado_por=cls.admin,
            fecha_aprobacion=cls.hoy - timedelta(days=70),
            motivo='Test pre-aprobada',
        )

    def setUp(self):
        self.client = Client()

    def test_wizard_responde_200_para_trabajador(self):
        """El wizard del trabajador responde 200."""
        self.client.login(username='worker1', password='testpass123')
        resp = self.client.get(reverse('vacacion_solicitar_wizard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Solicitar Vacaciones')

    def test_wizard_post_crea_solicitud_pendiente(self):
        """POST al wizard con datos válidos crea solicitud en estado PENDIENTE."""
        self.client.login(username='worker1', password='testpass123')
        ini = self.hoy + timedelta(days=30)
        fin = ini + timedelta(days=7)  # 8 días
        count_before = SolicitudVacacion.objects.filter(personal=self.empleado).count()
        resp = self.client.post(reverse('vacacion_solicitar_wizard'), {
            'fecha_inicio': ini.isoformat(),
            'fecha_fin': fin.isoformat(),
            'motivo': 'Test wizard',
        })
        # Redirect tras éxito
        self.assertIn(resp.status_code, (200, 302))
        count_after = SolicitudVacacion.objects.filter(personal=self.empleado).count()
        self.assertEqual(count_after, count_before + 1)
        ultima = SolicitudVacacion.objects.filter(
            personal=self.empleado
        ).order_by('-creado_en').first()
        self.assertEqual(ultima.estado, 'PENDIENTE')

    def test_wizard_rechaza_solicitud_excede_saldo(self):
        """POST con días > saldo no crea solicitud."""
        self.client.login(username='worker1', password='testpass123')
        ini = self.hoy + timedelta(days=30)
        fin = ini + timedelta(days=60)  # 61 días > 30
        count_before = SolicitudVacacion.objects.filter(personal=self.empleado).count()
        resp = self.client.post(reverse('vacacion_solicitar_wizard'), {
            'fecha_inicio': ini.isoformat(),
            'fecha_fin': fin.isoformat(),
            'motivo': 'Test exceso',
        })
        self.assertEqual(resp.status_code, 200)  # No redirect
        count_after = SolicitudVacacion.objects.filter(personal=self.empleado).count()
        self.assertEqual(count_after, count_before)  # NO se creó

    def test_calendario_anual_responde_200(self):
        """Calendario anual responde 200 para admin."""
        self.client.login(username='admin_wf', password='testpass123')
        resp = self.client.get(reverse('vacaciones_calendario_anual'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Calendario Anual')

    def test_calendario_anual_con_anio_parametro(self):
        """Calendario anual acepta ?anio=2026."""
        self.client.login(username='admin_wf', password='testpass123')
        resp = self.client.get(reverse('vacaciones_calendario_anual') + '?anio=2026')
        self.assertEqual(resp.status_code, 200)

    def test_calendario_anual_requiere_admin(self):
        """Trabajador NO puede acceder al calendario anual."""
        self.client.login(username='worker1', password='testpass123')
        resp = self.client.get(reverse('vacaciones_calendario_anual'))
        # Redirige a login (user_passes_test) - no es admin
        self.assertIn(resp.status_code, (302, 403))

    def test_constancia_pdf_aprobada_responde_200(self):
        """PDF Constancia de solicitud APROBADA responde 200."""
        self.client.login(username='admin_wf', password='testpass123')
        url = reverse('vacacion_constancia_pdf', args=[self.solicitud_aprobada.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        # PDF debe empezar con la firma %PDF-
        self.assertTrue(resp.content.startswith(b'%PDF-'))

    def test_constancia_pdf_no_aprobada_redirige(self):
        """PDF Constancia de solicitud PENDIENTE redirige con error."""
        pendiente = SolicitudVacacion.objects.create(
            personal=self.empleado,
            fecha_inicio=self.hoy + timedelta(days=10),
            fecha_fin=self.hoy + timedelta(days=17),
            dias_calendario=0,
            estado='PENDIENTE',
        )
        self.client.login(username='admin_wf', password='testpass123')
        url = reverse('vacacion_constancia_pdf', args=[pendiente.pk])
        resp = self.client.get(url, follow=False)
        # Redirige (302) porque no está APROBADA
        self.assertEqual(resp.status_code, 302)

    def test_admin_lista_responde_200(self):
        """El endpoint /vacaciones/admin/ responde 200."""
        self.client.login(username='admin_wf', password='testpass123')
        resp = self.client.get(reverse('vacaciones_admin'))
        self.assertEqual(resp.status_code, 200)


# ════════════════════════════════════════════════════════════════════
# 3. Workflow: BORRADOR → PENDIENTE → APROBADA
# ════════════════════════════════════════════════════════════════════

class TestWorkflowEstados(TestCase):
    """Verifica el flujo completo de estados."""

    @classmethod
    def setUpTestData(cls):
        cls.hoy = date.today()
        cls.admin = User.objects.create_superuser(
            username='admin_flow', password='x', email='a@b.c'
        )
        cls.emp = Personal.objects.create(
            nro_doc='40000001',
            apellidos_nombres='Flujo Test',
            tipo_doc='DNI',
            fecha_alta=cls.hoy - timedelta(days=400),
            estado='Activo',
        )
        cls.saldo = SaldoVacacional.objects.create(
            personal=cls.emp,
            periodo_inicio=cls.hoy - timedelta(days=400),
            periodo_fin=cls.hoy - timedelta(days=35),
            dias_derecho=30, dias_gozados=0,
            dias_vendidos=0, dias_pendientes=30,
            estado='PENDIENTE',
        )

    def test_workflow_borrador_pendiente_aprobada(self):
        """BORRADOR → PENDIENTE → APROBADA con persistencia correcta."""
        sol = SolicitudVacacion.objects.create(
            personal=self.emp,
            saldo=self.saldo,
            fecha_inicio=self.hoy + timedelta(days=30),
            fecha_fin=self.hoy + timedelta(days=39),  # 10 días
            dias_calendario=0,
            estado='BORRADOR',
        )
        self.assertEqual(sol.estado, 'BORRADOR')

        # → PENDIENTE
        sol.estado = 'PENDIENTE'
        sol.save(update_fields=['estado'])
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'PENDIENTE')

        # → APROBADA
        sol.aprobar(self.admin)
        sol.refresh_from_db()
        self.assertEqual(sol.estado, 'APROBADA')
        self.assertEqual(sol.aprobado_por, self.admin)
        self.assertIsNotNone(sol.fecha_aprobacion)

        # Saldo descontado
        self.saldo.refresh_from_db()
        self.assertEqual(self.saldo.dias_gozados, 10)
        self.assertEqual(self.saldo.dias_pendientes, 20)

    def test_no_se_puede_aprobar_mas_dias_que_saldo(self):
        """aprobar() lanza ValueError si solicita > saldo."""
        # Saldo con sólo 5 días
        saldo_chico = SaldoVacacional.objects.create(
            personal=self.emp,
            periodo_inicio=self.hoy - timedelta(days=800),
            periodo_fin=self.hoy - timedelta(days=435),
            dias_derecho=30, dias_gozados=25,
            dias_vendidos=0, dias_pendientes=5,
            estado='PARCIAL',
        )
        sol = SolicitudVacacion.objects.create(
            personal=self.emp,
            saldo=saldo_chico,
            fecha_inicio=self.hoy + timedelta(days=30),
            fecha_fin=self.hoy + timedelta(days=39),  # 10 días
            dias_calendario=0,
            estado='PENDIENTE',
        )
        with self.assertRaises(ValueError):
            sol.aprobar(self.admin)


# ════════════════════════════════════════════════════════════════════
# 4. Seeds command
# ════════════════════════════════════════════════════════════════════

class TestSeedsCommand(TestCase):
    """Verifica que el management command de seeds no falle."""

    @classmethod
    def setUpTestData(cls):
        # Crear 6 empleados con >1 año
        hoy = date.today()
        for i in range(6):
            Personal.objects.create(
                nro_doc=f'5000000{i}',
                apellidos_nombres=f'Seed Test {i}',
                tipo_doc='DNI',
                fecha_alta=hoy - timedelta(days=400 + i * 30),
                estado='Activo',
            )

    def test_seed_command_runs_without_error(self):
        """El comando seed_solicitudes_vacacion corre sin errores."""
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        try:
            call_command('seed_solicitudes_vacacion', stdout=out)
        except Exception as e:
            self.fail(f'seed_solicitudes_vacacion falló: {e}')
        # Al menos 1 solicitud creada
        self.assertGreater(
            SolicitudVacacion.objects.filter(motivo__startswith='[SEED]').count(),
            0
        )
