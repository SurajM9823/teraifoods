import os
import shutil
import subprocess
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from catalog.models import Category, Product
from .models import WeightBand


@skipUnless(os.environ.get('RUN_DELIVERY_BROWSER_TESTS') == '1', 'Optional Edge browser check')
class DeliveryBrowserTests(StaticLiveServerTestCase):
    def test_existing_cart_displays_weight_based_delivery(self):
        category = Category.objects.create(name='Delivery browser category', slug='delivery-browser-category')
        grams = Product.objects.create(name='Browser grams', slug='browser-grams', category=category,
            regular_price='4.00', stock=100, stock_confirmed=True, is_published=True)
        kilos = Product.objects.create(name='Browser kilograms', slug='browser-kilograms', category=category,
            regular_price='6.00', weight='0.5', weight_unit='kg',
            stock=100, stock_confirmed=True, is_published=True)
        WeightBand.objects.create(max_weight_grams=300, charge='2.50')
        WeightBand.objects.create(max_weight_grams=2000, charge='5.00')
        result = subprocess.run(
            [shutil.which('node') or 'node', str(settings.BASE_DIR / 'tools/delivery_smoke.cjs')],
            env={**os.environ, 'DELIVERY_TEST_URL':self.live_server_url,
                 'DELIVERY_GRAMS_PRODUCT':str(grams.pk), 'DELIVERY_KILOS_PRODUCT':str(kilos.pk)},
            capture_output=True, text=True, timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
