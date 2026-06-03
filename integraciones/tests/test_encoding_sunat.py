"""
Regresión: los archivos planos SUNAT/SBS (T-Registro, AFPNet, PLAME) se exportan
en latin-1 (ANSI), NO utf-8. Con utf-8 las tildes salían como bytes multibyte y el
sistema regulatorio las leía mal. El helper `_flat_sunat` normaliza a NFC y codifica
a latin-1. (EsSalud/planilla se exportan como CSV utf-8-sig para Excel → no usan esto.)
"""
import unicodedata

from integraciones.views import _flat_sunat


def _nfd(s):
    return unicodedata.normalize('NFD', s)


class TestFlatSunatEncoding:

    def test_devuelve_bytes_latin1(self):
        out = _flat_sunat('JOSE PEREZ')
        assert isinstance(out, bytes)
        assert out == b'JOSE PEREZ'

    def test_tildes_se_conservan_en_latin1(self):
        # 'é','ñ','ú' existen en latin-1 → se conservan (no '?')
        out = _flat_sunat('José Núñez')
        assert out == 'José Núñez'.encode('latin-1')
        assert b'?' not in out

    def test_normaliza_nfd_antes_de_codificar(self):
        # Forma descompuesta (acento combinante) → NFC → latin-1 sin pérdida
        out = _flat_sunat(_nfd('María Peña'))
        assert out == 'María Peña'.encode('latin-1')
        assert b'?' not in out

    def test_no_es_utf8_para_acentos(self):
        # En latin-1 'é' es 1 byte (0xE9); en utf-8 serían 2 (0xC3 0xA9).
        out = _flat_sunat('é')
        assert out == b'\xe9'
        assert out != 'é'.encode('utf-8')
