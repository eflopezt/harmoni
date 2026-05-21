"""Detector de duplicados de postulaciones (adaptado de NexoTalent).

Estrategias en orden de confianza:
1. DNI exacto (100)
2. Email exacto (95)
3. Celular normalizado (90)
4. Nombre fuzzy con Levenshtein (60-80)

Devuelve lista de tuplas (Postulacion, motivo, score).
"""
from __future__ import annotations

import unicodedata
from typing import List, Tuple

from django.db.models import Q


def _normalize_phone(phone: str) -> str:
    if not phone:
        return ''
    digits = ''.join(c for c in phone if c.isdigit())
    return digits[-9:]


def _strip_acentos(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', s or '')
        if unicodedata.category(c) != 'Mn'
    )


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        curr = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            ins = prev[j] + 1
            dele = curr[j - 1] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            curr[j] = min(ins, dele, sub)
        prev = curr
    return prev[-1]


def buscar_duplicados(
    *,
    email: str = '',
    telefono: str = '',
    nombre_completo: str = '',
    exclude_id: int | None = None,
    limit: int = 10,
) -> List[Tuple]:
    """Busca postulaciones posiblemente duplicadas.

    Devuelve lista de tuplas (Postulacion, motivo, score 0-100).
    """
    from .models import Postulacion

    matches = []
    seen = set()

    def _add(cand, motivo, score):
        if cand.pk == exclude_id or cand.pk in seen:
            return
        seen.add(cand.pk)
        matches.append((cand, motivo, score))

    # 1) Email exacto (más confiable que DNI ya que no siempre lo tenemos)
    if email:
        for c in Postulacion.objects.filter(email__iexact=email.strip()):
            _add(c, 'Email exacto', 95)

    # 2) Teléfono normalizado (últimos 9 dígitos)
    if telefono:
        tel_norm = _normalize_phone(telefono)
        if tel_norm and len(tel_norm) >= 9:
            for c in Postulacion.objects.filter(
                telefono__icontains=tel_norm,
            )[:20]:
                if _normalize_phone(c.telefono) == tel_norm:
                    _add(c, 'Teléfono coincide', 90)

    # 3) Fuzzy nombre completo (si hay 5+ chars)
    if nombre_completo and len(nombre_completo) >= 5:
        nombre_norm = _strip_acentos(nombre_completo).upper()
        # Prefiltro: primera palabra del nombre
        primera = nombre_norm.split()[0] if nombre_norm.split() else ''
        if primera:
            candidatos = Postulacion.objects.filter(
                nombre_completo__icontains=primera,
            )[:50]
            for c in candidatos:
                cand_norm = _strip_acentos(c.nombre_completo).upper()
                if not cand_norm:
                    continue
                # Distancia normalizada
                dist = _levenshtein(nombre_norm, cand_norm)
                maxlen = max(len(nombre_norm), len(cand_norm))
                if maxlen == 0:
                    continue
                similarity = 1 - (dist / maxlen)
                if similarity >= 0.85:
                    score = int(60 + similarity * 30)  # 60-90 range
                    _add(c, f'Nombre similar ({similarity*100:.0f}%)', score)

    # Ordenar por score descendente
    matches.sort(key=lambda t: t[2], reverse=True)
    return matches[:limit]
