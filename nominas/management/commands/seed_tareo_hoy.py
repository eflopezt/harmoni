"""
Genera RegistroTareo de HOY para los trabajadores activos, con un patrón
present-heavy, para que el dashboard de la demo nunca se vea vacío (KPIs
"Presentes / Faltas / Permisos" en 0).

`seed_asistencia_demo` siembra el mes PERO se detiene en ayer (fin = hoy - 1),
así que el día en curso queda sin tareo y los KPIs de hoy salen en 0. Este
comando llena específicamente HOY, siempre como día laborable (aunque caiga fin
de semana), para que la demo se vea activa cualquier día.

Distribución: ~84% presente (T) · ~6% presente sin salida (SS) · ~5% falta (FA)
· ~5% permiso (V). Idempotente: salta los (personal, hoy) que ya existan.

Pensado para DEMO/seed. Inofensivo en prod (solo crea tareo de hoy si falta),
pero su uso natural es la demo vía reset_demo.sh.

Uso:
    python manage.py seed_tareo_hoy
"""
from datetime import date, time
from decimal import Decimal
import random

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Siembra el tareo de HOY (present-heavy) para que la demo no se vea vacía"

    def add_arguments(self, parser):
        parser.add_argument('--seed', type=int, default=789,
                            help='Random seed para reproducibilidad.')

    def handle(self, *args, **opts):
        from personal.models import Personal
        from asistencia.models import RegistroTareo, TareoImportacion
        from django.utils import timezone

        random.seed(opts['seed'])
        hoy = date.today()

        imp, _ = TareoImportacion.objects.get_or_create(
            archivo_nombre='seed_tareo_hoy.xlsx',
            periodo_inicio=hoy,
            defaults=dict(
                tipo='RELOJ', periodo_fin=hoy, estado='PROCESADO',
                total_registros=0, registros_ok=0, registros_error=0,
                registros_sin_match=0, errores=[], advertencias=[],
                metadata={'source': 'seed_tareo_hoy'},
                procesado_en=timezone.now(),
            ),
        )

        workers = Personal.objects.filter(estado='Activo')
        nuevos = 0
        for p in workers:
            if RegistroTareo.objects.filter(personal=p, fecha=hoy).exists():
                continue

            r = random.random()
            if r < 0.05:
                codigo, h_e, h_s = 'FA', None, None
                h_ef = h_n = Decimal('0')
            elif r < 0.10:
                codigo, h_e, h_s = 'V', None, None       # permiso/vacaciones
                h_ef = h_n = Decimal('0')
            elif r < 0.16:
                codigo, h_e, h_s = 'SS', None, None       # presente, sin marcar salida
                h_ef = h_n = Decimal('0')
            else:
                codigo = 'T'
                ent_min = 480 + random.randint(-15, 15)   # ~08:00
                h_e = time(ent_min // 60, ent_min % 60)
                sal_min = 1020 + random.randint(-15, 60)  # ~17:00
                h_s = time(sal_min // 60, sal_min % 60)
                h_ef = Decimal(f"{(sal_min - ent_min - 60) / 60.0:.2f}")
                h_n = Decimal('8.00')

            RegistroTareo.objects.create(
                importacion=imp,
                personal=p,
                fecha=hoy,
                dni=p.nro_doc,
                grupo=p.grupo_tareo or 'STAFF',
                condicion=p.tipo_trab or 'EMPLEADO',
                dia_semana=hoy.weekday(),
                es_feriado=False,
                codigo_dia=codigo,
                fuente_codigo='RELOJ' if codigo == 'T' else 'SISTEMA',
                hora_entrada_real=h_e,
                hora_salida_real=h_s,
                horas_efectivas=h_ef,
                horas_normales=h_n,
                he_25=Decimal('0'), he_35=Decimal('0'), he_100=Decimal('0'),
                he_al_banco=False,
                almuerzo_manual=Decimal('1.00') if codigo == 'T' else Decimal('0'),
                horas_marcadas=(h_ef + Decimal('1.00')) if codigo == 'T' else Decimal('0'),
                valor_reloj_raw=(f"{h_e.strftime('%H%M')}/{h_s.strftime('%H%M')}"
                                 if h_e else ''),
                nombre_archivo='seed_tareo_hoy',
                papeleta_ref='', observaciones='',
            )
            nuevos += 1

        total_imp = RegistroTareo.objects.filter(importacion=imp).count()
        imp.total_registros = total_imp
        imp.registros_ok = total_imp
        imp.save()

        self.stdout.write(self.style.SUCCESS(
            f"Tareo de HOY ({hoy}) sembrado: {nuevos} nuevos "
            f"de {workers.count()} activos."))
