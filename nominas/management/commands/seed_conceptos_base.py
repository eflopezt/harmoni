"""
Seed inicial de conceptos remunerativos para una empresa nueva.

Crea los 28 conceptos básicos con códigos PLAME SUNAT, flags de afectación
correctos y descripciones completas. Pensado para que al contratar un cliente
nuevo, el sistema arranque con todo configurado.

Uso:
    python manage.py seed_conceptos_base

Opciones:
    --reset  Borra los conceptos existentes antes de crear (CUIDADO)
"""
from django.core.management.base import BaseCommand

from nominas.models import ConceptoRemunerativo
from nominas.views_conceptos import TEMPLATES_CONCEPTOS


class Command(BaseCommand):
    help = 'Inicializa los 28 conceptos remunerativos base con códigos PLAME SUNAT'
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='ATENCIÓN: borra los conceptos no-sistema antes de crear',
        )
        parser.add_argument(
            '--update-plame', action='store_true',
            help='Solo actualiza códigos PLAME en conceptos existentes (no crea nuevos)',
        )

    def handle(self, *args, **opts):
        reset = opts.get('reset')
        update_only = opts.get('update_plame')

        if reset:
            n = ConceptoRemunerativo.objects.filter(es_sistema=False).count()
            ConceptoRemunerativo.objects.filter(es_sistema=False).delete()
            self.stdout.write(self.style.WARNING(f'⚠  {n} conceptos no-sistema eliminados'))

        created = 0
        updated = 0
        skipped = 0

        for key, t in TEMPLATES_CONCEPTOS.items():
            existing = ConceptoRemunerativo.objects.filter(codigo=t['codigo']).first()

            if existing:
                if update_only or not existing.codigo_plame:
                    # Actualizar PLAME + descripción si falta
                    changed = False
                    for field in ('codigo_plame', 'casilla_plame', 'codigo_tregistro',
                                  'descripcion', 'categoria'):
                        v = t.get(field)
                        if v and not getattr(existing, field, None):
                            setattr(existing, field, v)
                            changed = True
                    if changed:
                        existing.save()
                        updated += 1
                        self.stdout.write(f'  ~ {t["codigo"]:30} ({t["nombre"]}) — campos actualizados')
                    else:
                        skipped += 1
                else:
                    skipped += 1
            else:
                if update_only:
                    continue
                ConceptoRemunerativo.objects.create(**t)
                created += 1
                plame = f' [PLAME {t.get("codigo_plame")}]' if t.get('codigo_plame') else ''
                self.stdout.write(self.style.SUCCESS(f'  ✓ {t["codigo"]:30} ({t["nombre"]}){plame}'))

        # Resumen
        self.stdout.write('')
        self.stdout.write('═' * 70)
        self.stdout.write(f'  Conceptos creados:       {created}')
        self.stdout.write(f'  Actualizados (PLAME):    {updated}')
        self.stdout.write(f'  Ya existían (skip):      {skipped}')
        self.stdout.write(f'  TOTAL en sistema:        {ConceptoRemunerativo.objects.count()}')
        self.stdout.write(f'  Con código PLAME SUNAT:  {ConceptoRemunerativo.objects.exclude(codigo_plame="").count()}')
        self.stdout.write('═' * 70)
        self.stdout.write(self.style.SUCCESS('✓ Onboarding de conceptos completado'))
