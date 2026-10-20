import io
import json
import tempfile
from decimal import Decimal
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from .models import Product, ProductImage, Category, Subcategory, StockAudit, Order
from .services import adjust_stock, reserve_order, cancel_order, set_main_image, delete_image, reorder_images
from .media import add_image, prepare_image
from .product_forms import ProductForm


def image_bytes(fmt='PNG'):
    result = io.BytesIO()
    Image.new('RGB', (24, 16), '#d17828').save(result, format=fmt)
    result.seek(0)
    return result


class ProductTests(TestCase):
    def setUp(self):
        cache.clear()
        from delivery.models import WeightBand
        WeightBand.objects.create(max_weight_grams=100000, charge=0)
        self.staff = get_user_model().objects.create_user('product-staff', is_staff=True, is_superuser=True)
        self.customer = get_user_model().objects.create_user('buyer')
        self.category = Category.objects.first()
        self.product = Product.objects.create(name='Test groceries', slug='test-groceries', category=self.category,
            regular_price=Decimal('10.00'), sale_price=Decimal('8.00'), featured=True, is_published=True)
        self.image = ProductImage.objects.create(product=self.product, source='products/test/main.jpg',
            width=24, height=16, digest='a'*64, is_main=True, variants={})

    def stock(self, quantity=10, key='initial'):
        return adjust_stock(self.product.pk, quantity, reason='Counted stock', actor=self.staff, key=key, kind='initial')

    def test_price_constraints_and_featured_validation(self):
        for changes in ({'regular_price':0}, {'sale_price':11}, {'sale_price':0}, {'sale_price':None}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Product.objects.filter(pk=self.product.pk).update(**changes)
        self.product.sale_price = None
        with self.assertRaises(ValidationError):
            self.product.full_clean()
        self.product.featured = False
        self.product.full_clean()

    def test_subcategory_parent_validation(self):
        other = Category.objects.exclude(pk=self.category.pk).first()
        self.product.subcategory = other.subcategories.first() or Subcategory.objects.create(category=other, name='Other', slug='other')
        with self.assertRaises(ValidationError):
            self.product.full_clean()

    def test_public_listing_sections_and_inactive(self):
        data = self.client.get('/api/products/?section=for_you').json()
        self.assertEqual(len(data['products']), 1)
        self.assertIn('for_you', data['products'][0]['sections'])
        self.assertFalse(data['products'][0]['available'])
        self.assertEqual(self.client.get('/api/products/?section=featured').json()['total'], 1)
        self.product.is_active = False
        self.product.save()
        self.assertEqual(self.client.get('/api/products/').json()['total'], 0)
        self.assertEqual(self.client.get('/api/products/test-groceries/').status_code, 404)

    def test_all_optional_sections_and_none(self):
        self.product.new_arrival = self.product.best_seller = True
        self.product.save()
        for section in ('new_arrival', 'featured', 'best_seller', 'for_you'):
            self.assertEqual(self.client.get('/api/products/', {'section':section}).json()['total'], 1)
        self.product.new_arrival = self.product.best_seller = self.product.featured = False
        self.product.save()
        self.assertEqual(self.client.get('/api/products/?section=for_you').json()['total'], 1)

    def test_keyset_pagination_ties_and_filter_mismatch(self):
        for i in range(7):
            Product.objects.create(name=f'Item {i}', slug=f'item-{i}', category=self.category,
                                   regular_price=10, is_published=True)
        for sort in ('', 'price-asc', 'price-desc', 'name', 'rating', 'newest'):
            seen, cursor = [], ''
            for _ in range(8):
                response = self.client.get('/api/products/', {'limit':3, 'sort':sort, 'cursor':cursor})
                self.assertEqual(response.status_code, 200, response.content)
                data = response.json()
                seen.extend(p['id'] for p in data['products'])
                if not data['has_more']:
                    break
                cursor = data['next_cursor']
            self.assertEqual(len(seen), 8)
            self.assertEqual(len(set(seen)), 8)
        first = self.client.get('/api/products/?limit=2').json()
        self.assertEqual(self.client.get('/api/products/', {'limit':2,'q':'other','cursor':first['next_cursor']}).status_code, 400)
        self.assertEqual(self.client.get('/api/products/?cursor=garbage').status_code, 400)
        self.assertEqual(self.client.get('/api/products/?min_price=NaN').status_code, 400)

    def test_advanced_search_space_and_typo_matching(self):
        from django.core.cache import cache
        cache.clear()
        p1 = Product.objects.create(name='Organic Himalayan Basmati Rice', slug='organic-basmati-rice',
                                    category=self.category, regular_price=12, is_published=True)
        p2 = Product.objects.create(name='Red Split Lentils', slug='red-split-lentils',
                                    category=self.category, regular_price=5, is_published=True)
        # Multi-word space search
        res1 = self.client.get('/api/products/', {'q': 'basmati rice'}).json()
        self.assertIn(p1.pk, [p['id'] for p in res1['products']])

        # Typo / spelling mistake tolerance: "oragnic" -> "organic"
        res2 = self.client.get('/api/products/', {'q': 'oragnic'}).json()
        self.assertIn(p1.pk, [p['id'] for p in res2['products']])

        # Typo with space: "splti lentils" -> "split lentils"
        res3 = self.client.get('/api/products/', {'q': 'splti lentils'}).json()
        self.assertIn(p2.pk, [p['id'] for p in res3['products']])

    def test_stock_initial_adjustments_idempotency_and_immutability(self):
        audit = self.stock()
        self.assertEqual(self.stock().pk, audit.pk)
        decrease = adjust_stock(self.product.pk, -4, reason='Damaged', actor=self.staff, key='damage', kind='manual_decrease')
        self.assertEqual((decrease.previous_quantity, decrease.new_quantity), (10,6))
        with self.assertRaises(ValidationError):
            adjust_stock(self.product.pk, -7, reason='Too many', actor=self.staff, key='bad')
        with self.assertRaises(ValidationError):
            adjust_stock(self.product.pk, 2, reason='Different', actor=self.staff, key='damage')
        with self.assertRaises(ValidationError):
            audit.save()
        with self.assertRaises(ValidationError):
            StockAudit.objects.filter(pk=audit.pk).update(reason='Edited')
        with self.assertRaises(ValidationError):
            audit.delete()
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 6)
        self.assertEqual(StockAudit.objects.count(), 2)

    def test_order_uses_database_price_and_atomic_stock(self):
        self.stock(3)
        items = [{'product_id':self.product.pk, 'quantity':2, 'price':'0.01'}]
        order = reserve_order(self.customer, items, 'checkout-one')
        self.assertEqual(order.total, Decimal('16.00'))
        self.assertEqual(reserve_order(self.customer, items, 'checkout-one').pk, order.pk)
        with self.assertRaises(ValidationError):
            reserve_order(self.customer, items, 'checkout-two')
        self.assertEqual(Order.objects.count(), 1)
        cancel_order(order.pk, self.staff)
        cancel_order(order.pk, self.staff)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)
        self.assertEqual(StockAudit.objects.filter(adjustment_type='cancellation').count(), 1)

    def test_checkout_rejects_inactive_category_and_unknown_stock(self):
        items = [{'product_id':self.product.pk,'quantity':1}]
        with self.assertRaises(ValidationError):
            reserve_order(self.customer, items, 'unknown')
        self.stock()
        self.category.is_active = False
        self.category.save()
        with self.assertRaises(ValidationError):
            reserve_order(self.customer, items, 'inactive-category')

    def test_checkout_auth_and_payload(self):
        response = self.client.post('/api/checkout/reserve/', '{}', content_type='application/json')
        self.assertEqual(response.status_code, 401)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post('/api/checkout/reserve/', '[]', content_type='application/json').status_code, 400)

    def test_image_main_delete_reorder_and_five_limit(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            second = add_image(self.product.pk, image_bytes(), main=True)
            self.image.refresh_from_db()
            self.assertFalse(self.image.is_main)
            with self.assertRaises(ValidationError):
                delete_image(self.product.pk, second.pk)
            delete_image(self.product.pk, second.pk, self.image.pk)
            self.image.refresh_from_db()
            self.assertTrue(self.image.is_main)
            images = [self.image]
            for _ in range(4):
                images.append(add_image(self.product.pk, image_bytes()))
            reorder_images(self.product.pk, [i.pk for i in reversed(images)])
            self.assertEqual(self.product.images.first().pk, images[-1].pk)
            with self.assertRaises(ValidationError):
                add_image(self.product.pk, image_bytes())

    def test_image_formats_and_content_validation(self):
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            for fmt in ('JPEG', 'PNG', 'WEBP', 'AVIF'):
                prepared = prepare_image(image_bytes(fmt))
                self.assertEqual(set(prepared['variants']), {'avif','webp','jpeg'})
                for extension, paths in prepared['variants'].items():
                    for path in paths.values():
                        with Image.open(directory + '/' + path) as image:
                            self.assertEqual(image.size, (24,16))
            with self.assertRaises(ValidationError):
                prepare_image(io.BytesIO(b'<script>not an image</script>'))

    def test_cache_invalidation_and_redis_failure_fallback(self):
        self.client.get('/api/products/')
        self.product.name = 'Changed name'
        self.product.save()
        self.assertEqual(self.client.get('/api/products/').json()['products'][0]['name'], 'Changed name')
        with patch('catalog.api.cache.get', side_effect=ConnectionError):
            self.assertEqual(self.client.get('/api/products/').status_code, 200)
        response = self.client.get('/api/products/')
        self.assertIn('must-revalidate', response['Cache-Control'])
        self.assertEqual(self.client.get('/api/products/', HTTP_IF_NONE_MATCH=response['ETag']).status_code, 304)

    def test_admin_authorization_and_html_escaping(self):
        self.assertEqual(self.client.get('/admin/products/').status_code, 302)
        self.client.force_login(self.customer)
        self.assertEqual(self.client.post(reverse('products:stock', args=[self.product.pk]), {}).status_code, 302)
        self.client.force_login(self.staff)
        self.product.name = '<script>alert(1)</script>'
        self.product.save()
        response = self.client.get('/admin/products/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.client.get(reverse('products:edit', args=[self.product.pk])).status_code, 200)

    def test_category_delete_protected_by_products(self):
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.category.delete()

    def test_frontend_uses_existing_card_and_backend_name(self):
        response = self.client.get('/shop/')
        self.assertContains(response, 'shop-product-card')
        self.assertContains(response, 'Test groceries')
        self.assertContains(response, 'data-catalog-product')
        self.assertNotContains(response, 'Royal Himalayan 2-Year Aged Basmati Rice')
        self.assertContains(self.client.get('/product-detail/?product=test-groceries'), 'Test groceries')
        self.assertEqual(self.client.get('/product-detail/?product=missing').status_code, 404)
        self.assertContains(self.client.get('/search/?q=groceries'), 'Test groceries')

    def test_admin_api_create_edit_archive_and_permission(self):
        self.assertEqual(self.client.get('/api/admin/products/').status_code, 401)
        self.client.force_login(self.staff)
        payload = dict(name='API draft', slug='api-draft', regular_price='3.25',
                       category=self.category.pk, is_active=True)
        response = self.client.post('/api/admin/products/', json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 201, response.content)
        product_id = response.json()['id']
        url = f'/api/admin/products/{product_id}/'
        response = self.client.patch(url, json.dumps({'featured':True}), content_type='application/json')
        self.assertEqual(response.status_code, 400)
        response = self.client.patch(url, json.dumps({'sale_price':'2.50','featured':True,'new_arrival':True,'best_seller':True}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()['featured'])
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertTrue(Product.objects.get(pk=product_id).is_archived)

    def test_admin_stock_api_idempotency_and_history(self):
        self.client.force_login(self.staff)
        url = f'/api/admin/products/{self.product.pk}/stock/'
        data = json.dumps({'quantity':4,'reason':'Delivery received','type':'initial'})
        for _ in range(2):
            response = self.client.post(url, data, content_type='application/json', HTTP_IDEMPOTENCY_KEY='api-stock')
            self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(len(self.client.get(url).json()['history']), 1)
        invalid = self.client.post(url, json.dumps({'quantity':1,'reason':5}), content_type='application/json', HTTP_IDEMPOTENCY_KEY='bad')
        self.assertEqual(invalid.status_code, 400)

    def test_staff_writes_require_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.staff)
        self.assertEqual(client.post('/api/admin/products/', '{}', content_type='application/json').status_code, 403)

    def test_admin_form_initial_stock(self):
        self.client.force_login(self.staff)
        response = self.client.post('/admin/products/add/', dict(name='Initial stock form', slug='initial-stock-form',
            regular_price='4.00', category=self.category.pk, is_active='on', low_stock_threshold=5, initial_stock=9,
            weight='150', weight_unit='g'))
        self.assertEqual(response.status_code, 302, response.content)
        product = Product.objects.get(slug='initial-stock-form')
        self.assertEqual(product.stock, 9)
        self.assertEqual(product.stock_history.get().adjustment_type, 'initial')

    def test_catalog_revision_and_ids_filter(self):
        from .models import CatalogRevision
        res = self.client.get('/api/catalog/revision/')
        self.assertEqual(res.status_code, 200)
        v1 = res.json()['version']

        # Edit product and verify revision increments
        self.product.name = 'Updated Real-time Groceries'
        self.product.save()

        res2 = self.client.get('/api/catalog/revision/')
        self.assertEqual(res2.status_code, 200)
        v2 = res2.json()['version']
        self.assertGreater(v2, v1)
        self.assertIn(self.product.pk, res2.json().get('changed_ids', []))

        # Test querying products by ids
        res_ids = self.client.get(f'/api/products/?ids={self.product.pk}')
        self.assertEqual(res_ids.status_code, 200)
        data = res_ids.json()
        self.assertTrue(any(p['id'] == self.product.pk for p in data['products']))
        self.assertEqual(data['products'][0]['name'], 'Updated Real-time Groceries')


class ImportTests(TestCase):
    def test_complete_idempotent_import_and_no_overwrite(self):
        from django.conf import settings
        manifest = json.loads((settings.BASE_DIR / 'catalog/data/legacy-products.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            path = directory + '/report.json'
            call_command('import_legacy_products', report=path, stdout=io.StringIO())
            self.assertEqual(Product.objects.count(), len(manifest['products']))
            product = Product.objects.first()
            product.name = 'Administrator edit'
            product.save()
            image_count = ProductImage.objects.count()
            call_command('import_legacy_products', report=path, stdout=io.StringIO())
            product.refresh_from_db()
            self.assertEqual(product.name, 'Administrator edit')
            self.assertEqual(Product.objects.count(), len(manifest['products']))
            self.assertEqual(ProductImage.objects.count(), image_count)
            self.assertFalse(Product.objects.filter(stock_confirmed=True).exists())
            report = json.loads(open(path, encoding='utf-8').read())
            self.assertEqual(report['skipped'], len(manifest['products']))
