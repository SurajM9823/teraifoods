import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta
import stripe
from catalog.models import Category, Product, Order
from delivery.models import WeightBand
from .models import Address, Payment


@override_settings(STRIPE_SECRET_KEY='sk_test_fake', STRIPE_PUBLISHABLE_KEY='pk_test_fake',
                   ORDER_PAYMENT_MODE='stripe', ORDER_PUBLIC_ORIGIN='http://testserver')
class EmbeddedPaymentTests(TestCase):
    def setUp(self):
        category = Category.objects.create(name='Elements', slug='elements')
        self.product = Product.objects.create(name='Rice', slug='elements-rice', category=category,
            regular_price=4, stock=100, stock_confirmed=True, is_published=True)
        WeightBand.objects.create(max_weight_grams=2000, charge=2)
        self.body = {'email': 'buyer@example.com', 'address': {'name': 'Buyer', 'phone': '07700900123',
            'line1': '1 Test Street', 'city': 'London', 'postcode': 'SW1A 1AA'},
            'items': [{'product_id': self.product.pk, 'quantity': 2}], 'total': '.01', 'save_card': True}
        self.user = get_user_model().objects.create_user('elements-user', email='buyer@example.com')
        self.gateway_patch = patch('orders.payments.client')
        self.gateway = self.gateway_patch.start().return_value
        self.addCleanup(self.gateway_patch.stop)
        self.gateway.v1.checkout.sessions.create.side_effect = self.create_session
        self.gateway.v1.checkout.sessions.retrieve.side_effect = lambda *args: self.session

    def create_session(self, **kwargs):
        params = kwargs['params']
        self.session = stripe.checkout.Session.construct_from(dict(id='cs_test_elements', url=None,
            client_secret='cs_test_elements_secret_fake', status='open', payment_status='unpaid',
            livemode=False, currency='gbp', amount_total=1000, metadata=params['metadata']), 'sk_test_fake')
        return self.session

    def post(self, url, body=None):
        return self.client.post(url, json.dumps(body or {}), content_type='application/json', HTTP_IDEMPOTENCY_KEY='elements-attempt')

    def start(self):
        response = self.post('/api/orders/checkout/', self.body)
        self.assertEqual(response.status_code, 201, response.content)
        return response, Order.objects.get()

    def test_guest_embed_totals_idempotency_no_card_saving_or_secret_persistence(self):
        response, order = self.start()
        self.assertEqual(response.json()['client_secret'], self.session.client_secret)
        self.assertIn('no-store', response['Cache-Control'])
        params = self.gateway.v1.checkout.sessions.create.call_args.kwargs['params']
        self.assertEqual(params['ui_mode'], 'elements')
        self.assertEqual(params['line_items'][0]['price_data']['unit_amount'], 1000)
        for key in ('customer', 'customer_creation', 'saved_payment_method_options', 'success_url', 'payment_method_types'):
            self.assertNotIn(key, params)
        self.assertNotIn('setup_future_usage', params['payment_intent_data'])
        self.assertNotIn('client_secret', Payment.objects.values().get())
        self.assertNotIn('cs_test_elements_secret_fake', str(dict(self.client.session)))
        self.post('/api/orders/checkout/', self.body)
        self.assertEqual(Order.objects.count(), 1)
        self.gateway.v1.checkout.sessions.create.assert_called_once()
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock, 98)

    def test_authenticated_access_and_guest_isolation(self):
        self.client.force_login(self.user)
        _, order = self.start()
        self.assertEqual(order.customer_id, self.user.pk)
        self.assertEqual(self.post(f'/api/orders/{order.public_id}/payment/').status_code, 200)
        outsider = Client()
        for route in ('payment', 'payment-status'):
            self.assertEqual(outsider.post(f'/api/orders/{order.public_id}/{route}/', '{}', content_type='application/json').status_code, 403)

    def test_frontend_success_does_not_pay_and_server_reconciliation_is_idempotent(self):
        _, order = self.start()
        url = f'/api/orders/{order.public_id}/payment-status/'
        self.post(url, {'paid': True})
        order.refresh_from_db(); self.assertEqual(order.payment_status, 'pending')
        self.session.payment_status = 'paid'; self.session.status = 'complete'
        self.session.payment_intent = 'pi_elements'
        self.post(url); self.post(url)
        order.refresh_from_db(); self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.events.filter(event_type='payment_confirmed').count(), 1)

    def test_reconcile_rejects_wrong_amount_and_live_mode(self):
        _, order = self.start()
        self.session.payment_status = 'paid'; self.session.amount_total = 1
        self.assertEqual(self.post(f'/api/orders/{order.public_id}/payment-status/').status_code, 400)
        self.session.amount_total = 1000; self.session.livemode = True
        self.assertEqual(self.post(f'/api/orders/{order.public_id}/payment-status/').status_code, 400)
        order.refresh_from_db(); self.assertEqual(order.payment_status, 'pending')

    def test_retry_after_provider_failure_reuses_order(self):
        self.gateway.v1.checkout.sessions.create.side_effect = stripe.APIConnectionError('Unavailable')
        self.assertEqual(self.post('/api/orders/checkout/', self.body).status_code, 503)
        self.gateway.v1.checkout.sessions.create.side_effect = self.create_session
        self.start()
        self.assertEqual(Order.objects.count(), 1)

    @override_settings(STRIPE_PUBLISHABLE_KEY='')
    def test_missing_configuration_does_not_reserve_inventory(self):
        self.assertEqual(self.post('/api/orders/checkout/', self.body).status_code, 400)
        self.assertFalse(Order.objects.exists())

    def test_expired_and_cancelled_orders_cannot_mount(self):
        _, order = self.start()
        Order.objects.filter(pk=order.pk).update(reservation_expires_at=timezone.now()-timedelta(minutes=1))
        self.assertEqual(self.post(f'/api/orders/{order.public_id}/payment/').status_code, 400)

    def test_pending_async_payment_cannot_release_stock(self):
        _, order = self.start()
        self.session.status = 'complete'
        response = self.post(f'/api/orders/{order.public_id}/action/', {'action': 'replace_payment'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock, 98)

    def test_address_explicit_save_dedup_edit_and_delete_are_owner_scoped(self):
        self.client.force_login(self.user)
        data = {**self.body['address'], 'is_default': True}
        first = self.post('/api/orders/addresses/', data).json()['address']
        self.post('/api/orders/addresses/', data)
        self.assertEqual(Address.objects.count(), 1)
        url = f"/api/orders/addresses/{first['id']}/"
        response = self.client.patch(url, json.dumps({**data, 'line1': '2 Test Street'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Address.objects.get().line1, '2 Test Street')
        self.assertEqual(Client().delete(url).status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 200)
        self.assertFalse(Address.objects.exists())
