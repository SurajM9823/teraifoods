from pathlib import Path
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import Client, TestCase
from redis.exceptions import ConnectionError as RedisConnectionError
from .content import category_tree
from .forms import CategoryForm, SubcategoryForm
from .icons import ICON_CHOICES
from .models import Category, Subcategory


class CategoryTests(TestCase):
    def setUp(self):
        cache.clear()
        Subcategory.objects.all().delete()
        Category.objects.all().delete()
        self.category = Category.objects.create(name='Groceries', slug='groceries')
        self.child = Subcategory.objects.create(category=self.category, name='Rice', slug='rice')
        self.owner = get_user_model().objects.create_user('owner', is_staff=True, is_superuser=True)
        self.client.force_login(self.owner)

    def test_create_category_then_subcategory(self):
        response = self.client.post('/admin/categories/category/new/', {
            'name': 'Fresh Produce', 'position': 2, 'icon': 'fa-solid fa-carrot', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        parent = Category.objects.get(slug='fresh-produce')
        response = self.client.post('/admin/categories/subcategory/new/', {
            'name': 'Organic carrots', 'category': parent.pk, 'position': 0, 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Subcategory.objects.get(slug='organic-carrots').category, parent)
        self.assertContains(self.client.get('/admin/categories/'), 'Organic carrots')

    def test_subcategory_requires_existing_parent(self):
        for parent in ('', '999999'):
            form = SubcategoryForm(dict(name='Child', category=parent, position=0))
            self.assertFalse(form.is_valid())
            self.assertIn('category', form.errors)

    def test_duplicates_are_validated_and_database_enforced(self):
        form = CategoryForm(dict(name='GROCERIES', slug='other', position=0))
        self.assertFalse(form.is_valid())
        form = SubcategoryForm(dict(name='RICE', slug='other', category=self.category.pk, position=0))
        self.assertFalse(form.is_valid())
        with self.assertRaises(IntegrityError), transaction.atomic():
            Category.objects.create(name='GROCERIES', slug='other')
        other = Category.objects.create(name='Bulk', slug='bulk')
        Subcategory.objects.create(name='Rice', slug='rice', category=other)

    def test_edit_move_optional_icon_and_html_safety(self):
        other = Category.objects.create(name='Bulk', slug='bulk')
        response = self.client.post(f'/admin/categories/subcategory/{self.child.pk}/edit/', {
            'category': other.pk, 'name': '<script>Rice</script>', 'slug': 'rice',
            'position': 4, 'icon': '', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.child.refresh_from_db()
        self.assertEqual(self.child.category, other)
        self.assertContains(self.client.get('/admin/categories/'), '&lt;script&gt;Rice&lt;/script&gt;')
        form = CategoryForm(dict(name='Unsafe', position=0, icon='" onclick="alert(1)'))
        self.assertFalse(form.is_valid())
        self.assertIn('icon', form.errors)

    def test_status_inheritance_and_cache_invalidation(self):
        with self.assertNumQueries(2):
            self.assertEqual(len(category_tree()[0]['subcategories']), 1)
        with self.assertNumQueries(0):
            category_tree()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/admin/categories/category/{self.category.pk}/status/', {'active': 'false'})
        self.assertEqual(category_tree(), [])
        self.child.refresh_from_db()
        self.assertTrue(self.child.is_active)
        self.assertFalse(self.child.effective_active)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/admin/categories/category/{self.category.pk}/status/', {'active': 'true'})
        self.assertEqual(len(category_tree()[0]['subcategories']), 1)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/admin/categories/subcategory/{self.child.pk}/status/', {'active': 'false'})
        self.assertEqual(category_tree()[0]['subcategories'], [])

    def test_parent_delete_is_protected_and_child_delete_invalidates(self):
        self.assertEqual(self.client.get(f'/admin/categories/category/{self.category.pk}/delete/').status_code, 200)
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        self.client.post(f'/admin/categories/category/{self.category.pk}/delete/')
        self.assertTrue(Category.objects.filter(pk=self.category.pk).exists())
        with self.assertRaises(ProtectedError):
            self.category.delete()
        category_tree()
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(f'/admin/categories/subcategory/{self.child.pk}/delete/')
        self.assertEqual(category_tree()[0]['subcategories'], [])
        self.assertEqual(self.client.post(f'/admin/categories/category/{self.category.pk}/delete/').status_code, 302)

    def test_permissions_csrf_and_safe_methods(self):
        self.client.logout()
        self.assertEqual(self.client.get('/admin/categories/').status_code, 302)
        staff = get_user_model().objects.create_user('staff', is_staff=True)
        self.client.force_login(staff)
        self.assertEqual(self.client.get('/admin/categories/').status_code, 403)
        self.assertEqual(self.client.post('/admin/categories/category/new/', {}).status_code, 403)
        self.assertEqual(self.client.post(f'/admin/categories/category/{self.category.pk}/status/', {'active': 'false'}).status_code, 403)
        self.assertEqual(self.client.post(f'/admin/categories/category/{self.category.pk}/delete/').status_code, 403)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(self.owner)
        self.assertEqual(secured.post('/admin/categories/category/new/', {}).status_code, 403)
        self.client.force_login(self.owner)
        self.assertEqual(self.client.get(f'/admin/categories/category/{self.category.pk}/status/').status_code, 405)
        self.assertEqual(self.client.post(f'/admin/categories/category/{self.category.pk}/status/', {}).status_code, 400)

    def test_search_filters_order_and_parent_selection(self):
        Category.objects.create(name='Frozen', slug='frozen', is_active=False, position=5)
        response = self.client.get('/admin/categories/?q=Rice')
        self.assertContains(response, 'Groceries')
        self.assertNotContains(response, '<h2>Frozen</h2>')
        response = self.client.get('/admin/categories/?status=inactive')
        self.assertContains(response, '<h2>Frozen</h2>')
        self.assertNotContains(response, '<h2>Groceries</h2>')
        response = self.client.get(f'/admin/categories/subcategory/new/?parent={self.category.pk}')
        self.assertEqual(response.context['form'].initial['category'], self.category)
        self.assertEqual(self.client.get('/admin/categories/subcategory/new/?parent=bad').status_code, 404)

    def test_redis_failure_falls_back(self):
        with patch('catalog.content.cache.get', side_effect=RedisConnectionError):
            self.assertEqual(category_tree()[0]['name'], 'Groceries')

    def test_icons_exist_in_bundled_font_awesome(self):
        css = (Path(settings.BASE_DIR) / 'web/static/web/css/font-awesome.min.css').read_text(encoding='utf-8')
        for icon, _ in ICON_CHOICES:
            if icon:
                self.assertIn('.' + icon.split()[-1] + ':before', css)
