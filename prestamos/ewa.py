"""
Adelanto de sueldo sobre lo devengado (EWA — Earned Wage Access).

El trabajador puede solicitar desde el portal un adelanto contra los días
YA TRABAJADOS del ciclo de planilla en curso (22→21, el mismo MES_CORTE
que usa nómina). El adelanto:

  - tiene tope = PCT_TOPE_DEVENGADO del devengado bruto a la fecha,
    menos los adelantos EWA vivos del mismo ciclo (pendientes/aprobados/
    en curso);
  - se crea como Prestamo PENDIENTE del tipo `adelanto-sueldo-ewa`
    (1 cuota, sin interés) → RRHH aprueba/rechaza con el flujo normal
    de préstamos, y la cuota se descuenta sola en el cierre del período
    (engine consolida cuotas EN_CURSO del mes);
  - nunca se desembolsa automáticamente: este módulo solo calcula topes
    y registra la solicitud.

El devengado se estima igual que nómina: días del ciclo transcurridos
hasta hoy menos los no laborados del tareo (FA/LSG/SAI), a razón de
sueldo_base/30 por día. Sin tareo se asume asistencia (igual que el
default de nómina); el tope conservador y la aprobación manual cubren
el riesgo.
"""
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum

# Tope del adelanto como fracción del devengado bruto a la fecha.
# Referencia mercado: Buk y TuSueldoYa operan entre 50% y 70%.
PCT_TOPE_DEVENGADO = Decimal('0.50')

# Monto mínimo que tiene sentido tramitar.
MONTO_MINIMO = Decimal('50.00')

TIPO_CODIGO = 'adelanto-sueldo-ewa'
TIPO_NOMBRE = 'Adelanto de sueldo (devengado)'

CODIGOS_NO_LABORADOS = ('FA', 'LSG', 'SAI')  # mismos que engine asistencia→nómina


def get_tipo_ewa():
    """Tipo de préstamo EWA (1 cuota, sin interés). Se crea si no existe."""
    from .models import TipoPrestamo
    tipo, _ = TipoPrestamo.objects.get_or_create(
        codigo=TIPO_CODIGO,
        defaults={
            'nombre': TIPO_NOMBRE,
            'descripcion': 'Adelanto contra los días ya trabajados del ciclo '
                           'de planilla en curso. Se descuenta íntegro en la '
                           'planilla del mismo período.',
            'max_cuotas': 1,
            'tasa_interes_mensual': Decimal('0.000'),
            'requiere_aprobacion': True,
        },
    )
    return tipo


def ciclo_en_curso(hoy=None):
    """Ciclo de planilla (22→21) que contiene `hoy`, y el (anio, mes) del
    período de nómina al que pertenece (el ciclo cierra el 21 de ese mes)."""
    from asistencia.services.periodo_helper import TIPO_MES_CORTE, get_periodo
    hoy = hoy or date.today()
    anio, mes = hoy.year, hoy.month
    if hoy.day >= 22:
        mes += 1
        if mes > 12:
            mes, anio = 1, anio + 1
    return get_periodo(TIPO_MES_CORTE, anio, mes), (anio, mes)


def calcular_disponible(personal, hoy=None):
    """Calcula el adelanto disponible para el trabajador a la fecha.

    Returns dict con: ciclo, dias_devengados, devengado, tope,
    comprometido (adelantos EWA vivos del ciclo) y disponible.
    """
    from .models import Prestamo

    hoy = hoy or date.today()
    ciclo, (anio, mes) = ciclo_en_curso(hoy)

    # Días transcurridos del ciclo (inclusive), capados al fin del ciclo.
    fin = min(hoy, ciclo.fecha_fin)
    dias_transcurridos = (fin - ciclo.fecha_inicio).days + 1

    # No laborados registrados en el tareo del ciclo a la fecha.
    no_laborados = 0
    try:
        from asistencia.models import RegistroTareo
        no_laborados = RegistroTareo.objects.filter(
            personal=personal,
            fecha__gte=ciclo.fecha_inicio, fecha__lte=fin,
            codigo_dia__in=CODIGOS_NO_LABORADOS,
        ).count()
    except Exception:
        pass

    dias_devengados = max(0, dias_transcurridos - no_laborados)
    sueldo_diario = (personal.sueldo_base or Decimal('0')) / Decimal('30')
    devengado = (sueldo_diario * dias_devengados).quantize(Decimal('0.01'))
    tope = (devengado * PCT_TOPE_DEVENGADO).quantize(Decimal('0.01'))

    # Adelantos EWA vivos solicitados dentro del ciclo en curso.
    comprometido = (
        Prestamo.objects.filter(
            personal=personal,
            tipo__codigo=TIPO_CODIGO,
            estado__in=['PENDIENTE', 'APROBADO', 'EN_CURSO'],
            fecha_solicitud__gte=ciclo.fecha_inicio,
            fecha_solicitud__lte=ciclo.fecha_fin,
        ).aggregate(total=Sum('monto_solicitado'))['total']
        or Decimal('0')
    )

    disponible = max(Decimal('0'), tope - comprometido)
    return {
        'ciclo': ciclo,
        'periodo_anio': anio,
        'periodo_mes': mes,
        'dias_devengados': dias_devengados,
        'devengado': devengado,
        'tope': tope,
        'comprometido': comprometido,
        'disponible': disponible,
    }


class EWAError(Exception):
    """Solicitud inválida (monto fuera de rango, sin sueldo, etc.)."""


@transaction.atomic
def solicitar_adelanto(personal, monto, usuario=None, motivo='', hoy=None):
    """Registra la solicitud de adelanto como Prestamo PENDIENTE.

    Valida monto contra el disponible a la fecha. Devuelve el Prestamo.
    Lanza EWAError con mensaje legible si la solicitud no procede.
    """
    from .models import Prestamo

    try:
        monto = Decimal(str(monto)).quantize(Decimal('0.01'))
    except Exception:
        raise EWAError('Monto inválido.')

    if monto < MONTO_MINIMO:
        raise EWAError(f'El monto mínimo de adelanto es S/ {MONTO_MINIMO}.')

    if not personal.sueldo_base or personal.sueldo_base <= 0:
        raise EWAError('No tienes un sueldo base registrado; consulta con RRHH.')

    info = calcular_disponible(personal, hoy=hoy)
    if monto > info['disponible']:
        raise EWAError(
            f'El monto supera tu adelanto disponible (S/ {info["disponible"]}). '
            f'Has devengado S/ {info["devengado"]} en {info["dias_devengados"]} días '
            f'y el tope es el {int(PCT_TOPE_DEVENGADO * 100)}%.'
        )

    prestamo = Prestamo.objects.create(
        personal=personal,
        tipo=get_tipo_ewa(),
        monto_solicitado=monto,
        num_cuotas=1,
        tasa_interes=Decimal('0.000'),
        estado='PENDIENTE',
        motivo=motivo or 'Adelanto de sueldo sobre devengado (portal)',
        solicitado_por=usuario,
        fecha_solicitud=hoy or date.today(),
    )
    return prestamo
