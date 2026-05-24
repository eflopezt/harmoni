"""Tests para la lógica de turno noche en sync_picados.

Caso validado en el plan Q2 2026: DNI 70919188 (LOPEZ TORRE) marcó entrada
22:30 día N y salida 03:15 día N+1. El sync debe consolidar ambos picados
en un único RegistroTareo del día N.

La función `_remapear_turno_noche` se prueba como unidad pura (sin BD) —
recibe el dict `grupos` que `sync_picados` construye en memoria.
"""
from datetime import date, datetime, time


from integraciones.services.synkro_sync import (
    CORTE_TURNO_NOCHE_AM,
    PIVOT_NOCHE_PM,
    _remapear_turno_noche,
)


class TestRemapearTurnoNoche:
    """Cobertura del re-agrupamiento de picados nocturnos."""

    def test_constantes_corte(self):
        """Documenta los valores de corte/pivot para detectar cambios sin querer."""
        assert CORTE_TURNO_NOCHE_AM == time(5, 30)
        assert PIVOT_NOCHE_PM == time(18, 0)

    def test_caso_lopez_torre_entrada_22_salida_03(self):
        """Caso validado: 22:30 día N + 03:15 día N+1 → ambos al día N."""
        ID_PERSONAL = 1234
        DIA_N = date(2026, 5, 20)
        DIA_N1 = date(2026, 5, 21)

        grupos = {
            (ID_PERSONAL, DIA_N): [datetime(2026, 5, 20, 22, 30)],
            (ID_PERSONAL, DIA_N1): [datetime(2026, 5, 21, 3, 15)],
        }

        remapeos = _remapear_turno_noche(grupos)

        assert remapeos == 1
        # El grupo del día N+1 desapareció
        assert (ID_PERSONAL, DIA_N1) not in grupos
        # El grupo del día N ahora tiene los dos picados
        picados_n = grupos[(ID_PERSONAL, DIA_N)]
        assert len(picados_n) == 2
        assert min(picados_n).time() == time(22, 30)
        assert max(picados_n).time() == time(3, 15)

    def test_trabajador_diurno_temprano_no_se_remapea(self):
        """Panadero entra 05:00 AM día N+1 — sin picado >=18:00 día N,
        no debe atribuirse al día anterior."""
        ID = 999
        grupos = {
            # Día N: jornada diurna normal
            (ID, date(2026, 5, 20)): [
                datetime(2026, 5, 20, 7, 0),
                datetime(2026, 5, 20, 16, 0),
            ],
            # Día N+1: entrada muy temprana
            (ID, date(2026, 5, 21)): [datetime(2026, 5, 21, 5, 0)],
        }
        snapshot = {k: list(v) for k, v in grupos.items()}

        remapeos = _remapear_turno_noche(grupos)

        assert remapeos == 0
        assert grupos == snapshot

    def test_picado_diurno_pre_18_no_califica_como_entrada_nocturna(self):
        """Día N tiene picado a las 17:30 (no >=18:00) → no es pivot
        nocturno → el picado de madrugada del día N+1 no se remapea."""
        ID = 555
        grupos = {
            (ID, date(2026, 5, 20)): [datetime(2026, 5, 20, 17, 30)],
            (ID, date(2026, 5, 21)): [datetime(2026, 5, 21, 4, 0)],
        }

        remapeos = _remapear_turno_noche(grupos)

        assert remapeos == 0
        assert (ID, date(2026, 5, 21)) in grupos
        assert len(grupos[(ID, date(2026, 5, 20))]) == 1
        assert len(grupos[(ID, date(2026, 5, 21))]) == 1

    def test_corte_exacto_5_30_no_remapea(self):
        """05:30:00 exacto NO es "antes de 05:30" → no remapear."""
        ID = 1
        grupos = {
            (ID, date(2026, 5, 20)): [datetime(2026, 5, 20, 22, 0)],
            (ID, date(2026, 5, 21)): [datetime(2026, 5, 21, 5, 30, 0)],
        }
        remapeos = _remapear_turno_noche(grupos)
        assert remapeos == 0
        assert (ID, date(2026, 5, 21)) in grupos

    def test_corte_5_29_si_remapea(self):
        """05:29:59 SÍ es antes de 05:30 → remapear si hay evidencia."""
        ID = 2
        grupos = {
            (ID, date(2026, 5, 20)): [datetime(2026, 5, 20, 22, 0)],
            (ID, date(2026, 5, 21)): [datetime(2026, 5, 21, 5, 29, 59)],
        }
        remapeos = _remapear_turno_noche(grupos)
        assert remapeos == 1

    def test_grupo_madrugada_sin_dia_anterior_no_explota(self):
        """Solo hay picados del día N+1 madrugada, sin grupo del día N
        en esta corrida → no se remapea (sin evidencia in-memory)."""
        ID = 77
        grupos = {
            (ID, date(2026, 5, 21)): [datetime(2026, 5, 21, 3, 0)],
        }
        remapeos = _remapear_turno_noche(grupos)
        assert remapeos == 0
        assert (ID, date(2026, 5, 21)) in grupos

    def test_idempotente_corrida_repetida(self):
        """Si ya está remapeado, una segunda pasada no hace nada."""
        ID = 333
        grupos = {
            (ID, date(2026, 5, 20)): [
                datetime(2026, 5, 20, 22, 30),
                datetime(2026, 5, 21, 3, 15),
            ],
        }
        snapshot = {k: list(v) for k, v in grupos.items()}

        r1 = _remapear_turno_noche(grupos)
        r2 = _remapear_turno_noche(grupos)

        assert r1 == 0
        assert r2 == 0
        assert grupos == snapshot

    def test_dos_trabajadores_independientes(self):
        """Trabajador A tiene turno noche real, B es diurno temprano.
        Solo A se remapea."""
        A, B = 100, 200
        grupos = {
            # A: turno noche
            (A, date(2026, 5, 20)): [datetime(2026, 5, 20, 21, 0)],
            (A, date(2026, 5, 21)): [datetime(2026, 5, 21, 4, 0)],
            # B: diurno
            (B, date(2026, 5, 20)): [
                datetime(2026, 5, 20, 8, 0),
                datetime(2026, 5, 20, 17, 0),
            ],
            (B, date(2026, 5, 21)): [datetime(2026, 5, 21, 5, 0)],
        }

        remapeos = _remapear_turno_noche(grupos)

        assert remapeos == 1
        # A: día N ahora tiene 2 picados, día N+1 borrado
        assert len(grupos[(A, date(2026, 5, 20))]) == 2
        assert (A, date(2026, 5, 21)) not in grupos
        # B: intacto
        assert len(grupos[(B, date(2026, 5, 20))]) == 2
        assert len(grupos[(B, date(2026, 5, 21))]) == 1

    def test_multiples_picados_de_madrugada_todos_movidos(self):
        """Día N+1 tiene 03:00 y 03:15 (re-marcaciones). Ambos al día N."""
        ID = 42
        grupos = {
            (ID, date(2026, 5, 20)): [datetime(2026, 5, 20, 22, 0)],
            (ID, date(2026, 5, 21)): [
                datetime(2026, 5, 21, 3, 0),
                datetime(2026, 5, 21, 3, 15),
            ],
        }

        remapeos = _remapear_turno_noche(grupos)

        assert remapeos == 1
        assert (ID, date(2026, 5, 21)) not in grupos
        assert len(grupos[(ID, date(2026, 5, 20))]) == 3

    def test_dia_n1_mixto_no_remapea(self):
        """Día N+1 tiene 03:00 (madrugada) Y 08:00 (jornada del día) →
        NO se mueve porque el grupo no es 'solo madrugada'."""
        ID = 88
        grupos = {
            (ID, date(2026, 5, 20)): [datetime(2026, 5, 20, 21, 0)],
            (ID, date(2026, 5, 21)): [
                datetime(2026, 5, 21, 3, 0),
                datetime(2026, 5, 21, 8, 0),
            ],
        }
        snapshot = {k: list(v) for k, v in grupos.items()}

        remapeos = _remapear_turno_noche(grupos)

        # El grupo del día N+1 no califica (tiene picado >=05:30)
        assert remapeos == 0
        assert grupos == snapshot
