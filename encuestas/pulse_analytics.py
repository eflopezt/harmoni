"""
Analítica del Pulse Semanal.

Funciones puras (sin side-effects) que reciben el queryset/filtros y devuelven
estructuras Python listas para serializar a JSON (Chart.js) o pasar al template.

Diseñado para gastronomía: pensado por local (Empresa), pero degrada
graciosamente a Area si no hay multi-empresa configurado.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import date
from typing import Iterable

from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import PulseSemanal


# ── Configuración ─────────────────────────────────────────────────────────────

STOPWORDS = {
    'el', 'la', 'los', 'las', 'de', 'del', 'que', 'es', 'en', 'un', 'una',
    'unos', 'unas', 'y', 'o', 'a', 'al', 'se', 'por', 'para', 'con', 'sin',
    'lo', 'le', 'su', 'sus', 'mi', 'mis', 'tu', 'tus', 'yo', 'me', 'te',
    'nos', 'no', 'si', 'sí', 'esta', 'este', 'esto', 'esos', 'esas',
    'ese', 'esa', 'eso', 'pero', 'como', 'cuando', 'donde', 'porque',
    'muy', 'mas', 'más', 'menos', 'ya', 'aun', 'aún', 'también', 'tambien',
    'hay', 'ser', 'estar', 'son', 'soy', 'somos', 'estoy', 'esta', 'están',
    'va', 'voy', 'vamos', 'fui', 'fue', 'era', 'eran', 'sea', 'mientras',
    'sobre', 'bajo', 'entre', 'tras', 'hasta', 'desde', 'aqui', 'allí',
}

_WORD_RE = re.compile(r"[a-záéíóúñü0-9]+", re.IGNORECASE)


def _semana_actual(today: date | None = None) -> tuple[int, int]:
    """Devuelve (anio_iso, semana_iso) para 'hoy'."""
    today = today or timezone.now().date()
    iso = today.isocalendar()
    return iso.year, iso.week


def _qs_base(empresa_id=None, semana=None, anio=None):
    """Queryset base con filtros opcionales aplicados."""
    qs = PulseSemanal.objects.all()
    if empresa_id is not None:
        qs = qs.filter(empresa_id=empresa_id)
    if semana is not None:
        qs = qs.filter(semana=semana)
    if anio is not None:
        qs = qs.filter(anio=anio)
    return qs


# ── 1. Animo semanal ──────────────────────────────────────────────────────────

def calcular_animo_semanal(empresa_id=None, semana=None, anio=None):
    """Devuelve dict con métricas de ánimo + participación para la semana indicada.

    Si no se pasa semana/anio, usa la semana ISO actual.

    Retorna:
        {
            'semana': int, 'anio': int,
            'respuestas': int,
            'universo': int,
            'participacion_pct': float,
            'animo_promedio': float | None,
            'breakdown': {1: n, 2: n, 3: n, 4: n, 5: n},
            'nps_promedio': float | None,
            'enps_score': int | None,  # -100 a +100
        }
    """
    if semana is None or anio is None:
        anio_actual, sem_actual = _semana_actual()
        semana = semana if semana is not None else sem_actual
        anio = anio if anio is not None else anio_actual

    qs = _qs_base(empresa_id=empresa_id, semana=semana, anio=anio)

    respuestas = qs.count()
    animo_avg = qs.aggregate(a=Avg('animo'))['a']
    nps_avg = qs.exclude(nps__isnull=True).aggregate(a=Avg('nps'))['a']

    breakdown = {i: 0 for i in range(1, 6)}
    for row in qs.values('animo').annotate(n=Count('id')):
        breakdown[row['animo']] = row['n']

    # eNPS
    enps_score = None
    try:
        nps_qs = qs.exclude(nps__isnull=True)
        total_nps = nps_qs.count()
        if total_nps > 0:
            promotores = nps_qs.filter(nps__gte=9).count()
            detractores = nps_qs.filter(nps__lte=6).count()
            enps_score = round(((promotores - detractores) / total_nps) * 100)
    except Exception:
        pass

    # Universo: trabajadores activos (filtrado por empresa si aplica)
    universo = 0
    try:
        from personal.models import Personal
        u_qs = Personal.objects.filter(estado='Activo')
        if empresa_id is not None:
            u_qs = u_qs.filter(empresa_id=empresa_id)
        universo = u_qs.count()
    except Exception:
        pass

    participacion_pct = round((respuestas / universo) * 100, 1) if universo else 0.0

    return {
        'semana': int(semana),
        'anio': int(anio),
        'respuestas': respuestas,
        'universo': universo,
        'participacion_pct': participacion_pct,
        'animo_promedio': round(float(animo_avg), 2) if animo_avg is not None else None,
        'breakdown': breakdown,
        'nps_promedio': round(float(nps_avg), 2) if nps_avg is not None else None,
        'enps_score': enps_score,
    }


# ── 2. Heatmap por local ──────────────────────────────────────────────────────

def heatmap_por_local(anio: int, semana_inicio: int, semana_fin: int):
    """Matriz para heatmap: filas=empresas (o áreas si no hay empresa), columnas=semanas.

    Retorna:
        {
            'semanas': [w1, w2, …],
            'filas': [
                {'nombre': 'Local A', 'empresa_id': 1, 'celdas': {w1: 4.2, w2: None, …}},
                …
            ],
        }
    """
    semanas = list(range(int(semana_inicio), int(semana_fin) + 1))

    qs = (
        PulseSemanal.objects
        .filter(anio=anio, semana__gte=semana_inicio, semana__lte=semana_fin)
        .values('empresa_id', 'semana')
        .annotate(animo_avg=Avg('animo'), n=Count('id'))
    )

    # Agrupar por empresa → semana
    matriz: dict[int | None, dict[int, float | None]] = defaultdict(dict)
    for row in qs:
        matriz[row['empresa_id']][row['semana']] = (
            round(float(row['animo_avg']), 2) if row['animo_avg'] is not None else None
        )

    # Resolver nombres de empresa (o fallback Area)
    nombres: dict[int | None, str] = {}
    empresa_ids = [eid for eid in matriz.keys() if eid is not None]
    if empresa_ids:
        try:
            from empresas.models import Empresa
            for e in Empresa.objects.filter(pk__in=empresa_ids):
                nombres[e.pk] = e.nombre_comercial or e.razon_social
        except Exception:
            pass

    # Fallback para pulses sin empresa: agrupar bajo "Sin local"
    if None in matriz:
        nombres[None] = 'Sin local asignado'

    filas = []
    for eid, celdas in matriz.items():
        filas.append({
            'empresa_id': eid,
            'nombre': nombres.get(eid, f'Empresa #{eid}'),
            'celdas': {w: celdas.get(w) for w in semanas},
        })
    filas.sort(key=lambda f: f['nombre'])

    return {'semanas': semanas, 'filas': filas}


# ── 3. Tendencia 12 semanas ───────────────────────────────────────────────────

def tendencia_12_semanas(empresa_id=None, n_semanas: int = 12):
    """Tendencia de ánimo + NPS de las últimas N semanas ISO.

    Retorna lista ordenada cronológicamente: [(semana, anio, animo_avg, n, nps_avg), …]
    """
    today = timezone.now().date()
    # Generar (anio, semana) de las últimas N semanas
    semanas_obj = []
    cur = today
    seen = set()
    while len(semanas_obj) < n_semanas:
        iso = cur.isocalendar()
        key = (iso.year, iso.week)
        if key not in seen:
            seen.add(key)
            semanas_obj.append(key)
        # retroceder 7 días
        from datetime import timedelta
        cur = cur - timedelta(days=7)

    semanas_obj.reverse()  # cronológico

    out = []
    for anio, semana in semanas_obj:
        qs = _qs_base(empresa_id=empresa_id, semana=semana, anio=anio)
        n = qs.count()
        animo_avg = qs.aggregate(a=Avg('animo'))['a']
        nps_avg = qs.exclude(nps__isnull=True).aggregate(a=Avg('nps'))['a']
        out.append((
            int(semana),
            int(anio),
            round(float(animo_avg), 2) if animo_avg is not None else None,
            n,
            round(float(nps_avg), 2) if nps_avg is not None else None,
        ))
    return out


# ── 4. Top propuestas (bag of words simple) ───────────────────────────────────

def _tokenize(text: str) -> Iterable[str]:
    if not text:
        return []
    return (
        tok.lower()
        for tok in _WORD_RE.findall(text)
        if len(tok) >= 3 and tok.lower() not in STOPWORDS
    )


def top_propuestas(empresa_id=None, semana=None, anio=None, top_n: int = 10):
    """Top palabras frecuentes en propuestas + que_falta.

    Retorna: [{'palabra': 'turnos', 'count': 12}, …]
    """
    qs = _qs_base(empresa_id=empresa_id, semana=semana, anio=anio)
    counter: Counter[str] = Counter()
    for que_falta, propuestas in qs.values_list('que_falta', 'propuestas'):
        for tok in _tokenize(que_falta or ''):
            counter[tok] += 1
        for tok in _tokenize(propuestas or ''):
            counter[tok] += 1

    return [
        {'palabra': palabra, 'count': cnt}
        for palabra, cnt in counter.most_common(top_n)
    ]


# ── Extra utilitario: respuestas crudas para sección "Falta esta semana" ──────

def respuestas_texto(empresa_id=None, semana=None, anio=None, limite: int = 50):
    """Textos libres (que_falta + propuestas) shuffled, SIN identificar autor.

    Retorna: [{'que_falta': str, 'propuestas': str, 'animo': int}, …]
    """
    import random as _rnd
    qs = _qs_base(empresa_id=empresa_id, semana=semana, anio=anio)
    rows = [
        {'que_falta': r[0] or '', 'propuestas': r[1] or '', 'animo': r[2]}
        for r in qs.values_list('que_falta', 'propuestas', 'animo')
        if (r[0] and r[0].strip()) or (r[1] and r[1].strip())
    ]
    _rnd.shuffle(rows)
    return rows[:limite]
