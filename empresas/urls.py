from django.urls import include, path
from . import views
from . import views_billing
from . import views_admin

urlpatterns = [
    path('', views.empresas_panel, name='empresas_panel'),
    path('nueva/', views.empresa_crear, name='empresa_crear'),
    path('<int:pk>/editar/', views.empresa_editar, name='empresa_editar'),
    path('seleccionar/', views.seleccionar_empresa, name='empresa_seleccionar'),
    path('onboarding/', include('empresas.urls_onboarding')),

    # Billing — user-facing
    path('billing/', views_billing.billing_dashboard, name='billing_dashboard'),
    path('billing/upgrade/', views_billing.billing_upgrade, name='billing_upgrade'),
    path('billing/pago/', views_billing.billing_payment, name='billing_payment'),
    path('billing/comprobante/<int:pago_id>/', views_billing.billing_invoice, name='billing_invoice'),

    # Billing — super-admin
    path('billing/admin/', views_admin.admin_billing_dashboard, name='admin_billing_dashboard'),
    path('billing/admin/action/', views_admin.admin_billing_action, name='admin_billing_action'),
]
