from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from unittest.mock import patch
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.db import connection, close_old_connections
from django.test import TransactionTestCase
from catalog.models import Category, Product, Order
from delivery.models import WeightBand
from .services import create_order


@skipUnless(connection.vendor=='postgresql','Requires PostgreSQL row locks')
class GuestCheckoutConcurrencyTests(TransactionTestCase):
    def setUp(self):
        category=Category.objects.create(name='Guest concurrency',slug='guest-concurrency')
        self.product=Product.objects.create(name='One unit',slug='one-unit',category=category,regular_price=4,
            stock=1,stock_confirmed=True,is_published=True)
        WeightBand.objects.create(max_weight_grams=1000,charge=2)
        self.body={'email':'guest@example.com','address':{'name':'Concurrent Guest','phone':'07700900123',
            'line1':'1 Test Street','city':'London','postcode':'SW1A1AA'},
            'items':[{'product_id':self.product.pk,'quantity':1}]}

    def buy(self,key):
        close_old_connections()
        try:
            return create_order(AnonymousUser(),'same-session',self.body,key).pk
        except ValidationError:
            return None
        finally:
            close_old_connections()

    @patch('orders.tasks.dispatch_pending.apply_async')
    def test_two_guests_cannot_buy_last_unit(self,queue):
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(self.buy,['first','second']))
        self.assertEqual(len([r for r in result if r]),1)
        self.assertEqual(Order.objects.count(),1)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,0)

    @patch('orders.tasks.dispatch_pending.apply_async')
    def test_concurrent_retry_is_same_order(self,queue):
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(self.buy,['same','same']))
        self.assertIsNotNone(result[0]);self.assertEqual(result[0],result[1])
        self.assertEqual(Order.objects.count(),1)

    @patch('orders.tasks.dispatch_pending.apply_async')
    def test_same_voucher_cannot_fund_two_concurrent_orders(self,queue):
        from .vouchers import issue
        self.product.stock=20;self.product.save()
        source=create_order(AnonymousUser(),'source',self.body,'source')
        voucher=issue(source,10)
        self.body['voucher_code']=voucher.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(self.buy,['first','second']))
        self.assertEqual(len([r for r in result if r]),1)
        voucher.refresh_from_db();self.assertIsNotNone(voucher.redeemed_at)
        self.assertEqual(Order.objects.count(),2)

    @patch('orders.tasks.dispatch_pending.apply_async')
    def test_package_and_regular_purchase_compete_for_same_stock(self,queue):
        from catalog.models import Package,PackageItem
        product=Product.objects.create(name='Single package',slug='single-package',category=self.product.category,
            regular_price=4,is_package=True,is_published=True,stock_confirmed=True)
        package=Package.objects.create(product=product,slot=1)
        PackageItem.objects.create(package=package,product=self.product,quantity=1)
        def buy_package(key):
            close_old_connections()
            try:
                body={**self.body,'items':[{'product_id':product.pk if key=='package' else self.product.pk,'quantity':1}]}
                return create_order(AnonymousUser(),key,body,key).pk
            except ValidationError:
                return None
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            result=list(pool.map(buy_package,['package','regular']))
        self.assertEqual(len([r for r in result if r]),1)
        self.product.refresh_from_db();self.assertEqual(self.product.stock,0)

    @patch('orders.tasks.dispatch_pending.apply_async')
    def test_duplicate_payment_and_refund_webhooks_serialize(self, queue):
        from .models import ProviderEvent, Refund
        from .payments import apply_event
        order = create_order(AnonymousUser(), 'webhook-race', self.body, 'webhook-race')
        event = {'id': 'evt_race_paid', 'type': 'checkout.session.completed', 'livemode': False,
                 'data': {'object': {'id': 'cs_test_race', 'metadata': {'order_id': str(order.public_id)},
                     'payment_status': 'paid', 'amount_total': int(order.total * 100),
                     'currency': 'gbp', 'payment_intent': 'pi_race'}}}

        def deliver(payload):
            close_old_connections()
            try:
                apply_event(payload)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(deliver, [event, event]))
        self.assertEqual(order.events.filter(event_type='payment_confirmed').count(), 1)
        Refund.objects.create(order=order, amount=order.total, reason='Concurrent refund')
        event = {'id': 'evt_race_refund', 'type': 'refund.updated', 'livemode': False,
                 'data': {'object': {'id': 're_race', 'metadata': {'order_id': str(order.public_id)},
                     'status': 'succeeded', 'amount': int(order.total * 100),
                     'currency': 'gbp', 'payment_intent': 'pi_race'}}}
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(deliver, [event, event]))
        self.assertEqual(order.events.filter(event_type='refund_succeeded').count(), 1)
        self.assertEqual(ProviderEvent.objects.count(), 2)
