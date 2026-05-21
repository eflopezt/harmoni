"""
Predictor de Rotación de Personal — rule-based scoring.

Score 0-100 donde mayor = más probable a renunciar / cesar.

Señales (cada una contribuye con peso variable):
- Antigüedad: nuevos (<6m) y muy antiguos (>5y sin movimiento) son riesgo
- Papeletas: muchas en últimos 90 días = riesgo
- Faltas: registros 'F'/'FALTA_AUTO' en últimos 90 días
- Sin aumento: >18 meses sin cambio de sueldo base
- Bajas calificaciones: última Evaluacion con puntaje bajo
- Sin capacitación reciente: no asistió a capacitaciones en último año
- Sanciones disciplinarias recientes (MedidaDisciplinaria)

Algoritmo explicable: cada factor reporta nombre + puntos + detalle + severidad.
"""
from dataclasses import dataclass
from datetime import timedelta
from typing import List

from django.utils import timezone


@dataclass
class FactorRiesgo:
    """Un factor que contribuye al score de rotación."""
    nombre: str
    puntos: int
    detalle: str
    severidad: str  # 'alto', 'medio', 'bajo'


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE SCORING POR FACTOR
# ─────────────────────────────────────────────────────────────────────────────

def _factor_antiguedad(personal, hoy) -> List[FactorRiesgo]:
    """Antigüedad: muy nuevo o muy antiguo = riesgo."""
    if not personal.fecha_alta:
        return []

    dias = (hoy - personal.fecha_alta).days
    if dias < 90:
        return [FactorRiesgo(
            'Trabajador nuevo (<3 meses)',
            15,
            f'{dias} días desde ingreso',
            'medio',
        )]
    elif dias < 180:
        return [FactorRiesgo(
            'Trabajador nuevo (3-6 meses)',
            10,
            f'{dias} días desde ingreso',
            'bajo',
        )]
    elif dias > 1825:  # 5 años
        return [FactorRiesgo(
            'Antigüedad alta sin movimiento',
            10,
            f'{dias // 365} años en mismo cargo',
            'medio',
        )]
    return []


def _factor_papeletas(personal, hoy) -> List[FactorRiesgo]:
    """Papeletas frecuentes en últimos 90 días."""
    try:
        from asistencia.models import RegistroPapeleta
        # Solo papeletas aprobadas o ejecutadas (no anuladas/rechazadas)
        n = RegistroPapeleta.objects.filter(
            personal=personal,
            fecha_inicio__gte=hoy - timedelta(days=90),
            estado__in=['APROBADA', 'EJECUTADA', 'PENDIENTE'],
        ).count()
    except Exception:
        return []

    if n >= 5:
        return [FactorRiesgo(
            'Papeletas frecuentes (≥5 en 90 días)',
            20,
            f'{n} papeletas',
            'alto',
        )]
    elif n >= 3:
        return [FactorRiesgo(
            'Papeletas moderadas (3-4 en 90 días)',
            10,
            f'{n} papeletas',
            'medio',
        )]
    return []


def _factor_sanciones(personal, hoy) -> List[FactorRiesgo]:
    """Medidas disciplinarias recientes (últimos 180 días)."""
    try:
        from disciplinaria.models import MedidaDisciplinaria
        n = MedidaDisciplinaria.objects.filter(
            personal=personal,
            fecha_hechos__gte=hoy - timedelta(days=180),
        ).exclude(estado__in=['ANULADA', 'BORRADOR']).count()
    except Exception:
        return []

    if n > 0:
        return [FactorRiesgo(
            'Sanciones disciplinarias recientes',
            25,
            f'{n} medida(s) en 6 meses',
            'alto',
        )]
    return []


def _factor_sin_aumento(personal) -> List[FactorRiesgo]:
    """Sin aumento de sueldo en últimos 18 meses (basado en RegistroNomina)."""
    try:
        from nominas.models import RegistroNomina
        # Tomamos los últimos 18 registros ordenados por período
        registros = list(RegistroNomina.objects.filter(
            personal=personal,
        ).select_related('periodo').order_by(
            '-periodo__anio', '-periodo__mes',
        )[:18])
    except Exception:
        return []

    if len(registros) < 12:
        return []  # No hay historial suficiente

    sueldos = {float(r.sueldo_base or 0) for r in registros if r.sueldo_base}
    sueldos.discard(0.0)
    if len(sueldos) == 1:
        unico = next(iter(sueldos))
        return [FactorRiesgo(
            'Sin aumento de sueldo en 18+ meses',
            15,
            f'Sueldo S/ {unico:,.0f} sin cambio',
            'medio',
        )]
    return []


def _factor_evaluacion_baja(personal) -> List[FactorRiesgo]:
    """Última evaluación con puntaje bajo."""
    try:
        from evaluaciones.models import Evaluacion
        ultima = Evaluacion.objects.filter(
            evaluado=personal,
            estado__in=['COMPLETADA', 'CALIBRADA'],
        ).order_by('-fecha_completada', '-creado_en').first()
    except Exception:
        return []

    if not ultima:
        return []

    # puntaje_final = calibrado || total; típicamente 0-5
    puntaje = ultima.puntaje_calibrado or ultima.puntaje_total
    if puntaje is None:
        return []

    try:
        puntaje_f = float(puntaje)
    except (TypeError, ValueError):
        return []

    # Heurística: escala 0-5. <3 = bajo, 3-3.5 = borderline
    if puntaje_f < 3.0:
        return [FactorRiesgo(
            'Última evaluación baja',
            20,
            f'{puntaje_f:.1f}/5.0 puntos',
            'alto',
        )]
    elif puntaje_f < 3.5:
        return [FactorRiesgo(
            'Evaluación borderline',
            10,
            f'{puntaje_f:.1f}/5.0 puntos',
            'medio',
        )]
    return []


def _factor_sin_capacitacion(personal, hoy) -> List[FactorRiesgo]:
    """Sin capacitación asistida en último año (señal débil de baja participación)."""
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        n = AsistenciaCapacitacion.objects.filter(
            personal=personal,
            capacitacion__fecha_inicio__gte=hoy - timedelta(days=365),
            estado__in=['ASISTIO', 'PARCIAL'],
        ).count()
    except Exception:
        return []

    if n == 0:
        return [FactorRiesgo(
            'Sin capacitación en último año',
            8,
            'No participó en capacitaciones',
            'bajo',
        )]
    return []


def _factor_faltas(personal, hoy) -> List[FactorRiesgo]:
    """Faltas detectadas en RegistroTareo en últimos 90 días."""
    try:
        from asistencia.models import RegistroTareo
        n = RegistroTareo.objects.filter(
            personal=personal,
            fecha__gte=hoy - timedelta(days=90),
            codigo_dia__in=['F', 'FALTA'],
        ).count()
    except Exception:
        return []

    if n >= 5:
        return [FactorRiesgo(
            'Faltas recientes',
            15,
            f'{n} faltas en 90 días',
            'alto',
        )]
    elif n >= 3:
        return [FactorRiesgo(
            'Faltas ocasionales',
            8,
            f'{n} faltas en 90 días',
            'medio',
        )]
    return []


# ─────────────────────────────────────────────────────────────────────────────
# API PÚBLICA
# ─────────────────────────────────────────────────────────────────────────────

def calcular_score_rotacion(personal) -> dict:
    """
    Calcula score 0-100 de probabilidad de rotación.

    Returns:
        {
            'score': int,
            'nivel': 'CRITICO' | 'ALTO' | 'MEDIO' | 'BAJO',
            'factores': List[FactorRiesgo],
            'recomendaciones': List[str],
        }
    """
    hoy = timezone.localdate()
    factores: List[FactorRiesgo] = []

    factores.extend(_factor_antiguedad(personal, hoy))
    factores.extend(_factor_papeletas(personal, hoy))
    factores.extend(_factor_sanciones(personal, hoy))
    factores.extend(_factor_sin_aumento(personal))
    factores.extend(_factor_evaluacion_baja(personal))
    factores.extend(_factor_sin_capacitacion(personal, hoy))
    factores.extend(_factor_faltas(personal, hoy))

    score = sum(f.puntos for f in factores)
    score = min(score, 100)  # Cap

    # Niveles
    if score >= 70:
        nivel = 'CRITICO'
    elif score >= 50:
        nivel = 'ALTO'
    elif score >= 30:
        nivel = 'MEDIO'
    else:
        nivel = 'BAJO'

    # Recomendaciones accionables basadas en factores presentes
    recomendaciones: List[str] = []
    nombres = {f.nombre for f in factores}

    if score >= 50:
        recomendaciones.append('Programar reunión 1:1 esta semana')
    if any(n.startswith('Sin aumento') for n in nombres):
        recomendaciones.append('Considerar revisión salarial')
    if any(n.startswith('Papeletas') for n in nombres):
        recomendaciones.append('Indagar motivos personales/salud')
    if any(n.startswith('Trabajador nuevo') for n in nombres):
        recomendaciones.append('Reforzar onboarding y mentoring')
    if any(n.startswith('Sanciones') for n in nombres):
        recomendaciones.append('Plan de mejora con seguimiento mensual')
    if any(n.startswith('Faltas') for n in nombres):
        recomendaciones.append('Conversar sobre ausentismo y posibles causas')
    if 'Antigüedad alta sin movimiento' in nombres:
        recomendaciones.append('Explorar ruta de crecimiento o rotación interna')
    if any(n.startswith('Última evaluación baja') or n.startswith('Evaluación borderline')
           for n in nombres):
        recomendaciones.append('Plan de desarrollo individual con metas trimestrales')
    if 'Sin capacitación en último año' in nombres:
        recomendaciones.append('Inscribir en capacitación alineada al cargo')

    return {
        'score': score,
        'nivel': nivel,
        'factores': factores,
        'recomendaciones': recomendaciones,
    }


def top_personal_en_riesgo(limit: int = 20, min_score: int = 30) -> list:
    """
    Devuelve los top N personal activo con mayor score de rotación.

    Returns:
        Lista ordenada desc por score:
        [{'personal': Personal, 'analisis': {...}}, ...]
    """
    from personal.models import Personal

    activos = (
        Personal.objects.filter(estado='Activo')
        .select_related('subarea', 'subarea__area')
    )

    resultados = []
    for p in activos:
        analisis = calcular_score_rotacion(p)
        if analisis['score'] >= min_score:
            resultados.append({'personal': p, 'analisis': analisis})

    resultados.sort(key=lambda x: -x['analisis']['score'])
    return resultados[:limit]
