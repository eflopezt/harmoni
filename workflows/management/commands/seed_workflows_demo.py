"""Siembra flujos y instancias de demo para el motor de aprobaciones.

Crea 3 plantillas de flujo (Vacaciones, Prestamo > 1000, Reembolso Viatico) y 5
instancias mock en distintos pasos, ideales para presentar la bandeja de
aprobaciones en demos sin depender de modulos cargados (vacaciones, prestamos,
reembolsos pueden o no existir).

Idempotente: usa get_or_create por nombre. Re-ejecutar no duplica datos.

Uso:
    manage.py seed_workflows_demo
    manage.py seed_workflows_demo --reset   # borra demo previa y recrea
"""
from datetime import timedelta

from django.contrib.auth.models import Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workflows.models import (
    EtapaFlujo,
    FlujoTrabajo,
    InstanciaFlujo,
    PasoFlujo,
)


MARCADOR_DEMO = '[DEMO]'


class Command(BaseCommand):
    help = 'Siembra 3 flujos demo + 5 instancias mock para presentaciones.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Borra los flujos demo previos antes de recrearlos.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['reset']:
            n_inst = InstanciaFlujo.objects.filter(
                metadata__demo=True,
            ).delete()[0]
            n_fl = FlujoTrabajo.objects.filter(
                nombre__startswith=MARCADOR_DEMO,
            ).delete()[0]
            self.stdout.write(self.style.WARNING(
                f'Reset: borradas {n_inst} instancias y {n_fl} flujos demo.'
            ))

        # Aprobadores demo (re-utilizamos superusers existentes si los hay)
        users = self._asegurar_usuarios_demo()
        ct_self = ContentType.objects.get_for_model(FlujoTrabajo)

        # ── Flujos ──────────────────────────────────────────────────
        f1 = self._crear_flujo_vacaciones(ct_self, users)
        f2 = self._crear_flujo_prestamo(ct_self, users)
        f3 = self._crear_flujo_viatico(ct_self, users)

        # ── Instancias mock ─────────────────────────────────────────
        instancias = self._crear_instancias_mock(f1, f2, f3, users)

        self.stdout.write(self.style.SUCCESS(
            f'seed_workflows_demo: 3 flujos + {len(instancias)} instancias listas.'
        ))
        self.stdout.write('Visita /workflows/bandeja/ logueado como uno de:')
        for u in users.values():
            self.stdout.write(f'  - {u.username}')

    # ─────────────────────────────────────────────────────────────────────
    # Setup
    # ─────────────────────────────────────────────────────────────────────

    def _asegurar_usuarios_demo(self):
        """Crea/recupera 4 usuarios demo + grupos."""
        users = {}
        defs = [
            ('demo_manager',   'Manager',  'Demo'),
            ('demo_gerencia',  'Gerencia', 'Demo'),
            ('demo_finanzas',  'Finanzas', 'Demo'),
            ('demo_solicit',   'Trabajador', 'Demo'),
        ]
        for username, first, last in defs:
            u, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first, 'last_name': last,
                    'email': f'{username}@harmoni.demo', 'is_active': True,
                },
            )
            if created:
                u.set_password('demo1234')
                u.save()
            users[username] = u

        # Grupos
        g_finanzas, _ = Group.objects.get_or_create(name='Finanzas Demo')
        g_finanzas.user_set.add(users['demo_finanzas'])
        users['grupo_finanzas'] = g_finanzas

        g_gerencia, _ = Group.objects.get_or_create(name='Gerencia Demo')
        g_gerencia.user_set.add(users['demo_gerencia'])
        users['grupo_gerencia'] = g_gerencia

        return users

    # ─────────────────────────────────────────────────────────────────────
    # Flujos
    # ─────────────────────────────────────────────────────────────────────

    def _crear_flujo_vacaciones(self, ct, users):
        flujo, created = FlujoTrabajo.objects.get_or_create(
            nombre=f'{MARCADOR_DEMO} Solicitud Vacaciones',
            defaults={
                'descripcion': 'Manager directo aprueba; RRHH valida y confirma.',
                'icono': 'fa-umbrella-beach',
                'content_type': ct,
                'campo_trigger': 'estado',
                'valor_trigger': 'PENDIENTE_DEMO',
                'campo_resultado': 'estado',
                'valor_aprobado': 'APROBADA',
                'valor_rechazado': 'RECHAZADA',
                'activo': True,
                'notificar_email': False,
            },
        )
        if created:
            EtapaFlujo.objects.create(
                flujo=flujo, orden=1, nombre='Aprobacion Manager',
                tipo_aprobador='USUARIO',
                aprobador_usuario=users['demo_manager'],
                tiempo_limite_horas=48,
                accion_vencimiento='ESPERAR',
            )
            EtapaFlujo.objects.create(
                flujo=flujo, orden=2, nombre='Confirmacion RRHH',
                tipo_aprobador='SUPERUSER',
                tiempo_limite_horas=24,
                accion_vencimiento='AUTO_APROBAR',
            )
            self.stdout.write(f'  [+] Flujo: {flujo.nombre}')
        return flujo

    def _crear_flujo_prestamo(self, ct, users):
        flujo, created = FlujoTrabajo.objects.get_or_create(
            nombre=f'{MARCADOR_DEMO} Prestamo > 1000',
            defaults={
                'descripcion': (
                    'Cadena de 3 niveles: manager directo, gerencia, y luego '
                    'finanzas valida la disponibilidad y desembolsa.'
                ),
                'icono': 'fa-hand-holding-usd',
                'content_type': ct,
                'campo_trigger': 'estado',
                'valor_trigger': 'PENDIENTE_DEMO',
                'campo_resultado': 'estado',
                'valor_aprobado': 'APROBADO',
                'valor_rechazado': 'RECHAZADO',
                'activo': True,
                'notificar_email': False,
            },
        )
        if created:
            EtapaFlujo.objects.create(
                flujo=flujo, orden=1, nombre='Manager',
                tipo_aprobador='USUARIO',
                aprobador_usuario=users['demo_manager'],
                tiempo_limite_horas=48,
                accion_vencimiento='ESPERAR',
            )
            EtapaFlujo.objects.create(
                flujo=flujo, orden=2, nombre='Gerencia',
                tipo_aprobador='GRUPO_DJANGO',
                aprobador_grupo=users['grupo_gerencia'],
                tiempo_limite_horas=72,
                accion_vencimiento='ESPERAR',
                requiere_comentario=True,
            )
            EtapaFlujo.objects.create(
                flujo=flujo, orden=3, nombre='Finanzas (desembolso)',
                tipo_aprobador='GRUPO_DJANGO',
                aprobador_grupo=users['grupo_finanzas'],
                tiempo_limite_horas=48,
                accion_vencimiento='ESPERAR',
            )
            self.stdout.write(f'  [+] Flujo: {flujo.nombre}')
        return flujo

    def _crear_flujo_viatico(self, ct, users):
        flujo, created = FlujoTrabajo.objects.get_or_create(
            nombre=f'{MARCADOR_DEMO} Reembolso Viatico',
            defaults={
                'descripcion': 'Jefe de area autoriza y contabilidad procesa.',
                'icono': 'fa-receipt',
                'content_type': ct,
                'campo_trigger': 'estado',
                'valor_trigger': 'PENDIENTE_DEMO',
                'campo_resultado': 'estado',
                'valor_aprobado': 'APROBADO',
                'valor_rechazado': 'RECHAZADO',
                'activo': True,
                'notificar_email': False,
            },
        )
        if created:
            EtapaFlujo.objects.create(
                flujo=flujo, orden=1, nombre='Jefe de Area',
                tipo_aprobador='USUARIO',
                aprobador_usuario=users['demo_manager'],
                tiempo_limite_horas=24,
                accion_vencimiento='AUTO_APROBAR',
            )
            EtapaFlujo.objects.create(
                flujo=flujo, orden=2, nombre='Contabilidad',
                tipo_aprobador='GRUPO_DJANGO',
                aprobador_grupo=users['grupo_finanzas'],
                tiempo_limite_horas=72,
                accion_vencimiento='ESPERAR',
                requiere_comentario=False,
            )
            self.stdout.write(f'  [+] Flujo: {flujo.nombre}')
        return flujo

    # ─────────────────────────────────────────────────────────────────────
    # Instancias mock
    # ─────────────────────────────────────────────────────────────────────

    def _crear_instancias_mock(self, f1, f2, f3, users):
        """Crea 5 instancias en distintos estados/pasos."""
        ahora = timezone.now()
        ct_self = ContentType.objects.get_for_model(FlujoTrabajo)
        creadas = []

        # 1) Vacaciones en etapa 1 (recien creada)
        inst, was_new = self._get_or_create_instancia(
            flujo=f1,
            slug='vacaciones_etapa1',
            solicitante=users['demo_solicit'],
            ct=ct_self,
            etapa=f1.etapas.get(orden=1),
            vence_offset=timedelta(hours=40),
            titulo='Vacaciones 15-25 Junio (Juan Perez)',
        )
        if was_new:
            self.stdout.write(f'  [+] Instancia: vacaciones etapa 1 (#{inst.pk})')
        creadas.append(inst)

        # 2) Vacaciones en etapa 2 (manager ya aprobo)
        inst, was_new = self._get_or_create_instancia(
            flujo=f1,
            slug='vacaciones_etapa2',
            solicitante=users['demo_solicit'],
            ct=ct_self,
            etapa=f1.etapas.get(orden=2),
            vence_offset=timedelta(hours=20),
            titulo='Vacaciones 1-10 Julio (Maria Lopez)',
            pasos_previos=[
                (f1.etapas.get(orden=1), users['demo_manager'], 'APROBADO',
                 'Visto bueno del manager directo'),
            ],
        )
        if was_new:
            self.stdout.write(f'  [+] Instancia: vacaciones etapa 2 (#{inst.pk})')
        creadas.append(inst)

        # 3) Prestamo en etapa 2 (gerencia revisando)
        inst, was_new = self._get_or_create_instancia(
            flujo=f2,
            slug='prestamo_etapa2',
            solicitante=users['demo_solicit'],
            ct=ct_self,
            etapa=f2.etapas.get(orden=2),
            vence_offset=timedelta(hours=60),
            titulo='Prestamo S/ 3,500 (12 cuotas)',
            pasos_previos=[
                (f2.etapas.get(orden=1), users['demo_manager'], 'APROBADO',
                 'Trabajador con historial limpio'),
            ],
        )
        if was_new:
            self.stdout.write(f'  [+] Instancia: prestamo etapa 2 (#{inst.pk})')
        creadas.append(inst)

        # 4) Prestamo VENCIDO en etapa 1 (urgente)
        inst, was_new = self._get_or_create_instancia(
            flujo=f2,
            slug='prestamo_vencido',
            solicitante=users['demo_solicit'],
            ct=ct_self,
            etapa=f2.etapas.get(orden=1),
            vence_offset=timedelta(hours=-5),    # ya vencio
            titulo='Prestamo S/ 1,800 (urgente — vencido)',
        )
        if was_new:
            self.stdout.write(f'  [+] Instancia: prestamo VENCIDO (#{inst.pk})')
        creadas.append(inst)

        # 5) Viatico en etapa 2 (contabilidad)
        inst, was_new = self._get_or_create_instancia(
            flujo=f3,
            slug='viatico_etapa2',
            solicitante=users['demo_solicit'],
            ct=ct_self,
            etapa=f3.etapas.get(orden=2),
            vence_offset=timedelta(hours=50),
            titulo='Viatico viaje Trujillo S/ 480',
            pasos_previos=[
                (f3.etapas.get(orden=1), users['demo_manager'], 'APROBADO',
                 'Viaje autorizado por gerencia comercial'),
            ],
        )
        if was_new:
            self.stdout.write(f'  [+] Instancia: viatico etapa 2 (#{inst.pk})')
        creadas.append(inst)

        return creadas

    def _get_or_create_instancia(self, *, flujo, slug, solicitante, ct, etapa,
                                 vence_offset, titulo, pasos_previos=None):
        """Idempotente — usa metadata.demo_slug como llave."""
        existente = InstanciaFlujo.objects.filter(
            flujo=flujo, metadata__demo_slug=slug,
        ).first()
        if existente:
            return existente, False

        ahora = timezone.now()
        inst = InstanciaFlujo.objects.create(
            flujo=flujo,
            content_type=ct,
            object_id=flujo.pk,    # placeholder: no hay objeto real en demo
            etapa_actual=etapa,
            estado='EN_PROCESO',
            solicitante=solicitante,
            etapa_vence_en=ahora + vence_offset,
            metadata={
                'demo': True,
                'demo_slug': slug,
                'titulo': titulo,
            },
        )
        for paso_etapa, paso_user, decision, comentario in (pasos_previos or []):
            PasoFlujo.objects.create(
                instancia=inst,
                etapa=paso_etapa,
                aprobador=paso_user,
                decision=decision,
                comentario=comentario,
            )
        return inst, True
