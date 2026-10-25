import io
import json
from pathlib import Path
import tempfile

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, SimpleTestCase
from PIL import Image

from catalog.models import Product, Category, Subcategory
from catalog.rmfoods import extract_product, normalize, plain_text
from catalog.rmfoods_taxonomy import assign, mapped_metadata


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

    def test_hierarchy_beats_brands_and_promotions(self):
        row = self.record()
        row['name'] = 'Monster Energy Original'
        row['categories'] += [{'id': str(i), 'name': name} for i, name in enumerate(
            ['Brands', 'Monster Energy', 'Energy Drinks', 'Best Offers'])]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'seed.json'
            path.write_text(json.dumps({'schema_version': 1, 'currency': 'GBP', 'products': [row]}))
            call_command('import_rmfoods', seed=str(path), stdout=io.StringIO())
        product = Product.objects.get()
        self.assertEqual(product.category.name, 'Energy Drinks')
        self.assertEqual(product.subcategory.name, 'Monster Energy')
        self.assertEqual(product.subcategory.category_id, product.category_id)
        self.assertFalse(Category.objects.filter(name__in=['Brands', 'Best Offers', 'Monster Energy']).exists())
        self.assertTrue(product.metadata['rmfoods_collections']['best_offers'])

    def test_repair_is_planned_by_default_and_preserves_owner_edits(self):
        bad = Category.objects.create(name='Nescafe', slug='nescafe-flat', legacy_key='rm:brand')
        unused = Category.objects.create(name='Brands', slug='brands-flat', legacy_key='rm:brands')
        parent = Category.objects.create(name='Coffee', slug='coffee', is_active=False)
        row = self.record()
        row['name'] = 'Nescafe Instant Coffee'
        row['categories'] = [{'id': 'coffee-id', 'name': 'Coffee'}, {'id': 'brand', 'name': 'Nescafe'}]
        product = Product.objects.create(name='Owner edited name', slug='owner-edited', legacy_key=row['key'],
            category=bad, regular_price=22, stock=9, stock_confirmed=True, metadata={'owner_note': 'keep'})
        manual = Product.objects.create(name='Manual', slug='manual', category=bad, regular_price=1)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'seed.json'
            path.write_text(json.dumps({'schema_version': 1, 'currency': 'GBP', 'products': [row]}))
            call_command('repair_rmfoods_categories', seed=str(path), stdout=io.StringIO())
            product.refresh_from_db()
            self.assertEqual(product.category_id, bad.pk)
            call_command('repair_rmfoods_categories', seed=str(path), apply=True, stdout=io.StringIO())
            call_command('repair_rmfoods_categories', seed=str(path), apply=True, stdout=io.StringIO())
        product.refresh_from_db()
        parent.refresh_from_db()
        unused.refresh_from_db()
        bad.refresh_from_db()
        manual.refresh_from_db()
        self.assertEqual(product.category_id, parent.pk)
        self.assertEqual(product.subcategory.name, 'Coffee Ground / Granules')
        self.assertEqual(product.name, 'Owner edited name')
        self.assertEqual(product.regular_price, 22)
        self.assertEqual(product.stock, 9)
        self.assertTrue(product.stock_confirmed)
        self.assertFalse(product.is_published)
        self.assertEqual(product.metadata['owner_note'], 'keep')
        self.assertFalse(parent.is_active)
        self.assertFalse(unused.is_active)
        self.assertTrue(bad.is_active)  # Still used by the manual product.
        self.assertEqual(manual.category_id, bad.pk)
        self.assertEqual(parent.subcategories.count(), 1)

    def test_collection_filters_and_cursor_cannot_cross_collections(self):
        from catalog.api import paginate
        from catalog.content import collection_links
        from django.core.exceptions import ValidationError
        category = Category.objects.create(name='Energy Drinks', slug='energy-drinks')
        child = Subcategory.objects.create(category=category, name='Monster Energy', slug='monster')
        for i in range(3):
            row = self.record()
            row['categories'] = [{'id': 'offers', 'name': 'Best Offers'}] if i < 2 else []
            Product.objects.create(name=f'Monster {i}', slug=f'monster-{i}', category=category,
                subcategory=child, regular_price=10, is_published=True, metadata=mapped_metadata(row, assign(row)))
        rows, page = paginate({'category': category.slug, 'subcategory': child.slug,
                               'collection': 'best-offers', 'limit': '1'})
        self.assertEqual(page['total'], 2)
        self.assertEqual(len(rows), 1)
        with self.assertRaises(ValidationError):
            paginate({'category': category.slug, 'subcategory': child.slug,
                      'collection': 'most-popular', 'limit': '1', 'cursor': page['next_cursor']})
        self.assertEqual(collection_links(), [{'name': 'Best Offers', 'key': 'best-offers'}])


class RMFoodsTaxonomyTests(SimpleTestCase):
    def test_merchandise_types_and_recovery(self):
        examples = [
            ('Monster Mango Energy', ['All Products', 'Brands', 'Drinks', 'Energy Drinks', 'Monster Energy'], 'Energy Drinks', 'Monster Energy'),
            ('Nescafe Latte Sachets', ['Brands', 'Nescafe', 'Coffee', 'Coffee Sachets/Blends'], 'Coffee', 'Coffee Sachets / Blends'),
            ('Cadbury Dairy Milk', ['Cadbury', 'Chocolate Bars', 'Best Offers'], 'Snacks & Chocolates', 'Chocolate Bars'),
            ('Walkers Ready Salted', ['Walkers Crisps', 'Crisps'], 'Crisps', 'Walkers Crisps'),
            ('Hell Iced Coffee Slim Vanilla', ['Drinks', 'Hell Energy', 'Brands'], 'Coffee', 'Ready to Drink Coffee'),
            ('Whiskas Fish Selection in Jelly', ['Pet Foods'], 'Pet Foods', 'Cat Food & Treats'),
            ('Haribo Jelly Babies', ['Bagged Sweets'], 'Snacks & Chocolates', 'Bagged Sweets'),
            ('Honey Roast Peanuts', ['Nuts'], 'Snacks & Chocolates', 'Nuts & Savoury Snacks'),
            ('Flipz Peanut Butter Pretzels', ['All Products'], 'Snacks & Chocolates', 'Nuts & Savoury Snacks'),
            ('Best-In Golden Oats Flapjacks', ['All Products'], 'Snacks & Chocolates', 'Cereal & Snack Bars'),
            ('Alpen Original Breakfast Cereal', ['All Products'], 'Cereals', 'Breakfast Cereals'),
            ('MONIN Gourmet Syrup Strawberry', ['All Products'], 'Drinks', 'Drink Syrups & Purees'),
            ('Nescafe Coffee Mate Coffee Whitener', ['Nescafe', 'Brands'], 'Food Cupboard', 'Milk & Coffee Whiteners'),
            ('KTC Edible Mustard Oil', ['Tinned Goods'], 'Food Cupboard', 'Oils & Ghee'),
        ]
        for name, categories, parent, child in examples:
            with self.subTest(name=name):
                result = assign({'name': name, 'categories': [{'name': c} for c in categories]})
                self.assertEqual((result.category, result.subcategory), (parent, child))

    def test_complete_seed_has_no_unresolved_products(self):
        from catalog.rmfoods_taxonomy import GROUPS
        data = json.loads((Path(__file__).parent / 'data/rmfoods/seed.json').read_text(encoding='utf-8'))
        allowed = {name: {child for child, aliases in children} for name, aliases, children in GROUPS}
        for row in data['products']:
            assignment = assign(row)
            with self.subTest(key=row['key']):
                self.assertNotEqual(assignment.method, 'unresolved')
                self.assertIn(assignment.category, allowed)
                self.assertIn(assignment.subcategory, allowed[assignment.category])
