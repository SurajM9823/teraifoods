import io
import json
from decimal import Decimal
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from catalog.models import Product, Category, Package, PackageItem, Order
from delivery.models import WeightBand
from . import services, payments, vouchers
from .models import Voucher, VoucherUse


@override_settings(DEBUG=True,ORDER_PAYMENT_MODE='demo',ORDER_RETURN_DAYS=0)
class VoucherPackageTests(TestCase):
    def setUp(self):
        self.staff=get_user_model().objects.create_superuser('package-admin','admin@example.invalid','test-pass')
        self.category=Category.objects.first()
        self.a=Product.objects.create(name='Rice',slug='voucher-rice',category=self.category,regular_price=4,stock=30,stock_confirmed=True,is_published=True)
        self.b=Product.objects.create(name='Flour',slug='voucher-flour',category=self.category,regular_price=3,stock=10,stock_confirmed=True,is_published=True,weight=500)
        WeightBand.objects.create(max_weight_grams=20000,charge=2)
        self.body={'email':'buyer@example.invalid','address':{'name':'Buyer','phone':'07700900123','line1':'1 Test Street','city':'London','postcode':'SW1A 1AA'},'items':[{'product_id':self.a.pk,'quantity':2}]}

    def order(self,key='one',body=None):
        return services.create_order(AnonymousUser(),'voucher-test',body or self.body,key)

    def voucher(self,amount=10):
        source=self.order('source')
        return vouchers.issue(source,Decimal(amount))

    def test_voucher_partial_full_and_surplus_are_single_use(self):
        code=self.voucher(6)
        order=self.order(body={**self.body,'voucher_code':code.code})
        self.assertEqual(order.total,4);self.assertEqual(order.voucher_use.amount,6)
        with self.assertRaises(ValidationError):self.order('another',{**self.body,'voucher_code':code.code})
        self.assertEqual(self.order(body={**self.body,'voucher_code':code.code}).pk,order.pk)
        payments.confirm_demo(order.pk);code.refresh_from_db();self.assertIsNotNone(code.redeemed_at)
        with self.assertRaises(ValidationError):vouchers.validate(code.code,self.body['email'])

    def test_surplus_is_forfeited_and_zero_checkout_needs_no_stripe(self):
        code=self.voucher(50)
        with override_settings(DEBUG=False,ORDER_PAYMENT_MODE='stripe',STRIPE_SECRET_KEY=''):
            with patch('orders.payments.client') as client:
                response=self.client.post('/api/orders/checkout/',json.dumps({**self.body,'voucher_code':code.code}),content_type='application/json',HTTP_IDEMPOTENCY_KEY='full')
                self.assertEqual(response.status_code,201,response.content);client.assert_not_called()
        order=Order.objects.get(public_id=response.json()['order']['id'])
        self.assertEqual(order.total,0);self.assertEqual(order.payment_status,'paid');self.assertEqual(order.voucher_use.amount,10)
        code.refresh_from_db();self.assertIsNotNone(code.redeemed_at)
        self.assertIn('/track-order/',response.json()['payment_url'])
        with self.assertRaises(ValidationError):self.order('reuse',{**self.body,'voucher_code':code.code})

    def test_unpaid_cancel_releases_voucher_and_wrong_email_rejected(self):
        code=self.voucher(5)
        with self.assertRaises(ValidationError):self.order('bad',{**self.body,'email':'other@example.invalid','voucher_code':code.code})
        order=self.order(body={**self.body,'voucher_code':code.code})
        services.finalize_cancel(order.pk)
        self.assertEqual(vouchers.validate(code.code,self.body['email']).pk,code.pk)
        replacement=self.order('retry',{**self.body,'voucher_code':code.code});self.assertEqual(replacement.total,5)

    def test_return_automatically_issues_voucher_after_receipt(self):
        order=self.order();payments.confirm_demo(order.pk)
        order.refresh_from_db();order.fulfilment_status='delivered';order.delivered_at=timezone.now();order.save()
        services.request_return(order.pk,'Return',refund_preference='voucher')
        services.decide_return(order.pk,'approved','Accepted',self.staff)
        self.assertFalse(Voucher.objects.exists())
        services.decide_return(order.pk,'received','Received',self.staff)
        order.refresh_from_db();self.assertEqual(order.return_request.status,'refunded')
        self.assertEqual(order.issued_voucher.amount,10);self.assertEqual(order.return_request.settlement_reference,order.issued_voucher.code)
        self.assertEqual(order.refund.status,'succeeded')

    def package(self):
        product=Product.objects.create(name='Grocery package',slug='grocery-package',category=self.category,regular_price=14,is_package=True,is_published=True,stock_confirmed=True)
        package=Package.objects.create(product=product,slot=1,discount_type='percent',discount_value=10)
        PackageItem.objects.create(package=package,product=self.a,quantity=2)
        PackageItem.objects.create(package=package,product=self.b,quantity=2)
        return package

    def test_package_price_weight_and_shared_inventory_snapshot(self):
        package=self.package();product=package.product
        self.assertEqual(product.price,Decimal('12.60'));self.assertEqual(product.weight_grams,1300);self.assertEqual(product.effective_stock,5)
        body={**self.body,'items':[{'product_id':product.pk,'quantity':2},{'product_id':self.a.pk,'quantity':1}]}
        order=self.order(body=body);self.assertEqual(order.subtotal,Decimal('29.20'));self.assertEqual(order.total_weight_grams,2750)
        self.a.refresh_from_db();self.b.refresh_from_db();self.assertEqual(self.a.stock,25);self.assertEqual(self.b.stock,6)
        package.components.filter(product=self.b).update(quantity=1)
        services.finalize_cancel(order.pk)
        self.a.refresh_from_db();self.b.refresh_from_db();self.assertEqual(self.a.stock,30);self.assertEqual(self.b.stock,10)

    def test_package_and_separate_items_cannot_oversell_component(self):
        package=self.package()
        body={**self.body,'items':[{'product_id':package.product_id,'quantity':5},{'product_id':self.b.pk,'quantity':1}]}
        with self.assertRaises(ValidationError):self.order(body=body)
        response=self.client.post('/api/cart/quote/',json.dumps(body),content_type='application/json')
        self.assertEqual(response.status_code,400)
        self.assertEqual(Order.objects.count(),0)

    def test_package_admin_upload_publish_banner_and_details(self):
        self.client.force_login(self.staff)
        image=io.BytesIO();Image.new('RGB',(1000,700),'orange').save(image,format='PNG')
        body={'product-name':'Weekly package','product-slug':'weekly-package','product-category':self.category.pk,'product-is_published':'on','product-is_active':'on',
            'product-banner':SimpleUploadedFile('banner.png',image.getvalue(),content_type='image/png'),
            'slot':1,'subtitle':'This week','tagline':'Our grocery selection','discount_type':'amount','discount_value':'2',
            'items-TOTAL_FORMS':'2','items-INITIAL_FORMS':'0','items-MIN_NUM_FORMS':'1','items-MAX_NUM_FORMS':'50',
            'items-0-product':self.a.pk,'items-0-quantity':'2','items-1-product':self.b.pk,'items-1-quantity':'1'}
        response=self.client.post('/admin/packages/',body)
        self.assertEqual(response.status_code,302,response.content[:2500])
        product=Package.objects.get().product
        self.assertEqual(product.price,9);self.assertEqual((product.main_image.width,product.main_image.height),(867,441))
        self.assertContains(self.client.get('/'),'weekly-package')
        self.assertContains(self.client.get('/product-detail/?product=weekly-package'),'2 x Rice')
