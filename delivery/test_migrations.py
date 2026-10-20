from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ExistingProductWeightMigrationTests(TransactionTestCase):
    def test_existing_product_receives_150_grams_without_price_or_stock_changes(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [('catalog', '0007_product_display_order_product_rating_and_more')]
        try:
            executor.migrate(before)
            old_apps = executor.loader.project_state(before).apps
            Product = old_apps.get_model('catalog', 'Product')
            existing = Product.objects.create(
                name='Existing migration product', slug='existing-migration-product',
                regular_price=Decimal('4.25'), stock=17, stock_confirmed=True,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            new_apps = executor.loader.project_state(latest).apps
            product = new_apps.get_model('catalog', 'Product').objects.get(pk=existing.pk)
            self.assertEqual(product.weight, Decimal('150'))
            self.assertEqual(product.weight_unit, 'g')
            self.assertEqual(product.regular_price, Decimal('4.25'))
            self.assertEqual(product.stock, 17)
            self.assertTrue(product.stock_confirmed)
        finally:
            MigrationExecutor(connection).migrate(latest)
