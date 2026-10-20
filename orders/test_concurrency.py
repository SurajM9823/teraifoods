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
