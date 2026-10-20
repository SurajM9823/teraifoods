import json
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from catalog.models import Category, Product
from catalog.services import adjust_stock, reserve_order
from .forms import WeightBandForm, DeliveryPolicyForm
from .models import WeightBand, DeliveryPolicy
from .services import quote_delivery


class DeliveryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('delivery-customer')
        self.staff = get_user_model().objects.create_user('delivery-admin', is_staff=True, is_superuser=True)
        self.product = Product.objects.create(name='Weighted product', slug='weighted-product',
            regular_price=Decimal('4.00'), category=Category.objects.first(), is_published=True)
        adjust_stock(self.product.pk, 100, reason='Initial count', actor=self.staff, key='weight-initial', kind='initial')
        self.small = WeightBand.objects.create(max_weight_grams=300, charge=Decimal('2.50'))
        self.large = WeightBand.objects.create(max_weight_grams=2000, charge=Decimal('5.00'))

    def test_default_weight_and_default_estimate(self):
        self.assertEqual(self.product.weight, Decimal('150'))
        self.assertEqual(self.product.weight_unit, 'g')
        self.assertEqual(self.product.weight_grams, Decimal('150'))
        result = quote_delivery([self.product], {self.product.pk:1})
        self.assertEqual((result['minimum_days'],result['maximum_days']), (2,4))

    def test_inclusive_boundary_quantities_and_kg_conversion(self):
        result = quote_delivery([self.product], {self.product.pk:2})
        self.assertEqual(result['weight_grams'], Decimal('300'))
        self.assertEqual(result['charge'], Decimal('2.50'))
        result = quote_delivery([self.product], {self.product.pk:3})
        self.assertEqual(result['charge'], Decimal('5.00'))
        self.product.weight, self.product.weight_unit = Decimal('0.150'), 'kg'
        self.assertEqual(quote_delivery([self.product], {self.product.pk:2})['charge'], Decimal('2.50'))

    def test_mixed_basket_weights(self):
        other = Product.objects.create(name='Kilogram product', slug='kilogram-product',
            regular_price=2, weight=Decimal('0.5'), weight_unit='kg')
        result = quote_delivery([self.product,other], {self.product.pk:2,other.pk:2})
        self.assertEqual(result['weight_grams'], Decimal('1300'))
        self.assertEqual(result['charge'], Decimal('5.00'))

    def test_no_band_does_not_assume_free_shipping(self):
        with self.assertRaises(ValidationError):
            quote_delivery([self.product], {self.product.pk:20})
        self.small.is_active = False
        self.small.save()
        self.assertEqual(quote_delivery([self.product], {self.product.pk:1})['charge'], Decimal('5.00'))
        self.large.is_active = False
        self.large.save()
        with self.assertRaises(ValidationError):
            quote_delivery([self.product], {self.product.pk:1})

    def test_uk_coverage_only(self):
        for country in ('GB', 'UK'):
            self.assertEqual(quote_delivery([self.product], {self.product.pk:1},country=country)['country'], 'GB')
        with self.assertRaises(ValidationError):
            quote_delivery([self.product], {self.product.pk:1},country='US')

    def test_admin_weight_units_and_duplicate_limits(self):
        form = WeightBandForm(dict(upper_weight='3',unit='kg',charge='6.25',is_active='on'))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().max_weight_grams, Decimal('3000'))
        duplicate = WeightBandForm(dict(upper_weight='3000',unit='g',charge='7',is_active='on'))
        self.assertFalse(duplicate.is_valid())
        invalid = DeliveryPolicyForm(dict(minimum_days=5,maximum_days=2))
        self.assertFalse(invalid.is_valid())

    def test_admin_settings_authorization_and_edit(self):
        self.assertEqual(self.client.get('/admin/delivery/').status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/admin/delivery/').status_code, 200)
        response = self.client.post('/admin/delivery/', dict(action='policy',minimum_days=3,maximum_days=5))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(DeliveryPolicy.objects.get(pk=1).maximum_days, 5)
        self.assertEqual(quote_delivery([self.product], {self.product.pk:1})['minimum_days'], 3)

    def test_quote_ignores_client_prices_and_weights(self):
        response = self.client.post('/api/cart/quote/', json.dumps({'items':[
            {'product_id':self.product.pk,'quantity':2,'price':'0.01','weight':1}],
            'delivery_charge':'0.00','total_weight_grams':1}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()
        self.assertEqual(Decimal(data['total_weight_grams']), Decimal('300'))
        self.assertEqual(data['subtotal'], '8.00')
        self.assertEqual(data['delivery_charge'], '2.50')
        self.assertEqual(data['total'], '10.50')

    def test_order_snapshots_remain_after_admin_edits(self):
        order = reserve_order(self.user, [{'product_id':self.product.pk,'quantity':2}], 'weighted-checkout')
        self.assertEqual(order.total, Decimal('10.50'))
        self.assertEqual(order.total_weight_grams, Decimal('300'))
        self.product.weight = 900
        self.product.save()
        self.small.charge = 9
        self.small.save()
        order.refresh_from_db()
        self.assertEqual(order.delivery_charge, Decimal('2.50'))
        self.assertEqual(order.lines.get().unit_weight_grams, Decimal('150'))
        self.assertEqual(reserve_order(self.user,[{'product_id':self.product.pk,'quantity':2}], 'weighted-checkout').pk, order.pk)

    def test_missing_rate_rolls_back_stock_reservation(self):
        with self.assertRaises(ValidationError):
            reserve_order(self.user,[{'product_id':self.product.pk,'quantity':20}], 'too-heavy')
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 100)

    def test_database_rejects_invalid_weights_and_prices(self):
        for values in ({'weight':0},{'weight':-1},{'weight_unit':'lb'}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Product.objects.filter(pk=self.product.pk).update(**values)
        with self.assertRaises(IntegrityError), transaction.atomic():
            WeightBand.objects.create(max_weight_grams=500,charge=-1)
