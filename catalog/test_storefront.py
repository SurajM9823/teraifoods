import importlib
from django.apps import apps
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from .models import Category, Subcategory
from .content import category_tree


class StorefrontCategoryTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_original_categories_are_imported_once_with_artwork(self):
        self.assertEqual(Category.objects.count(), 11)
        self.assertEqual(Subcategory.objects.count(), 58)
        fruit = Category.objects.get(legacy_key='fruits-veg')
        self.assertEqual(fruit.menu_image, 'apple.svg')
        self.assertEqual(fruit.subcategories.count(), 7)
        seed = importlib.import_module('catalog.migrations.0003_import_storefront_categories').seed
        seed(apps, type('Editor', (), {'connection': connection})())
        self.assertEqual(Category.objects.count(), 11)
        self.assertEqual(Subcategory.objects.count(), 58)

    def test_one_shared_template_used_across_storefront(self):
        for path in ('/', '/shop/', '/product/', '/product-detail/', '/cart/', '/checkout/', '/contact/', '/blogs/', '/bulk-order/', '/track-order/', '/payment/'):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertTemplateUsed(response, 'catalog/storefront/menu.html')
            self.assertContains(response, 'data-backend-category="fruits-veg"')
            self.assertContains(response, '/static/web/images/apple.svg')
            self.assertNotContains(response, 'Breaksfast &amp; Dairy')

    def test_admin_changes_update_every_menu_and_cache(self):
        category_tree()
        parent = Category.objects.get(legacy_key='fruits-veg')
        with self.captureOnCommitCallbacks(execute=True):
            parent.name = 'Fresh Farm Produce'
            parent.save()
        for path in ('/', '/shop/', '/contact/'):
            self.assertContains(self.client.get(path), 'Fresh Farm Produce')
        with self.assertNumQueries(0):
            category_tree()
        child = parent.subcategories.first()
        with self.captureOnCommitCallbacks(execute=True):
            child.is_active = False
            child.save()
        self.assertNotContains(self.client.get('/'), child.name)
        with self.captureOnCommitCallbacks(execute=True):
            parent.is_active = False
            parent.save()
        for path in ('/', '/shop/', '/contact/'):
            self.assertNotContains(self.client.get(path), 'data-backend-category="fruits-veg"')

    def test_storefront_text_is_escaped(self):
        parent = Category.objects.get(legacy_key='fruits-veg')
        parent.name = '<script>alert(1)</script>'
        parent.save()
        response = self.client.get('/')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
