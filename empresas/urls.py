from django.urls import include, path
from django.views.generic import RedirectView
from . import views
from . import views_billing
from . import views_admin

urlpatterns = [
    path('', views.empresas_panel, name='empresas_panel'),
    path('pulse/', views.pulse_del_grupo, name='pulse_del_grupo'),
    path('pulse/<int:pk>/', views.pulse_local_detalle, name='pulse_local_detalle'),
    path('pulse/<int:pk>/cuadricula/', views.cuadricula_semanal_local, name='cuadricula_semanal_local'),
    path('nueva/', views.empresa_crear, name='empresa_crear'),
    path('<int:pk>/editar/', views.empresa_editar, name='empresa_editar'),
    path('<int:pk>/datos/', views.empresa_datos, name='empresa_datos'),
    path('<int:pk>/configuracion/', views.configuracion_empresa, name='configuracion_empresa'),
    path('seleccionar/', views.seleccionar_empresa, name='empresa_seleccionar'),
    path('onboarding/', include('empresas.urls_onboarding')),

    # Billing legacy → redirige a los paneles VIVOS (sistema consolidado).
    # El subsistema viejo (Plan/Suscripcion + BillingMiddleware) quedó retirado;
    # estas rutas se mantienen para no romper enlaces/reverse y llevar al panel real.
    path('billing/', RedirectView.as_view(pattern_name='mi_cuenta_plan', permanent=False), name='billing_dashboard'),
    path('billing/upgrade/', RedirectView.as_view(pattern_name='upgrade_plan', permanent=False), name='billing_upgrade'),
    path('billing/pago/', RedirectView.as_view(pattern_name='mi_cuenta_plan', permanent=False), name='billing_payment'),
    path('billing/comprobante/<int:pago_id>/', RedirectView.as_view(url='/cuenta/plan/', permanent=False), name='billing_invoice'),
    path('billing/admin/', RedirectView.as_view(pattern_name='suscripciones_admin', permanent=False), name='admin_billing_dashboard'),
    path('billing/admin/action/', RedirectView.as_view(pattern_name='suscripciones_admin', permanent=False), name='admin_billing_action'),
]
