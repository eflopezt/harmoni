"""
index_knowledge_embeddings.py — Calcula y almacena embeddings para la base de conocimiento IA.

Uso:
    python manage.py index_knowledge_embeddings             # Solo artículos sin embedding
    python manage.py index_knowledge_embeddings --force     # Recalcula todos
    python manage.py index_knowledge_embeddings --dry-run   # Muestra qué haría
    python manage.py index_knowledge_embeddings --stats     # Solo muestra estadísticas

Requisitos:
    - ConfiguracionSistema.ia_provider = OPENAI y ia_api_key configurada.
    - O si el proveedor es DeepSeek/Gemini y hay una key de OpenAI para embeddings,
      configurar ia_api_key con la key de OpenAI.

Costo estimado (text-embedding-3-small):
    - 19 artículos × ~200 tokens promedio = ~3,800 tokens ≈ $0.0001 USD
    - Prácticamente gratis. Rara vez necesita re-calcularse.
"""
import json
import time

from django.core.management.base import BaseCommand, CommandError

from core.models import KnowledgeArticle


class Command(BaseCommand):
    help = 'Calcula embeddings vectoriales para los artículos de la base de conocimiento IA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force', action='store_true',
            help='Recalcula embeddings incluso para artículos que ya los tienen.',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Muestra qué artículos se procesarían sin llamar a la API.',
        )
        parser.add_argument(
            '--stats', action='store_true',
            help='Muestra estadísticas del estado de embeddings y sale.',
        )
        parser.add_argument(
            '--api-key', type=str, default='',
            help='API key de OpenAI (alternativa a la guardada en ConfiguracionSistema).',
        )

    def handle(self, *args, **options):
        from core.knowledge_service import embed_text, get_embedding_stats, EMBEDDING_MODEL

        # ── Estadísticas ──
        if options['stats']:
            stats = get_embedding_stats()
            self.stdout.write(self.style.HTTP_INFO('-' * 50))
            self.stdout.write(self.style.HTTP_INFO('  Base de Conocimiento IA — Estado Embeddings'))
            self.stdout.write(self.style.HTTP_INFO('-' * 50))
            self.stdout.write(f'  Modelo:              {stats["embedding_model"]}')
            self.stdout.write(f'  Artículos activos:   {stats["total"]}')
            self.stdout.write(f'  Con embedding:       {stats["with_embedding"]}')
            self.stdout.write(f'  Sin embedding:       {stats["without_embedding"]}')
            ready = stats['phase_b_ready']
            status = self.style.SUCCESS('ACTIVA') if ready else self.style.WARNING('INACTIVA (sin API key o sin embeddings)')
            self.stdout.write(f'  Búsqueda semántica:  {status}')
            self.stdout.write(self.style.HTTP_INFO('-' * 50))
            return

        # ── Obtener API key ──
        api_key = options.get('api_key', '').strip()
        if not api_key:
            try:
                from asistencia.models import ConfiguracionSistema
                config = ConfiguracionSistema.get_config()
                if config.ia_provider == 'OPENAI' and config.ia_api_key:
                    api_key = config.ia_api_key
                elif config.ia_api_key and 'sk-' in config.ia_api_key:
                    api_key = config.ia_api_key
            except Exception as exc:
                self.stderr.write(f'Error leyendo ConfiguracionSistema: {exc}')

        if not api_key:
            raise CommandError(
                'No se encontró API key de OpenAI. \n'
                'Opciones:\n'
                '  1. Configurar en Admin → Configuración del Sistema → IA Provider = OPENAI + API Key\n'
                '  2. Pasar --api-key=sk-...'
            )

        # ── Seleccionar artículos a procesar ──
        force   = options['force']
        dry_run = options['dry_run']

        qs = KnowledgeArticle.objects.filter(activo=True)
        if not force:
            qs = qs.filter(embedding_json__isnull=True) | qs.filter(embedding_json='')
            # Django ORM: combinar con OR
            from django.db.models import Q
            qs = KnowledgeArticle.objects.filter(activo=True).filter(
                Q(embedding_json__isnull=True) | Q(embedding_json='')
            )

        articles = list(qs.order_by('prioridad', 'id'))

        if not articles:
            self.stdout.write(self.style.SUCCESS('✓ Todos los artículos ya tienen embeddings.'))
            self.stdout.write('  Usa --force para recalcular o --stats para ver estado.')
            return

        self.stdout.write(
            f'Calculando embeddings para {len(articles)} artículo(s) '
            f'con {EMBEDDING_MODEL}...'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING('  [DRY-RUN] No se llamará a la API ni se guardará nada.'))

        ok = 0
        errors = 0
        total_tokens_approx = 0

        for i, art in enumerate(articles, 1):
            # Texto a embeddear: título + contenido (más rico que solo contenido)
            text_to_embed = f'{art.titulo}\n\n{art.contenido}'
            # Estimación muy aproximada de tokens
            tokens_est = len(text_to_embed) // 4
            total_tokens_approx += tokens_est

            label = f'[{i}/{len(articles)}] {art.titulo[:60]}'

            if dry_run:
                self.stdout.write(f'  {label} (~{tokens_est} tokens)')
                ok += 1
                continue

            try:
                vec = embed_text(text_to_embed, api_key=api_key)
                if vec is None:
                    self.stderr.write(self.style.ERROR(f'  ✗ {label} — embed_text retornó None'))
                    errors += 1
                    continue

                art.embedding_json = json.dumps(vec)
                art.save(update_fields=['embedding_json'])
                self.stdout.write(self.style.SUCCESS(f'  OK {label}'))
                ok += 1

                # Pequeña pausa para no saturar la API
                if i < len(articles):
                    time.sleep(0.1)

            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'  ✗ {label} — {exc}'))
                errors += 1

        # ── Resumen ──
        self.stdout.write('')
        cost_usd = total_tokens_approx / 1_000_000 * 0.020   # $0.02/M tokens
        self.stdout.write(f'Tokens estimados: ~{total_tokens_approx:,}  (costo ~${cost_usd:.5f} USD)')

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[DRY-RUN] Habría procesado {ok} artículos.'))
        elif errors == 0:
            self.stdout.write(self.style.SUCCESS(
                f'✓ {ok} embeddings calculados. Búsqueda semántica Phase B activa.'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f'{ok} OK, {errors} errores. Revisa los errores arriba.'
            ))
