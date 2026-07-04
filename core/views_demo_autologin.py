"""
Auto-login para demos comerciales — un clic, sin teclear credenciales.

Uso (en WhatsApp/email):
    https://demo.harmoni.pe/d/starter      → login automático como demo2
    https://demo.harmoni.pe/d/enterprise   → login automático como demo

Seguridad:
    - Solo funciona en hosts demo.* (DEMO_HOSTS configurable).
    - Solo logea users de la whitelist DEMO_AUTOLOGIN_USERS.
    - El user demo no debe tener datos sensibles reales — es ambiente demo.
    - No usar este patrón en producción.
"""
import logging
import time

from django.conf import settings
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import redirect

logger = logging.getLogger('core.demo_autologin')


# Rate-limit: máximo N hits por IP por ventana de tiempo (segundos)
RATE_LIMIT_HITS    = 10    # hits
RATE_LIMIT_WINDOW  = 60    # segundos (1 minuto)


def _check_rate_limit(request):
    """
    Devuelve True si la IP excedió el rate limit, False si está OK.
    Usa Django cache (Redis en prod) con TTL = ventana.
    """
    # Extraer IP (considerar X-Forwarded-For si está detrás de proxy)
    ip = (
        request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
        or request.META.get('REMOTE_ADDR', '0.0.0.0')
    )
    key = f'autologin_rl:{ip}'
    hits = cache.get(key, 0)
    if hits >= RATE_LIMIT_HITS:
        logger.warning(
            f"Rate limit excedido — IP={ip} hits={hits} ventana={RATE_LIMIT_WINDOW}s"
        )
        return True
    # Incrementar contador (set initial con TTL si era 0)
    if hits == 0:
        cache.set(key, 1, timeout=RATE_LIMIT_WINDOW)
    else:
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, hits + 1, timeout=RATE_LIMIT_WINDOW)
    return False


# Escenarios de demo: cada uno logea un user y fija la empresa/vista adecuada.
#   modo='consolidado' → grupo multiempresa (vista de todas las empresas).
#   ruc=<ruc>          → empresa ÚNICA (se selecciona esa).
DEMO_ESCENARIOS = {
    'gastronomia': {
        'user': 'demo', 'label': 'Grupo Gastronómico', 'icon': 'fa-utensils',
        'sub': 'Multiempresa · varios restaurantes (un solo rubro)',
        'modo': 'consolidado',
    },
    'mineria': {
        'user': 'demo', 'label': 'Minera', 'icon': 'fa-hard-hat',
        'sub': 'Empresa única · régimen 14x7, cuadrilla foránea',
        'ruc': '20600000029',
    },
    'construccion': {
        'user': 'demo', 'label': 'Constructora', 'icon': 'fa-helmet-safety',
        'sub': 'Empresa única · construcción civil (operario/oficial/peón)',
        'ruc': '20600000011',
    },
    'agencia': {
        'user': 'demo2', 'label': 'Agencia Creativa', 'icon': 'fa-palette',
        'sub': 'Empresa única · audiovisual / agencia',
        'ruc': '20612345678',
    },
}

# Slug → escenario (incluye alias de compatibilidad con enlaces viejos).
_ALIAS = {
    'starter': 'agencia', 's': 'agencia', 'pixelmotion': 'agencia',
    'enterprise': 'gastronomia', 'e': 'gastronomia', 'edo': 'gastronomia',
    'grupo': 'gastronomia', 'gastro': 'gastronomia',
    'mina': 'mineria', 'construccion-civil': 'construccion',
}


def _resolver_escenario(slug):
    key = _ALIAS.get(slug.lower(), slug.lower())
    return key, DEMO_ESCENARIOS.get(key)


def _aplicar_empresa(request, esc, key=None):
    """Fija en la sesión la empresa/vista del escenario + marca el escenario
    elegido (para que el home no vuelva a pedir la selección)."""
    if key:
        request.session['demo_escenario'] = key
    if esc.get('modo') == 'consolidado':
        request.session['modo_consolidado'] = True
        request.session.pop('empresa_actual_id', None)
        request.session.pop('empresa_actual_nombre', None)
        return
    ruc = esc.get('ruc')
    if ruc:
        try:
            from empresas.models import Empresa
            emp = Empresa.objects.filter(ruc=ruc, activa=True).first()
            if emp:
                request.session['empresa_actual_id'] = emp.pk
                request.session['empresa_actual_nombre'] = emp.nombre_display
                request.session.pop('modo_consolidado', None)
        except Exception:
            pass


# Hosts permitidos para auto-login (cualquier subdom demo.*)
def _is_demo_host(request):
    host = request.get_host().lower()
    # Permitir demo.harmoni.pe, demo-staging.*, localhost (dev)
    return (
        host.startswith('demo.')
        or host.startswith('demo-')
        or 'localhost' in host
        or '127.0.0.1' in host
    )


def demo_autologin(request, slug):
    """
    Login automático para demos. Slug determina qué user demo se usa.

    Si el slug no existe o el host no es demo.* → 404.
    Si el user no existe en DB → 404 con log.
    """
    if not _is_demo_host(request):
        logger.warning(
            f"Intento de auto-login en host no-demo: {request.get_host()} slug={slug}"
        )
        raise Http404("Auto-login solo disponible en host demo.")

    # Rate-limit por IP (10 hits / 60s)
    if _check_rate_limit(request):
        return HttpResponse(
            'Demasiados intentos. Espera un momento antes de reintentar.',
            status=429,
            content_type='text/plain; charset=utf-8',
        )

    key, esc = _resolver_escenario(slug)
    if not esc:
        logger.info(f"Auto-login slug desconocido: {slug}")
        raise Http404(f"Demo '{slug}' no existe.")
    username = esc['user']

    User = get_user_model()
    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        logger.error(f"Auto-login: user '{username}' no existe en DB")
        raise Http404("Demo no disponible.")

    # Si ya está autenticado como otro user, hacer logout primero
    if request.user.is_authenticated and request.user.username != username:
        logout(request)

    # Login (especificamos backend porque hay varios configurados)
    user.backend = f"{ModelBackend.__module__}.{ModelBackend.__name__}"
    login(request, user)
    _aplicar_empresa(request, esc, key=key)
    logger.info(f"Auto-login OK: escenario={key} user={username} from {request.META.get('REMOTE_ADDR')}")

    return redirect('/')


def demo_landing(request):
    """Página de bienvenida de la demo: tarjetas para elegir el escenario
    (grupo gastronómico, minera, constructora, agencia). Cada una entra con
    un clic al ambiente correspondiente."""
    if not _is_demo_host(request):
        raise Http404("Solo disponible en el ambiente demo.")
    from django.shortcuts import render
    escenarios = [
        {'slug': k, **v} for k, v in DEMO_ESCENARIOS.items()
    ]
    return render(request, 'core/demo_landing.html', {'escenarios': escenarios})
