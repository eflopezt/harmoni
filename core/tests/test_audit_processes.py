import json

import pytest
from django.core.management import call_command

from empresas.models import Empresa

pytestmark = pytest.mark.django_db


def test_command_json_respeta_empresa(capsys):
    empresa = Empresa.objects.create(
        ruc='20123456991', razon_social='Empresa auditada', activa=True)

    call_command('audit_processes', empresa=empresa.pk, as_json=True)

    data = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert data['alcance'] == 'Empresa auditada'
    assert data['empresas'] == 1
    assert len(data['etapas']) == 6


def test_command_empresa_inexistente_falla():
    from django.core.management.base import CommandError
    with pytest.raises(CommandError, match='no encontrada'):
        call_command('audit_processes', empresa=999999)
