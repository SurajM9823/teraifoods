import json
from unittest.mock import patch
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.test import TransactionTestCase, override_settings
from django.conf import settings
from catalog.models import Category, Product
from delivery.models import WeightBand
from . import services


@override_settings(ALLOWED_HOSTS=['testserver'])
class OrderSocketTests(TransactionTestCase):
    def setUp(self):
        self.queue=patch('orders.tasks.dispatch_pending.apply_async')
        self.queue.start();self.addCleanup(self.queue.stop)
        product=Product.objects.create(name='Socket product',slug='socket-product',regular_price=4,
            category=Category.objects.create(name='Socket category',slug='socket-category'),stock=10,stock_confirmed=True,is_published=True)
        WeightBand.objects.create(max_weight_grams=1000,charge=2)
        self.order=services.create_order(AnonymousUser(),'socket-test',{
            'email':'socket@example.com','address':{'name':'Socket Guest','phone':'07700900123',
            'line1':'1 Test Street','city':'London','postcode':'SW1A1AA'},
            'items':[{'product_id':product.pk,'quantity':1}]},'socket-order')
        session=self.client.session
        services.grant_access(session,self.order);session.save()
        self.cookie=f'{settings.SESSION_COOKIE_NAME}={session.session_key}'.encode()

    async def connection(self,origin=b'http://testserver',cookie=True):
        from config.asgi import application
        app=ApplicationCommunicator(application,{'type':'websocket','path':f'/ws/orders/{self.order.public_id}/',
            'headers':[(b'origin',origin),(b'host',b'testserver')]+([(b'cookie',self.cookie)] if cookie else []),
            'query_string':b'','subprotocols':[]})
        await app.send_input({'type':'websocket.connect'})
        return app

    def test_guest_snapshot_sync_and_revocation(self):
        async def scenario():
            app=await self.connection()
            self.assertEqual((await app.receive_output(timeout=5))['type'],'websocket.accept')
            snapshot=json.loads((await app.receive_output(timeout=5))['text'])
            self.assertEqual(snapshot['order']['id'],str(self.order.public_id))
            await app.send_input({'type':'websocket.receive','text':'{"type":"sync"}'})
            self.assertEqual(json.loads((await app.receive_output(timeout=5))['text'])['order']['version'],self.order.version)
            @database_sync_to_async
            def revoke():
                self.order.guest_access_version+=1;self.order.save()
            await revoke()
            await app.send_input({'type':'websocket.receive','text':'{"type":"ping"}'})
            self.assertEqual((await app.receive_output(timeout=5))['code'],4403)
            await app.send_input({'type':'websocket.disconnect','code':1000})
            await app.wait()
        async_to_sync(scenario)()

    def test_unrelated_guest_and_cross_origin_cannot_subscribe(self):
        async def scenario():
            for origin,cookie in [(b'http://testserver',False),(b'https://attacker.example',True)]:
                app=await self.connection(origin,cookie)
                self.assertEqual((await app.receive_output(timeout=5))['type'],'websocket.close')
                await app.send_input({'type':'websocket.disconnect','code':1000})
                await app.wait()
        async_to_sync(scenario)()
