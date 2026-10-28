import hashlib
import hmac
import json
import os
import runpy
import time
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils import timezone

from catalog.models import Order, Product
from . import payments, tests as fixtures
from .checks import stripe_configuration
from .models import Payment, ProviderEvent, Refund
from .stripe_config import validate


class ConfigurationTests(SimpleTestCase):
    def test_environment_selection_never_falls_back(self):
        path = Path(settings.BASE_DIR) / 'config/settings/orders.py'
        for selected in ('test', 'live', '', 'invalid'):
            with self.subTest(mode=selected), patch.dict(os.environ, {
                'STRIPE_MODE': selected,
                'STRIPE_TEST_SECRET_KEY': 'rk_test_fake', 'STRIPE_LIVE_SECRET_KEY': 'rk_live_fake',
                'STRIPE_TEST_PUBLISHABLE_KEY': 'pk_test_fake', 'STRIPE_LIVE_PUBLISHABLE_KEY': 'pk_live_fake',
                'STRIPE_TEST_WEBHOOK_SECRET': 'whsec_test', 'STRIPE_LIVE_WEBHOOK_SECRET': 'whsec_live',
            }, clear=True):
                config = runpy.run_path(str(path))
                expected = selected in ('test', 'live')
                self.assertEqual(config['STRIPE_SECRET_KEY'], f'rk_{selected}_fake' if expected else '')
                self.assertEqual(config['STRIPE_PUBLISHABLE_KEY'], f'pk_{selected}_fake' if expected else '')
                self.assertEqual(config['STRIPE_WEBHOOK_SECRET'], f'whsec_{selected}' if expected else '')
        with patch.dict(os.environ, {'STRIPE_MODE': 'live', 'STRIPE_TEST_SECRET_KEY': 'sk_test_fake'}, clear=True):
            self.assertEqual(runpy.run_path(str(path))['STRIPE_SECRET_KEY'], '')

    @override_settings(STRIPE_MODE='live', ORDER_PAYMENT_MODE='stripe', STRIPE_SECRET_KEY='rk_live_fake',
                       STRIPE_PUBLISHABLE_KEY='pk_live_fake', STRIPE_WEBHOOK_SECRET='whsec_fake',
                       ORDER_PUBLIC_ORIGIN='https://teraifoods.co.uk')
    def test_keys_origin_and_deploy_checks(self):
        validate()
        with patch('orders.payments.stripe.StripeClient') as sdk:
            payments.client()
            sdk.assert_called_once_with('rk_live_fake', max_network_retries=2)
        self.assertEqual(stripe_configuration(None), [])
        for values in ({'STRIPE_MODE': ''}, {'STRIPE_MODE': 'invalid'}, {'STRIPE_SECRET_KEY': ''},
                       {'STRIPE_SECRET_KEY': 'rk_test_fake'}, {'STRIPE_SECRET_KEY': 'sk_live_'},
                       {'STRIPE_PUBLISHABLE_KEY': 'pk_test_fake'}, {'STRIPE_PUBLISHABLE_KEY': ''},
                       {'STRIPE_WEBHOOK_SECRET': ''}, {'STRIPE_SECRET_KEY': 'rk_live_...'},
                       {'ORDER_PUBLIC_ORIGIN': 'http://teraifoods.co.uk'},
                       {'ORDER_PUBLIC_ORIGIN': 'https://teraifoods.co.uk/path'}):
            with self.subTest(fields=list(values)), override_settings(**values):
                with self.assertRaises(ValidationError):
                    validate()
                self.assertTrue(stripe_configuration(None))


@override_settings(STRIPE_MODE='live', ORDER_PAYMENT_MODE='stripe', STRIPE_SECRET_KEY='rk_live_fake',
                   STRIPE_PUBLISHABLE_KEY='pk_live_fake', STRIPE_WEBHOOK_SECRET='whsec_live_fake',
                   ORDER_PUBLIC_ORIGIN='https://teraifoods.co.uk')
class LivePaymentTests(TestCase):
    setUp = fixtures.OrderTests.setUp
    create = fixtures.OrderTests.create
    post = fixtures.OrderTests.post

    def event(self, order, kind='checkout.session.completed', event_id='evt_live', **values):
        event = fixtures.OrderTests.event(self, order, **values)
        event.update(id=event_id, type=kind, livemode=True)
        return event

    def paid(self):
        order = self.create()
        payments.apply_event(self.event(order))
        order.refresh_from_db()
        return order

    def session(self, order, **values):
        return stripe.checkout.Session.construct_from(dict(id='cs_live_fake', url=None,
            client_secret='cs_live_fake_secret_dummy', status='open', payment_status='unpaid',
            livemode=True, currency='gbp', amount_total=1199,
            metadata={'order_id': str(order.public_id)}, **values), 'rk_live_fake')

    def signed(self, event, secret=b'whsec_live_fake', stamp=None):
        body = json.dumps(event)
        stamp = str(stamp or int(time.time()))
        signature = hmac.new(secret, (stamp + '.' + body).encode(), hashlib.sha256).hexdigest()
        return Client(enforce_csrf_checks=True).post('/api/orders/webhook/stripe/', body,
            content_type='application/json', HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}')

    def refund_data(self, order, status='succeeded', amount=1199):
        return dict(id='re_live_fake', status=status, amount=amount, currency='gbp',
                    payment_intent=order.payment.intent_id, metadata={'order_id': str(order.public_id)})

    def test_live_guest_checkout_and_retry_no_secret_disclosure(self):
        with patch('orders.payments.stripe.StripeClient') as sdk:
            gateway = sdk.return_value
            gateway.v1.checkout.sessions.create.side_effect = lambda **kwargs: self.session(Order.objects.get())
            gateway.v1.checkout.sessions.retrieve.side_effect = lambda *args: self.session(Order.objects.get())
            for _ in range(2):
                response = self.post('/api/orders/checkout/', self.body, HTTP_IDEMPOTENCY_KEY='live-checkout')
                self.assertEqual(response.status_code, 201, response.content)
                self.assertFalse(response.json()['test_mode'])
                self.assertEqual(response.json()['publishable_key'], 'pk_live_fake')
                self.assertNotIn('rk_live_fake', response.content.decode())
                self.assertNotIn('whsec_live_fake', response.content.decode())
            self.assertEqual(Order.objects.count(), 1)
            self.assertEqual(Payment.objects.get().stripe_mode, 'live')
            self.assertIsNone(Order.objects.get().customer_id)
            gateway.v1.checkout.sessions.create.assert_called_once()
            params = gateway.v1.checkout.sessions.create.call_args.kwargs['params']
            self.assertEqual(params['line_items'][0]['price_data']['currency'], 'gbp')
            self.assertEqual(params['line_items'][0]['price_data']['unit_amount'], 1199)
            self.assertEqual(params['ui_mode'], 'elements')
            self.assertEqual(Product.objects.get(pk=self.product.pk).stock, 18)

    def test_permission_error_is_sanitized_and_preserves_guest_retry(self):
        with patch('orders.payments.stripe.StripeClient') as sdk:
            gateway = sdk.return_value
            gateway.v1.checkout.sessions.create.side_effect = stripe.PermissionError('rk_live_fake forbidden')
            response = self.post('/api/orders/checkout/', self.body, HTTP_IDEMPOTENCY_KEY='permission')
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('rk_live_fake', response.content.decode())
            order = Order.objects.get()
            self.assertEqual(self.client.get(f'/api/orders/{order.public_id}/').status_code, 200)
            gateway.v1.checkout.sessions.create.side_effect = lambda **kwargs: self.session(order)
            self.assertEqual(self.post('/api/orders/checkout/', self.body, HTTP_IDEMPOTENCY_KEY='permission').status_code, 201)
            self.assertEqual(Order.objects.count(), 1)

    def test_signatures_modes_and_idempotent_notifications(self):
        order = self.create()
        event = self.event(order)
        self.assertEqual(self.signed(event, secret=b'wrong').status_code, 400)
        self.assertEqual(self.signed(event, stamp=int(time.time())-600).status_code, 400)
        self.assertEqual(self.signed({**event, 'livemode': False}).status_code, 400)
        for _ in range(2):
            self.assertEqual(self.signed(event).status_code, 200)
        self.assertEqual(self.signed(self.event(order, event_id='evt_duplicate_object')).status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.events.filter(event_type='payment_confirmed').count(), 1)
        self.assertEqual(order.events.get(event_type='payment_confirmed').notification.recipient, order.email)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock, 18)
        from .tasks import dispatch_pending
        channel = MagicMock(group_send=AsyncMock())
        with patch('orders.tasks.get_channel_layer', return_value=channel), patch('orders.tasks.send_notification.delay'):
            dispatch_pending()
            dispatch_pending()
        confirmed = order.events.get(event_type='payment_confirmed')
        channel.group_send.assert_any_await(f'order.{order.public_id}', {'type': 'order.changed', 'version': confirmed.version})
        self.assertEqual(channel.group_send.await_count, order.events.count())

    def test_amount_currency_intent_and_session_mismatches(self):
        order = self.create()
        Payment.objects.filter(order=order).update(session_id='cs_test_1')
        for values in ({'amount_total': 1}, {'currency': 'usd'}, {'payment_intent': ''}, {'id': 'cs_other'}):
            with self.subTest(values=values), self.assertRaises(ValidationError):
                payments.apply_event(self.event(order, **values))
        self.assertFalse(ProviderEvent.objects.exists())
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')

    def test_unpaid_completion_then_async_success(self):
        order = self.create()
        payments.apply_event(self.event(order, payment_status='unpaid'))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')
        payments.apply_event(self.event(order, 'checkout.session.async_payment_succeeded', 'evt_async'))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')

    def test_failed_expired_and_repeated_snapshots(self):
        order = self.create()
        for index in range(2):
            payments.apply_event(self.event(order, 'checkout.session.async_payment_failed', f'fail-{index}'))
        self.assertEqual(order.events.filter(event_type='payment_failed').count(), 1)
        for index in range(2):
            payments.apply_event(self.event(order, 'checkout.session.expired', f'expire-{index}'))
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'expired')
        self.assertEqual(order.fulfilment_status, 'cancelled')
        self.assertEqual(order.events.filter(event_type='cancelled').count(), 1)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock, 20)

    def test_historical_test_payment_cannot_use_live_api_or_webhook(self):
        with override_settings(STRIPE_MODE='test'):
            order = self.create()
        with patch('orders.payments.client') as gateway:
            for operation in (lambda: payments.create_session(order), lambda: payments.cancel_with_provider(order.pk),
                              lambda: payments.apply_event(self.event(order))):
                with self.assertRaises(ValidationError):
                    operation()
            gateway.return_value.v1.checkout.sessions.create.assert_not_called()
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'pending')

    def test_refund_webhook_before_response_and_stale_pending(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=order.total, reason='Cancel')
        data = self.refund_data(order)
        for index, kind in enumerate(('refund.created', 'refund.updated')):
            response = self.signed(dict(id=f'evt_refund_{index}', type=kind, livemode=True, data={'object': data}))
            self.assertEqual(response.status_code, 200, response.content)
        payments.apply_refund(refund.pk, {**data, 'status': 'pending'})
        order.refresh_from_db(); refund.refresh_from_db()
        self.assertEqual(refund.provider_id, 're_live_fake')
        self.assertEqual(order.payment_status, 'refunded')
        self.assertEqual(order.events.filter(event_type='refund_succeeded').count(), 1)

    def test_partial_refund_and_failure_do_not_mark_fully_refunded(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=Decimal('3.00'), reason='Partial')
        data = self.refund_data(order, amount=300)
        with patch('orders.payments.stripe.StripeClient') as sdk:
            sdk.return_value.v1.refunds.create.return_value = stripe.Refund.construct_from(data, 'rk_live_fake')
            payments.process_refund(refund.pk)
            payments.process_refund(refund.pk)
            sdk.return_value.v1.refunds.create.assert_called_once()
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.refund_status, 'partially_refunded')

    def test_refund_failure_and_no_over_refund(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=Decimal('12.00'), reason='Invalid')
        with patch('orders.payments.client') as gateway:
            with self.assertRaises(ValidationError):
                payments.process_refund(refund.pk)
            gateway.assert_not_called()
        refund.amount = order.total; refund.save()
        data = self.refund_data(order, status='failed')
        response = self.signed(dict(id='evt_failed', type='refund.failed', livemode=True, data={'object': data}))
        self.assertEqual(response.status_code, 200)
        payments.apply_refund(refund.pk, {**data, 'status': 'pending'})
        order.refresh_from_db(); refund.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(refund.status, 'failed')
        self.assertEqual(order.refund_status, 'failed')
        with patch('orders.payments.client') as gateway:
            payments.process_refund(refund.pk)
            gateway.assert_not_called()

    def test_refund_restricted_permission_failure_can_retry_same_request(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=order.total, reason='Cancel')
        with patch('orders.payments.stripe.StripeClient') as sdk:
            sdk.return_value.v1.refunds.create.side_effect = stripe.PermissionError('forbidden')
            with self.assertRaises(stripe.PermissionError):
                payments.process_refund(refund.pk)
        refund.refresh_from_db()
        self.assertEqual(refund.status, 'pending')
        self.assertEqual(refund.provider_id, '')

    def test_refund_rejects_wrong_intent_currency_amount(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=order.total, reason='Cancel')
        for changes in ({'payment_intent': 'pi_other'}, {'amount': 1}, {'currency': 'usd'}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                payments.apply_refund(refund.pk, {**self.refund_data(order), **changes})

    def test_dashboard_refund_is_matched_by_intent(self):
        order = self.paid()
        data = self.refund_data(order)
        data['metadata'] = {}
        event = dict(id='dashboard_refund', type='refund.created', livemode=True, data={'object': data})
        self.assertEqual(self.signed(event).status_code, 200)
        self.assertEqual(self.signed(event).status_code, 200)
        self.assertEqual(Refund.objects.count(), 1)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'refunded')

    def test_live_cancel_reconciles_paid_session_and_queues_refund(self):
        order = self.create()
        Payment.objects.filter(order=order).update(session_id='cs_test_1')
        data = self.event(order)['data']['object']
        data.update(status='complete', livemode=True)
        with patch('orders.payments.stripe.StripeClient') as sdk:
            sdk.return_value.v1.checkout.sessions.retrieve.return_value = stripe.checkout.Session.construct_from(data, 'rk_live_fake')
            payments.cancel_with_provider(order.pk)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.fulfilment_status, 'cancelled')
        self.assertEqual(order.refund_status, 'pending')

    def test_live_session_response_mode_and_total_are_checked_before_saving(self):
        order = self.create()
        for field, value in (('livemode', False), ('amount_total', 1), ('currency', 'usd')):
            session = self.session(order)
            setattr(session, field, value)
            with self.subTest(field=field), patch('orders.payments.stripe.StripeClient') as sdk:
                sdk.return_value.v1.checkout.sessions.create.return_value = session
                with self.assertRaises(ValidationError):
                    payments.create_session(order, embedded=True)
            self.assertEqual(Payment.objects.get(order=order).session_id, '')

    def test_failed_refund_after_success_restores_payment_state(self):
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=order.total, reason='Return')
        data = self.refund_data(order)
        payments.apply_refund(refund.pk, data)
        response = self.signed(dict(id='evt_returned_refund', type='refund.failed', livemode=True,
                                   data={'object': {**data, 'status': 'failed'}}))
        self.assertEqual(response.status_code, 200)
        payments.apply_refund(refund.pk, data)
        order.refresh_from_db(); refund.refresh_from_db()
        self.assertEqual(order.payment_status, 'paid')
        self.assertEqual(order.refund_status, 'failed')
        self.assertEqual(refund.status, 'failed')

    def test_unmatched_refund_is_not_acknowledged_before_payment_arrives(self):
        order = self.create()
        data = dict(id='re_early', amount=1199, currency='gbp', payment_intent='pi_test_1', status='succeeded', metadata={})
        event = dict(id='evt_early', type='refund.created', livemode=True, data={'object': data})
        self.assertEqual(self.signed(event).status_code, 400)
        self.assertFalse(ProviderEvent.objects.filter(event_id='evt_early').exists())
        payments.apply_event(self.event(order))
        self.assertEqual(self.signed(event).status_code, 200)

    def test_partial_refund_cancellation_preserves_balance_and_return_cannot_double_pay(self):
        from . import services
        order = self.paid()
        refund = Refund.objects.create(order=order, amount=Decimal('3.00'), reason='Partial')
        payments.apply_refund(refund.pk, self.refund_data(order, amount=300))
        services.finalize_cancel(order.pk)
        order.refresh_from_db()
        self.assertEqual(order.refund_status, 'partially_refunded')
        self.assertEqual(Refund.objects.count(), 1)
        # A previously refunded delivered order cannot also receive a full voucher.
        Order.objects.filter(pk=order.pk).update(fulfilment_status='delivered', delivered_at=timezone.now())
        services.request_return(order.pk, 'Damaged', refund_preference='voucher')
        services.decide_return(order.pk, 'approved', 'Approved', self.staff)
        with self.assertRaises(ValidationError):
            services.decide_return(order.pk, 'received', 'Received', self.staff)
