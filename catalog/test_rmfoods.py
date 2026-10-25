import io
import json
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from PIL import Image

from catalog.models import Product
from catalog.rmfoods import extract_product, normalize, plain_text


class RMFoodsImportTests(TestCase):
    def record(self):
        product = {'id': 'test-product', 'name': 'Example pack', 'urlPart': 'example',
                   'price': 10, 'discountedPrice': 8, 'productItems': [], 'media': [],
                   'categories': [{'id': 'category-id', 'name': 'Drinks'}]}
        return normalize(product, 'https://www.rmfoodswholesale.co.uk/product-page/example')

    def test_target_product_and_prices(self):
        product = {'urlPart': 'example', 'price': 10, 'productItems': []}
        html = '<script id="wix-warmup-data" type="application/json">' + json.dumps({'nested': product}) + '</script>'
        self.assertEqual(extract_product(html, 'example'), product)
        with self.assertRaises(ValueError):
            extract_product(html, 'different')
        self.assertEqual(self.record()['sale_price'], '8.00')

    def test_rich_text_table(self):
        def cell(text):
            return {'type': 'TABLE_CELL', 'nodes': [{'textData': {'text': text}}]}
        value = {'nodes': [{'type': 'TABLE', 'nodes': [
            {'type': 'TABLE_ROW', 'nodes': [cell('Energy'), cell('100 kJ')]},
            {'type': 'TABLE_ROW', 'nodes': [cell('Salt'), cell('1g')]}]}]}
        self.assertEqual(plain_text(json.dumps(value)), 'Energy\t100 kJ\nSalt\t1g')

    def test_draft_idempotency_and_dry_run(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'seed.json'
            path.write_text(json.dumps({'schema_version': 1, 'currency': 'GBP', 'products': [self.record()]}))
            call_command('import_rmfoods', seed=str(path), dry_run=True, stdout=io.StringIO())
            self.assertEqual(Product.objects.count(), 0)
            call_command('import_rmfoods', seed=str(path), stdout=io.StringIO())
            product = Product.objects.get()
            self.assertFalse(product.is_published)
            self.assertFalse(product.stock_confirmed)
            self.assertEqual(product.category.name, 'Drinks')
            product.name = 'Owner edit'
            product.save()
            call_command('import_rmfoods', seed=str(path), stdout=io.StringIO())
            self.assertEqual(Product.objects.count(), 1)
            self.assertEqual(Product.objects.get().name, 'Owner edit')

    def test_checksum_failure_prevents_writes(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'seed.json'
            image = Path(folder) / 'image.png'
            Image.new('RGB', (10, 10)).save(image)
            record = self.record()
            record['images'] = [{'path': 'image.png', 'digest': 'wrong'}]
            path.write_text(json.dumps({'schema_version': 1, 'currency': 'GBP', 'products': [record]}))
            with self.assertRaises(CommandError):
                call_command('import_rmfoods', seed=str(path), stdout=io.StringIO())
            self.assertFalse(Product.objects.exists())

    def test_real_image_pipeline(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder, self.settings(MEDIA_ROOT=folder):
            path = Path(folder) / 'seed.json'
            image = Path(folder) / 'image.png'
            Image.new('RGB', (20, 20), 'red').save(image)
            record = self.record()
            record['images'] = [{'path': 'image.png', 'digest': hashlib.sha256(image.read_bytes()).hexdigest(),
                                 'alt': 'Example pack'}]
            path.write_text(json.dumps({'schema_version': 1, 'currency': 'GBP', 'products': [record]}))
            call_command('import_rmfoods', seed=str(path), stdout=io.StringIO())
            stored = Product.objects.get().images.get()
            self.assertTrue(stored.is_main)
            self.assertIn('webp', stored.variants)
            self.assertIn('avif', stored.variants)
            self.assertTrue((Path(folder) / stored.source).exists())
