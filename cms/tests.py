from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.test import Client, TestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError

from .content import homepage_content
from .forms import BannerForm
from .models import Banner, InformationBlock


class ContentTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_upload_saved_in_server_media_and_replacement_has_new_url(self):
        with TemporaryDirectory() as directory, override_settings(MEDIA_ROOT=directory):
            banner = Banner.objects.first()
            def upload():
                image = BytesIO()
                Image.new('RGB', (1170, 548)).save(image, format='PNG')
                return SimpleUploadedFile('banner.png', image.getvalue(), content_type='image/png')
            data = dict(title='Local banner', button_label='Shop', position=0,
                        is_active=True, destination='/shop/')
            form = BannerForm(data, {'image': upload()}, instance=banner)
            self.assertTrue(form.is_valid(), form.errors)
            banner = form.save()
            self.assertRegex(banner.image.name, r'^cms/banners/\d{4}/\d{2}/[a-f0-9]{32}\.png$')
            original = banner.image.name
            self.assertTrue((Path(directory) / original).is_file())
            self.assertEqual(banner.image.url, '/media/' + original)
            form = BannerForm(data, {'image': upload()}, instance=banner)
            self.assertTrue(form.is_valid(), form.errors)
            replacement = form.save()
            self.assertNotEqual(replacement.image.name, original)
            self.assertTrue((Path(directory) / replacement.image.name).is_file())

    def test_shared_cache_avoids_database_queries(self):
        with self.assertNumQueries(2):
            initial = homepage_content()
        with self.assertNumQueries(0):
            self.assertEqual(homepage_content(), initial)
        self.assertEqual(len(initial['information']), 4)

    def test_save_and_delete_invalidate_after_commit(self):
        homepage_content()
        banner = Banner.objects.first()
        with self.captureOnCommitCallbacks(execute=True):
            banner.title = 'Updated content'
            banner.save()
        self.assertEqual(homepage_content()['banners'][0]['title'], 'Updated content')
        with self.captureOnCommitCallbacks(execute=True):
            banner.delete()
        self.assertEqual(len(homepage_content()['banners']), 1)
        item = InformationBlock.objects.first()
        with self.captureOnCommitCallbacks(execute=True):
            item.is_active = False
            item.save()
        self.assertNotIn(item.slot, homepage_content()['information'])

    def test_rollback_leaves_published_content_unchanged(self):
        before = homepage_content()
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    banner = Banner.objects.first()
                    banner.title = 'Rolled back'
                    banner.save()
                    raise ValueError('rollback')
            except ValueError:
                pass
        self.assertEqual(homepage_content(), before)

    def test_inflight_old_load_cannot_repopulate_new_generation(self):
        from .content import _load, invalidate_home
        def racing_load():
            old = _load()
            Banner.objects.filter(pk=Banner.objects.first().pk).update(title='New generation')
            invalidate_home()
            return old
        with patch('cms.content._load', side_effect=racing_load):
            homepage_content()
        self.assertEqual(homepage_content()['banners'][0]['title'], 'New generation')

    def test_redis_outage_falls_back_to_database(self):
        with patch('cms.content.cache.get', side_effect=RedisConnectionError):
            self.assertEqual(len(homepage_content()['banners']), 2)

    def test_homepage_escapes_content_and_has_no_fake_prices(self):
        banner = Banner.objects.first()
        banner.title = '<script>alert(1)</script>'
        banner.save()
        response = self.client.get('/')
        self.assertContains(response, '&lt;script&gt;alert(1)&lt;/script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertNotContains(response, 'banner-price')
        for item in InformationBlock.objects.all():
            self.assertContains(response, item.title)

    def test_admin_access_permissions_and_csrf(self):
        self.assertEqual(self.client.get('/admin/cms/').status_code, 302)
        user = get_user_model().objects.create_user('editor', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/cms/').status_code, 403)
        self.assertEqual(self.client.post('/admin/cms/banners/new/', {}).status_code, 403)
        user.is_superuser = True
        user.save()
        self.assertEqual(self.client.get('/admin/cms/').status_code, 200)
        secured = Client(enforce_csrf_checks=True)
        secured.force_login(user)
        banner = Banner.objects.first()
        self.assertEqual(secured.post(f'/admin/cms/banners/{banner.pk}/delete/').status_code, 403)
        self.assertEqual(self.client.get(f'/admin/cms/banners/{banner.pk}/delete/').status_code, 405)

    def test_admin_edit_updates_public_page(self):
        user = get_user_model().objects.create_user('owner', is_staff=True, is_superuser=True)
        self.client.force_login(user)
        banner = Banner.objects.first()
        homepage_content()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f'/admin/cms/banners/{banner.pk}/', {
                'title': 'Fresh groceries', 'button_label': 'Browse',
                'destination': '/shop/', 'position': 0, 'is_active': 'on',
            })
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get('/'), 'Fresh groceries')

    def test_unsafe_links_and_invalid_uploads_are_rejected(self):
        base = dict(title='Banner', button_label='Shop', position=0, is_active=True)
        for destination in ('javascript:alert(1)', '//evil.test', '/\\evil.test', 'https://evil.test'):
            form = BannerForm({**base, 'destination': destination}, instance=Banner.objects.first())
            self.assertFalse(form.is_valid())
            self.assertIn('destination', form.errors)
        form = BannerForm({**base, 'destination': '/shop/'}, {'image': SimpleUploadedFile('x.png', b'not an image', content_type='image/png')})
        self.assertFalse(form.is_valid())
        image = BytesIO()
        Image.new('RGB', (1170, 548)).save(image, format='PNG')
        form = BannerForm({**base, 'destination': '/shop/'}, {'image': SimpleUploadedFile('banner.png', image.getvalue(), content_type='image/png')})
        self.assertTrue(form.is_valid(), form.errors)
