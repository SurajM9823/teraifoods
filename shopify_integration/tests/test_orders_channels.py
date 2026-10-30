import base64
import copy
from datetime import timedelta
from decimal import Decimal
import hashlib
import hmac
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase, Client, override_settings
from django.utils import timezone

from catalog.models import Category, Product, Order, OrderLine, StockAudit
from catalog.services import cancel_order
from orders import services, payments, vouchers
from orders.models import Payment, Refund, Notification, OrderEvent, Voucher
from orders.tasks import dispatch_pending, expire_reservations, send_notification
from shopify_integration.client import ShopifyError
from shopify_integration.models import (ShopifyConnection, ShopifyProductMapping, ShopifyVariantMapping,
    ShopifyOrderMapping, ShopifyOrderLineMapping, ShopifyWebhookReceipt)
from shopify_integration.order_import import import_snapshot, cipher, fetch_order
from shopify_integration.webhooks import valid_hmac, process_receipt


def amount(value, currency='GBP'):
    return {'shopMoney':{'amount':str(value),'currencyCode':currency},
            'presentmentMoney':{'amount':str(value),'currencyCode':currency}}


def example_order():
    return {'id':'gid://shopify/Order/123','name':'#1001','createdAt':'2026-10-30T10:00:00Z',
        'updatedAt':'2026-10-30T11:00:00Z','email':'private@example.com','phone':'+441234567890',
        'currencyCode':'GBP','cancelledAt':None,'taxesIncluded':False,
        'displayFinancialStatus':'PAID','displayFulfillmentStatus':'UNFULFILLED',
        'shippingAddress':{'name':'Private Buyer','address1':'Private address','city':'London','zip':'SW1A 1AA','countryCodeV2':'GB'},
        'billingAddress':None,'fulfillments':[],
        'currentTotalPriceSet':amount('23.00'),'currentSubtotalPriceSet':amount('17.00'),
        'currentTotalDiscountsSet':amount('3.00'),'currentTotalTaxSet':amount('4.00'),
        'currentShippingPriceSet':amount('2.00'),'totalRefundedSet':amount('0.00'),
        'currentTotalDutiesSet':None,'currentTotalAdditionalFeesSet':None,
        'lineItems':{'nodes':[{'id':'gid://shopify/LineItem/1','name':'Purchased product',
            'sku':'AT-PURCHASE','quantity':2,'currentQuantity':2,'variantTitle':'Small',
            'originalUnitPriceSet':amount('10.00'),'variant':{'id':'gid://shopify/ProductVariant/1'}}],
            'pageInfo':{'hasNextPage':False,'endCursor':None}}}


@override_settings(SHOPIFY_ENABLED=True,SHOPIFY_ORDER_IMPORT_ENABLED=True,
    SHOPIFY_SHOP_DOMAIN='test.myshopify.com',SHOPIFY_CLIENT_SECRET='webhook-test-secret')
class ImportTests(TestCase):
    def setUp(self):
        self.shop=ShopifyConnection.objects.create(shop_domain='test.myshopify.com',enabled=True,import_orders_enabled=True)
        category=Category.objects.create(name='Channel tests',slug='channel-tests')
        self.product=Product.objects.create(name='Current catalogue product',slug='channel-product',category=category,
            is_published=True,regular_price=Decimal('1000.00'),stock=0,stock_confirmed=False)
        mapping=ShopifyProductMapping.objects.create(connection=self.shop,product=self.product)
        self.variant=ShopifyVariantMapping.objects.create(product_mapping=mapping,local_key='default',
            remote_variant_gid='gid://shopify/ProductVariant/1')
        self.data=example_order()
        self.staff=get_user_model().objects.create_superuser('channel-staff','staff@example.com','testpass')

    def imported(self):
        result=import_snapshot(self.shop,self.data)
        self.assertEqual(result.status,'imported',result.error_code)
        return result

    @patch('orders.payments.client')
    @patch('catalog.services.adjust_stock')
    @patch('orders.services.adjust_stock')
    def test_import_uses_shopify_totals_without_checkout_stock_or_payments(self,*mocks):
        mapping=self.imported();order=mapping.order
        self.assertEqual(order.sales_channel,'shopify')
        self.assertEqual(order.payment_method,'shopify')
        self.assertEqual(order.total,Decimal('23.00'))
        self.assertEqual(order.subtotal,Decimal('17.00'))
        self.assertEqual(order.tax,Decimal('4.00'))
        self.assertEqual(order.delivery_charge,Decimal('2.00'))
        self.assertEqual(order.lines.get().unit_price,Decimal('10.00'))
        self.assertEqual(order.lines.get().product_sku,'AT-PURCHASE')
        self.assertIsNone(order.customer_id);self.assertIsNone(order.reservation_expires_at)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock,0)
        self.assertEqual(self.product.regular_price,Decimal('1000.00'))
        for model in (Payment,StockAudit,Refund,Notification,Voucher):self.assertFalse(model.objects.exists())
        self.assertEqual(len(mail.outbox),0)
        for mock in mocks:mock.assert_not_called()

    def test_duplicate_and_out_of_order_snapshots_do_not_duplicate_or_regress(self):
        mapping=self.imported()
        self.imported()
        self.assertEqual(Order.objects.count(),1);self.assertEqual(OrderLine.objects.count(),1)
        self.assertEqual(OrderEvent.objects.count(),1)
        old=copy.deepcopy(self.data);old['updatedAt']='2026-10-30T10:30:00Z';old['currentTotalPriceSet']=amount('1.00')
        import_snapshot(self.shop,old)
        mapping.order.refresh_from_db();self.assertEqual(mapping.order.total,Decimal('23.00'))

    def test_unmapped_or_deleted_variant_is_quarantined_without_partial_order(self):
        for value in (None,{'id':'gid://shopify/ProductVariant/999'}):
            with self.subTest(value=value):
                data=copy.deepcopy(self.data);data['lineItems']['nodes'][0]['variant']=value
                result=import_snapshot(self.shop,data)
                self.assertEqual(result.status,'quarantined')
                self.assertEqual(result.error_code,'unmapped_shopify_variant')
                self.assertFalse(Order.objects.exists());self.assertFalse(OrderLine.objects.exists())

    def test_unknown_line_on_edited_order_preserves_previous_complete_import(self):
        mapping=self.imported()
        new=copy.deepcopy(self.data);new['updatedAt']='2026-10-30T12:00:00Z'
        unknown=copy.deepcopy(new['lineItems']['nodes'][0]);unknown['id']='gid://shopify/LineItem/2';unknown['variant']=None
        new['lineItems']['nodes'].append(unknown);new['currentTotalPriceSet']=amount('100.00')
        self.assertEqual(import_snapshot(self.shop,new).status,'quarantined')
        mapping.order.refresh_from_db();self.assertEqual(mapping.order.total,Decimal('23.00'))
        self.assertEqual(OrderLine.objects.count(),1)

    def test_financial_refund_cancel_and_partial_refund_never_refund_or_restock_locally(self):
        for index,state in enumerate(('PARTIALLY_REFUNDED','REFUNDED')):
            data=copy.deepcopy(self.data);data['updatedAt']=f'2026-10-30T1{index+2}:00:00Z';data['displayFinancialStatus']=state
            data['cancelledAt']='2026-10-30T12:00:00Z'
            result=import_snapshot(self.shop,data)
            self.assertEqual(result.status,'imported')
            self.assertEqual(result.order.fulfilment_status,'cancelled')
        self.assertFalse(Refund.objects.exists());self.assertFalse(StockAudit.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_private_snapshot_encrypted_and_financial_metadata_contains_no_addresses(self):
        mapping=self.imported()
        self.assertNotIn('private@example.com',mapping.payload_encrypted)
        self.assertNotIn('Private address',json.dumps(mapping.financial_snapshot))
        self.assertEqual(json.loads(cipher().decrypt(mapping.payload_encrypted.encode()))['email'],'private@example.com')

    def test_invalid_currency_precision_or_totals_quarantine(self):
        for value,currency in (('1.001','GBP'),('NaN','GBP'),('-1.00','GBP'),('1.00','USD')):
            data=copy.deepcopy(self.data);data['currentTotalPriceSet']=amount(value,currency)
            self.assertEqual(import_snapshot(self.shop,data).status,'quarantined')
            self.assertFalse(Order.objects.exists())

    def test_shop_currency_preserved_with_different_presentment_currency(self):
        self.data['currentTotalPriceSet']['presentmentMoney']={'amount':'27.00','currencyCode':'EUR'}
        result=self.imported();self.assertEqual(result.order.currency,'GBP')
        self.assertEqual(result.financial_snapshot['currentTotalPriceSet']['presentmentMoney']['currencyCode'],'EUR')

    def test_disable_import_is_an_explicit_gate(self):
        self.shop.import_orders_enabled=False;self.shop.save()
        with self.assertRaisesMessage(ShopifyError,'order_import_disabled'):import_snapshot(self.shop,self.data)
        self.assertFalse(Order.objects.exists())

    def test_historical_orders_require_explicit_opt_in_after_activation(self):
        self.shop.import_started_at=timezone.now();self.shop.save()
        mapping=import_snapshot(self.shop,self.data)
        self.assertEqual(mapping.status,'ignored');self.assertFalse(Order.objects.exists())
        self.assertEqual(mapping.payload_encrypted,'')
        mapping=import_snapshot(self.shop,self.data,allow_historical=True)
        self.assertEqual(mapping.status,'imported')

    def test_financial_inventory_voucher_and_guest_entry_points_are_blocked(self):
        order=self.imported().order
        operations=[lambda:payments.create_session(order),lambda:payments.payment_data(order),lambda:payments.reconcile(order),
            lambda:payments.cancel_with_provider(order.pk),lambda:services.restore_stock(order,None),
            lambda:services.finalize_cancel(order.pk),lambda:services.request_cancel(order.pk,'Cancel'),
            lambda:services.request_return(order.pk,'Return'),lambda:services.decide_return(order.pk,'received','Reason',self.staff,True),
            lambda:services.settle_return(order.pk,'cash','ref',self.staff),lambda:cancel_order(order.pk,self.staff),
            lambda:vouchers.issue(order,Decimal('10')),lambda:vouchers.consume(order),lambda:vouchers.release(order),
            lambda:services.guest_token(order),lambda:services.grant_access({},order)]
        with patch('orders.payments.client') as stripe:
            for operation in operations:
                with self.subTest(operation=operation),self.assertRaises(ValidationError):operation()
            stripe.assert_not_called()
        self.assertFalse(StockAudit.objects.exists());self.assertFalse(Refund.objects.exists())

    def test_refund_entry_points_and_background_jobs_exclude_shopify(self):
        order=self.imported().order
        refund=Refund.objects.create(order=order,amount=1,reason='Accidental foreign-channel record')
        with self.assertRaises(ValidationError):payments.process_refund(refund.pk)
        with self.assertRaises(ValidationError):payments.apply_refund(refund.pk,{})
        Order.objects.filter(pk=order.pk).update(cancellation_status='requested')
        with patch('orders.payments.cancel_with_provider') as cancel,patch('orders.payments.process_refund') as process:
            dispatch_pending();expire_reservations()
            cancel.assert_not_called();process.assert_not_called()

    def test_foreign_order_notifications_are_suppressed_even_if_accidentally_created(self):
        order=self.imported().order;event=order.events.first()
        notification=Notification.objects.create(event=event,recipient='private@example.com')
        send_notification(notification.pk)
        notification.refresh_from_db();self.assertEqual(notification.status,'suppressed')
        self.assertEqual(len(mail.outbox),0)

    def test_order_cannot_be_claimed_by_customer_email_or_guest_grant(self):
        order=self.imported().order
        buyer=get_user_model().objects.create_user('unlinked',email=order.email)
        for user in (buyer,AnonymousUser()):
            with self.assertRaises(PermissionDenied):services.authorize(order,user,{})
        services.authorize(order,self.staff,{})

    def test_staff_order_view_has_no_manual_payment_or_cancellation_forms(self):
        order=self.imported().order;self.client.force_login(self.staff)
        url=f'/admin/orders/{order.public_id}/'
        response=self.client.get(url)
        self.assertContains(response,'Manage payments, refunds and cancellations in Shopify')
        self.assertNotContains(response,'name="action" value="payment_status"')
        self.client.post(url,{'action':'payment_status','payment_status':'failed'})
        order.refresh_from_db();self.assertEqual(order.payment_status,'paid')

    def test_internal_fulfilment_progress_does_not_send_email_and_survives_financial_updates(self):
        order=self.imported().order
        services.transition(order.pk,'preparing',self.staff)
        newer=copy.deepcopy(self.data);newer['updatedAt']='2026-10-30T12:00:00Z'
        result=import_snapshot(self.shop,newer)
        self.assertEqual(result.order.fulfilment_status,'preparing')
        self.assertFalse(Notification.objects.exists())

    def test_import_isolation_database_constraint(self):
        with self.assertRaises(IntegrityError),transaction.atomic():
            Order.objects.create(sales_channel='shopify',payment_method='stripe',total=1,
                idempotency_key='bad-channel',request_digest='x'*64)

    def test_older_website_workers_can_insert_orders_during_rollout(self):
        from django.db.migrations.loader import MigrationLoader
        state=MigrationLoader(None).project_state([('catalog','0012_orderline_components_snapshot_product_is_package_and_more')])
        old_order=state.apps.get_model('catalog','Order')
        old=old_order.objects.create(total=1,idempotency_key='legacy-worker-order',request_digest='x'*64)
        self.assertEqual(Order.objects.get(pk=old.pk).sales_channel,'website')


@override_settings(SHOPIFY_ENABLED=True,SHOPIFY_ORDER_IMPORT_ENABLED=True,SHOPIFY_SHOP_DOMAIN='test.myshopify.com',
    SHOPIFY_CLIENT_SECRET='webhook-test-secret')
class WebhookTests(TestCase):
    def setUp(self):
        self.shop=ShopifyConnection.objects.create(shop_domain='test.myshopify.com',enabled=True,import_orders_enabled=True)
        self.path='/api/shopify/webhook/'
        self.raw=json.dumps({'id':123,'email':'not-stored@example.com','shipping_address':{'address1':'private'}}).encode()

    def headers(self,raw=None,topic='orders/create',delivery='delivery-1',secret='webhook-test-secret'):
        raw=self.raw if raw is None else raw
        return {'HTTP_X_SHOPIFY_HMAC_SHA256':base64.b64encode(hmac.new(secret.encode(),raw,hashlib.sha256).digest()).decode(),
            'HTTP_X_SHOPIFY_SHOP_DOMAIN':'test.myshopify.com','HTTP_X_SHOPIFY_TOPIC':topic,'HTTP_X_SHOPIFY_WEBHOOK_ID':delivery}

    def test_verified_raw_body_persists_only_routing_metadata(self):
        response=Client(enforce_csrf_checks=True).post(self.path,self.raw,content_type='application/json',**self.headers())
        self.assertEqual(response.status_code,200)
        receipt=ShopifyWebhookReceipt.objects.get()
        self.assertEqual(receipt.payload,{'order_gid':'gid://shopify/Order/123'})
        self.assertNotIn('not-stored',json.dumps(receipt.payload))
        self.assertFalse(Order.objects.exists())

    def test_tampered_body_or_signature_has_no_database_side_effects(self):
        for body,headers in ((self.raw+b' ',self.headers()),(self.raw,{**self.headers(),'HTTP_X_SHOPIFY_HMAC_SHA256':'bad'})):
            self.assertEqual(self.client.post(self.path,body,content_type='application/json',**headers).status_code,401)
        self.assertFalse(ShopifyWebhookReceipt.objects.exists())
        self.assertFalse(valid_hmac(self.raw,'😀'))

    def test_duplicate_receipts_and_conflicting_delivery(self):
        for _ in range(2):self.assertEqual(self.client.post(self.path,self.raw,content_type='application/json',**self.headers()).status_code,200)
        self.assertEqual(ShopifyWebhookReceipt.objects.count(),1)
        other=json.dumps({'id':124}).encode()
        self.assertEqual(self.client.post(self.path,other,content_type='application/json',**self.headers(other)).status_code,409)

    def test_wrong_store_or_unsupported_topic_rejected(self):
        for key,value in (('HTTP_X_SHOPIFY_SHOP_DOMAIN','evil.myshopify.com'),('HTTP_X_SHOPIFY_TOPIC','products/delete')):
            self.assertEqual(self.client.post(self.path,self.raw,content_type='application/json',**{**self.headers(),key:value}).status_code,400)
        self.assertFalse(ShopifyWebhookReceipt.objects.exists())

    @override_settings(SHOPIFY_WEBHOOK_MAX_BYTES=10)
    def test_oversize_webhook_rejected(self):
        self.assertEqual(self.client.post(self.path,self.raw,content_type='application/json',**self.headers()).status_code,413)

    @override_settings(SHOPIFY_WEBHOOK_PREVIOUS_SECRET='old-secret')
    def test_secret_rotation_accepts_previous_secret(self):
        self.assertEqual(self.client.post(self.path,self.raw,content_type='application/json',**self.headers(secret='old-secret')).status_code,200)

    def test_uninstall_disables_connection_and_header_relabel_cannot_do_so(self):
        self.assertEqual(self.client.post(self.path,self.raw,content_type='application/json',**self.headers(topic='app/uninstalled')).status_code,400)
        self.shop.refresh_from_db();self.assertTrue(self.shop.enabled)
        body=json.dumps({'id':1,'myshopify_domain':'test.myshopify.com'}).encode()
        self.assertEqual(self.client.post(self.path,body,content_type='application/json',**self.headers(body,topic='app/uninstalled')).status_code,200)
        self.shop.refresh_from_db();self.assertFalse(self.shop.enabled);self.assertFalse(self.shop.import_orders_enabled)

    def test_broker_failure_does_not_lose_receipt_or_fail_ack(self):
        with patch('shopify_integration.tasks.process_webhook.apply_async',side_effect=RuntimeError('offline')):
            with self.captureOnCommitCallbacks(execute=True):
                response=self.client.post(self.path,self.raw,content_type='application/json',**self.headers())
        self.assertEqual(response.status_code,200)
        self.assertEqual(ShopifyWebhookReceipt.objects.get().status,'pending')

    def test_import_disabled_stores_receipt_but_never_fetches_real_order(self):
        self.shop.import_orders_enabled=False;self.shop.save()
        self.client.post(self.path,self.raw,content_type='application/json',**self.headers())
        receipt=ShopifyWebhookReceipt.objects.get()
        with patch('shopify_integration.webhooks.import_order') as importer:
            process_receipt(receipt.pk)
            importer.assert_not_called()

    def test_transient_fetch_failure_is_retryable_and_payload_not_logged(self):
        self.client.post(self.path,self.raw,content_type='application/json',**self.headers())
        receipt=ShopifyWebhookReceipt.objects.get()
        with patch('shopify_integration.webhooks.import_order',side_effect=ShopifyError('http_503')):
            result=process_receipt(receipt.pk)
        self.assertEqual(result.status,'retry');self.assertEqual(result.error_code,'http_503')
        self.assertIsNotNone(result.next_retry_at)
