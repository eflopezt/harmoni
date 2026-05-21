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
