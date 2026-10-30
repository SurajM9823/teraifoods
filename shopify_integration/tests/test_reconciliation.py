import copy
from datetime import timedelta
from unittest.mock import Mock,patch
from django.test import TestCase,override_settings
from django.utils import timezone
from shopify_integration.client import ShopifyError
from shopify_integration.models import ShopifyConnection,ShopifyOrderMapping,ShopifyWebhookReceipt,ShopifySyncJob
from shopify_integration.order_import import fetch_order,reconcile
from shopify_integration.setup import setup_webhooks
from shopify_integration.tasks import expire_private_snapshots
from shopify_integration.graphql import SCOPES_QUERY,WEBHOOKS_QUERY,WEBHOOK_CREATE,ORDERS_QUERY
from .test_orders_channels import example_order


@override_settings(SHOPIFY_ENABLED=True,SHOPIFY_ORDER_IMPORT_ENABLED=True,
    SHOPIFY_SHOP_DOMAIN='test.myshopify.com',ORDER_PUBLIC_ORIGIN='https://store.example.com')
class ReconciliationTests(TestCase):
    def setUp(self):
        self.shop=ShopifyConnection.objects.create(shop_domain='test.myshopify.com',enabled=True,import_orders_enabled=True)

    def test_line_pagination_fetches_complete_snapshot_and_rejects_mid_fetch_edits(self):
        first=example_order();first['lineItems']['pageInfo']={'hasNextPage':True,'endCursor':'next'}
        second=example_order();second['lineItems']['nodes'][0]['id']='gid://shopify/LineItem/2'
        api=Mock();api.query.side_effect=[{'order':first},{'order':second}]
        self.assertEqual(len(fetch_order(api,first['id'])['lineItems']['nodes']),2)
        first=example_order();first['lineItems']['pageInfo']={'hasNextPage':True,'endCursor':'next'}
        second=example_order();second['updatedAt']='2026-10-30T12:00:00Z'
        api.query.side_effect=[{'order':first},{'order':second}]
        with self.assertRaisesMessage(ShopifyError,'order_changed_during_fetch'):fetch_order(api,first['id'])

    def test_reconciliation_does_not_advance_cursor_when_fetch_fails(self):
        start=timezone.now()-timedelta(hours=1)
        self.shop.order_sync_cursor=start;self.shop.save()
        api=Mock();api.query.return_value={'orders':{'nodes':[{'id':'gid://shopify/Order/123'}],
            'pageInfo':{'hasNextPage':False,'endCursor':None}}}
        with patch('shopify_integration.order_import.ShopifyClient',return_value=api),patch(
            'shopify_integration.order_import.fetch_order',side_effect=ShopifyError('http_503')):
            with self.assertRaises(ShopifyError):reconcile(self.shop)
        self.shop.refresh_from_db();self.assertEqual(self.shop.order_sync_cursor,start)

    def test_reconciliation_pagination_window_is_persisted(self):
        api=Mock();api.query.return_value={'orders':{'nodes':[], 'pageInfo':{'hasNextPage':True,'endCursor':'page-two'}}}
        with patch('shopify_integration.order_import.ShopifyClient',return_value=api):reconcile(self.shop)
        self.shop.refresh_from_db()
        self.assertEqual(self.shop.order_sync_after,'page-two');self.assertIsNotNone(self.shop.order_sync_window_end)
        end=self.shop.order_sync_window_end
        api.query.return_value={'orders':{'nodes':[], 'pageInfo':{'hasNextPage':False,'endCursor':None}}}
        with patch('shopify_integration.order_import.ShopifyClient',return_value=api):reconcile(self.shop)
        self.shop.refresh_from_db();self.assertEqual(self.shop.order_sync_cursor,end)
        self.assertEqual(self.shop.order_sync_after,'')

    def test_webhook_setup_plan_is_read_only_and_existing_subscriptions_are_reused(self):
        api=Mock()
        def query(document,variables=None):
            if document==SCOPES_QUERY:return {'currentAppInstallation':{'accessScopes':[{'handle':'read_orders'}]}}
            return {'webhookSubscriptions':{'nodes':[{'id':'1','topic':'ORDERS_CREATE','uri':'https://store.example.com/api/shopify/webhook/'}],
                'pageInfo':{'hasNextPage':False,'endCursor':None}}}
        api.query.side_effect=query
        with patch('shopify_integration.setup.ShopifyClient',return_value=api):
            plan=setup_webhooks(self.shop)
            api.mutate.assert_not_called()
            self.assertEqual(plan[0]['action'],'unchanged')
            setup_webhooks(self.shop,apply=True)
            self.assertEqual(api.mutate.call_count,5)
            self.assertTrue(all(call.args[0]==WEBHOOK_CREATE for call in api.mutate.call_args_list))

    def test_snapshot_retention_removes_private_extra_copy_not_operational_order(self):
        old=timezone.now()-timedelta(days=91)
        mapping=ShopifyOrderMapping.objects.create(connection=self.shop,remote_order_gid='gid://shopify/Order/123',
            payload_encrypted='encrypted-old-data',snapshot_saved_at=old)
        receipt=ShopifyWebhookReceipt.objects.create(connection=self.shop,delivery_id='old',topic='orders/create',status='processed',processed_at=old)
        expire_private_snapshots()
        mapping.refresh_from_db();self.assertEqual(mapping.payload_encrypted,'')
        self.assertFalse(ShopifyWebhookReceipt.objects.filter(pk=receipt.pk).exists())
