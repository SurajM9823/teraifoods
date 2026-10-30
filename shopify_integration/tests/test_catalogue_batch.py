from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from catalog.models import Category, Product
from shopify_integration.models import ShopifyCatalogueBatch, ShopifyConnection, ShopifySyncJob, IntegrationLog
from shopify_integration.tasks import prepare_catalogue_batch


@override_settings(SHOPIFY_ENABLED=True, SHOPIFY_DRAFT_SYNC_ENABLED=True,
                   SHOPIFY_SHOP_DOMAIN='batch.myshopify.com')
class CatalogueBatchTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_superuser('batch-admin', 'batch@example.com', 'test-password')
        self.connection = ShopifyConnection.objects.create(shop_domain='batch.myshopify.com', enabled=True)
        category = Category.objects.create(name='Batch', slug='batch')
        for i in range(23):
            Product.objects.create(name=f'Product {i}', slug=f'product-{i}', category=category,
                                   regular_price='2.00', is_published=True)

    def test_button_requires_post_permission_and_deduplicates(self):
        url = '/admin/system/shopify_integration/shopifycatalogueproduct/sync-all/'
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(ShopifyCatalogueBatch.objects.exists())
        self.client.force_login(self.actor)
        self.assertEqual(self.client.get(url).status_code, 405)
        for _ in range(2):
            self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(ShopifyCatalogueBatch.objects.count(), 1)
        self.assertFalse(ShopifySyncJob.objects.exists())
        self.actor.is_superuser = False
        self.actor.save()
        self.assertEqual(self.client.post(url).status_code, 403)

    @patch('shopify_integration.draft_sync.prepare_draft')
    @patch('shopify_integration.services.dry_run', return_value={'errors': [], 'payload_hash': 'new'})
    def test_worker_resumes_in_pages_without_api_calls_or_publication(self, preview, prepare):
        batch = ShopifyCatalogueBatch.objects.create(connection=self.connection, actor=self.actor)
        with patch('socket.socket.connect', side_effect=AssertionError('Unexpected network')):
            prepare_catalogue_batch(batch.pk)
            batch.refresh_from_db()
            self.assertEqual((batch.status, batch.queued), ('pending', 20))
            prepare_catalogue_batch(batch.pk)
            batch.refresh_from_db()
            self.assertEqual((batch.status, batch.queued), ('prepared', 23))
            prepare_catalogue_batch(batch.pk)
        self.assertEqual(prepare.call_count, 23)
        self.assertFalse(ShopifySyncJob.objects.filter(operation__in=['publish', 'unpublish']).exists())

    @patch('shopify_integration.services.dry_run', return_value={'errors': ['unreviewed_variants']})
    def test_invalid_products_are_reported_without_jobs(self, preview):
        batch = ShopifyCatalogueBatch.objects.create(connection=self.connection, actor=self.actor)
        prepare_catalogue_batch(batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.skipped, 20)
        self.assertEqual(IntegrationLog.objects.filter(operation='bulk_sync', status='skipped').count(), 20)
        self.assertFalse(ShopifySyncJob.objects.exists())

    def test_disabled_connection_stops_batch(self):
        batch = ShopifyCatalogueBatch.objects.create(connection=self.connection, actor=self.actor)
        self.connection.enabled = False
        self.connection.save()
        prepare_catalogue_batch(batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.status, 'stopped')
        self.assertFalse(ShopifySyncJob.objects.exists())
