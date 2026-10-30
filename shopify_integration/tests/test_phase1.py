import io
import json
from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.core.management import call_command, CommandError
from django.db import IntegrityError, transaction, connection
from django.test import SimpleTestCase, TestCase, override_settings

from catalog.models import Category, Order, OrderLine, Product, ProductImage, StockAudit
from orders.models import Notification, Payment
from shopify_integration.client import SHOP_QUERY, ShopifyClient, ShopifyError
from shopify_integration.models import (ChannelVariantDefinition, IntegrationLog, ShopifyConnection,
    ShopifyOrderMapping, ShopifyProductMapping, ShopifyWebhookReceipt, ShopifyMediaMapping)
from shopify_integration.services import approve_variant_review, dry_run


@contextmanager
def read_only_preview():
    def check(execute, sql, params, many, context):
        if sql.lstrip().split(None, 1)[0].upper() != 'SELECT':
            raise AssertionError('Preview attempted a database mutation: ' + sql)
        return execute(sql, params, many, context)
    with connection.execute_wrapper(check), patch('socket.socket.connect', side_effect=AssertionError('Preview attempted network access')):
        yield


@override_settings(SHOPIFY_MEDIA_ORIGIN='https://media.example.com', SHOPIFY_ENABLED=False)
class DryRunTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name='Integration test', slug='integration-test')
        self.product = Product.objects.create(name='Rice', slug='integration-rice', category=self.category,
                                              regular_price='10.00', sale_price='8.00', is_published=True)
        self.image = ProductImage.objects.create(product=self.product, source='products/rice.jpg',
            variants={}, digest='a' * 64, width=100, height=100, is_main=True)
        self.product.refresh_from_db()
        self.staff = get_user_model().objects.create_superuser('integration-staff', 'staff@example.com', 'test-password')

    def definition(self, **kwargs):
        values = {'product': self.product, 'key': 'cola', 'source_variant_id': 'v1',
                  'option_values': [{'name': 'Flavour', 'value': 'Cola'}]}
        values.update(kwargs)
        return ChannelVariantDefinition.objects.create(**values)

    def source(self):
        self.product.metadata = {'source_options': [{'title': 'Flavour', 'selections': [{'id': 1, 'value': 'Cola'}]}],
                                 'source_variants': [{'id': 'v1', 'optionsSelections': [1], 'price': 25}],
                                 'untouched': {'nested': True}}
        self.product.save()

    def test_simple_product_draft_without_stock_or_credentials(self):
        report = dry_run(self.product)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['proposed_action'], 'create_draft')
        self.assertEqual(report['new_product_status'], 'DRAFT')
        self.assertEqual(report['payload']['variants'][0]['price'], '8.00')
        self.assertEqual(report['payload']['variants'][0]['compareAtPrice'], '10.00')
        self.assertFalse(report['payload']['variants'][0]['inventoryTracked'])
        self.assertEqual(report['payload']['images'][0]['url'], 'https://media.example.com/media/products/rice.jpg')

    @patch('shopify_integration.client.build_opener')
    @patch('orders.payments.client')
    @patch('catalog.services.adjust_stock')
    def test_preview_never_networks_pays_reserves_or_emails(self, stock, stripe, opener):
        before = self.product.metadata.copy()
        with read_only_preview():
            dry_run(self.product)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 0)
        self.assertEqual(self.product.metadata, before)
        for model in (Order, OrderLine, Payment, StockAudit, Notification, ShopifyProductMapping):
            self.assertEqual(model.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)
        stock.assert_not_called(); stripe.assert_not_called(); opener.assert_not_called()
        self.assertFalse(IntegrationLog.objects.exists())

    def test_last_applied_diff_only_managed_fields_no_status_update(self):
        connection = ShopifyConnection.objects.create(shop_domain='test.myshopify.com')
        report = dry_run(self.product)
        mapping = ShopifyProductMapping.objects.create(connection=connection, product=self.product,
            remote_product_gid='gid://shopify/Product/1', applied_payload={**report['payload'], 'vendor': 'Shopify merchant'})
        report = dry_run(self.product, connection)
        self.assertEqual(report['expected_changes'], [])
        self.assertEqual(report['proposed_action'], 'update_managed_fields')
        self.assertNotIn('status', report['managed_fields'])
        self.assertNotIn('vendor', report['managed_fields'])
        mapping.refresh_from_db()
        self.assertEqual(mapping.status, 'not_synced')

    def test_unreviewed_source_options_block_and_preserve_metadata(self):
        self.source()
        before = json.dumps(self.product.metadata, sort_keys=True)
        report = dry_run(self.product)
        self.assertEqual(report['proposed_action'], 'blocked')
        self.assertIn('normalized_variants_required', report['errors'])
        self.product.refresh_from_db()
        self.assertEqual(json.dumps(self.product.metadata, sort_keys=True), before)

    def test_single_source_default_item_remains_simple(self):
        self.product.metadata = {'source_variants': [{'id': 'v1', 'optionsSelections': []}]}
        self.product.save()
        self.assertEqual(dry_run(self.product)['kind'], 'simple')
        self.assertEqual(dry_run(self.product)['errors'], [])

    def test_review_approves_inheritance_not_unreviewed_source_price(self):
        self.source(); self.definition()
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])
        approve_variant_review(self.product.pk, self.staff)
        self.product.refresh_from_db()
        report = dry_run(self.product)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['payload']['variants'][0]['price'], '8.00')
        self.assertEqual(report['payload']['options'], [{'name': 'Flavour', 'values': ['Cola']}])

    def test_review_stales_on_definition_source_or_price_changes(self):
        self.source(); definition = self.definition()
        approve_variant_review(self.product.pk, self.staff)
        definition.option_values = [{'name': 'Flavour', 'value': 'Cherry'}]
        definition.save()
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])
        approve_variant_review(self.product.pk, self.staff)
        self.product.metadata['source_variants'][0]['price'] = 99
        self.product.save()
        self.product.refresh_from_db()
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])
        approve_variant_review(self.product.pk, self.staff)
        self.product.regular_price = Decimal('11.00'); self.product.save(); self.product.refresh_from_db()
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])

    def test_missing_price_mapping_or_duplicate_combinations_cannot_be_approved(self):
        self.source(); definition = self.definition(price_policy='explicit')
        with self.assertRaises(ValidationError):
            approve_variant_review(self.product.pk, self.staff)
        self.assertIn('invalid_variant_price', dry_run(self.product)['errors'])
        definition.price_policy = 'inherit'; definition.source_variant_id = 'wrong'; definition.save()
        self.assertIn('incomplete_source_variant_mapping', dry_run(self.product)['errors'])
        self.definition(key='duplicate', source_variant_id='v1')
        self.assertIn('duplicate_option_combination', dry_run(self.product)['errors'])

    def test_option_shape_foreign_image_and_invalid_price_block(self):
        definition = self.definition(option_values={'Flavour': 'Cola'})
        self.assertIn('invalid_option_mapping', dry_run(self.product)['errors'])
        other = Product.objects.create(name='Other', slug='integration-other', regular_price=1)
        self.image.product = other; self.image.save()
        definition.option_values = [{'name': 'Flavour', 'value': 'Cola'}]
        definition.image = self.image; definition.price_policy = 'explicit'; definition.price = -1; definition.save()
        errors = dry_run(self.product)['errors']
        self.assertIn('variant_image_not_owned_by_product', errors)
        self.assertIn('invalid_variant_price', errors)

    def test_non_staff_cannot_approve(self):
        self.definition()
        user = get_user_model().objects.create_user('integration-buyer')
        with self.assertRaises(PermissionDenied):
            approve_variant_review(self.product.pk, user)

    def test_reviewed_explicit_prices_weight_and_owned_image(self):
        self.definition(price_policy='explicit', price=Decimal('12.50'), compare_at_price=Decimal('15.00'),
                        weight_grams=Decimal('2000'), image=self.image)
        approve_variant_review(self.product.pk, self.staff)
        report = dry_run(self.product)
        self.assertEqual(report['errors'], [])
        variant = report['payload']['variants'][0]
        self.assertEqual(variant['price'], '12.50')
        self.assertEqual(variant['compareAtPrice'], '15.00')
        self.assertEqual(Decimal(variant['weightGrams']), Decimal('2000'))
        self.assertEqual(variant['django_image_id'], self.image.pk)

    @override_settings(SHOPIFY_MEDIA_ORIGIN='')
    def test_relative_images_block_without_origin(self):
        self.assertIn('image_requires_public_https_url', dry_run(self.product)['errors'])

    def test_inactive_product_never_proposes_archive_or_delete(self):
        self.product.is_active = False
        report = dry_run(self.product)
        self.assertEqual(report['proposed_action'], 'blocked')
        self.assertNotIn('status', report['payload'])

    def test_command_outputs_local_preview_without_writes(self):
        output = io.StringIO()
        with read_only_preview():
            call_command('shopify_dry_run', str(self.product.pk), stdout=output)
        self.assertTrue(json.loads(output.getvalue())[0]['dry_run'])
        self.assertFalse(IntegrationLog.objects.exists())
        with self.assertRaises(CommandError):
            call_command('shopify_dry_run', str(self.product.pk), '--record', stdout=io.StringIO())
        self.assertFalse(IntegrationLog.objects.exists())

    def test_malformed_single_source_record_cannot_become_simple(self):
        for variants in ([None], ['bad'], [3], [{}], [{'id': ''}], [{'id': 'v1', 'optionsSelections': 'bad'}], False, 0, {}):
            with self.subTest(variants=variants):
                self.product.metadata = {'source_variants': variants}
                before = json.dumps(self.product.metadata, sort_keys=True)
                with read_only_preview():
                    report = dry_run(self.product)
                self.assertIn('invalid_source_variants', report['errors'])
                self.assertEqual(report['proposed_action'], 'blocked')
                self.assertEqual(json.dumps(self.product.metadata, sort_keys=True), before)

    def test_inherited_sku_change_invalidates_variant_review(self):
        self.definition()
        approve_variant_review(self.product.pk, self.staff)
        self.assertEqual(dry_run(self.product)['errors'], [])
        self.product.sku = 'CHANGED-SKU'
        self.product.save()
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])
        approve_variant_review(self.product.pk, self.staff)
        self.assertEqual(dry_run(self.product)['errors'], [])

    def test_explicit_variant_sku_does_not_inherit_product_sku(self):
        self.definition(sku='REVIEWED-SKU')
        approve_variant_review(self.product.pk, self.staff)
        self.product.sku = 'UNUSED-SKU'
        self.product.save()
        report = dry_run(self.product)
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['payload']['variants'][0]['sku'], 'REVIEWED-SKU')

    def test_existing_image_editor_can_delete_referenced_main_image(self):
        definition = self.definition(image=self.image)
        approve_variant_review(self.product.pk, self.staff)
        replacement = ProductImage.objects.create(product=self.product, source='products/replacement.jpg',
            digest='b'*64, width=100, height=100, position=1)
        shop = ShopifyConnection.objects.create(shop_domain='images.myshopify.com')
        mapping = ShopifyProductMapping.objects.create(connection=shop, product=self.product)
        media = ShopifyMediaMapping.objects.create(product_mapping=mapping, image=self.image,
            digest=self.image.digest, remote_file_gid='gid://shopify/MediaImage/123')
        self.client.force_login(self.staff)
        response = self.client.post(f'/admin/products/{self.product.pk}/images/', {
            'action': 'delete', 'image_id': self.image.pk, 'replacement_id': replacement.pk})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(ProductImage.objects.filter(pk=self.image.pk).exists())
        definition.refresh_from_db(); media.refresh_from_db(); replacement.refresh_from_db()
        self.assertIsNone(definition.image_id)
        self.assertIsNone(media.image_id)
        self.assertEqual(media.remote_file_gid, 'gid://shopify/MediaImage/123')
        self.assertTrue(replacement.is_main)
        self.assertIn('variant_review_required_or_stale', dry_run(self.product)['errors'])

    def test_description_is_escaped(self):
        self.product.description = '<script>bad()</script>\nText'
        self.assertEqual(dry_run(self.product)['payload']['descriptionHtml'], '<p>&lt;script&gt;bad()&lt;/script&gt;<br>Text</p>')

    def test_malformed_metadata_is_a_validation_error(self):
        self.product.metadata = {'source_variants': 3, 'source_options': {'bad': True}}
        errors = dry_run(self.product)['errors']
        self.assertIn('invalid_source_variants', errors)
        self.assertIn('invalid_source_options', errors)

    def test_review_with_same_product_instance_refreshes_approval(self):
        self.source(); self.definition()
        dry_run(self.product)
        approve_variant_review(self.product.pk, self.staff)
        self.assertEqual(dry_run(self.product)['errors'], [])

    def test_database_variant_identity_and_channel_constraints(self):
        self.definition()
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.definition()
        connection = ShopifyConnection.objects.create(shop_domain='channel.myshopify.com')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ShopifyOrderMapping.objects.create(connection=connection, remote_order_gid='1', sales_channel='website')

    def test_deleting_reviewed_definitions_cannot_silently_make_simple_product(self):
        definition = self.definition()
        approve_variant_review(self.product.pk, self.staff)
        definition.delete()
        report = dry_run(self.product)
        self.assertEqual(report['kind'], 'variant')
        self.assertIn('normalized_variants_required', report['errors'])

    def test_admin_review_and_preview_require_staff_access(self):
        self.definition()
        url = '/admin/system/shopify_integration/channelvariantdefinition/'
        self.assertEqual(self.client.get(url).status_code, 302)
        self.client.force_login(self.staff)
        selected = str(self.product.channel_variants.get().pk)
        with read_only_preview():
            response = self.client.post(url, {'action': 'preview', '_selected_action': [selected]})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['reports'][0]['dry_run'])
        self.assertTemplateUsed(response, 'admin/shopify_integration/base.html')
        self.assertContains(response, 'admin-sidebar')
        self.assertFalse(Order.objects.exists())
        self.assertFalse(IntegrationLog.objects.exists())

    def test_shopify_admin_screens_use_custom_layout(self):
        self.client.force_login(self.staff)
        for model in ('shopifycatalogueproduct', 'shopifyconnection', 'shopifysyncjob',
                      'shopifyordermapping', 'shopifywebhookreceipt', 'channelvariantdefinition'):
            with self.subTest(model=model):
                response = self.client.get('/admin/system/shopify_integration/' + model + '/')
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, 'admin/shopify_integration/base.html')
                self.assertContains(response, 'admin-sidebar')
                self.assertContains(response, 'shopify-workspace')
        response = self.client.get('/admin/system/shopify_integration/shopifyconnection/add/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'admin/shopify_integration/base.html')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.client.logout()
        self.assertEqual(self.client.get('/admin/system/shopify_integration/shopifyconnection/').status_code, 302)

    def test_staging_has_channel_and_no_operational_side_effects(self):
        connection = ShopifyConnection.objects.create(shop_domain='test.myshopify.com')
        mapping = ShopifyOrderMapping.objects.create(connection=connection, remote_order_gid='gid://shopify/Order/1')
        self.assertEqual(mapping.sales_channel, 'shopify')
        self.assertIsNone(mapping.order_id)
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
        with self.assertRaises(IntegrityError), transaction.atomic():
            ShopifyOrderMapping.objects.create(connection=connection, remote_order_gid=mapping.remote_order_gid)
        ShopifyWebhookReceipt.objects.create(connection=connection, delivery_id='delivery', topic='orders/create')
        with self.assertRaises(IntegrityError), transaction.atomic():
            ShopifyWebhookReceipt.objects.create(connection=connection, delivery_id='delivery', topic='orders/create')


@override_settings(SHOPIFY_ENABLED=True, SHOPIFY_SHOP_DOMAIN='test.myshopify.com',
                   SHOPIFY_API_VERSION='2026-10', SHOPIFY_ACCESS_TOKEN='secret-token', SHOPIFY_MAX_RETRIES=2)
class ClientTests(SimpleTestCase):
    def setUp(self):
        self.connection = ShopifyConnection(shop_domain='test.myshopify.com', enabled=True)
        self.client = ShopifyClient(self.connection)

    def response(self, value):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(value).encode()
        return response

    def test_query_uses_versioned_endpoint_and_token(self):
        self.client._opener.open = Mock(return_value=self.response({'data': {'shop': {'id': '1'}}}))
        self.assertEqual(self.client.query(SHOP_QUERY), {'shop': {'id': '1'}})
        request = self.client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://test.myshopify.com/admin/api/2026-10/graphql.json')
        self.assertIn('secret-token', request.headers.values())

    def test_mutations_and_mixed_documents_rejected_before_network(self):
        self.client._opener.open = Mock()
        for document in ('mutation { productDelete { id } }', SHOP_QUERY + ' mutation { x }'):
            with self.assertRaises(ShopifyError):
                self.client.query(document)
        with self.assertRaises(ShopifyError):
            self.client.mutate('anything')
        self.client._opener.open.assert_not_called()

    @override_settings(SHOPIFY_ENABLED=False)
    def test_disabled_by_default(self):
        with self.assertRaises(ImproperlyConfigured):
            ShopifyClient(self.connection)

    def test_domain_mismatch_and_injection_rejected(self):
        for domain in ('other.myshopify.com', 'test.myshopify.com/evil', 'https://test.myshopify.com', 'localhost'):
            self.connection.shop_domain = domain
            with self.assertRaises(ImproperlyConfigured):
                ShopifyClient(self.connection)

    @override_settings(SHOPIFY_ACCESS_TOKEN='', SHOPIFY_CLIENT_ID='client', SHOPIFY_CLIENT_SECRET='private')
    def test_client_credentials_cached_only_in_memory(self):
        with patch.object(self.client, '_post', return_value={'access_token': 'short-lived', 'expires_in': 86399}) as post:
            self.assertEqual(self.client.access_token(), 'short-lived')
            self.assertEqual(self.client.access_token(), 'short-lived')
            self.assertEqual(post.call_count, 1)
            self.client._expires_at = 0
            self.client.access_token()
            self.assertEqual(post.call_count, 2)

    @patch('shopify_integration.client.time.sleep')
    def test_http_429_and_transport_errors_retried(self, sleep):
        self.client._opener.open = Mock(side_effect=[
            HTTPError('https://test', 429, 'limited', {'Retry-After': '1'}, None),
            URLError('private provider body'), self.response({'data': {'shop': {}}})])
        self.assertEqual(self.client.query(SHOP_QUERY), {'shop': {}})
        self.assertEqual(sleep.call_count, 2)

    @patch('shopify_integration.client.time.sleep')
    def test_graphql_throttle_and_errors_are_sanitized(self, sleep):
        self.client._opener.open = Mock(side_effect=[
            self.response({'errors': [{'message': 'secret', 'extensions': {'code': 'THROTTLED'}}]}),
            self.response({'data': {'shop': {}}})])
        self.assertEqual(self.client.query(SHOP_QUERY), {'shop': {}})
        sleep.assert_called_once()
        self.client._opener.open = Mock(return_value=self.response({'errors': [{'message': 'secret-token'}]}))
        with self.assertRaisesMessage(ShopifyError, 'graphql_error'):
            self.client.query(SHOP_QUERY)

    def test_auth_failure_not_retried_or_leaked(self):
        self.client._opener.open = Mock(side_effect=HTTPError('https://test', 401, 'secret-token', {}, None))
        with self.assertRaisesMessage(ShopifyError, 'http_401'):
            self.client.query(SHOP_QUERY)
        self.assertEqual(self.client._opener.open.call_count, 1)

    def test_invalid_response_rejected(self):
        self.client._opener.open = Mock(return_value=self.response(['bad']))
        with self.assertRaisesMessage(ShopifyError, 'invalid_response'):
            self.client.query(SHOP_QUERY)
