"""Pueblar datos demo para que el portal del trabajador no se vea vacío.

Crea:
- Saldos vacacionales + 1 solicitud aprobada pasada + 1 pendiente futura
- Préstamos: 1 en curso, 1 aprobado
- Capacitaciones: 1 finalizada (asistencia aprobada) + 1 próxima (inscritos)
- ArchivoHR: contrato + constancia
- ComunicadoMasivo: 2 + confirmación de lectura
- Notificaciones: 2 por trabajador
- AsignacionViatico: 1 rendido

Workers afectados: Hans (71445678) + Yessica (73000005) + 5 más para variedad.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Pueblar datos demo para portal del trabajador (Hans + Yessica + EDO sample)"

    def handle(self, *args, **kw):
        from personal.models import Personal
        from vacaciones.models import SolicitudVacacion, SaldoVacacional
        from prestamos.models import Prestamo, TipoPrestamo
        from capacitaciones.models import (
            Capacitacion, AsistenciaCapacitacion, CategoriaCapacitacion,
        )
        from documentos.models import ArchivoHR
        from comunicaciones.models import (
            ComunicadoMasivo, ConfirmacionLectura, Notificacion,
        )
        from viaticos.models import AsignacionViatico

        today = date.today()

        target_dnis = [
            '71445678', '73000005', '73000002', '73000004',
            '73000006', '73000011', '73000012',
        ]
        # Cargar en el ORDEN de target_dnis (Hans primero, Yessica segundo)
        # para que las personalizaciones (workers[0]=Hans, workers[1]=Yessica)
        # coincidan con la intención de la demo.
        by_dni = {p.nro_doc: p for p in Personal.objects.filter(nro_doc__in=target_dnis)}
        workers = [by_dni[d] for d in target_dnis if d in by_dni]
        self.stdout.write(f"Pueblando {len(workers)} trabajadores")
        for i, w in enumerate(workers):
            self.stdout.write(f"  [{i}] {w.apellidos_nombres} (DNI {w.nro_doc})")

        # ===== Vacaciones =====
        for w in workers:
            SaldoVacacional.objects.update_or_create(
                personal=w,
                periodo_inicio=date(today.year, 1, 1),
                defaults=dict(
                    periodo_fin=date(today.year, 12, 31),
                    dias_derecho=30, dias_gozados=7, dias_vendidos=0,
                    dias_pendientes=23, dias_truncos=Decimal('0'),
                    estado='PARCIAL',
                ),
            )
            SaldoVacacional.objects.update_or_create(
                personal=w,
                periodo_inicio=date(today.year - 1, 1, 1),
                defaults=dict(
                    periodo_fin=date(today.year - 1, 12, 31),
                    dias_derecho=30, dias_gozados=30, dias_vendidos=0,
                    dias_pendientes=0, dias_truncos=Decimal('0'),
                    estado='GOZADO',
                ),
            )
            f_ini = today - timedelta(days=90)
            f_fin = f_ini + timedelta(days=6)
            SolicitudVacacion.objects.get_or_create(
                personal=w, fecha_inicio=f_ini,
                defaults=dict(
                    fecha_fin=f_fin, dias_calendario=7, dias_habiles=5,
                    motivo='Vacaciones familiares.', estado='APROBADA',
                    fecha_aprobacion=f_ini - timedelta(days=15),
                ),
            )

        # Solicitud pendiente futura solo para los 2 primeros (Hans, Yessica)
        for w in workers[:2]:
            f_ini = today + timedelta(days=20)
            f_fin = f_ini + timedelta(days=4)
            SolicitudVacacion.objects.get_or_create(
                personal=w, fecha_inicio=f_ini,
                defaults=dict(
                    fecha_fin=f_fin, dias_calendario=5, dias_habiles=4,
                    motivo='Descanso programado.', estado='PENDIENTE',
                ),
            )
        self.stdout.write("  [OK] Vacaciones")

        # ===== Préstamos =====
        tipo_adelanto = TipoPrestamo.objects.filter(
            nombre__icontains='Adelanto de Sueldo'
        ).first()
        tipo_personal = TipoPrestamo.objects.filter(
            nombre__icontains='Personal'
        ).first()

        if tipo_personal and len(workers) >= 1:
            Prestamo.objects.get_or_create(
                personal=workers[0], tipo=tipo_personal,
                fecha_solicitud=today - timedelta(days=60),
                defaults=dict(
                    monto_solicitado=Decimal('2000.00'),
                    monto_aprobado=Decimal('2000.00'),
                    num_cuotas=6, cuota_mensual=Decimal('333.34'),
                    tasa_interes=Decimal('0.00'),
                    fecha_aprobacion=today - timedelta(days=58),
                    fecha_primer_descuento=today - timedelta(days=30),
                    estado='EN_CURSO',
                    motivo='Reparación de moto para llegar al trabajo.',
                ),
            )
        if tipo_adelanto and len(workers) >= 2:
            Prestamo.objects.get_or_create(
                personal=workers[1], tipo=tipo_adelanto,
                fecha_solicitud=today - timedelta(days=5),
                defaults=dict(
                    monto_solicitado=Decimal('500.00'),
                    monto_aprobado=Decimal('500.00'),
                    num_cuotas=1, cuota_mensual=Decimal('500.00'),
                    tasa_interes=Decimal('0.00'),
                    fecha_aprobacion=today - timedelta(days=4),
                    estado='APROBADO', motivo='Gastos imprevistos.',
                ),
            )
        self.stdout.write("  [OK] Prestamos")

        # ===== Capacitaciones =====
        cat_ssoma = CategoriaCapacitacion.objects.filter(
            nombre__icontains='SSOMA'
        ).first()
        cat_servicio = CategoriaCapacitacion.objects.filter(
            nombre__icontains='Servicio'
        ).first()

        cap1, _ = Capacitacion.objects.get_or_create(
            titulo='Manipulacion de Alimentos - Renovacion Anual',
            defaults=dict(
                descripcion='Curso obligatorio DIGESA para personal de cocina.',
                categoria=cat_ssoma, tipo='SSOMA',
                instructor='Lic. Patricia Mendoza',
                lugar='Aula Central EDO',
                fecha_inicio=today - timedelta(days=15),
                fecha_fin=today - timedelta(days=15),
                horas=Decimal('8.00'), costo=Decimal('150.00'),
                max_participantes=30, estado='COMPLETADA',
                obligatoria=True,
            ),
        )
        cap2, _ = Capacitacion.objects.get_or_create(
            titulo='Excelencia en Servicio al Cliente',
            defaults=dict(
                descripcion='Tecnicas de atencion al cliente.',
                categoria=cat_servicio, tipo='ELEARNING',
                instructor='Mg. Roberto Vargas',
                lugar='Plataforma virtual',
                fecha_inicio=today + timedelta(days=10),
                fecha_fin=today + timedelta(days=11),
                horas=Decimal('6.00'), costo=Decimal('80.00'),
                max_participantes=50, estado='PROGRAMADA',
                obligatoria=False,
            ),
        )

        for w in workers:
            AsistenciaCapacitacion.objects.get_or_create(
                capacitacion=cap1, personal=w,
                defaults=dict(
                    estado='ASISTIO',
                    nota=Decimal('17.0'), aprobado=True,
                ),
            )
        for w in workers[:4]:
            AsistenciaCapacitacion.objects.get_or_create(
                capacitacion=cap2, personal=w,
                defaults=dict(estado='INSCRITO', aprobado=False),
            )
        self.stdout.write("  [OK] Capacitaciones")

        # ===== ArchivoHR =====
        for w in workers:
            for nombre, periodo in [
                ('Contrato Indefinido', ''),
                ('Constancia de Trabajo', today.strftime('%Y-%m')),
            ]:
                if not ArchivoHR.objects.filter(
                    personal=w, nombre=nombre
                ).exists():
                    archivo = ArchivoHR(
                        personal=w, nombre=nombre,
                        descripcion=f'{nombre} - documento oficial.',
                        periodo=periodo, visible=True,
                    )
                    archivo.archivo.save(
                        f"{w.nro_doc}_{nombre.lower().replace(' ', '_')}.txt",
                        ContentFile(
                            (f"Documento: {nombre}\n"
                             f"Trabajador: {w.apellidos_nombres}\n"
                             f"Empresa: {w.empresa.razon_social if w.empresa else 'N/A'}\n"
                             f"Fecha: {today}\n").encode()
                        ),
                        save=True,
                    )
        self.stdout.write("  [OK] ArchivoHR")

        # ===== DocumentosLaborales (lo que muestra /documentos/laborales/mis/) =====
        from documentos.models import DocumentoLaboral, EntregaDocumento
        docs_specs = [
            dict(
                titulo='Reglamento Interno de Trabajo 2026',
                tipo='REGLAMENTO',
                descripcion=(
                    'Reglamento Interno de Trabajo - vigente desde enero 2026. '
                    'Lectura obligatoria para todo el personal.'
                ),
                requiere_confirmacion=True,
            ),
            dict(
                titulo='Politica de Seguridad e Higiene Alimentaria',
                tipo='SST',
                descripcion=(
                    'Politica DIGESA + HACCP. Define lineamientos y '
                    'responsabilidades para personal de cocina y servicio.'
                ),
                requiere_confirmacion=True,
            ),
            dict(
                titulo='Memo: Actualizacion uniforme corporativo',
                tipo='MEMO',
                descripcion=(
                    'Comunicacion sobre el nuevo diseño del uniforme y '
                    'protocolo de presentacion.'
                ),
                requiere_confirmacion=False,
            ),
        ]

        for spec in docs_specs:
            doc, created = DocumentoLaboral.objects.get_or_create(
                titulo=spec['titulo'],
                defaults=dict(
                    tipo=spec['tipo'],
                    descripcion=spec['descripcion'],
                    destinatarios_tipo='TODOS',
                    estado='PUBLICADO',
                    requiere_confirmacion=spec['requiere_confirmacion'],
                    fecha_publicacion=timezone.now() - timedelta(days=20),
                    contenido_html=(
                        f"<h3>{spec['titulo']}</h3>"
                        f"<p>{spec['descripcion']}</p>"
                        "<p>Documento oficial - Grupo EDO 2026.</p>"
                    ),
                ),
            )
            for w in workers:
                EntregaDocumento.objects.get_or_create(
                    documento=doc, personal=w,
                )
        # Hans confirma los 2 que requieren confirmacion (para mostrar trail)
        for doc in DocumentoLaboral.objects.filter(
            titulo__in=[s['titulo'] for s in docs_specs[:2]]
        ):
            for w in workers[:1]:
                e = EntregaDocumento.objects.filter(
                    documento=doc, personal=w,
                ).first()
                if e and not e.confirmado:
                    e.confirmado = True
                    e.fecha_confirmacion = timezone.now() - timedelta(days=15)
                    e.save()
        self.stdout.write("  [OK] DocumentosLaborales")

        # ===== Comunicados =====
        com1, _ = ComunicadoMasivo.objects.get_or_create(
            titulo='Politica de Vacaciones 2026 - Importante',
            defaults=dict(
                cuerpo=(
                    'Estimados colaboradores:\n\n'
                    'Comunicamos la nueva politica de programacion de '
                    'vacaciones para el periodo 2026. Las solicitudes '
                    'deberan presentarse con 15 dias de anticipacion a '
                    'traves del portal del trabajador.\n\n'
                    'Saludos,\nGerencia de Recursos Humanos'
                ),
                tipo='POLITICA', estado='ENVIADO',
                destinatarios_tipo='TODOS', requiere_confirmacion=True,
                enviado_en=timezone.now() - timedelta(days=10),
            ),
        )
        com2, _ = ComunicadoMasivo.objects.get_or_create(
            titulo='Brindis fin de ano - Confirmar asistencia',
            defaults=dict(
                cuerpo=(
                    'Tenemos el agrado de invitarlos al brindis anual EDO. '
                    'Lugar: Restaurante Costanera. '
                    'Fecha: 20 diciembre 19:00 hrs.'
                ),
                tipo='EVENTO', estado='ENVIADO',
                destinatarios_tipo='TODOS', requiere_confirmacion=False,
                enviado_en=timezone.now() - timedelta(days=3),
            ),
        )
        for w in workers[:4]:
            ConfirmacionLectura.objects.get_or_create(
                comunicado=com1, personal=w,
            )
        self.stdout.write("  [OK] Comunicados")

        # ===== Notificaciones =====
        # destinatario es FK a Personal (no User).
        for w in workers[:2]:
            Notificacion.objects.get_or_create(
                destinatario=w,
                asunto='Tu boleta de mayo ya esta disponible',
                defaults=dict(
                    cuerpo=(
                        'Hola, tu boleta del periodo de mayo esta '
                        'disponible en el portal. Recuerda confirmar '
                        'la recepcion.'
                    ),
                    tipo='IN_APP', estado='ENVIADA',
                    enviada_en=timezone.now() - timedelta(days=2),
                ),
            )
            Notificacion.objects.get_or_create(
                destinatario=w,
                asunto='Curso de manipulacion de alimentos confirmado',
                defaults=dict(
                    cuerpo=(
                        'Quedaste inscrito en el curso obligatorio '
                        'DIGESA. Fecha: proximo viernes 9:00 am.'
                    ),
                    tipo='IN_APP', estado='ENVIADA',
                    enviada_en=timezone.now() - timedelta(days=5),
                ),
            )
        self.stdout.write("  [OK] Notificaciones")

        # ===== Viaticos =====
        if workers:
            AsignacionViatico.objects.get_or_create(
                personal=workers[0],
                periodo=date(today.year, today.month, 1),
                defaults=dict(
                    monto_asignado=Decimal('300.00'),
                    monto_adicional=Decimal('0'),
                    ubicacion='Trujillo - apertura sucursal',
                    dias_campo=3, estado='CONCILIADO',
                    fecha_entrega=today - timedelta(days=20),
                    monto_rendido=Decimal('285.50'),
                    monto_devuelto=Decimal('14.50'),
                    monto_reembolso=Decimal('0'),
                ),
            )
        self.stdout.write("  [OK] Viaticos")
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            "Seed portal demo completado"
        ))
