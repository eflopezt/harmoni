"""
API: información del plan comercial del usuario actual.

GET /api/v1/me/plan/

Devuelve:
{
    "plan": "STARTER",
    "plan_display": "Starter — S/ 149/mes",
    "max_trabajadores": 30,
    "trabajadores_actuales": 25,
    "es_starter": true,
    "features_bloqueadas": ["reclutamiento", "portal", "capacitaciones", ...],
    "upgrade_url": "/upgrade/",
    "empresa": {
        "ruc": "20612345678",
        "razon_social": "Pixel Motion Design S.A.C.",
    }
}

Útil para:
- Integraciones que necesitan saber qué pueden hacer
- Mostrar info en topbar / cuenta del cliente
- Validar antes de invocar features (cliente puede esconder UI)
"""
from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


# Derivado de la fuente única core/planes.py (4 planes por módulos).
from core.planes import (PLANES, MODULOS, plan_max_trabajadores,
                         plan_display as _plan_display, plan_nivel,
                         plan_incluye_modulo)

PLAN_LIMITS = {code: plan_max_trabajadores(code) for code in PLANES}
PLAN_DISPLAY = {code: _plan_display(code) for code in PLANES}


def _features_bloqueadas(plan_code):
    """Lista de módulos NO incluidos en el plan (los que exigen nivel superior)."""
    return sorted(k for k in MODULOS if not plan_incluye_modulo(plan_code, k))


FEATURES_BLOQUEADAS_POR_PLAN = {code: _features_bloqueadas(code) for code in PLANES}


@extend_schema(
    summary='Plan comercial del usuario actual',
    description=(
        'Devuelve el plan vigente del user autenticado: tier, cap de '
        'trabajadores, count actual, features bloqueadas y datos de la '
        'empresa asociada (si la hay).\n\n'
        'Útil para integraciones que necesitan saber qué pueden hacer, '
        'o para clientes que quieren mostrar info de plan en su UI.'
    ),
    tags=['plan-billing'],
    responses={
        200: {
            'type': 'object',
            'properties': {
                'plan':                  {'type': 'string', 'enum': ['ASISTENCIA', 'PLANILLA', 'TALENTO', 'SUITE']},
                'plan_display':          {'type': 'string'},
                'max_trabajadores':      {'type': 'integer', 'nullable': True},
                'trabajadores_actuales': {'type': 'integer'},
                'es_starter':            {'type': 'boolean'},
                'features_bloqueadas':   {'type': 'array', 'items': {'type': 'string'}},
                'upgrade_url':           {'type': 'string'},
                'empresa': {
                    'type': 'object',
                    'nullable': True,
                    'properties': {
                        'ruc':          {'type': 'string'},
                        'razon_social': {'type': 'string'},
                    },
                },
            },
        },
    },
    examples=[
        OpenApiExample(
            'Cliente Starter (Pixel Motion)',
            value={
                'plan': 'STARTER',
                'plan_display': 'Starter — S/ 149/mes (hasta 30 colaboradores)',
                'max_trabajadores': 30,
                'trabajadores_actuales': 25,
                'es_starter': True,
                'features_bloqueadas': ['reclutamiento', 'portal', 'capacitaciones', 'evaluaciones'],
                'upgrade_url': '/upgrade/',
                'empresa': {'ruc': '20612345678', 'razon_social': 'Pixel Motion Design S.A.C.'},
            },
            response_only=True,
        ),
    ],
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def api_me_plan(request):
    """
    GET /api/v1/me/plan/

    Devuelve info del plan comercial del user autenticado.
    """
    user = request.user

    # Resolver empresa del user
    empresa = None
    try:
        personal = getattr(user, 'personal', None)
        if personal:
            empresa = personal.empresa
    except Exception:
        pass

    from core.middleware_plan_starter import resolve_plan, is_starter_user
    from core.planes import PLAN_DEFAULT
    plan_code = empresa.plan if empresa else resolve_plan(user) if user.is_authenticated else PLAN_DEFAULT

    # Contar trabajadores activos
    workers_count = 0
    if empresa:
        try:
            from personal.models import Personal
            workers_count = Personal.objects.filter(
                empresa=empresa, estado='Activo'
            ).count()
        except Exception:
            workers_count = 0

    es_starter = is_starter_user(user)

    return Response({
        'plan':                  plan_code,
        'plan_display':          PLAN_DISPLAY.get(plan_code, plan_code),
        'max_trabajadores':      PLAN_LIMITS.get(plan_code),
        'trabajadores_actuales': workers_count,
        'es_starter':            es_starter,
        'features_bloqueadas':   FEATURES_BLOQUEADAS_POR_PLAN.get(plan_code, []),
        'upgrade_url':           '/upgrade/',
        'empresa': {
            'ruc':          empresa.ruc if empresa else None,
            'razon_social': empresa.razon_social if empresa else None,
        } if empresa else None,
    })
