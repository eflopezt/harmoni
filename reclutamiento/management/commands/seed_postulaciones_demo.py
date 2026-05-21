"""
Seed: postulaciones demo distribuidas en el pipeline.

Crea ~25 postulaciones con datos realistas (CV parseado simulado),
distribuidas entre vacantes activas y etapas del pipeline.
"""
import random
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from reclutamiento.models import Vacante, Postulacion, EtapaPipeline


CANDIDATOS_DEMO = [
    # (nombre, email, telefono, exp_anios, skills, idiomas, score_base)
    ('MARIA QUISPE LOPEZ',          'maria.quispe@gmail.com',    '987111222', 5,
     ['atencion al cliente', 'cata de vinos', 'protocolo de servicio', 'caja'],
     ['ingles intermedio'], 75),
    ('CARLOS RAMIREZ TORRES',       'carlos.ramirez@hotmail.com','998222333', 8,
     ['cocina_caliente', 'parrilla', 'haccp', 'control de costos', 'manipulacion de alimentos'],
     [], 85),
    ('LUCIANA FERNANDEZ MOLINA',    'l.fernandez@yahoo.com',     '912333444', 3,
     ['atencion al cliente', 'caja', 'protocolo de servicio'],
     ['ingles avanzado', 'portugues'], 78),
    ('JOSE ANTONIO CHAVEZ ROJAS',   'jchavez.rojas@outlook.com', '976444555', 12,
     ['cocina_caliente', 'cocina_fria', 'sushi', 'haccp', 'iso 22000', 'inventarios'],
     ['ingles intermedio'], 92),
    ('ANDREA SOTO HUAMAN',          'andrea.soto@gmail.com',     '987555666', 2,
     ['caja', 'manejo de propinas', 'atencion al cliente'],
     [], 65),
    ('DIEGO PALACIOS ROCA',         'diego.palacios@gmail.com',  '999666777', 7,
     ['sommelier', 'cata de vinos', 'mixologia', 'bartender'],
     ['ingles avanzado', 'frances'], 88),
    ('PATRICIA AGUILAR ENCISO',     'p.aguilar@gmail.com',       '987777888', 4,
     ['reposteria', 'pasteleria', 'panaderia'],
     [], 80),
    ('JUAN MANUEL DAVILA SOLIS',    'jm.davila@hotmail.com',     '923888999', 6,
     ['cocina_caliente', 'mariscos', 'manipulacion de alimentos'],
     [], 82),
    ('CAMILA REYES MORA',           'camila.reyes@gmail.com',    '912999000', 1,
     ['atencion al cliente'],
     ['ingles intermedio'], 55),
    ('FERNANDO TORRES VEGA',        'f.torres@empresa.com',      '987101010', 10,
     ['cocina_caliente', 'sushi', 'parrilla', 'haccp', 'control de costos', 'inventarios'],
     ['japones', 'ingles intermedio'], 90),
    ('NATALIA HUAMAN PIZARRO',      'natalia.h@gmail.com',       '977202020', 3,
     ['cata de vinos', 'protocolo de servicio', 'manejo de propinas'],
     ['ingles avanzado'], 76),
    ('SEBASTIAN AYALA CRUZ',        'sebastian.ayala@gmail.com', '998303030', 5,
     ['bartender', 'mixologia', 'cata de vinos'],
     ['ingles avanzado'], 84),
    ('ROCIO MORENO LIZARRAGA',      'rocio.moreno@hotmail.com',  '987404040', 4,
     ['atencion al cliente', 'caja', 'manejo de propinas'],
     [], 70),
    ('GIANCARLO RIOS BUSTAMANTE',   'gc.rios@gmail.com',         '966505050', 9,
     ['cocina_caliente', 'mariscos', 'sushi', 'haccp', 'control de costos'],
     ['ingles intermedio'], 87),
    ('ALEJANDRA VARGAS QUINTANA',   'a.vargas@yahoo.com',        '923606060', 2,
     ['pasteleria', 'reposteria'],
     [], 62),
    ('RICARDO MENDEZ PORRAS',       'ricardo.mendez@gmail.com',  '987707070', 6,
     ['cocina_caliente', 'cocina_fria', 'manipulacion de alimentos'],
     [], 79),
    ('PAOLA VALDIVIA CHACON',       'paola.valdivia@gmail.com',  '977808080', 4,
     ['atencion al cliente', 'protocolo de servicio', 'cata de vinos'],
     ['ingles avanzado', 'italiano'], 81),
    ('HERNAN PEREZ MONTOYA',        'hernan.perez@hotmail.com',  '998909090', 11,
     ['cocina_caliente', 'parrilla', 'haccp', 'iso 22000', 'control de costos', 'inventarios'],
     [], 91),
    ('ISABEL CASTRO YUPANQUI',      'icastro@empresa.com',       '912121212', 5,
     ['planillas', 'sunat', 'plame', 'gratificaciones', 'cts'],
     [], 82),
    ('MARCO ANTONIO LUNA SALAS',    'm.luna@gmail.com',          '966131313', 3,
     ['bartender', 'cata de vinos'],
     ['ingles intermedio'], 68),
    ('SHEILA RAMOS DELGADO',        'sheila.ramos@gmail.com',    '987141414', 8,
     ['cocina_caliente', 'reposteria', 'pasteleria', 'haccp'],
     [], 86),
    ('ANDRES CALERO MENDOZA',       'andres.calero@hotmail.com', '977151515', 1,
     ['atencion al cliente'],
     [], 48),
    ('CINTHIA ROBLES NAVARRO',      'cinthia.r@gmail.com',       '923161616', 6,
     ['cocina_caliente', 'mariscos', 'manipulacion de alimentos'],
     ['ingles intermedio'], 83),
    ('OSCAR HUERTAS PEÑA',          'oscar.huertas@gmail.com',   '987171717', 4,
     ['sommelier', 'cata de vinos', 'protocolo de servicio'],
     ['ingles avanzado', 'frances'], 80),
    ('LEONOR JIMENEZ SAAVEDRA',     'leonor.jimenez@gmail.com',  '977181818', 7,
     ['cocina_caliente', 'cocina_fria', 'haccp', 'inventarios'],
     [], 85),
]

FUENTES = ['PORTAL', 'LINKEDIN', 'REFERIDO', 'HEADHUNTER']

# Distribución: cómo se reparten los candidatos en el pipeline
DISTRIBUCION_ETAPAS = [
    ('Recibido',     0.40),   # 40% en etapa inicial
    ('Screening',    0.25),
    ('Entrevista',   0.18),
    ('Prueba',       0.10),
    ('Oferta',       0.05),
    ('Contratado',   0.02),
]


class Command(BaseCommand):
    help = 'Sembrar 25 postulaciones demo con CVs realistas.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true',
                            help='Eliminar postulaciones previas seed.')

    def handle(self, *args, **opts):
        if opts['clear']:
            n = Postulacion.objects.filter(
                notas__contains='[seed_postulaciones_demo]'
            ).delete()
            self.stdout.write(f'  Eliminadas {n[0]} postulaciones previas seed.')

        # Asegurar etapas mínimas
        nombres_etapas = ['Recibido', 'Screening', 'Entrevista', 'Prueba', 'Oferta', 'Contratado']
        etapas = {}
        for i, nombre in enumerate(nombres_etapas, start=1):
            codigo_slug = nombre.lower().replace(' ', '_')
            etapa, _ = EtapaPipeline.objects.get_or_create(
                codigo=codigo_slug,
                defaults={'nombre': nombre, 'orden': i, 'color': '#0f766e'},
            )
            etapas[nombre] = etapa

        # Obtener vacantes activas
        vacantes = list(Vacante.objects.filter(
            estado__in=['PUBLICADA', 'ACTIVA']
        ))
        if not vacantes:
            self.stdout.write(self.style.ERROR(
                'No hay vacantes activas. Corre seed_demo_extra primero.'
            ))
            return

        random.seed(73)
        now = timezone.now()
        creados = 0

        for i, (nombre, email, tel, exp, skills, idiomas, score_base) in enumerate(CANDIDATOS_DEMO):
            # Skip si ya existe (idempotencia)
            if Postulacion.objects.filter(email=email).exists():
                continue

            vac = vacantes[i % len(vacantes)]

            # Elegir etapa según distribución acumulada
            r = random.random()
            acum = 0
            etapa_nombre = 'Recibido'
            for et, pct in DISTRIBUCION_ETAPAS:
                acum += pct
                if r <= acum:
                    etapa_nombre = et
                    break

            etapa = etapas.get(etapa_nombre, etapas['Recibido'])

            # Estado coherente con etapa
            if etapa_nombre == 'Contratado':
                estado = 'CONTRATADA'
            else:
                estado = 'ACTIVA'

            # Fecha de postulación: distribuida en últimos 45 días
            dias_atras = random.randint(1, 45)
            fecha = now - timedelta(days=dias_atras)

            # Score con variación
            score = max(0, min(100, score_base + random.randint(-8, 8)))

            post = Postulacion.objects.create(
                vacante=vac,
                etapa=etapa,
                nombre_completo=nombre,
                email=email,
                telefono=tel,
                experiencia_anos=exp,
                estado=estado,
                fuente=random.choice(FUENTES),
                cv_skills=skills,
                cv_idiomas=idiomas,
                cv_score=score,
                cv_parsed_at=fecha,
                cv_texto_extraido=(
                    f"CV de {nombre}\n"
                    f"Email: {email}\nTeléfono: {tel}\n"
                    f"Experiencia: {exp} años\n"
                    f"Skills: {', '.join(skills)}\n"
                    f"Idiomas: {', '.join(idiomas) if idiomas else 'Español (nativo)'}"
                ),
                notas=f'[seed_postulaciones_demo] Fuente sintética para demo.',
            )
            # Manualmente setear fecha_postulacion (auto_now_add ignora el valor inicial)
            Postulacion.objects.filter(pk=post.pk).update(fecha_postulacion=fecha)
            creados += 1

        # Aggregates
        total = Postulacion.objects.count()
        por_etapa = {}
        for et in etapas.values():
            por_etapa[et.nombre] = Postulacion.objects.filter(etapa=et).count()

        self.stdout.write(self.style.SUCCESS(
            f'\n=== Postulaciones Demo ===\n'
            f'  Creadas:      {creados}\n'
            f'  Total sistema: {total}\n'
            f'  Por etapa: {por_etapa}\n'
        ))
