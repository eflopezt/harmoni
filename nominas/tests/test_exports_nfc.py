"""
Regresión: los archivos planos para SUNAT (PLAME, T-Registro) se codifican a
latin-1. Si un nombre trae tildes en forma NFD (acento combinante), latin-1 las
reemplaza por '?' y el archivo declara mal el nombre. Los exportadores deben
normalizar a NFC antes de ensamblar cada fila.
"""
from nominas.exports_plame import _nfc as _nfc_plame
from nominas.exports_tregistro import _nfc as _nfc_treg


def _nfd(s):
    """Devuelve la forma NFD (descompuesta) de un texto."""
    import unicodedata
    return unicodedata.normalize('NFD', s)


class TestNFCExportadores:

    def test_nfc_plame_combina_tildes(self):
        nfd = _nfd('José Núñez')          # 'e'+◌́, 'n'+◌̃, 'u'+◌́
        assert _nfc_plame(nfd) == 'José Núñez'

    def test_nfc_plame_encodea_latin1_sin_perdida(self):
        nfd = _nfd('MARÍA PEÑA')
        # sin NFC la forma descompuesta pierde el acento a '?' en latin-1
        assert b'?' in nfd.encode('latin-1', errors='replace')
        # con NFC, latin-1 conserva todos los caracteres acentuados
        assert _nfc_plame(nfd).encode('latin-1', errors='replace') == \
            'MARÍA PEÑA'.encode('latin-1')

    def test_nfc_idempotente_para_texto_ya_nfc(self):
        ya_nfc = 'José'
        assert _nfc_plame(ya_nfc) == ya_nfc

    def test_nfc_tregistro_combina_tildes(self):
        nfd = _nfd('Andrés Gutiérrez')
        assert _nfc_treg(nfd) == 'Andrés Gutiérrez'

    def test_nfc_no_altera_pipes_ni_numeros(self):
        fila = _nfd('01|12345678|JOSÉ|3000.00')
        out = _nfc_plame(fila)
        assert out == '01|12345678|JOSÉ|3000.00'
        assert out.count('|') == 3
