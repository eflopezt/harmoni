from pathlib import Path

import yaml
from django.conf import settings


def test_servicios_productivos_comparten_la_misma_imagen():
    compose_path = Path(settings.BASE_DIR) / 'deploy' / 'docker-compose.prod.yml'
    compose = yaml.safe_load(compose_path.read_text(encoding='utf-8'))
    services = compose['services']

    images = {services[name].get('image') for name in ('web', 'celery', 'celery-beat')}
    assert images == {'harmoni-app:latest'}
    assert 'build' in services['web']
    assert 'build' not in services['celery']
    assert 'build' not in services['celery-beat']


def test_scripts_de_deploy_no_abren_permisos_globales():
    deploy_dir = Path(settings.BASE_DIR) / 'deploy'
    for filename in ('deploy.sh', 'deploy_tarball.sh'):
        content = (deploy_dir / filename).read_text(encoding='utf-8')
        assert 'chmod -R 777' not in content
