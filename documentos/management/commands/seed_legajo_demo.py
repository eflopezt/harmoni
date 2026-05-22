"""
Management command: seed_legajo_demo

Genera documentos demo para los primeros N trabajadores activos.
Por cada trabajador crea hasta 5 documentos:
  - DNI                  (vigente, sin vencimiento)
  - Examen Médico        (estado rotativo: vigente / por vencer / vencido)
  - Contrato             (vigente)
  - Antecedentes Penales (vigente 6 meses)
  - Carné de Sanidad     (estado rotativo)

Usa PDF mínimo válido como contenido placeholder.
Idempotente: si ya existe el doc para ese personal+tipo, lo respeta.

Uso:
    python manage.py seed_legajo_demo
    python manage.py seed_legajo_demo --personal 25     # limita a N trabajadores
    python manage.py seed_legajo_demo --reset           # borra demos previas
"""
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from documentos.models import (
    CategoriaDocumento, DocumentoTrabajador, TipoDocumento,
)


def _build_pdf_bytes(label: str) -> bytes:
    """
    Construye un PDF mínimo válido (~ 500 B) con un label visible.
    Estructura PDF 1.4: catalog → pages → page con texto.
    """
    body = (
        f'BT /F1 12 Tf 72 720 Td (Demo legajo - {label}) Tj ET'
    ).encode('ascii', errors='ignore')

    def _obj(n, content):
        return f'{n} 0 obj\n{content}\nendobj\n'.encode('ascii')

    parts = []
    parts.append(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')

    # Stream object (Page contents)
    stream = b'stream\n' + body + b'\nendstream'
    obj4 = (
        f'4 0 obj\n<< /Length {len(body)} >>\n'.encode('ascii')
        + stream + b'\nendobj\n'
    )

    parts.append(_obj(1, '<< /Type /Catalog /Pages 2 0 R >>'))
    parts.append(_obj(2, '<< /Type /Pages /Kids [3 0 R] /Count 1 >>'))
    parts.append(_obj(3,
        '<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] '
        '/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>'
    ))
    parts.append(obj4)
    parts.append(_obj(5, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'))

    body_bytes = b''.join(parts)
    xref_offset = len(body_bytes)

    xref = b'xref\n0 6\n0000000000 65535 f \n'
    offsets = []
    cursor = len(parts[0])
    for p in parts[1:]:
        offsets.append(cursor)
        cursor += len(p)
    for off in offsets:
        xref += f'{off:010d} 00000 n \n'.encode('ascii')

    trailer = (
        b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'
        + str(xref_offset).encode('ascii') + b'\n%%EOF\n'
    )
    return body_bytes + xref + trailer


def _ensure_categoria(nombre, icono, orden):
    obj, _ = CategoriaDocumento.objects.get_or_create(
        nombre=nombre,
        defaults={'icono': icono, 'orden': orden, 'activa': True},
    )
    return obj


def _ensure_tipo(nombre, categoria, *, vence, vigencia_dias, obligatorio,
                 aplica_staff=True, aplica_rco=True):
    obj, _ = TipoDocumento.objects.get_or_create(
        nombre=nombre,
        defaults={
            'categoria': categoria,
            'vence': vence,
            'vigencia_dias': vigencia_dias,
            'obligatorio': obligatorio,
            'aplica_staff': aplica_staff,
            'aplica_rco': aplica_rco,
            'dias_alerta_vencimiento': 30,
            'activo': True,
        },
    )
    cambios = []
    if obj.vence != vence:
        obj.vence = vence; cambios.append('vence')
    if vence and obj.vigencia_dias is None and vigencia_dias:
        obj.vigencia_dias = vigencia_dias; cambios.append('vigencia_dias')
    if cambios:
        obj.save(update_fields=cambios)
    return obj


class Command(BaseCommand):
    help = 'Crea documentos demo de legajo para los primeros N trabajadores activos.'

    def add_arguments(self, parser):
        parser.add_argument('--personal', type=int, default=10,
                            help='Cantidad de trabajadores a sembrar (default 10).')
        parser.add_argument('--reset', action='store_true',
                            help='Elimina documentos demo previos (por nombre_archivo).')

    @transaction.atomic
    def handle(self, *args, **opts):
        from personal.models import Personal

        n_personal = opts.get('personal', 10)
        reset = opts.get('reset', False)

        cat_identidad   = _ensure_categoria('Identidad',     'fa-id-card',       2)
        cat_contractual = _ensure_categoria('Contractual',   'fa-file-contract', 1)
        cat_ssoma       = _ensure_categoria('SSOMA',         'fa-hard-hat',      4)
        cat_legal       = _ensure_categoria('Disciplinario', 'fa-gavel',         6)

        tipo_dni = _ensure_tipo(
            'DNI / CE', cat_identidad,
            vence=False, vigencia_dias=None, obligatorio=True,
        )
        tipo_examen = _ensure_tipo(
            'Examen Médico Pre-ocupacional', cat_ssoma,
            vence=True, vigencia_dias=365, obligatorio=True,
        )
        tipo_contrato = _ensure_tipo(
            'Contrato de Trabajo', cat_contractual,
            vence=False, vigencia_dias=None, obligatorio=True,
        )
        tipo_antec = _ensure_tipo(
            'Antecedentes Penales', cat_legal,
            vence=True, vigencia_dias=180, obligatorio=False,
        )
        tipo_carne = _ensure_tipo(
            'Carné de Sanidad', cat_ssoma,
            vence=True, vigencia_dias=365, obligatorio=True,
        )

        trabajadores = list(
            Personal.objects.filter(estado='Activo')
            .order_by('apellidos_nombres')[:n_personal]
        )
        if not trabajadores:
            self.stdout.write(self.style.WARNING(
                'No hay trabajadores activos para sembrar. Aborto.'
            ))
            return

        if reset:
            removed = DocumentoTrabajador.objects.filter(
                personal__in=trabajadores,
                nombre_archivo__startswith='demo_legajo_',
            ).delete()
            self.stdout.write(self.style.WARNING(
                f'Reset: eliminados {removed[0]} documentos demo previos.'
            ))

        hoy = date.today()
        plantilla = [
            (tipo_dni,      hoy - timedelta(days=730), None, 'DNI'),
            (tipo_contrato, hoy - timedelta(days=540), None, 'CONTRATO'),
            (tipo_antec,    hoy - timedelta(days=60),  None, 'ANTECEDENTES'),
            (tipo_examen,   None, None, 'EXAMEN'),
            (tipo_carne,    None, None, 'CARNE'),
        ]

        creados_total = 0
        for idx, personal in enumerate(trabajadores):
            for tipo, fecha_emision, _override, label in plantilla:
                if DocumentoTrabajador.objects.filter(
                    personal=personal, tipo=tipo,
                ).exists():
                    continue

                fe = fecha_emision
                fv = None
                if tipo == tipo_examen:
                    mod = idx % 3
                    if mod == 0:
                        fe = hoy - timedelta(days=30); fv = hoy + timedelta(days=335)
                    elif mod == 1:
                        fe = hoy - timedelta(days=345); fv = hoy + timedelta(days=20)
                    else:
                        fe = hoy - timedelta(days=400); fv = hoy - timedelta(days=35)
                elif tipo == tipo_carne:
                    mod = (idx + 1) % 3
                    if mod == 0:
                        fe = hoy - timedelta(days=60); fv = hoy + timedelta(days=305)
                    elif mod == 1:
                        fe = hoy - timedelta(days=350); fv = hoy + timedelta(days=15)
                    else:
                        fe = hoy - timedelta(days=420); fv = hoy - timedelta(days=55)
                elif tipo == tipo_antec:
                    fv = (fe or hoy) + timedelta(days=180)

                contenido = _build_pdf_bytes(label)
                nombre = f'demo_legajo_{label.lower()}_{personal.pk}.pdf'
                doc = DocumentoTrabajador(
                    personal=personal,
                    tipo=tipo,
                    fecha_emision=fe,
                    fecha_vencimiento=fv,
                    nombre_archivo=nombre,
                    notas='Documento demo generado por seed_legajo_demo.',
                )
                doc.archivo.save(nombre, ContentFile(contenido), save=False)
                doc.save()
                creados_total += 1

        self.stdout.write(self.style.SUCCESS(
            f'OK · {creados_total} documentos demo creados '
            f'para {len(trabajadores)} trabajadores.'
        ))
