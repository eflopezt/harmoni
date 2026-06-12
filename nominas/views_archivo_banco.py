"""
Genera archivos planos para depósito masivo de haberes en bancos peruanos.

Formatos soportados:
- BCP (Telecrédito Web — pago haberes): TXT línea fija
- BBVA (Pago Múltiple — Net Cash): CSV
- Scotiabank (Telebanking Empresas): CSV
- Interbank (Comercio.com — pago de planillas): TXT
- BN (Multired Virtual): TXT
- Genérico CSV (Excel-friendly): para cualquier otro banco

Uso UI:
    /nominas/periodos/<pk>/archivo-banco/?banco=BCP
    /nominas/periodos/<pk>/archivo-banco/?banco=BBVA
    etc.

Cada banco tiene su propio formato técnico exacto — los layouts pueden
variar levemente por versión. Los archivos generados aquí cumplen con
los specs estándar 2024-2026. Si el banco cambia el layout, se actualiza
en este archivo sin tocar el modelo.
"""
import csv
import io
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .models import PeriodoNomina, RegistroNomina


solo_admin = user_passes_test(lambda u: u.is_superuser)


# ─────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────

def _registros_pagables(periodo):
    """Devuelve registros con neto > 0 ordenados por trabajador."""
    return (
        periodo.registros
        .select_related('personal')
        .filter(neto_a_pagar__gt=0)
        .order_by('personal__apellidos_nombres')
    )


def _split_por_medio_pago(registros):
    """Separa los registros entre pago por cuenta bancaria y por billetera
    digital (Ley 32413). Un trabajador va a billetera SOLO si tiene acuerdo
    firmado y celular válido; en cualquier otro caso queda en cuenta."""
    cuenta, billetera = [], []
    for r in registros:
        (billetera if r.personal.paga_por_billetera else cuenta).append(r)
    return cuenta, billetera


def _normalizar_cuenta(raw):
    """Limpia espacios y guiones de un número de cuenta."""
    return (raw or '').replace('-', '').replace(' ', '').strip()


def _validar_cci(cci):
    """CCI: 20 dígitos. Si no cumple, retorna False."""
    s = _normalizar_cuenta(cci)
    return len(s) == 20 and s.isdigit()


# ─────────────────────────────────────────────────────────────────────
# BCP — Telecrédito (TXT línea fija)
# ─────────────────────────────────────────────────────────────────────

def _bcp_telecredito(periodo, registros):
    """
    Formato Telecrédito Web BCP — Pago a Cuenta de Terceros.
    Línea fija de ~104 caracteres por registro.

    Layout estándar BCP:
      Pos 1-20 : Cuenta destino (CCI 20 dígitos)
      Pos 21-22: Tipo doc (01=DNI, 04=CE)
      Pos 23-34: Número documento (12 chars, justif. derecha con ceros)
      Pos 35-94: Nombre beneficiario (60 chars, espacios al final)
      Pos 95-106: Monto en céntimos (12 dígitos, ceros izq.)
      Pos 107-110: Moneda (PEN=4 chars)
      Pos 111-120: Referencia (10 chars)
    """
    lines = []
    for r in registros:
        p = r.personal
        cci = _normalizar_cuenta(p.cuenta_cci) if p.cuenta_cci else ''
        if not _validar_cci(cci):
            # Si no hay CCI válido, omitir (cliente debe completar)
            continue
        tipo_doc = '01' if (p.tipo_doc or 'DNI').upper() == 'DNI' else '04'
        nro_doc = (p.nro_doc or '').rjust(12, '0')[:12]
        nombre = (p.apellidos_nombres or '').ljust(60)[:60]
        # Monto en céntimos
        cents = int(r.neto_a_pagar * Decimal('100'))
        monto_str = str(cents).rjust(12, '0')[:12]
        moneda = 'PEN '
        ref = f'P{periodo.anio}{periodo.mes:02d}'.ljust(10)[:10]

        line = f'{cci.ljust(20)[:20]}{tipo_doc}{nro_doc}{nombre}{monto_str}{moneda}{ref}'
        lines.append(line)

    return '\r\n'.join(lines) + '\r\n', 'BCP_Telecredito'


# ─────────────────────────────────────────────────────────────────────
# BBVA — Pago Múltiple Net Cash (CSV)
# ─────────────────────────────────────────────────────────────────────

def _bbva_netcash(periodo, registros):
    """CSV BBVA — separador ; sin headers."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=';', lineterminator='\r\n')
    for r in registros:
        p = r.personal
        cci = _normalizar_cuenta(p.cuenta_cci)
        if not _validar_cci(cci):
            continue
        w.writerow([
            cci,
            'PEN',
            f'{r.neto_a_pagar:.2f}',
            (p.nro_doc or '').strip(),
            (p.apellidos_nombres or '').strip(),
            f'PAYROLL-{periodo.anio}-{periodo.mes:02d}',
        ])
    return buf.getvalue(), 'BBVA_NetCash'


# ─────────────────────────────────────────────────────────────────────
# Scotiabank — Telebanking Empresas (CSV)
# ─────────────────────────────────────────────────────────────────────

def _scotia_telebanking(periodo, registros):
    """CSV Scotia — separador , con header."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=',', lineterminator='\r\n')
    w.writerow(['CCI', 'MONEDA', 'MONTO', 'TIPO_DOC', 'NRO_DOC', 'NOMBRE', 'REFERENCIA'])
    for r in registros:
        p = r.personal
        cci = _normalizar_cuenta(p.cuenta_cci)
        if not _validar_cci(cci):
            continue
        w.writerow([
            cci,
            'PEN',
            f'{r.neto_a_pagar:.2f}',
            (p.tipo_doc or 'DNI'),
            (p.nro_doc or '').strip(),
            (p.apellidos_nombres or '').strip(),
            f'Pago haberes {periodo.anio}-{periodo.mes:02d}',
        ])
    return buf.getvalue(), 'Scotia_Telebanking'


# ─────────────────────────────────────────────────────────────────────
# Interbank — Comercio.com (TXT)
# ─────────────────────────────────────────────────────────────────────

def _interbank_planillas(periodo, registros):
    """Layout Interbank — pipe-delimited."""
    buf = io.StringIO()
    for r in registros:
        p = r.personal
        cci = _normalizar_cuenta(p.cuenta_cci)
        if not _validar_cci(cci):
            continue
        line = '|'.join([
            cci,
            f'{int(r.neto_a_pagar * 100)}',  # monto en céntimos
            'PEN',
            (p.tipo_doc or 'DNI'),
            (p.nro_doc or '').strip(),
            (p.apellidos_nombres or '').strip()[:60],
            f'PAY{periodo.anio}{periodo.mes:02d}',
        ])
        buf.write(line + '\r\n')
    return buf.getvalue(), 'Interbank_Comercio'


# ─────────────────────────────────────────────────────────────────────
# BN — Multired Virtual (TXT estilo BCP simplificado)
# ─────────────────────────────────────────────────────────────────────

def _bn_multired(periodo, registros):
    """Layout BN — campo fijo, parecido a BCP pero con sufijo BN."""
    lines = []
    for r in registros:
        p = r.personal
        cuenta = _normalizar_cuenta(p.cuenta_ahorros or p.cuenta_cci)
        if not cuenta:
            continue
        # BN: cuenta sin CCI, número estándar 14 dígitos
        cuenta = cuenta.ljust(14)[:14]
        nro_doc = (p.nro_doc or '').rjust(11, '0')[:11]
        nombre = (p.apellidos_nombres or '').ljust(50)[:50]
        cents = int(r.neto_a_pagar * Decimal('100'))
        monto = str(cents).rjust(11, '0')[:11]
        ref = f'PAY{periodo.mes:02d}{periodo.anio}'.ljust(10)[:10]
        lines.append(f'{cuenta}{nro_doc}{nombre}{monto}{ref}')
    return '\r\n'.join(lines) + '\r\n', 'BN_Multired'


# ─────────────────────────────────────────────────────────────────────
# Genérico CSV (Excel friendly)
# ─────────────────────────────────────────────────────────────────────

def _generico_csv(periodo, registros):
    """CSV universal con todas las columnas. Para cualquier banco que
    acepte importación libre.
    """
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=',', lineterminator='\r\n')
    w.writerow([
        'DNI', 'Apellidos y Nombres', 'Banco', 'Cuenta ahorros', 'CCI',
        'Monto (S/)', 'Moneda', 'Período', 'Concepto',
    ])
    for r in registros:
        p = r.personal
        w.writerow([
            (p.nro_doc or '').strip(),
            (p.apellidos_nombres or '').strip(),
            (p.banco or ''),
            _normalizar_cuenta(p.cuenta_ahorros or ''),
            _normalizar_cuenta(p.cuenta_cci or ''),
            f'{r.neto_a_pagar:.2f}',
            'PEN',
            f'{periodo.anio}-{periodo.mes:02d}',
            f'Pago haberes {periodo.anio}-{periodo.mes:02d}',
        ])
    return buf.getvalue(), 'Generico_CSV'


# ─────────────────────────────────────────────────────────────────────
# Billeteras digitales — Yape / Plin / Ligo / Kontigo (Ley 32413)
# ─────────────────────────────────────────────────────────────────────

def _billeteras_csv(periodo, registros):
    """CSV de dispersión a billeteras digitales.

    Ley 32413 + D.S. 011-2026-EF: el pago de haberes/CTS/gratificaciones
    vía billetera es válido solo con acuerdo previo del trabajador (la
    selección ya viene filtrada por `paga_por_billetera`). El CSV sirve
    para importar en las plataformas empresariales de pago masivo de cada
    billetera o como sustento del abono manual.
    """
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=',', lineterminator='\r\n')
    w.writerow([
        'DNI', 'Apellidos y Nombres', 'Billetera', 'Celular',
        'Monto (S/)', 'Moneda', 'Referencia',
    ])
    for r in registros:
        p = r.personal
        w.writerow([
            (p.nro_doc or '').strip(),
            (p.apellidos_nombres or '').strip(),
            p.get_billetera_tipo_display() if p.billetera_tipo else '',
            (p.billetera_celular or '').strip(),
            f'{r.neto_a_pagar:.2f}',
            'PEN',
            f'Pago haberes {periodo.anio}-{periodo.mes:02d}',
        ])
    return buf.getvalue(), 'Billeteras'


# ─────────────────────────────────────────────────────────────────────
# Dispatch + view
# ─────────────────────────────────────────────────────────────────────

GENERADORES = {
    'BCP':        (_bcp_telecredito,   'txt'),
    'BBVA':       (_bbva_netcash,      'csv'),
    'SCOTIA':     (_scotia_telebanking,'csv'),
    'INTERBANK':  (_interbank_planillas,'txt'),
    'BN':         (_bn_multired,       'txt'),
    'GENERICO':   (_generico_csv,      'csv'),
    'BILLETERAS': (_billeteras_csv,    'csv'),
}


@login_required
@solo_admin
def periodo_archivo_banco(request, pk):
    """
    GET /nominas/periodos/<pk>/archivo-banco/?banco=BCP

    Genera el archivo plano para depósito masivo del período al banco
    especificado. Si el banco no tiene CCI válido para un trabajador,
    se omite de la corrida y se reporta en logs.
    """
    periodo = get_object_or_404(PeriodoNomina, pk=pk)

    banco = (request.GET.get('banco', 'GENERICO') or '').upper()
    if banco not in GENERADORES:
        messages.error(request, f'Banco no soportado: {banco}. Opciones: {", ".join(GENERADORES.keys())}')
        return redirect('nominas_periodo_detalle', pk=pk)

    todos = list(_registros_pagables(periodo))
    if not todos:
        messages.warning(request, 'No hay registros pagables en este período.')
        return redirect('nominas_periodo_detalle', pk=pk)

    # Ley 32413: quien paga por billetera sale del archivo de banco (evita
    # doble pago si además tiene CCI) y viceversa.
    por_cuenta, por_billetera = _split_por_medio_pago(todos)
    registros = por_billetera if banco == 'BILLETERAS' else por_cuenta
    if not registros:
        detalle = ('ningún trabajador con acuerdo de billetera vigente'
                   if banco == 'BILLETERAS'
                   else 'todos los trabajadores pagables cobran por billetera')
        messages.warning(request, f'Sin registros para este archivo: {detalle}.')
        return redirect('nominas_periodo_detalle', pk=pk)

    generador, ext = GENERADORES[banco]
    contenido, label = generador(periodo, registros)

    # Stats
    total_trabajadores = len(registros)
    total_incluidos = contenido.count('\r\n') if ext == 'txt' else contenido.count('\n')
    total_monto = sum(r.neto_a_pagar for r in registros)

    # Filename: PAGO_HABERES_<banco>_<empresa>_<periodo>.txt|csv
    fname = (
        f'PAGO_HABERES_{label}_{periodo.empresa.ruc if periodo.empresa else "GRUPO"}_'
        f'{periodo.anio}-{periodo.mes:02d}.{ext}'
    )

    content_type = 'text/plain' if ext == 'txt' else 'text/csv'
    response = HttpResponse(contenido, content_type=f'{content_type}; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    response['X-Trabajadores-Pagables'] = str(total_trabajadores)
    response['X-Monto-Total'] = f'{total_monto:.2f}'
    return response
