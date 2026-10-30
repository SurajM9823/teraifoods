import copy
import json
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import connection
from django.test import TestCase, SimpleTestCase, override_settings

from catalog.models import Product, Category, ProductImage, Order, StockAudit
from orders.models import Payment, Notification
from shopify_integration.client import ShopifyClient, ShopifyError
from shopify_integration.graphql import (SCOPES_QUERY, FILES_QUERY, FILE_QUERY, PRODUCT_SNAPSHOT, FILE_CREATE, PRODUCT_SET)
from shopify_integration.draft_sync import prepare_draft, execute_draft
from shopify_integration.models import (ShopifyConnection, ShopifyProductMapping, ShopifySyncJob,
    ShopifyVariantMapping, ShopifyMediaMapping, ChannelVariantDefinition, IntegrationLog)
from shopify_integration.services import dry_run, approve_variant_review


@override_settings(SHOPIFY_ENABLED=True, SHOPIFY_DRAFT_SYNC_ENABLED=True,
    SHOPIFY_SHOP_DOMAIN='test.myshopify.com', SHOPIFY_MEDIA_ORIGIN='https://media.example.com')
class DraftSyncTests(TestCase):
    def setUp(self):
        self.shop = ShopifyConnection.objects.create(shop_domain='test.myshopify.com', enabled=True)
        category = Category.objects.create(name='Draft groceries', slug='draft-groceries')
        self.product = Product.objects.create(name='Draft rice', slug='draft-rice', regular_price=Decimal('10.00'),
            sale_price=Decimal('8.00'), category=category, is_published=True, description='Rice & more')
        self.image = ProductImage.objects.create(product=self.product, source='products/rice.jpg',
            digest='a'*64, width=100, height=100, is_main=True)
        self.product.refresh_from_db()
        self.remote = None
        self.api = Mock()
        self.api.query.side_effect = self.query
        self.api.mutate.side_effect = self.mutate
        self.client_patch = patch('shopify_integration.draft_sync.ShopifyClient', return_value=self.api)
        self.client_patch.start(); self.addCleanup(self.client_patch.stop)

    def query(self, document, variables=None):
        if document == SCOPES_QUERY:
            return {'shop': {'currencyCode': 'GBP'}, 'currentAppInstallation': {'accessScopes': [
                {'handle': 'write_products'}, {'handle': 'write_files'}]}}
        if document == FILES_QUERY:
            return {'files': {'nodes': []}}
        if document == FILE_QUERY:
            return {'node': {'id': 'gid://shopify/MediaImage/1', 'fileStatus': 'READY'}}
        if document == PRODUCT_SNAPSHOT:
            return {'productByIdentifier': copy.deepcopy(self.remote)}
        raise AssertionError(document)

    def mutate(self, document, variables):
        if document == FILE_CREATE:
            return {'files': [{'id': 'gid://shopify/MediaImage/1', 'fileStatus': 'READY'}]}
        if document == PRODUCT_SET:
            payload = variables['input']
            self.remote = {'id': 'gid://shopify/Product/1', 'title': payload['title'],
                'handle': payload['handle'], 'descriptionHtml': payload['descriptionHtml'], 'status': 'DRAFT',
                'metafield': {'value': str(self.product.pk)},
                'media': {'nodes': [{'id': f['id'], 'status': 'READY'} for f in payload['files']],
                          'pageInfo': {'hasNextPage': False}},
                'variants': {'nodes': [], 'pageInfo': {'hasNextPage': False, 'endCursor': None}}}
            for index, variant in enumerate(payload['variants']):
                self.remote['variants']['nodes'].append({'id': variant.get('id', f'gid://shopify/ProductVariant/{index+1}'),
                    'price': variant['price'], 'compareAtPrice': variant['compareAtPrice'], 'sku': variant['inventoryItem']['sku'],
                    'selectedOptions': [{'name': v['optionName'], 'value': v['name']} for v in variant['optionValues']],
                    'inventoryItem': {'id': f'gid://shopify/InventoryItem/{index+1}', **variant['inventoryItem']}})
            return {'product': {'id': self.remote['id'], 'status': 'DRAFT'}}
        raise AssertionError(document)

    def run_job(self):
        return execute_draft(prepare_draft(self.shop, self.product.pk).pk)

    def test_create_draft_media_price_weight_and_untracked_inventory(self):
        job = self.run_job()
        self.assertEqual(job.status, 'succeeded')
        mapping = ShopifyProductMapping.objects.get()
        self.assertEqual(mapping.status, 'draft_synced')
        self.assertEqual(mapping.remote_product_gid, 'gid://shopify/Product/1')
        self.assertEqual(ShopifyVariantMapping.objects.get().local_key, 'default')
        self.assertEqual(ShopifyMediaMapping.objects.get().status, 'ready')
        sent = [c.args[1]['input'] for c in self.api.mutate.call_args_list if c.args[0] == PRODUCT_SET][0]
        self.assertEqual(sent['status'], 'DRAFT')
        row = sent['variants'][0]
        self.assertEqual(row['price'], '8.00')
        self.assertEqual(row['compareAtPrice'], '10.00')
        self.assertFalse(row['inventoryItem']['tracked'])
        self.assertEqual(row['inventoryItem']['measurement']['weight'], {'unit': 'GRAMS', 'value': 150.0})
        self.assertNotIn('inventoryQuantities', row)

    def test_retry_reuses_remote_product_variant_and_media(self):
        self.assertEqual(self.run_job().status, 'succeeded')
        original_id = self.remote['variants']['nodes'][0]['id']
        self.product.regular_price = Decimal('12.00'); self.product.save()
        self.assertEqual(self.run_job().status, 'succeeded')
        creations = [c for c in self.api.mutate.call_args_list if c.args[0] == FILE_CREATE]
        self.assertEqual(len(creations), 1)
        sent = [c.args[1]['input'] for c in self.api.mutate.call_args_list if c.args[0] == PRODUCT_SET][-1]
        self.assertEqual(sent['variants'][0]['id'], original_id)
        self.assertNotIn('metafields', sent)
        self.assertNotIn('status', sent)
        self.assertEqual(ShopifyProductMapping.objects.count(), 1)

    def test_uncertain_create_reconciles_handle_before_retry(self):
        mutate = self.mutate
        first = True
        def uncertain(document, variables):
            nonlocal first
            result = mutate(document, variables)
            if document == PRODUCT_SET and first:
                first = False
                raise ShopifyError('transport_error')
            return result
        self.api.mutate.side_effect = uncertain
        job = self.run_job()
        self.assertEqual(job.status, 'retry')
        self.assertIsNone(ShopifyProductMapping.objects.get().remote_product_gid)
        self.assertEqual(execute_draft(job.pk).status, 'succeeded')
        self.assertEqual(ShopifyProductMapping.objects.get().remote_product_gid, 'gid://shopify/Product/1')
        product_calls = [c for c in self.api.mutate.call_args_list if c.args[0] == PRODUCT_SET]
        self.assertEqual(product_calls[-1].args[1]['identifier'], {'id': 'gid://shopify/Product/1'})

    def test_missing_scope_stops_before_upload_or_product_mutation(self):
        self.api.query.return_value = {'shop': {'currencyCode': 'GBP'}, 'currentAppInstallation': {'accessScopes': []}}
        self.api.query.side_effect = None
        job = self.run_job()
        self.assertEqual(job.status, 'failed')
        self.assertIn('missing_write', job.error_code)
        self.api.mutate.assert_not_called()

    def test_unreviewed_variants_do_not_queue(self):
        self.product.metadata = {'source_options': [{'title': 'Flavour'}]}; self.product.save()
        with self.assertRaises(ValidationError):
            prepare_draft(self.shop, self.product.pk)
        self.assertFalse(ShopifyProductMapping.objects.exists())
        self.api.query.assert_not_called()

    @override_settings(SHOPIFY_DRAFT_SYNC_ENABLED=False)
    def test_disabled_draft_writes_do_not_queue(self):
        with self.assertRaises(ShopifyError):
            prepare_draft(self.shop, self.product.pk)
        self.assertFalse(ShopifySyncJob.objects.exists())

    def test_stock_payments_orders_and_notifications_untouched(self):
        self.product.stock = 12; self.product.stock_confirmed = True; self.product.save()
        before = self.product.metadata.copy()
        self.assertEqual(self.run_job().status, 'succeeded')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 12)
        self.assertEqual(self.product.metadata, before)
        for model in (Order, Payment, StockAudit, Notification):
            self.assertFalse(model.objects.exists())

    def test_remote_active_or_unmanaged_product_cannot_be_overwritten(self):
        self.run_job()
        for status, owner in [('ACTIVE', str(self.product.pk)), ('DRAFT', 'other')]:
            with self.subTest(status=status):
                self.remote['status'] = status; self.remote['metafield']['value'] = owner
                self.api.mutate.reset_mock()
                job = self.run_job()
                self.assertEqual(job.status, 'failed')
                self.api.mutate.assert_not_called()

    def test_extra_remote_variant_blocks_implicit_deletion(self):
        self.run_job()
        extra = copy.deepcopy(self.remote['variants']['nodes'][0])
        extra['selectedOptions'] = [{'name': 'Unmanaged', 'value': 'Extra'}]
        self.remote['variants']['nodes'].append(extra)
        self.api.mutate.reset_mock()
        self.assertEqual(self.run_job().error_code, 'variant_removal_requires_explicit_review')
        self.api.mutate.assert_not_called()

    def test_merchant_media_preserved(self):
        self.run_job()
        self.remote['media']['nodes'].append({'id': 'gid://shopify/MediaImage/merchant', 'status': 'READY'})
        self.assertEqual(self.run_job().status, 'succeeded')
        self.assertIn('gid://shopify/MediaImage/merchant', [m['id'] for m in self.remote['media']['nodes']])

    def test_reviewed_variants_use_normalized_prices_and_option_names(self):
        for key, price in [('cola', '12.00'), ('cherry', '15.00')]:
            ChannelVariantDefinition.objects.create(product=self.product, key=key,
                option_values=[{'name': 'Flavour', 'value': key}], price_policy='explicit', price=price, image=self.image)
        staff = get_user_model().objects.create_superuser('draft-staff', 'staff@example.com', 'testpass')
        approve_variant_review(self.product.pk, staff)
        self.assertEqual(self.run_job().status, 'succeeded')
        self.assertEqual(ShopifyVariantMapping.objects.count(), 2)

    def test_pending_jobs_deduplicated_and_completed_jobs_not_reexecuted(self):
        first = prepare_draft(self.shop, self.product.pk)
        self.assertEqual(prepare_draft(self.shop, self.product.pk).pk, first.pk)
        execute_draft(first.pk)
        count = self.api.mutate.call_count
        self.assertEqual(execute_draft(first.pk).status, 'succeeded')
        self.assertEqual(self.api.mutate.call_count, count)

    def test_source_change_during_api_call_requires_reconciliation(self):
        def change_source(document, variables):
            result = self.mutate(document, variables)
            if document == PRODUCT_SET:
                Product.objects.filter(pk=self.product.pk).update(name='Changed during sync')
            return result
        self.api.mutate.side_effect = change_source
        job = self.run_job()
        self.assertEqual(job.error_code, 'source_changed_during_sync')
        self.assertEqual(job.status, 'retry')

    def test_api_exceptions_do_not_leak_secrets(self):
        self.api.query.side_effect = RuntimeError('client-secret-DO-NOT-LOG')
        job = self.run_job()
        self.assertEqual(job.error_code, 'internal_sync_error')
        self.assertEqual(IntegrationLog.objects.get().codes, ['internal_sync_error'])

    def test_staff_sync_permission_required(self):
        staff = get_user_model().objects.create_user('restricted-staff', is_staff=True)
        with self.assertRaises(PermissionDenied):
            prepare_draft(self.shop, self.product.pk, actor=staff)

    def test_cli_requires_explicit_apply(self):
        with self.assertRaises(CommandError):
            call_command('shopify_sync', str(self.product.pk))
        self.assertFalse(ShopifySyncJob.objects.exists())

    def test_website_avif_uses_retained_jpeg_for_shopify(self):
        self.image.source = 'products/current.avif'
        self.image.variants = {'jpeg': {'160': 'products/small.jpg', '1200': 'products/original.jpg'}}
        self.image.save()
        self.assertEqual(dry_run(self.product)['payload']['images'][0]['url'],
                         'https://media.example.com/media/products/original.jpg')

    def test_oversize_titles_block_before_network(self):
        self.product.name = 'X' * 256; self.product.save()
        with self.assertRaisesMessage(ValidationError, 'shopify_title_too_long'):
            prepare_draft(self.shop, self.product.pk)
        self.api.query.assert_not_called()

    def test_dispatcher_only_dispatches_explicit_jobs_on_dedicated_queue(self):
        from shopify_integration.tasks import dispatch_draft_jobs
        with patch('shopify_integration.tasks.run_draft_job.apply_async') as enqueue:
            dispatch_draft_jobs()
            enqueue.assert_not_called()
            job = prepare_draft(self.shop, self.product.pk)
            dispatch_draft_jobs()
            enqueue.assert_called_once_with(args=[job.pk], queue='shopify')

    def test_remote_tracking_verification_failure_not_marked_successful(self):
        def tracked(document, variables):
            result = self.mutate(document, variables)
            if document == PRODUCT_SET:
                self.remote['variants']['nodes'][0]['inventoryItem']['tracked'] = True
            return result
        self.api.mutate.side_effect = tracked
        self.assertEqual(self.run_job().error_code, 'inventory_tracking_not_disabled')
        self.assertNotEqual(ShopifyProductMapping.objects.get().status, 'draft_synced')

    def test_shopify_null_sku_matches_unassigned_django_sku(self):
        def null_sku(document, variables):
            result = self.mutate(document, variables)
            if document == PRODUCT_SET:
                self.remote['variants']['nodes'][0]['sku'] = None
            return result
        self.api.mutate.side_effect = null_sku
        self.assertEqual(self.run_job().status, 'succeeded')


@override_settings(SHOPIFY_ENABLED=True, SHOPIFY_DRAFT_SYNC_ENABLED=True, SHOPIFY_SHOP_DOMAIN='test.myshopify.com',
    SHOPIFY_ACCESS_TOKEN='fake', SHOPIFY_API_VERSION='2026-10')
class DraftClientTests(SimpleTestCase):
    def setUp(self):
        self.api = ShopifyClient(ShopifyConnection(shop_domain='test.myshopify.com', enabled=True))

    def test_active_status_and_unknown_mutations_rejected(self):
        with patch.object(self.api, '_post') as post:
            with self.assertRaisesMessage(ShopifyError, 'publication_not_allowed'):
                self.api.mutate(PRODUCT_SET, {'input': {'status': 'ACTIVE'}})
            with self.assertRaises(ShopifyError):
                self.api.mutate('mutation { productDelete { id } }')
            post.assert_not_called()

    def test_uncertain_mutations_are_never_automatically_replayed(self):
        self.api._opener.open = Mock(side_effect=HTTPError('https://test', 503, 'private', {}, None))
        with self.assertRaisesMessage(ShopifyError, 'http_503'):
            self.api.mutate(PRODUCT_SET, {'input': {'status': 'DRAFT'}})
        self.assertEqual(self.api._opener.open.call_count, 1)

    def test_user_errors_only_log_codes(self):
        with patch.object(self.api, '_post', return_value={'data': {'productSet': {
                'product': None, 'userErrors': [{'code': 'INVALID', 'message': 'secret data'}]}}}):
            with self.assertRaisesMessage(ShopifyError, 'user_error:INVALID'):
                self.api.mutate(PRODUCT_SET, {'input': {'status': 'DRAFT'}})
