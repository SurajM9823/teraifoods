"""Import the portable RM Foods seed, preserving existing products."""
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from catalog.media import add_image
from catalog.models import Product
from catalog.rmfoods_taxonomy import assign, mapped_metadata, resolve
from catalog.rmfoods_duplicates import DuplicateIndex


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
        duplicates = DuplicateIndex(Product.objects.order_by('pk').values('id', 'name', 'sku', 'legacy_key'))
        for row in rows:
            if duplicates.find(row)[1] is not None:
                skipped += 1
                continue
            with transaction.atomic():
                assignment = assign(row)
                category, subcategory = resolve(assignment)
                product = self.product(row)
                product.category = category
                product.subcategory = subcategory
                product.full_clean()
                product.save()
                for image in row['images'][:5]:
                    with (path.parent / image['path']).open('rb') as upload:
                        add_image(product.pk, upload, alt=image['alt'][:300])
                duplicates.add(dict(id=product.pk, name=product.name, sku=product.sku, legacy_key=product.legacy_key))
                created += 1
            if created % 25 == 0:
                self.stdout.write(f'Created {created} drafts; skipped {skipped}')
        self.stdout.write(self.style.SUCCESS(f'Created {created} drafts; skipped {skipped} existing products.'))

    @staticmethod
    def product(row):
        metadata = mapped_metadata(row, assign(row))
        metadata['source_images'] = row['images']
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
