"""Import the portable RM Foods seed, preserving existing products."""
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.media import add_image
from catalog.models import Category, Product


class Command(BaseCommand):
    help = 'Validate/import RM Foods seed as drafts with unconfirmed stock; safe to rerun.'

    def add_arguments(self, parser):
        parser.add_argument('--seed', default='catalog/data/rmfoods/seed.json')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int)

    def handle(self, *args, **options):
        path = Path(options['seed']).resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or data.get('currency') != 'GBP':
            raise CommandError('Expected version 1 GBP seed')
        rows = data['products']
        if options['limit']:
            rows = rows[:options['limit']]
        counts = Counter(c['id'] for row in data['products'] for c in row['categories'])
        skipped = created = 0
        keys = set()
        # Preflight everything before writing: no partial import from corrupt assets.
        for row in rows:
            if row['key'] in keys:
                raise CommandError('Duplicate source key: ' + row['key'])
            keys.add(row['key'])
            product = self.product(row)
            product.full_clean(validate_unique=False, validate_constraints=False)
            if product.regular_price <= 0 or (product.sale_price is not None and not 0 < product.sale_price < product.regular_price):
                raise CommandError('Invalid price: ' + row['key'])
            for image in row['images']:
                asset = (path.parent / image['path']).resolve()
                if not asset.is_relative_to(path.parent) or not asset.is_file():
                    raise CommandError('Missing/unsafe image path: ' + image['path'])
                if hashlib.sha256(asset.read_bytes()).hexdigest() != image['digest']:
                    raise CommandError('Image checksum mismatch: ' + image['path'])
        if options['dry_run']:
            self.stdout.write(self.style.SUCCESS(f'Validated {len(rows)} products and their image checksums. No database changes.'))
            return
        for row in rows:
            if Product.objects.filter(legacy_key=row['key']).exists():
                skipped += 1
                continue
            with transaction.atomic():
                candidates = [c for c in row['categories'] if c['name'].casefold() not in
                              {'all products', 'brands', 'best offers', 'most popular', 'new arrivals'}]
                # The source uses overlapping collections; retain every membership in metadata.
                # Pick the most specific collection by catalogue size for the single FK.
                selected = min(candidates, key=lambda c: (counts[c['id']], c['name'])) if candidates else None
                category = None
                for source in row['categories']:
                    source_key = 'rm:' + source['id']
                    existing = (Category.objects.filter(legacy_key=source_key).first() or
                                Category.objects.filter(name__iexact=source['name']).first())
                    if existing is None:
                        existing = Category(name=source['name'],
                                            slug=slugify(source['name'])[:75] + '-rm-' + source['id'][:8],
                                            legacy_key=source_key)
                        existing.full_clean()
                        existing.save()
                    if selected and source['id'] == selected['id']:
                        category = existing
                product = self.product(row)
                product.category = category
                product.full_clean()
                product.save()
                for image in row['images'][:5]:
                    with (path.parent / image['path']).open('rb') as upload:
                        add_image(product.pk, upload, alt=image['alt'][:300])
                created += 1
            if created % 25 == 0:
                self.stdout.write(f'Created {created} drafts; skipped {skipped}')
        self.stdout.write(self.style.SUCCESS(f'Created {created} drafts; skipped {skipped} existing products.'))

    @staticmethod
    def product(row):
        metadata = {**row['metadata'], 'source_images': row['images'],
                    'category_assignment': 'smallest source collection; review before publication'}
        metadata['review_required'] = list(dict.fromkeys(metadata.get('review_required', []) + ['category_assignment_review']))
        return Product(
            legacy_key=row['key'], name=row['name'],
            slug=slugify(row['slug'])[:270] + '-rm-' + row['key'].split(':')[-1],
            sku=row['sku'], description=row['description'],
            regular_price=Decimal(row['regular_price']),
            sale_price=Decimal(row['sale_price']) if row['sale_price'] else None,
            metadata=metadata, is_published=False, stock=0, stock_confirmed=False,
            # Required model default is only a placeholder, explicitly flagged above.
            weight=Decimal('150'), weight_unit='g',
            new_arrival=(row['metadata'].get('source_ribbon') or '').upper() == 'NEW',
        )
