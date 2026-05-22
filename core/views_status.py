"""
Status page público — para clientes potenciales que quieren verificar
que el sistema está vivo y la demo está actualizada.

URL: /status/

NO requiere autenticación (página pública).
"""
import os
import subprocess
from datetime import datetime

from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import cache_page


# Lista oficial de features 2026 entregadas (para mostrar conteo)
FEATURES_2026 = [
    # Reclutamiento
    'Pipeline Kanban con filtros score/fuente/tag',
    'Pipeline bulk actions (mover, descartar, etiquetar, nota)',
    'Mi Día Reclutador — home personalizado',
    'Tags / etiquetas en candidatos',
    'PDF candidato para entrevista',
    'Atajos teclado en Pipeline (J/K/H/L/Enter/M/D/P/T)',
    'Comparación side-by-side hasta 4 candidatos',
    'Banco de Talento (rescatar descartados)',
    'Calendario de entrevistas mensual',
    'Búsqueda global Ctrl+K',
    'Stats Reclutadores con medallas',
    'PDF Stats Reclutadores mensual',
    'Emails automáticos en hitos del pipeline',
    'Notifs in-app a reclutadores',
    'API REST DRF con 5 custom actions',
    'Filtro candidatos estancados + alertas',
    'CV parser PyMuPDF/pdfplumber/docx',
    'Detección duplicados (email/phone/name fuzzy)',
    'Funnel reclutamiento ejecutivo',
    'Bulk import CSV/Excel',
    'Score matching explicado',
    'AI Summary del CV (Gemini/DeepSeek)',
    # Dashboard / BI
    'Dashboard Ejecutivo Unificado cross-módulo',
    'Reportes BI Excel ejecutivo (8 tabs)',
    # Gastronomía
    'Onboarding Gastro Checklist 30/60/90',
    'BPM/HACCP tracking certificaciones',
    'Briefing del Día (handover pre-shift)',
    'Cuadrícula Semanal del Local',
    'Pulse del Grupo (dashboard multi-local)',
    'Encuestas Pulse semanales (NPS + heatmap)',
    # IA
    'Predictor IA de Rotación de Personal',
    # Workflows
    'Evaluaciones 360 con radar comparativo',
    'Vacaciones workflow + calendario anual + PDF',
    'Disciplinaria workflow + cartas PDF + timeline',
    'Préstamos cronograma + integración descuentos',
    # Salarios
    'Bandas salariales + análisis equidad + simulador',
    # UX
    'Mobile UX polish con FAB + glassmorphism',
    'Plantillas email editables desde admin',
    'Home admin tiles 2026',
    'Menu lateral admin reorganizado',
]


def _git_commit_short():
    """Lee el commit actual del repo. Cachea entre requests."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        return result.stdout.strip() if result.returncode == 0 else 'unknown'
    except Exception:
        return 'unknown'


def _git_last_commit_date():
    """Fecha del último commit."""
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%cI'],
            capture_output=True, text=True, timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if result.returncode == 0:
            iso = result.stdout.strip()
            # Convertir a datetime para formateo
            try:
                return datetime.fromisoformat(iso)
            except ValueError:
                return iso
        return None
    except Exception:
        return None


def _db_check():
    """Verifica que la DB responde."""
    try:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        return True
    except Exception:
        return False


def _redis_check():
    """Verifica que Redis responde (si está configurado)."""
    try:
        from django.core.cache import cache
        cache.set('status_check', '1', 5)
        return cache.get('status_check') == '1'
    except Exception:
        return False


def _smtp_check():
    """Verifica que SMTP está configurado (sin enviar email)."""
    try:
        from comunicaciones.models import ConfiguracionSMTP
        config = ConfiguracionSMTP.get()
        return config.activa
    except Exception:
        return False


@cache_page(60)  # Cache 1 min
def status_page(request):
    """Página HTML pública con estado del sistema."""
    context = {
        'git_commit':       _git_commit_short(),
        'git_date':         _git_last_commit_date(),
        'db_ok':            _db_check(),
        'redis_ok':         _redis_check(),
        'smtp_ok':          _smtp_check(),
        'features_count':   len(FEATURES_2026),
        'features_list':    FEATURES_2026,
        'ahora':            timezone.now(),
        'app_name':         'Harmoni ERP',
        'demo_url':         'https://demo.harmoni.pe',
    }
    return render(request, 'core/status.html', context)


def status_json(request):
    """Endpoint JSON para health checks externos / monitoring."""
    return JsonResponse({
        'status':         'ok',
        'git_commit':     _git_commit_short(),
        'db':             'ok' if _db_check() else 'fail',
        'redis':          'ok' if _redis_check() else 'fail',
        'smtp':           'ok' if _smtp_check() else 'fail',
        'timestamp':      timezone.now().isoformat(),
        'features_count': len(FEATURES_2026),
    })
