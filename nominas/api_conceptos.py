"""
API REST de Conceptos Remunerativos.

Endpoints:
- GET    /api/v1/conceptos/             list (filtros via query string)
- POST   /api/v1/conceptos/             create
- GET    /api/v1/conceptos/<id>/        detail
- PUT    /api/v1/conceptos/<id>/        update
- DELETE /api/v1/conceptos/<id>/        delete (solo no-sistema)
- GET    /api/v1/conceptos/templates/   lista de templates pre-armados
- POST   /api/v1/conceptos/templates/<key>/aplicar/  crea desde template
"""
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from .models import ConceptoRemunerativo
from .signals_audit import clear_audit_context, set_audit_context
from .views_conceptos import TEMPLATES_CONCEPTOS, detectar_inconsistencias


def _set_audit(request, accion_override=None):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
         or request.META.get('REMOTE_ADDR') or None
    set_audit_context(
        usuario=request.user if request.user.is_authenticated else None,
        ip=ip,
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:300],
        contexto=f'API:{request.path}'[:200],
        accion_override=accion_override,
    )


class ConceptoSerializer(serializers.ModelSerializer):
    inconsistencias = serializers.SerializerMethodField()
    plame_info = serializers.SerializerMethodField()

    class Meta:
        model = ConceptoRemunerativo
        fields = [
            'id', 'codigo', 'nombre', 'descripcion', 'categoria',
            'tipo', 'subtipo', 'formula', 'porcentaje', 'monto_fijo',
            'afecto_essalud', 'afecto_afp', 'afecto_onp',
            'afecto_renta', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
            'codigo_plame', 'casilla_plame', 'codigo_tregistro',
            'activo', 'orden', 'es_sistema',
            'inconsistencias', 'plame_info',
            'creado_en', 'actualizado_en',
        ]
        read_only_fields = ['id', 'es_sistema', 'inconsistencias',
                             'plame_info', 'creado_en', 'actualizado_en']

    def get_inconsistencias(self, obj):
        return detectar_inconsistencias(obj)

    def get_plame_info(self, obj):
        return {
            'codigo': obj.codigo_plame or None,
            'casilla': obj.casilla_plame or None,
            'sin_plame': not obj.codigo_plame,
        }

    def validate_codigo(self, value):
        # No permitir cambiar codigo en update
        if self.instance and self.instance.codigo != value:
            raise serializers.ValidationError('No se puede cambiar el código de un concepto existente.')
        return value


class _EscrituraSoloSuperuser(BasePermission):
    """ConceptoRemunerativo es config GLOBAL del deployment (sin campo
    empresa): la comparten las planillas de todas las empresas. Cualquier
    autenticado puede leer, pero solo superuser puede escribir — un admin
    trial de /onboarding/starter/ no debe poder alterar conceptos que usan
    las planillas de otras empresas."""
    message = 'Solo un superusuario puede modificar conceptos (configuración global).'

    def has_permission(self, request, view):
        if view.action in ('list', 'retrieve', 'templates', 'stats'):
            return True
        return bool(request.user and request.user.is_superuser)


@extend_schema(
    summary='Conceptos Remunerativos',
    description='CRUD de conceptos. Filtros: ?tipo=INGRESO&activo=true&categoria=SUELDO&q=texto',
    tags=['nominas-conceptos'],
)
class ConceptoViewSet(viewsets.ModelViewSet):
    """
    CRUD de conceptos remunerativos.

    Filtros (query string):
    - tipo: INGRESO / DESCUENTO / APORTE_EMPLEADOR
    - subtipo: REMUNERATIVO / NO_REMUNERATIVO / PROVISION
    - activo: true / false
    - categoria: SUELDO / BONIFICACION / etc.
    - q: búsqueda full-text en nombre, código, PLAME, descripción
    """
    serializer_class = ConceptoSerializer
    permission_classes = [IsAuthenticated, _EscrituraSoloSuperuser]
    queryset = ConceptoRemunerativo.objects.all()

    def get_queryset(self):
        qs = ConceptoRemunerativo.objects.all().order_by('tipo', 'orden', 'codigo')

        tipo = self.request.query_params.get('tipo')
        if tipo:
            qs = qs.filter(tipo=tipo)

        subtipo = self.request.query_params.get('subtipo')
        if subtipo:
            qs = qs.filter(subtipo=subtipo)

        categoria = self.request.query_params.get('categoria')
        if categoria:
            qs = qs.filter(categoria=categoria)

        activo = self.request.query_params.get('activo')
        if activo is not None:
            qs = qs.filter(activo=activo.lower() in ('true', '1', 'yes'))

        q = self.request.query_params.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(nombre__icontains=q) |
                Q(codigo__icontains=q) |
                Q(codigo_plame__icontains=q) |
                Q(descripcion__icontains=q)
            )

        return qs

    def destroy(self, request, *args, **kwargs):
        c = self.get_object()
        if c.es_sistema:
            return Response(
                {'detail': 'No se puede eliminar concepto del sistema'},
                status=status.HTTP_403_FORBIDDEN,
            )
        _set_audit(request)
        try:
            return super().destroy(request, *args, **kwargs)
        finally:
            clear_audit_context()

    def perform_create(self, serializer):
        _set_audit(self.request)
        try:
            return serializer.save()
        finally:
            clear_audit_context()

    def perform_update(self, serializer):
        _set_audit(self.request)
        try:
            return serializer.save()
        finally:
            clear_audit_context()

    @action(detail=False, methods=['get'])
    def templates(self, request):
        """GET /api/v1/conceptos/templates/ — Lista catálogo pre-armado."""
        items = []
        for key, t in TEMPLATES_CONCEPTOS.items():
            existing = ConceptoRemunerativo.objects.filter(codigo=t['codigo']).first()
            items.append({
                'key': key,
                'codigo': t['codigo'],
                'nombre': t['nombre'],
                'categoria': t.get('categoria', 'OTRO'),
                'tipo': t['tipo'],
                'subtipo': t['subtipo'],
                'codigo_plame': t.get('codigo_plame', ''),
                'descripcion': t.get('descripcion', ''),
                'instalado': existing is not None,
                'existing_id': existing.id if existing else None,
            })
        return Response({'templates': items, 'count': len(items)})

    @action(detail=False, methods=['post'], url_path=r'templates/(?P<key>[\w_-]+)/aplicar')
    def aplicar_template(self, request, key=None):
        """POST /api/v1/conceptos/templates/<key>/aplicar/ — Crea desde template."""
        t = TEMPLATES_CONCEPTOS.get(key)
        if not t:
            return Response({'error': 'Template no encontrado'}, status=status.HTTP_404_NOT_FOUND)
        if ConceptoRemunerativo.objects.filter(codigo=t['codigo']).exists():
            return Response({'error': f'Concepto "{t["codigo"]}" ya existe'}, status=status.HTTP_409_CONFLICT)
        _set_audit(request, accion_override='TEMPLATE')
        try:
            c = ConceptoRemunerativo.objects.create(**t)
        finally:
            clear_audit_context()
        return Response(ConceptoSerializer(c).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def autofix(self, request, pk=None):
        """POST /api/v1/conceptos/<id>/autofix/ — Aplica auto-fix de inconsistencias."""
        c = self.get_object()
        warns_antes = detectar_inconsistencias(c)
        changes = []

        if c.subtipo == 'NO_REMUNERATIVO':
            for f in ('afecto_essalud', 'afecto_afp', 'afecto_onp',
                      'afecto_cts', 'afecto_gratif', 'afecto_vacaciones'):
                if getattr(c, f):
                    setattr(c, f, False)
                    changes.append(f)

        elif c.subtipo == 'REMUNERATIVO' and c.tipo == 'INGRESO':
            if not any([c.afecto_essalud, c.afecto_afp, c.afecto_onp]):
                c.afecto_essalud = True
                c.afecto_afp = True
                c.afecto_onp = True
                c.afecto_renta = True
                c.afecto_cts = True
                c.afecto_gratif = True
                changes = ['auto_marcados_rem']

        if changes:
            c.save()

        warns_despues = detectar_inconsistencias(c)
        return Response({
            'concepto': ConceptoSerializer(c).data,
            'warns_antes': warns_antes,
            'warns_despues': warns_despues,
            'cambios': changes,
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """GET /api/v1/conceptos/stats/ — Estadísticas globales."""
        qs = ConceptoRemunerativo.objects.all()
        return Response({
            'total':       qs.count(),
            'activos':     qs.filter(activo=True).count(),
            'sistema':     qs.filter(es_sistema=True).count(),
            'custom':      qs.filter(es_sistema=False).count(),
            'con_plame':   qs.exclude(codigo_plame='').count(),
            'sin_plame':   qs.filter(codigo_plame='').count(),
            'por_tipo': {
                'INGRESO':          qs.filter(tipo='INGRESO').count(),
                'DESCUENTO':        qs.filter(tipo='DESCUENTO').count(),
                'APORTE_EMPLEADOR': qs.filter(tipo='APORTE_EMPLEADOR').count(),
            },
            'por_subtipo': {
                'REMUNERATIVO':    qs.filter(subtipo='REMUNERATIVO').count(),
                'NO_REMUNERATIVO': qs.filter(subtipo='NO_REMUNERATIVO').count(),
                'PROVISION':       qs.filter(subtipo='PROVISION').count(),
            },
        })
