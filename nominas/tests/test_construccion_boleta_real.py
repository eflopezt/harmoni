"""
Validación de los helpers de construcción civil contra una BOLETA REAL.

Fuente: boleta semanal CONSORCIO STILER-RIPCONCIV-TECNOEDIL, Semana 2026-10
(02–08/03/2026), trabajador FERNANDEZ POMA JOSE ALBERTO, Operario, jornal
diario S/ 89.30, 6 días asistidos + 1 dominical.

Totales de la boleta (todos reconciliados):
  TOTAL REMUNERACIÓN  1,540.41
  TOTAL DESCUENTO       256.24
  TOTAL APORTACIONES    140.92
  NETO (rem − desc)   1,284.17

Estos asserts fijan las BASES de cálculo verificadas contra la realidad, para
que la implementación de EstrategiaConstructor no se desvíe.
"""
from decimal import Decimal
from types import SimpleNamespace

from nominas import construccion as cc

JORNAL = Decimal('89.30')


def _registro_boleta():
    """RegistroNomina simulado con los datos de la boleta real."""
    return SimpleNamespace(
        sueldo_base=Decimal('89.30'),     # jornal diario
        dias_trabajados=6,
        regimen_pension='AFP',
        personal=SimpleNamespace(categoria_construccion=''),  # usa sueldo_base
        periodo=None,
        conceptos_manuales={
            'cc-hhee-60':       '214.32',
            'cc-hhee-100':      '44.65',
            'cc-hhee-100-dom':  '111.63',
            'cc-movilidad':     '60.20',
            'cc-bono-altitud':  '17.50',
            'cc-gratif-julio':  '119.07',
            'cc-bonif-extraord': '10.72',
            'cc-cts':           '112.18',
            'cc-ir-5ta':        '92.96',
            'cc-afp-comseg':    '16.96',
            'cc-cuota-sindical': '10.00',
        },
    )


def test_boleta_completa_reconcilia_al_centimo():
    """calcular_boleta_construccion reproduce la boleta real exacta."""
    r = cc.calcular_boleta_construccion(_registro_boleta())
    assert r['total_ingresos'] == Decimal('1540.41')
    assert r['total_descuentos'] == Decimal('256.24')
    assert r['neto_a_pagar'] == Decimal('1284.17')
    assert r['rem_computable'] == Decimal('1238.24')
    assert r['aporte_essalud'] == Decimal('111.44')
    assert r['aporte_sctr_salud'] == Decimal('8.05')
    assert r['aporte_sctr_pension'] == Decimal('8.05')
    assert r['aporte_vida_ley'] == Decimal('5.57')
    assert r['aporte_fondo_capacitacion'] == Decimal('2.81')
    assert r['total_aportaciones'] == Decimal('140.92')


def test_estrategia_constructor_usa_reglas_cc():
    """El dispatcher enruta a EstrategiaConstructor y reproduce la boleta."""
    from nominas.estrategias import calcular_por_regimen
    r = _registro_boleta()
    r.personal = SimpleNamespace(categoria_construccion='', regimen_laboral='CONSTRUCCION')
    out = calcular_por_regimen(r)
    assert out['neto_a_pagar'] == Decimal('1284.17')


def test_jornal_semanal_6_dias():
    assert cc.jornal_basico(JORNAL, 6) == Decimal('535.80')


def test_dominical_1_jornal():
    assert cc.dominical(JORNAL, Decimal('1')) == Decimal('89.30')


def test_buc_32pct_sobre_basico():
    # B.U.C. en la boleta = 171.46 = 32% del jornal semanal (535.80)
    assert cc.buc(Decimal('535.80'), Decimal('32')) == Decimal('171.46')


def test_vacaciones_10pct_por_dia():
    # VACACIONES en la boleta = 53.58 = 10% del jornal × 6 días
    assert cc.compensacion_vacacional(JORNAL, 6) == Decimal('53.58')


def test_conafovicer_2pct_sobre_basico_mas_dominical():
    # CONAFOVICER en la boleta = 12.50 = 2% de (535.80 + 89.30)
    base = Decimal('535.80') + Decimal('89.30')   # 625.10
    assert cc.conafovicer(base) == Decimal('12.50')


def test_totales_boleta_reconcilian():
    """Suma de líneas = totales impresos (documenta la composición real)."""
    remuneraciones = [
        Decimal('535.80'),   # jornal semanal
        Decimal('89.30'),    # dominical
        Decimal('214.32'),   # HHEE 60%
        Decimal('44.65'),    # HHEE 100%
        Decimal('111.63'),   # HHEE 100% dominical
        Decimal('171.46'),   # BUC
        Decimal('60.20'),    # movilidad acumulada
        Decimal('119.07'),   # gratificación julio (provisión semanal)
        Decimal('10.72'),    # bonif. extraord. Ley 29714 (9% de gratif)
        Decimal('53.58'),    # vacaciones
        Decimal('17.50'),    # bonificación por altitud
        Decimal('112.18'),   # CTS
    ]
    descuentos = [
        Decimal('92.96'),    # 5ta impuesto
        Decimal('123.82'),   # AFP aporte pensión
        Decimal('16.96'),    # AFP comisión + seguro
        Decimal('12.50'),    # CONAFOVICER
        Decimal('10.00'),    # cuota sindical
    ]
    aportes = [
        Decimal('111.44'),   # ESSALUD
        Decimal('2.81'),     # fondo de capacitación
        Decimal('5.00'),     # EsSalud Vida
        Decimal('8.05'),     # SCTR salud
        Decimal('8.05'),     # SCTR pensiones
        Decimal('5.57'),     # Vida Ley
    ]
    assert sum(remuneraciones) == Decimal('1540.41')
    assert sum(descuentos) == Decimal('256.24')
    assert sum(aportes) == Decimal('140.92')
    assert sum(remuneraciones) - sum(descuentos) == Decimal('1284.17')  # neto


def test_bonif_extraordinaria_9pct_de_gratificacion():
    # Bonif. Extraord. Ley 29714 = 9% de la gratificación (119.07 → 10.72)
    grati = Decimal('119.07')
    assert (grati * Decimal('9') / Decimal('100')).quantize(Decimal('0.01')) == Decimal('10.72')


def test_base_computable_por_afectaciones():
    """La base computable (afectos) = 1,238.24, y valida ESSALUD/AFP/SCTR.

    Solo entran los conceptos afectos; movilidad, gratif, bonif. extraord. y CTS
    quedan fuera. Reconcilia contra la boleta real.
    """
    lineas = {
        'cc-jornal-basico':  Decimal('535.80'),
        'cc-dominical':      Decimal('89.30'),
        'cc-hhee-60':        Decimal('214.32'),
        'cc-hhee-100':       Decimal('44.65'),
        'cc-hhee-100-dom':   Decimal('111.63'),
        'cc-buc':            Decimal('171.46'),
        'cc-bono-altitud':   Decimal('17.50'),
        'cc-comp-vacacional': Decimal('53.58'),
        # NO computables (deben quedar fuera):
        'cc-movilidad':      Decimal('60.20'),
        'cc-gratif-julio':   Decimal('119.07'),
        'cc-bonif-extraord': Decimal('10.72'),
        'cc-cts':            Decimal('112.18'),
    }
    base = cc.base_computable(lineas)
    assert base == Decimal('1238.24')

    # Cargas sobre la base computable (verificadas contra la boleta):
    assert (base * Decimal('9') / Decimal('100')).quantize(Decimal('0.01')) == Decimal('111.44')   # ESSALUD
    assert (base * Decimal('10') / Decimal('100')).quantize(Decimal('0.01')) == Decimal('123.82')  # AFP aporte 10%
    assert (base * Decimal('0.65') / Decimal('100')).quantize(Decimal('0.01')) == Decimal('8.05')  # SCTR salud 0.65%
