import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from reclutamiento.models import Vacante

pytestmark = pytest.mark.django_db


def _empresa(ruc, owner):
    return Empresa.objects.create(
        ruc=ruc, razon_social=ruc, activa=True, creado_por=owner)


def test_panel_web_no_muestra_vacantes_de_otro_ruc(client):
    owner = User.objects.create_superuser(
        'recruiter_a', 'a@scope.pe', 'pw12345')
    other = User.objects.create_superuser(
        'recruiter_b', 'b@scope.pe', 'pw12345')
    emp_a = _empresa('20123456901', owner)
    emp_b = _empresa('20123456902', other)
    propia = Vacante.objects.create(
        empresa=emp_a, titulo='VACANTE PROPIA', creado_por=owner)
    Vacante.objects.create(
        empresa=emp_b, titulo='VACANTE CONFIDENCIAL', creado_por=other)
    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = emp_a.pk
    session.save()

    response = client.get(reverse('vacantes_panel'))

    assert response.status_code == 200
    assert list(response.context['vacantes']) == [propia]
    assert 'VACANTE CONFIDENCIAL' not in response.content.decode()


def test_crear_vacante_asigna_empresa_activa(client):
    owner = User.objects.create_superuser(
        'recruiter_create', 'create@scope.pe', 'pw12345')
    empresa = _empresa('20123456903', owner)
    client.force_login(owner)
    session = client.session
    session['empresa_actual_id'] = empresa.pk
    session.save()

    response = client.post(reverse('vacante_crear'), {
        'titulo': 'Analista de datos',
        'experiencia_minima': 1,
        'educacion_minima': 'UNIVERSITARIO',
        'tipo_contrato': 'INDETERMINADO',
        'moneda': 'PEN',
        'estado': 'BORRADOR',
        'prioridad': 'MEDIA',
    })

    assert response.status_code == 302
    assert Vacante.all_objects.get(titulo='Analista de datos').empresa == empresa
