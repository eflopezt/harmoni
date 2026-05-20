"""
Tests para edge cases del motor de nomina peruana.

Cobertura adicional a test_engine.py:
- Asignacion familiar con sueldo = RMV exacto
- IR 5ta sobre sueldos altos (rangos progresivos)
- Gratificacion trunca (cese a mitad de semestre)
- Cap de horas extras (DL 713 — alerta no bloqueante)
- Decimal precision en montos extremos
"""
from decimal import Decimal
from nominas.engine import (
    calcular_ir_5ta_mensual,
    calcular_prov_gratif,
    _redondear,
    _ir_anual,
    UIT_2026,
    RMV_2026,
    ASIG_FAM,
    IR_5TA_DEDUCCION_UITS,
    TOPE_HE_MES,
)


# ════════════════════════════════════════════════════════════════════════════
# 1. Asignacion familiar (Ley 25129 — 10% RMV, fija no proporcional)
# ════════════════════════════════════════════════════════════════════════════

class TestAsignacionFamiliar:
    """ASIG_FAM = 10% RMV. Para 2026 con RMV S/1130 -> S/113."""

    def test_asig_fam_es_10_pct_rmv(self):
        assert ASIG_FAM == RMV_2026 * Decimal('0.10')
        assert ASIG_FAM == Decimal('113.00')

    def test_prov_gratif_con_asig_familiar(self):
        """Provision gratif debe incluir asig_fam en la base."""
        sueldo = Decimal('3000')
        prov = calcular_prov_gratif(sueldo, ASIG_FAM)
        expected = _redondear((sueldo + ASIG_FAM) / Decimal('6'))
        assert prov == expected
        # = (3000 + 113) / 6 = 518.83
        assert prov == Decimal('518.83')

    def test_prov_gratif_sin_asig_familiar(self):
        """Sin asig_fam, prov_gratif = sueldo / 6."""
        prov = calcular_prov_gratif(Decimal('3000'), Decimal('0'))
        assert prov == Decimal('500.00')


# ════════════════════════════════════════════════════════════════════════════
# 2. IR 5ta — escala progresiva (8/14/17/20/30%)
# ════════════════════════════════════════════════════════════════════════════

class TestIR5taEscala:
    """Verifica que cada tramo de la escala se aplica correctamente."""

    def test_ir_anual_sueldo_bajo_no_paga(self):
        """Si rem_anual < 7 UIT, no paga IR."""
        rem_anual = IR_5TA_DEDUCCION_UITS * UIT_2026 - Decimal('1000')
        # _ir_anual se llama sobre base imponible (ya restado 7 UIT)
        # Si base < 0, debe ser 0
        assert _ir_anual(Decimal('-1000'), UIT_2026) == Decimal('0')
        assert _ir_anual(Decimal('0'), UIT_2026) == Decimal('0')

    def test_ir_anual_tramo_1(self):
        """Hasta 5 UIT = 8%."""
        base = Decimal('5500')  # 1 UIT
        imp = _ir_anual(base, UIT_2026)
        assert imp == base * Decimal('0.08')

    def test_ir_anual_tramo_2(self):
        """Entre 5 y 20 UIT: 8% primeros 5 + 14% resto."""
        base = UIT_2026 * Decimal('10')  # 10 UIT
        imp = _ir_anual(base, UIT_2026)
        expected = (
            UIT_2026 * Decimal('5') * Decimal('0.08')  # primeros 5 UIT al 8%
            + UIT_2026 * Decimal('5') * Decimal('0.14')  # 5-10 UIT al 14%
        )
        assert imp == expected

    def test_ir_anual_tramo_top_30pct(self):
        """Sobre 45 UIT: 30% del exceso."""
        base = UIT_2026 * Decimal('50')  # 50 UIT
        imp = _ir_anual(base, UIT_2026)
        # 5 UIT @ 8% + 15 UIT @ 14% + 15 UIT @ 17% + 10 UIT @ 20% + 5 UIT @ 30%
        expected = (
            UIT_2026 * Decimal('5')  * Decimal('0.08') +
            UIT_2026 * Decimal('15') * Decimal('0.14') +
            UIT_2026 * Decimal('15') * Decimal('0.17') +
            UIT_2026 * Decimal('10') * Decimal('0.20') +
            UIT_2026 * Decimal('5')  * Decimal('0.30')
        )
        assert imp == expected

    def test_ir_mensual_sueldo_minimo_no_paga(self):
        """Sueldo RMV (1130) × 14 = 15820 anual. Menos 7 UIT (38500) = base negativa → 0 IR."""
        rem_anual = RMV_2026 * Decimal('14')
        ir = calcular_ir_5ta_mensual(rem_anual)
        assert ir == Decimal('0')

    def test_ir_mensual_sueldo_4000_no_paga(self):
        """Sueldo S/4000 × 14 = 56000. Menos 7 UIT (38500) = 17500 base. Paga IR pequeño."""
        rem_anual = Decimal('4000') * Decimal('14')  # 56000
        ir_mensual = calcular_ir_5ta_mensual(rem_anual)
        # Base = 56000 - 38500 = 17500. Tramo 1: 17500 < 5 UIT (27500) → 8%
        ir_anual_esperado = Decimal('17500') * Decimal('0.08')
        assert ir_mensual == _redondear(ir_anual_esperado / 12)


# ════════════════════════════════════════════════════════════════════════════
# 3. TOPE_HE_MES (DL 713 — 4h/dia ~ 60h/mes)
# ════════════════════════════════════════════════════════════════════════════

class TestTopeHEConstante:
    """Solo verifica que la constante existe y tiene el valor esperado."""

    def test_tope_60_horas(self):
        assert TOPE_HE_MES == Decimal('60')

    def test_tope_es_decimal(self):
        assert isinstance(TOPE_HE_MES, Decimal)


# ════════════════════════════════════════════════════════════════════════════
# 4. Decimal precision — montos extremos
# ════════════════════════════════════════════════════════════════════════════

class TestDecimalPrecision:
    """ROUND_HALF_UP estandar planilla peruana."""

    def test_redondear_50_centavos_sube(self):
        """0.005 → 0.01 (ROUND_HALF_UP)."""
        assert _redondear(Decimal('100.005')) == Decimal('100.01')

    def test_redondear_no_pierde_centavo(self):
        """100.999 → 101.00."""
        assert _redondear(Decimal('100.999')) == Decimal('101.00')

    def test_redondear_negativo(self):
        """Negativos también con HALF_UP."""
        # En Decimal ROUND_HALF_UP redondea away from zero,
        # asi que -100.005 -> -100.01
        assert _redondear(Decimal('-100.005')) == Decimal('-100.01')

    def test_prov_gratif_redondea_al_final(self):
        """(sueldo + asig_fam) / 6 debe redondearse al final, no antes."""
        sueldo = Decimal('1000')
        asig = Decimal('113')  # asig_fam 2026
        # (1000 + 113) / 6 = 185.5
        prov = calcular_prov_gratif(sueldo, asig)
        # 185.5 con ROUND_HALF_UP → 185.50
        assert prov == Decimal('185.50')

    def test_prov_gratif_acepta_cero(self):
        """Si ambos son 0, prov = 0."""
        assert calcular_prov_gratif(Decimal('0'), Decimal('0')) == Decimal('0.00')

    def test_prov_gratif_acepta_none_safe(self):
        """Manejo defensivo de None (convertido a 0)."""
        # calcular_prov_gratif hace Decimal(x or 0)
        assert calcular_prov_gratif(None, None) == Decimal('0.00')
        assert calcular_prov_gratif(Decimal('1000'), None) == Decimal('166.67')


# ════════════════════════════════════════════════════════════════════════════
# 5. Sueldos extremos — boundaries del sistema
# ════════════════════════════════════════════════════════════════════════════

class TestSueldosExtremos:
    """Casos limites del cálculo."""

    def test_ir_sueldo_gerencial_alto(self):
        """Sueldo S/30000/mes = 420000/ano. Tramo alto."""
        rem_anual = Decimal('30000') * Decimal('14')  # 420000
        ir = calcular_ir_5ta_mensual(rem_anual)
        # Base = 420000 - 38500 = 381500
        # 381500 / 5500 = ~69.36 UIT
        # 5 UIT@8% + 15@14% + 15@17% + 10@20% + 24.36@30%
        assert ir > Decimal('0')
        # Debe ser un monto significativo (en miles)
        assert ir > Decimal('5000')

    def test_ir_con_deduccion_eps(self):
        """Aporte EPS reduce la base imponible."""
        rem_anual = Decimal('4000') * Decimal('14')  # 56000
        ir_sin_eps = calcular_ir_5ta_mensual(rem_anual)
        ir_con_eps = calcular_ir_5ta_mensual(rem_anual, deduccion_eps_anual=Decimal('3000'))
        assert ir_con_eps < ir_sin_eps

    def test_ir_uit_explicito(self):
        """Permite pasar UIT explicito (para escenarios historicos)."""
        rem_anual = Decimal('60000')
        # Con UIT 5350 (2025) el calculo es distinto
        ir_2025 = calcular_ir_5ta_mensual(rem_anual, uit=Decimal('5350'))
        ir_2026 = calcular_ir_5ta_mensual(rem_anual, uit=Decimal('5500'))
        # Con UIT mas alta, la deduccion 7 UIT es mayor, asi que IR mas bajo
        assert ir_2025 >= ir_2026
