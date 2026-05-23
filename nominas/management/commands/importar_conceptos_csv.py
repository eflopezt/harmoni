"""
Importa conceptos remunerativos desde CSV.

Útil para migrar configuración de un cliente a otro, o cargar masivamente.

Formato CSV esperado (cabecera obligatoria):
codigo,nombre,descripcion,categoria,tipo,subtipo,formula,monto_fijo,porcentaje,
afecto_essalud,afecto_afp,afecto_onp,afecto_renta,afecto_cts,afecto_gratif,afecto_vacaciones,
codigo_plame,casilla_plame,codigo_tregistro,activo,orden

Los campos boolean aceptan: SI/NO, true/false, 1/0

Uso:
    python manage.py importar_conceptos_csv archivo.csv
    python manage.py importar_conceptos_csv archivo.csv --update   # actualiza existentes
    python manage.py importar_conceptos_csv archivo.csv --dry-run  # simulación
"""
import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from nominas.models import ConceptoRemunerativo
from nominas.signals_audit import clear_audit_context, set_audit_context


def _bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in ('si', 'sí', 'yes', 'true', '1', 'y')


def _decimal(value, default='0'):
    try:
        return Decimal(str(value).replace(',', '.').strip() or default)
    except (InvalidOperation, ValueError):
        return Decimal(default)


class Command(BaseCommand):
    help = 'Importa conceptos remunerativos desde CSV (codigo, nombre, flags, PLAME, etc.)'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument('csv_path', help='Ruta al archivo CSV')
        parser.add_argument('--update', action='store_true', help='Actualizar conceptos existentes')
        parser.add_argument('--dry-run', action='store_true', help='Simular sin guardar')
        parser.add_argument(
            '--usuario', default='',
            help='Username para audit log (si no, usa el primer superuser).',
        )

    def handle(self, *args, **opts):
        csv_path = Path(opts['csv_path'])
        if not csv_path.exists():
            raise CommandError(f'Archivo no existe: {csv_path}')

        update_mode = opts.get('update', False)
        dry_run = opts.get('dry_run', False)

        if dry_run:
            self.stdout.write(self.style.WARNING('🟡 DRY RUN — no se guardan cambios'))

        # Audit context — para que cambios queden registrados con CSV_IMPORT
        User = get_user_model()
        usuario = None
        usuario_username = opts.get('usuario') or ''
        if usuario_username:
            usuario = User.objects.filter(username=usuario_username).first()
        if not usuario:
            usuario = User.objects.filter(is_superuser=True).order_by('id').first()
        set_audit_context(
            usuario=usuario,
            ip=None,
            user_agent='manage.py importar_conceptos_csv',
            contexto=f'CLI:{csv_path.name}',
            accion_override='CSV_IMPORT',
        )

        created = 0
        updated = 0
        errors  = []
        skipped = 0

        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_num, row in enumerate(reader, start=2):
                codigo = (row.get('codigo') or '').strip().lower().replace(' ', '_')
                nombre = (row.get('nombre') or '').strip()

                if not codigo or not nombre:
                    errors.append(f'Fila {row_num}: código o nombre vacíos — saltada')
                    continue

                existing = ConceptoRemunerativo.objects.filter(codigo=codigo).first()

                if existing and not update_mode:
                    skipped += 1
                    self.stdout.write(f'  ~ Fila {row_num}: "{codigo}" ya existe — saltada (usa --update para actualizar)')
                    continue

                data = {
                    'codigo':           codigo,
                    'nombre':           nombre,
                    'descripcion':      row.get('descripcion', '').strip(),
                    'categoria':        row.get('categoria', 'OTRO').strip().upper() or 'OTRO',
                    'tipo':             row.get('tipo', 'INGRESO').strip().upper() or 'INGRESO',
                    'subtipo':          row.get('subtipo', 'REMUNERATIVO').strip().upper() or 'REMUNERATIVO',
                    'formula':          row.get('formula', 'FIJO').strip().upper() or 'FIJO',
                    'monto_fijo':       _decimal(row.get('monto_fijo'), '0'),
                    'porcentaje':       _decimal(row.get('porcentaje'), '0'),
                    'afecto_essalud':   _bool(row.get('afecto_essalud')),
                    'afecto_afp':       _bool(row.get('afecto_afp')),
                    'afecto_onp':       _bool(row.get('afecto_onp')),
                    'afecto_renta':     _bool(row.get('afecto_renta')),
                    'afecto_cts':       _bool(row.get('afecto_cts')),
                    'afecto_gratif':    _bool(row.get('afecto_gratif')),
                    'afecto_vacaciones': _bool(row.get('afecto_vacaciones')),
                    'codigo_plame':     row.get('codigo_plame', '').strip(),
                    'casilla_plame':    row.get('casilla_plame', '').strip(),
                    'codigo_tregistro': row.get('codigo_tregistro', '').strip(),
                    'activo':           _bool(row.get('activo', 'SI')),
                    'orden':            int(row.get('orden', '0') or 0),
                }

                if dry_run:
                    if existing:
                        updated += 1
                        self.stdout.write(f'  [DRY] Actualizaría {codigo}')
                    else:
                        created += 1
                        self.stdout.write(f'  [DRY] Crearía {codigo}')
                    continue

                try:
                    if existing:
                        for k, v in data.items():
                            if k == 'codigo':
                                continue
                            setattr(existing, k, v)
                        existing.save()
                        updated += 1
                        self.stdout.write(f'  ↻ {codigo} actualizado')
                    else:
                        ConceptoRemunerativo.objects.create(**data)
                        created += 1
                        self.stdout.write(self.style.SUCCESS(f'  ✓ {codigo} creado'))
                except Exception as e:
                    errors.append(f'Fila {row_num} ({codigo}): {e}')

        # Limpiar audit context
        clear_audit_context()

        # Resumen
        self.stdout.write('')
        self.stdout.write('═' * 70)
        self.stdout.write(f'  Procesados:   {created + updated + skipped + len(errors)}')
        self.stdout.write(self.style.SUCCESS(f'  Creados:      {created}'))
        self.stdout.write(self.style.SUCCESS(f'  Actualizados: {updated}'))
        self.stdout.write(self.style.WARNING(f'  Saltados:     {skipped}'))
        if errors:
            self.stdout.write(self.style.ERROR(f'  Errores:      {len(errors)}'))
            for e in errors[:10]:
                self.stdout.write(self.style.ERROR(f'    - {e}'))
        self.stdout.write('═' * 70)
