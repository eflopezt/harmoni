"""
Helpers compartidos para los tests de aislamiento multi-empresa de la
API DRF (/api/v1/). Usados por los test_api_empresa.py de cada app.

Escenario estándar:
  - Empresa A con un trabajador y data sensible ("la víctima").
  - Usuario tenant logueado con Empresa B activa en sesión.
  - El usuario de B NO debe ver ni tocar nada de A.
"""
import itertools

from django.contrib.auth import get_user_model

from empresas.models import Empresa
from personal.models import Personal

User = get_user_model()

_seq = itertools.count(1)


def crear_empresa(nombre='Empresa', principal=False):
    n = next(_seq)
    return Empresa.objects.create(
        ruc=f'2055{n:07d}',
        razon_social=f'{nombre} {n} S.A.C.',
        activa=True,
        es_principal=principal,
    )


def crear_personal(empresa, nombre='TRABAJADOR PRUEBA'):
    n = next(_seq)
    return Personal.objects.create(
        nro_doc=str(40000000 + n),
        apellidos_nombres=f'{nombre} {n}',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        empresa=empresa,
    )


def crear_usuario(superuser=False, staff=True):
    """Usuario tenant. staff=True replica al admin trial que crea
    /onboarding/starter/ (is_staff=True, NO superuser)."""
    n = next(_seq)
    if superuser:
        return User.objects.create_superuser(
            f'su_{n}', f'su_{n}@test.pe', 'pw12345')
    user = User.objects.create_user(f'user_{n}', f'user_{n}@test.pe', 'pw12345')
    if staff:
        user.is_staff = True
        user.save(update_fields=['is_staff'])
    return user


def login_en_empresa(client, user, empresa=None):
    """Login + deja `empresa` como empresa activa en sesión (equivalente a
    elegirla en el selector). Sin empresa: sesión limpia (el middleware
    cae a la empresa principal si existe; en tests no suele existir)."""
    if empresa is not None and not user.is_superuser and empresa.creado_por_id is None:
        empresa.creado_por = user
        empresa.save(update_fields=['creado_por', 'actualizado_en'])
    client.force_login(user)
    if empresa is not None:
        session = client.session
        session['empresa_actual_id'] = empresa.pk
        session.save()


def ids_de(resp):
    """IDs de una respuesta de list DRF (paginada o no)."""
    data = resp.json()
    items = data['results'] if isinstance(data, dict) and 'results' in data else data
    return {item['id'] for item in items}
