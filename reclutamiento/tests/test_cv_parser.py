"""
Tests para CV parser (adaptado de NexoTalent).
"""
import os
import tempfile

import pytest

from reclutamiento.cv_parser import (
    parse_cv,
    extract_text_from_file,
    parse_cv_from_file,
    SKILLS_CATALOG,
)


SAMPLE_CV = """
MARIA QUISPE LOPEZ

Mesera Senior · 5 años en gastronomía
Email: maria.quispe@ejemplo.com
Teléfono: 987654321
DNI: 71234567
Lima, Perú

EXPERIENCIA LABORAL

Mar 2022 - Actualidad: Restaurante Insignia
Mesera Senior. Atención al cliente, protocolo de servicio,
manejo de caja. Cata de vinos básica.

Ene 2019 - Feb 2022: Café del Olivar
Mesera. Manipulación de alimentos certificada.
Inglés intermedio para atender turistas.

EDUCACIÓN

2017-2018: Cibertec - Técnico en Gastronomía
Curso de Atención al Cliente

HABILIDADES
- Atención al cliente
- Manipulación de alimentos
- Caja
- Cata de vinos
- Inglés intermedio
"""


class TestParseCV:
    def test_parse_text_completo(self):
        result = parse_cv(SAMPLE_CV)
        assert result['email'] == 'maria.quispe@ejemplo.com'
        assert result['telefono'] == '987654321'
        assert result['dni'] == '71234567'
        assert 'MARIA QUISPE LOPEZ' in result['nombre_completo']
        assert result['anios_experiencia'] > 0
        assert result['tiene_experiencia']
        assert result['tiene_educacion']

    def test_parse_skills_detecta(self):
        result = parse_cv(SAMPLE_CV)
        skills = result['skills']
        assert 'atencion al cliente' in skills
        assert 'manipulacion de alimentos' in skills
        assert 'cata de vinos' in skills
        assert 'ingles intermedio' in skills

    def test_parse_idiomas(self):
        result = parse_cv(SAMPLE_CV)
        assert 'ingles intermedio' in result['idiomas']

    def test_parse_anios_experiencia(self):
        result = parse_cv(SAMPLE_CV)
        # 2017 → ahora son al menos 5 años
        assert result['anios_experiencia'] >= 5

    def test_parse_texto_vacio(self):
        result = parse_cv('')
        assert result['email'] == ''
        assert result['telefono'] == ''
        assert result['anios_experiencia'] == 0
        assert result['skills'] == []
        assert result['longitud_texto'] == 0

    def test_parse_solo_email(self):
        result = parse_cv('contacto: hola@empresa.com')
        assert result['email'] == 'hola@empresa.com'
        assert result['telefono'] == ''

    def test_parse_telefono_formato_internacional(self):
        result = parse_cv('Teléfono: +51 987 654 321')
        assert '987' in result['telefono']

    def test_parse_dni_excluye_años(self):
        # No debe confundir años (20240101) con DNI
        result = parse_cv('Vivió en 2024. DNI: 71234567')
        assert result['dni'] == '71234567'


class TestExtractText:
    def test_extract_text_archivo_inexistente(self):
        result = extract_text_from_file('/path/no/existe.pdf')
        assert result == ''

    def test_extract_text_extension_no_soportada(self):
        result = extract_text_from_file('/tmp/cv.xyz')
        assert result == ''

    def test_extract_txt(self):
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write('Hola mundo desde TXT')
            path = tmp.name
        try:
            text = extract_text_from_file(path)
            assert 'Hola mundo' in text
        finally:
            os.unlink(path)

    def test_parse_cv_from_file_pipeline_completo(self):
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(SAMPLE_CV)
            path = tmp.name
        try:
            result = parse_cv_from_file(path)
            assert result['email'] == 'maria.quispe@ejemplo.com'
            assert 'texto_extraido' in result
            assert len(result['texto_extraido']) > 0
        finally:
            os.unlink(path)


class TestSkillsCatalog:
    def test_catalog_tiene_skills_gastronomia(self):
        assert 'cocina_caliente' in SKILLS_CATALOG
        assert 'sommelier' in SKILLS_CATALOG
        assert 'bartender' in SKILLS_CATALOG

    def test_catalog_tiene_idiomas(self):
        assert 'ingles avanzado' in SKILLS_CATALOG
        assert 'portugues' in SKILLS_CATALOG

    def test_catalog_tiene_skills_admin(self):
        assert 'planillas' in SKILLS_CATALOG
        assert 'sunat' in SKILLS_CATALOG


class TestExtraerExperiencias:
    def test_extrae_experiencias_basicas(self):
        from reclutamiento.cv_parser import extraer_experiencias
        exps = extraer_experiencias(SAMPLE_CV)
        # SAMPLE_CV tiene 2 experiencias: Mar 2022 - Actualidad y Ene 2019 - Feb 2022
        assert len(exps) >= 2
        # La primera debe tener fecha inicio "Mar 2022"
        assert exps[0]['año_inicio'] == 2022

    def test_calcula_año_actualidad(self):
        from reclutamiento.cv_parser import extraer_experiencias
        from datetime import date
        exps = extraer_experiencias(SAMPLE_CV)
        if exps and 'actualidad' in exps[0]['fecha_fin'].lower():
            assert exps[0]['año_fin'] == date.today().year

    def test_sin_seccion_experiencia_devuelve_vacio(self):
        from reclutamiento.cv_parser import extraer_experiencias
        exps = extraer_experiencias("Solo texto sin headers reconocidos")
        assert exps == []


class TestExtraerEducacion:
    def test_extrae_educacion(self):
        from reclutamiento.cv_parser import extraer_educacion
        items = extraer_educacion(SAMPLE_CV)
        # SAMPLE_CV tiene "2017-2018: Cibertec - Técnico en Gastronomía"
        assert len(items) >= 1
        # El primer año debe ser 2017
        assert any(item['año'] == 2017 for item in items)

    def test_sin_seccion_educacion(self):
        from reclutamiento.cv_parser import extraer_educacion
        items = extraer_educacion("Solo texto sin headers")
        assert items == []


class TestParseCVCompleto:
    def test_parse_cv_from_file_incluye_estructura(self):
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(SAMPLE_CV)
            path = tmp.name
        try:
            result = parse_cv_from_file(path)
            # Ahora incluye experiencias y educacion_items
            assert 'experiencias' in result
            assert 'educacion_items' in result
            assert len(result['experiencias']) >= 1
        finally:
            os.unlink(path)


# ────────────────────────────────────────────────────────────────
# FASE 1 — Segmentación section-aware
# ────────────────────────────────────────────────────────────────

CV_CON_FECHA_NACIMIENTO = """
JUAN PEREZ GOMEZ

DATOS PERSONALES
Nombre: Juan Perez Gomez
Fecha de nacimiento: 14/03/1990
DNI: 71234567
Email: juan@test.com
Teléfono: 987654321
Lima, Perú

EXPERIENCIA LABORAL

Mar 2018 - Ene 2022: Restaurante ABC
Cocinero principal. Manejo de cocina caliente.

Feb 2022 - Actualidad: Restaurante XYZ
Sous Chef. Coordinación de equipo.

EDUCACIÓN
2010-2014: Universidad Continental - Administración

HABILIDADES
- Cocina caliente
- Inventarios
"""


class TestSegmentarSecciones:
    """Fase 1.1: segmentación del CV por headers."""

    def test_segmenta_secciones_comunes(self):
        from reclutamiento.cv_parser import segmentar_secciones
        secciones = segmentar_secciones(CV_CON_FECHA_NACIMIENTO)
        assert 'datos_personales' in secciones
        assert 'experiencia' in secciones
        assert 'educacion' in secciones
        assert 'skills' in secciones
        # Cada sección no debe contener su header como contenido
        assert 'DATOS PERSONALES' not in secciones['datos_personales']
        assert 'EXPERIENCIA LABORAL' not in secciones['experiencia']

    def test_seccion_experiencia_no_contiene_datos_personales(self):
        from reclutamiento.cv_parser import segmentar_secciones
        secciones = segmentar_secciones(CV_CON_FECHA_NACIMIENTO)
        # La fecha de nacimiento NO debe estar en la sección experiencia
        assert '14/03/1990' not in secciones.get('experiencia', '')
        assert 'Fecha de nacimiento' not in secciones.get('experiencia', '')

    def test_secciones_detectadas_en_parsed(self):
        result = parse_cv(CV_CON_FECHA_NACIMIENTO)
        secs = result.get('secciones_detectadas', [])
        assert 'datos_personales' in secs
        assert 'experiencia' in secs


# ────────────────────────────────────────────────────────────────
# Bug fix principal: fecha de nacimiento != inicio de experiencia
# ────────────────────────────────────────────────────────────────

class TestFechaNacimientoNoContamina:
    """Regresión del bug reportado por cliente: el parser tomaba la
    fecha de nacimiento como inicio de experiencia laboral."""

    def test_fecha_nacimiento_extraida_separadamente(self):
        result = parse_cv(CV_CON_FECHA_NACIMIENTO)
        assert result['fecha_nacimiento'] == '14/03/1990'

    def test_fecha_min_NO_es_año_nacimiento(self):
        result = parse_cv(CV_CON_FECHA_NACIMIENTO)
        # fecha_min debe ser 2018 (inicio de la primera experiencia),
        # NO 1990 (año de nacimiento)
        assert result['fecha_min'] != 1990
        assert result['fecha_min'] == 2018

    def test_anios_experiencia_no_incluye_nacimiento(self):
        result = parse_cv(CV_CON_FECHA_NACIMIENTO)
        # Si tomara 1990, daría ~36. Real: 2018-2026 ~= 8.
        assert result['anios_experiencia'] <= 12
        assert result['anios_experiencia'] >= 5

    def test_experiencias_estructuradas_no_incluyen_nacimiento(self):
        from reclutamiento.cv_parser import extraer_experiencias
        exps = extraer_experiencias(CV_CON_FECHA_NACIMIENTO)
        años_inicio = [e.get('año_inicio') for e in exps]
        assert 1990 not in años_inicio
        assert 2018 in años_inicio

    def test_cv_con_solo_año_nacimiento(self):
        """Variante: fecha de nacimiento sólo como año."""
        cv = """
        MARIA LOPEZ
        DATOS PERSONALES
        Nacimiento: 1985
        Email: maria@x.com

        EXPERIENCIA LABORAL
        2020 - 2023: Empresa A — Analista
        2023 - Actualidad: Empresa B — Senior
        """
        result = parse_cv(cv)
        assert result['fecha_min'] != 1985
        assert result['anios_experiencia'] < 20

    def test_etiqueta_nacimiento_inline_excluida(self):
        """Aún sin sección, si hay etiqueta 'Nacimiento:' debe excluirse."""
        cv = """
        Pedro Ruiz
        Nacimiento: 12/06/1988
        Email: pedro@x.com

        Experiencia:
        2019 - 2024 Empresa Z — Cargo
        """
        result = parse_cv(cv)
        assert result['fecha_nacimiento'] == '12/06/1988'
        # 2019 a 2024 = 5; si tomara 1988 daría >30
        assert result['anios_experiencia'] <= 10


# ────────────────────────────────────────────────────────────────
# FASE 2 — Enriquecimiento con IA (mockeado)
# ────────────────────────────────────────────────────────────────

class TestEnriquecimientoIA:
    """FASE 2 del pipeline: el LLM sólo rellena campos vacíos
    y se valida contra el texto original."""

    def test_ia_no_se_llama_si_todo_completo(self):
        """Si el parsing local extrajo todo, el LLM no debe ejecutarse."""
        import tempfile
        called = {'count': 0}

        def fake_llm(texto, parsed):
            called['count'] += 1
            return {}

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(SAMPLE_CV)
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm)
            # SAMPLE_CV ya da nombre, email y teléfono → no necesita IA
            assert called['count'] == 0
            assert result['ia_usada'] is False
            assert result['campos_de_ia'] == []
        finally:
            os.unlink(path)

    def test_ia_se_llama_si_falta_campo_critico(self):
        """Si falta email o teléfono, sí se llama al LLM."""
        import tempfile
        cv_sin_email = """
        JUAN PEREZ
        Cocinero con 5 años de experiencia
        Lima, Perú

        EXPERIENCIA LABORAL
        2020 - 2024 Restaurante X — Cocinero
        """
        called = {'count': 0}

        def fake_llm(texto, parsed):
            called['count'] += 1
            return {'email': 'juan@parser.com'}  # valor inventado

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(cv_sin_email)
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm)
            assert called['count'] == 1
            # Como el email NO aparece en el texto, debe rechazarse
            assert result['email'] == ''
            assert 'email' not in result['campos_de_ia']
        finally:
            os.unlink(path)

    def test_ia_rellena_solo_campos_vacios(self):
        """LLM no debe sobrescribir lo que ya extrajo el local."""
        import tempfile
        cv_solo_nombre = """
        ANA TORRES SILVA
        Datos personales:
        Email: ana.torres@empresa.pe
        Teléfono: 987-111-222

        EXPERIENCIA LABORAL
        2019 - 2024 Restaurante Y — Mesera
        """

        def fake_llm(texto, parsed):
            # LLM intenta sobreescribir email → debe ignorarse
            return {
                'email': 'otro@dominio.com',
                'fecha_nacimiento': '01/01/1990',  # no aparece, rechazar
            }

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(cv_solo_nombre)
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm)
            # Email original conservado
            assert result['email'] == 'ana.torres@empresa.pe'
            # Fecha de nacimiento inventada (no en texto) → rechazada
            assert result['fecha_nacimiento'] == ''
        finally:
            os.unlink(path)

    def test_ia_rellena_si_valor_si_aparece_en_texto(self):
        """LLM sí rellena un campo vacío si el valor SÍ aparece en el CV."""
        import tempfile
        # CV donde el nombre y email no se detectan por heurística simple
        cv_caotico = """
        ===========================
        ::HOJA DE VIDA::
        ===========================
        Contactar a Carlos Mendez Vargas vía carlos.mendez@empresa.com.pe
        Movil: +51 988 777 666

        EXPERIENCIA LABORAL
        2020 - 2025: Empresa A — Analista
        """

        def fake_llm(texto, parsed):
            return {
                'nombre_completo': 'Carlos Mendez Vargas',
                'email': 'carlos.mendez@empresa.com.pe',
            }

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(cv_caotico)
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm)
            # Email lo extrae el local (RE_EMAIL), pero podría no extraer
            # el nombre. El LLM lo aporta y SE VALIDA.
            assert 'Carlos Mendez Vargas' in (result['nombre_completo'] or '')
            # Email también debe estar (lo aporta el local o el LLM)
            assert 'carlos.mendez@empresa.com.pe' == result['email']
            assert result['ia_usada'] is True
            assert 'nombre_completo' in result['campos_de_ia']
        finally:
            os.unlink(path)

    def test_ia_excepcion_no_rompe_pipeline(self):
        """Si el LLM lanza excepción, el parsing local sigue siendo válido."""
        import tempfile

        def fake_llm_rompe(texto, parsed):
            raise RuntimeError('API down')

        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write('Solo texto sin datos\n2020 - 2024 Empresa\n')
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm_rompe)
            # Debe devolver el resultado local sin crashear
            assert 'texto_extraido' in result
            assert result['ia_usada'] is False
        finally:
            os.unlink(path)

    def test_ia_valida_dni_8_digitos(self):
        """El LLM no puede inventar un DNI."""
        import tempfile

        def fake_llm(texto, parsed):
            return {'dni': '99999999'}  # no aparece en texto

        cv = "Juan\nTeléfono: 987111222\n"
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w',
                                          delete=False, encoding='utf-8') as tmp:
            tmp.write(cv)
            path = tmp.name
        try:
            result = parse_cv_from_file(path, llm_caller=fake_llm)
            assert result['dni'] == ''
        finally:
            os.unlink(path)


# ────────────────────────────────────────────────────────────────
# Fecha de nacimiento — extracción aislada
# ────────────────────────────────────────────────────────────────

class TestExtraerFechaNacimiento:
    def test_label_fecha_de_nacimiento(self):
        from reclutamiento.cv_parser import extraer_fecha_nacimiento
        assert extraer_fecha_nacimiento('Fecha de nacimiento: 14/03/1990') == '14/03/1990'

    def test_label_nacimiento_corto(self):
        from reclutamiento.cv_parser import extraer_fecha_nacimiento
        assert extraer_fecha_nacimiento('Nacimiento: 05-12-1985') == '05-12-1985'

    def test_label_born_en_ingles(self):
        from reclutamiento.cv_parser import extraer_fecha_nacimiento
        assert extraer_fecha_nacimiento('Born: 22/07/1992') == '22/07/1992'

    def test_sin_label_no_extrae(self):
        """Una fecha suelta sin etiqueta de nacimiento no debe extraerse."""
        from reclutamiento.cv_parser import extraer_fecha_nacimiento
        # "Trabajé desde 14/03/2020" no debe confundirse con nacimiento
        assert extraer_fecha_nacimiento('Trabajé desde 14/03/2020') is None
