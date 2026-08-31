"""Reglas compartidas para continuidad y solapes de contratos laborales."""
from datetime import timedelta

from dateutil.relativedelta import relativedelta
from django.db.models import Q
from django.utils import timezone

from personal.models import Contrato


MANTENER_MODALIDAD = "__MANTENER__"


def fecha_inicio_continuidad(contrato=None, personal=None):
    """Devuelve el inicio que mantiene continuidad documental."""
    fechas_fin = []
    if contrato and contrato.fecha_fin:
        fechas_fin.append(contrato.fecha_fin)
    if personal and personal.fecha_fin_contrato:
        fechas_fin.append(personal.fecha_fin_contrato)
    if fechas_fin:
        return max(fechas_fin) + timedelta(days=1)
    return timezone.localdate()


def fecha_fin_por_duracion(fecha_inicio, meses):
    """Calcula un vencimiento inclusivo a partir de una fecha de inicio."""
    return fecha_inicio + relativedelta(months=meses) - timedelta(days=1)


def contratos_solapados(personal, fecha_inicio, fecha_fin=None, excluir_pk=None):
    """Contratos existentes cuyo periodo se cruza con el rango indicado."""
    qs = Contrato.objects.filter(personal=personal)
    if excluir_pk:
        qs = qs.exclude(pk=excluir_pk)

    if fecha_fin:
        qs = qs.filter(fecha_inicio__lte=fecha_fin)

    return qs.filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha_inicio)).order_by(
        "-fecha_inicio", "-pk"
    )


def describir_periodo(contrato):
    fin = contrato.fecha_fin.strftime("%d/%m/%Y") if contrato.fecha_fin else "indefinido"
    return f"{contrato.fecha_inicio.strftime('%d/%m/%Y')} - {fin}"
