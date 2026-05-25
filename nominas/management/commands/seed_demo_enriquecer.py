"""
Enriquece el demo con datos que NO genera `seed_demo_historico`:
- Contratos para todos los trabajadores (vigentes + vencidos + algunos por vencer en 30 días para alertas dashboard)
- Más solicitudes de vacaciones (Pendiente/Aprobado/Rechazado mix)
- Más préstamos con variedad de estados
- Capacitaciones realistas para gastronomía

Idempotente: no recrea registros existentes. Pensado para correr en `reset_demo.sh`
después de `seed_demo_historico`.

Uso:
    python manage.py seed_demo_enriquecer
"""
import random
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction


CAPACITACIONES_GASTRO = [
    ('Manipulación de alimentos DIGESA', 'Obligatoria — renovación anual. Resolución DIGESA D-Nº 071-2020.', 8),
    ('Primeros auxilios básicos', 'Defensa civil — todo el personal de salón debe tenerlo.', 6),
    ('Servicio al cliente excepcional', 'Mozos y hostess — técnicas avanzadas de upselling y atención.', 12),
    ('Coctelería avanzada', 'Bartenders — nueva carta de bebidas y técnicas de mixología.', 16),
    ('Liderazgo para supervisores', 'Capataces y administradores de local — soft skills.', 20),
    ('Gestión de stock y mermas', 'Cocineros senior y administradores — reducir desperdicio.', 8),
    ('Inducción de nuevos ingresos', 'Onboarding general — primera semana en empresa.', 4),
]


class Command(BaseCommand):
    help = 'Enriquece demo con contratos, vacaciones extras, préstamos, capacitaciones.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--seed', type=int, default=42)

    @transaction.atomic
    def handle(self, *args, **opts):
        random.seed(opts['seed'])
        self.dry = opts['dry_run']
        hoy = date.today()

        self.stdout.write('\n=== Seed Demo Enriquecer ===\n')

        contratos = self._sembrar_contratos(hoy)
        self.stdout.write(f'  Contratos creados:       {contratos}')

        vacaciones = self._sembrar_vacaciones(hoy)
        self.stdout.write(f'  Vacaciones creadas:      {vacaciones}')

        prestamos = self._sembrar_prestamos(hoy)
        self.stdout.write(f'  Préstamos creados:       {prestamos}')

        capacitaciones = self._sembrar_capacitaciones(hoy)
        self.stdout.write(f'  Capacitaciones creadas:  {capacitaciones}')

        liquidaciones = self._sembrar_liquidaciones(hoy)
        self.stdout.write(f'  Liquidaciones creadas:   {liquidaciones}')

        notifs = self._sembrar_notificaciones(hoy)
        self.stdout.write(f'  Notificaciones creadas:  {notifs}')

        if self.dry:
            self.stdout.write(self.style.WARNING('\n  [DRY-RUN] Rollback — no se persistieron cambios.\n'))
            raise transaction.TransactionManagementError('rollback dry-run')

        self.stdout.write(self.style.SUCCESS('\nSeed enriquecer: OK\n'))

    # ─────────────────────────────────────────────────────────
    def _sembrar_contratos(self, hoy):
        from personal.models import Personal, Contrato
        TIPOS = ['INDEFINIDO', 'INDEFINIDO', 'PLAZO_FIJO', 'PERIODO_PRUEBA']
        creados = 0
        n_count = Contrato.objects.count()

        # Para activos
        for p in Personal.objects.filter(estado='Activo'):
            if Contrato.objects.filter(personal=p).exists():
                continue
            n_count += 1
            fecha_inicio = p.fecha_alta or (hoy - timedelta(days=random.randint(180, 1800)))
            tipo = random.choice(TIPOS)
            if tipo == 'INDEFINIDO':
                fecha_fin = fecha_inicio + timedelta(days=365 * 10)
            elif tipo == 'PLAZO_FIJO':
                fecha_fin = fecha_inicio + timedelta(days=random.choice([180, 365, 730]))
            else:
                fecha_fin = fecha_inicio + timedelta(days=90)
            cargo_t = self._cargo_texto(p)
            try:
                Contrato.objects.create(
                    personal=p,
                    tipo_contrato=tipo,
                    numero_contrato=f'C-{hoy.year}-{n_count:04d}',
                    fecha_inicio=fecha_inicio,
                    fecha_fin=fecha_fin,
                    estado='VIGENTE' if fecha_fin >= hoy else 'VENCIDO',
                    sueldo_pactado=p.sueldo_base or 1500,
                    cargo_contrato=cargo_t,
                    jornada_semanal=48,
                    renovacion_automatica=(tipo == 'PLAZO_FIJO'),
                )
                creados += 1
            except Exception:
                continue

        # Forzar ~5 contratos a vencer en próximos 30 días (para alertas dashboard)
        vigentes = list(Contrato.objects.filter(estado='VIGENTE', tipo_contrato='INDEFINIDO').order_by('?')[:5])
        for i, c in enumerate(vigentes):
            c.fecha_fin = hoy + timedelta(days=[5, 12, 18, 25, 28][i])
            c.tipo_contrato = 'PLAZO_FIJO'
            c.save()

        # Para cesados
        for p in Personal.objects.exclude(estado='Activo'):
            if Contrato.objects.filter(personal=p).exists():
                continue
            n_count += 1
            fecha_inicio = p.fecha_alta or (hoy - timedelta(days=random.randint(365, 1800)))
            try:
                Contrato.objects.create(
                    personal=p,
                    tipo_contrato='INDEFINIDO',
                    numero_contrato=f'C-{hoy.year}-{n_count:04d}',
                    fecha_inicio=fecha_inicio,
                    fecha_fin=p.fecha_cese or hoy,
                    estado='TERMINADO',
                    sueldo_pactado=p.sueldo_base or 1500,
                    cargo_contrato=self._cargo_texto(p),
                    jornada_semanal=48,
                )
                creados += 1
            except Exception:
                continue

        return creados

    def _sembrar_vacaciones(self, hoy):
        from personal.models import Personal
        from vacaciones.models import SolicitudVacacion
        estados = ['PENDIENTE', 'APROBADO', 'APROBADO', 'APROBADO', 'RECHAZADO']
        motivos = ['Vacaciones programadas', 'Descanso anual', 'Viaje familiar',
                   'Tiempo personal', 'Permiso aprobado']
        creados = 0
        for p in Personal.objects.filter(estado='Activo').order_by('?')[:30]:
            if SolicitudVacacion.objects.filter(personal=p).count() >= 1:
                continue
            if random.random() > 0.5:
                continue
            fi = hoy + timedelta(days=random.randint(-60, 60))
            dias = random.choice([7, 10, 14, 15, 21])
            try:
                SolicitudVacacion.objects.create(
                    personal=p,
                    fecha_inicio=fi,
                    fecha_fin=fi + timedelta(days=dias),
                    dias_calendario=dias,
                    dias_habiles=int(dias * 5 / 7),
                    motivo=random.choice(motivos),
                    estado=random.choice(estados),
                )
                creados += 1
            except Exception:
                pass
        return creados

    def _sembrar_prestamos(self, hoy):
        from personal.models import Personal
        from prestamos.models import Prestamo, TipoPrestamo
        tipo = TipoPrestamo.objects.first() or TipoPrestamo.objects.create(
            nombre='Préstamo personal', codigo='PERSONAL'
        )
        estados = ['SOLICITADO', 'APROBADO', 'EN_CURSO', 'EN_CURSO', 'PAGADO']
        motivos = ['Emergencia médica', 'Estudios hijos', 'Reparación vehículo',
                   'Mudanza', 'Útiles escolares']
        creados = 0
        for p in Personal.objects.filter(estado='Activo').order_by('?')[:20]:
            if Prestamo.objects.filter(personal=p).exists():
                continue
            monto = random.choice([500, 1000, 1500, 2000, 3000, 5000])
            n = random.choice([3, 6, 12])
            try:
                Prestamo.objects.create(
                    personal=p,
                    tipo=tipo,
                    monto_solicitado=monto,
                    monto_aprobado=monto,
                    num_cuotas=n,
                    cuota_mensual=monto / n,
                    estado=random.choice(estados),
                    motivo=random.choice(motivos),
                    fecha_solicitud=hoy - timedelta(days=random.randint(15, 365)),
                )
                creados += 1
            except Exception:
                pass
        return creados

    def _sembrar_capacitaciones(self, hoy):
        from capacitaciones.models import Capacitacion
        creados = 0
        for titulo, desc, horas in CAPACITACIONES_GASTRO:
            fecha = hoy + timedelta(days=random.randint(-90, 60))
            estado = 'PROGRAMADA' if fecha > hoy else random.choice(['EN_CURSO', 'COMPLETADA', 'COMPLETADA'])
            try:
                _, created = Capacitacion.objects.get_or_create(
                    titulo=titulo,
                    defaults={
                        'descripcion': desc,
                        'horas': horas,
                        'estado': estado,
                        'fecha_inicio': fecha,
                        'fecha_fin': fecha + timedelta(days=1),
                        'tipo': 'INTERNA',
                        'obligatoria': True,
                    },
                )
                if created:
                    creados += 1
            except Exception:
                pass
        return creados

    def _sembrar_liquidaciones(self, hoy):
        """Crea LiquidacionLaboral para los cesados (con cálculo automático)."""
        from personal.models import Personal
        try:
            from nominas.models import LiquidacionLaboral
        except ImportError:
            return 0
        motivos = ['RENUNCIA', 'DESPIDO_ARB', 'MUTUO', 'CADUCIDAD', 'JUBILACION']
        creados = 0
        for i, p in enumerate(Personal.objects.filter(estado='Cesado', fecha_cese__isnull=False)[:8]):
            if LiquidacionLaboral.objects.filter(personal=p).exists():
                continue
            try:
                ll = LiquidacionLaboral.objects.create(
                    personal=p,
                    fecha_cese=p.fecha_cese,
                    motivo_cese=motivos[i % len(motivos)],
                )
                try:
                    ll.calcular()
                except Exception:
                    pass  # cálculo puede fallar si faltan datos pero LL queda creado
                creados += 1
            except Exception:
                pass
        return creados

    def _sembrar_notificaciones(self, hoy):
        """8 notificaciones realistas para usuario demo."""
        from personal.models import Personal
        try:
            from comunicaciones.models import Notificacion
        except ImportError:
            return 0
        # Personal demo (admin tiene Personal asociado via primer activo)
        p_demo = Personal.objects.filter(estado='Activo').first()
        if not p_demo:
            return 0
        if Notificacion.objects.filter(destinatario=p_demo).count() >= 5:
            return 0  # idempotente
        notifs_data = [
            ('Contratos por vencer', '6 contratos vencen en próximos 30 días — revisar renovaciones'),
            ('Vacaciones pendientes', '8 solicitudes de vacaciones esperan tu aprobación'),
            ('Liquidación calculada', 'Liquidación lista para revisar — S/ 4,215.97'),
            ('Cierre planilla Mayo', 'Falta aprobar período REGULAR — 11 pasos restantes'),
            ('DIGESA vence', '12 trabajadores requieren renovar capacitación en 15 días'),
            ('Postulantes top', '3 nuevos candidatos para Chef Ejecutivo Senior'),
            ('Alerta Pulse', 'Sabores del Sur Vinos: pulse bajó a 6.2/10'),
            ('Workflow Offboarding', '3 procesos de cese activos esperan tu acción'),
        ]
        creados = 0
        for asunto, cuerpo in notifs_data:
            try:
                Notificacion.objects.create(
                    destinatario=p_demo,
                    destinatario_email='demo@demo.com',
                    asunto=asunto, cuerpo=cuerpo,
                    tipo='SYSTEM', estado='ENVIADA',
                )
                creados += 1
            except Exception:
                pass
        return creados

    @staticmethod
    def _cargo_texto(p):
        if isinstance(p.cargo, str):
            return p.cargo
        if p.cargo:
            return getattr(p.cargo, 'nombre', str(p.cargo))
        return 'Operativo'
