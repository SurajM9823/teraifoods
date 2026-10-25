import io
import json
import tempfile
from pathlib import Path
from django.test import TestCase, SimpleTestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from catalog.models import Product, Category
from catalog.rmfoods_duplicates import DuplicateIndex
from catalog.management.commands.import_rmfoods_reviewed import PRODUCT_FIELDS


class DuplicateMatchingTests(SimpleTestCase):
    def test_identity_preserves_pack_sizes_and_matches_owner_skus(self):
        index = DuplicateIndex([dict(id=1, legacy_key='rmfoods:one', name='Original 12 x 500ml', sku='ABC')])
        self.assertEqual(index.find(dict(legacy_key='rmfoods:one', name='Edited', sku=''))[0], 'source_key')
        self.assertEqual(index.find(dict(name=' ORIGINAL  12 x 500ml ', sku=''))[0], 'name')
        self.assertEqual(index.find(dict(name='Owner renamed it', sku=' abc '))[0], 'sku')
        self.assertIsNone(index.find(dict(name='Original 24 x 500ml', sku=''))[1])


class ReviewedPromotionTests(TestCase):
    def row(self, key, name, *, images=None):
        product = Product(name=name, slug=key.replace(':', '-'), legacy_key=key,
                          regular_price=10, is_published=True, metadata={'owner_note': 'reviewed'})
        fields = {name: getattr(product, name) for name in PRODUCT_FIELDS}
        return dict(product=fields, category='Drinks', subcategory='Soft Drinks', images=images or [])

    def write(self, folder, rows):
        path = folder / 'reviewed.json'
        path.write_text(json.dumps(dict(schema_version=1, source='rmfoods-reviewed', currency='GBP', products=rows), default=str))
        return path

    def test_skips_existing_and_seed_duplicates_preserves_owner_and_copies_media(self):
        category = Category.objects.create(name='Drinks', slug='drinks', is_active=False)
        owner = Product.objects.create(name='Existing 12 x 500ml', slug='owner', category=category,
            sku='OWN-SKU', regular_price=7, stock=5, stock_confirmed=True, metadata={'keep': True})
        before = Product.objects.values().get(pk=owner.pk)
        image = dict(source='products/reviewed/20.jpg', variants={'jpeg': {'20': 'products/reviewed/20.jpg'}},
                     alt='Reviewed', is_main=True, position=0, digest='a' * 64, width=20, height=20)
        rows = [self.row('rmfoods:old', ' EXISTING 12 x 500ml '),
                self.row('rmfoods:new', 'New 12 x 500ml', images=[image]),
                self.row('rmfoods:duplicate', ' New  12 x 500ml ')]
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root / 'source', root / 'target'
            (source / 'products/reviewed').mkdir(parents=True)
            (source / image['source']).write_bytes(b'prepared-image')
            report = root / 'report.json'
            path = self.write(root, rows)
            with self.settings(MEDIA_ROOT=target):
                call_command('import_rmfoods_reviewed', catalog=str(path), media_root=str(source), report=str(report), stdout=io.StringIO())
                self.assertEqual(Product.objects.count(), 1)
                self.assertFalse(target.exists())
                call_command('import_rmfoods_reviewed', catalog=str(path), media_root=str(source), apply=True, report=str(report), stdout=io.StringIO())
                result = json.loads(report.read_text())
                self.assertEqual((result['created'], result['skipped']), (1, 2))
                self.assertEqual((target / image['source']).read_bytes(), b'prepared-image')
                new = Product.objects.get(legacy_key='rmfoods:new')
                self.assertTrue(new.is_published)
                self.assertFalse(new.stock_confirmed)
                self.assertEqual(new.stock, 0)
                self.assertEqual(new.subcategory.category_id, new.category_id)
                self.assertEqual(new.images.count(), 1)
                self.assertEqual(new.metadata['owner_note'], 'reviewed')
                call_command('import_rmfoods_reviewed', catalog=str(path), media_root=str(source), apply=True, report=str(report), stdout=io.StringIO())
                self.assertEqual(json.loads(report.read_text())['created'], 0)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Product.objects.values().get(pk=owner.pk), before)
        category.refresh_from_db()
        self.assertFalse(category.is_active)

    def test_refuses_media_overwrite_before_database_changes(self):
        image = dict(source='products/reviewed/20.jpg', variants={}, alt='', is_main=True,
                     position=0, digest='a' * 64, width=20, height=20)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for name, content in [('source', b'reviewed'), ('target', b'existing')]:
                (root / name / 'products/reviewed').mkdir(parents=True)
                (root / name / image['source']).write_bytes(content)
            path = self.write(root, [self.row('rmfoods:new', 'New', images=[image])])
            with self.settings(MEDIA_ROOT=root / 'target'), self.assertRaises(CommandError):
                call_command('import_rmfoods_reviewed', catalog=str(path), media_root=str(root / 'source'), apply=True, stdout=io.StringIO())
            self.assertEqual((root / 'target' / image['source']).read_bytes(), b'existing')
        self.assertFalse(Product.objects.exists())
