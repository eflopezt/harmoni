"""
Modo SUNAFIL — paquete de inspección laboral en un clic.

El inspector pide siempre lo mismo para un rango de fechas: boletas de pago,
resumen de planillas, control de asistencia y contratos. Hoy eso significa
horas armando carpetas a mano; este módulo lo genera como UN ZIP ordenado:

    Inspeccion_SUNAFIL_<desde>_<hasta>.zip
    ├── 00_INDICE.txt                        (qué contiene + conteos)
    ├── 01_Boletas/<YYYY-MM>/Boleta_<DNI>_<YYYYMM>.pdf
    ├── 02_Planillas/Planilla_<YYYY-MM>.csv  (resumen por trabajador)
    ├── 03_Asistencia/Tareo_<YYYY-MM>.csv    (registro diario)
    └── 04_Contratos/Contrato_<DNI>_<tipo>.pdf  (archivos adjuntos)

URL: /documentos/inspeccion/  (solo superuser)
Límite: 12 meses por paquete (tamaño en memoria).
"""
import csv
import io
import logging
import zipfile
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

logger = logging.getLogger(__name__)

solo_admin = user_passes_test(lambda u: u.is_superuser)

MAX_MESES = 12


def _meses_en_rango(desde: date, hasta: date):
    """Lista de (anio, mes) entre dos fechas, inclusivo."""
    meses = []
    anio, mes = desde.year, desde.month
    while (anio, mes) <= (hasta.year, hasta.month):
        meses.append((anio, mes))
        mes += 1
        if mes > 12:
            mes = 1
            anio += 1
    return meses


def _agregar_boletas_y_planillas(zf, meses, incluir_boletas, incluir_planillas, indice):
    from nominas.models import PeriodoNomina

    try:
        from nominas.pdf import generar_boleta_pdf
    except ImportError:
        generar_boleta_pdf = None

    n_boletas = n_planillas = 0
    periodos = PeriodoNomina.objects.filter(
        estado__in=('APROBADO', 'CERRADO'),
    ).order_by('anio', 'mes', 'tipo')
    periodos = [p for p in periodos if (p.anio, p.mes) in set(meses)]

    for p in periodos:
        etiqueta = f'{p.anio}-{p.mes:02d}'
        sufijo = '' if p.tipo == 'REGULAR' else f'_{p.tipo}'
        registros = (
            p.registros.select_related('personal')
            .prefetch_related('lineas__concepto')
            .order_by('personal__apellidos_nombres')
        )

        if incluir_planillas:
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow([
                'DNI', 'Apellidos y Nombres', 'Días trab.', 'Días falta',
                'HE 25', 'HE 35', 'HE 100', 'Total ingresos',
                'Total descuentos', 'Neto a pagar', 'EsSalud empleador',
            ])
            for r in registros:
                w.writerow([
                    r.personal.nro_doc, r.personal.apellidos_nombres,
                    r.dias_trabajados, r.dias_falta,
                    r.horas_extra_25, r.horas_extra_35, r.horas_extra_100,
                    r.total_ingresos, r.total_descuentos, r.neto_a_pagar,
                    r.aporte_essalud,
                ])
            zf.writestr(
                f'02_Planillas/Planilla_{etiqueta}{sufijo}.csv',
                '﻿' + buf.getvalue(),   # BOM para Excel
            )
            n_planillas += 1

        if incluir_boletas and generar_boleta_pdf is not None:
            for r in registros:
                try:
                    pdf = generar_boleta_pdf(r)
                    dni = r.personal.nro_doc or f'reg{r.pk}'
                    zf.writestr(
                        f'01_Boletas/{etiqueta}{sufijo}/Boleta_{dni}_{p.anio}{p.mes:02d}.pdf',
                        pdf,
                    )
                    n_boletas += 1
                except Exception as e:
                    logger.warning('Inspección: boleta %s falló: %s', r.pk, e)

    indice.append(f'Boletas de pago: {n_boletas} PDF')
    indice.append(f'Planillas resumen: {n_planillas} CSV')


def _agregar_tareo(zf, desde, hasta, indice):
    from asistencia.models import RegistroTareo

    qs = (
        RegistroTareo.objects.filter(fecha__gte=desde, fecha__lte=hasta)
        .order_by('fecha', 'dni')
        .values_list(
            'fecha', 'dni', 'nombre_archivo', 'grupo',
            'codigo_dia', 'he_25', 'he_35', 'he_100',
        )
    )
    por_mes = {}
    for fecha, dni, nombre, grupo, cod, he25, he35, he100 in qs.iterator():
        por_mes.setdefault((fecha.year, fecha.month), []).append(
            (fecha, dni, nombre, grupo, cod, he25, he35, he100)
        )

    total = 0
    for (anio, mes), filas in sorted(por_mes.items()):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['Fecha', 'DNI', 'Apellidos y Nombres', 'Grupo',
                    'Código día', 'HE 25%', 'HE 35%', 'HE 100%'])
        for fila in filas:
            w.writerow([fila[0].isoformat(), *fila[1:]])
        zf.writestr(
            f'03_Asistencia/Tareo_{anio}-{mes:02d}.csv',
            '﻿' + buf.getvalue(),
        )
        total += len(filas)
    indice.append(f'Asistencia (tareo diario): {total} registros en {len(por_mes)} archivo(s)')


def _agregar_contratos(zf, indice):
    from personal.models import Contrato

    n = 0
    contratos = (
        Contrato.objects.filter(personal__estado='Activo')
        .exclude(archivo_pdf='')
        .select_related('personal')
        .order_by('personal__apellidos_nombres', '-fecha_inicio')
    )
    for c in contratos:
        try:
            with c.archivo_pdf.open('rb') as fh:
                dni = c.personal.nro_doc or f'p{c.personal_id}'
                tipo = (c.tipo_contrato or 'contrato').replace('/', '-')[:30]
                zf.writestr(
                    f'04_Contratos/Contrato_{dni}_{tipo}_{c.pk}.pdf',
                    fh.read(),
                )
                n += 1
        except Exception as e:
            logger.warning('Inspección: contrato %s sin archivo legible: %s', c.pk, e)
    indice.append(f'Contratos con PDF adjunto (personal activo): {n}')


@login_required
@solo_admin
def inspeccion_sunafil(request):
    """Form (GET) + generación del ZIP (POST)."""
    if request.method != 'POST':
        hoy = timezone.localdate()
        return render(request, 'documentos/inspeccion_sunafil.html', {
            'default_desde': date(hoy.year, 1, 1),
            'default_hasta': hoy,
        })

    try:
        desde = date.fromisoformat(request.POST.get('desde', ''))
        hasta = date.fromisoformat(request.POST.get('hasta', ''))
    except ValueError:
        messages.error(request, 'Rango de fechas inválido.')
        return redirect('documentos_inspeccion_sunafil')

    if desde > hasta:
        desde, hasta = hasta, desde
    meses = _meses_en_rango(desde, hasta)
    if len(meses) > MAX_MESES:
        messages.error(
            request,
            f'Máximo {MAX_MESES} meses por paquete (pediste {len(meses)}). '
            'Genera dos paquetes.'
        )
        return redirect('documentos_inspeccion_sunafil')

    incluir_boletas   = bool(request.POST.get('boletas'))
    incluir_planillas = bool(request.POST.get('planillas'))
    incluir_tareo     = bool(request.POST.get('tareo'))
    incluir_contratos = bool(request.POST.get('contratos'))
    if not any([incluir_boletas, incluir_planillas, incluir_tareo, incluir_contratos]):
        messages.error(request, 'Selecciona al menos un componente.')
        return redirect('documentos_inspeccion_sunafil')

    indice = [
        'PAQUETE DE INSPECCIÓN LABORAL — generado por Harmoni',
        f'Rango solicitado: {desde.isoformat()} a {hasta.isoformat()}',
        f'Generado: {timezone.localtime():%Y-%m-%d %H:%M} por {request.user.get_username()}',
        '',
    ]

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        if incluir_boletas or incluir_planillas:
            _agregar_boletas_y_planillas(
                zf, meses, incluir_boletas, incluir_planillas, indice
            )
        if incluir_tareo:
            _agregar_tareo(zf, desde, hasta, indice)
        if incluir_contratos:
            _agregar_contratos(zf, indice)

        indice += [
            '',
            'Contenido:',
            '  01_Boletas/      boletas de pago PDF por mes (períodos aprobados/cerrados)',
            '  02_Planillas/    resumen CSV por período (días, HE, ingresos, descuentos, neto)',
            '  03_Asistencia/   tareo diario CSV por mes',
            '  04_Contratos/    contratos PDF adjuntos del personal activo',
        ]
        zf.writestr('00_INDICE.txt', '\r\n'.join(indice))

    # Auditoría: las exportaciones masivas de datos laborales quedan logueadas
    logger.info(
        'Paquete SUNAFIL generado por %s — rango %s a %s, componentes: %s',
        request.user.get_username(), desde, hasta,
        [n for n, f in [('boletas', incluir_boletas), ('planillas', incluir_planillas),
                        ('tareo', incluir_tareo), ('contratos', incluir_contratos)] if f],
    )

    zip_buffer.seek(0)
    resp = HttpResponse(zip_buffer.read(), content_type='application/zip')
    resp['Content-Disposition'] = (
        f'attachment; filename="Inspeccion_SUNAFIL_{desde.isoformat()}_{hasta.isoformat()}.zip"'
    )
    return resp
