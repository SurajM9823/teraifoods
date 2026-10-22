import hashlib
import hmac
import json
import time
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core import mail
from django.core.exceptions import ValidationError
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from catalog.models import Product, Category, Order, StockAudit
from catalog.services import adjust_stock
from delivery.models import WeightBand
from . import services, payments
from .models import Notification, Refund, Review, Address
from .tasks import send_notification


@override_settings(STRIPE_PUBLISHABLE_KEY='pk_test_unit_only', STRIPE_SECRET_KEY='sk_test_unit_test_only', STRIPE_WEBHOOK_SECRET='whsec_test_only',
                   ORDER_RETURN_DAYS=14, ORDER_PUBLIC_ORIGIN='http://testserver')
class OrderTests(TestCase):
    def setUp(self):
        self.staff=get_user_model().objects.create_user('order-admin',is_staff=True,is_superuser=True)
        self.user=get_user_model().objects.create_user('buyer')
        self.product=Product.objects.create(name='Order product',slug='order-product',regular_price='4.00',
            category=Category.objects.first(),is_published=True)
        adjust_stock(self.product.pk,20,reason='Counted',actor=self.staff,key='orders-test-stock',kind='initial')
        WeightBand.objects.create(max_weight_grams=2000,charge='3.99')
        self.body={'email':'guest@example.com','address':{'name':'Test Recipient','phone':'07700900123',
            'line1':'1 Test Street','city':'London','postcode':'sw1a1aa','country':'GB'},
            'items':[{'product_id':self.product.pk,'quantity':2,'price':'.01'}], 'total':'.02'}

    def create(self,key='checkout-one',user=None):
        return services.create_order(user or AnonymousUser(),'session-one',self.body,key)

    def paid(self,order):
        payments.apply_event(self.event(order))
        order.refresh_from_db()
        return order

    def event(self,order,**overrides):
        obj={'id':'cs_test_1','metadata':{'order_id':str(order.public_id)},'payment_status':'paid',
             'currency':'gbp','amount_total':1199,'payment_intent':'pi_test_1',**overrides}
        return {'id':'evt_test_1','type':'checkout.session.completed','livemode':False,'data':{'object':obj}}

    def post(self,url,data,**kwargs):
        return self.client.post(url,json.dumps(data),content_type='application/json',**kwargs)

    def grant(self,order):
        session=self.client.session;services.grant_access(session,order);session.save()

    def test_guest_checkout_calculates_totals_and_is_idempotent(self):
        order=self.create()
        self.assertIsNone(order.customer_id)
        self.assertEqual(order.total,Decimal('11.99'))
        self.assertEqual(order.total_weight_grams,Decimal('300'))
        self.assertEqual(order.address['postcode'],'SW1A 1AA')
        self.assertEqual(self.create().pk,order.pk)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock,18)
        self.assertEqual(StockAudit.objects.filter(adjustment_type='order').count(),1)
        self.body['items'][0]['quantity']=3
        with self.assertRaises(ValidationError):self.create()

    def test_product_and_address_snapshots_are_immutable(self):
        order=self.create(user=self.user)
        self.product.name='Renamed';self.product.weight=900;self.product.save()
        line=order.lines.get()
        self.assertEqual(line.product_name,'Order product')
        self.assertEqual(line.unit_weight_grams,150)
        self.assertEqual(line.unit_price,4)
        self.assertEqual(order.total,Decimal('11.99'))

    def test_checkout_api_creates_test_session_and_guest_access(self):
        with patch('orders.payments.client') as client:
            client.return_value.v1.checkout.sessions.create.side_effect=lambda **kw:SimpleNamespace(id='cs_test_1',url=None,client_secret='cs_test_1_secret_fake',status='open',livemode=False,currency='gbp',amount_total=1199,metadata=kw['params']['metadata'])
            response=self.post('/api/orders/checkout/',self.body,HTTP_IDEMPOTENCY_KEY='checkout-api')
        self.assertEqual(response.status_code,201,response.content)
        order=response.json()['order']
        self.assertEqual(self.client.get('/api/orders/'+order['id']+'/').status_code,200)
        self.assertEqual(Client().get('/api/orders/'+order['id']+'/').status_code,403)
        self.assertEqual(order['payment_status'],'pending')
        self.assertEqual(client.return_value.v1.checkout.sessions.create.call_args.kwargs['params']['line_items'][0]['price_data']['unit_amount'],1199)

    def test_guest_token_revocation_and_tampering(self):
        order=self.create();token=services.guest_token(order)
        response=self.post('/api/orders/access/',{'token':token})
        self.assertEqual(response.status_code,200)
        order.guest_access_version+=1;order.save()
        self.assertEqual(self.client.get(f'/api/orders/{order.public_id}/').status_code,403)
        self.assertEqual(self.post('/api/orders/access/',{'token':token+'x'}).status_code,403)

    def test_owner_history_is_private(self):
        owned=self.create(user=self.user)
        self.create('guest-other')
        self.client.force_login(self.user)
        self.assertEqual([o['id'] for o in self.client.get('/api/orders/history/').json()['orders']],[str(owned.public_id)])

    def test_webhook_rejects_unsigned_and_duplicate_paid_is_once(self):
        order=self.create()
        event=self.event(order);body=json.dumps(event);stamp=str(int(time.time()))
        signature=hmac.new(b'whsec_test_only',(stamp+'.'+body).encode(),hashlib.sha256).hexdigest()
        url='/api/orders/webhook/stripe/'
        self.assertEqual(self.client.post(url,body,content_type='application/json').status_code,400)
        for _ in range(2):
            result=self.client.post(url,body,content_type='application/json',HTTP_STRIPE_SIGNATURE=f't={stamp},v1={signature}')
            self.assertEqual(result.status_code,200,result.content)
        order.refresh_from_db()
        self.assertEqual(order.payment_status,'paid')
        self.assertEqual(order.events.filter(event_type='payment_confirmed').count(),1)
        self.assertEqual(order.lines.count(),1)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,18)

    def test_wrong_amount_and_live_payment_rejected(self):
        order=self.create()
        with self.assertRaises(ValidationError):payments.apply_event(self.event(order,amount_total=1))
        event=self.event(order);event['livemode']=True
        with self.assertRaises(ValidationError):payments.apply_event(event)
        order.refresh_from_db();self.assertEqual(order.payment_status,'pending')

    def test_late_expiry_does_not_cancel_paid_order(self):
        order=self.paid(self.create())
        event=self.event(order);event.update(id='evt_expired',type='checkout.session.expired')
        payments.apply_event(event)
        order.refresh_from_db();self.assertEqual(order.fulfilment_status,'placed')

    def test_cancellation_and_refund_restore_stock_once(self):
        order=self.paid(self.create())
        services.request_cancel(order.pk,'Changed mind')
        payments.cancel_with_provider(order.pk)
        payments.cancel_with_provider(order.pk)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,20)
        self.assertEqual(Refund.objects.count(),1)
        with patch('orders.payments.client') as client:
            client.return_value.v1.refunds.create.return_value=SimpleNamespace(id='re_test',status='succeeded')
            payments.process_refund(Refund.objects.get().pk)
            payments.process_refund(Refund.objects.get().pk)
            self.assertEqual(client.return_value.v1.refunds.create.call_count,1)
        order.refresh_from_db();self.assertEqual(order.refund_status,'refunded')
        for index,kind in enumerate(('checkout.session.completed','checkout.session.expired','checkout.session.async_payment_failed')):
            event=self.event(order);event.update(id=f'late-event-{index}',type=kind)
            payments.apply_event(event)
        order.refresh_from_db();self.assertEqual(order.payment_status,'refunded');self.assertEqual(order.refund_status,'refunded')

    def test_expired_reservation_reconciles_provider_before_releasing_stock(self):
        order=self.create();payment=order.payment;payment.session_id='cs_test_1';payment.save()
        with patch('orders.payments.client') as client:
            client.return_value.v1.checkout.sessions.retrieve.return_value=SimpleNamespace(status='open',payment_status='unpaid')
            payments.cancel_with_provider(order.pk,'Expired')
            client.return_value.v1.checkout.sessions.expire.assert_called_once()
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,20)

    def test_late_payment_for_cancelled_order_is_refunded(self):
        order=self.create();services.finalize_cancel(order.pk)
        self.paid(order)
        self.assertEqual(order.fulfilment_status,'cancelled')
        self.assertEqual(order.refund_status,'pending')
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,20)

    def test_state_machine_and_preparing_cancellation_rules(self):
        order=self.create()
        with self.assertRaises(ValidationError):services.transition(order.pk,'confirmed',self.staff)
        self.paid(order)
        with self.assertRaises(ValidationError):services.transition(order.pk,'delivered',self.staff)
        services.transition(order.pk,'confirmed',self.staff)
        services.transition(order.pk,'preparing',self.staff)
        with self.assertRaises(ValidationError):services.request_cancel(order.pk,'Too late')

    def delivered(self):
        order=self.paid(self.create())
        for state in ('confirmed','preparing','ready_for_dispatch','dispatched','out_for_delivery'):
            services.transition(order.pk,state,self.staff)
        with patch('orders.services.secrets.randbelow',return_value=123456):
            services.issue_delivery_pin(order.pk,self.staff)
        return order

    def test_delivery_pin_failures_commit_and_lock_after_five(self):
        order=self.delivered()
        for _ in range(5):
            with self.assertRaises(ValidationError):services.complete_delivery(order.pk,self.staff,pin='000000')
        order.refresh_from_db();self.assertEqual(order.delivery_pin_attempts,5)
        with self.assertRaises(ValidationError):services.complete_delivery(order.pk,self.staff,pin='123456')
        with patch('orders.services.secrets.randbelow',return_value=654321):
            services.issue_delivery_pin(order.pk,self.staff)
        services.complete_delivery(order.pk,self.staff,pin='654321')
        order.refresh_from_db();self.assertEqual(order.fulfilment_status,'delivered')
        self.assertEqual(order.delivery_pin_hash,'')
        self.assertEqual(order.delivery_attempts.filter(successful=True).count(),1)

    def test_returns_require_delivery_and_explicit_restock(self):
        order=self.delivered()
        with self.assertRaises(ValidationError):services.request_return(order.pk,'Damaged')
        services.complete_delivery(order.pk,self.staff,pin='123456')
        services.request_return(order.pk,'Damaged')
        services.decide_return(order.pk,'approved','Please return',self.staff)
        services.decide_return(order.pk,'received','Received damaged',self.staff,restock=False)
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,18)
        self.assertEqual(Refund.objects.count(),1)

    def test_saved_addresses_owner_only_and_one_default(self):
        self.client.force_login(self.user)
        data={**self.body['address'],'is_default':True}
        first=self.post('/api/orders/addresses/',data)
        self.assertEqual(first.status_code,201,first.content)
        data['line1']='2 Test Street'
        self.assertEqual(self.post('/api/orders/addresses/',data).status_code,201)
        self.assertEqual(Address.objects.filter(customer=self.user,is_default=True).count(),1)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.delete(f"/api/orders/addresses/{first.json()['address']['id']}/").status_code,404)

    def test_bank_return_admin_settlement_and_private_details(self):
        order=self.delivered();self.grant(order)
        url=f'/api/orders/{order.public_id}/action/'
        body={'action':'return','reason':'Damaged','refund_preference':'bank',
              'bank_details':{'account_name':'Test Buyer','sort_code':'12-34-56','account_number':'12345678'}}
        self.assertEqual(self.post(url,body).status_code,400)
        services.complete_delivery(order.pk,self.staff,pin='123456')
        self.assertEqual(Client().post(url,json.dumps(body),content_type='application/json').status_code,403)
        invalid={**body,'bank_details':{'account_name':'Test','sort_code':'bad','account_number':'1'}}
        self.assertEqual(self.post(url,invalid).status_code,400)
        response=self.post(url,body);self.assertEqual(response.status_code,200,response.content)
        self.assertNotIn('12345678',response.content.decode())
        ret=order.return_request
        self.assertNotIn('12345678',ret.bank_details_encrypted)
        self.assertEqual(ret.bank_details['account_number'],'12345678')
        self.assertEqual(self.post(url,body).status_code,200)
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/admin/orders/?returns=1'), 'Return: requested')
        admin=f'/admin/orders/{order.public_id}/'
        self.assertContains(self.client.get(admin),'12345678')
        self.client.post(admin,{'action':'return','status':'approved','reason':'Send it back'})
        with self.assertRaises(ValidationError):services.settle_return(order.pk,'bank','transfer-1',self.staff)
        self.client.post(admin,{'action':'return','status':'received','reason':'Received','restock':'on'})
        refund=Refund.objects.get(order=order)
        self.assertEqual(refund.status,'awaiting_manual')
        with patch('orders.payments.client') as gateway:
            payments.process_refund(refund.pk);gateway.assert_not_called()
        self.client.post(admin,{'action':'settle_return','method':'bank','reference':'transfer-1'})
        services.settle_return(order.pk,'bank','transfer-1',self.staff)
        order.refresh_from_db();ret.refresh_from_db()
        self.assertEqual(order.refund_status,'refunded');self.assertEqual(ret.status,'refunded')
        self.assertEqual(ret.bank_details_encrypted,'')
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,20)
        self.assertEqual(order.events.filter(event_type='return_refunded').count(),1)
        with self.assertRaises(ValidationError):services.settle_return(order.pk,'cash','another',self.staff)

    def test_voucher_return_and_original_provider_double_payment_guard(self):
        order=self.delivered();services.complete_delivery(order.pk,self.staff,pin='123456')
        services.request_return(order.pk,'Return please',refund_preference='voucher')
        services.decide_return(order.pk,'approved','Accepted',self.staff)
        services.decide_return(order.pk,'received','Received',self.staff)
        order.refresh_from_db()
        self.assertTrue(order.issued_voucher.code.startswith('TF-'))
        self.grant(order)
        data=self.client.get(f'/api/orders/{order.public_id}/').json()
        self.assertEqual(data['return_request']['reference'],order.issued_voucher.code)
        self.assertEqual(data['return_request']['method'],'voucher')
        self.assertTrue(data['items'][0]['can_review'])

    def test_provider_refund_cannot_be_manually_paid_again(self):
        order=self.delivered();services.complete_delivery(order.pk,self.staff,pin='123456')
        services.request_return(order.pk,'Return please')
        services.decide_return(order.pk,'approved','Accepted',self.staff)
        services.decide_return(order.pk,'received','Received',self.staff)
        with self.assertRaises(ValidationError):services.settle_return(order.pk,'bank','transfer-2',self.staff)

    def test_verified_guest_review_and_moderation(self):
        order=self.delivered();self.grant(order)
        body={'order_line':order.lines.get().pk,'rating':5,'text':'Actual review'}
        url=f'/api/orders/reviews/{self.product.pk}/'
        self.assertEqual(self.post(url,body).status_code,400)
        services.complete_delivery(order.pk,self.staff,pin='123456')
        response=self.post(url,body);self.assertEqual(response.status_code,201,response.content)
        self.assertEqual(self.post(url,body).status_code,400)
        self.assertEqual(self.client.get(url).json()['summary']['count'],0)
        self.client.force_login(self.staff)
        self.assertEqual(self.post(f"/api/orders/admin/reviews/{response.json()['id']}/",{'status':'approved'}).status_code,200)
        self.assertEqual(self.client.get(url).json()['summary']['count'],1)
        self.product.refresh_from_db();self.assertEqual(self.product.rating,5);self.assertEqual(self.product.review_count,1)

    def test_notification_once_and_pin_not_in_public_order(self):
        order=self.delivered();self.grant(order)
        event=order.events.get(event_type='delivery_pin')
        send_notification(event.notification.pk);send_notification(event.notification.pk)
        self.assertEqual(len(mail.outbox),1)
        self.assertIn('123456',mail.outbox[0].body)
        self.assertNotIn('123456',self.client.get(f'/api/orders/{order.public_id}/').content.decode())
        event.notification.refresh_from_db();self.assertEqual(event.notification.secret_payload,'')

    def test_admin_pages_and_actions_require_permissions(self):
        order=self.create()
        self.client.force_login(self.user)
        self.assertNotEqual(self.client.get('/admin/orders/').status_code,200)
        self.client.force_login(self.staff)
        for url in ('/admin/orders/',f'/admin/orders/{order.public_id}/','/admin/orders/reviews/'):
            self.assertEqual(self.client.get(url).status_code,200,url)

    def test_oversized_basket_rolls_back_without_order(self):
        self.body['items'][0]['quantity']=30
        with self.assertRaises(ValidationError):self.create()
        self.assertFalse(Order.objects.exists())
        self.assertEqual(Product.objects.get(pk=self.product.pk).stock,20)

    def test_csrf_required_for_checkout(self):
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/api/orders/checkout/',json.dumps(self.body),content_type='application/json').status_code,403)

    @override_settings(DEBUG=True, ORDER_PAYMENT_MODE='demo')
    def test_demo_confirmation_and_refund_are_local_idempotent_and_protected(self):
        response=self.post('/api/orders/checkout/',self.body,HTTP_IDEMPOTENCY_KEY='demo-checkout')
        self.assertEqual(response.status_code,201,response.content)
        order=Order.objects.get()
        self.assertEqual(order.payment_method,'demo')
        url=f'/api/orders/{order.public_id}/action/'
        for _ in range(2):
            self.assertEqual(self.post(url,{'action':'demo_payment'}).status_code,200)
        self.assertEqual(order.events.filter(event_type='payment_confirmed').count(),1)
        with override_settings(DEBUG=False):
            self.assertEqual(self.post(url,{'action':'demo_payment'}).status_code,400)
        services.finalize_cancel(order.pk)
        payments.process_refund(Refund.objects.get(order=order).pk)
        order.refresh_from_db();self.assertEqual(order.refund_status,'refunded')
