import json
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, Client, override_settings
from .models import BulkRequest, BulkReply
from .bulk import token
from .tasks import send_bulk_notification


@override_settings(ORDER_PUBLIC_ORIGIN='http://testserver')
class BulkTests(TestCase):
    def setUp(self):
        self.staff=get_user_model().objects.create_user('bulk-admin',is_staff=True,is_superuser=True)
        self.body={'company':'Test Grocer','contact_name':'Buyer','email':'buyer@example.invalid','phone':'07700900123',
            'address':'1 Example Street','city_postcode':'London SW1A 1AA','requested_date':'','notes':'Morning delivery',
            'items':[{'description':'Rice','sku':'RICE','quantity':20,'unit':'5kg bag','requested_price':'4.50'}]}

    def submit(self,body=None,key='bulk-one'):
        return self.client.post('/api/bulk/requests/',json.dumps(body or self.body),content_type='application/json',HTTP_IDEMPOTENCY_KEY=key)

    def test_submission_retries_and_secure_tracking(self):
        response=self.submit();self.assertEqual(response.status_code,201,response.content)
        row=BulkRequest.objects.get();self.assertEqual(row.items[0]['quantity'],20)
        self.assertEqual(self.submit().status_code,200);self.assertEqual(BulkRequest.objects.count(),1)
        self.assertEqual(BulkReply.objects.count(),1)
        self.assertEqual(self.submit({**self.body,'company':'Different'}).status_code,400)
        url=f'/api/bulk/requests/{row.public_id}/'
        self.assertEqual(self.client.get(url).status_code,200)
        other=Client();self.assertEqual(other.get(url).status_code,404)
        self.assertEqual(other.get('/api/bulk/requests/').json()['requests'],[])
        self.assertEqual(other.post('/api/bulk/access/',json.dumps({'token':token(row)}),content_type='application/json').status_code,200)
        self.assertEqual(other.get(url).json()['number'],row.number)
        self.assertEqual(other.post('/api/bulk/access/',json.dumps({'token':'bad'}),content_type='application/json').status_code,403)

    def test_validation_and_admin_permissions(self):
        self.assertEqual(self.submit({**self.body,'email':'invalid'}).status_code,400)
        self.assertEqual(self.submit({**self.body,'items':[]}).status_code,400)
        self.assertEqual(self.submit({**self.body,'requested_date':'2000-01-01'}).status_code,400)
        self.assertEqual(self.submit({**self.body,'items':[{'quantity':2,'description':'Rice','requested_price':'NaN'}]}).status_code,400)
        self.assertEqual(BulkRequest.objects.count(),0)
        self.submit();row=BulkRequest.objects.get()
        self.assertNotEqual(self.client.get('/admin/bulk-orders/').status_code,200)
        user=get_user_model().objects.create_user('limited',is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/bulk-orders/').status_code,403)
        self.assertEqual(self.client.post(f'/admin/bulk-orders/{row.public_id}/',{}).status_code,403)

    def test_admin_quote_history_email_and_customer_updates(self):
        self.submit();row=BulkRequest.objects.get();customer=self.client
        admin=Client();admin.force_login(self.staff)
        self.assertContains(admin.get('/admin/bulk-orders/'),row.number)
        url=f'/admin/bulk-orders/{row.public_id}/'
        self.assertContains(admin.get(url),'Morning delivery')
        quote={'version':'1','status':'quoted','message':'20 bags available. Total includes delivery.','quoted_total':'95.00',
               'delivery_terms':'Delivery within 4 days after payment','payment_terms':'Bank transfer on invoice'}
        invalid={**quote,'payment_terms':''}
        self.assertEqual(admin.post(url,invalid).status_code,200)
        row.refresh_from_db();self.assertEqual(row.status,'new')
        self.assertEqual(admin.post(url,quote).status_code,302)
        self.assertEqual(admin.post(url,quote).status_code,200) # stale retry does not duplicate reply
        row.refresh_from_db();self.assertEqual(row.status,'quoted');self.assertEqual(row.replies.count(),2)
        response=customer.get(f'/api/bulk/requests/{row.public_id}/').json()
        self.assertEqual(response['quoted_total'],'95.00');self.assertIn('20 bags',response['replies'][-1]['message'])
        reply=row.replies.latest('pk');send_bulk_notification(reply.pk);send_bulk_notification(reply.pk)
        self.assertEqual(len(mail.outbox),1);self.assertIn('95.00',mail.outbox[0].body);self.assertIn('#access=',mail.outbox[0].body)
        invalid={**quote,'version':'2','status':'completed'}
        admin.post(url,invalid);row.refresh_from_db();self.assertEqual(row.status,'quoted')

    def test_account_history_does_not_match_unverified_email(self):
        user=get_user_model().objects.create_user('buyer',email=self.body['email'])
        self.submit();self.client.force_login(user)
        self.submit(key='owned')
        other=Client();other.force_login(user)
        self.assertEqual(len(other.get('/api/bulk/requests/').json()['requests']),1)
