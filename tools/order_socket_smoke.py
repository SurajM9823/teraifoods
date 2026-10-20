"""Exercise the local Compose HTTP -> Nginx -> ASGI -> Redis WebSocket path."""
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings.development')
import django
django.setup()
from django.conf import settings
from django.contrib.sessions.models import Session
from catalog.models import Order
from orders.services import guest_token
import requests
from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus

if not settings.DEBUG:
    raise SystemExit('Local-development diagnostic only.')

base='http://127.0.0.1:8080'
order=Order.objects.create(idempotency_key='diagnostic-'+uuid.uuid4().hex,request_digest='diagnostic',
    total=0,fulfilment_status='diagnostic',payment_method='diagnostic',recipient_name='Temporary local socket check')
browser=requests.Session()
try:
    response=browser.get(base+'/track-order/',timeout=15);response.raise_for_status()
    response=browser.post(base+'/api/orders/access/',json={'token':guest_token(order)},
        headers={'X-CSRFToken':browser.cookies['csrftoken']},timeout=15)
    response.raise_for_status()
    cookie='; '.join(f'{k}={v}' for k,v in browser.cookies.items())
    url=f'ws://127.0.0.1:8080/ws/orders/{order.public_id}/'
    with connect(url,origin=base,additional_headers={'Cookie':cookie},open_timeout=10) as socket:
        initial=json.loads(socket.recv(timeout=10))
        assert initial['order']['id']==str(order.public_id)
        Order.objects.filter(pk=order.pk).update(version=1)
        code=("from asgiref.sync import async_to_sync; from channels.layers import get_channel_layer; "
              f"async_to_sync(get_channel_layer().group_send)('order.{order.public_id}',"
              "{'type':'order.changed','version':1})")
        result=subprocess.run(['docker','compose','exec','-T','web','python','manage.py','shell','-c',code],
                              capture_output=True,text=True,timeout=30)
        assert result.returncode==0,'Redis broadcast command failed'
        assert json.loads(socket.recv(timeout=10))['order']['version']==1
    for origin,headers in [('https://untrusted.example',{'Cookie':cookie}),(base,{})]:
        try:
            with connect(url,origin=origin,additional_headers=headers,open_timeout=10):
                raise AssertionError('Unauthorized socket accepted')
        except InvalidStatus as exc:
            assert exc.response.status_code==403
    print('PASS: Docker guest session, WebSocket snapshot, Redis update, origin and access restrictions.')
finally:
    if browser.cookies.get(settings.SESSION_COOKIE_NAME):
        Session.objects.filter(session_key=browser.cookies[settings.SESSION_COOKIE_NAME]).delete()
    Order.objects.filter(pk=order.pk,idempotency_key=order.idempotency_key).delete()
