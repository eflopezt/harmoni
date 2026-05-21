"""
Genera RegistroTareo diario para todos los workers activos del mes en curso.

Patrón realista:
- Lunes a viernes: trabajado (codigo T), 8h normales + 0-1h extras esporádicas
- Sábado y domingo: descanso legal (DL)
- 2% de probabilidad de falta (FA) en días laborables
- 2% de probabilidad de SS (sin sustento / permiso)
- Hora entrada: 8:00 ± 15min, salida: 17:00 ± 30min
- Almuerzo: 1h
- Idempotente: skip si ya existe RegistroTareo para (personal, fecha)
"""
from datetime import date, timedelta, time
from decimal import Decimal
import random

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Seed asistencia diaria del mes para workers activos (idempotente)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--seed', type=int, default=456,
            help='Random seed para reproducibilidad.',
        )

    def handle(self, *args, **opts):
        from personal.models import Personal
        from asistencia.models import RegistroTareo, TareoImportacion
        from django.utils import timezone

        random.seed(opts['seed'])
        hoy = date.today()
        inicio_mes = date(hoy.year, hoy.month, 1)
        fin = hoy - timedelta(days=1) if hoy.day > 1 else hoy
        dias = (fin - inicio_mes).days + 1

        imp, created = TareoImportacion.objects.get_or_create(
            archivo_nombre='seed_demo_diario.xlsx',
            periodo_inicio=inicio_mes,
            defaults=dict(
                tipo='RELOJ',
                periodo_fin=fin,
                estado='PROCESADO',
                total_registros=0,
                registros_ok=0,
                registros_error=0,
                registros_sin_match=0,
                errores=[],
                advertencias=[],
                metadata={'source': 'seed_asistencia_demo'},
                procesado_en=timezone.now(),
            ),
        )
        self.stdout.write(
            f"TareoImportacion id={imp.id} "
            f"({'creado' if created else 'existente'})"
        )

        workers = Personal.objects.filter(estado='Activo')
        self.stdout.write(
            f"Generando asistencia para {workers.count()} workers, "
            f"{dias} días ({inicio_mes} -> {fin})"
        )

        nuevos = 0
        for p in workers:
            grupo = p.grupo_tareo or 'STAFF'
            for i in range(dias):
                f = inicio_mes + timedelta(days=i)
                if RegistroTareo.objects.filter(personal=p, fecha=f).exists():
                    continue

                dia_sem = f.weekday()
                if dia_sem >= 5:
                    codigo = 'DL'
                    h_e = h_s = None
                    h_ef = h_n = Decimal('0')
                else:
                    r = random.random()
                    if r < 0.02:
                        codigo = 'FA'
                        h_e = h_s = None
                        h_ef = h_n = Decimal('0')
                    elif r < 0.04:
                        codigo = 'SS'
                        h_e = h_s = None
                        h_ef = h_n = Decimal('0')
                    else:
                        codigo = 'T'
                        ent_min = 480 + random.randint(-15, 15)
                        h_e = time(ent_min // 60, ent_min % 60)
                        sal_min = 1020 + random.randint(-15, 60)
                        h_s = time(sal_min // 60, sal_min % 60)
                        h_ef = Decimal(
                            f"{(sal_min - ent_min - 60) / 60.0:.2f}"
                        )
                        h_n = Decimal('8.00')

                RegistroTareo.objects.create(
                    importacion=imp,
                    personal=p,
                    fecha=f,
                    dni=p.nro_doc,
                    grupo=grupo,
                    condicion=p.tipo_trab or 'EMPLEADO',
                    dia_semana=dia_sem,
                    es_feriado=False,
                    codigo_dia=codigo,
                    fuente_codigo='RELOJ' if codigo == 'T' else 'SISTEMA',
                    hora_entrada_real=h_e,
                    hora_salida_real=h_s,
                    horas_efectivas=h_ef,
                    horas_normales=h_n,
                    he_25=Decimal('0'),
                    he_35=Decimal('0'),
                    he_100=Decimal('0'),
                    he_al_banco=False,
                    almuerzo_manual=Decimal('1.00') if codigo == 'T' else Decimal('0'),
                    horas_marcadas=(h_ef + Decimal('1.00')) if codigo == 'T' else Decimal('0'),
                    valor_reloj_raw=(
                        f"{h_e.strftime('%H%M')}/{h_s.strftime('%H%M')}"
                        if h_e else ''
                    ),
                    nombre_archivo='seed_demo',
                    papeleta_ref='',
                    observaciones='',
                )
                nuevos += 1

        # Actualizar contadores
        total_imp = RegistroTareo.objects.filter(importacion=imp).count()
        imp.total_registros = total_imp
        imp.registros_ok = total_imp
        imp.save()

        self.stdout.write(self.style.SUCCESS(
            f"Total RegistroTareo nuevos: {nuevos} "
            f"(total en mes: {RegistroTareo.objects.filter(fecha__gte=inicio_mes).count()})"
        ))
