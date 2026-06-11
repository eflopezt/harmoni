"""
Aislamiento multi-tenant para la API DRF (/api/v1/).

Problema que resuelve: los ViewSets exponían `Model.objects.all()` con solo
IsAuthenticated, así que cualquier usuario autenticado (incluido un trial
self-serve de /onboarding/starter/) podía listar datos de TODAS las empresas.

Uso:

    class PersonalViewSet(EmpresaFilteredViewSetMixin, viewsets.ModelViewSet):
        empresa_field = 'empresa'              # FK directo
        ...

    class CuotaPrestamoViewSet(EmpresaFilteredViewSetMixin, ...):
        empresa_field = 'prestamo__personal__empresa'   # ruta ORM

    class TipoDocumentoViewSet(EmpresaFilteredViewSetMixin, ...):
        empresa_global = True                  # catálogo compartido, no se filtra

Reglas (en orden):
  1. Superuser ve todo (consistente con la vista consolidada del web).
  2. `empresa_global = True` → catálogo compartido entre empresas, sin filtro.
  3. Sin `empresa_field` (modelo sin ruta ORM hacia Empresa, p.ej. Vacante,
     Encuesta, KPISnapshot) → deny-by-default: queryset.none() y escritura
     prohibida. Cuando el modelo gane tenancy se le asigna su empresa_field.
  4. Con `empresa_field`: se filtra por la empresa activa; si no se puede
     resolver una empresa → queryset.none() (deny-by-default).

Resolución de la empresa activa:
  - `request.empresa_actual` (inyectado por empresas.middleware.EmpresaMiddleware
    a partir de subdominio/sesión). Cubre las llamadas con sesión web.
  - Fallback: `user.personal_data.empresa`. Necesario para JWT: la
    autenticación DRF ocurre DESPUÉS del middleware, así que en llamadas con
    Bearer token `request.empresa_actual` es None aunque el usuario sea un
    empleado vinculado.
"""
from rest_framework.exceptions import PermissionDenied


class EmpresaFilteredViewSetMixin:
    """Filtra el queryset y valida escrituras contra la empresa activa."""

    #: Ruta ORM desde el modelo del ViewSet hasta el FK Empresa
    #: ('empresa', 'personal__empresa', 'prestamo__personal__empresa', ...).
    #: None = el modelo no tiene tenancy → deny-by-default salvo empresa_global.
    empresa_field = None

    #: True = catálogo compartido entre empresas (tipos, etapas, competencias):
    #: no se filtra ni se valida empresa en escritura.
    empresa_global = False

    def get_empresa_activa(self):
        empresa = getattr(self.request, 'empresa_actual', None)
        if empresa is not None:
            return empresa
        user = getattr(self.request, 'user', None)
        personal = getattr(user, 'personal_data', None) if user else None
        return getattr(personal, 'empresa', None)

    def get_queryset(self):
        qs = super().get_queryset()
        # drf-spectacular genera el schema con una vista fake sin request real
        if getattr(self, 'swagger_fake_view', False):
            return qs.none()
        user = getattr(getattr(self, 'request', None), 'user', None)
        if user is None:
            return qs.none()
        if user.is_superuser or self.empresa_global:
            return qs
        if not self.empresa_field:
            return qs.none()
        empresa = self.get_empresa_activa()
        if empresa is None:
            return qs.none()
        return qs.filter(**{self.empresa_field: empresa})

    # ── Escritura ────────────────────────────────────────────────

    def _empresa_del_payload(self, serializer):
        """Resuelve la empresa a la que pertenece el objeto del payload,
        siguiendo empresa_field sobre validated_data (los FKs ya vienen
        como instancias). Devuelve None si no hay forma de resolverla."""
        partes = self.empresa_field.split('__')
        if partes[0] == 'empresa':
            return serializer.validated_data.get('empresa')
        obj = serializer.validated_data.get(partes[0])
        if obj is None and serializer.instance is not None:
            obj = getattr(serializer.instance, partes[0], None)
        for parte in partes[1:]:
            if obj is None:
                return None
            obj = getattr(obj, parte, None)
        return obj

    def validar_empresa_payload(self, serializer):
        """Bloquea crear/asociar objetos que pertenezcan a otra empresa.
        Los ViewSets que sobreescriben perform_create/perform_update deben
        llamar esto explícitamente (la sobreescritura pisa la del mixin)."""
        user = self.request.user
        if user.is_superuser or self.empresa_global:
            return
        if not self.empresa_field:
            raise PermissionDenied(
                'Este recurso no admite escritura por API en modo multi-empresa.')
        empresa = self.get_empresa_activa()
        if empresa is None:
            raise PermissionDenied('No hay una empresa activa.')
        empresa_payload = self._empresa_del_payload(serializer)
        if empresa_payload is not None and empresa_payload.pk != empresa.pk:
            raise PermissionDenied('El objeto referenciado pertenece a otra empresa.')

    def validar_empresa_objeto(self, obj, path=None):
        """Variante para actions/bulk que reciben instancias ya cargadas.
        `path` es la ruta ORM desde `obj` hasta Empresa; por defecto
        empresa_field (es decir, obj es del modelo del ViewSet)."""
        user = self.request.user
        if user.is_superuser or self.empresa_global:
            return
        path = path or self.empresa_field
        if not path:
            raise PermissionDenied(
                'Este recurso no admite escritura por API en modo multi-empresa.')
        empresa = self.get_empresa_activa()
        if empresa is None:
            raise PermissionDenied('No hay una empresa activa.')
        for parte in path.split('__'):
            if obj is None:
                break
            obj = getattr(obj, parte, None)
        if obj is not None and obj.pk != empresa.pk:
            raise PermissionDenied('El objeto referenciado pertenece a otra empresa.')

    def perform_create(self, serializer):
        self.validar_empresa_payload(serializer)
        user = self.request.user
        # FK directo y usuario tenant: forzar la empresa activa para que el
        # objeto no nazca sin empresa (o con una ajena) aunque el serializer
        # no exponga el campo.
        if (self.empresa_field == 'empresa' and not user.is_superuser
                and not self.empresa_global):
            serializer.save(empresa=self.get_empresa_activa())
            return
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self.validar_empresa_payload(serializer)
        super().perform_update(serializer)
