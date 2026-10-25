"""Portable catalogue-only export: excludes users, sessions, orders and secrets."""
import json
from copy import deepcopy
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from catalog.models import Product
from catalog.management.commands.import_rmfoods_reviewed import PRODUCT_FIELDS, IMAGE_FIELDS


class Command(BaseCommand):
    help = 'Export the reviewed RM Foods products and prepared image references from a named local database.'

    def add_arguments(self, parser):
        parser.add_argument('--source-database', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, *args, **options):
        name = options['source_database']
        config = deepcopy(settings.DATABASES['default'])
        config['NAME'] = name
        config['CONN_MAX_AGE'] = 0
        settings.DATABASES['rmfoods_review_export'] = config
        products = Product.objects.using('rmfoods_review_export').filter(
            legacy_key__startswith='rmfoods:').select_related('category', 'subcategory').prefetch_related('images').order_by('pk')
        rows = []
        for product in products:
            if product.is_package or not product.category_id or not product.subcategory_id:
                raise CommandError('Expected individual products with reviewed category/subcategory')
            if product.subcategory.category_id != product.category_id:
                raise CommandError('Subcategory does not belong to its category')
            rows.append(dict(product={name: getattr(product, name) for name in PRODUCT_FIELDS},
                             category=product.category.name, subcategory=product.subcategory.name,
                             images=[{name: getattr(image, name) for name in IMAGE_FIELDS} for image in product.images.all()]))
        if not rows:
            raise CommandError('No RM Foods products found')
        Path(options['output']).write_text(json.dumps(dict(schema_version=1, source='rmfoods-reviewed', currency='GBP', products=rows), default=str) + '\n')
        self.stdout.write(f'Exported {len(rows)} reviewed catalogue products. No database changes.')
