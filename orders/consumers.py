from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.core.exceptions import PermissionDenied
from catalog.models import Order
from .services import authorize
from .views import order_data


class OrderConsumer(AsyncJsonWebsocketConsumer):
    @database_sync_to_async
    def snapshot(self):
        # Reload the session on every event so logout/revocation is respected.
        session = self.scope['session']
        session._session_cache = session.load()
        order = Order.objects.get(public_id=self.scope['url_route']['kwargs']['public_id'])
        from django.contrib.auth import get_user
        from types import SimpleNamespace
        user = get_user(SimpleNamespace(session=session))
        authorize(order, user, session)
        return order_data(order)

    async def connect(self):
        self.group = 'order.' + str(self.scope['url_route']['kwargs']['public_id'])
        try:
            snapshot = await self.snapshot()
        except (Order.DoesNotExist, PermissionDenied):
            await self.close(code=4403)
            return
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({'type':'snapshot', 'order':snapshot})

    async def disconnect(self, code):
        if hasattr(self, 'group'):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if isinstance(content, dict) and content.get('type') in ('sync','ping'):
            await self.order_changed({})

    async def order_changed(self, event):
        try:
            snapshot = await self.snapshot()
        except (Order.DoesNotExist, PermissionDenied):
            await self.close(code=4403)
            return
        await self.send_json({'type':'snapshot','order':snapshot})
