import os
import shutil
import subprocess
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch
from django.conf import settings
from django.test import override_settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from catalog.models import Category, Product, Order
from delivery.models import WeightBand


@skipUnless(os.environ.get('RUN_ORDER_BROWSER_TESTS')=='1','Optional Edge order flow')
@override_settings(STRIPE_SECRET_KEY='sk_test_browser_only',STRIPE_WEBHOOK_SECRET='whsec_browser_test')
class OrderBrowserTests(StaticLiveServerTestCase):
    def test_guest_order_flow(self):
        category=Category.objects.create(name='Browser order category',slug='browser-order-category')
        grams=Product.objects.create(name='Browser grams',slug='browser-grams',category=category,regular_price=4,
            stock=100,stock_confirmed=True,is_published=True)
        kilos=Product.objects.create(name='Browser kilograms',slug='browser-kilograms',category=category,regular_price=6,
            weight='0.5',weight_unit='kg',stock=100,stock_confirmed=True,is_published=True)
        WeightBand.objects.create(max_weight_grams=300,charge='2.50')
        WeightBand.objects.create(max_weight_grams=2000,charge='5.00')
        with patch('orders.payments.client') as gateway, patch('orders.tasks.dispatch_pending.apply_async'):
            gateway.return_value.v1.checkout.sessions.create.side_effect=lambda **kwargs:SimpleNamespace(
                id='cs_browser_test',url=self.live_server_url+'/track-order/?order='+kwargs['params']['metadata']['order_id'])
            result=subprocess.run([shutil.which('node') or 'node',str(settings.BASE_DIR/'tools/delivery_smoke.cjs')],
                env={**os.environ,'DELIVERY_TEST_URL':self.live_server_url,'DELIVERY_GRAMS_PRODUCT':str(grams.pk),
                     'DELIVERY_KILOS_PRODUCT':str(kilos.pk),'ORDER_BROWSER_FLOW':'1'},
                capture_output=True,text=True,timeout=100)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual(Order.objects.count(),1)
        order=Order.objects.get();self.assertIsNone(order.customer_id);self.assertEqual(order.payment_status,'paid')
        grams.refresh_from_db();self.assertEqual(grams.stock,98)
