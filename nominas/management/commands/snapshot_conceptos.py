"""
Snapshot y restore de Conceptos Remunerativos.

Crea un backup completo de la configuración de conceptos en JSON,
y permite restaurar desde ese snapshot.

Usado para:
- Backup antes de cambios masivos riesgosos (bulk autofix, CSV import grande)
- Migración entre ambientes (export prod, import demo)
- Recuperación rápida ante cambio accidental

Uso:
    # Snapshot
    python manage.py snapshot_conceptos                       # genera snapshots/conceptos_YYYYMMDD_HHMMSS.json
    python manage.py snapshot_conceptos --out backup.json     # destino custom
    python manage.py snapshot_conceptos --label "antes-bulk"  # nombrado

    # Restore (modo seguro: --dry-run primero)
    python manage.py snapshot_conceptos --restore backup.json --dry-run
    python manage.py snapshot_conceptos --restore backup.json
    python manage.py snapshot_conceptos --restore backup.json --strategy merge   # default (UPSERT)
    python manage.py snapshot_conceptos --restore backup.json --strategy reset   # borra y recrea
"""
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from nominas.models import ConceptoRemunerativo
from nominas.signals_audit import clear_audit_context, set_audit_context


SNAPSHOT_FIELDS = [
    'codigo', 'nombre', 'descripcion', 'categoria',
    'tipo', 'subtipo', 'formula', 'porcentaje', 'monto_fijo',
    'afecto_essalud', 'afecto_afp', 'afecto_onp',
    'afecto_renta', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
    'codigo_plame', 'casilla_plame', 'codigo_tregistro',
    'es_sistema', 'activo', 'orden',
]


def _serialize(c):
    """Concepto → dict JSON-safe."""
    d = {}
    for f in SNAPSHOT_FIELDS:
        v = getattr(c, f)
        if isinstance(v, Decimal):
            d[f] = str(v)
        else:
            d[f] = v
    return d


class Command(BaseCommand):
    help = 'Snapshot/restore de conceptos remunerativos (JSON)'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('--out',     default='', help='Ruta de salida (snapshot)')
        parser.add_argument('--label',   default='', help='Etiqueta para el nombre del archivo')
        parser.add_argument('--restore', default='', help='Ruta del JSON a restaurar')
        parser.add_argument('--dry-run', action='store_true', help='Simular sin escribir')
        parser.add_argument(
            '--strategy', default='merge', choices=['merge', 'reset'],
            help='merge=UPSERT por código (default), reset=borra todo y recrea',
        )

    def handle(self, *args, **opts):
        if opts['restore']:
            return self._do_restore(opts)
        return self._do_snapshot(opts)

    def _do_snapshot(self, opts):
        out_path = opts.get('out') or ''
        if not out_path:
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            label = opts.get('label', '')
            label_suffix = f'_{label}' if label else ''
            out_dir = Path('snapshots')
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / f'conceptos_{stamp}{label_suffix}.json'
        else:
            out_path = Path(out_path)

        qs = ConceptoRemunerativo.objects.all().order_by('codigo')
        data = {
            'meta': {
                'version': '1.0',
                'generated_at': datetime.now().isoformat(),
                'count': qs.count(),
                'label': opts.get('label', ''),
            },
            'conceptos': [_serialize(c) for c in qs],
        }

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[DRY] DRY RUN — habría escrito {len(data["conceptos"])} conceptos a {out_path}'
            ))
            return

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f'[OK] Snapshot guardado: {out_path} ({len(data["conceptos"])} conceptos)'
        ))

    def _do_restore(self, opts):
        in_path = Path(opts['restore'])
        if not in_path.exists():
            raise CommandError(f'Archivo no existe: {in_path}')

        with open(in_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        conceptos = data.get('conceptos', [])
        meta = data.get('meta', {})
        strategy = opts['strategy']

        self.stdout.write(
            f'[SNAP] Snapshot generado: {meta.get("generated_at", "?")} '
            f'({meta.get("count", len(conceptos))} conceptos, label: {meta.get("label", "—")})'
        )
        self.stdout.write(f'   Estrategia: {strategy.upper()}')
        if opts['dry_run']:
            self.stdout.write(self.style.WARNING('   [DRY] DRY RUN — no se aplican cambios'))

        # Audit context para que la restauración deje trail
        User = get_user_model()
        sysuser = User.objects.filter(is_superuser=True).order_by('id').first()
        set_audit_context(
            usuario=sysuser,
            ip=None,
            user_agent=f'manage.py snapshot_conceptos --restore {in_path.name}',
            contexto=f'CLI:restore:{strategy}',
            accion_override='UPDATE',  # se sobrescribe por CREATE si es nuevo
        )

        created = updated = skipped = 0
        try:
            with transaction.atomic():
                if strategy == 'reset':
                    n_borrar = ConceptoRemunerativo.objects.filter(es_sistema=False).count()
                    self.stdout.write(f'   [!] RESET — se eliminarán {n_borrar} conceptos custom (es_sistema=False)')
                    if not opts['dry_run']:
                        # Solo borramos los NO-sistema, los es_sistema=True se mantienen
                        ConceptoRemunerativo.objects.filter(es_sistema=False).delete()

                for snap in conceptos:
                    codigo = snap.get('codigo')
                    if not codigo:
                        skipped += 1
                        continue

                    existing = ConceptoRemunerativo.objects.filter(codigo=codigo).first()
                    if existing and existing.es_sistema and strategy == 'merge':
                        # No tocamos conceptos del sistema en merge
                        # (a menos que el snapshot los modifique también — confiamos en el snap)
                        pass

                    fields = {f: snap[f] for f in SNAPSHOT_FIELDS if f in snap}
                    # Decimals
                    for f in ('porcentaje', 'monto_fijo'):
                        if f in fields and fields[f] is not None:
                            try:
                                fields[f] = Decimal(str(fields[f]))
                            except Exception:
                                fields[f] = Decimal('0')

                    if opts['dry_run']:
                        if existing:
                            updated += 1
                        else:
                            created += 1
                        continue

                    if existing:
                        for k, v in fields.items():
                            if k == 'codigo':
                                continue
                            setattr(existing, k, v)
                        existing.save()
                        updated += 1
                    else:
                        ConceptoRemunerativo.objects.create(**fields)
                        created += 1

                if opts['dry_run']:
                    raise transaction.TransactionManagementError('DRY RUN — rollback intencional')
        except transaction.TransactionManagementError:
            pass  # dry-run rollback expected

        clear_audit_context()

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'   Creados:      {created}'))
        self.stdout.write(self.style.SUCCESS(f'   Actualizados: {updated}'))
        if skipped:
            self.stdout.write(self.style.WARNING(f'   Saltados:     {skipped}'))
