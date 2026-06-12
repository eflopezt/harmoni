"""
Tests del Agente IA Nóminas — engine de reintegros + tools + flujo aprobación.

Cubre:
- Engine reintegros (diff, impacto, HE, asig fam, gratif)
- Tools del agente (buscar, calcular, proponer)
- RAG normativa (búsqueda por keyword)
- Approval flow (PROPUESTO → APROBADO → APLICADO → REVERSADO)
- Audit del agente
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from nominas.engine_reintegros import (
    calcular_diferencia_sueldo,
    calcular_impacto_total_reintegro,
    calcular_reintegro_asignacion_familiar,
    calcular_reintegro_gratificacion,
    calcular_reintegro_he_no_pagadas,
    simular_impacto_aportes,
)
from nominas.models import (
    AuditAgenteIA,
    ConversacionAgenteIA,
    MensajeAgenteIA,
    ReintegroNomina,
)

User = get_user_model()


def _crear_personal(dni='40000001', nombre='Test Worker', sueldo=Decimal('3000'),
                    regimen='ONP', eps=False, empresa_ruc=None):
    """Helper para crear trabajador con datos requeridos."""
    from empresas.models import Empresa
    from personal.models import Personal
    from nominas.tests._helpers import unique_ruc

    if empresa_ruc is None:
        # RUC vía counter atómico, no timestamp — evita colisión por ms en suite.
        empresa_ruc = unique_ruc()

    emp, _ = Empresa.objects.get_or_create(
        ruc=empresa_ruc,
        defaults={'razon_social': 'Test SAC', 'plan': 'PROFESIONAL'},
    )
    p = Personal.objects.create(
        tipo_doc='DNI', nro_doc=dni,
        apellidos_nombres=nombre, cargo='Tester',
        tipo_trab='EMPLEADO', categoria='EMPLEADO',
        estado='Activo', empresa=emp,
        sueldo_base=sueldo,
        fecha_alta=date(2024, 1, 1),
        regimen_pension=regimen,
        tiene_eps=eps,
    )
    return p, emp


class EngineReintegrosTests(TestCase):
    def test_diferencia_sueldo_basica(self):
        """500 a favor del trabajador (2500 → 3000)."""
        d = calcular_diferencia_sueldo(Decimal('2500'), Decimal('3000'))
        self.assertEqual(d['diferencia'], Decimal('500'))
        self.assertEqual(d['tipo'], 'A_FAVOR_TRABAJADOR')
        self.assertTrue(d['es_relevante'])

    def test_diferencia_sueldo_descuento(self):
        """Si pagamos 3000 cuando era 2500 → descuento."""
        d = calcular_diferencia_sueldo(Decimal('3000'), Decimal('2500'))
        self.assertEqual(d['diferencia'], Decimal('-500'))
        self.assertEqual(d['tipo'], 'DESCUENTO')

    def test_diferencia_sin_cambio(self):
        d = calcular_diferencia_sueldo(Decimal('3000'), Decimal('3000'))
        self.assertEqual(d['tipo'], 'SIN_CAMBIO')
        self.assertFalse(d['es_relevante'])

    def test_simular_impacto_500_onp(self):
        """500 ONP: descuento 13% = 65, neto = 435."""
        imp = simular_impacto_aportes(Decimal('500'), regimen='ONP')
        self.assertEqual(imp['descuentos']['ONP_13pct'], Decimal('65.00'))
        self.assertEqual(imp['monto_neto'], Decimal('435.00'))
        # ESSALUD empleador 9% = 45
        self.assertEqual(imp['aportes_empleador']['ESSALUD'], Decimal('45.00'))

    def test_simular_impacto_eps_baja_essalud(self):
        """Con EPS, ESSALUD baja de 9% a 6.75%."""
        imp = simular_impacto_aportes(Decimal('1000'), regimen='ONP', tiene_eps=True)
        # 1000 × 6.75% = 67.50
        self.assertEqual(imp['aportes_empleador']['ESSALUD'], Decimal('67.50'))

    def test_simular_impacto_no_remunerativo(self):
        """No remunerativo → sin aportes."""
        imp = simular_impacto_aportes(Decimal('500'), es_remunerativo=False)
        self.assertEqual(imp['descuentos'], {})
        self.assertEqual(imp['monto_neto'], Decimal('500'))

    def test_he_no_pagadas(self):
        """4h HE 25% sueldo 2400 = 50.00"""
        r = calcular_reintegro_he_no_pagadas(Decimal('4'), Decimal('2400'), 'HE_25')
        self.assertEqual(r['monto'], Decimal('50.00'))

    def test_asignacion_familiar_3_meses(self):
        """3 meses × 113 = 339"""
        r = calcular_reintegro_asignacion_familiar(3, Decimal('113.00'))
        self.assertEqual(r['monto_total'], Decimal('339.00'))

    def test_reintegro_gratificacion_con_bonif(self):
        """Pagado 2000, correcto 2500 → dif 500 + bonif 9% (45) = 545."""
        r = calcular_reintegro_gratificacion(
            Decimal('2000'), Decimal('2500'), tiene_eps=False,
        )
        self.assertEqual(r['diferencia'], Decimal('500'))
        self.assertEqual(r['bonif_extra'], Decimal('45.00'))
        self.assertEqual(r['monto_reintegro'], Decimal('545.00'))

    def test_reintegro_gratificacion_con_eps(self):
        """EPS: bonif 6.75% en lugar de 9%."""
        r = calcular_reintegro_gratificacion(
            Decimal('2000'), Decimal('2500'), tiene_eps=True,
        )
        self.assertEqual(r['bonif_extra'], Decimal('33.75'))  # 500 × 6.75%
        self.assertEqual(r['monto_reintegro'], Decimal('533.75'))


class ToolsAgenteTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='agente_admin', password='admin', is_superuser=True,
        )
        self.personal, self.empresa = _crear_personal(
            dni='49999991', nombre='Juan Perez',
            empresa_ruc='20888888881',
        )

    def test_tool_buscar_trabajador_por_dni(self):
        from nominas.agente_ia.tools import tool_buscar_trabajador
        r = tool_buscar_trabajador('49999991')
        self.assertNotIn('error', r)
        self.assertEqual(r['total'], 1)
        self.assertEqual(r['encontrados'][0]['dni'], '49999991')

    def test_tool_buscar_trabajador_por_nombre(self):
        from nominas.agente_ia.tools import tool_buscar_trabajador
        r = tool_buscar_trabajador('Juan')
        self.assertNotIn('error', r)
        self.assertGreaterEqual(r['total'], 1)

    def test_tool_buscar_no_existe(self):
        from nominas.agente_ia.tools import tool_buscar_trabajador
        r = tool_buscar_trabajador('99999999')
        self.assertIn('error', r)

    def test_tool_calcular_reintegro_sueldo(self):
        from nominas.agente_ia.tools import tool_calcular_reintegro_sueldo
        r = tool_calcular_reintegro_sueldo(
            personal_id=self.personal.pk,
            sueldo_pagado=2500, sueldo_correcto=3000,
            periodo_origen_anio=2026, periodo_origen_mes=4,
        )
        self.assertNotIn('error', r)
        self.assertEqual(r['monto_reintegro'], 500.00)
        self.assertGreater(r['monto_neto'], 0)
        # Con régimen ONP, neto debería ser 500 - 65 = 435
        self.assertEqual(r['monto_neto'], 435.00)

    def test_tool_aprobaciones_pendientes_vacio(self):
        from nominas.agente_ia.tools import tool_listar_aprobaciones_pendientes
        r = tool_listar_aprobaciones_pendientes()
        self.assertEqual(r['total_pendientes'], 0)
        self.assertIn('nota', r)

    def test_tool_aprobaciones_pendientes_consolida_modulos(self):
        from descuentos.models import DescuentoPlanilla
        from prestamos.models import Prestamo, TipoPrestamo
        from nominas.agente_ia.tools import tool_listar_aprobaciones_pendientes

        tipo = TipoPrestamo.objects.create(
            nombre='Adelanto test', codigo='adelanto-sueldo-ewa', max_cuotas=1)
        Prestamo.objects.create(
            personal=self.personal, tipo=tipo,
            monto_solicitado=Decimal('300'), num_cuotas=1, estado='PENDIENTE')
        DescuentoPlanilla.objects.create(
            personal=self.personal, causal='ROTURA_HERRAMIENTA',
            detalle='x', monto_total=Decimal('100'), num_cuotas=1,
            estado='PENDIENTE')

        r = tool_listar_aprobaciones_pendientes()
        self.assertEqual(r['total_pendientes'], 2)
        self.assertEqual(r['bloques']['prestamos_y_adelantos']['total'], 1)
        self.assertTrue(r['bloques']['prestamos_y_adelantos']['detalle'][0]['es_adelanto_ewa'])
        self.assertEqual(r['bloques']['descuentos_planilla']['total'], 1)
        self.assertIn('donde_aprobar', r['bloques']['descuentos_planilla'])

    def test_intent_aprobaciones_y_respuesta_heuristica(self):
        from nominas.agente_ia.orquestador import _detectar_intent, _procesar_heuristico
        self.assertEqual(_detectar_intent('¿qué tengo pendiente de aprobar?'),
                         'aprobaciones_pendientes')

        conv = ConversacionAgenteIA.objects.create(usuario=self.user)
        resultado = _procesar_heuristico(conv, '¿qué aprobaciones tengo pendientes?',
                                         usuario=self.user)
        self.assertEqual(resultado['intent_detectado'], 'aprobaciones_pendientes')
        self.assertIn('No tienes nada pendiente', resultado['respuesta'])
        self.assertTrue(AuditAgenteIA.objects.filter(accion='CONSULTA_PENDIENTES').exists())

    def test_tool_proponer_reintegro_crea_propuesto(self):
        from nominas.agente_ia.tools import tool_proponer_reintegro
        r = tool_proponer_reintegro(
            personal_id=self.personal.pk,
            motivo='ERROR_SUELDO',
            descripcion='Test reintegro',
            periodo_origen_anio=2026, periodo_origen_mes=4,
            monto_que_se_pago=2500, monto_correcto=3000,
            _context={'usuario': self.user},
        )
        self.assertNotIn('error', r)
        self.assertEqual(r['estado'], 'PROPUESTO')
        self.assertTrue(r['requiere_aprobacion'])

        # Verificar que se creó
        reintegro = ReintegroNomina.objects.get(pk=r['reintegro_id'])
        self.assertEqual(reintegro.estado, 'PROPUESTO')
        self.assertEqual(reintegro.monto_reintegro, Decimal('500.00'))
        self.assertTrue(reintegro.propuesto_por_ia)

    def test_tool_listar_pendientes_filtro_personal(self):
        """Crear 2 reintegros y listar solo del trabajador."""
        from nominas.agente_ia.tools import tool_proponer_reintegro, tool_listar_reintegros_pendientes
        tool_proponer_reintegro(
            personal_id=self.personal.pk, motivo='ERROR_SUELDO',
            descripcion='r1', periodo_origen_anio=2026, periodo_origen_mes=3,
            monto_que_se_pago=2000, monto_correcto=2500,
            _context={'usuario': self.user},
        )
        r = tool_listar_reintegros_pendientes(personal_id=self.personal.pk)
        self.assertGreaterEqual(r['total'], 1)


class RAGNormativaTests(TestCase):
    def test_buscar_gratificacion(self):
        from nominas.agente_ia.rag import buscar_normativa
        r = buscar_normativa('cuándo se paga la gratificación')
        self.assertGreater(len(r), 0)
        self.assertIn('Gratificación', r[0]['titulo'])

    def test_buscar_embargo(self):
        from nominas.agente_ia.rag import buscar_normativa
        r = buscar_normativa('tope embargo civil')
        self.assertGreater(len(r), 0)
        self.assertIn('Embargo', r[0]['titulo'])

    def test_buscar_eps(self):
        from nominas.agente_ia.rag import buscar_normativa
        r = buscar_normativa('EPS crédito empleador 6.75')
        self.assertGreater(len(r), 0)

    def test_buscar_sin_resultados(self):
        from nominas.agente_ia.rag import buscar_normativa
        r = buscar_normativa('quantum entanglement física')
        self.assertEqual(len(r), 0)


class ApprovalFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='flow_admin', password='admin', is_superuser=True,
        )
        self.personal, _ = _crear_personal(
            dni='49999992', nombre='Maria Lopez', empresa_ruc='20888888882',
        )
        self.client.force_login(self.user)
        # Crear reintegro propuesto
        self.reintegro = ReintegroNomina.objects.create(
            personal=self.personal,
            motivo='ERROR_SUELDO',
            descripcion='Test approval flow',
            periodo_origen_anio=2026, periodo_origen_mes=4,
            monto_que_se_pago=Decimal('2500'),
            monto_correcto=Decimal('3000'),
            monto_reintegro=Decimal('500'),
            estado='PROPUESTO',
            propuesto_por=self.user,
        )

    def test_aprobar_pasa_a_aprobado(self):
        resp = self.client.post(f'/nominas/reintegros/{self.reintegro.pk}/aprobar/')
        self.assertEqual(resp.status_code, 302)  # redirect
        self.reintegro.refresh_from_db()
        self.assertEqual(self.reintegro.estado, 'APROBADO')
        self.assertEqual(self.reintegro.aprobado_por, self.user)
        self.assertIsNotNone(self.reintegro.aprobado_en)

    def test_aprobar_solo_si_propuesto(self):
        """No se puede aprobar uno ya aprobado."""
        self.reintegro.estado = 'APROBADO'
        self.reintegro.save()
        resp = self.client.post(f'/nominas/reintegros/{self.reintegro.pk}/aprobar/')
        self.reintegro.refresh_from_db()
        # No cambia
        self.assertEqual(self.reintegro.estado, 'APROBADO')

    def test_revertir_requiere_motivo(self):
        self.reintegro.estado = 'APROBADO'
        self.reintegro.save()
        # Sin motivo
        resp = self.client.post(
            f'/nominas/reintegros/{self.reintegro.pk}/revertir/',
            data={'motivo': ''},
        )
        self.reintegro.refresh_from_db()
        # No cambió por falta de motivo
        self.assertEqual(self.reintegro.estado, 'APROBADO')

    def test_revertir_con_motivo(self):
        self.reintegro.estado = 'APROBADO'
        self.reintegro.save()
        resp = self.client.post(
            f'/nominas/reintegros/{self.reintegro.pk}/revertir/',
            data={'motivo': 'Error de cálculo, voy a recalcular'},
        )
        self.reintegro.refresh_from_db()
        self.assertEqual(self.reintegro.estado, 'REVERSADO')
        self.assertEqual(self.reintegro.revertido_por, self.user)
        self.assertIn('Error', self.reintegro.motivo_reversion)


class OrquestadorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='orq_admin', password='admin', is_superuser=True,
        )
        self.conv = ConversacionAgenteIA.objects.create(usuario=self.user)

    def test_intent_consulta_normativa(self):
        from nominas.agente_ia.orquestador import procesar_mensaje
        r = procesar_mensaje(
            self.conv, '¿Cuándo se paga la gratificación?', usuario=self.user,
        )
        self.assertEqual(r['intent_detectado'], 'consulta_normativa')
        self.assertEqual(len(r['tools_llamadas']), 1)
        self.assertEqual(r['tools_llamadas'][0]['name'], 'consultar_normativa')

    def test_mensaje_se_guarda(self):
        from nominas.agente_ia.orquestador import procesar_mensaje
        procesar_mensaje(self.conv, '¿Qué es la EPS?', usuario=self.user)
        # Debe haber al menos: 1 user, 1 tool, 1 assistant
        mensajes = MensajeAgenteIA.objects.filter(conversacion=self.conv)
        self.assertGreaterEqual(mensajes.count(), 3)

    def test_audit_se_registra(self):
        from nominas.agente_ia.orquestador import procesar_mensaje
        procesar_mensaje(self.conv, '¿Cómo funciona la CTS?', usuario=self.user)
        audits = AuditAgenteIA.objects.filter(conversacion=self.conv)
        self.assertGreater(audits.count(), 0)

    def test_titulo_auto_asignado(self):
        from nominas.agente_ia.orquestador import procesar_mensaje
        procesar_mensaje(self.conv, 'Mi primera consulta sobre gratificación', usuario=self.user)
        self.conv.refresh_from_db()
        self.assertIn('gratificación', self.conv.titulo.lower())
