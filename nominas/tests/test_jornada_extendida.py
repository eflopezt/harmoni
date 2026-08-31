"""
Tests E2E para todos los features de la jornada extendida:
- Calculadora simulador + pública + comparar + AFP + PDF
- Cierre mensual de planilla
- Detector duplicados
- Health endpoint
- Detector anomalías
- Reporte ejecutivo PDF
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from nominas.models import ConceptoRemunerativo, PeriodoNomina, RegistroNomina

User = get_user_model()


class CalculadoraTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='calc_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_calculadora_get(self):
        resp = self.client.get('/nominas/calculadora/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Calculadora de Planilla')

    def test_calculadora_post_basico(self):
        resp = self.client.post('/nominas/calculadora/', {
            'sueldo': '3000', 'regimen': 'ONP',
        })
        self.assertEqual(resp.status_code, 200)
        result = resp.context['result']
        self.assertIsNotNone(result)
        self.assertNotIn('error', result)
        # 3000 con ONP 13% → descuento ONP debería ser cerca de 390
        self.assertIn('onp', result['descuentos'])

    def test_calculadora_eps_baja_essalud(self):
        """Con EPS, ESSALUD debe ser 6.75% en vez de 9%."""
        resp = self.client.post('/nominas/calculadora/', {
            'sueldo': '3000', 'regimen': 'ONP', 'tiene_eps': 'on',
        })
        result = resp.context['result']
        essalud_label = result['aportes_empleador']['essalud']['label']
        self.assertIn('6.75', essalud_label)

    def test_calculadora_comparar_dos_escenarios(self):
        resp = self.client.post('/nominas/calculadora/comparar/', {
            'sueldo_a': '2500', 'sueldo_b': '3000', 'regimen': 'ONP',
        })
        self.assertEqual(resp.status_code, 200)
        delta = resp.context['delta']
        self.assertIsNotNone(delta)
        # Sueldo subió 500 → delta positivo
        self.assertGreater(delta['sueldo'], 0)
        self.assertGreater(delta['neto'], 0)

    def test_calculadora_afp_compara_5_opciones(self):
        """AFP recomendador debe devolver ONP + 4 AFPs."""
        resp = self.client.post('/nominas/calculadora/afp/', {
            'sueldo': '3000',
        })
        self.assertEqual(resp.status_code, 200)
        ranking = resp.context['ranking']
        self.assertEqual(len(ranking), 5)  # ONP + Habitat + Integra + Prima + Profuturo
        # El primero debe tener mayor neto
        self.assertEqual(ranking[0]['rank'], 1)
        self.assertGreaterEqual(ranking[0]['neto'], ranking[-1]['neto'])

    def test_calculadora_publica_sin_login(self):
        """Accesible sin autenticación."""
        self.client.logout()
        resp = self.client.get('/calculadora/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Calculadora de Planilla')

    def test_calculadora_api_json_post(self):
        """POST con body JSON devuelve simulación JSON."""
        import json
        self.client.logout()  # API es CSRF-exempt y sin auth
        resp = self.client.post(
            '/api/calculadora/',
            data=json.dumps({'sueldo': '3000', 'regimen': 'ONP'}),
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('neto', data)
        self.assertIn('costo_full_loaded', data)


class WorkflowMesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='wf_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_workflow_mes_render(self):
        resp = self.client.get('/nominas/workflow-mes/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Cierre de planilla')
        # Debe haber 12 steps (se añadió 'Pago a banco' como paso #10, entre
        # AFPNet y Asiento Contable, renumerando los siguientes).
        self.assertEqual(len(resp.context['steps']), 12)
        # Progreso siempre entre 0 y 100
        self.assertGreaterEqual(resp.context['progreso_pct'], 0)
        self.assertLessEqual(resp.context['progreso_pct'], 100)

    def test_workflow_mes_respeta_periodo_elegido(self):
        marzo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
        )
        PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=8,
            descripcion='Agosto 2026',
            fecha_inicio=date(2026, 8, 1),
            fecha_fin=date(2026, 8, 31),
            estado='BORRADOR',
        )

        resp = self.client.get('/nominas/workflow-mes/?mes=3&anio=2026')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['periodo'], marzo)
        self.assertEqual(resp.context['mes'], 3)
        self.assertEqual(resp.context['anio'], 2026)
        self.assertContains(resp, 'Marzo 2026')
        self.assertContains(resp, 'Estado del cierre')

    def test_workflow_mes_crear_periodo_conserva_mes_y_anio(self):
        resp = self.client.get('/nominas/workflow-mes/?mes=4&anio=2026')

        self.assertEqual(resp.status_code, 200)
        step_periodo = next(s for s in resp.context['steps'] if s['key'] == 'periodo')
        self.assertIn('tipo=REGULAR', step_periodo['link'])
        self.assertIn('mes=4', step_periodo['link'])
        self.assertIn('anio=2026', step_periodo['link'])
        self.assertIn('origen=workflow', step_periodo['link'])
        self.assertContains(
            resp,
            '/nominas/periodos/nuevo/?tipo=REGULAR&amp;mes=4&amp;anio=2026&amp;origen=workflow',
        )
        self.assertContains(resp, '/nominas/workflow-mes/?mes=3&amp;anio=2026')
        self.assertContains(resp, '/nominas/workflow-mes/?mes=5&amp;anio=2026')

    def test_workflow_mes_cerrado_sin_boletas_pide_regularizar(self):
        PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
        )

        resp = self.client.get('/nominas/workflow-mes/?mes=3&anio=2026')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['estado_operativo_label'], 'En revisión')
        self.assertEqual(resp.context['n_registros_periodo'], 0)
        self.assertContains(resp, 'Cierre congelado sin boletas calculadas')
        self.assertContains(resp, 'Regularizar cierre')

        generar = next(s for s in resp.context['steps'] if s['key'] == 'generar')
        aprobar = next(s for s in resp.context['steps'] if s['key'] == 'aprobar')
        cerrar = next(s for s in resp.context['steps'] if s['key'] == 'cerrar')
        acuses = next(s for s in resp.context['steps'] if s['key'] == 'acuses')

        self.assertFalse(generar['done'])
        self.assertTrue(generar['post_close_attention'])
        self.assertTrue(aprobar['bloqueado'])
        self.assertFalse(cerrar['done'])
        self.assertFalse(acuses['done'])

    def test_periodo_detalle_regulariza_cierre_vacio(self):
        from personal.models import Personal

        Personal.objects.create(
            tipo_doc='DNI',
            nro_doc='49990091',
            apellidos_nombres='TRABAJADOR REGULARIZACION, LIA',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        periodo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
            cerrado_por=self.user,
            cerrado_en=timezone.now(),
        )

        detalle = self.client.get(f'/nominas/periodos/{periodo.pk}/')

        self.assertContains(detalle, 'Regularizar cierre')
        self.assertTrue(detalle.context['periodo_cerrado_sin_calculo'])
        self.assertTrue(detalle.context['puede_generar'])

        self.client.post(f'/nominas/periodos/{periodo.pk}/generar/')
        periodo.refresh_from_db()

        self.assertEqual(periodo.estado, 'CALCULADO')
        self.assertIsNone(periodo.cerrado_por)
        self.assertIsNone(periodo.cerrado_en)
        self.assertGreater(periodo.registros.count(), 0)

    def test_periodo_generar_no_reabre_cerrado_con_boletas(self):
        from personal.models import Personal

        trabajador = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc='49990092',
            apellidos_nombres='TRABAJADOR CERRADO, MARCO',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        periodo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
            cerrado_por=self.user,
            cerrado_en=timezone.now(),
        )
        RegistroNomina.objects.create(
            periodo=periodo,
            personal=trabajador,
            sueldo_base=Decimal('3000'),
            dias_trabajados=30,
            regimen_pension='ONP',
            total_ingresos=Decimal('3000'),
            total_descuentos=Decimal('390'),
            neto_a_pagar=Decimal('2610'),
            estado='APROBADO',
        )

        self.client.post(f'/nominas/periodos/{periodo.pk}/generar/')
        periodo.refresh_from_db()

        self.assertEqual(periodo.estado, 'CERRADO')
        self.assertEqual(periodo.registros.count(), 1)

    def test_periodo_crear_prefill_desde_workflow(self):
        resp = self.client.get(
            '/nominas/periodos/nuevo/?tipo=REGULAR&mes=4&anio=2026&origen=workflow')

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['tipo_actual'], 'REGULAR')
        self.assertEqual(resp.context['mes_actual'], 4)
        self.assertEqual(resp.context['anio_actual'], 2026)
        self.assertEqual(resp.context['fecha_inicio_default'], date(2026, 3, 22))
        self.assertEqual(resp.context['fecha_fin_default'], date(2026, 4, 21))
        self.assertEqual(resp.context['fecha_pago_default'], date(2026, 4, 25))
        self.assertContains(resp, 'Abril 2026')
        self.assertContains(resp, 'value="2026-03-22"')
        self.assertContains(resp, 'value="2026-04-21"')
        self.assertContains(resp, 'value="2026-04-25"')
        self.assertContains(resp, 'name="origen" value="workflow"')
        self.assertContains(resp, '/nominas/workflow-mes/?mes=4&amp;anio=2026')

    def test_periodo_crear_asocia_empresa_actual_y_no_duplica(self):
        from empresas.models import Empresa

        empresa = Empresa.objects.create(
            ruc='20987654321',
            razon_social='Empresa Nómina Test SAC',
            activa=True,
            es_principal=True,
        )
        session = self.client.session
        session['empresa_actual_id'] = empresa.pk
        session.save()

        payload = {
            'origen': 'workflow',
            'tipo': 'REGULAR',
            'anio': '2026',
            'mes': '4',
            'descripcion': '',
            'fecha_inicio': '2026-03-22',
            'fecha_fin': '2026-04-21',
            'fecha_pago': '2026-04-25',
        }
        resp = self.client.post('/nominas/periodos/nuevo/', payload)

        periodo = PeriodoNomina.objects.get(tipo='REGULAR', anio=2026, mes=4)
        self.assertEqual(periodo.empresa, empresa)
        self.assertEqual(periodo.descripcion, 'Planilla regular Abril 2026')
        self.assertRedirects(
            resp,
            f'/nominas/periodos/{periodo.pk}/',
            fetch_redirect_response=False,
        )

        resp_dup = self.client.post('/nominas/periodos/nuevo/', payload)

        self.assertEqual(
            PeriodoNomina.objects.filter(tipo='REGULAR', anio=2026, mes=4).count(),
            1,
        )
        self.assertRedirects(
            resp_dup,
            f'/nominas/periodos/{periodo.pk}/',
            fetch_redirect_response=False,
        )

    def test_pre_planilla_valida_cobertura_contractual_del_periodo(self):
        from empresas.models import Empresa
        from nominas.tests._helpers import unique_dni, unique_ruc
        from personal.models import Personal

        empresa = Empresa.objects.create(
            ruc=unique_ruc(),
            razon_social='Empresa Cobertura Contratos SAC',
            activa=True,
            es_principal=True,
        )
        session = self.client.session
        session['empresa_actual_id'] = empresa.pk
        session.save()
        Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='CONTRATO EN FICHA, ANA',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa,
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2026, 1, 1),
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio_contrato=date(2026, 1, 1),
            fecha_fin_contrato=date(2026, 11, 30),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )

        resp = self.client.get('/nominas/pre-planilla/?mes=3&anio=2026')

        self.assertEqual(resp.status_code, 200)
        check_contratos = next(c for c in resp.context['checks'] if c['clave'] == 'contratos')
        self.assertEqual(check_contratos['valor'], 0)
        self.assertEqual(check_contratos['estado'], 'ok')
        self.assertContains(resp, 'Trabajadores sin contrato del período')

    def test_pre_planilla_detecta_solo_contratos_sin_continuidad(self):
        from empresas.models import Empresa
        from nominas.tests._helpers import unique_dni, unique_ruc
        from personal.models import Contrato, Personal

        empresa = Empresa.objects.create(
            ruc=unique_ruc(),
            razon_social='Empresa Continuidad Contratos SAC',
            activa=True,
            es_principal=True,
        )
        session = self.client.session
        session['empresa_actual_id'] = empresa.pk
        session.save()
        renovado = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='CONTRATO RENOVADO, LUIS',
            cargo='Supervisor',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa,
            sueldo_base=Decimal('4200'),
            fecha_alta=date(2026, 1, 1),
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio_contrato=date(2026, 4, 1),
            fecha_fin_contrato=date(2026, 11, 30),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        Contrato.objects.create(
            personal=renovado,
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 3, 31),
            estado='RENOVADO',
            sueldo_pactado=Decimal('4200'),
        )
        Contrato.objects.create(
            personal=renovado,
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio=date(2026, 4, 1),
            fecha_fin=date(2026, 11, 30),
            estado='VIGENTE',
            sueldo_pactado=Decimal('4200'),
        )
        sin_continuidad = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='CONTRATO SIN CONTINUIDAD, ROSA',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa,
            sueldo_base=Decimal('3500'),
            fecha_alta=date(2026, 1, 1),
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio_contrato=date(2026, 1, 1),
            fecha_fin_contrato=date(2026, 3, 31),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        Contrato.objects.create(
            personal=sin_continuidad,
            tipo_contrato='PLAZO_FIJO',
            fecha_inicio=date(2026, 1, 1),
            fecha_fin=date(2026, 3, 31),
            estado='VIGENTE',
            sueldo_pactado=Decimal('3500'),
        )

        resp = self.client.get('/nominas/pre-planilla/?mes=3&anio=2026')

        self.assertEqual(resp.status_code, 200)
        check_contratos = next(c for c in resp.context['checks'] if c['clave'] == 'contratos')
        check_vencen = next(c for c in resp.context['checks'] if c['clave'] == 'vencen')
        self.assertEqual(check_contratos['valor'], 0)
        self.assertEqual(check_contratos['estado'], 'ok')
        self.assertEqual(check_vencen['valor'], 1)
        self.assertEqual(check_vencen['estado'], 'warn')
        self.assertEqual(check_vencen['detalle'], '1 por enlazar')
        self.assertContains(resp, 'Contratos que terminan sin continuidad')

    def test_generar_periodo_respeta_empresa_y_trabajadores_del_periodo(self):
        from empresas.models import Empresa
        from nominas import engine
        from nominas.tests._helpers import unique_dni, unique_ruc
        from personal.models import Personal

        empresa_a = Empresa.objects.create(
            ruc=unique_ruc(),
            razon_social='Empresa Nómina A SAC',
            activa=True,
            es_principal=True,
        )
        empresa_b = Empresa.objects.create(
            ruc=unique_ruc(),
            razon_social='Empresa Nómina B SAC',
            activa=True,
            es_principal=True,
        )
        vigente_a = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='TRABAJADOR A, VIGENTE',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa_a,
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        cesado_en_periodo_a = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='TRABAJADOR A, CESADO EN MES',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Cesado',
            empresa=empresa_a,
            sueldo_base=Decimal('2500'),
            fecha_alta=date(2025, 1, 1),
            fecha_cese=date(2026, 4, 5),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        Personal.objects.create(
            tipo_doc='DNI',
            nro_doc=unique_dni(),
            apellidos_nombres='TRABAJADOR B, NO DEBE ENTRAR',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa_b,
            sueldo_base=Decimal('4000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        periodo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=4,
            descripcion='Planilla regular Abril 2026',
            fecha_inicio=date(2026, 3, 22),
            fecha_fin=date(2026, 4, 21),
            fecha_pago=date(2026, 4, 25),
            empresa=empresa_a,
        )

        engine.generar_periodo(periodo, usuario=self.user)

        personal_ids = set(
            RegistroNomina.objects.filter(periodo=periodo)
            .values_list('personal_id', flat=True)
        )
        self.assertEqual(personal_ids, {vigente_a.pk, cesado_en_periodo_a.pk})

    def test_periodo_cerrar_bloquea_vacio_y_guarda_trazabilidad(self):
        from personal.models import Personal

        periodo = PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=4,
            descripcion='Planilla regular Abril 2026',
            fecha_inicio=date(2026, 3, 22),
            fecha_fin=date(2026, 4, 21),
            fecha_pago=date(2026, 4, 25),
            estado='APROBADO',
        )

        resp_vacio = self.client.post(f'/nominas/periodos/{periodo.pk}/cerrar/')

        self.assertRedirects(
            resp_vacio,
            f'/nominas/periodos/{periodo.pk}/',
            fetch_redirect_response=False,
        )
        periodo.refresh_from_db()
        self.assertEqual(periodo.estado, 'APROBADO')
        self.assertIsNone(periodo.cerrado_en)
        self.assertIsNone(periodo.cerrado_por)

        trabajador = Personal.objects.create(
            tipo_doc='DNI',
            nro_doc='49990001',
            apellidos_nombres='TRABAJADOR CIERRE, ANA',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )
        RegistroNomina.objects.create(
            periodo=periodo,
            personal=trabajador,
            sueldo_base=Decimal('3000'),
            dias_trabajados=30,
            regimen_pension='ONP',
            total_ingresos=Decimal('3000'),
            total_descuentos=Decimal('390'),
            neto_a_pagar=Decimal('2610'),
            estado='APROBADO',
        )

        resp_cierre = self.client.post(f'/nominas/periodos/{periodo.pk}/cerrar/')

        self.assertRedirects(
            resp_cierre,
            f'/nominas/periodos/{periodo.pk}/',
            fetch_redirect_response=False,
        )
        periodo.refresh_from_db()
        self.assertEqual(periodo.estado, 'CERRADO')
        self.assertEqual(periodo.cerrado_por, self.user)
        self.assertIsNotNone(periodo.cerrado_en)

    def test_cierre_marzo_a_julio_flujo_completo_aislado(self):
        from empresas.models import Empresa
        from personal.models import Personal

        empresa = Empresa.objects.create(
            ruc='20987654322',
            razon_social='Empresa Cierre Mensual SAC',
            activa=True,
            es_principal=True,
        )
        session = self.client.session
        session['empresa_actual_id'] = empresa.pk
        session.save()
        Personal.objects.create(
            tipo_doc='DNI',
            nro_doc='49990002',
            apellidos_nombres='TRABAJADOR MENSUAL, LUIS',
            cargo='Analista',
            tipo_trab='Empleado',
            estado='Activo',
            empresa=empresa,
            sueldo_base=Decimal('3000'),
            fecha_alta=date(2025, 1, 1),
            regimen_pension='ONP',
            grupo_tareo='STAFF',
        )

        for mes in range(3, 9):
            mes_anterior = 12 if mes == 1 else mes - 1
            anio_anterior = 2025 if mes == 1 else 2026
            resp_workflow = self.client.get(f'/nominas/workflow-mes/?mes={mes}&anio=2026')
            self.assertEqual(resp_workflow.status_code, 200)
            self.assertIn(f'mes={mes}', resp_workflow.context['resumen_cierre']['url'])

            self.client.post('/nominas/periodos/nuevo/', {
                'origen': 'workflow',
                'tipo': 'REGULAR',
                'anio': '2026',
                'mes': str(mes),
                'descripcion': '',
                'fecha_inicio': f'{anio_anterior}-{mes_anterior:02d}-22',
                'fecha_fin': f'2026-{mes:02d}-21',
                'fecha_pago': f'2026-{mes:02d}-25',
            })
            periodo = PeriodoNomina.objects.get(
                tipo='REGULAR',
                anio=2026,
                mes=mes,
                empresa=empresa,
            )
            self.assertEqual(periodo.estado, 'BORRADOR')

            self.client.post(f'/nominas/periodos/{periodo.pk}/generar/')
            periodo.refresh_from_db()
            self.assertEqual(periodo.estado, 'CALCULADO')
            self.assertGreater(periodo.registros.count(), 0)

            self.client.post(f'/nominas/periodos/{periodo.pk}/aprobar/')
            periodo.refresh_from_db()
            self.assertEqual(periodo.estado, 'APROBADO')
            resp_detalle = self.client.get(f'/nominas/periodos/{periodo.pk}/')
            self.assertContains(resp_detalle, 'Salidas y cierre')
            self.assertContains(resp_detalle, 'Cada salida nace de este período')
            self.assertContains(resp_detalle, 'Cerrar período')

            self.client.post(f'/nominas/periodos/{periodo.pk}/cerrar/')
            periodo.refresh_from_db()
            self.assertEqual(periodo.estado, 'CERRADO')
            self.assertEqual(periodo.cerrado_por, self.user)
            self.assertIsNotNone(periodo.cerrado_en)

            resp_cerrado = self.client.get(f'/nominas/workflow-mes/?mes={mes}&anio=2026')
            self.assertEqual(resp_cerrado.context['periodo'], periodo)

    def test_pre_planilla_cerrada_es_consulta_y_vuelve_al_cierre(self):
        PeriodoNomina.objects.create(
            tipo='REGULAR',
            anio=2026,
            mes=3,
            descripcion='Marzo 2026',
            fecha_inicio=date(2026, 3, 1),
            fecha_fin=date(2026, 3, 31),
            estado='CERRADO',
        )

        resp = self.client.get('/nominas/pre-planilla/?mes=3&anio=2026')

        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['modo_cerrado'])
        self.assertContains(resp, 'Período cerrado')
        self.assertContains(resp, '/nominas/workflow-mes/?mes=3&anio=2026')
        self.assertNotContains(resp, 'Resolver <i')


class DetectorDuplicadosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dup_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)
        # Crear concepto base
        ConceptoRemunerativo.objects.create(
            codigo='sueldo_basico', nombre='Sueldo Básico', tipo='INGRESO',
        )

    def test_detector_funciona_exacto(self):
        from nominas.views_conceptos import detectar_similares
        sims = detectar_similares('sueldo_basico', 'Otro nombre')
        # Match exacto en codigo
        self.assertTrue(any(s['confianza'] == 'EXACTO' for s in sims))

    def test_detector_bloquea_creacion_duplicada(self):
        """POST sin ignorar_similares con código existente debería redirigir al form con warning."""
        resp = self.client.post('/nominas/conceptos/configurar/nuevo/', {
            'codigo': 'sueldo_basico',
            'nombre': 'Sueldo Básico',
            'tipo': 'INGRESO',
            'subtipo': 'REMUNERATIVO',
            'formula': 'FIJO',
            'categoria': 'SUELDO',
        })
        # Debe re-renderizar el form (no redirigir a lista)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'similares')

    def test_detector_se_puede_ignorar(self):
        """Con ignorar_similares=1, sí se permite crear."""
        # Crear con código distinto pero nombre parecido
        resp = self.client.post('/nominas/conceptos/configurar/nuevo/', {
            'codigo': 'sueldo_extra_v2',
            'nombre': 'Sueldo Extra',
            'tipo': 'INGRESO',
            'subtipo': 'REMUNERATIVO',
            'formula': 'FIJO',
            'categoria': 'SUELDO',
            'ignorar_similares': '1',
        })
        # Si llegó al save y se creó, redirige
        self.assertIn(resp.status_code, [200, 302])
        # Verificar que se creó
        self.assertTrue(ConceptoRemunerativo.objects.filter(codigo='sueldo_extra_v2').exists())


class HealthEndpointTests(TestCase):
    def test_health_publico_sin_auth(self):
        """No requiere auth."""
        resp = self.client.get('/api/health/nominas/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('status', data)
        self.assertIn('service', data)
        self.assertEqual(data['service'], 'harmoni-nominas')

    def test_health_devuelve_score(self):
        resp = self.client.get('/api/health/nominas/')
        data = resp.json()
        # onboarding_score puede ser None si no hay empresa, pero la key debe existir
        self.assertIn('onboarding_score', data)
        self.assertIn('conceptos', data)


class AnomaliasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='anom_admin', password='admin', is_superuser=True,
        )
        self.client.force_login(self.user)

    def test_anomalias_pct_cambio_helper(self):
        from nominas.views_anomalias import _pct_cambio
        # 100 → 130 = +30%
        self.assertEqual(_pct_cambio(Decimal('100'), Decimal('130')), Decimal('30'))
        # 100 → 50 = -50%
        self.assertEqual(_pct_cambio(Decimal('100'), Decimal('50')), Decimal('-50'))
        # 0 → 50 = 100% (defensiva)
        self.assertEqual(_pct_cambio(Decimal('0'), Decimal('50')), Decimal('100'))
