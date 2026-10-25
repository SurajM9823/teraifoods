"""Promote a reviewed catalogue export, retaining all existing live records."""
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import F
from catalog.content import invalidate_categories, CACHE_ERRORS
from catalog.models import Product, ProductImage, CatalogRevision
from catalog.rmfoods_duplicates import DuplicateIndex
from catalog.rmfoods_taxonomy import Assignment, resolve

PRODUCT_FIELDS = ('name', 'slug', 'sku', 'description', 'regular_price', 'sale_price', 'weight',
                  'weight_unit', 'is_active', 'is_published', 'is_archived', 'new_arrival',
                  'featured', 'best_seller', 'stock', 'stock_confirmed', 'low_stock_threshold',
                  'display_order', 'rating', 'review_count', 'legacy_key', 'metadata')
IMAGE_FIELDS = ('source', 'variants', 'alt', 'is_main', 'position', 'digest', 'width', 'height')


def image_paths(image):
    yield image['source']
    if not isinstance(image['variants'], dict):
        raise CommandError('Invalid image variants')
    for sizes in image['variants'].values():
        if not isinstance(sizes, dict):
            raise CommandError('Invalid image variant sizes')
        yield from sizes.values()


def safe_path(root, name):
    if not isinstance(name, str) or not name.startswith('products/'):
        raise CommandError('Expected a relative product image path')
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise CommandError('Unsafe image path')
    return path


class Command(BaseCommand):
    help = 'Plan reviewed RM Foods promotion; --apply copies prepared media and imports new products only.'

    def add_arguments(self, parser):
        parser.add_argument('--catalog', required=True)
        parser.add_argument('--media-root', required=True)
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--report')

    def handle(self, *args, **options):
        data = json.loads(Path(options['catalog']).read_text())
        if data.get('schema_version') != 1 or data.get('source') != 'rmfoods-reviewed' or data.get('currency') != 'GBP':
            raise CommandError('Expected a version 1 reviewed RM Foods GBP export')
        rows = data['products']
        keys = [row['product']['legacy_key'] for row in rows]
        if len(keys) != len(set(keys)) or any(not key.startswith('rmfoods:') for key in keys):
            raise CommandError('Invalid or repeated source keys')
        source_root, target_root = Path(options['media_root']).resolve(), Path(settings.MEDIA_ROOT).resolve()
        if source_root == target_root:
            raise CommandError('Reviewed media must be separate from target media')
        index = self.index()
        selected, skipped = self.plan(rows, index)
        paths = set()
        # Preflight everything before database writes or file copies.
        for row in selected:
            fields = row['product']
            if set(fields) != set(PRODUCT_FIELDS):
                raise CommandError('Unexpected product fields')
            product = Product(**fields)
            published = product.is_published
            product.is_published = False  # Category FK is resolved only during apply.
            product.full_clean(exclude=['category', 'subcategory'], validate_unique=False, validate_constraints=False)
            product.is_published = published
            if product.is_archived or not row['category'] or not row['subcategory']:
                raise CommandError('Reviewed product must have category/subcategory and not be archived')
            if len(row['images']) > 5:
                raise CommandError('Too many product images')
            for image in row['images']:
                if set(image) != set(IMAGE_FIELDS):
                    raise CommandError('Unexpected image fields')
                for name in image_paths(image):
                    source, target = safe_path(source_root, name), safe_path(target_root, name)
                    if not source.is_file():
                        raise CommandError('Missing reviewed image: ' + name)
                    if name in paths:
                        continue
                    if target.exists():
                        with source.open('rb') as left, target.open('rb') as right:
                            if hashlib.file_digest(left, 'sha256').digest() != hashlib.file_digest(right, 'sha256').digest():
                                raise CommandError('Existing image differs; refusing to overwrite: ' + name)
                    paths.add(name)
        copied = 0
        if options['apply']:
            if not target_root.exists():
                target_root.mkdir(parents=True, mode=0o755)
                os.chmod(target_root, 0o755)
            for name in sorted(paths):
                source, target = safe_path(source_root, name), safe_path(target_root, name)
                if target.exists():
                    continue
                parent = target_root
                for part in target.parent.relative_to(target_root).parts:
                    parent = parent / part
                    if not parent.exists():
                        parent.mkdir(mode=0o755)
                        os.chmod(parent, 0o755)
                # Exclusive creation also prevents overwriting a concurrent upload.
                try:
                    with source.open('rb') as src, target.open('xb') as dst:
                        shutil.copyfileobj(src, dst)
                    os.chmod(target, 0o644)
                    copied += 1
                except FileExistsError:
                    with source.open('rb') as left, target.open('rb') as right:
                        if hashlib.file_digest(left, 'sha256').digest() != hashlib.file_digest(right, 'sha256').digest():
                            raise CommandError('Concurrent image collision: ' + name)
            with transaction.atomic():
                if connection.vendor == 'postgresql':
                    # Readers keep serving; briefly serialize catalogue writers.
                    with connection.cursor() as cursor:
                        cursor.execute('LOCK TABLE catalog_product IN SHARE ROW EXCLUSIVE MODE')
                # Recheck after media preparation to account for concurrent admin additions.
                prepared_keys = {row['product']['legacy_key'] for row in selected}
                selected, skipped = self.plan(rows, self.index())
                if any(row['product']['legacy_key'] not in prepared_keys for row in selected):
                    raise CommandError('Catalogue changed during preparation; rerun promotion before applying')
                targets, created = {}, []
                for row in selected:
                    pair = row['category'], row['subcategory']
                    if pair not in targets:
                        targets[pair] = resolve(Assignment(*pair, 'reviewed_preview'))
                    category, child = targets[pair]
                    product = Product(**row['product'], category=category, subcategory=child)
                    product.full_clean(exclude=['category', 'subcategory'], validate_unique=False, validate_constraints=False)
                    created.append(product)
                Product.objects.bulk_create(created, batch_size=200)
                images = [ProductImage(product=product, **image) for product, row in zip(created, selected)
                          for image in row['images']]
                ProductImage.objects.bulk_create(images, batch_size=200)
                revision, _ = CatalogRevision.objects.get_or_create(pk=1)
                CatalogRevision.objects.filter(pk=revision.pk).update(version=F('version') + 1)
                def refresh():
                    invalidate_categories()
                    try:
                        cache.delete('catalog:revision:version')
                        cache.delete('catalog:search_vocab')
                    except CACHE_ERRORS:
                        pass
                transaction.on_commit(refresh)
        report = dict(applied=options['apply'], source_products=len(rows),
                      created=len(selected) if options['apply'] else 0, would_create=len(selected),
                      skipped=len(skipped), skip_reasons=dict(Counter(row['reason'] for row in skipped)),
                      prepared_image_files=len(paths), copied_image_files=copied,
                      created_source_keys=[row['product']['legacy_key'] for row in selected] if options['apply'] else [],
                      skipped_products=skipped)
        if options['report']:
            Path(options['report']).write_text(json.dumps(report, indent=2) + '\n')
        self.stdout.write(json.dumps({key: value for key, value in report.items()
                                     if key not in ('created_source_keys', 'skipped_products')}, indent=2))

    @staticmethod
    def index():
        return DuplicateIndex(Product.objects.order_by('pk').values('id', 'name', 'sku', 'legacy_key'))

    @staticmethod
    def plan(rows, index):
        selected, skipped = [], []
        for row in rows:
            product = row['product']
            reason, existing = index.find(product)
            if existing is not None:
                skipped.append(dict(source_key=product['legacy_key'], name=product['name'], reason=reason,
                                    existing_id=existing.get('id'), existing_source_key=existing.get('legacy_key')))
            else:
                selected.append(row)
                index.add({**product, 'id': None})
        return selected, skipped
