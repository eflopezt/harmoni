"""
Servicio de resolución de placeholders para contratos, prórrogas y adendas laborales.

Resuelve {{placeholder}} en HTML de PlantillaContrato con datos reales
del contrato, personal, empresa, adenda, etc.
"""
import re
import html as html_module

from django.utils.formats import number_format


def _safe(value, default='---'):
    """HTML-escape value, return default if empty."""
    if value is None or value == '':
        return default
    return html_module.escape(str(value))


def _format_date(date_obj):
    """Formatea fecha en formato legible: '01 de enero de 2026'."""
    if not date_obj:
        return '---'
    MESES = [
        '', 'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    ]
    return f"{date_obj.day:02d} de {MESES[date_obj.month]} de {date_obj.year}"


def _format_money(amount):
    """Formatea monto monetario: S/ 2,500.00"""
    if amount is None:
        return '---'
    return f"S/ {number_format(amount, 2, force_grouping=True)}"


def _money_to_words(amount):
    """Convierte monto a palabras en español."""
    if amount is None:
        return '---'
    try:
        from num2words import num2words
        entero = int(amount)
        centimos = int(round((amount - entero) * 100))
        palabras = num2words(entero, lang='es')
        return f"{palabras} con {centimos:02d}/100 soles"
    except (ImportError, Exception):
        return str(amount)


def _img_tag(image_field, css_class='', max_height='70px'):
    """Genera <img> tag para xhtml2pdf (necesita file:// absolute path)."""
    if not image_field:
        return ''
    try:
        path = image_field.path
        return (
            f'<img src="file:///{path}" class="{css_class}" '
            f'style="max-height: {max_height};">'
        )
    except Exception:
        return ''


def _funciones_as_html(cargo_obj):
    """Convierte funciones del cargo a lista HTML numerada."""
    if not cargo_obj or not cargo_obj.funciones:
        return '---'
    funciones = [f.strip() for f in cargo_obj.funciones.strip().split('\n') if f.strip()]
    if not funciones:
        return '---'
    items = ''.join(f'<li>{html_module.escape(f)}</li>\n' for f in funciones)
    return f'<ol style="margin:5px 0; padding-left:20px;">\n{items}</ol>'


def resolve_placeholders(contenido_html, contrato=None, personal=None, empresa=None,
                         adenda=None, extra_context=None):
    """
    Resuelve todos los {{placeholder}} en el HTML de una plantilla de contrato.

    Args:
        contenido_html: HTML con placeholders {{...}}
        contrato: instancia de Contrato (puede ser None para adendas standalone)
        personal: instancia de Personal
        empresa: instancia de Empresa
        adenda: instancia de Adenda (opcional, para adendas)
        extra_context: dict con valores adicionales que sobreescriben los calculados

    Returns:
        HTML con placeholders resueltos
    """
    if not contenido_html:
        return ''

    # Build mapping
    mapping = {}

    # ── Empresa ──
    if empresa:
        mapping.update({
            'empresa': _safe(empresa.razon_social),
            'ruc_empresa': _safe(empresa.ruc),
            'direccion_empresa': _safe(empresa.direccion),
            'representante_legal': _safe(empresa.representante_legal),
            'cargo_representante': _safe(empresa.cargo_representante, 'Representante Legal'),
            'tipo_doc_representante': _safe(getattr(empresa, 'tipo_doc_representante', ''), 'D.N.I.'),
            'nro_doc_representante': _safe(getattr(empresa, 'nro_doc_representante', '')),
            'logo': _img_tag(empresa.logo, 'logo', '70px'),
            'firma_representante': _img_tag(empresa.firma_representante, 'firma-img', '60px'),
            'membrete': _img_tag(empresa.membrete_header, 'membrete', '100px'),
        })

    # ── Personal / Trabajador ──
    if personal:
        mapping.update({
            'nombre_empleado': _safe(personal.apellidos_nombres),
            'dni': _safe(personal.nro_doc),
            'tipo_doc_trabajador': _safe(personal.tipo_doc, 'D.N.I.'),
            'cargo': _safe(personal.cargo),
            'domicilio': _safe(personal.direccion),
            'email_trabajador': _safe(
                getattr(personal, 'correo_personal', '') or
                getattr(personal, 'correo_corporativo', '')
            ),
        })
        # Dirección desglosada (si tiene ubigeo)
        ubigeo = getattr(personal, 'ubigeo', '') or ''
        mapping['distrito'] = _safe(getattr(personal, 'distrito', ''))
        mapping['provincia'] = _safe(getattr(personal, 'provincia', ''))
        mapping['departamento'] = _safe(getattr(personal, 'departamento', ''))

        # Funciones del cargo (desde Cargo model)
        cargo_obj = getattr(personal, 'cargo_obj', None)
        mapping['funciones_cargo'] = _funciones_as_html(cargo_obj)

    # ── Contrato ──
    if contrato:
        mapping.update({
            'fecha_inicio': _format_date(contrato.fecha_inicio),
            'fecha_fin': _format_date(contrato.fecha_fin),
            'remuneracion': _format_money(contrato.sueldo_pactado),
            'remuneracion_letras': _money_to_words(
                float(contrato.sueldo_pactado) if contrato.sueldo_pactado else None
            ),
            'jornada_semanal': _safe(
                int(contrato.jornada_semanal) if contrato.jornada_semanal else 48
            ),
            'numero_contrato': _safe(contrato.numero_contrato),
            'tipo_contrato': _safe(contrato.get_tipo_contrato_display()),
        })

        # Período de prueba basado en categoría
        if personal:
            cat = getattr(personal, 'categoria', 'NORMAL')
            cargo_obj = getattr(personal, 'cargo_obj', None)
            if cat == 'DIRECCION':
                mapping['periodo_prueba'] = 'doce (12) meses'
            elif cat == 'CONFIANZA' or (cargo_obj and cargo_obj.es_confianza):
                mapping['periodo_prueba'] = 'seis (06) meses'
            else:
                mapping['periodo_prueba'] = 'tres (03) meses'

        # Datos para prórrogas
        # Buscar contrato original y última prórroga
        if personal and contrato:
            contratos_anteriores = list(
                personal.contratos.filter(
                    fecha_inicio__lt=contrato.fecha_inicio
                ).order_by('fecha_inicio')
            )
            if contratos_anteriores:
                primer_contrato = contratos_anteriores[0]
                ultimo_contrato = contratos_anteriores[-1]
                mapping['fecha_inicio_original'] = _format_date(primer_contrato.fecha_inicio)
                mapping['fecha_fin_original'] = _format_date(primer_contrato.fecha_fin)
                mapping['fecha_fin_anterior'] = _format_date(ultimo_contrato.fecha_fin)
                mapping['ultima_prorroga'] = _format_date(ultimo_contrato.fecha_fin)

    # ── Adenda ──
    if adenda:
        mapping.update({
            'sueldo_anterior': _safe(adenda.valor_anterior),
            'sueldo_nuevo': _safe(adenda.valor_nuevo),
            'cargo_anterior': _safe(adenda.valor_anterior),
            'cargo_nuevo': _safe(adenda.valor_nuevo),
            'tipo_modificacion': _safe(adenda.get_tipo_modificacion_display()),
            'detalle_adenda': _safe(adenda.detalle),
            'fecha_adenda': _format_date(adenda.fecha),
        })

    # ── Fechas de firma ──
    if empresa:
        mapping['ciudad_firma'] = _safe(
            empresa.distrito or empresa.departamento, 'Lima'
        )

    from django.utils import timezone
    hoy = timezone.localdate()
    mapping.setdefault('fecha_firma', _format_date(hoy))

    # ── Extra context (overrides) ──
    if extra_context:
        for key, value in extra_context.items():
            mapping[key] = _safe(value) if not isinstance(value, str) or '>' not in value else value

    # ── Resolve ──
    def replacer(match):
        key = match.group(1)
        return mapping.get(key, f'{{{{{key}}}}}')  # Leave unreplaced if not found

    result = re.sub(r'\{\{(\w+)\}\}', replacer, contenido_html)
    return result
