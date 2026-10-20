from concurrent.futures import ThreadPoolExecutor
from unittest import skipUnless
from django.db import connection, close_old_connections, DatabaseError, transaction
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from .models import Category, Product, StockAudit
from .services import adjust_stock, reserve_order


@skipUnless(connection.vendor == 'postgresql', 'Requires real PostgreSQL row locks and audit trigger')
class PostgreSQLInventoryTests(TransactionTestCase):
    def test_simultaneous_orders_cannot_oversell(self):
        category = Category.objects.create(name='Concurrency category', slug='concurrency-category')
        product = Product.objects.create(name='Last unit', slug='last-unit', category=category,
                                         regular_price=10, is_published=True)
        buyers = [get_user_model().objects.create_user(f'buyer-{i}') for i in range(2)]
        adjust_stock(product.pk, 1, reason='Initial count', actor=buyers[0], key='initial', kind='initial')
        def buy(pk):
            close_old_connections()
            try:
                buyer = get_user_model().objects.get(pk=pk)
                reserve_order(buyer, [{'product_id':product.pk,'quantity':1}], f'checkout-{pk}')
                return True
            except ValidationError:
                return False
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(buy, [buyer.pk for buyer in buyers]))
        self.assertEqual(sum(results), 1)
        product.refresh_from_db()
        self.assertEqual(product.stock, 0)
        self.assertEqual(StockAudit.objects.filter(adjustment_type='order').count(), 1)
        with self.assertRaises(DatabaseError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("UPDATE catalog_stockaudit SET reason = 'tampered'")
