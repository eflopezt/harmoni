"""
Seed: Consentimiento boleta electrónica para workers demo.

DS 009-2011-TR exige consentimiento previo escrito del trabajador
para recibir boletas por medio electrónico. Para el demo, aceptamos
el consentimiento por algunos workers (incluyendo Hans y Yessica) para
no tener que hacer el flow manualmente cada vez.

Idempotente: si ya existe consentimiento, lo actualiza.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


# DNIs de trabajadores demo que ya aceptaron consentimiento
TARGET_DNIS = [
    '71445678',  # Hans
    '73000005',  # Yessica
    '73000002', '73000004', '73000006', '73000011', '73000012',
]


class Command(BaseCommand):
    help = 'Acepta consentimiento boleta electrónica para workers demo'

    def handle(self, *args, **kw):
        from personal.models import Personal
        from documentos.models import ConsentimientoBoletaElectronica

        workers = list(Personal.objects.filter(nro_doc__in=TARGET_DNIS))
        self.stdout.write(f'Aceptando consentimiento para {len(workers)} workers')

        creados, actualizados = 0, 0
        for w in workers:
            consent, created = ConsentimientoBoletaElectronica.objects.update_or_create(
                personal=w,
                defaults=dict(
                    aceptado=True,
                    fecha_aceptacion=timezone.now() - timedelta(days=30),
                    ip_aceptacion='192.168.1.10',
                    user_agent='Mozilla/5.0 demo',
                    aviso_version=ConsentimientoBoletaElectronica.AVISO_VERSION_ACTUAL,
                    revocado=False,
                ),
            )
            if created:
                creados += 1
            else:
                actualizados += 1
            self.stdout.write(f'  {w.apellidos_nombres[:50]}')

        self.stdout.write(self.style.SUCCESS(
            f'Listo. Creados: {creados}, actualizados: {actualizados}'
        ))
