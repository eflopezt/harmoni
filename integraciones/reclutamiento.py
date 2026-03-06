"""
Integraciones — Publicacion de Vacantes en Plataformas Externas.

Clases:
    - ComputrabajoExporter:   Export XML/JSON compatible con importacion masiva Computrabajo Peru
    - BumeranExporter:        Export XML/JSON compatible con importacion masiva Bumeran Peru
    - LinkedInJobsPublisher:  Publicacion via API OAuth2 (v2/simpleJobPostings)
    - PortalPropio:           Verificacion del estado del portal empleo interno
    - TelegramJobPublisher:   Publica oferta en canal Telegram via Bot API (gratis, real-time)
    - WhatsAppBusinessPublisher: Publica oferta via WhatsApp Business Cloud API (Meta Graph API)

Uso:
    from integraciones.reclutamiento import ComputrabajoExporter, BumeranExporter, LinkedInJobsPublisher

    exporter = ComputrabajoExporter()
    resultado = exporter.publicar_vacante(vacante)
    # resultado = {'ok': True, 'payload': {...}, 'xml': '...', 'mensaje': '...'}
"""
import json
import logging
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal
from typing import Any
from xml.dom import minidom

import urllib.request
import urllib.error
import urllib.parse

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════

def _safe_str(value: Any, default: str = '') -> str:
    """Convierte valor a str de forma segura, retorna default si es None."""
    if value is None:
        return default
    return str(value).strip()


def _formatear_salario(salario_min, salario_max, moneda: str = 'PEN') -> dict:
    """Genera dict estandarizado de rango salarial."""
    resultado = {
        'moneda': moneda,
        'minimo': None,
        'maximo': None,
        'texto': 'A convenir',
    }
    if salario_min:
        resultado['minimo'] = float(salario_min)
    if salario_max:
        resultado['maximo'] = float(salario_max)

    if salario_min and salario_max:
        simbolo = 'S/' if moneda == 'PEN' else 'USD'
        resultado['texto'] = f'{simbolo} {salario_min:,.0f} - {simbolo} {salario_max:,.0f}'
    elif salario_min:
        simbolo = 'S/' if moneda == 'PEN' else 'USD'
        resultado['texto'] = f'Desde {simbolo} {salario_min:,.0f}'

    return resultado


def _prettify_xml(element: ET.Element) -> str:
    """Retorna string XML con indentacion legible."""
    raw = ET.tostring(element, encoding='unicode')
    reparsed = minidom.parseString(raw)
    return reparsed.toprettyxml(indent='  ', encoding=None)


# ══════════════════════════════════════════════════════════════
# MAPA DE NIVELES EDUCATIVOS
# ══════════════════════════════════════════════════════════════

EDUCACION_A_COMPUTRABAJO = {
    'NO_REQUERIDO':   'No Requerido',
    'SECUNDARIA':     'Secundaria Completa',
    'TECNICO':        'Tecnica',
    'UNIVERSITARIO':  'Universitaria',
    'MAESTRIA':       'Maestria',
    'DOCTORADO':      'Doctorado',
}

EDUCACION_A_BUMERAN = {
    'NO_REQUERIDO':   'No requiere',
    'SECUNDARIA':     'Secundario',
    'TECNICO':        'Terciario/Tecnico',
    'UNIVERSITARIO':  'Universitario',
    'MAESTRIA':       'Posgrado',
    'DOCTORADO':      'Doctorado',
}

CONTRATO_A_COMPUTRABAJO = {
    'INDETERMINADO':  'Tiempo completo',
    'PLAZO_FIJO':     'Contrato por tiempo determinado',
    'PROYECTO':       'Por proyecto',
    'SUPLENCIA':      'Suplencia',
}

CONTRATO_A_BUMERAN = {
    'INDETERMINADO':  'Relacion de dependencia',
    'PLAZO_FIJO':     'Contrato por tiempo determinado',
    'PROYECTO':       'Trabajo por proyecto o tarea',
    'SUPLENCIA':      'Eventual / Temporal',
}

# LinkedIn usa codigos estandar de industria (NAICS) y tipo de trabajo
CONTRATO_A_LINKEDIN = {
    'INDETERMINADO':  'FULL_TIME',
    'PLAZO_FIJO':     'CONTRACT',
    'PROYECTO':       'OTHER',
    'SUPLENCIA':      'TEMPORARY',
}

EXPERIENCIA_A_LINKEDIN = {
    0: 'ENTRY_LEVEL',
    1: 'ENTRY_LEVEL',
    2: 'MID_SENIOR_LEVEL',
    3: 'MID_SENIOR_LEVEL',
    4: 'MID_SENIOR_LEVEL',
    5: 'SENIOR_LEVEL',
}


def _linkedin_seniority(anos: int) -> str:
    if anos <= 1:
        return 'ENTRY_LEVEL'
    if anos <= 4:
        return 'MID_SENIOR_LEVEL'
    return 'SENIOR_LEVEL'


# ══════════════════════════════════════════════════════════════
# COMPUTRABAJO EXPORTER
# ══════════════════════════════════════════════════════════════

class ComputrabajoExporter:
    """
    Genera payload XML/JSON en formato compatible con la importacion
    masiva de ofertas de Computrabajo Peru.

    Referencia de campos: https://www.computrabajo.com.pe/empresas/publicar/
    (formato de feed de empleo estandar HR-XML / oferta empleo Computrabajo)

    Nota: Computrabajo Peru no tiene API publica oficial en 2026.
    Este exporter produce el archivo listo para subir manualmente o
    via SFTP/feed URL configurado en el panel de empresa.
    """

    PLATAFORMA = 'COMPUTRABAJO'

    def publicar_vacante(self, vacante) -> dict:
        """
        Genera el payload XML y JSON para una vacante.

        Args:
            vacante: instancia de reclutamiento.models.Vacante

        Returns:
            dict con claves:
                ok (bool), payload (dict), xml (str), mensaje (str), error (str|None)
        """
        try:
            payload = self._construir_payload(vacante)
            xml_str = self._construir_xml(vacante)
            return {
                'ok': True,
                'plataforma': self.PLATAFORMA,
                'payload': payload,
                'xml': xml_str,
                'mensaje': (
                    f'Payload Computrabajo generado correctamente para "{vacante.titulo}". '
                    f'Suba el archivo XML al panel de empresa en computrabajo.com.pe '
                    f'o configure el feed URL en su cuenta.'
                ),
                'error': None,
            }
        except Exception as exc:
            logger.exception('ComputrabajoExporter: error generando payload para vacante %s', vacante.pk)
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'payload': None,
                'xml': None,
                'mensaje': '',
                'error': str(exc),
            }

    def _construir_payload(self, vacante) -> dict:
        salario = _formatear_salario(vacante.salario_min, vacante.salario_max, vacante.moneda)
        return {
            'titulo':            _safe_str(vacante.titulo),
            'descripcion':       _safe_str(vacante.descripcion),
            'requisitos':        _safe_str(vacante.requisitos),
            'area':              _safe_str(vacante.area.nombre if vacante.area else ''),
            'tipo_contrato':     CONTRATO_A_COMPUTRABAJO.get(vacante.tipo_contrato, 'Tiempo completo'),
            'nivel_educativo':   EDUCACION_A_COMPUTRABAJO.get(vacante.educacion_minima, 'No Requerido'),
            'experiencia_anos':  vacante.experiencia_minima,
            'salario_minimo':    salario['minimo'],
            'salario_maximo':    salario['maximo'],
            'moneda':            vacante.moneda,
            'fecha_publicacion': _safe_str(vacante.fecha_publicacion or date.today()),
            'fecha_cierre':      _safe_str(vacante.fecha_limite or ''),
            'pais':              'Peru',
            'ciudad':            'Lima',                   # configurable en el futuro via ConfiguracionSistema
            'cantidad_vacantes': 1,
            'confidencial':      not vacante.publica,
        }

    def _construir_xml(self, vacante) -> str:
        """Genera XML en formato HR-XML compatible con feeds de Computrabajo."""
        root = ET.Element('Ofertas')
        oferta = ET.SubElement(root, 'Oferta')

        ET.SubElement(oferta, 'Titulo').text          = _safe_str(vacante.titulo)
        ET.SubElement(oferta, 'Descripcion').text     = _safe_str(vacante.descripcion)
        ET.SubElement(oferta, 'Requisitos').text      = _safe_str(vacante.requisitos)
        ET.SubElement(oferta, 'Area').text            = _safe_str(vacante.area.nombre if vacante.area else '')
        ET.SubElement(oferta, 'TipoContrato').text    = CONTRATO_A_COMPUTRABAJO.get(
            vacante.tipo_contrato, 'Tiempo completo'
        )
        ET.SubElement(oferta, 'NivelEducativo').text  = EDUCACION_A_COMPUTRABAJO.get(
            vacante.educacion_minima, 'No Requerido'
        )
        ET.SubElement(oferta, 'ExperienciaAnios').text = str(vacante.experiencia_minima)

        salario_el = ET.SubElement(oferta, 'Salario')
        ET.SubElement(salario_el, 'Moneda').text  = _safe_str(vacante.moneda)
        ET.SubElement(salario_el, 'Minimo').text  = str(vacante.salario_min or '')
        ET.SubElement(salario_el, 'Maximo').text  = str(vacante.salario_max or '')

        ET.SubElement(oferta, 'Pais').text             = 'Peru'
        ET.SubElement(oferta, 'Ciudad').text           = 'Lima'
        ET.SubElement(oferta, 'FechaPublicacion').text = _safe_str(vacante.fecha_publicacion or date.today())
        ET.SubElement(oferta, 'FechaCierre').text      = _safe_str(vacante.fecha_limite or '')
        ET.SubElement(oferta, 'Confidencial').text     = 'false' if vacante.publica else 'true'

        return _prettify_xml(root)

    def exportar_multiples(self, vacantes) -> dict:
        """
        Genera un archivo XML con multiples ofertas (feed masivo).

        Args:
            vacantes: queryset o lista de Vacante

        Returns:
            dict con ok, xml (str con todas las ofertas), count, errores
        """
        root = ET.Element('Ofertas')
        errores = []
        count = 0

        for vacante in vacantes:
            try:
                oferta = ET.SubElement(root, 'Oferta')
                ET.SubElement(oferta, 'Titulo').text       = _safe_str(vacante.titulo)
                ET.SubElement(oferta, 'Descripcion').text  = _safe_str(vacante.descripcion)
                ET.SubElement(oferta, 'Requisitos').text   = _safe_str(vacante.requisitos)
                ET.SubElement(oferta, 'TipoContrato').text = CONTRATO_A_COMPUTRABAJO.get(
                    vacante.tipo_contrato, 'Tiempo completo'
                )
                ET.SubElement(oferta, 'NivelEducativo').text = EDUCACION_A_COMPUTRABAJO.get(
                    vacante.educacion_minima, 'No Requerido'
                )
                ET.SubElement(oferta, 'ExperienciaAnios').text = str(vacante.experiencia_minima)
                count += 1
            except Exception as exc:
                errores.append({'vacante_id': vacante.pk, 'error': str(exc)})

        return {
            'ok': True,
            'plataforma': self.PLATAFORMA,
            'xml': _prettify_xml(root),
            'count': count,
            'errores': errores,
        }


# ══════════════════════════════════════════════════════════════
# BUMERAN EXPORTER
# ══════════════════════════════════════════════════════════════

class BumeranExporter:
    """
    Genera payload XML/JSON en formato compatible con la importacion
    masiva de ofertas de Bumeran Peru (bumeran.com.pe).

    Bumeran Peru usa el grupo Jobint (ex-Bumeran + Konzerta + OCC).
    Soporta importacion via feed XML o JSON. Este exporter genera ambos.

    Nota: No existe API publica oficial con auth OAuth en 2026.
    El feed se configura como URL publica o se sube manualmente.
    """

    PLATAFORMA = 'BUMERAN'

    def publicar_vacante(self, vacante) -> dict:
        """
        Genera el payload JSON y XML para Bumeran Peru.

        Args:
            vacante: instancia de reclutamiento.models.Vacante

        Returns:
            dict con ok, payload, xml, mensaje, error
        """
        try:
            payload = self._construir_payload(vacante)
            xml_str = self._construir_xml(vacante)
            return {
                'ok': True,
                'plataforma': self.PLATAFORMA,
                'payload': payload,
                'xml': xml_str,
                'mensaje': (
                    f'Payload Bumeran generado correctamente para "{vacante.titulo}". '
                    f'Suba el archivo XML/JSON al panel de empresa en bumeran.com.pe '
                    f'o configure el feed de empleo en su cuenta.'
                ),
                'error': None,
            }
        except Exception as exc:
            logger.exception('BumeranExporter: error generando payload para vacante %s', vacante.pk)
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'payload': None,
                'xml': None,
                'mensaje': '',
                'error': str(exc),
            }

    def _construir_payload(self, vacante) -> dict:
        salario = _formatear_salario(vacante.salario_min, vacante.salario_max, vacante.moneda)
        return {
            'job_title':          _safe_str(vacante.titulo),
            'description':        _safe_str(vacante.descripcion),
            'requirements':       _safe_str(vacante.requisitos),
            'category':           _safe_str(vacante.area.nombre if vacante.area else 'General'),
            'contract_type':      CONTRATO_A_BUMERAN.get(vacante.tipo_contrato, 'Relacion de dependencia'),
            'education_level':    EDUCACION_A_BUMERAN.get(vacante.educacion_minima, 'No requiere'),
            'experience_years':   vacante.experiencia_minima,
            'salary': {
                'currency':       vacante.moneda,
                'minimum':        salario['minimo'],
                'maximum':        salario['maximo'],
                'display_text':   salario['texto'],
            },
            'location': {
                'country':        'PE',
                'city':           'Lima',
                'district':       '',
            },
            'publication_date':   _safe_str(vacante.fecha_publicacion or date.today()),
            'expiration_date':    _safe_str(vacante.fecha_limite or ''),
            'vacancies_count':    1,
            'is_confidential':    not vacante.publica,
            'work_modality':      'PRESENCIAL',            # configurable a futuro
        }

    def _construir_xml(self, vacante) -> str:
        """Genera XML en formato Bumeran Job Feed."""
        root = ET.Element('BumeranFeed')
        root.set('version', '1.0')

        job = ET.SubElement(root, 'Job')
        ET.SubElement(job, 'Title').text       = _safe_str(vacante.titulo)
        ET.SubElement(job, 'Description').text = _safe_str(vacante.descripcion)
        ET.SubElement(job, 'Requirements').text = _safe_str(vacante.requisitos)
        ET.SubElement(job, 'Category').text    = _safe_str(vacante.area.nombre if vacante.area else 'General')
        ET.SubElement(job, 'ContractType').text = CONTRATO_A_BUMERAN.get(
            vacante.tipo_contrato, 'Relacion de dependencia'
        )
        ET.SubElement(job, 'EducationLevel').text = EDUCACION_A_BUMERAN.get(
            vacante.educacion_minima, 'No requiere'
        )
        ET.SubElement(job, 'ExperienceYears').text = str(vacante.experiencia_minima)

        salary_el = ET.SubElement(job, 'Salary')
        ET.SubElement(salary_el, 'Currency').text = _safe_str(vacante.moneda)
        ET.SubElement(salary_el, 'Minimum').text  = str(vacante.salario_min or '')
        ET.SubElement(salary_el, 'Maximum').text  = str(vacante.salario_max or '')

        location_el = ET.SubElement(job, 'Location')
        ET.SubElement(location_el, 'Country').text = 'PE'
        ET.SubElement(location_el, 'City').text    = 'Lima'

        ET.SubElement(job, 'PublicationDate').text = _safe_str(vacante.fecha_publicacion or date.today())
        ET.SubElement(job, 'ExpirationDate').text  = _safe_str(vacante.fecha_limite or '')
        ET.SubElement(job, 'Confidential').text    = 'false' if vacante.publica else 'true'

        return _prettify_xml(root)

    def exportar_multiples(self, vacantes) -> dict:
        """
        Genera feed XML con multiples ofertas para Bumeran.

        Args:
            vacantes: queryset o lista de Vacante

        Returns:
            dict con ok, xml, count, errores
        """
        root = ET.Element('BumeranFeed')
        root.set('version', '1.0')
        errores = []
        count = 0

        for vacante in vacantes:
            try:
                job = ET.SubElement(root, 'Job')
                ET.SubElement(job, 'Title').text       = _safe_str(vacante.titulo)
                ET.SubElement(job, 'Description').text = _safe_str(vacante.descripcion)
                ET.SubElement(job, 'ContractType').text = CONTRATO_A_BUMERAN.get(
                    vacante.tipo_contrato, 'Relacion de dependencia'
                )
                ET.SubElement(job, 'EducationLevel').text = EDUCACION_A_BUMERAN.get(
                    vacante.educacion_minima, 'No requiere'
                )
                ET.SubElement(job, 'ExperienceYears').text = str(vacante.experiencia_minima)
                count += 1
            except Exception as exc:
                errores.append({'vacante_id': vacante.pk, 'error': str(exc)})

        return {
            'ok': True,
            'plataforma': self.PLATAFORMA,
            'xml': _prettify_xml(root),
            'count': count,
            'errores': errores,
        }


# ══════════════════════════════════════════════════════════════
# LINKEDIN JOBS PUBLISHER (API OAuth2)
# ══════════════════════════════════════════════════════════════

class LinkedInJobsPublisher:
    """
    Publica vacantes en LinkedIn Jobs via API REST OAuth2.

    Endpoint: POST https://api.linkedin.com/v2/simpleJobPostings

    Autenticacion:
        - Requiere access_token OAuth2 con scope: w_member_social, r_emailaddress
        - El token se obtiene via OAuth2 Authorization Code Flow
        - Guardar en ConfiguracionSistema: linkedin_access_token, linkedin_organization_id

    Documentacion LinkedIn:
        https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/reference/

    IMPORTANTE:
        - La API de LinkedIn Jobs requiere cuenta de empresa verificada y aprobacion de partnership
        - Para ambientes de prueba usar el sandbox de LinkedIn Developer Portal
        - access_token tiene duracion limitada (60 dias) — implementar refresh a futuro
    """

    PLATAFORMA = 'LINKEDIN'
    API_BASE    = 'https://api.linkedin.com/v2'
    ENDPOINT    = '/simpleJobPostings'

    def publicar_vacante(self, vacante, access_token: str, organization_id: str) -> dict:
        """
        Publica una vacante en LinkedIn Jobs via API REST.

        Args:
            vacante:         instancia de reclutamiento.models.Vacante
            access_token:    token OAuth2 Bearer de LinkedIn
            organization_id: ID de la empresa en LinkedIn (ej: 'urn:li:organization:12345')

        Returns:
            dict con ok, job_posting_id (si exitoso), url_publicada, payload, respuesta_api, error
        """
        if not access_token:
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'error': 'access_token requerido. Configure linkedin_access_token en Configuracion del Sistema.',
                'payload': None,
                'respuesta_api': None,
                'url_publicada': '',
            }

        if not organization_id:
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'error': 'organization_id requerido. Configure linkedin_organization_id en Configuracion del Sistema.',
                'payload': None,
                'respuesta_api': None,
                'url_publicada': '',
            }

        payload = self._construir_payload(vacante, organization_id)

        try:
            respuesta = self._llamar_api(payload, access_token)
            job_id    = respuesta.get('id', '')
            url_pub   = f'https://www.linkedin.com/jobs/view/{job_id}/' if job_id else ''

            return {
                'ok': True,
                'plataforma': self.PLATAFORMA,
                'job_posting_id': job_id,
                'url_publicada': url_pub,
                'payload': payload,
                'respuesta_api': respuesta,
                'error': None,
                'mensaje': f'Vacante "{vacante.titulo}" publicada en LinkedIn Jobs. ID: {job_id}',
            }
        except LinkedInAPIError as exc:
            logger.error(
                'LinkedInJobsPublisher: error API para vacante %s — %s',
                vacante.pk, exc,
            )
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'job_posting_id': None,
                'url_publicada': '',
                'payload': payload,
                'respuesta_api': exc.respuesta,
                'error': str(exc),
            }
        except Exception as exc:
            logger.exception('LinkedInJobsPublisher: error inesperado para vacante %s', vacante.pk)
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'job_posting_id': None,
                'url_publicada': '',
                'payload': payload,
                'respuesta_api': None,
                'error': str(exc),
            }

    def _construir_payload(self, vacante, organization_id: str) -> dict:
        """
        Construye el payload JSON segun la especificacion de LinkedIn Simple Job Postings API.
        Ref: https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/reference/
        """
        # Descripcion enriquecida en HTML (LinkedIn acepta HTML basico)
        descripcion_html = self._construir_descripcion_html(vacante)

        payload = {
            'source': 'JOBS_PREMIUM_OFFLINE',
            'integrationContext': f'urn:li:organization:{organization_id.lstrip("urn:li:organization:")}',
            'companyApplyUrl': '',                          # URL de postulacion en portal propio (opcional)
            'description': {
                'text': descripcion_html,
            },
            'employmentStatus':  CONTRATO_A_LINKEDIN.get(vacante.tipo_contrato, 'FULL_TIME'),
            'experienceLevel':   _linkedin_seniority(vacante.experiencia_minima),
            'title':             _safe_str(vacante.titulo),
            'location':          'Lima, Peru',
            'workplaceType':     'ONSITE',                  # ONSITE | REMOTE | HYBRID — configurable a futuro
        }

        # Salario (campo opcional en LinkedIn)
        if vacante.salario_min or vacante.salario_max:
            payload['compensation'] = {
                'compensationType': 'SALARY',
                'currency':         vacante.moneda,
            }
            if vacante.salario_min:
                payload['compensation']['minimumCompensation'] = float(vacante.salario_min)
            if vacante.salario_max:
                payload['compensation']['maximumCompensation'] = float(vacante.salario_max)
            payload['compensation']['compensationPeriod'] = 'MONTHLY'

        return payload

    def _construir_descripcion_html(self, vacante) -> str:
        """Genera descripcion HTML enriquecida para LinkedIn."""
        partes = []

        if vacante.descripcion:
            partes.append(f'<p>{_safe_str(vacante.descripcion)}</p>')

        if vacante.requisitos:
            partes.append('<h3>Requisitos</h3>')
            # Convertir lineas separadas en lista HTML
            lineas = [l.strip() for l in vacante.requisitos.split('\n') if l.strip()]
            if lineas:
                items_html = ''.join(f'<li>{l}</li>' for l in lineas)
                partes.append(f'<ul>{items_html}</ul>')
            else:
                partes.append(f'<p>{_safe_str(vacante.requisitos)}</p>')

        if vacante.experiencia_minima:
            partes.append(
                f'<p><strong>Experiencia minima:</strong> {vacante.experiencia_minima} anio(s)</p>'
            )

        educacion_display = dict(vacante.__class__.EDUCACION_CHOICES).get(
            vacante.educacion_minima, ''
        )
        if educacion_display and vacante.educacion_minima != 'NO_REQUERIDO':
            partes.append(
                f'<p><strong>Nivel educativo:</strong> {educacion_display}</p>'
            )

        return ''.join(partes) if partes else _safe_str(vacante.descripcion)

    def _llamar_api(self, payload: dict, access_token: str) -> dict:
        """
        Realiza el POST a la API de LinkedIn Jobs.

        Usa urllib (stdlib) para evitar dependencia extra de requests.
        En produccion puede reemplazarse por requests o httpx si ya estan instalados.

        Raises:
            LinkedInAPIError: si la API responde con error HTTP
        """
        url     = f'{self.API_BASE}{self.ENDPOINT}'
        data    = json.dumps(payload).encode('utf-8')
        headers = {
            'Authorization':  f'Bearer {access_token}',
            'Content-Type':   'application/json',
            'X-Restli-Protocol-Version': '2.0.0',
            'LinkedIn-Version': '202306',
        }

        req = urllib.request.Request(url, data=data, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body      = resp.read().decode('utf-8')
                respuesta = json.loads(body) if body else {}
                return respuesta
        except urllib.error.HTTPError as exc:
            cuerpo = ''
            try:
                cuerpo = exc.read().decode('utf-8')
            except Exception:
                pass
            raise LinkedInAPIError(
                f'LinkedIn API HTTP {exc.code}: {exc.reason}. Detalle: {cuerpo}',
                respuesta=cuerpo,
            ) from exc
        except urllib.error.URLError as exc:
            raise LinkedInAPIError(
                f'Error de conexion a LinkedIn API: {exc.reason}',
                respuesta=None,
            ) from exc

    def generar_payload_preview(self, vacante, organization_id: str = 'ORG_ID') -> dict:
        """
        Genera el payload sin llamar a la API — util para preview y debug.

        Args:
            vacante: instancia de Vacante
            organization_id: ID de organizacion (puede ser dummy para preview)

        Returns:
            dict con payload JSON listo para revisar
        """
        return {
            'ok': True,
            'plataforma': self.PLATAFORMA,
            'payload': self._construir_payload(vacante, organization_id),
            'mensaje': 'Preview generado (sin publicar). Configure access_token para publicar.',
            'error': None,
        }


class LinkedInAPIError(Exception):
    """Error especifico de la API de LinkedIn Jobs."""

    def __init__(self, message: str, respuesta=None):
        super().__init__(message)
        self.respuesta = respuesta


# ══════════════════════════════════════════════════════════════
# PORTAL EMPLEO PROPIO
# ══════════════════════════════════════════════════════════════

class PortalPropio:
    """
    Verificador del estado de publicacion en el portal de empleo interno.

    El portal ya existe en reclutamiento/views.py (portal_empleo, portal_postular).
    Esta clase verifica el estado y genera la URL de la vacante en el portal.
    """

    PLATAFORMA = 'PORTAL'

    def publicar_vacante(self, vacante, base_url: str = '') -> dict:
        """
        Verifica y/o activa la publicacion de una vacante en el portal propio.

        Para publicar en el portal, la vacante debe tener:
            - publica = True
            - estado en ['PUBLICADA', 'EN_PROCESO']

        Esta funcion activa el flag publica si no lo esta y el estado es correcto.

        Args:
            vacante:  instancia de Vacante
            base_url: URL base del sitio (ej: 'https://erp.miempresa.pe')

        Returns:
            dict con ok, url_publicada, mensaje, error
        """
        try:
            cambios = []

            if not vacante.publica:
                vacante.publica = True
                cambios.append('Se activo visibilidad publica')

            if vacante.estado == 'BORRADOR':
                vacante.estado = 'PUBLICADA'
                if not vacante.fecha_publicacion:
                    vacante.fecha_publicacion = date.today()
                cambios.append('Estado cambiado a PUBLICADA')

            vacante.save(update_fields=['publica', 'estado', 'fecha_publicacion'])

            url_pub = f'{base_url.rstrip("/")}/reclutamiento/empleo/{vacante.pk}/' if base_url else f'/reclutamiento/empleo/{vacante.pk}/'

            mensaje = f'Vacante "{vacante.titulo}" disponible en el portal de empleo.'
            if cambios:
                mensaje += ' Cambios: ' + ', '.join(cambios) + '.'

            return {
                'ok': True,
                'plataforma': self.PLATAFORMA,
                'url_publicada': url_pub,
                'mensaje': mensaje,
                'error': None,
                'cambios': cambios,
            }

        except Exception as exc:
            logger.exception('PortalPropio: error publicando vacante %s', vacante.pk)
            return {
                'ok': False,
                'plataforma': self.PLATAFORMA,
                'url_publicada': '',
                'mensaje': '',
                'error': str(exc),
                'cambios': [],
            }

    def get_url_vacante(self, vacante, base_url: str = '') -> str:
        """Retorna la URL del portal empleo para la vacante."""
        return f'{base_url.rstrip("/")}/reclutamiento/empleo/{vacante.pk}/'


# ══════════════════════════════════════════════════════════════
# TELEGRAM BOT PUBLISHER
# ══════════════════════════════════════════════════════════════

class TelegramJobPublisher:
    """
    Publica ofertas de empleo en un canal de Telegram via Bot API.

    API oficial: https://core.telegram.org/bots/api#sendmessage
    Endpoint:    POST https://api.telegram.org/bot{TOKEN}/sendMessage

    Ventajas sobre otras plataformas:
      - API gratuita, sin aprobación ni costo por mensaje
      - Alcance inmediato (push notification a todos los suscriptores)
      - Muy popular en Perú para grupos y canales de empleos
      - Soporta formato HTML/Markdown para mensajes enriquecidos
      - No tiene límites de publicación relevantes para RR.HH.

    Configuración requerida:
      1. Crear un bot en Telegram vía @BotFather → obtener BOT_TOKEN
      2. Crear un canal público (ej: @empleos_miempresa) o grupo
      3. Agregar el bot como administrador del canal con permiso de publicar
      4. Obtener CHAT_ID:
         - Canal público:  "@nombre_canal" (ej: "@empleos_acme")
         - Canal privado:  "-100XXXXXXXXXX" (usar @userinfobot para obtener el ID)
      5. Guardar BOT_TOKEN y CHAT_ID en Configuración del Sistema

    Formato del mensaje publicado:
      🔔 *NUEVA OPORTUNIDAD LABORAL*
      📌 Puesto: NOMBRE DEL PUESTO
      🏢 Área: AREA
      📍 Modalidad: MODALIDAD — Tipo: TIPO CONTRATO
      💰 Rango salarial: S/ XXXX – S/ YYYY (si aplica)
      📋 Descripción breve...
      ✅ Requisitos: experiencia, educación
      📩 Postular en: [LINK AL PORTAL]
      📅 Cierre: FECHA LÍMITE
    """

    PLATAFORMA  = 'TELEGRAM'
    API_BASE    = 'https://api.telegram.org'
    TIMEOUT_SEG = 10

    def publicar_vacante(
        self,
        vacante,
        bot_token: str = '',
        chat_id: str   = '',
        portal_url: str = '',
    ) -> dict:
        """
        Envía el mensaje de la oferta al canal Telegram.

        Args:
            vacante:    instancia de Vacante
            bot_token:  token del bot Telegram (ej: "123456:ABC-DEF1234...")
            chat_id:    ID del canal (ej: "@empleos_empresa" o "-1001234567890")
            portal_url: URL pública al portal de empleo (para incluir en el mensaje)

        Returns:
            dict estandarizado: {'ok', 'plataforma', 'mensaje', 'url_publicada', 'error', 'message_id'}
        """
        import json
        import urllib.request
        import urllib.error

        if not bot_token:
            return {
                'ok':          False,
                'plataforma':  self.PLATAFORMA,
                'error':       'BOT TOKEN requerido. Configúralo en Configuración → Integraciones → Telegram.',
                'mensaje':     '',
                'url_publicada': '',
            }

        if not chat_id:
            return {
                'ok':          False,
                'plataforma':  self.PLATAFORMA,
                'error':       'CHAT ID requerido. Puede ser "@nombre_canal" o el ID numérico del grupo/canal.',
                'mensaje':     '',
                'url_publicada': '',
            }

        texto = self._construir_mensaje(vacante, portal_url)
        payload = {
            'chat_id':    chat_id,
            'text':       texto,
            'parse_mode': 'HTML',
            'disable_web_page_preview': False,
        }

        endpoint = f'{self.API_BASE}/bot{bot_token}/sendMessage'

        try:
            body = json.dumps(payload).encode('utf-8')
            req  = urllib.request.Request(
                endpoint,
                data    = body,
                headers = {'Content-Type': 'application/json'},
                method  = 'POST',
            )
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SEG) as resp:
                data       = json.loads(resp.read().decode('utf-8'))
                message_id = data.get('result', {}).get('message_id')
                # URL del mensaje en el canal (solo funciona con canales públicos)
                canal_limpio = chat_id.lstrip('@')
                url_msg = (
                    f'https://t.me/{canal_limpio}/{message_id}'
                    if not chat_id.startswith('-') else ''
                )
                return {
                    'ok':          True,
                    'plataforma':  self.PLATAFORMA,
                    'mensaje':     f'Oferta publicada en Telegram. Message ID: {message_id}',
                    'url_publicada': url_msg,
                    'message_id':  message_id,
                    'respuesta_api': data,
                    'error':       None,
                    'texto_enviado': texto,
                }

        except urllib.error.HTTPError as exc:
            try:
                err_body = json.loads(exc.read().decode('utf-8'))
                descripcion = err_body.get('description', str(exc))
            except Exception:
                descripcion = str(exc)
            return {
                'ok':          False,
                'plataforma':  self.PLATAFORMA,
                'error':       f'Telegram API Error {exc.code}: {descripcion}',
                'mensaje':     '',
                'url_publicada': '',
            }
        except Exception as exc:
            return {
                'ok':          False,
                'plataforma':  self.PLATAFORMA,
                'error':       f'Error de conexión: {exc}',
                'mensaje':     '',
                'url_publicada': '',
            }

    def _construir_mensaje(self, vacante, portal_url: str = '') -> str:
        """
        Construye el texto HTML del mensaje para Telegram.
        Usa etiquetas HTML básicas soportadas por Telegram: <b>, <i>, <a>, <code>.
        """
        lineas = ['🔔 <b>NUEVA OPORTUNIDAD LABORAL</b>']
        lineas.append('')
        lineas.append(f'📌 <b>{vacante.titulo}</b>')

        if hasattr(vacante, 'area') and vacante.area:
            lineas.append(f'🏢 Área: {vacante.area.nombre}')

        # Modalidad / tipo contrato
        modalidad = getattr(vacante, 'get_modalidad_display', lambda: '')()
        tipo_cont = getattr(vacante, 'get_tipo_contrato_display', lambda: '')()
        if modalidad or tipo_cont:
            partes = [p for p in [modalidad, tipo_cont] if p]
            lineas.append(f'📍 {" — ".join(partes)}')

        # Rango salarial
        sal_min = getattr(vacante, 'salario_minimo', None)
        sal_max = getattr(vacante, 'salario_maximo', None)
        if sal_min and sal_max:
            lineas.append(f'💰 S/ {sal_min:,.0f} – S/ {sal_max:,.0f}')
        elif sal_min:
            lineas.append(f'💰 Desde S/ {sal_min:,.0f}')

        # Descripción (primeras 200 chars)
        desc = getattr(vacante, 'descripcion', '') or ''
        if desc:
            desc_corta = desc[:220].strip()
            if len(desc) > 220:
                desc_corta += '…'
            lineas.append('')
            lineas.append(f'📋 {desc_corta}')

        # Requisitos
        req_edu  = getattr(vacante, 'get_educacion_display', lambda: '')()
        req_exp  = getattr(vacante, 'experiencia_minima', None)
        if req_edu or req_exp:
            lineas.append('')
            req_txt = []
            if req_edu and req_edu != 'No requerido':
                req_txt.append(req_edu)
            if req_exp:
                req_txt.append(f'{req_exp} año(s) de experiencia')
            if req_txt:
                lineas.append(f'✅ Requisitos: {", ".join(req_txt)}')

        # Link al portal
        lineas.append('')
        if portal_url:
            lineas.append(f'📩 <a href="{portal_url}">Postular aquí</a>')
        else:
            lineas.append('📩 Envía tu CV al área de Recursos Humanos')

        # Fecha límite
        fecha_lim = getattr(vacante, 'fecha_limite', None)
        if fecha_lim:
            lineas.append(f'📅 Cierre: <b>{fecha_lim.strftime("%d/%m/%Y")}</b>')

        lineas.append('')
        lineas.append('#empleo #trabajo #peru #rrhh')

        return '\n'.join(lineas)

    def generar_preview(self, vacante, portal_url: str = '') -> dict:
        """Genera preview del mensaje sin enviarlo (para mostrar en UI)."""
        return {
            'ok':          True,
            'plataforma':  self.PLATAFORMA,
            'mensaje':     'Vista previa generada (no enviado — falta token o chat_id)',
            'url_publicada': '',
            'error':       None,
            'es_preview':  True,
            'texto_enviado': self._construir_mensaje(vacante, portal_url),
        }


# ══════════════════════════════════════════════════════════════
# WHATSAPP BUSINESS CLOUD API PUBLISHER
# ══════════════════════════════════════════════════════════════

class WhatsAppBusinessPublisher:
    """
    Publica ofertas de empleo via WhatsApp Business Cloud API (Meta Graph API).

    API oficial: https://developers.facebook.com/docs/whatsapp/cloud-api/messages/text-messages
    Endpoint:    POST https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages
    Auth:        Bearer {ACCESS_TOKEN}

    Notas:
        - WhatsApp Business API envia a numeros individuales (no canales).
        - Soporta multiples destinatarios separados por coma.
        - El numero receptor debe haber iniciado conversacion o usar template aprobado.
        - Para job posting masivo: registrar candidatos con opt-in.

    Configuracion en ConfiguracionSistema:
        whatsapp_phone_number_id: ID del numero en Meta Developer Console.
        whatsapp_access_token:    Token permanente de la Meta Business App.
        whatsapp_to_number:       Numero(s) en formato 51XXXXXXXXX, separados por coma.
    """

    PLATAFORMA  = "WHATSAPP"
    API_BASE    = "https://graph.facebook.com/v18.0"
    TIMEOUT_SEG = 15

    def publicar_vacante(
        self,
        vacante,
        phone_number_id="",
        access_token="",
        to_numbers="",
        portal_url="",
    ):
        import json
        import urllib.request
        import urllib.error

        if not phone_number_id:
            return {
                "ok": False, "plataforma": self.PLATAFORMA,
                "error": "PHONE_NUMBER_ID requerido. Configuralo en Configuracion > Integraciones > WhatsApp.",
                "mensaje": "", "url_publicada": "",
            }
        if not access_token:
            return {
                "ok": False, "plataforma": self.PLATAFORMA,
                "error": "ACCESS TOKEN requerido. Obtenerlo en Meta Business Developer Console.",
                "mensaje": "", "url_publicada": "",
            }

        numeros = [n.strip() for n in to_numbers.split(",") if n.strip()]
        if not numeros:
            return {
                "ok": False, "plataforma": self.PLATAFORMA,
                "error": "Debe configurar al menos un numero de destino (formato: 51XXXXXXXXX).",
                "mensaje": "", "url_publicada": "",
            }

        texto    = self._construir_mensaje(vacante, portal_url)
        endpoint = f"{self.API_BASE}/{phone_number_id}/messages"
        headers  = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {access_token}",
        }

        enviados = []
        fallidos  = []

        for numero in numeros:
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type":    "individual",
                "to":                numero,
                "type":              "text",
                "text": {"preview_url": True, "body": texto},
            }
            try:
                body = json.dumps(payload).encode("utf-8")
                req  = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
                with urllib.request.urlopen(req, timeout=self.TIMEOUT_SEG) as resp:
                    data   = json.loads(resp.read().decode("utf-8"))
                    msg_id = data.get("messages", [{}])[0].get("id", "") if data.get("messages") else ""
                    enviados.append({"numero": numero, "message_id": msg_id})
            except urllib.error.HTTPError as exc:
                try:
                    err_body = json.loads(exc.read().decode("utf-8"))
                    desc = err_body.get("error", {}).get("message", str(exc))
                except Exception:
                    desc = str(exc)
                fallidos.append({"numero": numero, "error": f"HTTP {exc.code}: {desc}"})
            except Exception as exc:
                fallidos.append({"numero": numero, "error": str(exc)})

        ok = len(enviados) > 0
        if ok and not fallidos:
            mensaje = f"Oferta enviada a {len(enviados)} numero(s) de WhatsApp."
        elif ok:
            mensaje = (
                f"Enviado a {len(enviados)} numero(s). "
                f"Fallo en {len(fallidos)}: {', '.join(f['numero'] for f in fallidos)}."
            )
        else:
            mensaje = f"Todos los envios fallaron ({len(fallidos)} numero(s))."

        return {
            "ok":          ok,
            "plataforma":  self.PLATAFORMA,
            "mensaje":     mensaje,
            "url_publicada": "",
            "error":       None if ok else mensaje,
            "enviados":    enviados,
            "fallidos":    fallidos,
            "texto_enviado": texto,
            "respuesta_api": {"enviados": enviados, "fallidos": fallidos},
        }

    def _construir_mensaje(self, vacante, portal_url=""):
        """Texto WhatsApp: usa *negrita* (no HTML)."""
        lineas = ["🔔 *NUEVA OPORTUNIDAD LABORAL*", ""]
        lineas.append(f"📌 *{vacante.titulo}*")

        if hasattr(vacante, "area") and vacante.area:
            lineas.append(f"🏢 {vacante.area.nombre}")
        if getattr(vacante, "modalidad", None):
            lineas.append(f"📍 {vacante.get_modalidad_display()}")

        if getattr(vacante, "salario_min", None) or getattr(vacante, "salario_max", None):
            partes = []
            if vacante.salario_min:
                partes.append(f"{vacante.moneda} {vacante.salario_min:,.0f}")
            if vacante.salario_max:
                partes.append(f"{vacante.moneda} {vacante.salario_max:,.0f}")
            lineas.append(f"💰 {' - '.join(partes)}")
        else:
            lineas.append("💰 A convenir")

        if getattr(vacante, "descripcion", None):
            desc = vacante.descripcion.strip()
            if len(desc) > 280:
                desc = desc[:277] + "..."
            lineas += ["", "📋 *Descripcion:*", desc]

        if getattr(vacante, "requisitos", None):
            req = vacante.requisitos.strip()
            if len(req) > 220:
                req = req[:217] + "..."
            lineas += ["", "✅ *Requisitos:*", req]

        if portal_url:
            lineas += ["", f"📩 *Postular:* {portal_url}"]

        if getattr(vacante, "fecha_limite", None):
            lineas.append(f"📅 Cierre: {vacante.fecha_limite.strftime('%d/%m/%Y')}")

        lineas += ["", "#empleo #trabajo #peru #rrhh"]
        return "\n".join(lineas)

    def generar_preview(self, vacante, portal_url=""):
        """Preview sin enviar (sin credenciales configuradas)."""
        return {
            "ok":          True,
            "plataforma":  self.PLATAFORMA,
            "mensaje":     "Vista previa generada (no enviado — falta phone_number_id o access_token)",
            "url_publicada": "",
            "error":       None,
            "es_preview":  True,
            "texto_enviado": self._construir_mensaje(vacante, portal_url),
        }
