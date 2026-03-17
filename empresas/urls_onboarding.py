from django.urls import path
from . import views_onboarding as views

urlpatterns = [
    path('step-1/', views.step1_company, name='onboarding_step1'),
    path('step-2/', views.step2_email, name='onboarding_step2'),
    path('step-3/', views.step3_admin, name='onboarding_step3'),
    path('step-4/', views.step4_data, name='onboarding_step4'),
    path('step-5/', views.step5_summary, name='onboarding_step5'),
    path('complete/<int:empresa_id>/', views.onboarding_complete, name='onboarding_complete'),
    path('test-smtp/', views.test_smtp, name='onboarding_test_smtp'),
    path('suggest-subdomain/', views.suggest_subdomain, name='onboarding_suggest_subdomain'),
]
