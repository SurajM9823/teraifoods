"""Repair imported categories without downloading images or replacing products."""
import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, Q
from django.core.cache import cache
from catalog.models import Category, Product, CatalogRevision
from catalog.content import invalidate_categories, CACHE_ERRORS
from catalog.rmfoods_taxonomy import assign, mapped_metadata, resolve, DISPLAY_ORDER, canonical


class Command(BaseCommand):
    help = 'Plan RM Foods hierarchy repair; --apply updates only imported category/subcategory metadata.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', default='catalog/data/rmfoods/seed.json')
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report')

    def handle(self, *args, **options):
        data = json.loads(Path(options['seed']).read_text())
        if data.get('schema_version') != 1 or data.get('currency') != 'GBP':
            raise CommandError('Expected version 1 GBP seed')
        rows = {row['key']: row for row in data['products']}
        if len(rows) != len(data['products']) or any(not key.startswith('rmfoods:') for key in rows):
            raise CommandError('Invalid or duplicate RM Foods keys')
        products = list(Product.objects.filter(legacy_key__in=rows).order_by('pk'))
        assignments = {key: assign(row) for key, row in rows.items()}
        unresolved = [key for key, value in assignments.items() if value.method == 'unresolved']
        if unresolved:
            raise CommandError('Unresolved category mappings: ' + ', '.join(unresolved))
        report = {'applied': False, 'matched_products': len(products),
                  'missing_products': len(rows) - len(products),
                  'categories': dict(Counter(assignments[p.legacy_key].category for p in products)),
                  'inferred_products': sum(assignments[p.legacy_key].review for p in products),
                  'assignments': [dict(key=p.legacy_key, name=p.name,
                                       category=assignments[p.legacy_key].category,
                                       subcategory=assignments[p.legacy_key].subcategory,
                                       method=assignments[p.legacy_key].method,
                                       review_required=assignments[p.legacy_key].review) for p in products]}
        if options['apply']:
            if not products:
                raise CommandError('No imported products match this seed')
            with transaction.atomic():
                # Lock before writing so concurrent admin updates are not overwritten.
                products = list(Product.objects.select_for_update().filter(legacy_key__in=rows).order_by('pk'))
                targets = {}
                for product in products:
                    assignment = assignments[product.legacy_key]
                    pair = (assignment.category, assignment.subcategory)
                    if pair not in targets:
                        targets[pair] = resolve(assignment)
                    product.category, product.subcategory = targets[pair]
                    product.metadata = mapped_metadata(rows[product.legacy_key], assignment, product.metadata)
                Product.objects.bulk_update(products, ['category', 'subcategory', 'metadata'], batch_size=200)
                active_ids = {category.pk for category, child in targets.values()}
                # Preserve manual categories and any imported category still in use.
                obsolete = Category.objects.filter(
                    Q(legacy_key__startswith='rm:') | Q(legacy_key='preview:uncategorized'),
                    products__isnull=True, subcategories__isnull=True).exclude(pk__in=active_ids)
                report['deactivated_flat_categories'] = list(obsolete.values_list('name', flat=True))
                obsolete.update(is_active=False)
                for category in {category.pk: category for category, child in targets.values()}.values():
                    if category.legacy_key.startswith('rm:'):
                        position = next(i for i, name in enumerate(DISPLAY_ORDER) if canonical(name) == canonical(category.name))
                        Category.objects.filter(pk=category.pk).update(position=position)
                revision, _ = CatalogRevision.objects.get_or_create(pk=1)
                CatalogRevision.objects.filter(pk=revision.pk).update(version=F('version') + 1)
                def refresh():
                    invalidate_categories()
                    try:
                        cache.delete('catalog:revision:version')
                    except CACHE_ERRORS:
                        pass
                transaction.on_commit(refresh)
            report['applied'] = True
        if options['report']:
            Path(options['report']).write_text(json.dumps(report, indent=2) + '\n')
        summary = {key: value for key, value in report.items() if key != 'assignments'}
        self.stdout.write(json.dumps(summary, indent=2))
