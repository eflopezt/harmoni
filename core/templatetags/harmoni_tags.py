"""
Template tags y filtros compartidos del sistema Harmoni.
"""
from django import template

register = template.Library()


@register.filter
def moneda_pen(value):
    """Formato moneda peruana: S/ 1,234.56"""
    try:
        amount = float(value)
        return f"S/ {amount:,.2f}"
    except (ValueError, TypeError):
        return value


@register.filter
def horas_decimal(value):
    """Formato horas decimales: 8.50h"""
    try:
        hours = float(value)
        return f"{hours:.2f}h"
    except (ValueError, TypeError):
        return value


@register.filter
def porcentaje(value, decimals=1):
    """Formato porcentaje: 95.5%"""
    try:
        pct = float(value)
        return f"{pct:.{int(decimals)}f}%"
    except (ValueError, TypeError):
        return value


@register.filter
def add_decimal(value, arg):
    """
    Suma segura para campos Decimal/float/None.
    Reemplaza el filtro |add que falla silenciosamente con Decimal.
    Uso: {{ valor1|add_decimal:valor2 }}
    """
    try:
        return float(value or 0) + float(arg or 0)
    except (ValueError, TypeError):
        return 0


@register.filter
def sum_he(record):
    """
    Suma las tres columnas de horas extra de un RegistroTareo.
    Uso: {{ registro|sum_he }}
    """
    try:
        return float(record.he_25 or 0) + float(record.he_35 or 0) + float(record.he_100 or 0)
    except (AttributeError, ValueError, TypeError):
        return 0


@register.filter
def get_item(dictionary, key):
    """
    Accede a un valor de un diccionario por clave en templates.
    Uso: {{ mi_dict|get_item:clave }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def abs_value(value):
    """Valor absoluto de un número. Uso: {{ num|abs_value }}"""
    try:
        return abs(float(value))
    except (ValueError, TypeError):
        return value


@register.filter
def subtract(value, arg):
    """Resta segura entre dos números. Uso: {{ total|subtract:parcial }}"""
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def compa_ratio_clase(value):
    """
    Devuelve la clase CSS Bootstrap para el badge de compa-ratio.
    <0.85 → badge-compa-bajo, 0.85–1.15 → badge-compa-rango, >1.15 → badge-compa-sobre
    """
    try:
        v = float(value)
        if v < 0.85:
            return 'badge-compa-bajo'
        elif v > 1.15:
            return 'badge-compa-sobre'
        else:
            return 'badge-compa-rango'
    except (ValueError, TypeError):
        return 'badge-compa-nd'
