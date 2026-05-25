"""
Provisiona un nuevo cliente Enterprise — ADR-001.

Genera:
- docker-compose.yml a partir del template (variables sustituidas)
- .env.<slug> con secrets generados
- Caddyfile entry para subdominio
- SQL para crear DB + usuario Postgres dedicado
- Estructura de directorios /opt/harmoni-clients/<slug>/

Uso:
    python manage.py provision_enterprise_client edo \\
        --name "Grupo Sabores" \\
        --port 8001 \\
        --custom-domain harmoni.gruposabores.pe \\
        --output ./provisioning/edo/

    # En el server:
    cd /opt/harmoni-clients/edo/
    docker-compose up -d
"""
import secrets
import string
from pathlib import Path

from django.core.management.base import BaseCommand


TEMPLATE_DIR = Path(__file__).resolve().parents[3] / 'deploy'


def _genpass(n=24):
    alphabet = string.ascii_letters + string.digits + '_-'
    return ''.join(secrets.choice(alphabet) for _ in range(n))


def _gensecret(n=50):
    return ''.join(
        secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*()_-+=')
        for _ in range(n)
    )


def _substituir(content: str, replacements: dict) -> str:
    for k, v in replacements.items():
        content = content.replace(k, str(v))
    return content


class Command(BaseCommand):
    help = 'Provisiona archivos de deploy para un cliente Enterprise (ADR-001).'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('slug', help='Slug del cliente (lowercase, ej: edo, mayimbe)')
        parser.add_argument('--name', required=True, help='Nombre del cliente (ej: "Grupo Sabores")')
        parser.add_argument('--port', type=int, required=True, help='Puerto único en host (8001+)')
        parser.add_argument('--custom-domain', default='', help='Dominio propio opcional')
        parser.add_argument('--smtp-host', default='smtp.gmail.com')
        parser.add_argument('--smtp-user', default='')
        parser.add_argument('--smtp-pass', default='')
        parser.add_argument('--sentry-dsn', default='')
        parser.add_argument('--output', default='', help='Dir de salida (default: ./provisioning/<slug>/)')
        parser.add_argument('--apply', action='store_true', help='Ejecutar comandos reales (default: dry-run)')

    def handle(self, *args, **opts):
        slug = opts['slug'].lower().strip()
        if not slug.isascii() or not slug.replace('-', '').replace('_', '').isalnum():
            self.stdout.write(self.style.ERROR(f'[ERROR] Slug invalido: {slug}. Solo ascii + guiones + underscores.'))
            return

        port = opts['port']
        if port < 8001 or port > 9000:
            self.stdout.write(self.style.WARNING(f'[!] Puerto fuera de rango sugerido 8001-9000: {port}'))

        # Output dir
        out_dir = Path(opts['output']) if opts['output'] else Path('provisioning') / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        # Generar secrets
        db_password = _genpass(32)
        secret_key = _gensecret(50)
        # Redis DB num: hash del slug a [1, 15]
        redis_db = (sum(ord(c) for c in slug) % 15) + 1

        replacements = {
            '__CLIENT_SLUG__':   slug,
            '__CLIENT_NAME__':   opts['name'],
            '__CLIENT_PORT__':   str(port),
            '__APP_PATH__':      f'/opt/harmoni-clients/{slug}/app',
            '__DB_NAME__':       f'harmoni_{slug}_db',
            '__DB_USER__':       f'harmoni_{slug}',
            '__DB_PASSWORD__':   db_password,
            '__SECRET_KEY__':    secret_key,
            '__REDIS_DB__':      str(redis_db),
            '__CUSTOM_DOMAIN__': opts['custom_domain'] or '',
            '__SMTP_HOST__':     opts['smtp_host'],
            '__SMTP_USER__':     opts['smtp_user'],
            '__SMTP_PASS__':     opts['smtp_pass'],
            '__SENTRY_DSN__':    opts['sentry_dsn'],
        }

        # ── docker-compose.yml ──
        compose_template = (TEMPLATE_DIR / 'docker-compose.enterprise.template.yml').read_text(encoding='utf-8')
        compose = _substituir(compose_template, replacements)
        (out_dir / 'docker-compose.yml').write_text(compose, encoding='utf-8')

        # ── .env.<slug> ──
        env_template = (TEMPLATE_DIR / '.env.enterprise.template').read_text(encoding='utf-8')
        env = _substituir(env_template, replacements)
        (out_dir / f'.env.{slug}').write_text(env, encoding='utf-8')

        # ── Caddyfile entry ──
        caddy_template = (TEMPLATE_DIR / 'Caddyfile.enterprise.template').read_text(encoding='utf-8')
        caddy = _substituir(caddy_template, replacements)
        (out_dir / 'Caddyfile.entry').write_text(caddy, encoding='utf-8')

        # ── SQL setup ──
        sql = f"""-- Setup DB para cliente Enterprise: {opts['name']}
-- Ejecutar como postgres en el VPS:
--   sudo -u postgres psql -f /tmp/setup_{slug}.sql

CREATE USER {replacements['__DB_USER__']} WITH ENCRYPTED PASSWORD '{db_password}';
CREATE DATABASE {replacements['__DB_NAME__']} OWNER {replacements['__DB_USER__']};
GRANT ALL PRIVILEGES ON DATABASE {replacements['__DB_NAME__']} TO {replacements['__DB_USER__']};

-- pgvector si usamos embeddings IA
\\c {replacements['__DB_NAME__']}
CREATE EXTENSION IF NOT EXISTS vector;
GRANT ALL ON SCHEMA public TO {replacements['__DB_USER__']};
"""
        (out_dir / f'setup_{slug}.sql').write_text(sql, encoding='utf-8')

        # ── README de deploy ──
        readme = f"""# Deploy {opts['name']} — Enterprise Tier

## Resumen
- **Slug:** `{slug}`
- **Puerto:** `{port}`
- **Subdominio:** `{slug}.harmoni.pe`
{f"- **Dominio propio:** `{opts['custom_domain']}`" if opts['custom_domain'] else ""}
- **DB:** `{replacements['__DB_NAME__']}`
- **Usuario DB:** `{replacements['__DB_USER__']}`
- **Redis DB:** `{redis_db}`

## Pasos de deploy (en el VPS)

### 1. Crear estructura de directorios
```bash
sudo mkdir -p /opt/harmoni-clients/{slug}/{{app,staticfiles,media,logs,snapshots}}
sudo chown -R root:root /opt/harmoni-clients/{slug}
```

### 2. Clonar código (read-only para el container)
```bash
sudo git clone https://github.com/eflopezt/harmoni.git /opt/harmoni-clients/{slug}/app
cd /opt/harmoni-clients/{slug}/app
sudo git checkout main
```

### 3. Copiar archivos generados
```bash
sudo cp docker-compose.yml /opt/harmoni-clients/{slug}/
sudo cp .env.{slug} /opt/harmoni-clients/{slug}/
```

### 4. Crear DB
```bash
sudo cp setup_{slug}.sql /tmp/
sudo -u postgres psql -f /tmp/setup_{slug}.sql
sudo rm /tmp/setup_{slug}.sql  # contiene password
```

### 5. Subdominio + DNS
- DNS A record: `{slug}.harmoni.pe` → IP del VPS
{f"- DNS CNAME del cliente: `{opts['custom_domain']}` → `{slug}.harmoni.pe`" if opts['custom_domain'] else ""}

### 6. Caddy: agregar entry
```bash
sudo cat Caddyfile.entry >> /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

### 7. Build + start
```bash
cd /opt/harmoni-clients/{slug}/
sudo docker-compose build
sudo docker-compose up -d

# Aplicar migraciones
sudo docker-compose exec web python manage.py migrate
sudo docker-compose exec web python manage.py collectstatic --noinput
sudo docker-compose exec web python manage.py createsuperuser
```

### 8. Seed inicial
```bash
sudo docker-compose exec web python manage.py seed_conceptos_base
```

### 9. Verificar
- Browser: `https://{slug}.harmoni.pe`
- Health: `https://{slug}.harmoni.pe/health/`
- Login con superuser creado

## Backup automatico

Agregar al cron del VPS:
```cron
0 3 * * * pg_dump -U postgres {replacements['__DB_NAME__']} | gzip > /opt/backups/{slug}/db_$(date +%Y%m%d).sql.gz
```

## Rollback
```bash
cd /opt/harmoni-clients/{slug}/
sudo docker-compose down
sudo -u postgres dropdb {replacements['__DB_NAME__']}
sudo -u postgres dropuser {replacements['__DB_USER__']}
sudo rm -rf /opt/harmoni-clients/{slug}/
```

## Notas de seguridad
- El password DB esta en `.env.{slug}` — **NO commitear al repo**
- Rotar SECRET_KEY si hay sospecha de leak
- Backups DB son sensibles — encriptar con `gpg` antes de subir a S3/almacenamiento externo
"""
        (out_dir / 'README.md').write_text(readme, encoding='utf-8')

        # ── Output ──
        self.stdout.write(self.style.SUCCESS(f'[OK] Provisioning generado en: {out_dir}/'))
        self.stdout.write('')
        self.stdout.write('Archivos generados:')
        for f in sorted(out_dir.iterdir()):
            self.stdout.write(f'  - {f.name}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Importante:'))
        self.stdout.write(f'  - DB password: (en .env.{slug}, NO commitear)')
        self.stdout.write(f'  - Secret key: (en .env.{slug})')
        self.stdout.write('  - Lee README.md para pasos de deploy en el VPS')

        if not opts['apply']:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(
                '[DRY] Solo se generaron archivos locales. Para hacer deploy real, '
                'transferir a VPS y seguir README.md'
            ))
